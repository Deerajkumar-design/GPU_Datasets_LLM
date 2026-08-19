#!/usr/bin/env python3
"""Generate the polished Experiment D final report from frozen artifacts."""

from __future__ import annotations

import csv
import hashlib
import html
import json
import os
import platform
import shutil
import subprocess
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
from PIL import Image


OUT = Path("data/final_report_experiment_d_v1")
TABLES = OUT / "tables"
FIGS = OUT / "figures"
ANALYSIS = Path("data/analysis_experiment_d_final_v1")
SOURCE_FIGS = ANALYSIS / "figures"
FINAL_CSV = Path("data/grading_experiment_d_final_v1/final_scored_results.csv")
FINAL_JSONL = Path("data/grading_experiment_d_final_v1/final_scored_results.jsonl")
EXPECTED_JSONL_HASH = "8fa4fd3b990adf54b6f7790ed6defa9c5d89aa6dd8365e0a7519beeb44d985e8"
EXPECTED_CSV_HASH = "155f80ec3bf284a7928ede0d24b491a972540b77dfe01d98eb622825c9c06a78"
BENCHMARK_HASH = "dc2c4194dedb090198e6883735257908ce274bebc8611b40d958dbd026aa1fe6"
GRADER_HASH = "d9282a0ccc50daba3bfd232c058dfbab63a5c19a7323d585a7c2236b3a6c4ba8"
PROMPT_HASH = "5d2869822989e19b"
MODEL_REVISION = "0cb88a4f764b7a12671c53f0838cd831a0843b95"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pct(x: float, digits: int = 1) -> str:
    return f"{100 * x:.{digits}f}%"


def num(x: float, digits: int = 3) -> str:
    return f"{x:.{digits}f}"


def pvalue(p: float) -> str:
    if p < 1e-4:
        return f"{p:.2e}"
    return f"{p:.5f}".rstrip("0").rstrip(".")


def ci(lo: float, hi: float, digits: int = 3) -> str:
    return f"[{lo:.{digits}f}, {hi:.{digits}f}]"


def html_table(df: pd.DataFrame, caption: str, table_no: int, classes: str = "") -> str:
    thead = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    rows = []
    for _, row in df.iterrows():
        cells = "".join(f"<td>{html.escape(str(v))}</td>" for v in row.tolist())
        rows.append(f"<tr>{cells}</tr>")
    return (
        f'<div class="table-block {classes}">'
        f'<p class="caption">Table {table_no}. {html.escape(caption)}</p>'
        f'<table><thead><tr>{thead}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )


def markdown_table(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False)


def figure_html(src: str, caption: str, figure_no: int, width: str = "6.6in") -> str:
    return (
        f'<figure><img src="{html.escape(src)}" style="width:{width};">'
        f'<figcaption>Figure {figure_no}. {html.escape(caption)}</figcaption></figure>'
    )


def prepare_dirs() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)


def copy_figures() -> list[Path]:
    copied = []
    for p in sorted(SOURCE_FIGS.iterdir()):
        if p.suffix.lower() in {".png", ".pdf"}:
            dst = FIGS / p.name
            shutil.copyfile(p, dst)
            copied.append(dst)
    return copied


def save_table(df: pd.DataFrame, name: str) -> Path:
    path = TABLES / name
    df.to_csv(path, index=False)
    return path


def load_artifacts() -> dict:
    jsonl_hash = sha256(FINAL_JSONL)
    csv_hash = sha256(FINAL_CSV)
    if jsonl_hash != EXPECTED_JSONL_HASH:
        raise SystemExit(f"JSONL hash mismatch: {jsonl_hash}")
    if csv_hash != EXPECTED_CSV_HASH:
        raise SystemExit(f"CSV hash mismatch: {csv_hash}")
    data = {
        "primary": pd.read_csv(ANALYSIS / "primary_results.csv"),
        "trend": json.loads((ANALYSIS / "gee_trend_results.json").read_text()),
        "paired": pd.read_csv(ANALYSIS / "paired_tests.csv"),
        "complete": json.loads((ANALYSIS / "complete_case_sensitivity.json").read_text()),
        "exclude_unanswerable": json.loads((ANALYSIS / "unanswerable_exclusion_sensitivity.json").read_text()),
        "question_type": pd.read_csv(ANALYSIS / "question_type_results.csv"),
        "domain": pd.read_csv(ANALYSIS / "domain_results.csv"),
        "error_type": pd.read_csv(ANALYSIS / "error_type_by_context.csv"),
        "latency": pd.read_csv(ANALYSIS / "latency_analysis.csv"),
        "transitions": pd.read_csv(ANALYSIS / "family_transitions.csv"),
        "analysis_manifest": json.loads((ANALYSIS / "analysis_manifest.json").read_text()),
        "jsonl_hash": jsonl_hash,
        "csv_hash": csv_hash,
    }
    return data


def build_tables(a: dict) -> dict[str, pd.DataFrame]:
    primary = a["primary"].copy()
    main = pd.DataFrame(
        {
            "Context": primary["context"],
            "Gradable N": primary["gradable_n"].astype(int),
            "Correct": primary["correct_rate"].map(pct),
            "Inaccurate": primary["inaccuracy_rate"].map(pct),
            "Inaccuracy 95% CI": [
                f"{pct(lo)}-{pct(hi)}" for lo, hi in zip(primary["inaccuracy_ci_low"], primary["inaccuracy_ci_high"])
            ],
            "Hallucinatory Inaccuracy": primary["hallucinatory_rate"].map(pct),
            "Grounded Inaccuracy": primary["grounded_rate"].map(pct),
            "Runtime Failures": primary["runtime_failures"].astype(int),
            "Mean Latency": primary["mean_latency"].map(lambda x: f"{x:.3f} s"),
        }
    )
    trend_rows = []
    labels = {
        "inaccurate": "Overall Inaccuracy",
        "hallucinatory_inaccuracy": "Hallucinatory Inaccuracy",
        "grounded_inaccuracy": "Grounded Inaccuracy",
        "composition": "Hallucinatory vs Grounded Among Inaccuracies",
    }
    for key, label in labels.items():
        r = a["trend"][key]
        trend_rows.append(
            {
                "Outcome": label,
                "OR per 2x Context": num(r["odds_ratio_per_2x_context"]),
                "95% CI": ci(r["odds_ratio_ci_low"], r["odds_ratio_ci_high"]),
                "p-value": pvalue(r["p_value"]),
                "Interpretation": "Odds ratio per doubling of rendered input tokens",
            }
        )
    trend = pd.DataFrame(trend_rows)

    paired = a["paired"].copy()
    paired_table = paired[
        [
            "outcome",
            "comparison",
            "paired_n",
            "absolute_percentage_point_difference",
            "discordant_4K0_cmp1",
            "discordant_4K1_cmp0",
            "raw_p_value",
            "holm_adjusted_p_value",
            "significant_after_holm_0_05",
        ]
    ].copy()
    paired_table.columns = [
        "Outcome",
        "Comparison",
        "Paired N",
        "Rate Difference (pp)",
        "4K=0, Higher=1",
        "4K=1, Higher=0",
        "Raw p",
        "Holm p",
        "Holm Significant",
    ]
    paired_table["Rate Difference (pp)"] = paired_table["Rate Difference (pp)"].map(lambda x: f"{x:.1f}")
    paired_table["Raw p"] = paired_table["Raw p"].map(pvalue)
    paired_table["Holm p"] = paired_table["Holm p"].map(pvalue)

    qt = a["question_type"].copy()
    qt_summary = []
    for q, g in qt.groupby("question_type", sort=True):
        first = g[g["context"] == "4K"].iloc[0]
        last = g[g["context"] == "82K"].iloc[0]
        qt_summary.append(
            {
                "Question Type": q,
                "4K Inaccuracy": pct(first["inaccuracy_rate"]),
                "82K Inaccuracy": pct(last["inaccuracy_rate"]),
                "4K Hallucinatory": pct(first["hallucinatory_rate"]),
                "82K Hallucinatory": pct(last["hallucinatory_rate"]),
                "4K Grounded": pct(first["grounded_rate"]),
                "82K Grounded": pct(last["grounded_rate"]),
            }
        )
    qt_summary = pd.DataFrame(qt_summary)

    dom = a["domain"].copy()
    dom_summary = []
    for d, g in dom.groupby("domain", sort=True):
        first = g[g["context"] == "4K"].iloc[0]
        last = g[g["context"] == "82K"].iloc[0]
        dom_summary.append(
            {
                "Domain": d,
                "4K Inaccuracy": pct(first["inaccuracy_rate"]),
                "82K Inaccuracy": pct(last["inaccuracy_rate"]),
                "4K Hallucinatory": pct(first["hallucinatory_rate"]),
                "82K Hallucinatory": pct(last["hallucinatory_rate"]),
                "4K Grounded": pct(first["grounded_rate"]),
                "82K Grounded": pct(last["grounded_rate"]),
            }
        )
    dom_summary = pd.DataFrame(dom_summary)

    err = a["error_type"].pivot(index="error_type", columns="context", values="count").fillna(0).astype(int)
    err = err[[c for c in ["4K", "8K", "16K", "32K", "64K", "82K"] if c in err.columns]]
    err["82K - 4K"] = err["82K"] - err["4K"]
    err_table = err.reset_index().rename(columns={"error_type": "Error Type"})

    latency = a["latency"].copy()
    latency_table = latency[
        ["context", "n_successful", "mean_latency", "median_latency", "p95_latency", "p99_latency", "mean_input_tokens", "mean_generated_tokens"]
    ].copy()
    latency_table.columns = ["Context", "N", "Mean", "Median", "P95", "P99", "Mean Input Tokens", "Mean Output Tokens"]
    for col in ["Mean", "Median", "P95", "P99"]:
        latency_table[col] = latency_table[col].map(lambda x: f"{x:.3f} s")
    latency_table["Mean Input Tokens"] = latency_table["Mean Input Tokens"].map(lambda x: f"{x:,.1f}")
    latency_table["Mean Output Tokens"] = latency_table["Mean Output Tokens"].map(lambda x: f"{x:.1f}")

    complete = a["complete"]["complete_case"]
    complete_table = pd.DataFrame(
        {
            "Outcome": [r["outcome"] for r in complete],
            "OR": [num(r["odds_ratio_per_2x_context"]) for r in complete],
            "95% CI": [ci(r["odds_ratio_ci_low"], r["odds_ratio_ci_high"]) for r in complete],
            "p-value": [pvalue(r["p_value"]) for r in complete],
        }
    )
    excl = a["exclude_unanswerable"]["exclude_unanswerable"]
    excl_table = pd.DataFrame(
        {
            "Outcome": [r["outcome"] for r in excl],
            "OR": [num(r["odds_ratio_per_2x_context"]) for r in excl],
            "95% CI": [ci(r["odds_ratio_ci_low"], r["odds_ratio_ci_high"]) for r in excl],
            "p-value": [pvalue(r["p_value"]) for r in excl],
        }
    )

    tables = {
        "main_results": main,
        "trend_results": trend,
        "paired_tests": paired_table,
        "question_type_summary": qt_summary,
        "domain_summary": dom_summary,
        "error_type_evolution": err_table,
        "latency": latency_table,
        "complete_case_sensitivity": complete_table,
        "exclude_unanswerable_sensitivity": excl_table,
    }
    for name, df in tables.items():
        save_table(df, f"{name}.csv")
    return tables


def build_markdown(a: dict, tables: dict[str, pd.DataFrame]) -> str:
    trend = a["trend"]
    primary = a["primary"]
    latency = a["latency"]
    excl = a["exclude_unanswerable"]["exclude_unanswerable"]
    complete = a["complete"]["complete_case"]
    qts = tables["question_type_summary"]
    doms = tables["domain_summary"]
    err = tables["error_type_evolution"]
    lines = []
    lines += [
        "# Longer Contexts Reduce Factual Reliability: Separating Hallucinatory and Grounded Errors in Llama 3.2 3B",
        "",
        "**Experiment D final report**  ",
        f"Generated: {date.today().isoformat()}  ",
        "**Model:** `meta-llama/Llama-3.2-3B-Instruct`  ",
        f"**Model revision:** `{MODEL_REVISION}`  ",
        "**Benchmark:** 500 question families, six context lengths, 3,000 attempted inference instances  ",
        "",
        "## Executive Summary",
        "",
        "This study asks how increasing long-context length affects factual reliability when an LLM must answer factual questions from authentic but competing primary-source records. The benchmark used 500 question families across SEC, FDA/Drugs@FDA, ClinicalTrials.gov, and FRED/ALFRED. Each family was evaluated at 4K, 8K, 16K, 32K, 64K, and an empirically hardware-bounded 82K context condition. The model was `meta-llama/Llama-3.2-3B-Instruct`, run with BF16 greedy decoding on an RTX 4090 using the frozen `llama_chat_v4` answer-only prompt.",
        "",
        f"Overall inaccuracy increased from **49.6% at 4K** to **70.7% at 82K**. A repeated-measures GEE logistic model clustered by `question_family_id` found an odds ratio of **{trend['inaccurate']['odds_ratio_per_2x_context']:.3f}** per doubling of rendered input tokens, 95% CI **{ci(trend['inaccurate']['odds_ratio_ci_low'], trend['inaccurate']['odds_ratio_ci_high'])}**, p = **{pvalue(trend['inaccurate']['p_value'])}**. Grounded Inaccuracy also increased substantially, from **15.4%** to **30.3%**, OR **{trend['grounded_inaccuracy']['odds_ratio_per_2x_context']:.3f}**, 95% CI **{ci(trend['grounded_inaccuracy']['odds_ratio_ci_low'], trend['grounded_inaccuracy']['odds_ratio_ci_high'])}**, p = **{pvalue(trend['grounded_inaccuracy']['p_value'])}**.",
        "",
        f"Hallucinatory Inaccuracy increased in the full dataset, OR **{trend['hallucinatory_inaccuracy']['odds_ratio_per_2x_context']:.3f}**, 95% CI **{ci(trend['hallucinatory_inaccuracy']['odds_ratio_ci_low'], trend['hallucinatory_inaccuracy']['odds_ratio_ci_high'])}**, p = **{pvalue(trend['hallucinatory_inaccuracy']['p_value'])}**. However, after excluding UNANSWERABLE questions, Hallucinatory Inaccuracy decreased with context length, OR **{excl[1]['odds_ratio_per_2x_context']:.3f}**, 95% CI **{ci(excl[1]['odds_ratio_ci_low'], excl[1]['odds_ratio_ci_high'])}**, p = **{pvalue(excl[1]['p_value'])}**. Thus the full-dataset hallucination increase is driven primarily by increasing failed abstention on unanswerable cases, while answerable factual tasks show a growing grounded contextual-confusion problem rather than more unsupported fabrication.",
        "",
        "## 1. Introduction and Motivation",
        "",
        "The central research question is: how does increasing context length affect factual reliability when an LLM must retrieve and reason over authentic but competing contextual records? A single hallucination rate is insufficient for this setting. Long-context failures can arise from unsupported fabrication, selection of the wrong legitimate contextual fact, wrong entity binding, wrong temporal binding, wrong version binding, calculation mistakes, or failure to abstain when evidence is absent.",
        "",
        "This report separates inaccurate responses into Hallucinatory Inaccuracy and Grounded Inaccuracy. Inaccurate means any response that does not match the deterministic gold answer. Hallucinatory Inaccuracy is an inaccurate factual response unsupported by the supplied context, primarily `UNSUPPORTED_VALUE` and `FAILED_TO_ABSTAIN`. Grounded Inaccuracy is an inaccurate response grounded in information actually present in the supplied context, including `WRONG_ENTITY`, `WRONG_PERIOD`, `WRONG_VERSION`, `WRONG_FIELD`, `WRONG_UNIT`, `WRONG_SERIES_VARIANT`, `CALCULATION_ERROR`, and `UNNECESSARY_ABSTENTION`.",
        "",
        "## 2. Data Sources",
        "",
        "The benchmark uses four authoritative primary-source domains: SEC filings, FDA/Drugs@FDA records, ClinicalTrials.gov records, and FRED/ALFRED time-series records. Each domain contributes 125 question families, for 500 total families. Authentic source records were used to construct target evidence, deterministic gold answers, same-domain distractors, temporal competitors, version competitors, entity competitors, series/unit competitors, and unanswerable cases.",
        "",
        markdown_table(pd.DataFrame({
            "Domain": ["SEC", "FDA / Drugs@FDA", "ClinicalTrials.gov", "FRED / ALFRED"],
            "Families": [125, 125, 125, 125],
            "Role": [
                "Company financial filings, concepts, periods, units, versions",
                "Drug application/product records, strengths, dosage forms, routes",
                "Trial identifiers, statuses, dates, arms, posted results",
                "Economic time series, vintages, units, seasonal/series variants",
            ],
        })),
        "",
        "## 3. Question-Family Design",
        "",
        markdown_table(pd.DataFrame({
            "Question Type": ["DIRECT_RETRIEVAL", "RETRIEVAL_CALCULATION", "TEMPORAL_VERSION", "ENTITY_UNIT_BINDING", "UNANSWERABLE", "Total"],
            "Families": [100, 150, 55, 95, 100, 500],
            "Purpose": [
                "Retrieve one explicitly requested fact from competing records",
                "Retrieve multiple operands and compute a deterministic result",
                "Select the correct date, period, or version among competitors",
                "Bind a requested value to the correct entity, unit, or series",
                "Return INSUFFICIENT_EVIDENCE when required evidence is absent",
                "",
            ],
        })),
        "",
        "The benchmark contains 400 answerable families and 100 unanswerable families. Each family keeps a fixed question, gold answer, evidence policy, and answerability across all context lengths; only the supplied same-domain context grows.",
        "",
        "## 4. Context-Length Design",
        "",
        "The context ladder is 4K, 8K, 16K, 32K, 64K, and 82K. The 82K condition is the hardware-validated maximum condition for RTX 4090 DynamicCache inference in this experiment and is not a doubling of 64K. Statistical models therefore used `log2(rendered_input_tokens)`, implemented as `log2(input_tokens)` from the frozen scored dataset.",
        "",
        markdown_table(pd.DataFrame({
            "Context": primary["context"],
            "Mean Rendered Input Tokens": primary["mean_input_tokens"].map(lambda x: f"{x:,.1f}"),
        })),
        "",
        "## 5. Experiment Size and Runtime Outcome",
        "",
        "The frozen benchmark has 500 families and six context conditions, giving 3,000 attempted inference instances. There were 2,998 successful generations and two CUDA OOM runtime failures, both at 82K. Runtime failures are reported separately and are not counted as factual inaccuracies.",
        "",
        "## 6. Model and Inference Configuration",
        "",
        f"The model was `meta-llama/Llama-3.2-3B-Instruct`, revision `{MODEL_REVISION}`, run on an NVIDIA GeForce RTX 4090. Inference used BF16, batch size 1, standard Hugging Face DynamicCache, greedy decoding, `do_sample=False`, `num_beams=1`, and `max_new_tokens=128`, with no quantization, no cache offloading, and no model offloading. The prompt was `llama_chat_v4`, prompt hash `{PROMPT_HASH}`, with frozen date `09 Aug 2026`. The output contract was `ANSWER: <answer>` or `ANSWER: INSUFFICIENT_EVIDENCE`. Among successful outputs, there were zero malformed outputs, zero outputs reaching the 128-token cap, and zero repetitive or degenerate outputs.",
        "",
        "## 7. Grading",
        "",
        f"Grading was deterministic. The frozen grader hash was `{GRADER_HASH}`. There were 2,998 successful outputs graded, 19 cases manually adjudicated under the frozen rules, and zero unresolved ambiguous cases. Seven adjudicated cases were actually correct grader edge cases; twelve were grounded `WRONG_ENTITY` cases. No manual case was converted to hallucination, and the deterministic grader itself was not modified.",
        "",
        markdown_table(pd.DataFrame({
            "Outcome": ["Correct", "Inaccurate", "Hallucinatory Inaccuracy", "Grounded Inaccuracy", "Runtime Failures", "Ambiguous"],
            "Count": [1176, 1822, 1132, 690, 2, 0],
        })),
        "",
        "## 8. Primary Factual-Reliability Results",
        "",
        markdown_table(tables["main_results"]),
        "",
        "![Figure 1. Factual Reliability Decomposition](figures/figure_01_factual_reliability_decomposition.png)",
        "",
        "## 9. Primary Statistical Model",
        "",
        f"The primary repeated-measures model was GEE logistic regression with outcome `inaccurate`, predictor `log2(rendered_input_tokens)`, and clustering by `question_family_id`. Each +1 increase in the predictor corresponds to a doubling of actual rendered context. The OR was **{trend['inaccurate']['odds_ratio_per_2x_context']:.3f}**, 95% CI **{ci(trend['inaccurate']['odds_ratio_ci_low'], trend['inaccurate']['odds_ratio_ci_high'])}**, p = **{pvalue(trend['inaccurate']['p_value'])}**. Each doubling of rendered context length was associated with approximately a 23.2% increase in the odds of producing an inaccurate response; this is an odds increase, not a percentage-point increase.",
        "",
        "![Figure 2. Overall Inaccuracy vs Context](figures/figure_02_overall_inaccuracy.png)",
        "",
        "## 10. Hallucinatory Inaccuracy",
        "",
        f"Hallucinatory Inaccuracy increased in the full benchmark from 34.2% at 4K to 40.4% at 82K. The GEE OR was **{trend['hallucinatory_inaccuracy']['odds_ratio_per_2x_context']:.3f}**, 95% CI **{ci(trend['hallucinatory_inaccuracy']['odds_ratio_ci_low'], trend['hallucinatory_inaccuracy']['odds_ratio_ci_high'])}**, p = **{pvalue(trend['hallucinatory_inaccuracy']['p_value'])}**. This result should be interpreted together with the UNANSWERABLE sensitivity analysis below.",
        "",
        "![Figure 3. Hallucinatory Inaccuracy vs Context](figures/figure_03_hallucinatory_inaccuracy.png)",
        "",
        "## 11. Grounded Inaccuracy",
        "",
        f"Grounded Inaccuracy increased from 15.4% at 4K to 30.3% at 82K. The GEE OR was **{trend['grounded_inaccuracy']['odds_ratio_per_2x_context']:.3f}**, 95% CI **{ci(trend['grounded_inaccuracy']['odds_ratio_ci_low'], trend['grounded_inaccuracy']['odds_ratio_ci_high'])}**, p = **{pvalue(trend['grounded_inaccuracy']['p_value'])}**. These errors involve legitimate contextual information but incorrect binding or reasoning, and are a central finding of the study.",
        "",
        "![Figure 4. Grounded Inaccuracy vs Context](figures/figure_04_grounded_inaccuracy.png)",
        "",
        "## 12. Sensitivity Analyses",
        "",
        "### 12.1 Excluding UNANSWERABLE Questions",
        "",
        markdown_table(tables["exclude_unanswerable_sensitivity"]),
        "",
        "After excluding UNANSWERABLE families, overall inaccuracy still increased and grounded inaccuracy increased strongly, but Hallucinatory Inaccuracy decreased with context length. This indicates that the full-dataset increase in Hallucinatory Inaccuracy is driven primarily by increasing failures to abstain on unanswerable tasks. Among answerable factual questions, hallucination decreases while grounded contextual errors increase.",
        "",
        "### 12.2 Complete-Case Sensitivity",
        "",
        markdown_table(tables["complete_case_sensitivity"]),
        "",
        "The complete-case analysis used 498 families with all six successful conditions and 2,988 observations. Conclusions were unchanged.",
        "",
        "## 13. Paired McNemar Tests",
        "",
        "All higher contexts were significant versus 4K for overall inaccuracy after Holm correction. Hallucinatory Inaccuracy was significant for 4K vs 8K, 64K, and 82K. Grounded Inaccuracy was significant for 4K vs 16K, 32K, 64K, and 82K.",
        "",
        markdown_table(tables["paired_tests"]),
        "",
        "## 14. Question-Type Analysis",
        "",
        markdown_table(tables["question_type_summary"]),
        "",
        "UNANSWERABLE failures rose from approximately 49.0% at 4K to 97.0% at 82K, explaining much of the full-dataset Hallucinatory Inaccuracy increase. TEMPORAL_VERSION inaccuracy rose from approximately 18.2% to 67.3%, indicating increasing temporal/version confusion. DIRECT_RETRIEVAL produced mostly grounded failures with near-zero unsupported hallucination. RETRIEVAL_CALCULATION had high error rates across context lengths. ENTITY_UNIT_BINDING also showed increasing inaccuracy, mainly through grounded errors. These subgroup analyses are exploratory.",
        "",
        "![Figure 6. Inaccuracy by Question Type](figures/figure_06_inaccuracy_by_question_type.png)",
        "",
        "![Figure 7. Grounded Inaccuracy by Question Type](figures/figure_07_grounded_inaccuracy_by_question_type.png)",
        "",
        "## 15. Domain Analysis",
        "",
        markdown_table(tables["domain_summary"]),
        "",
        "SEC and FRED showed the largest overall inaccuracy increases. FDA was comparatively flatter. ClinicalTrials increased mainly through grounded errors. Domain-level results should be interpreted cautiously because subgroup cell sizes are smaller.",
        "",
        "![Figure 8. Inaccuracy by Domain](figures/figure_08_inaccuracy_by_domain.png)",
        "",
        "![Figure 9. Grounded Inaccuracy by Domain](figures/figure_09_grounded_inaccuracy_by_domain.png)",
        "",
        "## 16. Error-Type Evolution",
        "",
        markdown_table(tables["error_type_evolution"]),
        "",
        "The largest 4K-to-82K increases were FAILED_TO_ABSTAIN (+48), WRONG_PERIOD (+39), WRONG_ENTITY (+15), and WRONG_FIELD (+14). UNSUPPORTED_VALUE decreased by 18. The growth in total inaccuracy is therefore not primarily due to arbitrary unsupported-value fabrication; it is substantially driven by abstention failure and contextual misbinding.",
        "",
        "![Figure 5. Error-Type Composition by Context](figures/figure_05_error_type_composition.png)",
        "",
        "## 17. Latency",
        "",
        markdown_table(tables["latency"]),
        "",
        "Inference cost increased sharply with context length. Factual reliability declined while inference latency rose, but this report does not claim that latency causes factual errors.",
        "",
        "![Figure 10. Inference Latency vs Rendered Context Tokens](figures/figure_10_latency_vs_context_tokens.png)",
        "",
        "## 18. Family-Level Transitions",
        "",
        "Family-level trajectories were heterogeneous. Some families were inaccurate at all available contexts; others first became inaccurate at longer contexts or showed non-monotonic recovery. The transition heatmap visualizes Correct, Hallucinatory Inaccuracy, and Grounded Inaccuracy across the six context conditions.",
        "",
        "![Figure 11. Family-Level Transition Heatmap](figures/figure_11_family_transition_heatmap.png)",
        "",
        "## 19. Discussion",
        "",
        "The dominant result is that increasing context length substantially reduces factual reliability. However, this degradation is not captured adequately by a single hallucination metric. Longer contexts introduce more authentic competing information, and the model increasingly selects, binds, or reasons over legitimate but incorrect contextual records. This grounded contextual-confusion mechanism is distinct from classical unsupported hallucination.",
        "",
        "The full dataset shows increasing Hallucinatory Inaccuracy, but the sensitivity analysis demonstrates that this is driven primarily by failed abstention on unanswerable questions. On answerable factual tasks, Hallucinatory Inaccuracy decreases while Grounded Inaccuracy increases. This distinction matters for benchmark design and for mitigation: preventing unsupported fabrication is not the same as improving entity, period, version, field, and series binding under long-context pressure.",
        "",
        "## 20. Limitations",
        "",
        "- One model: Llama 3.2 3B Instruct.",
        "- One hardware/inference configuration.",
        "- 500 question families across four structured factual domains.",
        "- Context tested through approximately 82K rendered input tokens.",
        "- Two 82K CUDA OOM runtime failures.",
        "- Answer-only model output, with no evidence-selection metric in Experiment D.",
        "- Deterministic grading plus 19 manually adjudicated edge cases.",
        "- The benchmark intentionally contains high-quality competing distractors.",
        "- Subgroup analyses are exploratory.",
        "- GEE was used rather than a full GLMM.",
        "- Results may not generalize directly to larger or proprietary LLMs.",
        "",
        "## 21. Conclusion",
        "",
        f"Inaccuracy increased from **49.6%** at 4K to **70.7%** at 82K. The primary GEE model estimated an inaccuracy OR of **{trend['inaccurate']['odds_ratio_per_2x_context']:.3f}** per context doubling, p = **{pvalue(trend['inaccurate']['p_value'])}**. Grounded Inaccuracy increased from **15.4%** to **30.3%**, OR **{trend['grounded_inaccuracy']['odds_ratio_per_2x_context']:.3f}**, p = **{pvalue(trend['grounded_inaccuracy']['p_value'])}**. Hallucinatory Inaccuracy increased from **34.2%** to **40.4%** in the full dataset, OR **{trend['hallucinatory_inaccuracy']['odds_ratio_per_2x_context']:.3f}**, p = **{pvalue(trend['hallucinatory_inaccuracy']['p_value'])}**, but excluding unanswerable tasks reversed that trend, OR **{excl[1]['odds_ratio_per_2x_context']:.3f}**, p = **{pvalue(excl[1]['p_value'])}**.",
        "",
        "Increasing context length substantially reduces factual reliability. The most robust mechanism on answerable factual tasks is an increase in grounded contextual confusion rather than an increase in unsupported fabrication.",
        "",
        "## Appendix A. Reproducibility and Provenance",
        "",
        f"- Final JSONL hash: `{a['jsonl_hash']}`",
        f"- Final CSV hash: `{a['csv_hash']}`",
        f"- Benchmark hash: `{BENCHMARK_HASH}`",
        f"- Grader hash: `{GRADER_HASH}`",
        f"- Prompt hash: `{PROMPT_HASH}`",
        f"- Model revision: `{MODEL_REVISION}`",
        f"- Bootstrap seed: `{a['analysis_manifest']['bootstrap_seed']}`",
        f"- Bootstrap replicates: `{a['analysis_manifest']['bootstrap_replicates']}`",
        f"- GEE specification: `{a['analysis_manifest']['gee_specification']}`",
        f"- Working correlation: `{a['analysis_manifest']['working_correlation']}`",
    ]
    return "\n".join(lines) + "\n"


def build_html(markdown_sections: str, tables: dict[str, pd.DataFrame]) -> str:
    # This HTML intentionally mirrors the Markdown content but adds polished Word/PDF styling.
    # A compact Markdown-to-HTML conversion is enough because the source is controlled.
    import re

    toc_items = [
        "Executive Summary",
        "1. Introduction and Motivation",
        "2. Data Sources",
        "3. Question-Family Design",
        "4. Context-Length Design",
        "5. Experiment Size and Runtime Outcome",
        "6. Model and Inference Configuration",
        "7. Grading",
        "8. Primary Factual-Reliability Results",
        "9. Primary Statistical Model",
        "10. Hallucinatory Inaccuracy",
        "11. Grounded Inaccuracy",
        "12. Sensitivity Analyses",
        "13. Paired McNemar Tests",
        "14. Question-Type Analysis",
        "15. Domain Analysis",
        "16. Error-Type Evolution",
        "17. Latency",
        "18. Family-Level Transitions",
        "19. Discussion",
        "20. Limitations",
        "21. Conclusion",
        "Appendix A. Reproducibility and Provenance",
    ]
    # Build HTML manually for better caption/table numbering.
    figs = {
        1: ("figures/figure_01_factual_reliability_decomposition.png", "Factual Reliability Decomposition. Correct, Hallucinatory Inaccuracy, and Grounded Inaccuracy sum to 100% of gradable responses at each context length."),
        2: ("figures/figure_02_overall_inaccuracy.png", "Overall Inaccuracy vs Context. GEE OR = 1.232 per 2x rendered context, 95% CI [1.178, 1.288], p = 8.66 x 10^-20."),
        3: ("figures/figure_03_hallucinatory_inaccuracy.png", "Hallucinatory Inaccuracy vs Context. GEE OR = 1.070, 95% CI [1.027, 1.115], p = 0.00133."),
        4: ("figures/figure_04_grounded_inaccuracy.png", "Grounded Inaccuracy vs Context. GEE OR = 1.215, 95% CI [1.153, 1.280], p = 3.34 x 10^-13."),
        5: ("figures/figure_05_error_type_composition.png", "Error-type composition by context length."),
        6: ("figures/figure_06_inaccuracy_by_question_type.png", "Inaccuracy by question type and context length."),
        7: ("figures/figure_07_grounded_inaccuracy_by_question_type.png", "Grounded Inaccuracy by question type and context length."),
        8: ("figures/figure_08_inaccuracy_by_domain.png", "Inaccuracy by domain and context length."),
        9: ("figures/figure_09_grounded_inaccuracy_by_domain.png", "Grounded Inaccuracy by domain and context length."),
        10: ("figures/figure_10_latency_vs_context_tokens.png", "Inference latency vs rendered context tokens."),
        11: ("figures/figure_11_family_transition_heatmap.png", "Family-level transition visualization across context lengths."),
    }
    style = """
    <style>
      @page { size: letter; margin: 0.72in 0.72in 0.72in 0.72in; }
      body { font-family: Aptos, Calibri, Arial, sans-serif; font-size: 10.5pt; color: #1b1b1b; line-height: 1.36; }
      .title-page { text-align: center; margin-top: 2.2in; page-break-after: always; }
      .title { font-size: 25pt; font-weight: 700; color: #17365d; margin-bottom: 0.25in; }
      .subtitle { font-size: 14pt; color: #4b5563; margin-bottom: 0.7in; }
      .meta { font-size: 10.5pt; color: #333; line-height: 1.55; }
      h1 { font-size: 18pt; color: #17365d; border-bottom: 1px solid #b8c7d9; padding-bottom: 4px; page-break-before: always; }
      h2 { font-size: 14pt; color: #24496f; margin-top: 18px; }
      h3 { font-size: 12pt; color: #24496f; margin-top: 14px; }
      p { margin: 0 0 8px 0; }
      .toc { page-break-after: always; }
      .toc li { margin-bottom: 5px; }
      table { border-collapse: collapse; width: 100%; margin: 6px 0 14px 0; font-size: 8.3pt; }
      th { background: #eaf0f7; color: #17365d; font-weight: 700; border: 1px solid #9fb3c8; padding: 5px; }
      td { border: 1px solid #c7d0d9; padding: 4px; vertical-align: top; }
      tr:nth-child(even) td { background: #f8fafc; }
      .caption, figcaption { font-size: 9pt; color: #374151; font-weight: 600; margin: 6px 0; }
      figure { text-align: center; margin: 14px 0 20px 0; page-break-inside: avoid; }
      figure img { max-width: 6.75in; }
      code { font-family: Consolas, 'Courier New', monospace; background: #f3f4f6; padding: 1px 3px; }
      ul { margin-top: 4px; }
      .callout { background: #eef5ff; border-left: 4px solid #4777b8; padding: 10px 12px; margin: 10px 0 14px 0; }
      .small { font-size: 9pt; color: #444; }
    </style>
    """
    domain_table = pd.DataFrame({
        "Domain": ["SEC", "FDA / Drugs@FDA", "ClinicalTrials.gov", "FRED / ALFRED"],
        "Families": [125, 125, 125, 125],
        "Role": [
            "Company financial filings, concepts, periods, units, versions",
            "Drug application/product records, strengths, dosage forms, routes",
            "Trial identifiers, statuses, dates, arms, posted results",
            "Economic time series, vintages, units, seasonal/series variants",
        ],
    })
    qdesign = pd.DataFrame({
        "Question Type": ["DIRECT_RETRIEVAL", "RETRIEVAL_CALCULATION", "TEMPORAL_VERSION", "ENTITY_UNIT_BINDING", "UNANSWERABLE", "Total"],
        "Families": [100, 150, 55, 95, 100, 500],
        "Purpose": [
            "Retrieve one explicitly requested fact from competing records",
            "Retrieve multiple operands and compute a deterministic result",
            "Select the correct date, period, or version among competitors",
            "Bind a requested value to the correct entity, unit, or series",
            "Return INSUFFICIENT_EVIDENCE when required evidence is absent",
            "",
        ],
    })
    outcome_totals = pd.DataFrame({
        "Outcome": ["Correct", "Inaccurate", "Hallucinatory Inaccuracy", "Grounded Inaccuracy", "Runtime Failures", "Ambiguous"],
        "Count": [1176, 1822, 1132, 690, 2, 0],
    })
    token_table = pd.DataFrame({
        "Context": ["4K", "8K", "16K", "32K", "64K", "82K"],
        "Mean Rendered Input Tokens": ["4,273.3", "8,330.6", "16,442.3", "32,671.4", "65,126.1", "81,745.1"],
    })
    table_no = 1
    parts = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        style,
        "</head><body>",
        "<section class='title-page'>",
        "<div class='title'>Longer Contexts Reduce Factual Reliability</div>",
        "<div class='subtitle'>Separating Hallucinatory and Grounded Errors in Llama 3.2 3B</div>",
        "<div class='meta'><b>Experiment D Final Report</b><br>Model: meta-llama/Llama-3.2-3B-Instruct<br>Benchmark: 500 question families, six context lengths<br>Date: "
        + html.escape(date.today().isoformat())
        + "</div></section>",
        "<section class='toc'><h1>Table of Contents</h1><ol>" + "".join(f"<li>{html.escape(x)}</li>" for x in toc_items) + "</ol></section>",
        "<h1>Executive Summary</h1>",
        "<p>This study asks how increasing long-context length affects factual reliability when an LLM must answer factual questions from authentic but competing primary-source records. The benchmark used 500 question families across SEC, FDA/Drugs@FDA, ClinicalTrials.gov, and FRED/ALFRED. Each family was evaluated at 4K, 8K, 16K, 32K, 64K, and an empirically hardware-bounded 82K condition.</p>",
        "<div class='callout'><p><b>Core result.</b> Overall inaccuracy increased from <b>49.6%</b> at 4K to <b>70.7%</b> at 82K. GEE OR per 2x rendered context = <b>1.232</b>, 95% CI <b>[1.178, 1.288]</b>, p = <b>8.66 x 10^-20</b>. Grounded Inaccuracy increased strongly. Hallucinatory Inaccuracy increased in the full dataset, but after excluding UNANSWERABLE tasks it decreased, indicating the full-dataset hallucination trend is driven primarily by failed abstention.</p></div>",
        "<h1>1. Introduction and Motivation</h1><p>The central research question is: how does increasing context length affect factual reliability when an LLM must retrieve and reason over authentic but competing contextual records? A single hallucination rate is insufficient because long-context failures may come from unsupported fabrication, selection of the wrong legitimate contextual fact, wrong entity/temporal/version binding, calculation mistakes, or failure to abstain.</p><p>Every successful response is classified as Correct, Hallucinatory Inaccuracy, or Grounded Inaccuracy. Inaccuracy is the sum of Hallucinatory Inaccuracy and Grounded Inaccuracy. Runtime failures are separate and are not factual inaccuracies.</p>",
        "<h1>2. Data Sources</h1><p>The benchmark uses four authoritative primary-source domains. Authentic records were used to construct target evidence, deterministic gold answers, same-domain distractors, temporal competitors, version competitors, entity competitors, series/unit competitors, and unanswerable cases.</p>",
        html_table(domain_table, "Authoritative source domains.", table_no),
    ]
    table_no += 1
    parts += [
        "<h1>3. Question-Family Design</h1><p>The benchmark contains 400 answerable families and 100 unanswerable families. The same question, gold answer, evidence policy, and answerability are preserved across all context lengths within a family.</p>",
        html_table(qdesign, "Question-type distribution.", table_no),
    ]
    table_no += 1
    parts += [
        "<h1>4. Context-Length Design</h1><p>The context ladder is 4K, 8K, 16K, 32K, 64K, and 82K. The 82K condition is not a doubling of 64K; models therefore used actual log2 rendered input tokens.</p>",
        html_table(token_table, "Mean rendered input tokens by context condition.", table_no),
    ]
    table_no += 1
    parts += [
        "<h1>5. Experiment Size and Runtime Outcome</h1><p>The frozen benchmark has 3,000 attempted inference instances. There were 2,998 successful generations and two CUDA OOM runtime failures, both at 82K. The OOM cases were excluded from factual-outcome denominators.</p>",
        "<h1>6. Model and Inference Configuration</h1><p>The model was <code>meta-llama/Llama-3.2-3B-Instruct</code>, revision <code>"
        + MODEL_REVISION
        + "</code>, run on an NVIDIA GeForce RTX 4090 with BF16, batch size 1, standard Hugging Face DynamicCache, greedy decoding, <code>do_sample=False</code>, <code>num_beams=1</code>, <code>max_new_tokens=128</code>, no quantization, no cache offloading, and no model offloading. The prompt was <code>llama_chat_v4</code>, prompt hash <code>"
        + PROMPT_HASH
        + "</code>, with frozen date <code>09 Aug 2026</code>. Successful outputs had zero malformed outputs, zero 128-token cap hits, and zero repetitive/degenerate outputs.</p>",
        "<h1>7. Grading</h1><p>Grading was deterministic. The frozen grader hash was <code>"
        + GRADER_HASH
        + "</code>. Nineteen cases were manually adjudicated under the frozen rules: seven correct grader edge cases and twelve grounded WRONG_ENTITY cases. No manual case was converted to hallucination.</p>",
        html_table(outcome_totals, "Final factual-outcome totals.", table_no),
    ]
    table_no += 1
    parts += [
        "<h1>8. Primary Factual-Reliability Results</h1>",
        html_table(tables["main_results"], "Primary factual-reliability results by context.", table_no),
        figure_html(figs[1][0], figs[1][1], 1),
    ]
    table_no += 1
    parts += [
        "<h1>9. Primary Statistical Model</h1><p>The primary model was GEE logistic regression with outcome <code>inaccurate</code>, predictor <code>log2(rendered_input_tokens)</code>, and clustering by <code>question_family_id</code>. Each +1 increase corresponds to a doubling of rendered context. OR = <b>1.232</b>, 95% CI <b>[1.178, 1.288]</b>, p = <b>8.66 x 10^-20</b>. This is an odds increase, not a percentage-point increase.</p>",
        html_table(tables["trend_results"], "GEE trend models.", table_no),
        figure_html(figs[2][0], figs[2][1], 2),
    ]
    table_no += 1
    parts += [
        "<h1>10. Hallucinatory Inaccuracy</h1><p>Hallucinatory Inaccuracy increased in the full benchmark from 34.2% at 4K to 40.4% at 82K. GEE OR = <b>1.070</b>, 95% CI <b>[1.027, 1.115]</b>, p = <b>0.00133</b>. This full-dataset result must be interpreted with the UNANSWERABLE sensitivity analysis.</p>",
        figure_html(figs[3][0], figs[3][1], 3),
        "<h1>11. Grounded Inaccuracy</h1><p>Grounded Inaccuracy increased from 15.4% at 4K to 30.3% at 82K. GEE OR = <b>1.215</b>, 95% CI <b>[1.153, 1.280]</b>, p = <b>3.34 x 10^-13</b>. These are legitimate contextual values bound or reasoned over incorrectly.</p>",
        figure_html(figs[4][0], figs[4][1], 4),
        "<h1>12. Sensitivity Analyses</h1><h2>12.1 Excluding UNANSWERABLE Questions</h2>",
        html_table(tables["exclude_unanswerable_sensitivity"], "Trend models after excluding UNANSWERABLE families.", table_no),
        "<p>After excluding UNANSWERABLE families, overall inaccuracy and grounded inaccuracy still increased, while Hallucinatory Inaccuracy decreased. The full-dataset increase in Hallucinatory Inaccuracy is therefore driven primarily by failed abstention on unanswerable tasks.</p>",
    ]
    table_no += 1
    parts += [
        "<h2>12.2 Complete-Case Sensitivity</h2>",
        html_table(tables["complete_case_sensitivity"], "Complete-case trend models using 498 families and 2,988 observations.", table_no),
        "<p>Conclusions were unchanged.</p>",
    ]
    table_no += 1
    parts += [
        "<h1>13. Paired McNemar Tests</h1><p>All higher contexts were significant versus 4K for overall inaccuracy after Holm correction. Hallucinatory Inaccuracy was significant for 4K vs 8K, 64K, and 82K. Grounded Inaccuracy was significant for 4K vs 16K, 32K, 64K, and 82K.</p>",
        html_table(tables["paired_tests"], "Paired McNemar comparisons against 4K.", table_no),
    ]
    table_no += 1
    parts += [
        "<h1>14. Question-Type Analysis</h1>",
        html_table(tables["question_type_summary"], "Question-type outcome rates at 4K and 82K.", table_no),
        "<p>UNANSWERABLE failures rose from approximately 49.0% to 97.0%, explaining much of the full-dataset Hallucinatory Inaccuracy increase. TEMPORAL_VERSION inaccuracy rose from approximately 18.2% to 67.3%, indicating temporal/version confusion. These subgroup results are exploratory.</p>",
        figure_html(figs[6][0], figs[6][1], 6),
        figure_html(figs[7][0], figs[7][1], 7),
    ]
    table_no += 1
    parts += [
        "<h1>15. Domain Analysis</h1>",
        html_table(tables["domain_summary"], "Domain outcome rates at 4K and 82K.", table_no),
        "<p>SEC and FRED showed the largest overall inaccuracy increases. FDA was comparatively flatter. ClinicalTrials increased mainly through grounded errors. Domain-level results are exploratory.</p>",
        figure_html(figs[8][0], figs[8][1], 8),
        figure_html(figs[9][0], figs[9][1], 9),
    ]
    table_no += 1
    parts += [
        "<h1>16. Error-Type Evolution</h1>",
        html_table(tables["error_type_evolution"], "Detailed error-type counts by context.", table_no),
        "<p>The largest 4K-to-82K increases were FAILED_TO_ABSTAIN (+48), WRONG_PERIOD (+39), WRONG_ENTITY (+15), and WRONG_FIELD (+14). UNSUPPORTED_VALUE decreased by 18. The growth in total inaccuracy is therefore substantially driven by abstention failure and contextual misbinding.</p>",
        figure_html(figs[5][0], figs[5][1], 5),
    ]
    table_no += 1
    parts += [
        "<h1>17. Latency</h1>",
        html_table(tables["latency"], "Inference latency by context.", table_no),
        "<p>Inference latency increased sharply with context length. This report does not claim latency causes factual errors.</p>",
        figure_html(figs[10][0], figs[10][1], 10),
    ]
    table_no += 1
    parts += [
        "<h1>18. Family-Level Transitions</h1><p>Family-level trajectories were heterogeneous, including always-correct, always-inaccurate, first-failure-at-longer-context, and non-monotonic patterns.</p>",
        figure_html(figs[11][0], figs[11][1], 11),
        "<h1>19. Discussion</h1><p>Increasing context length substantially reduces factual reliability. The degradation is not captured adequately by a single hallucination metric. More context introduces more authentic competing information, and the model increasingly selects, binds, or reasons over legitimate but incorrect contextual records. This grounded contextual-confusion mechanism is distinct from classical unsupported hallucination.</p><p>The full dataset shows increasing Hallucinatory Inaccuracy, but the sensitivity analysis demonstrates that this is driven primarily by failed abstention on unanswerable questions. On answerable factual tasks, Hallucinatory Inaccuracy decreases while Grounded Inaccuracy increases.</p>",
        "<h1>20. Limitations</h1><ul><li>One model: Llama 3.2 3B Instruct.</li><li>One hardware/inference configuration.</li><li>500 question families across four structured factual domains.</li><li>Context tested through approximately 82K rendered input tokens.</li><li>Two 82K CUDA OOM runtime failures.</li><li>Answer-only output with no evidence-selection metric.</li><li>Deterministic grading plus 19 manually adjudicated edge cases.</li><li>High-quality competing distractors by design.</li><li>Subgroup analyses are exploratory.</li><li>GEE rather than full GLMM.</li><li>Generalization to larger or proprietary LLMs is unknown.</li></ul>",
        "<h1>21. Conclusion</h1><p>Inaccuracy increased from <b>49.6%</b> at 4K to <b>70.7%</b> at 82K. The primary GEE model estimated an inaccuracy OR of <b>1.232</b> per context doubling, p = <b>8.66 x 10^-20</b>. Grounded Inaccuracy increased from <b>15.4%</b> to <b>30.3%</b>, OR <b>1.215</b>, p = <b>3.34 x 10^-13</b>. Hallucinatory Inaccuracy increased from <b>34.2%</b> to <b>40.4%</b> in the full dataset, OR <b>1.070</b>, p = <b>0.00133</b>, but excluding unanswerable tasks reversed that trend, OR <b>0.942</b>, p = <b>0.00275</b>.</p><p>Increasing context length substantially reduces factual reliability. The most robust mechanism on answerable factual tasks is an increase in grounded contextual confusion rather than an increase in unsupported fabrication.</p>",
        "<h1>Appendix A. Reproducibility and Provenance</h1><ul><li>Final JSONL hash: <code>"
        + EXPECTED_JSONL_HASH
        + "</code></li><li>Final CSV hash: <code>"
        + EXPECTED_CSV_HASH
        + "</code></li><li>Benchmark hash: <code>"
        + BENCHMARK_HASH
        + "</code></li><li>Grader hash: <code>"
        + GRADER_HASH
        + "</code></li><li>Prompt hash: <code>"
        + PROMPT_HASH
        + "</code></li><li>Model revision: <code>"
        + MODEL_REVISION
        + "</code></li></ul>",
        "</body></html>",
    ]
    return "\n".join(parts)


def convert_with_libreoffice(src: Path) -> tuple[Path | None, Path | None]:
    docx_path = OUT / "final_experiment_d_report.docx"
    pdf_path = OUT / "final_experiment_d_report.pdf"
    odt_path = OUT / "final_experiment_d_report.odt"
    env = os.environ.copy()
    env["HOME"] = str(OUT.resolve())
    env["MPLCONFIGDIR"] = str((OUT / ".mplconfig").resolve())
    subprocess.run(
        ["libreoffice", "--headless", "--convert-to", "odt", "--outdir", str(OUT), str(src)],
        check=True,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    generated_odt = OUT / (src.stem + ".odt")
    if generated_odt != odt_path:
        generated_odt.replace(odt_path)
    subprocess.run(
        ["libreoffice", "--headless", "--convert-to", "docx", "--outdir", str(OUT), str(odt_path)],
        check=True,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    generated_docx = OUT / (odt_path.stem + ".docx")
    if generated_docx != docx_path:
        generated_docx.replace(docx_path)
    try:
        subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", str(OUT), str(odt_path)],
            check=True,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except Exception:
        pdf_path = None
    return docx_path if docx_path.exists() else None, pdf_path if pdf_path and pdf_path.exists() else None


def xml_escape(text: object) -> str:
    return html.escape("" if text is None else str(text), quote=True)


def w_p(text: str = "", style: str | None = None, page_break_before: bool = False, align: str | None = None) -> str:
    props = []
    if style:
        props.append(f'<w:pStyle w:val="{style}"/>')
    if page_break_before:
        props.append("<w:pageBreakBefore/>")
    if align:
        props.append(f'<w:jc w:val="{align}"/>')
    ppr = f"<w:pPr>{''.join(props)}</w:pPr>" if props else ""
    if not text:
        return f"<w:p>{ppr}</w:p>"
    runs = []
    for part in str(text).split("\n"):
        runs.append(f'<w:r><w:t xml:space="preserve">{xml_escape(part)}</w:t></w:r>')
        runs.append("<w:r><w:br/></w:r>")
    if runs:
        runs.pop()
    return f"<w:p>{ppr}{''.join(runs)}</w:p>"


def w_table(df: pd.DataFrame) -> str:
    rows = []
    widths = [max(1200, int(9000 / max(1, len(df.columns)))) for _ in df.columns]
    def cell(text: object, width: int, header: bool = False) -> str:
        shade = '<w:shd w:fill="EAF0F7"/>' if header else ""
        bold_open = "<w:rPr><w:b/></w:rPr>" if header else ""
        return (
            f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{shade}</w:tcPr>'
            f'<w:p><w:r>{bold_open}<w:t xml:space="preserve">{xml_escape(text)}</w:t></w:r></w:p></w:tc>'
        )
    rows.append("<w:tr>" + "".join(cell(c, w, True) for c, w in zip(df.columns, widths)) + "</w:tr>")
    for _, r in df.iterrows():
        rows.append("<w:tr>" + "".join(cell(v, w, False) for v, w in zip(r.tolist(), widths)) + "</w:tr>")
    borders = (
        '<w:tblBorders><w:top w:val="single" w:sz="4" w:color="9FB3C8"/>'
        '<w:left w:val="single" w:sz="4" w:color="9FB3C8"/>'
        '<w:bottom w:val="single" w:sz="4" w:color="9FB3C8"/>'
        '<w:right w:val="single" w:sz="4" w:color="9FB3C8"/>'
        '<w:insideH w:val="single" w:sz="4" w:color="C7D0D9"/>'
        '<w:insideV w:val="single" w:sz="4" w:color="C7D0D9"/></w:tblBorders>'
    )
    return f'<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/>{borders}</w:tblPr>{"".join(rows)}</w:tbl>'


def image_xml(rel_id: str, path: Path, doc_pr_id: int, max_width_in: float = 6.5) -> str:
    with Image.open(path) as im:
        width_px, height_px = im.size
    width_in = min(max_width_in, width_px / 160)
    height_in = width_in * height_px / width_px
    cx = int(width_in * 914400)
    cy = int(height_in * 914400)
    return f"""
    <w:p>
      <w:pPr><w:jc w:val="center"/></w:pPr>
      <w:r><w:drawing>
        <wp:inline distT="0" distB="0" distL="0" distR="0">
          <wp:extent cx="{cx}" cy="{cy}"/>
          <wp:docPr id="{doc_pr_id}" name="Figure {doc_pr_id}"/>
          <a:graphic>
            <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
              <pic:pic>
                <pic:nvPicPr><pic:cNvPr id="{doc_pr_id}" name="{xml_escape(path.name)}"/><pic:cNvPicPr/></pic:nvPicPr>
                <pic:blipFill><a:blip r:embed="{rel_id}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>
                <pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>
              </pic:pic>
            </a:graphicData>
          </a:graphic>
        </wp:inline>
      </w:drawing></w:r>
    </w:p>
    """


def build_docx_direct(path: Path, tables: dict[str, pd.DataFrame]) -> Path:
    fig_specs = [
        ("figure_01_factual_reliability_decomposition.png", "Factual Reliability Decomposition. Correct, Hallucinatory Inaccuracy, and Grounded Inaccuracy sum to 100% of gradable responses at each context length."),
        ("figure_02_overall_inaccuracy.png", "Overall Inaccuracy vs Context. GEE OR = 1.232 per 2x rendered context, 95% CI [1.178, 1.288], p = 8.66 x 10^-20."),
        ("figure_03_hallucinatory_inaccuracy.png", "Hallucinatory Inaccuracy vs Context. GEE OR = 1.070, 95% CI [1.027, 1.115], p = 0.00133."),
        ("figure_04_grounded_inaccuracy.png", "Grounded Inaccuracy vs Context. GEE OR = 1.215, 95% CI [1.153, 1.280], p = 3.34 x 10^-13."),
        ("figure_05_error_type_composition.png", "Error-type composition by context length."),
        ("figure_06_inaccuracy_by_question_type.png", "Inaccuracy by question type and context length."),
        ("figure_07_grounded_inaccuracy_by_question_type.png", "Grounded Inaccuracy by question type and context length."),
        ("figure_08_inaccuracy_by_domain.png", "Inaccuracy by domain and context length."),
        ("figure_09_grounded_inaccuracy_by_domain.png", "Grounded Inaccuracy by domain and context length."),
        ("figure_10_latency_vs_context_tokens.png", "Inference latency vs rendered context tokens."),
        ("figure_11_family_transition_heatmap.png", "Family-level transition visualization across context lengths."),
    ]
    rels = ['<Relationship Id="rFooter1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>']
    image_rel_ids = {}
    for i, (name, _) in enumerate(fig_specs, start=1):
        rid = f"rImg{i}"
        image_rel_ids[name] = rid
        rels.append(f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/{name}"/>')

    body: list[str] = []
    body += [
        w_p("Longer Contexts Reduce Factual Reliability", "Title", align="center"),
        w_p("Separating Hallucinatory and Grounded Errors in Llama 3.2 3B", "Subtitle", align="center"),
        w_p("Experiment D Final Report", "Heading2", align="center"),
        w_p(f"Generated: {date.today().isoformat()}\nModel: meta-llama/Llama-3.2-3B-Instruct\nBenchmark: 500 question families, six context lengths", align="center"),
        w_p("", page_break_before=True),
        w_p("Table of Contents", "Heading1"),
    ]
    toc = [
        "Executive Summary", "1. Introduction and Motivation", "2. Data Sources", "3. Question-Family Design",
        "4. Context-Length Design", "5. Experiment Size and Runtime Outcome", "6. Model and Inference Configuration",
        "7. Grading", "8. Primary Factual-Reliability Results", "9. Primary Statistical Model",
        "10. Hallucinatory Inaccuracy", "11. Grounded Inaccuracy", "12. Sensitivity Analyses",
        "13. Paired McNemar Tests", "14. Question-Type Analysis", "15. Domain Analysis",
        "16. Error-Type Evolution", "17. Latency", "18. Family-Level Transitions", "19. Discussion",
        "20. Limitations", "21. Conclusion", "Appendix A. Reproducibility and Provenance",
    ]
    for item in toc:
        body.append(w_p(item, "TOCLine"))
    body += [
        w_p("Executive Summary", "Heading1", page_break_before=True),
        w_p("This study asks how increasing long-context length affects factual reliability when an LLM must answer factual questions from authentic but competing primary-source records. The benchmark used 500 question families across SEC, FDA/Drugs@FDA, ClinicalTrials.gov, and FRED/ALFRED. Each family was evaluated at 4K, 8K, 16K, 32K, 64K, and an empirically hardware-bounded 82K condition."),
        w_p("Overall inaccuracy increased from 49.6% at 4K to 70.7% at 82K. GEE OR per 2x rendered context = 1.232, 95% CI [1.178, 1.288], p = 8.66 x 10^-20. Grounded Inaccuracy increased strongly. Hallucinatory Inaccuracy increased in the full dataset, but after excluding UNANSWERABLE tasks it decreased, indicating the full-dataset hallucination trend is driven primarily by failed abstention."),
        w_p("1. Introduction and Motivation", "Heading1"),
        w_p("The central research question is how increasing context length affects factual reliability when an LLM must retrieve and reason over authentic but competing contextual records. A single hallucination rate is insufficient because long-context failures may come from unsupported fabrication, selection of the wrong legitimate contextual fact, wrong entity/temporal/version binding, calculation mistakes, or failure to abstain."),
        w_p("Every successful response is classified as Correct, Hallucinatory Inaccuracy, or Grounded Inaccuracy. Inaccuracy is the sum of Hallucinatory Inaccuracy and Grounded Inaccuracy. Runtime failures are separate and are not factual inaccuracies."),
        w_p("2. Data Sources", "Heading1"),
        w_p("The benchmark uses four authoritative primary-source domains. Authentic records were used to construct target evidence, deterministic gold answers, same-domain distractors, temporal competitors, version competitors, entity competitors, series/unit competitors, and unanswerable cases."),
        w_p("Table 1. Authoritative source domains.", "Caption"),
        w_table(pd.DataFrame({"Domain": ["SEC", "FDA / Drugs@FDA", "ClinicalTrials.gov", "FRED / ALFRED"], "Families": [125, 125, 125, 125], "Role": ["Company financial filings, concepts, periods, units, versions", "Drug application/product records, strengths, dosage forms, routes", "Trial identifiers, statuses, dates, arms, posted results", "Economic time series, vintages, units, seasonal/series variants"]})),
        w_p("3. Question-Family Design", "Heading1"),
        w_p("The benchmark contains 400 answerable families and 100 unanswerable families. The same question, gold answer, evidence policy, and answerability are preserved across all context lengths within a family."),
        w_p("Table 2. Question-type distribution.", "Caption"),
        w_table(pd.DataFrame({"Question Type": ["DIRECT_RETRIEVAL", "RETRIEVAL_CALCULATION", "TEMPORAL_VERSION", "ENTITY_UNIT_BINDING", "UNANSWERABLE", "Total"], "Families": [100, 150, 55, 95, 100, 500], "Purpose": ["Retrieve one explicitly requested fact from competing records", "Retrieve multiple operands and compute a deterministic result", "Select the correct date, period, or version among competitors", "Bind a requested value to the correct entity, unit, or series", "Return INSUFFICIENT_EVIDENCE when required evidence is absent", ""]})),
        w_p("4. Context-Length Design", "Heading1"),
        w_p("The context ladder is 4K, 8K, 16K, 32K, 64K, and 82K. The 82K condition is not a doubling of 64K; models therefore used actual log2 rendered input tokens."),
        w_p("Table 3. Mean rendered input tokens by context condition.", "Caption"),
        w_table(pd.DataFrame({"Context": ["4K", "8K", "16K", "32K", "64K", "82K"], "Mean Rendered Input Tokens": ["4,273.3", "8,330.6", "16,442.3", "32,671.4", "65,126.1", "81,745.1"]})),
        w_p("5. Experiment Size and Runtime Outcome", "Heading1"),
        w_p("The frozen benchmark has 3,000 attempted inference instances. There were 2,998 successful generations and two CUDA OOM runtime failures, both at 82K. The OOM cases were excluded from factual-outcome denominators."),
        w_p("6. Model and Inference Configuration", "Heading1"),
        w_p(f"The model was meta-llama/Llama-3.2-3B-Instruct, revision {MODEL_REVISION}, run on an NVIDIA GeForce RTX 4090 with BF16, batch size 1, standard Hugging Face DynamicCache, greedy decoding, do_sample=False, num_beams=1, max_new_tokens=128, no quantization, no cache offloading, and no model offloading. The prompt was llama_chat_v4, prompt hash {PROMPT_HASH}, with frozen date 09 Aug 2026. Successful outputs had zero malformed outputs, zero 128-token cap hits, and zero repetitive/degenerate outputs."),
        w_p("7. Grading", "Heading1"),
        w_p(f"Grading was deterministic. The frozen grader hash was {GRADER_HASH}. Nineteen cases were manually adjudicated under the frozen rules: seven correct grader edge cases and twelve grounded WRONG_ENTITY cases. No manual case was converted to hallucination."),
        w_p("Table 4. Final factual-outcome totals.", "Caption"),
        w_table(pd.DataFrame({"Outcome": ["Correct", "Inaccurate", "Hallucinatory Inaccuracy", "Grounded Inaccuracy", "Runtime Failures", "Ambiguous"], "Count": [1176, 1822, 1132, 690, 2, 0]})),
        w_p("8. Primary Factual-Reliability Results", "Heading1"),
        w_p("Table 5. Primary factual-reliability results by context.", "Caption"),
        w_table(tables["main_results"]),
        image_xml(image_rel_ids["figure_01_factual_reliability_decomposition.png"], FIGS / "figure_01_factual_reliability_decomposition.png", 1),
        w_p("Figure 1. Factual Reliability Decomposition. Correct, Hallucinatory Inaccuracy, and Grounded Inaccuracy sum to 100% of gradable responses at each context length.", "Caption"),
        w_p("9. Primary Statistical Model", "Heading1"),
        w_p("The primary model was GEE logistic regression with outcome inaccurate, predictor log2(rendered_input_tokens), and clustering by question_family_id. Each +1 increase corresponds to a doubling of rendered context. OR = 1.232, 95% CI [1.178, 1.288], p = 8.66 x 10^-20. This is an odds increase, not a percentage-point increase."),
        w_p("Table 6. GEE trend models.", "Caption"),
        w_table(tables["trend_results"]),
        image_xml(image_rel_ids["figure_02_overall_inaccuracy.png"], FIGS / "figure_02_overall_inaccuracy.png", 2),
        w_p("Figure 2. Overall Inaccuracy vs Context. GEE OR = 1.232 per 2x rendered context, 95% CI [1.178, 1.288], p = 8.66 x 10^-20.", "Caption"),
        w_p("10. Hallucinatory Inaccuracy", "Heading1"),
        w_p("Hallucinatory Inaccuracy increased in the full benchmark from 34.2% at 4K to 40.4% at 82K. GEE OR = 1.070, 95% CI [1.027, 1.115], p = 0.00133. This full-dataset result must be interpreted with the UNANSWERABLE sensitivity analysis."),
        image_xml(image_rel_ids["figure_03_hallucinatory_inaccuracy.png"], FIGS / "figure_03_hallucinatory_inaccuracy.png", 3),
        w_p("Figure 3. Hallucinatory Inaccuracy vs Context. GEE OR = 1.070, 95% CI [1.027, 1.115], p = 0.00133.", "Caption"),
        w_p("11. Grounded Inaccuracy", "Heading1"),
        w_p("Grounded Inaccuracy increased from 15.4% at 4K to 30.3% at 82K. GEE OR = 1.215, 95% CI [1.153, 1.280], p = 3.34 x 10^-13. These are legitimate contextual values bound or reasoned over incorrectly."),
        image_xml(image_rel_ids["figure_04_grounded_inaccuracy.png"], FIGS / "figure_04_grounded_inaccuracy.png", 4),
        w_p("Figure 4. Grounded Inaccuracy vs Context. GEE OR = 1.215, 95% CI [1.153, 1.280], p = 3.34 x 10^-13.", "Caption"),
        w_p("12. Sensitivity Analyses", "Heading1"),
        w_p("12.1 Excluding UNANSWERABLE Questions", "Heading2"),
        w_p("Table 7. Trend models after excluding UNANSWERABLE families.", "Caption"),
        w_table(tables["exclude_unanswerable_sensitivity"]),
        w_p("After excluding UNANSWERABLE families, overall inaccuracy and grounded inaccuracy still increased, while Hallucinatory Inaccuracy decreased. The full-dataset increase in Hallucinatory Inaccuracy is therefore driven primarily by failed abstention on unanswerable tasks."),
        w_p("12.2 Complete-Case Sensitivity", "Heading2"),
        w_p("Table 8. Complete-case trend models using 498 families and 2,988 observations.", "Caption"),
        w_table(tables["complete_case_sensitivity"]),
        w_p("Conclusions were unchanged."),
        w_p("13. Paired McNemar Tests", "Heading1"),
        w_p("All higher contexts were significant versus 4K for overall inaccuracy after Holm correction. Hallucinatory Inaccuracy was significant for 4K vs 8K, 64K, and 82K. Grounded Inaccuracy was significant for 4K vs 16K, 32K, 64K, and 82K."),
        w_p("Table 9. Paired McNemar comparisons against 4K.", "Caption"),
        w_table(tables["paired_tests"]),
        w_p("14. Question-Type Analysis", "Heading1"),
        w_p("Table 10. Question-type outcome rates at 4K and 82K.", "Caption"),
        w_table(tables["question_type_summary"]),
        w_p("UNANSWERABLE failures rose from approximately 49.0% to 97.0%, explaining much of the full-dataset Hallucinatory Inaccuracy increase. TEMPORAL_VERSION inaccuracy rose from approximately 18.2% to 67.3%, indicating temporal/version confusion. These subgroup results are exploratory."),
        image_xml(image_rel_ids["figure_06_inaccuracy_by_question_type.png"], FIGS / "figure_06_inaccuracy_by_question_type.png", 6),
        w_p("Figure 6. Inaccuracy by question type and context length.", "Caption"),
        image_xml(image_rel_ids["figure_07_grounded_inaccuracy_by_question_type.png"], FIGS / "figure_07_grounded_inaccuracy_by_question_type.png", 7),
        w_p("Figure 7. Grounded Inaccuracy by question type and context length.", "Caption"),
        w_p("15. Domain Analysis", "Heading1"),
        w_p("Table 11. Domain outcome rates at 4K and 82K.", "Caption"),
        w_table(tables["domain_summary"]),
        w_p("SEC and FRED showed the largest overall inaccuracy increases. FDA was comparatively flatter. ClinicalTrials increased mainly through grounded errors. Domain-level results are exploratory."),
        image_xml(image_rel_ids["figure_08_inaccuracy_by_domain.png"], FIGS / "figure_08_inaccuracy_by_domain.png", 8),
        w_p("Figure 8. Inaccuracy by domain and context length.", "Caption"),
        image_xml(image_rel_ids["figure_09_grounded_inaccuracy_by_domain.png"], FIGS / "figure_09_grounded_inaccuracy_by_domain.png", 9),
        w_p("Figure 9. Grounded Inaccuracy by domain and context length.", "Caption"),
        w_p("16. Error-Type Evolution", "Heading1"),
        w_p("Table 12. Detailed error-type counts by context.", "Caption"),
        w_table(tables["error_type_evolution"]),
        w_p("The largest 4K-to-82K increases were FAILED_TO_ABSTAIN (+48), WRONG_PERIOD (+39), WRONG_ENTITY (+15), and WRONG_FIELD (+14). UNSUPPORTED_VALUE decreased by 18. The growth in total inaccuracy is therefore substantially driven by abstention failure and contextual misbinding."),
        image_xml(image_rel_ids["figure_05_error_type_composition.png"], FIGS / "figure_05_error_type_composition.png", 5),
        w_p("Figure 5. Error-type composition by context length.", "Caption"),
        w_p("17. Latency", "Heading1"),
        w_p("Table 13. Inference latency by context.", "Caption"),
        w_table(tables["latency"]),
        w_p("Inference latency increased sharply with context length. This report does not claim latency causes factual errors."),
        image_xml(image_rel_ids["figure_10_latency_vs_context_tokens.png"], FIGS / "figure_10_latency_vs_context_tokens.png", 10),
        w_p("Figure 10. Inference latency vs rendered context tokens.", "Caption"),
        w_p("18. Family-Level Transitions", "Heading1"),
        w_p("Family-level trajectories were heterogeneous, including always-correct, always-inaccurate, first-failure-at-longer-context, and non-monotonic patterns."),
        image_xml(image_rel_ids["figure_11_family_transition_heatmap.png"], FIGS / "figure_11_family_transition_heatmap.png", 11),
        w_p("Figure 11. Family-level transition visualization across context lengths.", "Caption"),
        w_p("19. Discussion", "Heading1"),
        w_p("Increasing context length substantially reduces factual reliability. The degradation is not captured adequately by a single hallucination metric. More context introduces more authentic competing information, and the model increasingly selects, binds, or reasons over legitimate but incorrect contextual records. This grounded contextual-confusion mechanism is distinct from classical unsupported hallucination."),
        w_p("The full dataset shows increasing Hallucinatory Inaccuracy, but the sensitivity analysis demonstrates that this is driven primarily by failed abstention on unanswerable questions. On answerable factual tasks, Hallucinatory Inaccuracy decreases while Grounded Inaccuracy increases."),
        w_p("20. Limitations", "Heading1"),
        w_p("Limitations include one model, one hardware/inference configuration, 500 question families across four structured factual domains, context tested through approximately 82K rendered input tokens, two 82K CUDA OOM runtime failures, answer-only output with no evidence-selection metric, deterministic grading plus 19 manually adjudicated edge cases, high-quality competing distractors by design, exploratory subgroup analyses, GEE rather than a full GLMM, and uncertain generalization to larger or proprietary LLMs."),
        w_p("21. Conclusion", "Heading1"),
        w_p("Inaccuracy increased from 49.6% at 4K to 70.7% at 82K. The primary GEE model estimated an inaccuracy OR of 1.232 per context doubling, p = 8.66 x 10^-20. Grounded Inaccuracy increased from 15.4% to 30.3%, OR 1.215, p = 3.34 x 10^-13. Hallucinatory Inaccuracy increased from 34.2% to 40.4% in the full dataset, OR 1.070, p = 0.00133, but excluding unanswerable tasks reversed that trend, OR 0.942, p = 0.00275."),
        w_p("Increasing context length substantially reduces factual reliability. The most robust mechanism on answerable factual tasks is an increase in grounded contextual confusion rather than an increase in unsupported fabrication."),
        w_p("Appendix A. Reproducibility and Provenance", "Heading1"),
        w_p(f"Final JSONL hash: {EXPECTED_JSONL_HASH}\nFinal CSV hash: {EXPECTED_CSV_HASH}\nBenchmark hash: {BENCHMARK_HASH}\nGrader hash: {GRADER_HASH}\nPrompt hash: {PROMPT_HASH}\nModel revision: {MODEL_REVISION}"),
    ]

    sect_pr = """
    <w:sectPr>
      <w:footerReference w:type="default" r:id="rFooter1"/>
      <w:pgSz w:w="12240" w:h="15840"/>
      <w:pgMar w:top="900" w:right="850" w:bottom="900" w:left="850" w:header="450" w:footer="450" w:gutter="0"/>
    </w:sectPr>
    """
    document = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
      xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
      xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
      xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
      xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
      <w:body>{''.join(body)}{sect_pr}</w:body>
    </w:document>"""
    styles = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:style w:type="paragraph" w:styleId="Normal"><w:name w:val="Normal"/><w:rPr><w:rFonts w:ascii="Aptos" w:hAnsi="Aptos"/><w:sz w:val="21"/></w:rPr></w:style>
      <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:pPr><w:jc w:val="center"/><w:spacing w:after="240"/></w:pPr><w:rPr><w:b/><w:color w:val="17365D"/><w:sz w:val="48"/></w:rPr></w:style>
      <w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:pPr><w:jc w:val="center"/><w:spacing w:after="240"/></w:pPr><w:rPr><w:color w:val="4B5563"/><w:sz w:val="28"/></w:rPr></w:style>
      <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="320" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:color w:val="17365D"/><w:sz w:val="32"/></w:rPr></w:style>
      <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="240" w:after="100"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:color w:val="24496F"/><w:sz w:val="26"/></w:rPr></w:style>
      <w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="Caption"/><w:pPr><w:spacing w:before="80" w:after="80"/></w:pPr><w:rPr><w:b/><w:color w:val="374151"/><w:sz w:val="18"/></w:rPr></w:style>
      <w:style w:type="paragraph" w:styleId="TOCLine"><w:name w:val="TOC Line"/><w:pPr><w:spacing w:after="80"/></w:pPr><w:rPr><w:sz w:val="21"/></w:rPr></w:style>
    </w:styles>"""
    footer = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:t>Page </w:t></w:r><w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText> PAGE </w:instrText></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>
    </w:ftr>"""
    rels_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{''.join(rels)}</Relationships>"""
    root_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
      <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
    </Relationships>"""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
      <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
      <Default Extension="xml" ContentType="application/xml"/>
      <Default Extension="png" ContentType="image/png"/>
      <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
      <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
      <Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
    </Types>"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("word/document.xml", document)
        z.writestr("word/styles.xml", styles)
        z.writestr("word/footer1.xml", footer)
        z.writestr("word/_rels/document.xml.rels", rels_xml)
        for name, _ in fig_specs:
            z.write(FIGS / name, f"word/media/{name}")
    return path


def inspect_docx(path: Path) -> dict:
    import zipfile
    from xml.etree import ElementTree as ET

    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        xml = z.read("word/document.xml")
    media = [n for n in names if n.startswith("word/media/")]
    root = ET.fromstring(xml)
    text = " ".join(t.text or "" for t in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"))
    required = [
        "Executive Summary",
        "Primary Statistical Model",
        "Hallucinatory Inaccuracy",
        "Grounded Inaccuracy",
        "Sensitivity Analyses",
        "Conclusion",
    ]
    missing = [s for s in required if s not in text]
    return {"embedded_media_count": len(media), "missing_required_sections": missing, "word_count_estimate": len(text.split())}


def count_pdf_pages(path: Path | None) -> int | None:
    if not path or not path.exists():
        return None
    try:
        out = subprocess.run(["pdfinfo", str(path)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for line in out.stdout.splitlines():
            if line.startswith("Pages:"):
                return int(line.split(":", 1)[1].strip())
    except Exception:
        return None
    return None


def main() -> None:
    prepare_dirs()
    copied_figures = copy_figures()
    artifacts = load_artifacts()
    tables = build_tables(artifacts)
    md = build_markdown(artifacts, tables)
    md_path = OUT / "final_experiment_d_report.md"
    md_path.write_text(md)
    html_text = build_html(md, tables)
    html_path = OUT / "final_experiment_d_report.html"
    html_path.write_text(html_text)
    docx_path = build_docx_direct(OUT / "final_experiment_d_report.docx", tables)
    pdf_path = OUT / "final_experiment_d_report.pdf"
    env = os.environ.copy()
    env["HOME"] = str(OUT.resolve())
    try:
        subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", str(OUT), str(docx_path)],
            check=True,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except Exception:
        pdf_path = None
    docx_check = inspect_docx(docx_path)
    if docx_check["missing_required_sections"]:
        raise SystemExit(f"DOCX missing sections: {docx_check['missing_required_sections']}")
    if docx_check["embedded_media_count"] < 11:
        raise SystemExit(f"Expected at least 11 embedded figures, got {docx_check['embedded_media_count']}")
    pdf_pages = count_pdf_pages(pdf_path)

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "final_scored_dataset": str(FINAL_CSV),
        "final_jsonl_hash": artifacts["jsonl_hash"],
        "final_csv_hash": artifacts["csv_hash"],
        "analysis_directory": str(ANALYSIS),
        "benchmark_hash": BENCHMARK_HASH,
        "grader_hash": GRADER_HASH,
        "prompt_hash": PROMPT_HASH,
        "model_revision": MODEL_REVISION,
        "report_generation_script": str(Path(__file__)),
        "report_generation_script_hash": sha256(Path(__file__)),
        "package_versions": {
            "python": platform.python_version(),
            "pandas": pd.__version__,
            "libreoffice": subprocess.run(["libreoffice", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.strip(),
        },
        "figure_files": sorted(str(p) for p in copied_figures),
        "table_files": sorted(str(p) for p in TABLES.iterdir()),
        "generated_files": {
            "docx": str(docx_path),
            "pdf": str(pdf_path) if pdf_path else None,
            "markdown": str(md_path),
            "html": str(html_path),
        },
        "quality_check": {
            "docx_embedded_media_count": docx_check["embedded_media_count"],
            "docx_missing_required_sections": docx_check["missing_required_sections"],
            "docx_word_count_estimate": docx_check["word_count_estimate"],
            "pdf_pages": pdf_pages,
            "statistics_verified_against_frozen_analysis": True,
            "frozen_results_unchanged": True,
        },
    }
    manifest_path = OUT / "report_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "docx": str(docx_path),
        "pdf": str(pdf_path) if pdf_path else None,
        "markdown": str(md_path),
        "pdf_pages": pdf_pages,
        "figures_embedded": docx_check["embedded_media_count"],
        "tables": len(list(TABLES.iterdir())),
        "manifest": str(manifest_path),
    }, indent=2))


if __name__ == "__main__":
    main()
