from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from longctx_dataset.grading import grade_answer_only_response
from longctx_dataset.schemas import Instance, QuestionFamily
from longctx_dataset.storage.io import iter_jsonl


RESULTS_PATH = Path("data/inference_llama32_3b_4k64k_v3/results.jsonl")
DATASET_DIR = Path("data/preproduction_llama32_3b_v2")
GRADER_PATH = Path("src/longctx_dataset/grading.py")
OUT_DIR = Path("data/grading_experiment_c_full_v1")
EXPECTED_CONTEXTS = ["4K", "8K", "16K", "32K", "64K"]
EXPECTED_ROWS = 500


CSV_FIELDS = [
    "instance_id",
    "question_family_id",
    "domain",
    "question_type",
    "context_length_label",
    "answerable",
    "gold_answer",
    "raw_output_text",
    "parsed_answer",
    "normalized_gold_answer",
    "normalized_model_answer",
    "answer_correct",
    "abstention_correct",
    "hallucination",
    "error_type",
    "matched_context_value",
    "matched_distractor_type",
    "grading_rule_used",
    "needs_semantic_review",
    "review_reason",
    "input_tokens",
    "generated_tokens_count",
    "generation_latency_seconds",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def load_inputs() -> tuple[dict[str, Instance], dict[str, QuestionFamily], list[dict[str, Any]]]:
    instances = {
        row["instance_id"]: Instance.model_validate(row)
        for row in iter_jsonl(DATASET_DIR / "instances.jsonl")
    }
    families = {
        row["question_family_id"]: QuestionFamily.model_validate(row)
        for row in iter_jsonl(DATASET_DIR / "question_families.jsonl")
    }
    results = list(iter_jsonl(RESULTS_PATH))
    return instances, families, results


def validate_inputs(instances: dict[str, Instance], results: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if len(results) != EXPECTED_ROWS:
        errors.append(f"expected {EXPECTED_ROWS} inference results, found {len(results)}")
    result_ids = [row.get("instance_id") for row in results]
    if len(set(result_ids)) != len(result_ids):
        errors.append("inference results contain duplicate instance IDs")
    missing_instances = sorted(set(result_ids) - set(instances))
    if missing_instances:
        errors.append(f"inference results reference unknown instances: {missing_instances[:10]}")
    context_counts = Counter(row.get("context_length_label") for row in results)
    for label in EXPECTED_CONTEXTS:
        if context_counts[label] != 100:
            errors.append(f"expected 100 results for {label}, found {context_counts[label]}")
    extra_contexts = sorted(set(context_counts) - set(EXPECTED_CONTEXTS))
    if extra_contexts:
        errors.append(f"unexpected context labels: {extra_contexts}")
    return errors


def write_outputs(
    scored: list[dict[str, Any]],
    *,
    grader_hash_before: str,
    grader_hash_after: str,
    raw_hash_before: str,
    raw_hash_after: str,
    started_at: str,
    completed_at: str,
) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in [
        "scored_results.jsonl",
        "scored_results.csv",
        "grading_summary.json",
        "grading_integrity_report.json",
        "grader_freeze_manifest.json",
        "grading_report.md",
    ]:
        path = OUT_DIR / name
        if path.exists():
            path.unlink()

    for row in scored:
        append_jsonl(OUT_DIR / "scored_results.jsonl", row)

    with (OUT_DIR / "scored_results.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in scored:
            writer.writerow({k: row.get(k) for k in CSV_FIELDS})

    context_counts = Counter(row["context_length_label"] for row in scored)
    error_counts = Counter(row["error_type"] for row in scored)
    semantic_review = sum(row["needs_semantic_review"] for row in scored)
    correct = sum(row["answer_correct"] is True for row in scored)
    hallucination_true = sum(row["hallucination"] is True for row in scored)
    hallucination_false = sum(row["hallucination"] is False for row in scored)
    summary = {
        "total_scored_rows": len(scored),
        "unique_instance_ids": len({row["instance_id"] for row in scored}),
        "context_counts": dict(context_counts),
        "answer_correct_true": correct,
        "answer_correct_false": sum(row["answer_correct"] is False for row in scored),
        "hallucination_true": hallucination_true,
        "hallucination_false": hallucination_false,
        "hallucination_null": sum(row["hallucination"] is None for row in scored),
        "semantic_review_count": semantic_review,
        "error_type_counts": dict(error_counts),
    }
    (OUT_DIR / "grading_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    integrity_errors = []
    if len(scored) != EXPECTED_ROWS:
        integrity_errors.append(f"expected {EXPECTED_ROWS} scored rows, found {len(scored)}")
    if len({row["instance_id"] for row in scored}) != len(scored):
        integrity_errors.append("duplicate scored instance IDs")
    for label in EXPECTED_CONTEXTS:
        if context_counts[label] != 100:
            integrity_errors.append(f"expected 100 scored rows for {label}, found {context_counts[label]}")
    extra_contexts = sorted(set(context_counts) - set(EXPECTED_CONTEXTS))
    if extra_contexts:
        integrity_errors.append(f"unexpected scored context labels: {extra_contexts}")
    if raw_hash_before != raw_hash_after:
        integrity_errors.append("raw Experiment C results hash changed during grading")
    if grader_hash_before != grader_hash_after:
        integrity_errors.append("grader hash changed during scoring")

    integrity = {
        "passed": not integrity_errors,
        "errors": integrity_errors,
        "expected_rows": EXPECTED_ROWS,
        "scored_rows": len(scored),
        "unique_instance_ids": len({row["instance_id"] for row in scored}),
        "context_counts": dict(context_counts),
        "raw_results_hash_before": raw_hash_before,
        "raw_results_hash_after": raw_hash_after,
        "raw_outputs_unchanged": raw_hash_before == raw_hash_after,
        "grader_hash_before": grader_hash_before,
        "grader_hash_after": grader_hash_after,
        "grader_unchanged_during_scoring": grader_hash_before == grader_hash_after,
        "no_llm_judge_used": True,
        "no_fuzzy_semantic_grader_used": True,
        "evidence_accuracy_graded": False,
    }
    (OUT_DIR / "grading_integrity_report.json").write_text(
        json.dumps(integrity, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "created_at": completed_at,
        "scoring_started_at": started_at,
        "scoring_completed_at": completed_at,
        "grader_path": str(GRADER_PATH),
        "grader_sha256": grader_hash_before,
        "grader_hash_after_scoring": grader_hash_after,
        "grading_function": "longctx_dataset.grading.grade_answer_only_response",
        "response_contract": "Experiment C answer-only: ANSWER: <answer>",
        "raw_results_path": str(RESULTS_PATH),
        "raw_results_sha256": raw_hash_before,
        "dataset_dir": str(DATASET_DIR),
        "tests_required_before_scoring": "conda run -n longctx-llama-infer python -m pytest tests/test_grading.py",
        "grading_semantics_frozen_before_aggregate_results": True,
    }
    (OUT_DIR / "grader_freeze_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Experiment C Full Deterministic Grading",
        "",
        f"- grader sha256: `{grader_hash_before}`",
        f"- total scored rows: `{len(scored)}`",
        f"- unique instance IDs: `{len({row['instance_id'] for row in scored})}`",
        f"- context counts: `{dict(context_counts)}`",
        f"- answer correct: `{summary['answer_correct_true']}`",
        f"- answer incorrect: `{summary['answer_correct_false']}`",
        f"- hallucination=true: `{summary['hallucination_true']}`",
        f"- hallucination=false: `{summary['hallucination_false']}`",
        f"- semantic review count: `{semantic_review}`",
        f"- error type counts: `{dict(error_counts)}`",
        f"- raw outputs unchanged: `{raw_hash_before == raw_hash_after}`",
        f"- grader unchanged during scoring: `{grader_hash_before == grader_hash_after}`",
        "",
        "Evidence-selection accuracy is intentionally not graded for Experiment C because the model was not asked to output evidence IDs.",
        "No LLM judge, fuzzy semantic grader, hypothesis test, confidence interval, regression, or trend analysis was run.",
        "",
    ]
    if semantic_review:
        lines.append("## Semantic Review Cases")
        lines.append("")
        for row in scored:
            if row["needs_semantic_review"]:
                lines.append(
                    f"- `{row['instance_id']}`: `{row['error_type']}` / {row.get('review_reason') or ''}"
                )
    (OUT_DIR / "grading_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    started_at = datetime.now(timezone.utc).isoformat()
    grader_hash_before = sha256_file(GRADER_PATH)
    raw_hash_before = sha256_file(RESULTS_PATH)
    instances, families, results = load_inputs()
    input_errors = validate_inputs(instances, results)
    if input_errors:
        for err in input_errors:
            print(f"ERROR: {err}", flush=True)
        return 1

    scored = [
        grade_answer_only_response(
            instances[row["instance_id"]],
            row,
            family=families[instances[row["instance_id"]].question_family_id],
        )
        for row in results
    ]
    grader_hash_after = sha256_file(GRADER_PATH)
    raw_hash_after = sha256_file(RESULTS_PATH)
    completed_at = datetime.now(timezone.utc).isoformat()
    write_outputs(
        scored,
        grader_hash_before=grader_hash_before,
        grader_hash_after=grader_hash_after,
        raw_hash_before=raw_hash_before,
        raw_hash_after=raw_hash_after,
        started_at=started_at,
        completed_at=completed_at,
    )
    summary = json.loads((OUT_DIR / "grading_summary.json").read_text(encoding="utf-8"))
    integrity = json.loads((OUT_DIR / "grading_integrity_report.json").read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "grader_sha256": grader_hash_before,
                "total_scored_rows": summary["total_scored_rows"],
                "unique_instance_ids": summary["unique_instance_ids"],
                "semantic_review_count": summary["semantic_review_count"],
                "answer_correct_true": summary["answer_correct_true"],
                "answer_correct_false": summary["answer_correct_false"],
                "hallucination_true": summary["hallucination_true"],
                "hallucination_false": summary["hallucination_false"],
                "error_type_counts": summary["error_type_counts"],
                "integrity_passed": integrity["passed"],
                "output_dir": str(OUT_DIR),
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        ),
        flush=True,
    )
    return 0 if integrity["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
