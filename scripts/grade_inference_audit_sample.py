from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from longctx_dataset.grading import grade_response, parse_context_records
from longctx_dataset.pipeline import instances_path
from longctx_dataset.schemas import Instance
from longctx_dataset.storage.io import iter_jsonl
from longctx_dataset.config import load_config


RESULTS_PATH = Path("data/inference_llama32_3b_4k64k_v1/results.jsonl")
OUT_DIR = Path("data/grading_audit_v2")
CONFIG_PATH = "config/preproduction_llama32_3b_v2.yaml"
TARGET_SIZE = 36


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def load_inputs() -> tuple[dict[str, Instance], list[dict[str, Any]]]:
    cfg = load_config(CONFIG_PATH)
    instances = {
        row["instance_id"]: Instance.model_validate(row)
        for row in iter_jsonl(instances_path(cfg))
    }
    results = list(iter_jsonl(RESULTS_PATH))
    return instances, results


def select_audit_rows(results: list[dict[str, Any]], instances: dict[str, Instance]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(row: dict[str, Any]) -> None:
        if row["instance_id"] not in seen and len(selected) < TARGET_SIZE:
            selected.append(row)
            seen.add(row["instance_id"])

    # Guarantee coverage of malformed and parseable outputs.
    for want_valid in (False, True):
        for row in results:
            if bool(row.get("json_parse_success")) == want_valid:
                add(row)
                break

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

    # Add same-family ladders for manual length comparison where useful.
    for family in ["SEC_0006", "CT_0007", "FDA_0003", "FRED_0007"]:
        fam_rows = [r for r in results if r["question_family_id"] == family]
        for label in ["4K", "32K", "64K"]:
            for row in fam_rows:
                if row["context_length_label"] == label:
                    add(row)
                    break

    # Fill deterministically with a mix of parseable/malformed and long/short outputs.
    ranked = sorted(
        results,
        key=lambda r: (
            bool(r.get("json_parse_success")),
            r["context_length_label"],
            -(r.get("generated_tokens_count") or 0),
            r["instance_id"],
        ),
    )
    for row in ranked:
        add(row)
        if len(selected) >= TARGET_SIZE:
            break
    return selected


def compact_context_metadata(inst: Instance, selected_ids: list[str], matched: dict[str, Any] | None) -> dict[str, Any]:
    records = parse_context_records(inst.context)
    ids = set(selected_ids or [])
    if matched and matched.get("display_id"):
        ids.add(matched["display_id"])
    for display_id in inst.gold_evidence_display_ids:
        ids.add(display_id)
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
            }
    return snippets


def write_outputs(scored: list[dict[str, Any]], instances: dict[str, Instance]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in ["audit_scored_results.jsonl", "audit_table.csv", "audit_report.md", "format_failure_diagnostics.json"]:
        path = OUT_DIR / old
        if path.exists():
            path.unlink()
    for row in scored:
        append_jsonl(OUT_DIR / "audit_scored_results.jsonl", row)

    fields = [
        "instance_id",
        "domain",
        "question_type",
        "context_length_label",
        "answerable",
        "json_valid",
        "strict_json_valid",
        "recovery_attempted",
        "recovery_success",
        "recovery_method",
        "malformed_output_pattern",
        "output_truncated",
        "degenerate_output",
        "parse_confidence",
        "answer_correct",
        "evidence_correct",
        "abstention_correct",
        "hallucination",
        "error_type",
        "needs_semantic_review",
        "review_reason",
        "normalized_gold_answer",
        "normalized_model_answer",
        "grading_rule_used",
    ]
    with (OUT_DIR / "audit_table.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for row in scored:
            writer.writerow({k: row.get(k) for k in fields})

    lines = ["# Deterministic Grading Audit Sample", ""]
    counts = Counter(row["error_type"] for row in scored)
    original_format_failures = sum(not row["strict_json_valid"] for row in scored)
    safely_recovered = sum(row["recovery_success"] for row in scored)
    unresolved_format = sum((not row["strict_json_valid"]) and (not row["recovery_success"]) for row in scored)
    lines += [
        f"- sample size: `{len(scored)}`",
        f"- original format failures: `{original_format_failures}`",
        f"- safely recovered: `{safely_recovered}`",
        f"- unresolved malformed outputs: `{unresolved_format}`",
        f"- hit max_new_tokens=512: `{sum(row['output_truncated'] for row in scored if not row['strict_json_valid'])}`",
        f"- deterministically resolved: `{sum(not r['needs_semantic_review'] for r in scored)}`",
        f"- semantic review required: `{sum(r['needs_semantic_review'] for r in scored)}`",
        f"- remaining format failures: `{sum(not r['json_valid'] for r in scored)}`",
        f"- malformed patterns: `{dict(Counter(row['malformed_output_pattern'] for row in scored if not row['strict_json_valid']))}`",
        f"- error types: `{dict(counts)}`",
        "",
    ]
    for idx, row in enumerate(scored, 1):
        inst = instances[row["instance_id"]]
        selected = row.get("parsed_selected_evidence") or []
        snippets = compact_context_metadata(inst, selected, row.get("matched_context_record"))
        lines += [
            f"## {idx}. {row['instance_id']}",
            "",
            f"- question: {inst.question}",
            f"- gold answer: `{inst.gold_answer_normalized}`",
            f"- model answer: `{row.get('parsed_answer')}`",
            f"- gold evidence display IDs: `{inst.gold_evidence_display_ids}`",
            f"- selected evidence: `{selected}`",
            f"- answer correct: `{row['answer_correct']}`",
            f"- evidence correct: `{row['evidence_correct']}`",
            f"- abstention correct: `{row['abstention_correct']}`",
            f"- hallucination: `{row['hallucination']}`",
            f"- error type: `{row['error_type']}`",
            f"- rule: `{row['grading_rule_used']}`",
            f"- strict JSON valid: `{row['strict_json_valid']}`",
            f"- recovery attempted: `{row['recovery_attempted']}`",
            f"- recovery success: `{row['recovery_success']}`",
            f"- recovery method: `{row['recovery_method']}`",
            f"- malformed pattern: `{row['malformed_output_pattern']}`",
            f"- output truncated: `{row['output_truncated']}`",
            f"- degenerate output: `{row['degenerate_output']}`",
            f"- parse confidence: `{row['parse_confidence']}`",
            f"- semantic review required: `{row['needs_semantic_review']}`",
            f"- review reason: {row.get('review_reason') or ''}",
            f"- compact context metadata: `{json.dumps(snippets, ensure_ascii=False)}`",
            "",
        ]
    (OUT_DIR / "audit_report.md").write_text("\n".join(lines), encoding="utf-8")

    diagnostics = {
        "sample_size": len(scored),
        "original_format_failures": original_format_failures,
        "safely_recovered": safely_recovered,
        "unresolved_malformed_outputs": unresolved_format,
        "hit_max_new_tokens_512": sum(row["output_truncated"] for row in scored if not row["strict_json_valid"]),
        "counts_by_malformed_output_pattern": dict(
            Counter(row["malformed_output_pattern"] for row in scored if not row["strict_json_valid"])
        ),
        "recovery_methods": dict(Counter(row["recovery_method"] for row in scored if row["recovery_success"])),
        "cases": [
            {
                "instance_id": row["instance_id"],
                "generated_tokens_count": row.get("generated_tokens_count"),
                "strict_json_valid": row["strict_json_valid"],
                "recovery_attempted": row["recovery_attempted"],
                "recovery_success": row["recovery_success"],
                "recovery_method": row["recovery_method"],
                "malformed_output_pattern": row["malformed_output_pattern"],
                "output_truncated": row["output_truncated"],
                "degenerate_output": row["degenerate_output"],
                "parse_confidence": row["parse_confidence"],
                "parse_failure_reason": row["parse_failure_reason"],
                "review_reason": row["review_reason"],
            }
            for row in scored
            if not row["strict_json_valid"]
        ],
    }
    (OUT_DIR / "format_failure_diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    instances, results = load_inputs()
    selected = select_audit_rows(results, instances)
    scored = [grade_response(instances[row["instance_id"]], row) for row in selected]
    write_outputs(scored, instances)
    summary = {
        "sample_size": len(scored),
        "deterministically_resolved": sum(not row["needs_semantic_review"] for row in scored),
        "semantic_review_required": sum(row["needs_semantic_review"] for row in scored),
        "original_format_failures": sum(not row["strict_json_valid"] for row in scored),
        "safely_recovered": sum(row["recovery_success"] for row in scored),
        "remaining_format_failures": sum(not row["json_valid"] for row in scored),
        "hit_max_new_tokens_512": sum(row["output_truncated"] for row in scored if not row["strict_json_valid"]),
        "malformed_patterns": dict(Counter(row["malformed_output_pattern"] for row in scored if not row["strict_json_valid"])),
        "error_type_counts": dict(Counter(row["error_type"] for row in scored)),
    }
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
