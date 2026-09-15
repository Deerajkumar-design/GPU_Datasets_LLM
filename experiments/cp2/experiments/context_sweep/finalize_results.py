#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

from common import (
    atomic_write_json,
    config_sha256,
    ensure_layout,
    hash_tree,
    load_config,
    read_jsonl,
    selected_instances,
    write_manifest,
)
from validate_results import validate_rows


def main() -> int:
    config = load_config()
    layout = ensure_layout()
    try:
        validation_path = layout["results"] / "validation.json"
        if not validation_path.is_file():
            raise FileNotFoundError(f"validation report is missing: {validation_path}")
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        if validation.get("status") != "PASS":
            raise RuntimeError("validation did not pass")
        if validation.get("config_sha256") != config_sha256():
            raise RuntimeError("validation configuration hash mismatch")
        independently_validated = validate_rows(
            read_jsonl(layout["results"] / "results.jsonl"),
            selected_instances(layout["dataset"]),
            config,
        )
        independently_validated["mode"] = "full"
        if independently_validated != validation:
            raise RuntimeError("stored validation report does not match independently validated results")
        required = ("results.jsonl", "run_manifest.json", "validation.json", "summary.csv")
        missing = [name for name in required if not (layout["results"] / name).is_file()]
        if missing:
            raise RuntimeError(f"required result artifacts are missing: {missing}")
        hashes = hash_tree(layout["results"], excluded_names={"hashes.json", "COMPLETE.json"})
        hash_report = {
            "status": "PASS",
            "experiment_id": config["experiment_id"],
            "config_sha256": config_sha256(),
            "root": str(layout["results"]),
            "sha256": hashes,
        }
        atomic_write_json(layout["results"] / "hashes.json", hash_report)
        write_manifest("hashes.json", hash_report)
        completion = {
            "status": "COMPLETE",
            "experiment_id": config["experiment_id"],
            "config_sha256": config_sha256(),
            "successful_runs": validation["runtime_successful"],
            "contexts": config["context_labels"],
            "families": config["source_benchmark"]["families"],
            "hash_manifest": str(layout["results"] / "hashes.json"),
        }
        atomic_write_json(layout["results"] / "COMPLETE.json", completion)
        write_manifest("completion.json", completion)
        print(json.dumps(completion, indent=2))
        print("ALL CONTEXT-SWEEP OUTPUTS VERIFIED")
        return 0
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
