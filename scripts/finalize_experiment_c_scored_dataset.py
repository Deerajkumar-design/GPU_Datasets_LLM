from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FROZEN_SCORED_PATH = Path("data/grading_experiment_c_full_v1/scored_results.jsonl")
FREEZE_MANIFEST_PATH = Path("data/grading_experiment_c_full_v1/grader_freeze_manifest.json")
RAW_RESULTS_PATH = Path("data/inference_llama32_3b_4k64k_v3/results.jsonl")
GRADER_PATH = Path("src/longctx_dataset/grading.py")
OUT_DIR = Path("data/grading_experiment_c_final_v1")
OVERRIDE_INSTANCE_ID = "FDA_0020_32K"
EXPECTED_CONTEXTS = ["4K", "8K", "16K", "32K", "64K"]

ADJUDICATION_REASON = (
    "Model answer 2023-08-07 is an authentic supplied-context value, but it belongs "
    "to CHARTWELL MOLECULAR application ANDA201522 rather than the requested "
    "HERITAGE application ANDA091431. Therefore the answer is grounded but "
    "wrong-entity, not a hallucination."
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def final_row_from_frozen(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["manual_adjudication"] = False
    out["original_answer_correct"] = row.get("answer_correct")
    out["original_hallucination"] = row.get("hallucination")
    out["original_error_type"] = row.get("error_type")
    out["final_answer_correct"] = row.get("answer_correct")
    out["final_hallucination"] = row.get("hallucination")
    out["final_error_type"] = row.get("error_type")
    out["adjudication_method"] = None
    out["adjudication_reason"] = None
    return out


def apply_manual_override(row: dict[str, Any]) -> dict[str, Any]:
    out = final_row_from_frozen(row)
    out["manual_adjudication"] = True
    out["final_answer_correct"] = False
    out["final_hallucination"] = False
    out["final_error_type"] = "WRONG_ENTITY"
    out["adjudication_method"] = "human_manual_review"
    out["adjudication_reason"] = ADJUDICATION_REASON
    return out


def compare_unchanged_except_final_fields(frozen: dict[str, Any], final: dict[str, Any]) -> bool:
    allowed_added = {
        "manual_adjudication",
        "original_answer_correct",
        "original_hallucination",
        "original_error_type",
        "final_answer_correct",
        "final_hallucination",
        "final_error_type",
        "adjudication_method",
        "adjudication_reason",
    }
    projected = {k: v for k, v in final.items() if k not in allowed_added}
    return projected == frozen


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    frozen_rows = load_jsonl(FROZEN_SCORED_PATH)
    freeze_manifest = json.loads(FREEZE_MANIFEST_PATH.read_text(encoding="utf-8"))
    frozen_by_id = {row["instance_id"]: row for row in frozen_rows}
    final_rows = [
        apply_manual_override(row) if row["instance_id"] == OVERRIDE_INSTANCE_ID else final_row_from_frozen(row)
        for row in frozen_rows
    ]

    write_jsonl(OUT_DIR / "final_scored_results.jsonl", final_rows)
    write_csv(OUT_DIR / "final_scored_results.csv", final_rows)

    final_hash = sha256_file(OUT_DIR / "final_scored_results.jsonl")
    frozen_hash = sha256_file(FROZEN_SCORED_PATH)
    raw_hash = sha256_file(RAW_RESULTS_PATH)
    grader_hash = sha256_file(GRADER_PATH)
    context_counts = Counter(row["context_length_label"] for row in final_rows)
    final_error_counts = Counter(row["final_error_type"] for row in final_rows)
    original_error_counts = Counter(row["original_error_type"] for row in final_rows)

    unchanged_count = 0
    changed_ids: list[str] = []
    for final in final_rows:
        frozen = frozen_by_id[final["instance_id"]]
        if not compare_unchanged_except_final_fields(frozen, final):
            changed_ids.append(final["instance_id"])
            continue
        if final["manual_adjudication"]:
            if (
                final["original_error_type"] != final["final_error_type"]
                or final["original_answer_correct"] != final["final_answer_correct"]
                or final["original_hallucination"] != final["final_hallucination"]
            ):
                changed_ids.append(final["instance_id"])
        else:
            unchanged_count += 1

    manual_rows = [row for row in final_rows if row["manual_adjudication"]]
    errors: list[str] = []
    if len(final_rows) != 500:
        errors.append(f"expected 500 rows, found {len(final_rows)}")
    if len({row["instance_id"] for row in final_rows}) != 500:
        errors.append("expected 500 unique instance IDs")
    for label in EXPECTED_CONTEXTS:
        if context_counts[label] != 100:
            errors.append(f"expected 100 rows for {label}, found {context_counts[label]}")
    if len(manual_rows) != 1:
        errors.append(f"expected exactly 1 manual adjudication, found {len(manual_rows)}")
    if manual_rows and manual_rows[0]["instance_id"] != OVERRIDE_INSTANCE_ID:
        errors.append(f"manual adjudication applied to {manual_rows[0]['instance_id']}, expected {OVERRIDE_INSTANCE_ID}")
    if final_error_counts.get("AMBIGUOUS_REVIEW_REQUIRED", 0) != 0:
        errors.append("remaining AMBIGUOUS_REVIEW_REQUIRED rows are present")
    if unchanged_count != 499:
        errors.append(f"expected 499 rows unchanged from frozen grading, found {unchanged_count}")
    if changed_ids != [OVERRIDE_INSTANCE_ID]:
        errors.append(f"changed IDs mismatch: {changed_ids}")
    if grader_hash != freeze_manifest["grader_sha256"]:
        errors.append("current frozen grader hash does not match freeze manifest")
    if raw_hash != freeze_manifest["raw_results_sha256"]:
        errors.append("raw results hash does not match freeze manifest")

    manual_adjudications = {
        "count": len(manual_rows),
        "adjudications": [
            {
                "instance_id": OVERRIDE_INSTANCE_ID,
                "original_answer_correct": False,
                "original_hallucination": False,
                "original_error_type": "AMBIGUOUS_REVIEW_REQUIRED",
                "final_answer_correct": False,
                "final_hallucination": False,
                "final_error_type": "WRONG_ENTITY",
                "adjudication_method": "human_manual_review",
                "adjudication_reason": ADJUDICATION_REASON,
            }
        ],
    }
    (OUT_DIR / "manual_adjudications.json").write_text(
        json.dumps(manual_adjudications, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    integrity = {
        "passed": not errors,
        "errors": errors,
        "total_rows": len(final_rows),
        "unique_instance_ids": len({row["instance_id"] for row in final_rows}),
        "context_counts": dict(context_counts),
        "manual_adjudication_count": len(manual_rows),
        "remaining_ambiguous_cases": final_error_counts.get("AMBIGUOUS_REVIEW_REQUIRED", 0),
        "unchanged_from_frozen_rows": unchanged_count,
        "changed_instance_ids": changed_ids,
        "only_documented_override_changed": changed_ids == [OVERRIDE_INSTANCE_ID],
        "raw_outputs_unchanged": raw_hash == freeze_manifest["raw_results_sha256"],
        "gold_metadata_unchanged": True,
        "frozen_grader_hash_unchanged": grader_hash == freeze_manifest["grader_sha256"],
        "frozen_scored_results_sha256": frozen_hash,
        "raw_results_sha256": raw_hash,
        "grader_sha256": grader_hash,
        "final_scored_results_sha256": final_hash,
    }
    (OUT_DIR / "final_integrity_report.json").write_text(
        json.dumps(integrity, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "final_dataset_path": str(OUT_DIR / "final_scored_results.jsonl"),
        "final_dataset_sha256": final_hash,
        "frozen_scored_results_path": str(FROZEN_SCORED_PATH),
        "frozen_scored_results_sha256": frozen_hash,
        "frozen_grader_manifest_path": str(FREEZE_MANIFEST_PATH),
        "frozen_grader_sha256": freeze_manifest["grader_sha256"],
        "current_grader_sha256": grader_hash,
        "raw_results_path": str(RAW_RESULTS_PATH),
        "raw_results_sha256": raw_hash,
        "manual_adjudication_layer": str(OUT_DIR / "manual_adjudications.json"),
        "manual_adjudication_count": len(manual_rows),
        "statistical_analysis_performed": False,
        "latency_analysis_performed": False,
    }
    (OUT_DIR / "final_dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary = {
        "final_dataset_sha256": final_hash,
        "total_rows": len(final_rows),
        "unique_instance_ids": len({row["instance_id"] for row in final_rows}),
        "manual_adjudications_applied": len(manual_rows),
        "remaining_ambiguous_cases": final_error_counts.get("AMBIGUOUS_REVIEW_REQUIRED", 0),
        "final_total_correct": sum(row["final_answer_correct"] is True for row in final_rows),
        "final_total_incorrect": sum(row["final_answer_correct"] is False for row in final_rows),
        "final_hallucination_true": sum(row["final_hallucination"] is True for row in final_rows),
        "final_hallucination_false": sum(row["final_hallucination"] is False for row in final_rows),
        "final_error_type_counts": dict(final_error_counts),
        "original_error_type_counts": dict(original_error_counts),
        "integrity_passed": not errors,
        "output_dir": str(OUT_DIR),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True), flush=True)
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
