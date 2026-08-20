#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

from common import MODEL_CHOICES, MODELS, output_path, paths, selected_models, write_manifest


def read_json(path: Path, description: str) -> dict:
    if not path.is_file():
        raise RuntimeError(f"{description} is missing: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{description} is unreadable: {path}: {exc}") from exc


def require_status(path: Path, description: str, status: str) -> dict:
    payload = read_json(path, description)
    if payload.get("status") != status:
        raise RuntimeError(f"{description} has status {payload.get('status')!r}, expected {status!r}")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def jsonl_ids(path: Path) -> list[str]:
    ids = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                instance_id = row.get("instance_id")
                if not instance_id:
                    raise RuntimeError(f"{path}:{line_number} has no instance_id")
                ids.append(instance_id)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"raw output is unreadable: {path}: {exc}") from exc
    return ids


def verify_persistent_success(model: str, workspace: Path | None = None) -> dict:
    layout = paths()
    persistent_root = (workspace or Path(os.environ.get("RUNPOD_WORKSPACE", "/workspace"))).resolve()
    project_root = layout["root"].resolve()
    if workspace is None and persistent_root != Path("/workspace"):
        raise RuntimeError(f"RUNPOD_WORKSPACE must resolve to /workspace, got {persistent_root}")
    if not project_root.is_relative_to(persistent_root):
        raise RuntimeError(f"outputs are not anchored to the required Network Volume: {project_root}")

    manifests = layout["manifests"]
    chosen = selected_models(model)
    preflight = require_status(manifests / f"b200_preflight_{model}.json", "preflight manifest", "PASS")
    if sorted(preflight.get("models", {})) != sorted(chosen):
        raise RuntimeError("preflight manifest does not cover every selected model")

    for mode in ("preflight", "smoke", "full"):
        validation = require_status(
            manifests / f"b200_validation_{model}_{mode}.json",
            f"{mode} validation manifest",
            "PASS",
        )
        if sorted(validation.get("models", {})) != sorted(chosen):
            raise RuntimeError(f"{mode} validation does not cover every selected model")

    full_validation = read_json(manifests / f"b200_validation_{model}_full.json", "full validation manifest")
    for name in chosen:
        report = full_validation["models"][name]
        if (
            report.get("expected") != 3000
            or report.get("attempted") != 3000
            or report.get("successful") != 3000
            or report.get("runtime_failures") != 0
        ):
            raise RuntimeError(f"{name} inference is incomplete: {report}")
        output_dir = output_path(name, layout).resolve()
        if not output_dir.is_relative_to(persistent_root) or not os.access(output_dir, os.R_OK):
            raise RuntimeError(f"{name} output directory is not readable on /workspace: {output_dir}")
        for filename in ("results.jsonl", "failures.jsonl", "integrity_report.json", "run_manifest.json"):
            artifact = output_dir / filename
            if not artifact.is_file() or not os.access(artifact, os.R_OK):
                raise RuntimeError(f"{name} persistent artifact is missing or unreadable: {artifact}")
        integrity = read_json(output_dir / "integrity_report.json", f"{name} integrity report")
        if integrity.get("passed") is not True:
            raise RuntimeError(f"{name} integrity report did not pass")
        run_manifest = read_json(output_dir / "run_manifest.json", f"{name} run manifest")
        if run_manifest.get("model_revision") != MODELS[name][1]:
            raise RuntimeError(f"{name} model revision mismatch in run manifest")
        ids = jsonl_ids(output_dir / "results.jsonl") + jsonl_ids(output_dir / "failures.jsonl")
        if len(ids) != 3000 or len(ids) != len(set(ids)):
            raise RuntimeError(
                f"{name} raw output accounting is invalid: attempted={len(ids)} unique={len(set(ids))}"
            )

    hashes = require_status(
        manifests / f"b200_inference_hashes_{model}.json",
        "inference hash manifest",
        "PASS",
    )
    if sorted(hashes.get("models", {})) != sorted(chosen):
        raise RuntimeError("hash manifest does not cover every selected model")
    for name in chosen:
        root = output_path(name, layout).resolve()
        record = hashes["models"][name]
        if Path(record.get("root", "")).resolve() != root:
            raise RuntimeError(f"{name} hash root does not match its persistent output directory")
        recorded_hashes = record.get("sha256", {})
        for required in ("results.jsonl", "failures.jsonl", "integrity_report.json", "run_manifest.json"):
            if required not in recorded_hashes:
                raise RuntimeError(f"{name} hash manifest is missing {required}")
        for relative, expected in recorded_hashes.items():
            artifact = (root / relative).resolve()
            if not artifact.is_relative_to(root) or not artifact.is_file():
                raise RuntimeError(f"{name} hashed artifact is missing: {artifact}")
            observed = sha256_file(artifact)
            if observed != expected:
                raise RuntimeError(f"{name} hash mismatch for {relative}: {observed} != {expected}")

    completion = require_status(
        manifests / f"b200_inference_complete_{model}.json",
        "completion marker",
        "COMPLETE",
    )
    if sorted(completion.get("hashed_models", [])) != sorted(chosen):
        raise RuntimeError("completion marker does not cover every selected model")
    for name in chosen:
        report = completion.get("validation", {}).get(name, {})
        if (
            report.get("expected") != 3000
            or report.get("attempted") != 3000
            or report.get("successful") != 3000
            or report.get("runtime_failures") != 0
        ):
            raise RuntimeError(f"{name} completion marker is incomplete")

    return {
        "model_selection": model,
        "persistent_root": str(persistent_root),
        "models": list(chosen),
        "completion_marker": str(manifests / f"b200_inference_complete_{model}.json"),
        "hash_manifest": str(manifests / f"b200_inference_hashes_{model}.json"),
    }


def terminate_pod(
    model: str,
    *,
    env: dict[str, str] | None = None,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> None:
    env = os.environ if env is None else env
    verification = verify_persistent_success(model)
    pod_id = env.get("RUNPOD_POD_ID", "").strip()
    api_key = env.get("RUNPOD_API_KEY", "").strip()
    if not pod_id:
        raise RuntimeError("RUNPOD_POD_ID is missing")
    if not api_key:
        raise RuntimeError("RUNPOD_API_KEY is missing")

    print("ALL GPU OUTPUTS VERIFIED ON NETWORK VOLUME", flush=True)
    print(f"Requesting termination for RunPod Pod ID: {pod_id}", flush=True)
    write_manifest(
        f"b200_termination_attempt_{model}.json",
        {"status": "REQUESTING", "pod_id": pod_id, "verification": verification},
    )
    request = urllib.request.Request(
        f"https://rest.runpod.io/v1/pods/{pod_id}",
        method="DELETE",
        headers={"Authorization": "Bearer " + api_key},
    )
    try:
        with opener(request, timeout=30) as response:
            status = getattr(response, "status", None)
            body = response.read(4096).decode("utf-8", errors="replace")
            if status is None or not 200 <= status < 300:
                raise RuntimeError(f"RunPod termination failed with HTTP {status}: {body}")
    except Exception as exc:
        write_manifest(
            f"b200_termination_result_{model}.json",
            {
                "status": "UNKNOWN",
                "pod_id": pod_id,
                "reason": str(exc),
                "action": "Check RunPod console; do not assume the Pod is still running.",
            },
        )
        raise RuntimeError(
            f"RunPod termination response was not confirmed ({exc}); "
            "termination status is unknown, check the RunPod console manually"
        ) from exc
    write_manifest(
        f"b200_termination_result_{model}.json",
        {"status": "ACCEPTED", "pod_id": pod_id, "http_status": status},
    )
    print(f"RunPod termination request accepted for Pod ID: {pod_id}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=MODEL_CHOICES, required=True)
    args = parser.parse_args()
    try:
        terminate_pod(args.model)
    except (RuntimeError, OSError, urllib.error.URLError) as exc:
        print(f"AUTOMATIC TERMINATION BLOCKED: {exc}", flush=True)
        print("Manual termination is required after resolving the reported issue.", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
