#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

from common import (
    atomic_write_json,
    config_sha256,
    dataset_sha256,
    ensure_layout,
    experiment_prompt_hash,
    expected_instance_ids,
    load_config,
    read_jsonl,
    selected_instances,
    verify_frozen_artifacts,
    write_manifest,
)


def validate_rows(rows: list[dict], instances: list[dict], config: dict) -> dict:
    expected_ids = expected_instance_ids(instances)
    observed_ids = [row.get("instance_id") for row in rows]
    duplicate_ids = sorted(instance_id for instance_id, count in Counter(observed_ids).items() if count > 1)
    if duplicate_ids:
        raise RuntimeError(f"duplicate instance IDs: {duplicate_ids[:20]}")
    missing = sorted(expected_ids - set(observed_ids))
    unexpected = sorted(set(observed_ids) - expected_ids)
    if missing or unexpected:
        raise RuntimeError(
            f"instance accounting failure: missing={missing[:20]}, unexpected={unexpected[:20]}"
        )
    by_id = {instance["instance_id"]: instance for instance in instances}
    expected_by_context = Counter(instance["context_length_label"] for instance in instances)
    by_context: dict[str, list[dict]] = defaultdict(list)
    row_failures = []
    for row in rows:
        instance = by_id[row["instance_id"]]
        checks = {
            "status": row.get("status") == "SUCCESS",
            "question_family_id": row.get("question_family_id") == instance["question_family_id"],
            "domain": row.get("domain") == instance["domain"],
            "question_type": row.get("question_type") == instance["question_type"],
            "context_length_label": row.get("context_length_label") == instance["context_length_label"],
            "answerable": row.get("answerable") == instance["answerable"],
            "model_id": row.get("model_id") == config["model"]["repo"],
            "model_revision": row.get("model_revision") == config["model"]["revision"],
            "prompt_version": row.get("prompt_version") == config["prompt"]["version"],
            "prompt_hash": row.get("prompt_hash") == experiment_prompt_hash(),
            "response_format": row.get("response_format_version") == config["prompt"]["response_format_version"],
            "generation_settings": row.get("generation_settings") == config["decoding"],
            "execution_seed": row.get("execution_seed") == config["execution_seed"],
            "input_tokens": row.get("input_tokens", 0) > 0,
            "generated_tokens": 0 < row.get("generated_tokens_count", 0) <= config["max_new_tokens"],
            "usable_answer_output": row.get("usable_answer_output") is True,
            "not_truncated": row.get("hit_max_new_tokens_128") is False,
            "latency": row.get("generation_latency_seconds", 0) > 0,
            "peak_memory": row.get("peak_reserved_vram_bytes", 0) > 0,
        }
        failed = [name for name, passed in checks.items() if not passed]
        if failed:
            row_failures.append({"instance_id": row["instance_id"], "failed": failed})
        by_context[row["context_length_label"]].append(row)
    if row_failures:
        raise RuntimeError(
            f"validation failures ({len(row_failures)} rows): {row_failures[:20]}"
        )

    context_reports = {}
    for label in config["context_labels"]:
        context_rows = by_context[label]
        if len(context_rows) != expected_by_context[label]:
            raise RuntimeError(f"{label}: expected {expected_by_context[label]} rows, got {len(context_rows)}")
        latencies = [row["generation_latency_seconds"] for row in context_rows]
        input_tokens = [row["input_tokens"] for row in context_rows]
        context_reports[label] = {
            "attempted": len(context_rows),
            "runtime_successful": len(context_rows),
            "usable_answer_outputs": sum(bool(row.get("usable_answer_output")) for row in context_rows),
            "malformed_outputs": sum(not bool(row.get("usable_answer_output")) for row in context_rows),
            "hit_max_new_tokens": sum(bool(row.get("hit_max_new_tokens_128")) for row in context_rows),
            "input_tokens": {
                "mean": statistics.mean(input_tokens),
                "min": min(input_tokens),
                "median": statistics.median(input_tokens),
                "max": max(input_tokens),
            },
            "latency_seconds": {
                "mean": statistics.mean(latencies),
                "median": statistics.median(latencies),
                "stdev": statistics.stdev(latencies),
                "min": min(latencies),
                "max": max(latencies),
            },
            "peak_reserved_vram_bytes": max(row["peak_reserved_vram_bytes"] for row in context_rows),
        }
    return {
        "status": "PASS",
        "experiment_id": config["experiment_id"],
        "config_sha256": config_sha256(),
        "dataset_sha256": config["source_benchmark"]["dataset_sha256"],
        "families": len({instance["question_family_id"] for instance in instances}),
        "expected_instances": len(expected_ids),
        "attempted": len(rows),
        "runtime_successful": len(rows),
        "usable_answer_outputs": sum(bool(row.get("usable_answer_output")) for row in rows),
        "contexts": context_reports,
        "output_philosophy": "raw_generation_plus_structured_answer_for_cpu_grading",
    }


def write_summary_csv(path: Path, report: dict) -> None:
    fields = (
        "context_length",
        "attempted",
        "runtime_successful",
        "usable_answer_outputs",
        "malformed_outputs",
        "hit_max_new_tokens",
        "mean_input_tokens",
        "median_input_tokens",
        "mean_latency_seconds",
        "median_latency_seconds",
        "stdev_latency_seconds",
        "peak_reserved_vram_bytes",
    )
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for label, summary in report["contexts"].items():
            writer.writerow(
                {
                    "context_length": label,
                    "attempted": summary["attempted"],
                    "runtime_successful": summary["runtime_successful"],
                    "usable_answer_outputs": summary["usable_answer_outputs"],
                    "malformed_outputs": summary["malformed_outputs"],
                    "hit_max_new_tokens": summary["hit_max_new_tokens"],
                    "mean_input_tokens": summary["input_tokens"]["mean"],
                    "median_input_tokens": summary["input_tokens"]["median"],
                    "mean_latency_seconds": summary["latency_seconds"]["mean"],
                    "median_latency_seconds": summary["latency_seconds"]["median"],
                    "stdev_latency_seconds": summary["latency_seconds"]["stdev"],
                    "peak_reserved_vram_bytes": summary["peak_reserved_vram_bytes"],
                }
            )
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("smoke", "full"), default="full")
    args = parser.parse_args()
    config = load_config()
    layout = ensure_layout()
    output = layout["results"] if args.mode == "full" else layout["results"] / "smoke"
    try:
        verify_frozen_artifacts()
        instances = selected_instances(layout["dataset"])
        if args.mode == "smoke":
            order_path = output / "execution_order.json"
            if not order_path.is_file():
                raise FileNotFoundError(f"smoke execution order is missing: {order_path}")
            selected_ids = {row["instance_id"] for row in json.loads(order_path.read_text())["order"]}
            instances = [instance for instance in instances if instance["instance_id"] in selected_ids]
        run_manifest = output / "run_manifest.json"
        if not run_manifest.is_file():
            raise FileNotFoundError(f"run manifest is missing: {run_manifest}")
        manifest = json.loads(run_manifest.read_text(encoding="utf-8"))
        if manifest.get("config_sha256") != config_sha256():
            raise RuntimeError("run manifest configuration does not match the frozen configuration")
        report = validate_rows(read_jsonl(output / "results.jsonl"), instances, config)
        report["mode"] = args.mode
        atomic_write_json(output / "validation.json", report)
        write_summary_csv(output / "summary.csv", report)
        write_manifest(f"validation_{args.mode}.json", report)
        print(json.dumps(report, indent=2))
        print(f"PASS: {len(instances)} GPU_DATASETS INSTANCES VALIDATED ({args.mode})")
        return 0
    except Exception as exc:
        report = {
            "status": "FAIL",
            "experiment_id": config["experiment_id"],
            "config_sha256": config_sha256(),
            "error": str(exc),
        }
        atomic_write_json(output / "validation.json", report)
        write_manifest(f"validation_{args.mode}.json", report)
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
