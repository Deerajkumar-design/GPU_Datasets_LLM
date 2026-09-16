#!/usr/bin/env python3
"""Build the frozen 500-family dataset with a true 128K condition.

The build reuses the exact frozen question families, regenerates contexts from the
normalized primary-source pool, and refuses to publish unless the regenerated 4K-64K
contexts exactly match the existing frozen controls. The published dataset keeps the
existing 4K-64K rows byte-for-byte and adds only the newly generated 128K rows.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml


HERE = Path(__file__).resolve().parent
REPOSITORY_ROOT = HERE.parents[3]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from longctx_dataset.config import load_config as load_pipeline_config
from longctx_dataset.pipeline import stage_build_contexts
from longctx_dataset.storage.io import write_parquet


PARENT_DATASET_SHA256 = "dc2c4194dedb090198e6883735257908ce274bebc8611b40d958dbd026aa1fe6"
NEW_DATASET_NAME = "preproduction_llama32_3b_500f_128k_v1"
PUBLISHED_LABELS = ("4K", "8K", "16K", "32K", "64K", "128K")
CONTROL_LABELS = ("4K", "8K", "16K", "32K", "64K")
EXPECTED_FAMILIES = 500
SAFE_RENDERED_INPUT_TOKENS = 131072 - 128
NORMALIZED_FILES = ("sec.jsonl", "fda.jsonl", "clinical_trials.jsonl", "fred.jsonl")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    temporary.replace(path)


def normalized_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def dataset_sha256(dataset_dir: Path) -> str:
    digest = hashlib.sha256()
    prefix = f"data/{dataset_dir.name}"
    for name in ("question_families.jsonl", "instances.jsonl"):
        path = dataset_dir / name
        digest.update(f"{prefix}/{name}".encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
        digest.update(b"\0")
    return digest.hexdigest()


def git_commit() -> str:
    completed = subprocess.run(
        ["git", "-C", str(REPOSITORY_ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "UNKNOWN"


def require_clean_repository() -> str:
    commit = git_commit()
    if commit == "UNKNOWN":
        raise RuntimeError("cannot finalize provenance: git rev-parse failed")
    completed = subprocess.run(
        ["git", "-C", str(REPOSITORY_ROOT), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("cannot finalize provenance: git status failed")
    if completed.stdout.strip():
        raise RuntimeError(
            "cannot finalize provenance from a dirty repository; commit or remove all changes first"
        )
    return commit


def derive_pipeline_config(base_path: Path, output_dir: Path) -> Path:
    payload = yaml.safe_load(base_path.read_text(encoding="utf-8"))
    payload["name"] = NEW_DATASET_NAME
    payload["data_root"] = str(output_dir.parent)
    payload["output_subdir"] = output_dir.name
    payload["write_parquet"] = True
    payload["context"]["lengths"] = [4096, 8192, 16384, 32768, 65536, 131072]
    payload["model"]["max_new_tokens"] = 128
    payload.setdefault("model_prompt", {})["max_rendered_input_tokens"] = SAFE_RENDERED_INPUT_TOKENS
    derived = output_dir / "build_config.yaml"
    derived.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8", newline="\n")
    return derived


def stage_normalized_records(source_dir: Path, destination_dir: Path) -> None:
    destination_dir.mkdir(parents=True, exist_ok=True)
    for name in NORMALIZED_FILES:
        source = source_dir / name
        destination = destination_dir / name
        if not source.is_file():
            raise FileNotFoundError(
                f"normalized source record file is missing: {source}; restore the original "
                "cache or run the parent config's fetch and normalize stages"
            )
        if source.resolve() != destination.resolve():
            shutil.copy2(source, destination)


def verify_parent(source_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    families = read_jsonl(source_dir / "question_families.jsonl")
    instances = read_jsonl(source_dir / "instances.jsonl")
    if len(families) != EXPECTED_FAMILIES or len(instances) != 3000:
        raise RuntimeError(
            f"parent accounting mismatch: families={len(families)}, instances={len(instances)}"
        )
    observed = dataset_sha256(source_dir)
    if observed != PARENT_DATASET_SHA256:
        raise RuntimeError(
            f"parent dataset hash mismatch: expected {PARENT_DATASET_SHA256}, observed {observed}"
        )
    return families, instances


def verify_controls(
    parent_rows: list[dict[str, Any]],
    generated_rows: list[dict[str, Any]],
) -> None:
    parent = {
        row["instance_id"]: row
        for row in parent_rows
        if row["context_length_label"] in CONTROL_LABELS
    }
    generated = {
        row["instance_id"]: row
        for row in generated_rows
        if row["context_length_label"] in CONTROL_LABELS
    }
    if set(parent) != set(generated):
        missing = sorted(set(parent) - set(generated))
        unexpected = sorted(set(generated) - set(parent))
        raise RuntimeError(
            f"regenerated control IDs differ: missing={missing[:10]}, unexpected={unexpected[:10]}"
        )
    fields = (
        "question_family_id",
        "domain",
        "question_type",
        "answerable",
        "question",
        "gold_answer",
        "gold_answer_normalized",
        "gold_evidence_ids",
        "context",
        "context_sha256",
        "context_record_ids",
        "context_tokens_actual",
        "target_evidence_start_token",
        "target_evidence_end_token",
    )
    mismatches = []
    for instance_id in sorted(parent):
        changed = [field for field in fields if parent[instance_id].get(field) != generated[instance_id].get(field)]
        if changed:
            mismatches.append({"instance_id": instance_id, "fields": changed})
            if len(mismatches) == 20:
                break
    if mismatches:
        raise RuntimeError(
            "regenerated 4K-64K controls do not match the frozen benchmark: "
            + json.dumps(mismatches)
        )


def verify_128k(
    parent_rows: list[dict[str, Any]],
    generated_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = [row for row in generated_rows if row["context_length_label"] == "128K"]
    if len(rows) != EXPECTED_FAMILIES:
        raise RuntimeError(f"expected 500 generated 128K rows, observed {len(rows)}")
    if len({row["instance_id"] for row in rows}) != EXPECTED_FAMILIES:
        raise RuntimeError("generated 128K instance IDs are not unique")
    by_family_64k = {
        row["question_family_id"]: row
        for row in parent_rows
        if row["context_length_label"] == "64K"
    }
    failures = []
    for row in rows:
        family_id = row["question_family_id"]
        parent = by_family_64k.get(family_id)
        checks = {
            "nominal": row.get("context_length_nominal") == 131072,
            "fill_ratio": row.get("context_tokens_actual", 0) / 131072 >= 0.95,
            "rendered_budget": 0 < row.get("rendered_input_tokens_actual", 0) <= SAFE_RENDERED_INPUT_TOKENS,
            "has_64k_parent": parent is not None,
            "nested_records": parent is not None
            and set(parent["context_record_ids"]).issubset(row["context_record_ids"]),
            "same_question": parent is not None and parent["question"] == row["question"],
            "same_gold": parent is not None
            and parent["gold_answer_normalized"] == row["gold_answer_normalized"],
            "target_position": row.get("stats", {}).get("target_position_ok") is True,
        }
        failed = [name for name, passed in checks.items() if not passed]
        if failed:
            failures.append({"instance_id": row["instance_id"], "failed": failed})
            if len(failures) == 20:
                break
    if failures:
        raise RuntimeError("128K validation failed: " + json.dumps(failures))
    return rows


def finalize_cp2_config(
    template_path: Path,
    output_path: Path,
    dataset_digest: str,
    repository_commit: str,
    generation_code_sha256: str,
) -> None:
    config = json.loads(template_path.read_text(encoding="utf-8"))
    benchmark = config["source_benchmark"]
    benchmark["name"] = NEW_DATASET_NAME
    benchmark["repository_commit"] = repository_commit
    benchmark["dataset_sha256"] = dataset_digest
    benchmark["generation_code_sha256"] = generation_code_sha256
    output_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a frozen 4K-128K benchmark and finalized CP2 64K/128K config."
    )
    parser.add_argument("--source", type=Path, required=True, help="Frozen 500-family 4K-82K dataset")
    parser.add_argument(
        "--base-config",
        type=Path,
        default=REPOSITORY_ROOT / "config" / "preproduction_llama32_3b_500f_6ctx_v1.yaml",
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--normalized-dir",
        type=Path,
        default=REPOSITORY_ROOT / "data" / "normalized",
        help="Directory containing sec.jsonl, fda.jsonl, clinical_trials.jsonl, and fred.jsonl",
    )
    parser.add_argument(
        "--cp2-template",
        type=Path,
        default=HERE / "experiment_config_64k_128k.template.json",
    )
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.out.resolve()
    if source == output:
        raise SystemExit("--source and --out must be different directories")
    if source.name != "preproduction_llama32_3b_500f_6ctx_v1":
        raise SystemExit(
            "--source must be the directory named preproduction_llama32_3b_500f_6ctx_v1"
        )
    if output.name != NEW_DATASET_NAME:
        raise SystemExit(f"--out must be a directory named {NEW_DATASET_NAME}")

    repository_commit = require_clean_repository()
    families, parent_rows = verify_parent(source)
    output.mkdir(parents=True, exist_ok=True)
    stage_normalized_records(args.normalized_dir.resolve(), output.parent / "normalized")
    shutil.copy2(source / "question_families.jsonl", output / "question_families.jsonl")
    derived_config = derive_pipeline_config(args.base_config.resolve(), output)
    pipeline_config = load_pipeline_config(derived_config)

    print("Building regenerated controls and 128K contexts from normalized source records...", flush=True)
    instance_count, unavailable_count = stage_build_contexts(pipeline_config, log=print)
    if instance_count != 3000 or unavailable_count != 0:
        raise RuntimeError(
            f"128K build is incomplete: instances={instance_count}, unavailable={unavailable_count}"
        )
    generated_rows = read_jsonl(output / "instances.jsonl")
    verify_controls(parent_rows, generated_rows)
    new_128k = verify_128k(parent_rows, generated_rows)

    parent_controls = [
        row for row in parent_rows if row["context_length_label"] in CONTROL_LABELS
    ]
    published = sorted(
        [*parent_controls, *new_128k],
        key=lambda row: (
            row["question_family_id"],
            PUBLISHED_LABELS.index(row["context_length_label"]),
        ),
    )
    counts = Counter(row["context_length_label"] for row in published)
    expected_counts = {label: EXPECTED_FAMILIES for label in PUBLISHED_LABELS}
    if counts != expected_counts:
        raise RuntimeError(f"published context accounting mismatch: {dict(counts)}")
    write_jsonl(output / "instances.jsonl", published)
    parquet_paths = (
        output / "instances.parquet",
        output / "question_families.parquet",
    )
    parquet_written = (
        write_parquet(parquet_paths[0], published)
        and write_parquet(parquet_paths[1], families)
    )
    if not parquet_written:
        for path in parquet_paths:
            path.unlink(missing_ok=True)
        raise RuntimeError(
            "Parquet mirrors could not be written; install the repository's parquet extra"
        )

    digest = dataset_sha256(output)
    generation_code_digest = normalized_sha256(Path(__file__))
    if require_clean_repository() != repository_commit:
        raise RuntimeError("repository commit changed during dataset construction")
    finalized_config = output / "cp2_experiment_config.json"
    finalize_cp2_config(
        args.cp2_template.resolve(),
        finalized_config,
        digest,
        repository_commit,
        generation_code_digest,
    )
    report = {
        "status": "PASS",
        "dataset": NEW_DATASET_NAME,
        "dataset_sha256": digest,
        "parent_dataset_sha256": PARENT_DATASET_SHA256,
        "families": len(families),
        "instances": len(published),
        "instances_by_context": dict(counts),
        "control_contexts_exact_match": True,
        "new_128k_instances": len(new_128k),
        "safe_rendered_input_tokens": SAFE_RENDERED_INPUT_TOKENS,
        "nominal_tokenizer": "hf:meta-llama/Llama-3.2-3B-Instruct",
        "published_metadata_budgets": {
            "4K-64K": "parent maximum rendered input tokens: 81800",
            "128K": f"derived maximum rendered input tokens: {SAFE_RENDERED_INPUT_TOKENS}",
        },
        "cp2_experiment_config": str(finalized_config),
        "generation_code_sha256": generation_code_digest,
        "repository_commit": repository_commit,
    }
    (output / "extension_manifest.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2))
    print(f"Set CP_EXPERIMENT_CONFIG={finalized_config}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
