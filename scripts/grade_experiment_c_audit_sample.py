from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from longctx_dataset.grading import grade_answer_only_response, parse_context_records
from longctx_dataset.schemas import Instance, QuestionFamily
from longctx_dataset.storage.io import iter_jsonl


RESULTS_PATH = Path("data/inference_llama32_3b_4k64k_v3/results.jsonl")
DATASET_DIR = Path("data/preproduction_llama32_3b_v2")
OUT_DIR = Path("data/grading_experiment_c_audit_v1")
TARGET_SIZE = 40


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


def select_audit_rows(results: list[dict[str, Any]], instances: dict[str, Instance]) -> list[dict[str, Any]]:
    rows_by_id = {row["instance_id"]: row for row in results}
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_instance_id(instance_id: str) -> None:
        row = rows_by_id.get(instance_id)
        if row is not None:
            add(row)

    def add(row: dict[str, Any]) -> None:
        if row["instance_id"] not in seen and len(selected) < TARGET_SIZE:
            selected.append(row)
            seen.add(row["instance_id"])

    # Include known manual-audit and edge-case families across multiple lengths.
    for instance_id in [
        "CT_0024_4K",
        "CT_0024_64K",
        "CT_0021_8K",
        "CT_0021_64K",
        "CT_0007_4K",
        "CT_0007_64K",
        "SEC_0006_4K",
        "SEC_0006_64K",
        "FDA_0003_4K",
        "FDA_0003_64K",
        "FRED_0007_4K",
        "FRED_0007_64K",
        "SEC_0009_32K",
        "SEC_0009_64K",
        "CT_0010_16K",
        "FDA_0010_32K",
        "FRED_0010_64K",
        "FRED_0013_4K",
        "CT_0013_32K",
    ]:
        add_instance_id(instance_id)

    for label in ["4K", "8K", "16K", "32K", "64K"]:
        for row in results:
            if row["context_length_label"] == label:
                add(row)
                break

    for domain in ["SEC", "FDA", "CLINICAL_TRIALS", "FRED"]:
        for row in results:
            if row["domain"] == domain:
                add(row)
                break

    for qtype in ["DIRECT_RETRIEVAL", "RETRIEVAL_CALCULATION", "TEMPORAL_VERSION", "ENTITY_UNIT_BINDING", "UNANSWERABLE"]:
        for row in results:
            if row["question_type"] == qtype:
                add(row)
                break

    for answerable in (True, False):
        for row in results:
            if instances[row["instance_id"]].answerable is answerable:
                add(row)
                break

    # Prefer a deterministic mix of abstentions, long contexts, and short contexts for fill.
    ranked = sorted(
        results,
        key=lambda r: (
            "INSUFFICIENT_EVIDENCE" not in (r.get("raw_output_text") or ""),
            r["context_length_label"] not in {"64K", "32K"},
            r["domain"],
            r["question_type"],
            r["instance_id"],
        ),
    )
    for row in ranked:
        add(row)
        if len(selected) >= TARGET_SIZE:
            break
    return selected


def compact_context_metadata(inst: Instance, matched: dict[str, Any] | None) -> dict[str, Any]:
    records = parse_context_records(inst.context)
    ids = set(inst.gold_evidence_display_ids)
    if matched and matched.get("display_id"):
        ids.add(matched["display_id"])
    snippets = {}
    for display_id in sorted(ids):
        rec = records.get(display_id)
        if rec:
            snippets[display_id] = {
                "canonical_record_id": inst.display_id_to_record_id.get(display_id),
                "field": rec.get("field"),
                "period": rec.get("period"),
                "unit": rec.get("unit"),
                "value": rec.get("value"),
                "distractor_type": next(
                    (d.distractor_type.value for d in inst.distractors if d.display_id == display_id),
                    None,
                ),
            }
    return snippets


def write_outputs(scored: list[dict[str, Any]], instances: dict[str, Instance]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in ["audit_scored_results.jsonl", "audit_table.csv", "audit_report.md"]:
        path = OUT_DIR / name
        if path.exists():
            path.unlink()

    for row in scored:
        append_jsonl(OUT_DIR / "audit_scored_results.jsonl", row)

    fields = [
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
        "generation_latency_seconds",
        "generated_tokens_count",
    ]
    with (OUT_DIR / "audit_table.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in scored:
            writer.writerow({k: row.get(k) for k in fields})

    counts = Counter(row["error_type"] for row in scored)
    lines = [
        "# Experiment C Deterministic Grading Audit",
        "",
        f"- sample size: `{len(scored)}`",
        f"- deterministically resolved: `{sum(not row['needs_semantic_review'] for row in scored)}`",
        f"- semantic review required: `{sum(row['needs_semantic_review'] for row in scored)}`",
        f"- hallucination=true: `{sum(row['hallucination'] is True for row in scored)}`",
        f"- error types: `{dict(counts)}`",
        "",
        "No evidence-selection accuracy is graded for Experiment C because the model-facing output contract is answer-only.",
        "",
    ]
    for idx, row in enumerate(scored, 1):
        inst = instances[row["instance_id"]]
        snippets = compact_context_metadata(inst, row.get("matched_context_record"))
        lines += [
            f"## {idx}. {row['instance_id']}",
            "",
            f"- context length: `{row['context_length_label']}`",
            f"- domain: `{row['domain']}`",
            f"- question type: `{row['question_type']}`",
            f"- answerable: `{row['answerable']}`",
            f"- question: {row['question']}",
            f"- gold answer: `{row['gold_answer_normalized']}`",
            f"- model answer: `{row['parsed_answer']}`",
            f"- answer correct: `{row['answer_correct']}`",
            f"- abstention correct: `{row['abstention_correct']}`",
            f"- hallucination: `{row['hallucination']}`",
            f"- error type: `{row['error_type']}`",
            f"- matched context/distractor value: `{row.get('matched_context_value')}`",
            f"- matched distractor type: `{row.get('matched_distractor_type')}`",
            f"- rule: `{row['grading_rule_used']}`",
            f"- semantic review required: `{row['needs_semantic_review']}`",
            f"- review reason: {row.get('review_reason') or ''}",
            f"- compact context metadata: `{json.dumps(snippets, ensure_ascii=False)}`",
            "",
        ]
    (OUT_DIR / "audit_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    instances, families, results = load_inputs()
    selected = select_audit_rows(results, instances)
    scored = [
        grade_answer_only_response(
            instances[row["instance_id"]],
            row,
            family=families[instances[row["instance_id"]].question_family_id],
        )
        for row in selected
    ]
    write_outputs(scored, instances)
    summary = {
        "sample_size": len(scored),
        "deterministically_resolved": sum(not row["needs_semantic_review"] for row in scored),
        "semantic_review_required": sum(row["needs_semantic_review"] for row in scored),
        "hallucination_true": sum(row["hallucination"] is True for row in scored),
        "error_type_counts": dict(Counter(row["error_type"] for row in scored)),
        "output_dir": str(OUT_DIR),
    }
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
