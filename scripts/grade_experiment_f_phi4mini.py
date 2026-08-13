#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import platform
import random
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from longctx_dataset.grading import ERROR_FORMAT_FAILURE, grade_answer_only_response
from longctx_dataset.schemas import Instance, QuestionFamily
from longctx_dataset.storage.io import iter_jsonl


DATASET_DIR = Path("data/preproduction_llama32_3b_500f_6ctx_v1")
RESULTS_PATH = Path("data/inference_phi4mini_500f_6ctx_v1/results.jsonl")
FAILURES_PATH = Path("data/inference_phi4mini_500f_6ctx_v1/failures.jsonl")
INFERENCE_INTEGRITY_PATH = Path("data/inference_phi4mini_500f_6ctx_v1/integrity_report.json")
OUT_DIR = Path("data/grading_experiment_f_phi4mini_v1")
MANUAL_RESOLUTIONS_PATH = OUT_DIR / "manual_resolutions.jsonl"
GRADER_PATH = Path("src/longctx_dataset/grading.py")
SCRIPT_PATH = Path("scripts/grade_experiment_f_phi4mini.py")

EXPECTED_DATASET_HASH = "dc2c4194dedb090198e6883735257908ce274bebc8611b40d958dbd026aa1fe6"
FROZEN_GRADER_HASH = "d9282a0ccc50daba3bfd232c058dfbab63a5c19a7323d585a7c2236b3a6c4ba8"
EXPECTED_CONTEXTS = ["4K", "8K", "16K", "32K", "64K", "82K"]
AUDIT_SEED = 20260812

CSV_FIELDS = [
    "instance_id", "question_family_id", "context_length_label", "domain", "question_type", "answerable",
    "question", "gold_answer", "raw_output_text", "parsed_answer", "normalized_gold_answer",
    "normalized_model_answer", "answer_correct", "abstention_correct", "hallucination",
    "factual_outcome", "inaccuracy_class", "error_type", "grading_method", "grading_rule_used",
    "needs_semantic_review", "review_reason", "matched_context_value", "matched_distractor_type",
    "input_tokens", "generated_tokens_count", "generation_latency_seconds", "execution_order_index",
    "peak_allocated_vram_bytes", "peak_reserved_vram_bytes",
    "grader_hash",
    "manual_resolution_applied", "manual_resolution_reason",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def dataset_hash() -> str:
    h = hashlib.sha256()
    for path in [DATASET_DIR / "question_families.jsonl", DATASET_DIR / "instances.jsonl"]:
        h.update(path.as_posix().encode("utf-8"))
        h.update(b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(chunk)
        h.update(b"\0")
    return h.hexdigest()


def load_inputs() -> tuple[dict[str, Instance], dict[str, QuestionFamily], list[dict[str, Any]], list[dict[str, Any]]]:
    instances = {row["instance_id"]: Instance.model_validate(row) for row in iter_jsonl(DATASET_DIR / "instances.jsonl")}
    families = {row["question_family_id"]: QuestionFamily.model_validate(row) for row in iter_jsonl(DATASET_DIR / "question_families.jsonl")}
    results = list(iter_jsonl(RESULTS_PATH))
    failures = list(iter_jsonl(FAILURES_PATH)) if FAILURES_PATH.exists() else []
    return instances, families, results, failures


def verify_inputs(instances: dict[str, Instance], results: list[dict[str, Any]], failures: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    observed_hash = dataset_hash()
    if observed_hash != EXPECTED_DATASET_HASH:
        errors.append(f"dataset hash mismatch: {observed_hash}")
    integrity = json.loads(INFERENCE_INTEGRITY_PATH.read_text())
    if not integrity.get("passed"):
        errors.append("inference integrity report did not pass")
    all_ids = [row["instance_id"] for row in results + failures]
    if len(all_ids) != len(set(all_ids)):
        errors.append("duplicate raw result/failure instance IDs")
    if set(all_ids) != set(instances):
        errors.append("raw results/failures do not cover the frozen 3000-instance set exactly")
    result_counts = Counter(row["context_length_label"] for row in results)
    failure_counts = Counter(row["context_length_label"] for row in failures)
    for ctx in EXPECTED_CONTEXTS:
        if result_counts.get(ctx, 0) + failure_counts.get(ctx, 0) != 500:
            errors.append(f"context {ctx} accounting mismatch: success={result_counts.get(ctx,0)} failure={failure_counts.get(ctx,0)}")
    # Phi sometimes omitted the required literal "ANSWER:" prefix while still
    # emitting a short answer. Preserve those raw outputs and let the frozen
    # deterministic grader classify them through its FORMAT_FAILURE path.
    return errors


def add_reporting_fields(row: dict[str, Any], grader_hash: str) -> dict[str, Any]:
    answer_correct = row.get("answer_correct")
    hallucination = row.get("hallucination")
    factual_outcome = "CORRECT" if answer_correct is True else "INACCURATE"
    if answer_correct is True or row.get("error_type") == "AMBIGUOUS_REVIEW_REQUIRED":
        inaccuracy_class = None
    elif hallucination is True:
        inaccuracy_class = "HALLUCINATORY_INACCURACY"
    elif hallucination is False:
        inaccuracy_class = "GROUNDED_INACCURACY"
    else:
        inaccuracy_class = None
    row.update({
        "factual_outcome": factual_outcome,
        "inaccuracy_class": inaccuracy_class,
        "grading_method": "deterministic_answer_only_experiment_c_rules",
        "grader_hash": grader_hash,
        "manual_resolution_applied": bool(row.get("manual_resolution_applied")),
        "manual_resolution_reason": row.get("manual_resolution_reason"),
    })
    return row


def load_manual_resolutions() -> dict[str, dict[str, Any]]:
    if not MANUAL_RESOLUTIONS_PATH.exists():
        return {}
    resolutions: dict[str, dict[str, Any]] = {}
    for line in MANUAL_RESOLUTIONS_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        instance_id = row["instance_id"]
        if instance_id in resolutions:
            raise SystemExit(f"duplicate manual resolution for {instance_id}")
        resolutions[instance_id] = row
    return resolutions


def recompute_reporting_fields(row: dict[str, Any]) -> None:
    answer_correct = row.get("answer_correct")
    hallucination = row.get("hallucination")
    row["factual_outcome"] = "CORRECT" if answer_correct is True else "INACCURATE"
    if answer_correct is True:
        row["inaccuracy_class"] = None
    elif hallucination is True:
        row["inaccuracy_class"] = "HALLUCINATORY_INACCURACY"
    elif hallucination is False:
        row["inaccuracy_class"] = "GROUNDED_INACCURACY"
    else:
        row["inaccuracy_class"] = None


def apply_manual_resolutions(scored: list[dict[str, Any]], resolutions: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not resolutions:
        return scored, []

    by_id = {row["instance_id"]: row for row in scored}
    missing = sorted(set(resolutions) - set(by_id))
    if missing:
        raise SystemExit(f"manual resolutions refer to unknown instances: {missing}")

    audit: list[dict[str, Any]] = []
    for instance_id, resolution in resolutions.items():
        row = by_id[instance_id]
        if row["error_type"] != "AMBIGUOUS_REVIEW_REQUIRED":
            raise SystemExit(f"manual resolution for non-ambiguous row {instance_id}: {row['error_type']}")
        before = {
            "answer_correct": row.get("answer_correct"),
            "hallucination": row.get("hallucination"),
            "error_type": row.get("error_type"),
            "inaccuracy_class": row.get("inaccuracy_class"),
            "review_reason": row.get("review_reason"),
        }
        for key in ["answer_correct", "hallucination", "error_type"]:
            if key not in resolution:
                raise SystemExit(f"manual resolution for {instance_id} lacks {key}")
            row[key] = resolution[key]
        row["needs_semantic_review"] = False
        row["review_reason"] = "manual_resolution_applied"
        row["grading_rule_used"] = "manual_resolution_of_frozen_grader_ambiguous_case"
        row["manual_resolution_applied"] = True
        row["manual_resolution_reason"] = resolution.get("reason", "")
        recompute_reporting_fields(row)
        audit.append({
            "instance_id": instance_id,
            "before": before,
            "after": {
                "answer_correct": row.get("answer_correct"),
                "hallucination": row.get("hallucination"),
                "error_type": row.get("error_type"),
                "inaccuracy_class": row.get("inaccuracy_class"),
                "review_reason": row.get("review_reason"),
            },
            "reason": row["manual_resolution_reason"],
        })
    return scored, audit


def grade_rows(raw_rows: list[dict[str, Any]], instances: dict[str, Instance], families: dict[str, QuestionFamily], grader_hash: str) -> list[dict[str, Any]]:
    scored = []
    for raw in raw_rows:
        inst = instances[raw["instance_id"]]
        family = families[inst.question_family_id]
        row = grade_answer_only_response(inst, raw, family=family)
        scored.append(add_reporting_fields(row, grader_hash))
    return scored


def stratified_audit_sample(results: list[dict[str, Any]], instances: dict[str, Instance]) -> list[dict[str, Any]]:
    by_id = {row["instance_id"]: row for row in results}
    selected: list[str] = []
    selected_set: set[str] = set()

    def add_matching(predicate, n: int) -> None:
        pool = [row for row in results if row["instance_id"] not in selected_set and predicate(instances[row["instance_id"]], row)]
        random.Random(AUDIT_SEED + len(selected)).shuffle(pool)
        for row in pool[:n]:
            selected.append(row["instance_id"])
            selected_set.add(row["instance_id"])

    for label in EXPECTED_CONTEXTS:
        add_matching(lambda inst, raw, label=label: inst.context_length_label == label, 15 if label in {"64K", "82K"} else 12)
    for domain in ["SEC", "FDA", "CLINICAL_TRIALS", "FRED"]:
        current = sum(instances[i].domain.value == domain for i in selected)
        add_matching(lambda inst, raw, domain=domain: inst.domain.value == domain, max(0, 20 - current))
    for qtype in ["DIRECT_RETRIEVAL", "RETRIEVAL_CALCULATION", "TEMPORAL_VERSION", "ENTITY_UNIT_BINDING", "UNANSWERABLE"]:
        current = sum(instances[i].question_type.value == qtype for i in selected)
        add_matching(lambda inst, raw, qtype=qtype: inst.question_type.value == qtype, max(0, 12 - current))
    add_matching(lambda inst, raw: str(raw.get("parsed_answer")).casefold() == "insufficient_evidence", 8)
    add_matching(lambda inst, raw: str(raw.get("parsed_answer")).casefold() != "insufficient_evidence", 8)
    if len(selected) < 100:
        pool = [row for row in results if row["instance_id"] not in selected_set]
        random.Random(AUDIT_SEED).shuffle(pool)
        for row in pool[: 100 - len(selected)]:
            selected.append(row["instance_id"])
            selected_set.add(row["instance_id"])
    return [by_id[iid] for iid in selected[:100]]


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in fields})


def audit_payload(scored: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "sample_size": len(scored),
        "counts_by_context": dict(Counter(row["context_length_label"] for row in scored)),
        "counts_by_domain": dict(Counter(row["domain"] for row in scored)),
        "counts_by_question_type": dict(Counter(row["question_type"] for row in scored)),
        "error_type_counts": dict(Counter(row["error_type"] for row in scored)),
        "answer_correct_counts": dict(Counter(str(row["answer_correct"]) for row in scored)),
        "hallucination_counts": dict(Counter(str(row["hallucination"]) for row in scored)),
        "semantic_review_count": sum(bool(row["needs_semantic_review"]) for row in scored),
        "format_failure_count": sum(row["error_type"] == ERROR_FORMAT_FAILURE for row in scored),
    }


def write_runtime_failures(failures: list[dict[str, Any]], instances: dict[str, Instance]) -> list[dict[str, Any]]:
    rows = []
    for failure in failures:
        inst = instances[failure["instance_id"]]
        rows.append({
            "instance_id": inst.instance_id,
            "question_family_id": inst.question_family_id,
            "context_length_label": inst.context_length_label,
            "domain": inst.domain.value,
            "question_type": inst.question_type.value,
            "answerable": inst.answerable,
            "rendered_input_tokens": failure.get("input_tokens"),
            "failure_status": "RUNTIME_FAILURE",
            "failure_type": failure.get("status") or failure.get("failure_type"),
            "error_type": failure.get("error_type"),
            "error_message": failure.get("error_message"),
        })
    with (OUT_DIR / "runtime_failures.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return rows


def summary_payload(scored: list[dict[str, Any]], runtime_failures: list[dict[str, Any]]) -> dict[str, Any]:
    by_context: dict[str, dict[str, Any]] = {}
    for label in EXPECTED_CONTEXTS:
        group = [row for row in scored if row["context_length_label"] == label]
        by_context[label] = {
            "gradable_n": len(group),
            "correct": sum(row["answer_correct"] is True for row in group),
            "inaccurate": sum(row["answer_correct"] is False for row in group),
            "hallucinatory_inaccuracy": sum(row.get("inaccuracy_class") == "HALLUCINATORY_INACCURACY" for row in group),
            "grounded_inaccuracy": sum(row.get("inaccuracy_class") == "GROUNDED_INACCURACY" for row in group),
            "ambiguous": sum(row["error_type"] == "AMBIGUOUS_REVIEW_REQUIRED" for row in group),
            "format_failure": sum(row["error_type"] == ERROR_FORMAT_FAILURE for row in group),
            "runtime_failures": sum(row["context_length_label"] == label for row in runtime_failures),
        }
    return {
        "successful_responses_graded": len(scored),
        "runtime_failures": len(runtime_failures),
        "correct": sum(row["answer_correct"] is True for row in scored),
        "inaccurate": sum(row["answer_correct"] is False for row in scored),
        "hallucinatory_inaccuracy": sum(row.get("inaccuracy_class") == "HALLUCINATORY_INACCURACY" for row in scored),
        "grounded_inaccuracy": sum(row.get("inaccuracy_class") == "GROUNDED_INACCURACY" for row in scored),
        "ambiguous_review": sum(row["error_type"] == "AMBIGUOUS_REVIEW_REQUIRED" for row in scored),
        "format_failure": sum(row["error_type"] == ERROR_FORMAT_FAILURE for row in scored),
        "error_type_counts": dict(Counter(row["error_type"] for row in scored)),
        "counts_by_context": by_context,
    }


def write_error_counts_by_context(scored: list[dict[str, Any]]) -> None:
    error_types = sorted(Counter(row["error_type"] for row in scored))
    fields = ["context_length_label", "gradable_n", *error_types]
    rows = []
    for label in EXPECTED_CONTEXTS:
        group = [row for row in scored if row["context_length_label"] == label]
        counts = Counter(row["error_type"] for row in group)
        rows.append({"context_length_label": label, "gradable_n": len(group), **{etype: counts.get(etype, 0) for etype in error_types}})
    write_csv(OUT_DIR / "error_counts_by_context.csv", rows, fields)


def write_outputs(scored: list[dict[str, Any]], runtime_failures: list[dict[str, Any]], audit: list[dict[str, Any]], *, manual_audit: list[dict[str, Any]], grader_hash: str, script_hash: str, raw_hash: str, failure_hash: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUT_DIR / "scored_results.jsonl").open("w", encoding="utf-8") as handle:
        for row in scored:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    write_csv(OUT_DIR / "scored_results.csv", scored, CSV_FIELDS)
    instances = {row["instance_id"]: Instance.model_validate(row) for row in iter_jsonl(DATASET_DIR / "instances.jsonl")}
    write_runtime_failures(runtime_failures, instances)
    write_error_counts_by_context(scored)
    (OUT_DIR / "grader_audit.json").write_text(json.dumps({"audit": audit_payload(audit), "cases": audit}, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    (OUT_DIR / "manual_resolution_audit.json").write_text(json.dumps({"count": len(manual_audit), "cases": manual_audit}, indent=2, ensure_ascii=False, sort_keys=True) + "\n")

    summary = summary_payload(scored, runtime_failures)
    scored_hash = sha256_file(OUT_DIR / "scored_results.jsonl")
    summary["scored_results_sha256"] = scored_hash
    (OUT_DIR / "grading_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n")

    integrity = {
        "passed": True,
        "expected_inference_attempts": 3000,
        "successful_outputs": len(scored),
        "factual_graded_rows": len(scored),
        "runtime_failures": len(runtime_failures),
        "unique_scored_instance_ids": len({r["instance_id"] for r in scored}),
        "unique_runtime_failure_ids": len({r["instance_id"] for r in runtime_failures}),
        "context_counts": dict(Counter(row["context_length_label"] for row in scored)),
        "raw_results_sha256": raw_hash,
        "raw_failures_sha256": failure_hash,
        "grader_hash": grader_hash,
        "dataset_hash": dataset_hash(),
        "frozen_benchmark_unchanged": dataset_hash() == EXPECTED_DATASET_HASH,
        "no_llm_judge_used": True,
        "no_statistical_hypothesis_testing_performed": True,
        "manual_resolution_count": len(manual_audit),
    }
    (OUT_DIR / "grading_integrity_report.json").write_text(json.dumps(integrity, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    manifest = {
        "created_at": utc_now(),
        "dataset_dir": str(DATASET_DIR),
        "dataset_hash": EXPECTED_DATASET_HASH,
        "raw_results_path": str(RESULTS_PATH),
        "raw_results_sha256": raw_hash,
        "raw_failures_path": str(FAILURES_PATH),
        "raw_failures_sha256": failure_hash,
        "frozen_grader_hash": FROZEN_GRADER_HASH,
        "observed_grader_hash": grader_hash,
        "grading_script_hash": script_hash,
        "semantic_grading_rules_changed_from_experiment_d": False,
        "manual_resolutions_path": str(MANUAL_RESOLUTIONS_PATH),
        "manual_resolution_count": len(manual_audit),
        "audit_result": audit_payload(audit),
        "python_version": sys.version,
        "platform": platform.platform(),
    }
    (OUT_DIR / "grader_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n")

    lines = [
        "# Experiment F Phi-4-mini Deterministic Grading",
        "",
        f"- successful responses graded: `{summary['successful_responses_graded']}`",
        f"- runtime failures excluded from factual grading: `{summary['runtime_failures']}`",
        f"- correct: `{summary['correct']}`",
        f"- inaccurate: `{summary['inaccurate']}`",
        f"- hallucinatory inaccuracies: `{summary['hallucinatory_inaccuracy']}`",
        f"- grounded inaccuracies: `{summary['grounded_inaccuracy']}`",
        f"- ambiguous-review cases: `{summary['ambiguous_review']}`",
        f"- format failures: `{summary['format_failure']}`",
        f"- manual resolutions applied: `{len(manual_audit)}`",
        f"- grader hash: `{grader_hash}`",
        f"- scored results hash: `{scored_hash}`",
        "",
        "| Context | Gradable N | Correct | Inaccurate | Hallucinatory | Grounded | Ambiguous | Runtime failures |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in EXPECTED_CONTEXTS:
        c = summary["counts_by_context"][label]
        lines.append(f"| {label} | {c['gradable_n']} | {c['correct']} | {c['inaccurate']} | {c['hallucinatory_inaccuracy']} | {c['grounded_inaccuracy']} | {c['ambiguous']} | {c['runtime_failures']} |")
    (OUT_DIR / "grading_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    grader_hash = sha256_file(GRADER_PATH)
    if grader_hash != FROZEN_GRADER_HASH:
        raise SystemExit(f"grader hash differs from frozen hash: {grader_hash}")
    script_hash = sha256_file(SCRIPT_PATH)
    raw_hash = sha256_file(RESULTS_PATH)
    failure_hash = sha256_file(FAILURES_PATH)
    test = subprocess.run([sys.executable, "-m", "pytest", "tests/test_grading.py"], cwd=Path.cwd(), capture_output=True, text=True, check=False)
    if test.returncode != 0:
        (OUT_DIR / "test_failure.json").write_text(json.dumps({"stdout": test.stdout[-4000:], "stderr": test.stderr[-4000:]}, indent=2) + "\n")
        raise SystemExit("grading tests failed")
    instances, families, results, failures = load_inputs()
    errors = verify_inputs(instances, results, failures)
    if errors:
        raise SystemExit("input verification failed: " + "; ".join(errors))
    audit = grade_rows(stratified_audit_sample(results, instances), instances, families, grader_hash)
    scored = grade_rows(results, instances, families, grader_hash)
    resolutions = load_manual_resolutions()
    scored, manual_audit = apply_manual_resolutions(scored, resolutions)
    ambiguous = [row for row in scored if row["error_type"] == "AMBIGUOUS_REVIEW_REQUIRED"]
    if ambiguous:
        with (OUT_DIR / "manual_review_cases.jsonl").open("w", encoding="utf-8") as handle:
            for row in ambiguous:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        raise SystemExit(f"deterministic grading produced {len(ambiguous)} ambiguous cases; inspect manual_review_cases.jsonl")
    stale_review_path = OUT_DIR / "manual_review_cases.jsonl"
    if stale_review_path.exists():
        stale_review_path.unlink()
    write_outputs(scored, failures, audit, manual_audit=manual_audit, grader_hash=grader_hash, script_hash=script_hash, raw_hash=raw_hash, failure_hash=failure_hash)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
