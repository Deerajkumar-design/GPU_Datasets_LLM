#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import binomtest

from common import GRADER_HASH, hash_tree, paths, repo_root, verify_frozen, write_manifest
from longctx_dataset.grading import grade_answer_only_response
from longctx_dataset.schemas import Instance, QuestionFamily

CONTEXTS = ["4K", "8K", "16K", "32K", "64K", "82K"]


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def grade_model(raw_path: Path, out_dir: Path, historical_scored_path: Path) -> list[dict]:
    root = repo_root()
    data = root / "data" / "preproduction_llama32_3b_500f_6ctx_v1"
    instances = {row["instance_id"]: Instance.model_validate(row) for row in read_jsonl(data / "instances.jsonl")}
    families = {row["question_family_id"]: QuestionFamily.model_validate(row) for row in read_jsonl(data / "question_families.jsonl")}
    raw = read_jsonl(raw_path)
    historical = {
        row["instance_id"]: row
        for row in read_jsonl(historical_scored_path)
    }
    scored = []
    for result in raw:
        inst = instances[result["instance_id"]]
        row = grade_answer_only_response(inst, result, family=families[inst.question_family_id])
        prior = historical.get(result["instance_id"])
        same_adjudicated_response = (
            prior
            and prior.get("parsed_answer") == row.get("parsed_answer")
            and prior.get("needs_semantic_review") is False
            and row.get("needs_semantic_review") is True
        )
        if same_adjudicated_response:
            for key in ("answer_correct", "hallucination", "error_type", "needs_semantic_review"):
                row[key] = prior.get(key)
            row["frozen_historical_resolution_applied"] = True
        else:
            row["frozen_historical_resolution_applied"] = False
        row["factual_outcome"] = "ACCURATE" if row.get("error_type") == "CORRECT" else "INACCURATE"
        row["grader_hash"] = GRADER_HASH
        scored.append(row)
    write_jsonl(out_dir / "scored_results.jsonl", scored)
    pd.DataFrame(scored).to_csv(out_dir / "scored_results.csv", index=False)
    return scored


def gee(rows: list[dict]) -> dict:
    frame = pd.DataFrame(rows)
    frame["inaccurate"] = (frame["factual_outcome"] != "ACCURATE").astype(int)
    frame["context_log2"] = np.log2(frame["input_tokens"].astype(float))
    fit = sm.GEE.from_formula(
        "inaccurate ~ context_log2",
        groups="question_family_id",
        data=frame,
        family=sm.families.Binomial(),
    ).fit()
    beta = float(fit.params["context_log2"])
    se = float(fit.bse["context_log2"])
    return {
        "n": len(frame),
        "coefficient": beta,
        "se": se,
        "odds_ratio": math.exp(beta),
        "ci95_low": math.exp(beta - 1.96 * se),
        "ci95_high": math.exp(beta + 1.96 * se),
        "p_value": float(fit.pvalues["context_log2"]),
    }


def rates(rows: list[dict]) -> list[dict]:
    frame = pd.DataFrame(rows)
    output = []
    for context in CONTEXTS:
        part = frame[frame.context_length_label == context]
        accurate = int((part.factual_outcome == "ACCURATE").sum())
        output.append({
            "context": context,
            "successful": len(part),
            "accurate": accurate,
            "inaccurate": len(part) - accurate,
            "accurate_rate": accurate / len(part) if len(part) else None,
        })
    return output


def paired_tests(rows: list[dict]) -> list[dict]:
    frame = pd.DataFrame(rows)
    frame["accurate"] = frame.factual_outcome == "ACCURATE"
    pivot = frame.pivot(index="question_family_id", columns="context_length_label", values="accurate")
    output = []
    for context in CONTEXTS[1:]:
        pair = pivot[["4K", context]].dropna()
        accurate_to_inaccurate = int((pair["4K"] & ~pair[context]).sum())
        inaccurate_to_accurate = int((~pair["4K"] & pair[context]).sum())
        discordant = accurate_to_inaccurate + inaccurate_to_accurate
        p = binomtest(accurate_to_inaccurate, discordant, 0.5).pvalue if discordant else 1.0
        output.append({
            "comparison": f"4K vs {context}",
            "complete_pairs": len(pair),
            "accurate_to_inaccurate": accurate_to_inaccurate,
            "inaccurate_to_accurate": inaccurate_to_accurate,
            "mcnemar_exact_p": p,
        })
    ordered = sorted(range(len(output)), key=lambda index: output[index]["mcnemar_exact_p"])
    adjusted = [1.0] * len(output)
    running = 0.0
    for rank, index in enumerate(ordered):
        running = max(running, min(1.0, output[index]["mcnemar_exact_p"] * (len(output) - rank)))
        adjusted[index] = running
    for row, value in zip(output, adjusted):
        row["holm_p"] = value
    return output


def compare_hardware(new_raw: list[dict], new_scored: list[dict], old_raw_path: Path, old_scored_path: Path) -> dict:
    old_raw = {row["instance_id"]: row for row in read_jsonl(old_raw_path)}
    old_scored = {row["instance_id"]: row for row in read_jsonl(old_scored_path)}
    new_raw_by_id = {row["instance_id"]: row for row in new_raw}
    new_scored_by_id = {row["instance_id"]: row for row in new_scored}
    common = sorted(set(old_raw) & set(new_raw_by_id) & set(old_scored) & set(new_scored_by_id))
    details = []
    for instance_id in common:
        old_label = "ACCURATE" if old_scored[instance_id].get("error_type") == "CORRECT" else "INACCURATE"
        new_label = new_scored_by_id[instance_id]["factual_outcome"]
        details.append({
            "instance_id": instance_id,
            "context": new_raw_by_id[instance_id]["context_length_label"],
            "exact_text": old_raw[instance_id].get("raw_output_text") == new_raw_by_id[instance_id].get("raw_output_text"),
            "parsed_answer": old_raw[instance_id].get("parsed_answer") == new_raw_by_id[instance_id].get("parsed_answer"),
            "label_agreement": old_label == new_label,
            "old_label": old_label,
            "new_label": new_label,
        })
    return {
        "common_successes": len(details),
        "exact_answer_text_match_rate": sum(row["exact_text"] for row in details) / len(details),
        "parsed_answer_match_rate": sum(row["parsed_answer"] for row in details) / len(details),
        "label_agreement_rate": sum(row["label_agreement"] for row in details) / len(details),
        "outcome_flips": sum(not row["label_agreement"] for row in details),
        "accurate_to_inaccurate": sum(row["old_label"] == "ACCURATE" and row["new_label"] == "INACCURATE" for row in details),
        "inaccurate_to_accurate": sum(row["old_label"] == "INACCURATE" and row["new_label"] == "ACCURATE" for row in details),
        "agreement_by_context": {
            context: {
                "n": sum(row["context"] == context for row in details),
                "agreement_rate": (
                    sum(row["context"] == context and row["label_agreement"] for row in details)
                    / sum(row["context"] == context for row in details)
                ),
            }
            for context in CONTEXTS
        },
    }


def main() -> int:
    verify_frozen()
    result_root = paths()["results"]
    analysis_dir = result_root / "analysis_b200_replication_v1"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    specifications = {
        "llama": (
            result_root / "inference_b200_llama32_3b_500f_6ctx_v1",
            repo_root() / "data" / "inference_llama32_3b_500f_6ctx_v1" / "results.jsonl",
            repo_root() / "data" / "grading_experiment_d_final_v1" / "final_scored_results.jsonl",
        ),
        "qwen": (
            result_root / "inference_b200_qwen35_2b_500f_6ctx_v1",
            repo_root() / "data" / "inference_qwen35_2b_500f_6ctx_v1" / "results.jsonl",
            repo_root() / "data" / "grading_experiment_e_qwen35_2b_v1" / "scored_results.jsonl",
        ),
    }
    report = {}
    for model, (raw_dir, old_raw, old_scored) in specifications.items():
        raw = read_jsonl(raw_dir / "results.jsonl")
        grading_dir = result_root / f"grading_b200_{model}_v1"
        scored = grade_model(raw_dir / "results.jsonl", grading_dir, old_scored)
        model_report = {
            "rates": rates(scored),
            "gee": gee(scored),
            "mcnemar": paired_tests(scored),
            "hardware_comparison": compare_hardware(raw, scored, old_raw, old_scored),
        }
        (analysis_dir / f"{model}_analysis.json").write_text(json.dumps(model_report, indent=2) + "\n")
        report[model] = model_report
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(7, 4))
    for model, model_report in report.items():
        axis.plot(
            CONTEXTS,
            [row["accurate_rate"] for row in model_report["rates"]],
            marker="o",
            label=model,
        )
    axis.set(xlabel="Context condition", ylabel="Accurate rate", ylim=(0, 1))
    axis.legend()
    figure.tight_layout()
    figure.savefig(analysis_dir / "b200_accuracy_by_context.png", dpi=160)
    plt.close(figure)
    (analysis_dir / "b200_replication_report.json").write_text(json.dumps(report, indent=2) + "\n")
    write_manifest("b200_analysis_hashes.json", {"sha256": hash_tree(result_root)})
    print(json.dumps(report, indent=2))
    print(f"CPU ANALYSIS COMPLETE: {analysis_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
