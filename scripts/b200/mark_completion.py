#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from common import MODEL_CHOICES, paths, selected_models, write_manifest


def require_pass(path, description: str) -> dict:
    if not path.is_file():
        raise SystemExit(f"{description} is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("status") != "PASS":
        raise SystemExit(f"{description} did not pass: {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=MODEL_CHOICES, default="all")
    args = parser.parse_args()
    manifests = paths()["manifests"]
    validation_path = manifests / f"b200_validation_{args.model}_full.json"
    hashes_path = manifests / f"b200_inference_hashes_{args.model}.json"
    validation = require_pass(validation_path, "full inference validation")
    hashes = require_pass(hashes_path, "inference hash manifest")
    expected_models = sorted(selected_models(args.model))
    if validation.get("model_selection") != args.model or sorted(validation.get("models", {})) != expected_models:
        raise SystemExit("validation manifest model selection mismatch")
    if hashes.get("model_selection") != args.model or sorted(hashes.get("models", {})) != expected_models:
        raise SystemExit("hash manifest model selection mismatch")
    for model in expected_models:
        report = validation["models"][model]
        if (
            report.get("expected") != 3000
            or report.get("attempted") != 3000
            or report.get("successful") != 3000
            or report.get("runtime_failures") != 0
        ):
            raise SystemExit(f"{model} has not reached successful terminal completion: {report}")
    manifest = write_manifest(
        f"b200_inference_complete_{args.model}.json",
        {
            "status": "COMPLETE",
            "model_selection": args.model,
            "validation_manifest": str(validation_path),
            "hash_manifest": str(hashes_path),
            "validation": validation["models"],
            "hashed_models": sorted(hashes["models"]),
        },
    )
    print(f"Terminal completion manifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
