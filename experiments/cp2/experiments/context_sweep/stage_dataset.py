#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

from common import dataset_sha256, ensure_layout, load_config, read_jsonl, write_manifest


def verify_dataset(dataset_dir: Path) -> dict:
    config = load_config()
    benchmark = config["source_benchmark"]
    observed_hash = dataset_sha256(dataset_dir)
    if observed_hash != benchmark["dataset_sha256"]:
        raise RuntimeError(
            f"dataset hash mismatch: expected {benchmark['dataset_sha256']}, observed {observed_hash}"
        )
    families = read_jsonl(dataset_dir / "question_families.jsonl")
    instances = read_jsonl(dataset_dir / "instances.jsonl")
    counts = Counter(row.get("context_length_label") for row in instances)
    selected = [row for row in instances if row.get("context_length_label") in config["context_labels"]]
    selected_families = Counter(row.get("question_family_id") for row in selected)
    if len(families) != benchmark["families"] or len(instances) != benchmark["source_instances"]:
        raise RuntimeError(
            f"benchmark accounting mismatch: families={len(families)}, instances={len(instances)}"
        )
    if len(selected) != benchmark["selected_instances"]:
        raise RuntimeError(f"selected instance count is {len(selected)}, expected {benchmark['selected_instances']}")
    if any(counts[label] != config["instances_per_context"] for label in config["context_labels"]):
        raise RuntimeError(f"selected context accounting mismatch: {dict(counts)}")
    if len(selected_families) != benchmark["families"] or any(count != 3 for count in selected_families.values()):
        raise RuntimeError("selected subset does not contain all 500 families at all three contexts")
    return {
        "status": "PASS",
        "dataset_sha256": observed_hash,
        "families": len(families),
        "source_instances": len(instances),
        "selected_instances": len(selected),
        "selected_by_context": {label: counts[label] for label in config["context_labels"]},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage the exact frozen GPU_Datasets benchmark.")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    layout = ensure_layout()
    try:
        if not args.verify_only:
            if args.source is None:
                raise RuntimeError("--source is required unless --verify-only is used")
            layout["dataset"].mkdir(parents=True, exist_ok=True)
            for name in ("question_families.jsonl", "instances.jsonl"):
                source = args.source / name
                if not source.is_file():
                    raise FileNotFoundError(f"source benchmark artifact is missing: {source}")
                shutil.copy2(source, layout["dataset"] / name)
        report = {**verify_dataset(layout["dataset"]), "local_path": str(layout["dataset"])}
        write_manifest("dataset_staging.json", report)
        print(json.dumps(report, indent=2))
        return 0
    except Exception as exc:
        write_manifest("dataset_staging.json", {"status": "FAIL", "error": str(exc)})
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
