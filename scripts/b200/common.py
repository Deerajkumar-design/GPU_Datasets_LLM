from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BENCHMARK_HASH = "dc2c4194dedb090198e6883735257908ce274bebc8611b40d958dbd026aa1fe6"
GRADER_HASH = "d9282a0ccc50daba3bfd232c058dfbab63a5c19a7323d585a7c2236b3a6c4ba8"
MODELS = {
    "llama": ("meta-llama/Llama-3.2-3B-Instruct", "0cb88a4f764b7a12671c53f0838cd831a0843b95"),
    "qwen": ("Qwen/Qwen3.5-2B", "15852e8c16360a2fea060d615a32b45270f8a8fc"),
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def workspace_root() -> Path:
    return Path(os.environ.get("RUNPOD_WORKSPACE", "/workspace")) / "long-context-reliability"


def paths() -> dict[str, Path]:
    root = workspace_root()
    return {
        "root": root,
        "repo": Path(os.environ.get("B200_REPO", root / "repo")),
        "models": Path(os.environ.get("B200_MODELS", root / "models")),
        "hf_cache": Path(os.environ.get("HF_HOME", root / "hf_cache")),
        "results": Path(os.environ.get("B200_RESULTS", root / "results")),
        "logs": Path(os.environ.get("B200_LOGS", root / "logs")),
        "manifests": Path(os.environ.get("B200_MANIFESTS", root / "manifests")),
    }


def normalized_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def benchmark_sha256(root: Path | None = None) -> str:
    root = root or repo_root()
    dataset = root / "data" / "preproduction_llama32_3b_500f_6ctx_v1"
    digest = hashlib.sha256()
    for name in ("question_families.jsonl", "instances.jsonl"):
        path = dataset / name
        digest.update(f"data/preproduction_llama32_3b_500f_6ctx_v1/{name}".encode())
        digest.update(b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
        digest.update(b"\0")
    return digest.hexdigest()


def verify_frozen(root: Path | None = None) -> dict[str, str]:
    root = root or repo_root()
    observed = {
        "benchmark": benchmark_sha256(root),
        "grader": normalized_sha256(root / "src" / "longctx_dataset" / "grading.py"),
    }
    expected = {"benchmark": BENCHMARK_HASH, "grader": GRADER_HASH}
    bad = {key: (expected[key], observed[key]) for key in expected if observed[key] != expected[key]}
    if bad:
        raise RuntimeError(f"frozen artifact hash mismatch: {bad}")
    return observed


def ensure_layout() -> dict[str, Path]:
    resolved = paths()
    for key in ("models", "hf_cache", "results", "logs", "manifests"):
        resolved[key].mkdir(parents=True, exist_ok=True)
    return resolved


def environment() -> dict[str, str]:
    resolved = ensure_layout()
    env = os.environ.copy()
    env.update({
        "HF_HOME": str(resolved["hf_cache"]),
        "HF_HUB_CACHE": str(resolved["hf_cache"] / "hub"),
        "TRANSFORMERS_CACHE": str(resolved["hf_cache"] / "hub"),
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "B200_DATASET_DIR": str(repo_root() / "data" / "preproduction_llama32_3b_500f_6ctx_v1"),
        "B200_LLAMA_OUT_DIR": str(resolved["results"] / "inference_b200_llama32_3b_500f_6ctx_v1"),
        "B200_QWEN_OUT_DIR": str(resolved["results"] / "inference_b200_qwen35_2b_500f_6ctx_v1"),
        "PYTHONPATH": str(repo_root() / "src") + os.pathsep + env.get("PYTHONPATH", ""),
    })
    return env


def write_manifest(name: str, payload: dict[str, Any]) -> Path:
    target = ensure_layout()["manifests"] / name
    payload = {"created_at": datetime.now(timezone.utc).isoformat(), **payload}
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def hash_tree(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
