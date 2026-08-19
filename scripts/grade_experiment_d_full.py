from __future__ import annotations

import csv
import hashlib
import json
import platform
import random
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from longctx_dataset.grading import ERROR_CORRECT, ERROR_FORMAT_FAILURE, grade_answer_only_response
from longctx_dataset.schemas import Instance, QuestionFamily
from longctx_dataset.storage.io import iter_jsonl


DATASET_DIR = Path("data/preproduction_llama32_3b_500f_6ctx_v1")
RESULTS_PATH = Path("data/inference_llama32_3b_500f_6ctx_v1/results.jsonl")
FAILURES_PATH = Path("data/inference_llama32_3b_500f_6ctx_v1/failures.jsonl")
INFERENCE_INTEGRITY_PATH = Path("data/inference_llama32_3b_500f_6ctx_v1/integrity_report.json")
OUT_DIR = Path("data/grading_experiment_d_full_v1")
GRADER_PATH = Path("src/longctx_dataset/grading.py")
SCRIPT_PATH = Path("scripts/grade_experiment_d_full.py")

EXPECTED_DATASET_HASH = "dc2c4194dedb090198e6883735257908ce274bebc8611b40d958dbd026aa1fe6"
EXPERIMENT_C_GRADER_HASH = "d9282a0ccc50daba3bfd232c058dfbab63a5c19a7323d585a7c2236b3a6c4ba8"
EXPECTED_CONTEXTS = ["4K", "8K", "16K", "32K", "64K", "82K"]
AUDIT_SEED = 20260811

CSV_FIELDS = [
    "instance_id",
    "question_family_id",
    "context_length_label",
    "domain",
    "question_type",
    "answerable",
    "question",
    "gold_answer",
    "raw_output_text",
    "parsed_answer",
    "normalized_gold_answer",
    "normalized_model_answer",
    "answer_correct",
    "abstention_correct",
    "hallucination",
    "factual_outcome",
    "inaccuracy_class",
    "error_type",
    "grading_method",
    "grading_rule_used",
    "needs_semantic_review",
    "review_reason",
    "matched_context_value",
    "matched_distractor_type",
    "input_tokens",
    "generated_tokens_count",
    "generation_latency_seconds",
    "execution_order_index",
    "grader_hash",
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
    instances = {
        row["instance_id"]: Instance.model_validate(row)
        for row in iter_jsonl(DATASET_DIR / "instances.jsonl")
    }
    families = {
        row["question_family_id"]: QuestionFamily.model_validate(row)
        for row in iter_jsonl(DATASET_DIR / "question_families.jsonl")
    }
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
    if integrity.get("successful") != 2998 or integrity.get("failed") != 2:
        errors.append(f"unexpected inference counts: {integrity}")
    if len(results) != 2998:
        errors.append(f"expected 2998 successful raw results, found {len(results)}")
    if len(failures) != 2:
        errors.append(f"expected 2 runtime failures, found {len(failures)}")
    if Counter(row.get("status") for row in failures) != {"CUDA_OOM": 2}:
        errors.append(f"runtime failures are not exactly two CUDA_OOM rows: {Counter(row.get('status') for row in failures)}")
    all_ids = [row["instance_id"] for row in results + failures]
    if len(all_ids) != len(set(all_ids)):
        errors.append("duplicate raw result/failure instance IDs")
    if set(all_ids) != set(instances):
        errors.append("raw results/failures do not cover the frozen 3000-instance set exactly")
    result_counts = Counter(row["context_length_label"] for row in results)
    expected_gradable = {"4K": 500, "8K": 500, "16K": 500, "32K": 500, "64K": 500, "82K": 498}
    if result_counts != expected_gradable:
        errors.append(f"gradable context counts mismatch: {dict(result_counts)}")
    if any(row.get("format_failure") for row in results):
        errors.append("successful inference results contain format_failure=true")
    if any(row.get("hit_max_new_tokens_128") for row in results):
        errors.append("successful inference results contain hit_max_new_tokens_128=true")
    if any(row.get("degenerate_output") for row in results):
        errors.append("successful inference results contain degenerate_output=true")
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
    })
    return row


def grade_rows(
    raw_rows: list[dict[str, Any]],
    instances: dict[str, Instance],
    families: dict[str, QuestionFamily],
    grader_hash: str,
) -> list[dict[str, Any]]:
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
    # Exercise obvious structural answer varieties without semantic scoring: abstentions and factual-looking values.
    add_matching(lambda inst, raw: str(raw.get("parsed_answer")).casefold() == "insufficient_evidence", 8)
    add_matching(lambda inst, raw: str(raw.get("parsed_answer")).casefold() != "insufficient_evidence", 8)

    if len(selected) < 100:
        pool = [row for row in results if row["instance_id"] not in selected_set]
        random.Random(AUDIT_SEED).shuffle(pool)
        for row in pool[: 100 - len(selected)]:
            selected.append(row["instance_id"])
            selected_set.add(row["instance_id"])
    return [by_id[iid] for iid in selected[:100]]


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


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


def write_audit(scored: list[dict[str, Any]]) -> None:
    payload = audit_payload(scored)
    payload["cases"] = scored
    (OUT_DIR / "grader_audit.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    lines = [
        "# Experiment D Deterministic Grader Audit",
        "",
        f"- sample size: `{payload['sample_size']}`",
        f"- counts by context: `{payload['counts_by_context']}`",
        f"- counts by domain: `{payload['counts_by_domain']}`",
        f"- counts by question type: `{payload['counts_by_question_type']}`",
        f"- error type counts: `{payload['error_type_counts']}`",
        f"- semantic-review count: `{payload['semantic_review_count']}`",
        f"- format-failure count: `{payload['format_failure_count']}`",
        "",
        "## Cases",
        "",
    ]
    for row in scored:
        lines.extend([
            f"### {row['instance_id']}",
            "",
            f"- context: `{row['context_length_label']}`",
            f"- domain/type: `{row['domain']}` / `{row['question_type']}`",
            f"- question: {row['question']}",
            f"- gold: `{row['gold_answer']}`",
            f"- model answer: `{row['parsed_answer']}`",
            f"- label: `{row['error_type']}`",
            f"- answer_correct: `{row['answer_correct']}`",
            f"- hallucination: `{row['hallucination']}`",
            f"- matched context value: `{row.get('matched_context_value')}`",
            f"- matched distractor type: `{row.get('matched_distractor_type')}`",
            f"- rule: `{row.get('grading_rule_used')}`",
            f"- semantic review: `{row.get('needs_semantic_review')}`",
            "",
        ])
    (OUT_DIR / "grader_audit.md").write_text("\n".join(lines), encoding="utf-8")


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
            "rendered_input_tokens": failure.get("input_tokens") or inst.rendered_input_tokens_actual,
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


def write_manual_review(scored: list[dict[str, Any]], instances: dict[str, Instance]) -> None:
    ambiguous = [row for row in scored if row["error_type"] == "AMBIGUOUS_REVIEW_REQUIRED"]
    if not ambiguous:
        return
    with (OUT_DIR / "manual_review_cases.jsonl").open("w", encoding="utf-8") as handle:
        for row in ambiguous:
            inst = instances[row["instance_id"]]
            payload = {
                "instance_id": row["instance_id"],
                "question_family_id": row["question_family_id"],
                "context_length_label": row["context_length_label"],
                "domain": row["domain"],
                "question_type": row["question_type"],
                "answerable": row["answerable"],
                "question": row["question"],
                "gold_answer": row["gold_answer"],
                "model_answer": row["parsed_answer"],
                "target_evidence": inst.gold_evidence_canonical_ids,
                "equivalent_evidence": [g.model_dump(mode="json") for g in inst.gold_evidence_equivalence_groups],
                "matched_context_record": row.get("matched_context_record"),
                "review_reason": row.get("review_reason"),
            }
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    lines = ["# Experiment D Manual Review Cases", ""]
    for row in ambiguous:
        lines.extend([
            f"## {row['instance_id']}",
            "",
            f"- family: `{row['question_family_id']}`",
            f"- context/domain/type: `{row['context_length_label']}` / `{row['domain']}` / `{row['question_type']}`",
            f"- answerable: `{row['answerable']}`",
            f"- question: {row['question']}",
            f"- gold: `{row['gold_answer']}`",
            f"- model answer: `{row['parsed_answer']}`",
            f"- matched context value: `{row.get('matched_context_value')}`",
            f"- matched distractor type: `{row.get('matched_distractor_type')}`",
            f"- review reason: {row.get('review_reason')}",
            "",
        ])
    (OUT_DIR / "manual_review_cases.md").write_text("\n".join(lines), encoding="utf-8")


def write_outputs(
    scored: list[dict[str, Any]],
    runtime_failures: list[dict[str, Any]],
    audit: list[dict[str, Any]],
    *,
    grader_hash_before: str,
    grader_hash_after: str,
    script_hash: str,
    raw_hash_before: str,
    raw_hash_after: str,
    failure_hash_before: str,
    failure_hash_after: str,
    test_result: dict[str, Any],
) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in [
        "scored_results.jsonl",
        "scored_results.csv",
        "runtime_failures.jsonl",
        "grading_summary.json",
        "grading_summary.md",
        "grading_integrity_report.json",
        "grader_manifest.json",
        "grader_audit.md",
        "grader_audit.json",
        "error_counts_by_context.csv",
        "manual_review_cases.md",
        "manual_review_cases.jsonl",
    ]:
        path = OUT_DIR / name
        if path.exists():
            path.unlink()

    with (OUT_DIR / "scored_results.jsonl").open("w", encoding="utf-8") as handle:
        for row in scored:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    write_csv(OUT_DIR / "scored_results.csv", scored, CSV_FIELDS)
    write_runtime_failures(runtime_failures, {row["instance_id"]: Instance.model_validate(row) for row in iter_jsonl(DATASET_DIR / "instances.jsonl")})
    write_audit(audit)
    write_error_counts_by_context(scored)
    instances = {row["instance_id"]: Instance.model_validate(row) for row in iter_jsonl(DATASET_DIR / "instances.jsonl")}
    write_manual_review(scored, instances)

    summary = summary_payload(scored, runtime_failures)
    (OUT_DIR / "grading_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n")

    ids = [row["instance_id"] for row in scored]
    runtime_ids = [row["instance_id"] for row in runtime_failures]
    expected_ids = set(instances)
    errors = []
    if len(scored) != 2998:
        errors.append(f"expected 2998 scored rows, found {len(scored)}")
    if len(set(ids)) != 2998:
        errors.append("scored instance IDs are not 2998 unique IDs")
    if len(runtime_failures) != 2 or len(set(runtime_ids)) != 2:
        errors.append("runtime failures are not exactly two unique rows")
    if set(ids) & set(runtime_ids):
        errors.append("runtime failures appear in scored results")
    if set(ids) | set(runtime_ids) != expected_ids:
        errors.append("scored + runtime failure IDs do not cover the frozen dataset")
    expected_context_counts = {"4K": 500, "8K": 500, "16K": 500, "32K": 500, "64K": 500, "82K": 498}
    if Counter(row["context_length_label"] for row in scored) != expected_context_counts:
        errors.append("scored context counts mismatch")
    if raw_hash_before != raw_hash_after or failure_hash_before != failure_hash_after:
        errors.append("raw inference files changed during grading")
    if grader_hash_before != grader_hash_after:
        errors.append("grader hash changed during scoring")
    integrity = {
        "passed": not errors,
        "errors": errors,
        "expected_inference_attempts": 3000,
        "successful_outputs": 2998,
        "factual_graded_rows": len(scored),
        "runtime_failures": len(runtime_failures),
        "unique_scored_instance_ids": len(set(ids)),
        "unique_runtime_failure_ids": len(set(runtime_ids)),
        "context_counts": dict(Counter(row["context_length_label"] for row in scored)),
        "raw_results_hash_before": raw_hash_before,
        "raw_results_hash_after": raw_hash_after,
        "raw_failures_hash_before": failure_hash_before,
        "raw_failures_hash_after": failure_hash_after,
        "raw_outputs_unchanged": raw_hash_before == raw_hash_after and failure_hash_before == failure_hash_after,
        "grader_hash_before": grader_hash_before,
        "grader_hash_after": grader_hash_after,
        "grader_unchanged_during_scoring": grader_hash_before == grader_hash_after,
        "dataset_hash": dataset_hash(),
        "frozen_benchmark_unchanged": dataset_hash() == EXPECTED_DATASET_HASH,
        "no_llm_judge_used": True,
        "no_statistical_hypothesis_testing_performed": True,
    }
    (OUT_DIR / "grading_integrity_report.json").write_text(json.dumps(integrity, indent=2, ensure_ascii=False, sort_keys=True) + "\n")

    manifest = {
        "created_at": utc_now(),
        "dataset_dir": str(DATASET_DIR),
        "dataset_hash": EXPECTED_DATASET_HASH,
        "raw_results_path": str(RESULTS_PATH),
        "raw_results_sha256": raw_hash_before,
        "raw_failures_path": str(FAILURES_PATH),
        "raw_failures_sha256": failure_hash_before,
        "experiment_c_frozen_grader_hash": EXPERIMENT_C_GRADER_HASH,
        "experiment_d_grader_hash": grader_hash_before,
        "experiment_d_script_hash": script_hash,
        "semantic_grading_rules_changed_from_experiment_c": False,
        "semantic_rule_change_note": "No semantic grading logic changed; Experiment D uses grade_answer_only_response from the Experiment C frozen grader.",
        "test_result": test_result,
        "audit_result": audit_payload(audit),
        "python_version": sys.version,
        "platform": platform.platform(),
    }
    (OUT_DIR / "grader_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n")

    scored_hash = sha256_file(OUT_DIR / "scored_results.jsonl")
    manifest_hash = sha256_file(OUT_DIR / "grader_manifest.json")
    summary["scored_results_sha256"] = scored_hash
    summary["grader_manifest_sha256"] = manifest_hash
    (OUT_DIR / "grading_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n")

    lines = [
        "# Experiment D Full Deterministic Grading",
        "",
        f"- successful responses graded: `{summary['successful_responses_graded']}`",
        f"- runtime failures excluded from factual grading: `{summary['runtime_failures']}`",
        f"- correct: `{summary['correct']}`",
        f"- inaccurate: `{summary['inaccurate']}`",
        f"- hallucinatory inaccuracies: `{summary['hallucinatory_inaccuracy']}`",
        f"- grounded inaccuracies: `{summary['grounded_inaccuracy']}`",
        f"- ambiguous-review cases: `{summary['ambiguous_review']}`",
        f"- format failures: `{summary['format_failure']}`",
        f"- error type counts: `{summary['error_type_counts']}`",
        f"- Experiment D grader hash: `{grader_hash_before}`",
        f"- scored results hash: `{scored_hash}`",
        "",
        "Runtime failures are preserved separately and are not factual inaccuracies.",
        "No regression, p-value, confidence interval, odds ratio, or trend test was run.",
        "",
        "## Counts By Context",
        "",
        "| Context | Gradable N | Correct | Inaccurate | Hallucinatory | Grounded | Ambiguous | Runtime failures |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in EXPECTED_CONTEXTS:
        c = summary["counts_by_context"][label]
        lines.append(
            f"| {label} | {c['gradable_n']} | {c['correct']} | {c['inaccurate']} | "
            f"{c['hallucinatory_inaccuracy']} | {c['grounded_inaccuracy']} | {c['ambiguous']} | {c['runtime_failures']} |"
        )
    (OUT_DIR / "grading_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_tests() -> dict[str, Any]:
    cmd = ["conda", "run", "-n", "longctx-llama-infer", "pytest", "tests/test_grading.py"]
    proc = subprocess.run(cmd, cwd=Path.cwd(), capture_output=True, text=True, check=False)
    return {
        "command": " ".join(cmd),
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def main() -> int:
    started = utc_now()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    grader_hash_before = sha256_file(GRADER_PATH)
    script_hash = sha256_file(SCRIPT_PATH)
    raw_hash_before = sha256_file(RESULTS_PATH)
    failure_hash_before = sha256_file(FAILURES_PATH)
    if grader_hash_before != EXPERIMENT_C_GRADER_HASH:
        raise SystemExit(f"grader hash differs from Experiment C frozen hash: {grader_hash_before}")
    tests = run_tests()
    if not tests["passed"]:
        (OUT_DIR / "test_failure.json").write_text(json.dumps(tests, indent=2) + "\n")
        raise SystemExit("grading tests failed; stopping before audit/full grading")

    instances, families, results, failures = load_inputs()
    errors = verify_inputs(instances, results, failures)
    if errors:
        raise SystemExit("input verification failed: " + "; ".join(errors))

    audit_raw = stratified_audit_sample(results, instances)
    audit_scored = grade_rows(audit_raw, instances, families, grader_hash_before)
    write_audit(audit_scored)

    scored = grade_rows(results, instances, families, grader_hash_before)
    runtime_failures = [
        {
            "instance_id": failure["instance_id"],
            "question_family_id": failure["question_family_id"],
            "context_length_label": failure["context_length_label"],
            "domain": failure["domain"],
            "question_type": failure["question_type"],
            "answerable": failure["answerable"],
            "rendered_input_tokens": failure.get("input_tokens"),
            "failure_status": "RUNTIME_FAILURE",
            "failure_type": failure.get("status"),
            "error_type": failure.get("error_type"),
            "error_message": failure.get("error_message"),
        }
        for failure in failures
    ]
    grader_hash_after = sha256_file(GRADER_PATH)
    raw_hash_after = sha256_file(RESULTS_PATH)
    failure_hash_after = sha256_file(FAILURES_PATH)
    write_outputs(
        scored,
        runtime_failures,
        audit_scored,
        grader_hash_before=grader_hash_before,
        grader_hash_after=grader_hash_after,
        script_hash=script_hash,
        raw_hash_before=raw_hash_before,
        raw_hash_after=raw_hash_after,
        failure_hash_before=failure_hash_before,
        failure_hash_after=failure_hash_after,
        test_result=tests,
    )
    summary = json.loads((OUT_DIR / "grading_summary.json").read_text())
    integrity = json.loads((OUT_DIR / "grading_integrity_report.json").read_text())
    print(json.dumps({
        "started_at": started,
        "completed_at": utc_now(),
        "tests_passed": tests["passed"],
        "grader_hash": grader_hash_before,
        "scored_results_hash": summary["scored_results_sha256"],
        "successful_responses_graded": summary["successful_responses_graded"],
        "runtime_failures": summary["runtime_failures"],
        "correct": summary["correct"],
        "inaccurate": summary["inaccurate"],
        "hallucinatory_inaccuracy": summary["hallucinatory_inaccuracy"],
        "grounded_inaccuracy": summary["grounded_inaccuracy"],
        "ambiguous_review": summary["ambiguous_review"],
        "format_failure": summary["format_failure"],
        "error_type_counts": summary["error_type_counts"],
        "integrity_passed": integrity["passed"],
        "output_dir": str(OUT_DIR),
    }, indent=2, sort_keys=True))
    return 0 if integrity["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
