from __future__ import annotations

import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from longctx_dataset.grading import parse_model_json


RESULTS_PATH = Path("data/inference_llama32_3b_4k64k_v1/results.jsonl")
OUT_DIR = Path("data/output_structure_analysis_v1")
CONTEXT_LABELS = ["4K", "8K", "16K", "32K", "64K"]


def pct(n: int, d: int) -> float:
    return (100.0 * n / d) if d else 0.0


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def classify_rows() -> list[dict[str, Any]]:
    rows = []
    for raw in (json.loads(line) for line in RESULTS_PATH.read_text(encoding="utf-8").splitlines()):
        parsed = parse_model_json(
            raw.get("raw_output_text"),
            generated_tokens_count=raw.get("generated_tokens_count"),
        )
        usable = bool(parsed["json_valid"])
        row = {
            "instance_id": raw["instance_id"],
            "question_family_id": raw["question_family_id"],
            "context_length_label": raw["context_length_label"],
            "domain": raw["domain"],
            "question_type": raw["question_type"],
            "answerable": raw["answerable"],
            "generated_tokens_count": raw.get("generated_tokens_count"),
            "hit_max_new_tokens_512": raw.get("generated_tokens_count") == 512,
            "strict_json_valid": parsed["strict_json_valid"],
            "recovery_success": parsed["recovery_success"],
            "usable_structured_output": usable,
            "format_failure": not usable,
            "output_truncated": parsed["output_truncated"],
            "degenerate_output": parsed["degenerate_output"],
            "malformed_output_pattern": parsed["malformed_output_pattern"],
            "recovery_method": parsed["recovery_method"],
            "parse_confidence": parsed["parse_confidence"],
            "parse_failure_reason": parsed["parse_failure_reason"],
            "raw_output_chars": len(raw.get("raw_output_text") or ""),
        }
        rows.append(row)
    return rows


def summarize_group(rows: list[dict[str, Any]], group_name: str, group_value: str) -> dict[str, Any]:
    total = len(rows)
    gen = [r["generated_tokens_count"] for r in rows if r["generated_tokens_count"] is not None]
    strict = sum(r["strict_json_valid"] for r in rows)
    recovered = sum(r["recovery_success"] for r in rows)
    usable = sum(r["usable_structured_output"] for r in rows)
    failures = sum(r["format_failure"] for r in rows)
    hit512 = sum(r["hit_max_new_tokens_512"] for r in rows)
    degenerate = sum(r["degenerate_output"] for r in rows)
    return {
        group_name: group_value,
        "total_responses": total,
        "valid_json": strict,
        "valid_json_pct": pct(strict, total),
        "recoverable_malformed_json": recovered,
        "recoverable_malformed_json_pct": pct(recovered, total),
        "usable_responses": usable,
        "usable_responses_pct": pct(usable, total),
        "format_failures": failures,
        "format_failure_pct": pct(failures, total),
        "hit_512_token_limit": hit512,
        "hit_512_token_limit_pct": pct(hit512, total),
        "repetitive_degenerate_outputs": degenerate,
        "repetitive_degenerate_outputs_pct": pct(degenerate, total),
        "mean_generated_tokens": statistics.mean(gen) if gen else None,
        "median_generated_tokens": statistics.median(gen) if gen else None,
    }


def grouped_summary(rows: list[dict[str, Any]], key: str, preferred_order: list[str] | None = None) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row[key])].append(row)
    order = preferred_order or sorted(groups)
    return [summarize_group(groups[value], key, value) for value in order if value in groups]


def family_transitions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_family: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        by_family[row["question_family_id"]][row["context_length_label"]] = row
    out = []
    for family_id in sorted(by_family):
        ladder = by_family[family_id]
        failures = [label for label in CONTEXT_LABELS if ladder[label]["format_failure"]]
        successes = [label for label in CONTEXT_LABELS if ladder[label]["usable_structured_output"]]
        first_failure = failures[0] if failures else None
        fail_every = len(failures) == len(CONTEXT_LABELS)
        success_every = len(successes) == len(CONTEXT_LABELS)
        short_success_long_fail = bool(
            ladder["4K"]["usable_structured_output"]
            and any(ladder[label]["format_failure"] for label in ["8K", "16K", "32K", "64K"])
        )
        out.append(
            {
                "question_family_id": family_id,
                "domain": ladder[CONTEXT_LABELS[0]]["domain"],
                "question_type": ladder[CONTEXT_LABELS[0]]["question_type"],
                "answerable": ladder[CONTEXT_LABELS[0]]["answerable"],
                "success_every_length": success_every,
                "fail_every_length": fail_every,
                "short_success_long_failure": short_success_long_fail,
                "first_format_failure_context": first_failure,
                "format_failure_contexts": ";".join(failures),
                "usable_contexts": ";".join(successes),
            }
        )
    return out


def report_md(
    rows: list[dict[str, Any]],
    by_context: list[dict[str, Any]],
    by_domain: list[dict[str, Any]],
    by_qtype: list[dict[str, Any]],
    by_answerable: list[dict[str, Any]],
    families: list[dict[str, Any]],
) -> str:
    total = len(rows)
    usable = sum(r["usable_structured_output"] for r in rows)
    failures = sum(r["format_failure"] for r in rows)
    hit512 = sum(r["hit_max_new_tokens_512"] for r in rows)
    deg = sum(r["malformed_output_pattern"] == "repetitive_truncated_selected_evidence" for r in rows)
    transition = sum(r["short_success_long_failure"] for r in families)
    fail_every = sum(r["fail_every_length"] for r in families)
    success_every = sum(r["success_every_length"] for r in families)
    lines = [
        "# Output Structure Analysis",
        "",
        "This diagnostic analyzes raw response structure only. It does not grade answer correctness, evidence correctness, hallucination, or accuracy.",
        "",
        f"- total responses: `{total}`",
        f"- fully usable structured outputs: `{usable}` ({pct(usable, total):.1f}%)",
        f"- format failures: `{failures}` ({pct(failures, total):.1f}%)",
        f"- hit 512 generated tokens: `{hit512}` ({pct(hit512, total):.1f}%)",
        f"- repetitive truncated selected-evidence degeneration: `{deg}` ({pct(deg, total):.1f}%)",
        f"- families successful at every length: `{success_every}`",
        f"- families failed at every length: `{fail_every}`",
        f"- families succeeding at 4K but failing later: `{transition}`",
        "",
        "## By Context Length",
        "",
        "| context | total | usable | format failures | failure % | hit 512 | degenerate | mean gen toks | median gen toks |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in by_context:
        lines.append(
            f"| {r['context_length_label']} | {r['total_responses']} | {r['usable_responses']} | "
            f"{r['format_failures']} | {r['format_failure_pct']:.1f}% | {r['hit_512_token_limit']} | "
            f"{r['repetitive_degenerate_outputs']} | {r['mean_generated_tokens']:.1f} | {r['median_generated_tokens']:.1f} |"
        )
    lines += ["", "## By Domain", ""]
    lines += _mini_table(by_domain, "domain")
    lines += ["", "## By Question Type", ""]
    lines += _mini_table(by_qtype, "question_type")
    lines += ["", "## By Answerability", ""]
    lines += _mini_table(by_answerable, "answerable")
    lines += [
        "",
        "## Interpretation",
        "",
        "The failure mode is both context-independent and context-dependent. There are failures even at 4K, so the JSON schema/output behavior itself is a problem. The failure rate also rises sharply with longer contexts, especially from 16K onward, indicating context length amplifies the degeneration.",
        "",
        "No final hallucination-rate or correctness analysis was performed.",
    ]
    return "\n".join(lines) + "\n"


def _mini_table(rows: list[dict[str, Any]], key: str) -> list[str]:
    lines = [
        f"| {key} | total | usable | format failures | failure % | hit 512 | degenerate |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"| {r[key]} | {r['total_responses']} | {r['usable_responses']} | {r['format_failures']} | "
            f"{r['format_failure_pct']:.1f}% | {r['hit_512_token_limit']} | {r['repetitive_degenerate_outputs']} |"
        )
    return lines


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = classify_rows()
    by_context = grouped_summary(rows, "context_length_label", CONTEXT_LABELS)
    by_domain = grouped_summary(rows, "domain", ["SEC", "FDA", "CLINICAL_TRIALS", "FRED"])
    by_qtype = grouped_summary(
        rows,
        "question_type",
        ["DIRECT_RETRIEVAL", "RETRIEVAL_CALCULATION", "TEMPORAL_VERSION", "ENTITY_UNIT_BINDING", "UNANSWERABLE"],
    )
    by_answerable = grouped_summary(rows, "answerable", ["True", "False"])
    families = family_transitions(rows)

    write_jsonl(OUT_DIR / "per_instance_structure.jsonl", rows)
    write_csv(OUT_DIR / "per_instance_structure.csv", rows)
    write_csv(OUT_DIR / "summary_by_context.csv", by_context)
    write_csv(OUT_DIR / "summary_by_domain.csv", by_domain)
    write_csv(OUT_DIR / "summary_by_question_type.csv", by_qtype)
    write_csv(OUT_DIR / "summary_by_answerability.csv", by_answerable)
    write_csv(OUT_DIR / "family_transition_analysis.csv", families)

    summary = {
        "total_responses": len(rows),
        "fully_usable": sum(r["usable_structured_output"] for r in rows),
        "format_failures": sum(r["format_failure"] for r in rows),
        "hit_512_generated_tokens": sum(r["hit_max_new_tokens_512"] for r in rows),
        "repetitive_truncated_selected_evidence": sum(
            r["malformed_output_pattern"] == "repetitive_truncated_selected_evidence" for r in rows
        ),
        "by_context": by_context,
        "by_domain": by_domain,
        "by_question_type": by_qtype,
        "by_answerable": by_answerable,
        "family_transition_counts": {
            "success_every_length": sum(r["success_every_length"] for r in families),
            "fail_every_length": sum(r["fail_every_length"] for r in families),
            "short_success_long_failure": sum(r["short_success_long_failure"] for r in families),
        },
        "malformed_patterns": dict(Counter(r["malformed_output_pattern"] for r in rows if r["format_failure"])),
        "no_correctness_or_hallucination_grading_performed": True,
    }
    (OUT_DIR / "structure_analysis.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUT_DIR / "structure_analysis_report.md").write_text(
        report_md(rows, by_context, by_domain, by_qtype, by_answerable, families),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
