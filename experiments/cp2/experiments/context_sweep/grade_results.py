#!/usr/bin/env python3
"""Grade completed CP2 responses on CPU with the frozen GPU_Datasets grader."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from common import atomic_write_json, load_config, read_jsonl


GRADER_SHA256 = "d9282a0ccc50daba3bfd232c058dfbab63a5c19a7323d585a7c2236b3a6c4ba8"


def normalized_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def write_jsonl(path: Path, rows: list[dict]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpu-datasets-repo", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    config = load_config()
    grader_path = args.gpu_datasets_repo / "src" / "longctx_dataset" / "grading.py"
    observed = normalized_sha256(grader_path)
    if observed != GRADER_SHA256:
        raise SystemExit(f"frozen grader hash mismatch: expected {GRADER_SHA256}, observed {observed}")
    sys.path.insert(0, str(args.gpu_datasets_repo / "src"))
    from longctx_dataset.grading import grade_answer_only_response
    from longctx_dataset.schemas import Instance, QuestionFamily

    dataset = args.gpu_datasets_repo / "data" / config["source_benchmark"]["name"]
    instances = {
        row["instance_id"]: Instance.model_validate(row)
        for row in read_jsonl(dataset / "instances.jsonl")
        if row["context_length_label"] in config["context_labels"]
    }
    families = {
        row["question_family_id"]: QuestionFamily.model_validate(row)
        for row in read_jsonl(dataset / "question_families.jsonl")
    }
    raw = read_jsonl(args.results)
    if len(raw) != len(instances) or {row["instance_id"] for row in raw} != set(instances):
        raise SystemExit("raw result IDs do not match the frozen 1,500-instance subset")
    scored = []
    for result in raw:
        instance = instances[result["instance_id"]]
        row = grade_answer_only_response(
            instance,
            result,
            family=families[instance.question_family_id],
        )
        row["factual_outcome"] = "ACCURATE" if row.get("error_type") == "CORRECT" else "INACCURATE"
        row["grader_hash"] = GRADER_SHA256
        scored.append(row)
    args.out.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.out / "scored_results.jsonl", scored)
    fields = sorted({key for row in scored for key in row})
    with (args.out / "scored_results.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(scored)
    by_context = {}
    for label in config["context_labels"]:
        rows = [row for row in scored if row["context_length_label"] == label]
        outcomes = Counter(row["factual_outcome"] for row in rows)
        by_context[label] = {
            "n": len(rows),
            "accurate": outcomes["ACCURATE"],
            "inaccurate": outcomes["INACCURATE"],
            "accuracy": outcomes["ACCURATE"] / len(rows),
            "needs_semantic_review": sum(bool(row.get("needs_semantic_review")) for row in rows),
            "error_types": dict(Counter(row.get("error_type") for row in rows)),
        }
    atomic_write_json(
        args.out / "grading_summary.json",
        {
            "status": "PASS",
            "experiment_id": config["experiment_id"],
            "grader_sha256": GRADER_SHA256,
            "total": len(scored),
            "by_context": by_context,
        },
    )
    print(json.dumps(by_context, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
