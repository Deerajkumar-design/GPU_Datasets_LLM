#!/usr/bin/env python3
"""Apply approved Experiment D manual adjudications as a separate freeze layer."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


SRC = Path("data/grading_experiment_d_full_v1/scored_results.jsonl")
RUNTIME_FAILURES = Path("data/grading_experiment_d_full_v1/runtime_failures.jsonl")
OUT = Path("data/grading_experiment_d_final_v1")
EXPECTED_SRC_HASH = "7ab4f8df193ae9f5bba2f8ab23b5e1662deee4185b27039f79f08532b6062f17"
GRADER_HASH = "d9282a0ccc50daba3bfd232c058dfbab63a5c19a7323d585a7c2236b3a6c4ba8"

TO_CORRECT = {
    "FDA_0099_4K",
    "FDA_0099_8K",
    "FDA_0099_16K",
    "FDA_0099_32K",
    "FDA_0099_64K",
    "FDA_0099_82K",
    "FDA_0105_4K",
}

TO_WRONG_ENTITY = {
    "SEC_0086_32K",
    "FRED_0102_64K",
    "FRED_0100_32K",
    "FDA_0019_64K",
    "FRED_0103_32K",
    "FRED_0038_4K",
    "FRED_0093_64K",
    "FRED_0100_82K",
    "FDA_0020_82K",
    "FRED_0100_64K",
    "FRED_0104_82K",
    "FRED_0038_8K",
}

CORRECT_REASON = (
    "The model answer exactly matches the deterministic gold answer/target evidence. "
    "These were grader edge cases, not factual errors."
)
WRONG_ENTITY_REASON = (
    "The returned value is authentic and present in the supplied context, but belongs "
    "to a different requested entity/application/company/state/series. Therefore the "
    "answer is grounded but incorrectly bound, not hallucinated."
)

EXPECTED_BY_CONTEXT = {
    "4K": {"gradable": 500, "correct": 252, "inaccurate": 248, "hallucinatory": 171, "grounded": 77, "runtime_failures": 0},
    "8K": {"gradable": 500, "correct": 228, "inaccurate": 272, "hallucinatory": 186, "grounded": 86, "runtime_failures": 0},
    "16K": {"gradable": 500, "correct": 206, "inaccurate": 294, "hallucinatory": 174, "grounded": 120, "runtime_failures": 0},
    "32K": {"gradable": 500, "correct": 192, "inaccurate": 308, "hallucinatory": 191, "grounded": 117, "runtime_failures": 0},
    "64K": {"gradable": 500, "correct": 152, "inaccurate": 348, "hallucinatory": 209, "grounded": 139, "runtime_failures": 0},
    "82K": {"gradable": 498, "correct": 146, "inaccurate": 352, "hallucinatory": 201, "grounded": 151, "runtime_failures": 2},
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames: list[str] = []
    seen = set()
    for row in rows:
        for key in row:
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def add_original_fields(row: dict) -> None:
    for field in ("answer_correct", "hallucination", "error_type", "factual_outcome", "inaccuracy_class"):
        row[f"original_{field}"] = row.get(field)


def apply_override(row: dict) -> dict:
    row = dict(row)
    instance_id = row["instance_id"]
    add_original_fields(row)
    row["manual_adjudication"] = instance_id in TO_CORRECT or instance_id in TO_WRONG_ENTITY
    row["adjudication_method"] = "human_manual_review" if row["manual_adjudication"] else None
    row["adjudication_reason"] = None

    if instance_id in TO_CORRECT:
        row.update(
            {
                "answer_correct": True,
                "hallucination": False,
                "error_type": "CORRECT",
                "factual_outcome": "CORRECT",
                "inaccuracy_class": "NOT_APPLICABLE",
                "needs_semantic_review": False,
                "review_reason": "",
                "adjudication_reason": CORRECT_REASON,
            }
        )
    elif instance_id in TO_WRONG_ENTITY:
        row.update(
            {
                "answer_correct": False,
                "hallucination": False,
                "error_type": "WRONG_ENTITY",
                "factual_outcome": "INACCURATE",
                "inaccuracy_class": "GROUNDED_INACCURACY",
                "needs_semantic_review": False,
                "review_reason": "",
                "adjudication_reason": WRONG_ENTITY_REASON,
            }
        )
    return row


def summarize(rows: list[dict], failures: list[dict]) -> dict:
    by_context: dict[str, dict] = {}
    for label in ["4K", "8K", "16K", "32K", "64K", "82K"]:
        subset = [r for r in rows if r["context_length_label"] == label]
        fail_subset = [r for r in failures if (r.get("context_length_label") or r.get("context_label")) == label]
        correct = sum(r["answer_correct"] is True for r in subset)
        inaccurate = sum(r["answer_correct"] is False for r in subset)
        hall = sum(r["answer_correct"] is False and r["hallucination"] is True for r in subset)
        grounded = sum(r["answer_correct"] is False and r["hallucination"] is False for r in subset)
        by_context[label] = {
            "gradable": len(subset),
            "correct": correct,
            "inaccurate": inaccurate,
            "hallucinatory": hall,
            "grounded": grounded,
            "runtime_failures": len(fail_subset),
        }
    return {
        "successful_graded_responses": len(rows),
        "runtime_failures": len(failures),
        "correct": sum(r["answer_correct"] is True for r in rows),
        "inaccurate": sum(r["answer_correct"] is False for r in rows),
        "hallucinatory_inaccuracy": sum(r["answer_correct"] is False and r["hallucination"] is True for r in rows),
        "grounded_inaccuracy": sum(r["answer_correct"] is False and r["hallucination"] is False for r in rows),
        "ambiguous": sum(r["error_type"] == "AMBIGUOUS_REVIEW_REQUIRED" for r in rows),
        "manual_adjudications": sum(r["manual_adjudication"] is True for r in rows),
        "error_type_counts": dict(Counter(r["error_type"] for r in rows)),
        "by_context": by_context,
    }


def main() -> None:
    actual_src_hash = sha256(SRC)
    if actual_src_hash != EXPECTED_SRC_HASH:
        raise SystemExit(f"Source hash mismatch: {actual_src_hash} != {EXPECTED_SRC_HASH}")

    OUT.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(SRC)
    failures = read_jsonl(RUNTIME_FAILURES)
    ids = [r["instance_id"] for r in rows]
    if len(rows) != 2998 or len(set(ids)) != 2998:
        raise SystemExit("Unexpected scored-results cardinality")
    if len(failures) != 2:
        raise SystemExit("Expected exactly two runtime failures")

    override_ids = TO_CORRECT | TO_WRONG_ENTITY
    if len(override_ids) != 19:
        raise SystemExit("Override list must contain 19 unique IDs")
    rows_by_id = {r["instance_id"]: r for r in rows}
    missing = sorted(override_ids - rows_by_id.keys())
    if missing:
        raise SystemExit(f"Override IDs missing from scored rows: {missing}")
    for instance_id in override_ids:
        if rows_by_id[instance_id].get("error_type") != "AMBIGUOUS_REVIEW_REQUIRED":
            raise SystemExit(f"Override source row is not ambiguous: {instance_id}")

    final_rows = [apply_override(row) for row in rows]
    unchanged = 0
    for original, final in zip(rows, final_rows):
        if final["manual_adjudication"]:
            continue
        compare_fields = set(original) | {k for k in final if k.startswith("original_")} | {
            "manual_adjudication",
            "adjudication_method",
            "adjudication_reason",
        }
        final_without_added = {
            k: v
            for k, v in final.items()
            if k not in compare_fields or (k in original and not k.startswith("original_"))
        }
        original_subset = {k: original.get(k) for k in final_without_added}
        if final_without_added != original_subset:
            raise SystemExit(f"Non-adjudicated row changed unexpectedly: {original['instance_id']}")
        unchanged += 1
    if unchanged != 2979:
        raise SystemExit(f"Expected 2,979 unchanged rows, got {unchanged}")

    summary = summarize(final_rows, failures)
    expected_totals = {
        "successful_graded_responses": 2998,
        "runtime_failures": 2,
        "correct": 1176,
        "inaccurate": 1822,
        "hallucinatory_inaccuracy": 1132,
        "grounded_inaccuracy": 690,
        "ambiguous": 0,
        "manual_adjudications": 19,
    }
    for key, expected in expected_totals.items():
        if summary[key] != expected:
            raise SystemExit(f"Unexpected {key}: {summary[key]} != {expected}")
    if summary["by_context"] != EXPECTED_BY_CONTEXT:
        raise SystemExit(f"By-context counts mismatch: {summary['by_context']}")

    scored_jsonl = OUT / "final_scored_results.jsonl"
    scored_csv = OUT / "final_scored_results.csv"
    write_jsonl(scored_jsonl, final_rows)
    write_csv(scored_csv, final_rows)
    shutil.copyfile(RUNTIME_FAILURES, OUT / "runtime_failures.jsonl")

    adjudications = []
    for row in final_rows:
        if row["manual_adjudication"]:
            adjudications.append(
                {
                    "instance_id": row["instance_id"],
                    "original_answer_correct": row["original_answer_correct"],
                    "original_hallucination": row["original_hallucination"],
                    "original_error_type": row["original_error_type"],
                    "final_answer_correct": row["answer_correct"],
                    "final_hallucination": row["hallucination"],
                    "final_error_type": row["error_type"],
                    "adjudication_method": row["adjudication_method"],
                    "adjudication_reason": row["adjudication_reason"],
                }
            )
    (OUT / "manual_adjudications.json").write_text(json.dumps(adjudications, indent=2, sort_keys=True) + "\n")

    final_hash = sha256(scored_jsonl)
    integrity = {
        "source_scored_results_hash": actual_src_hash,
        "final_scored_results_hash": final_hash,
        "frozen_grader_hash": GRADER_HASH,
        "rows": len(final_rows),
        "unique_instance_ids": len({r["instance_id"] for r in final_rows}),
        "runtime_failures": len(failures),
        "manual_adjudications": len(adjudications),
        "remaining_ambiguous": summary["ambiguous"],
        "non_adjudicated_rows_unchanged": unchanged,
        "only_documented_override_ids_changed": sorted(r["instance_id"] for r in final_rows if r["manual_adjudication"]) == sorted(override_ids),
        "raw_outputs_unchanged": True,
        "gold_metadata_unchanged": True,
        "context_counts": {k: v["gradable"] for k, v in summary["by_context"].items()},
        "runtime_failure_context_counts": {k: v["runtime_failures"] for k, v in summary["by_context"].items()},
    }
    (OUT / "final_integrity_report.json").write_text(json.dumps(integrity, indent=2, sort_keys=True) + "\n")
    (OUT / "final_grading_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_scored_results": str(SRC),
        "input_scored_results_hash": actual_src_hash,
        "runtime_failures": str(RUNTIME_FAILURES),
        "frozen_grader_hash": GRADER_HASH,
        "manual_adjudication_count": len(adjudications),
        "final_scored_results_jsonl": str(scored_jsonl),
        "final_scored_results_csv": str(scored_csv),
        "final_scored_results_hash": final_hash,
        "semantic_grading_rules_changed": False,
    }
    (OUT / "final_dataset_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "ok", "final_hash": final_hash, "summary": summary}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
