from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
CONFIG_PATH = HERE / "experiment_config.json"
RESPONSE_FORMAT_INSTRUCTIONS = """Return only one short line:
ANSWER: <answer>

If the supplied records are insufficient, return exactly:
ANSWER: INSUFFICIENT_EVIDENCE

Do not output JSON. Do not output evidence IDs, citations, explanations, reasoning, booleans, or extra lines."""


def load_config() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def workspace_root() -> Path:
    return Path(os.environ.get("CP_WORKSPACE", "/workspace/context-parallel-repro"))


def paths() -> dict[str, Path]:
    root = workspace_root()
    config = load_config()
    revision = config["model"]["revision"]
    return {
        "root": root,
        "model": root / "models" / "qwen" / revision,
        "dataset": root / "datasets" / config["source_benchmark"]["name"],
        "results": root / "results" / config["experiment_id"],
        "logs": root / "logs" / config["experiment_id"],
        "manifests": root / "manifests" / config["experiment_id"],
        "hf_cache": root / "hf_cache",
    }


def ensure_layout() -> dict[str, Path]:
    resolved = paths()
    for key in ("results", "logs", "manifests", "hf_cache"):
        resolved[key].mkdir(parents=True, exist_ok=True)
    return resolved


def sha256_file(path: Path, normalize_text: bool = False) -> str:
    data = path.read_bytes()
    if normalize_text:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def verify_frozen_artifacts() -> dict[str, str]:
    config = load_config()
    observed: dict[str, str] = {}
    for relative, expected in config["frozen_artifacts"].items():
        path = REPO_ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(f"frozen artifact is missing: {path}")
        digest = sha256_file(path, normalize_text=path.suffix in {".py", ".cu", ".txt"})
        if digest != expected:
            raise RuntimeError(
                f"frozen artifact hash mismatch for {relative}: expected {expected}, observed {digest}"
            )
        observed[relative] = digest
    return observed


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def write_manifest(name: str, payload: dict[str, Any]) -> Path:
    target = ensure_layout()["manifests"] / name
    atomic_write_json(
        target,
        {"created_at": datetime.now(timezone.utc).isoformat(), **payload},
    )
    return target


def config_sha256() -> str:
    return sha256_file(CONFIG_PATH, normalize_text=True)


def evaluation_prompt() -> str:
    return (HERE / "evaluation_v1.txt").read_text(encoding="utf-8")


def experiment_prompt_hash() -> str:
    prompt = load_config()["prompt"]
    payload = "\n\n".join(
        [
            f"prompt_version={prompt['version']}",
            f"system_prompt_version={prompt['system_prompt_version']}",
            f"template_date={prompt['template_date']}",
            "native_template=Qwen/Qwen2.5-7B-Instruct-1M apply_chat_template",
            evaluation_prompt(),
            f"response_format_version={prompt['response_format_version']}",
            RESPONSE_FORMAT_INSTRUCTIONS,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def git_commit() -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def dataset_sha256(dataset_dir: Path) -> str:
    digest = hashlib.sha256()
    prefix = "data/preproduction_llama32_3b_500f_6ctx_v1"
    for name in ("question_families.jsonl", "instances.jsonl"):
        path = dataset_dir / name
        if not path.is_file():
            raise FileNotFoundError(f"benchmark artifact is missing: {path}")
        digest.update(f"{prefix}/{name}".encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
        digest.update(b"\0")
    return digest.hexdigest()


def selected_instances(dataset_dir: Path | None = None) -> list[dict[str, Any]]:
    config = load_config()
    dataset_dir = dataset_dir or paths()["dataset"]
    labels = set(config["context_labels"])
    return [
        row
        for row in read_jsonl(dataset_dir / "instances.jsonl")
        if row.get("context_length_label") in labels
    ]


def expected_instance_ids(instances: list[dict[str, Any]] | None = None) -> set[str]:
    instances = instances if instances is not None else selected_instances()
    return {row["instance_id"] for row in instances}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid JSONL at {path}:{line_number}: {exc}") from exc
    return rows


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def hash_tree(root: Path, excluded_names: set[str] | None = None) -> dict[str, str]:
    excluded_names = excluded_names or set()
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name not in excluded_names
    }
