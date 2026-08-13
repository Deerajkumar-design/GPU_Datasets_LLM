#!/usr/bin/env python3
from __future__ import annotations

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
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", "/home/srinija/GPU_Datasets/.matplotlib-cache")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image


OUT = Path("data/final_report_cross_model_v1")
FIGS = OUT / "figures"
TABLES = OUT / "tables"

D_ANALYSIS = Path("data/analysis_experiment_d_final_v1")
D_GRADING = Path("data/grading_experiment_d_final_v1")
E_ANALYSIS = Path("data/analysis_experiment_e_qwen35_2b_v1")
E_GRADING = Path("data/grading_experiment_e_qwen35_2b_v1")
E_INFERENCE = Path("data/inference_qwen35_2b_500f_6ctx_v1")

CONTEXTS = ["4K", "8K", "16K", "32K", "64K", "82K"]
BENCHMARK_HASH = "dc2c4194dedb090198e6883735257908ce274bebc8611b40d958dbd026aa1fe6"
GRADER_HASH = "d9282a0ccc50daba3bfd232c058dfbab63a5c19a7323d585a7c2236b3a6c4ba8"
QWEN_REVISION = "15852e8c16360a2fea060d615a32b45270f8a8fc"
QWEN_PROMPT_HASH = "8b1f0e7700df4fe1"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def pct(x: float, digits: int = 1) -> str:
    return f"{100 * float(x):.{digits}f}%"


def fnum(x: float, digits: int = 3) -> str:
    return f"{float(x):.{digits}f}"


def pval(p: float) -> str:
    p = float(p)
    if p < 1e-4:
        return f"{p:.2e}"
    return f"{p:.5f}".rstrip("0").rstrip(".")


def ci(lo: float, hi: float) -> str:
    return f"[{float(lo):.3f}, {float(hi):.3f}]"


def prepare() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    lohome = OUT / ".lohome"
    if lohome.exists():
        shutil.rmtree(lohome)
    stale = OUT / "final_cross_model_report.odt"
    if stale.exists():
        stale.unlink()


def load_sources() -> dict[str, Any]:
    d_primary = pd.read_csv(D_ANALYSIS / "primary_results.csv")
    e_primary = pd.read_csv(E_ANALYSIS / "overall_context_results.csv")
    d_gee = json.loads((D_ANALYSIS / "gee_trend_results.json").read_text())["inaccurate"]
    e_gee = pd.read_csv(E_ANALYSIS / "gee_results.csv")
    e_gee = e_gee[e_gee["outcome"] == "inaccurate"].iloc[0].to_dict()
    interaction = pd.read_csv(E_ANALYSIS / "cross_model_interaction_models.csv")
    interaction = interaction[interaction["outcome"] == "inaccurate"].iloc[0].to_dict()
    return {
        "d_primary": d_primary,
        "e_primary": e_primary,
        "d_gee": d_gee,
        "e_gee": e_gee,
        "interaction": interaction,
        "d_paired": pd.read_csv(D_ANALYSIS / "paired_tests.csv"),
        "e_paired": pd.read_csv(E_ANALYSIS / "paired_tests.csv"),
        "d_qtype": pd.read_csv(D_ANALYSIS / "question_type_results.csv"),
        "e_qtype": pd.read_csv(E_ANALYSIS / "question_type_results.csv"),
        "d_domain": pd.read_csv(D_ANALYSIS / "domain_results.csv"),
        "e_domain": pd.read_csv(E_ANALYSIS / "domain_results.csv"),
        "d_error": pd.read_csv(D_ANALYSIS / "error_type_by_context.csv"),
        "e_error": pd.read_csv(E_ANALYSIS / "detailed_error_type_results.csv"),
        "d_latency": pd.read_csv(D_ANALYSIS / "latency_analysis.csv"),
        "e_latency": pd.read_csv(E_ANALYSIS / "latency_statistics.csv"),
        "qwen_env": json.loads((E_INFERENCE / "environment.json").read_text()),
        "qwen_integrity": json.loads((E_INFERENCE / "integrity_report.json").read_text()),
        "qwen_grading": json.loads((E_GRADING / "grading_integrity_report.json").read_text()),
        "d_integrity": json.loads((D_GRADING / "final_integrity_report.json").read_text()),
    }


def save_csv(df: pd.DataFrame, name: str) -> None:
    df.to_csv(TABLES / f"{name}.csv", index=False)


def build_tables(src: dict[str, Any]) -> dict[str, pd.DataFrame]:
    d = src["d_primary"].set_index("context").loc[CONTEXTS].reset_index()
    e = src["e_primary"].set_index("context").loc[CONTEXTS].reset_index()

    primary = pd.DataFrame({
        "Context": CONTEXTS,
        "Llama Accurate": [pct(x) for x in d["correct_rate"]],
        "Llama Inaccurate": [pct(x) for x in d["inaccuracy_rate"]],
        "Llama Runtime Failures": d["runtime_failures"].astype(int),
        "Qwen Mean Tokens": [f"{x:,.0f}" for x in e["mean_input_tokens"]],
        "Qwen Accurate": [pct(x) for x in e["correct_rate"]],
        "Qwen Inaccurate": [pct(x) for x in e["inaccuracy_rate"]],
        "Qwen Mean Latency": [f"{x:.2f} s" for x in e["mean_latency"]],
    })

    gee = pd.DataFrame([
        {
            "Model": "Llama-3.2-3B-Instruct",
            "Coefficient": fnum(src["d_gee"]["coefficient"]),
            "SE": fnum(src["d_gee"]["robust_se"]),
            "OR per 2x rendered context": fnum(src["d_gee"]["odds_ratio_per_2x_context"]),
            "95% CI": ci(src["d_gee"]["odds_ratio_ci_low"], src["d_gee"]["odds_ratio_ci_high"]),
            "p-value": pval(src["d_gee"]["p_value"]),
            "N": int(src["d_gee"]["n_observations"]),
        },
        {
            "Model": "Qwen3.5-2B",
            "Coefficient": fnum(src["e_gee"]["coefficient"]),
            "SE": fnum(src["e_gee"]["robust_se"]),
            "OR per 2x rendered context": fnum(src["e_gee"]["odds_ratio_per_2x_context"]),
            "95% CI": ci(src["e_gee"]["odds_ratio_ci_low"], src["e_gee"]["odds_ratio_ci_high"]),
            "p-value": pval(src["e_gee"]["p_value"]),
            "N": int(src["e_gee"]["n_observations"]),
        },
    ])

    interaction = pd.DataFrame([{
        "Outcome": "Inaccurate",
        "Interaction": "log2(rendered_input_tokens) x model",
        "Qwen-vs-Llama slope OR ratio": fnum(src["interaction"]["interaction_or_ratio"]),
        "95% CI": ci(src["interaction"]["ci_low"], src["interaction"]["ci_high"]),
        "p-value": pval(src["interaction"]["p_value"]),
        "Interpretation": "No statistically significant difference detected",
    }])

    paired_rows: list[dict[str, Any]] = []
    for model, df in [("Llama", src["d_paired"]), ("Qwen", src["e_paired"])]:
        sub = df[df["outcome"] == "inaccurate"].copy()
        for _, r in sub.iterrows():
            paired_rows.append({
                "Model": model,
                "Comparison": r["comparison"].replace("_", " "),
                "Paired N": int(r["paired_n"]),
                "4K Inaccurate": pct(r["event_rate_4K"]),
                "Higher Context Inaccurate": pct(r["event_rate_comparison"]),
                "Delta": f"{float(r['absolute_percentage_point_difference']):.1f} pp",
                "Discordant 4K=0,Higher=1": int(r["discordant_4K0_cmp1"]),
                "Discordant 4K=1,Higher=0": int(r["discordant_4K1_cmp0"]),
                "Raw p": pval(r["raw_p_value"]),
                "Holm p": pval(r["holm_adjusted_p_value"]),
            })
    paired = pd.DataFrame(paired_rows)

    qtype = summarize_subgroups(src["d_qtype"], src["e_qtype"], "question_type", "Question Type")
    domain = summarize_subgroups(src["d_domain"], src["e_domain"], "domain", "Domain")

    latency = pd.DataFrame({
        "Context": CONTEXTS,
        "Llama Mean Tokens": [f"{x:,.0f}" for x in d["mean_input_tokens"]],
        "Llama Mean Latency": [f"{x:.2f} s" for x in src["d_latency"].set_index("context").loc[CONTEXTS]["mean_latency"]],
        "Qwen Mean Tokens": [f"{x:,.0f}" for x in e["mean_input_tokens"]],
        "Qwen Mean Latency": [f"{x:.2f} s" for x in e["mean_latency"]],
    })

    d_err = src["d_error"].copy()
    e_err = src["e_error"].copy()
    error_rows = []
    for et in sorted(set(d_err["error_type"]) | set(e_err["error_type"])):
        d4 = int(d_err[(d_err["context"] == "4K") & (d_err["error_type"] == et)]["count"].sum())
        d82 = int(d_err[(d_err["context"] == "82K") & (d_err["error_type"] == et)]["count"].sum())
        e4 = int(e_err[(e_err["context"] == "4K") & (e_err["error_type"] == et)]["count"].sum())
        e82 = int(e_err[(e_err["context"] == "82K") & (e_err["error_type"] == et)]["count"].sum())
        error_rows.append({
            "Error Type": et,
            "Llama 4K": d4,
            "Llama 82K": d82,
            "Llama Delta": d82 - d4,
            "Qwen 4K": e4,
            "Qwen 82K": e82,
            "Qwen Delta": e82 - e4,
        })
    errors = pd.DataFrame(error_rows)

    tables = {
        "primary_binary_results": primary,
        "gee_primary": gee,
        "interaction": interaction,
        "paired_mcnemar": paired,
        "question_type_summary": qtype,
        "domain_summary": domain,
        "latency": latency,
        "secondary_error_diagnostics": errors,
    }
    for name, df in tables.items():
        save_csv(df, name)
    return tables


def summarize_subgroups(d_df: pd.DataFrame, e_df: pd.DataFrame, group_col: str, label: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for value in sorted(set(d_df[group_col]) | set(e_df[group_col])):
        d = d_df[d_df[group_col] == value].set_index("context")
        e = e_df[e_df[group_col] == value].set_index("context")
        rows.append({
            label: value,
            "Llama 4K Accurate": pct(d.loc["4K", "correct_rate"]),
            "Llama 82K Accurate": pct(d.loc["82K", "correct_rate"]),
            "Llama 4K Inaccurate": pct(d.loc["4K", "inaccuracy_rate"]),
            "Llama 82K Inaccurate": pct(d.loc["82K", "inaccuracy_rate"]),
            "Qwen 4K Accurate": pct(e.loc["4K", "correct_rate"]),
            "Qwen 82K Accurate": pct(e.loc["82K", "correct_rate"]),
            "Qwen 4K Inaccurate": pct(e.loc["4K", "inaccuracy_rate"]),
            "Qwen 82K Inaccurate": pct(e.loc["82K", "inaccuracy_rate"]),
        })
    return pd.DataFrame(rows)


def make_figures(src: dict[str, Any]) -> list[dict[str, str]]:
    plt.rcParams.update({
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.labelsize": 10,
        "legend.fontsize": 9,
        "figure.dpi": 160,
        "savefig.dpi": 300,
    })
    colors = {"Llama": "#2f5f8f", "Qwen": "#b65d32"}
    d = src["d_primary"].set_index("context").loc[CONTEXTS].reset_index()
    e = src["e_primary"].set_index("context").loc[CONTEXTS].reset_index()
    x = np.arange(len(CONTEXTS))
    figs: list[dict[str, str]] = []

    def save(name: str, title: str, caption: str) -> None:
        plt.tight_layout()
        png = FIGS / f"{name}.png"
        pdf = FIGS / f"{name}.pdf"
        plt.savefig(png)
        plt.savefig(pdf)
        plt.close()
        figs.append({"name": name, "title": title, "caption": caption, "png": str(png), "pdf": str(pdf)})

    plt.figure(figsize=(7.4, 4.6))
    plt.errorbar(x, d["correct_rate"], yerr=[d["correct_rate"] - d["correct_ci_low"], d["correct_ci_high"] - d["correct_rate"]], marker="o", linewidth=2, capsize=3, label="Llama", color=colors["Llama"])
    plt.errorbar(x, e["correct_rate"], yerr=[e["correct_rate"] - e["correct_ci_low"], e["correct_ci_high"] - e["correct_rate"]], marker="s", linewidth=2, capsize=3, label="Qwen", color=colors["Qwen"])
    plt.xticks(x, CONTEXTS)
    plt.ylim(0.2, 0.65)
    plt.ylabel("Accurate response rate")
    plt.xlabel("Matched context condition")
    plt.title("Factual accuracy decreases with longer context")
    plt.grid(axis="y", alpha=0.25)
    plt.legend(frameon=False)
    save("figure_01_accuracy_vs_context", "Factual accuracy vs context", "Accurate response rate by matched context condition for Llama and Qwen. Error bars show binomial confidence intervals over successful generations.")

    plt.figure(figsize=(7.4, 4.6))
    plt.errorbar(x, d["inaccuracy_rate"], yerr=[d["inaccuracy_rate"] - d["inaccuracy_ci_low"], d["inaccuracy_ci_high"] - d["inaccuracy_rate"]], marker="o", linewidth=2, capsize=3, label="Llama", color=colors["Llama"])
    plt.errorbar(x, e["inaccuracy_rate"], yerr=[e["inaccuracy_rate"] - e["inaccuracy_ci_low"], e["inaccuracy_ci_high"] - e["inaccuracy_rate"]], marker="s", linewidth=2, capsize=3, label="Qwen", color=colors["Qwen"])
    plt.xticks(x, CONTEXTS)
    plt.ylim(0.35, 0.8)
    plt.ylabel("Inaccurate response rate")
    plt.xlabel("Matched context condition")
    plt.title("Factual inaccuracy increases with longer context")
    plt.grid(axis="y", alpha=0.25)
    plt.legend(frameon=False)
    save("figure_02_inaccuracy_vs_context", "Factual inaccuracy vs context", "Inaccurate response rate by matched context condition for both models. Runtime failures are excluded from factual denominators.")

    gee_vals = [
        src["d_gee"]["odds_ratio_per_2x_context"],
        src["e_gee"]["odds_ratio_per_2x_context"],
    ]
    gee_low = [src["d_gee"]["odds_ratio_ci_low"], src["e_gee"]["odds_ratio_ci_low"]]
    gee_high = [src["d_gee"]["odds_ratio_ci_high"], src["e_gee"]["odds_ratio_ci_high"]]
    labels = ["Llama", "Qwen"]
    y = np.arange(2)
    plt.figure(figsize=(7.0, 3.4))
    plt.errorbar(gee_vals, y, xerr=[np.array(gee_vals) - np.array(gee_low), np.array(gee_high) - np.array(gee_vals)], fmt="o", capsize=4, color="#333333")
    plt.axvline(1, color="#777777", linestyle="--", linewidth=1)
    plt.yticks(y, labels)
    plt.xlabel("Odds ratio per true 2x rendered-token increase")
    plt.title("Model-specific degradation slopes")
    plt.grid(axis="x", alpha=0.25)
    save("figure_03_odds_ratios", "Model-specific odds ratios", "Primary GEE odds ratios for the binary Inaccurate outcome. Values greater than 1 indicate increasing odds of inaccuracy with longer rendered context.")

    plt.figure(figsize=(7.4, 4.6))
    plt.plot(np.log2(d["mean_input_tokens"]), d["inaccuracy_rate"], "o-", linewidth=2, label="Llama", color=colors["Llama"])
    plt.plot(np.log2(e["mean_input_tokens"]), e["inaccuracy_rate"], "s-", linewidth=2, label="Qwen", color=colors["Qwen"])
    plt.xlabel("log2(actual rendered input tokens)")
    plt.ylabel("Inaccurate response rate")
    plt.title("Token-count trend comparison")
    plt.grid(alpha=0.25)
    plt.legend(frameon=False)
    save("figure_04_cross_model_trend", "Cross-model trend comparison", "Inaccuracy plotted against each model's actual rendered token counts. The condition labels are matched semantically, while the trend predictor uses actual tokenizer-specific counts.")

    qtype = pd.concat([
        src["d_qtype"].assign(model="Llama"),
        src["e_qtype"].assign(model="Qwen"),
    ])
    qtype_82 = qtype[qtype["context"].isin(["4K", "82K"])].copy()
    labels_q = sorted(qtype_82["question_type"].unique())
    width = 0.18
    xpos = np.arange(len(labels_q))
    plt.figure(figsize=(9.2, 4.8))
    for i, (model, ctx, color, hatch) in enumerate([
        ("Llama", "4K", colors["Llama"], ""),
        ("Llama", "82K", colors["Llama"], "//"),
        ("Qwen", "4K", colors["Qwen"], ""),
        ("Qwen", "82K", colors["Qwen"], "//"),
    ]):
        vals = [qtype_82[(qtype_82["model"] == model) & (qtype_82["context"] == ctx) & (qtype_82["question_type"] == q)]["inaccuracy_rate"].iloc[0] for q in labels_q]
        plt.bar(xpos + (i - 1.5) * width, vals, width, label=f"{model} {ctx}", color=color, hatch=hatch, alpha=0.88)
    plt.xticks(xpos, labels_q, rotation=25, ha="right")
    plt.ylabel("Inaccurate response rate")
    plt.title("Exploratory question-type inaccuracy")
    plt.ylim(0, 1.05)
    plt.legend(ncol=2, frameon=False)
    plt.grid(axis="y", alpha=0.2)
    save("figure_05_question_type", "Question-type accuracy/inaccuracy", "Exploratory inaccuracy rates by question type at the shortest and longest context conditions.")

    dom = pd.concat([
        src["d_domain"].assign(model="Llama"),
        src["e_domain"].assign(model="Qwen"),
    ])
    dom_82 = dom[dom["context"].isin(["4K", "82K"])].copy()
    labels_d = sorted(dom_82["domain"].unique())
    xpos = np.arange(len(labels_d))
    plt.figure(figsize=(8.2, 4.6))
    for i, (model, ctx, color, hatch) in enumerate([
        ("Llama", "4K", colors["Llama"], ""),
        ("Llama", "82K", colors["Llama"], "//"),
        ("Qwen", "4K", colors["Qwen"], ""),
        ("Qwen", "82K", colors["Qwen"], "//"),
    ]):
        vals = [dom_82[(dom_82["model"] == model) & (dom_82["context"] == ctx) & (dom_82["domain"] == q)]["inaccuracy_rate"].iloc[0] for q in labels_d]
        plt.bar(xpos + (i - 1.5) * width, vals, width, label=f"{model} {ctx}", color=color, hatch=hatch, alpha=0.88)
    plt.xticks(xpos, labels_d, rotation=20, ha="right")
    plt.ylabel("Inaccurate response rate")
    plt.title("Exploratory domain inaccuracy")
    plt.ylim(0, 1.05)
    plt.legend(ncol=2, frameon=False)
    plt.grid(axis="y", alpha=0.2)
    save("figure_06_domain", "Domain accuracy/inaccuracy", "Exploratory inaccuracy rates by source domain at the shortest and longest context conditions.")

    plt.figure(figsize=(7.4, 4.6))
    plt.plot(d["mean_input_tokens"], src["d_latency"].set_index("context").loc[CONTEXTS]["mean_latency"], "o-", linewidth=2, label="Llama", color=colors["Llama"])
    plt.plot(e["mean_input_tokens"], e["mean_latency"], "s-", linewidth=2, label="Qwen", color=colors["Qwen"])
    plt.xscale("log", base=2)
    plt.xlabel("Actual rendered input tokens (log2 scale)")
    plt.ylabel("Mean latency (seconds)")
    plt.title("Latency increases with rendered context")
    plt.grid(alpha=0.25)
    plt.legend(frameon=False)
    save("figure_07_latency", "Latency vs rendered context", "Mean generation latency by actual rendered token count. Architecture and implementation differ between models, so latency is descriptive.")

    return figs


def html_table(df: pd.DataFrame, caption: str, number: int, small: bool = False) -> str:
    cls = " small-table" if small else ""
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    rows = []
    for _, row in df.iterrows():
        rows.append("<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in row.tolist()) + "</tr>")
    return f'<div class="table-block{cls}"><p class="caption">Table {number}. {html.escape(caption)}</p><table><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


def figure_html(fig: dict[str, str], number: int) -> str:
    rel = Path(fig["png"]).relative_to(OUT).as_posix()
    return f'<figure><img src="{html.escape(rel)}"><figcaption>Figure {number}. {html.escape(fig["caption"])}</figcaption></figure>'


def build_html(src: dict[str, Any], tables: dict[str, pd.DataFrame], figs: list[dict[str, str]]) -> str:
    d_gee = src["d_gee"]
    e_gee = src["e_gee"]
    inter = src["interaction"]
    toc = [
        "Abstract", "Executive Summary", "Research Question and Motivation", "Experimental Design",
        "Dataset and Question-Family Construction", "Context-Length Conditions", "Models",
        "Inference Configuration and Reproducibility", "Factual Accuracy Definition", "Statistical Methodology",
        "Llama Results", "Qwen Results", "Cross-Model Comparison", "Model x Context Interaction",
        "Paired Context Comparisons", "Question-Type Analysis", "Domain Analysis", "Latency and Runtime Behavior",
        "Secondary Error Diagnostics", "Discussion", "Limitations", "Conclusion", "Reproducibility / Artifact Manifest", "Appendix",
    ]
    style = """
    <style>
      @page { size: letter; margin: 0.7in; }
      body { font-family: Aptos, Calibri, Arial, sans-serif; color: #172033; font-size: 10.2pt; line-height: 1.35; }
      .title-page { text-align: center; margin-top: 2.0in; page-break-after: always; }
      .title { font-size: 25pt; font-weight: 700; color: #163b63; margin-bottom: 0.25in; }
      .subtitle { font-size: 14pt; color: #4b5563; margin-bottom: 0.55in; }
      .meta { font-size: 10pt; line-height: 1.6; }
      h1 { font-size: 17pt; color: #163b63; border-bottom: 1px solid #afbed0; padding-bottom: 3px; page-break-before: always; }
      h2 { font-size: 13pt; color: #244b73; margin-top: 14px; }
      h3 { font-size: 11.5pt; color: #244b73; margin-top: 12px; }
      p { margin: 0 0 8px 0; }
      .toc { page-break-after: always; }
      .toc li { margin-bottom: 4px; }
      .callout { background: #edf5ff; border-left: 4px solid #2f5f8f; padding: 10px 12px; margin: 9px 0 13px 0; }
      table { border-collapse: collapse; width: 100%; margin: 5px 0 13px 0; font-size: 8.1pt; }
      .small-table table { font-size: 7.2pt; }
      th { background: #e8eef6; color: #163b63; border: 1px solid #8fa7c0; padding: 4px; font-weight: 700; }
      td { border: 1px solid #c8d2dd; padding: 4px; vertical-align: top; }
      tr:nth-child(even) td { background: #f8fafc; }
      .caption, figcaption { font-size: 8.7pt; color: #38465a; font-weight: 600; margin: 5px 0; }
      figure { text-align: center; page-break-inside: avoid; margin: 12px 0 18px 0; }
      figure img { max-width: 6.7in; }
      code { font-family: Consolas, 'Courier New', monospace; background: #f3f4f6; padding: 1px 3px; }
      ul { margin-top: 4px; }
      .muted { color: #4b5563; }
    </style>
    """
    table_no = 1
    fig_no = 1
    parts = [
        "<!doctype html><html><head><meta charset='utf-8'>", style, "</head><body>",
        "<section class='title-page'>",
        "<div class='title'>Long-Context Factual Reliability Across Model Families</div>",
        "<div class='subtitle'>A binary Accurate/Inaccurate cross-model replication of Experiment D and Experiment E</div>",
        f"<div class='meta'><b>Final Cross-Model Report</b><br>Generated: {date.today().isoformat()}<br>Benchmark hash: <code>{BENCHMARK_HASH}</code><br>Primary outcome: Accurate vs Inaccurate</div>",
        "</section>",
        "<section class='toc'><h1>Table of Contents</h1><ol>" + "".join(f"<li>{html.escape(x)}</li>" for x in toc) + "</ol></section>",
        "<h1>Abstract</h1>",
        "<p>This report summarizes two completed long-context factual-reliability experiments using a shared frozen benchmark. The primary scientific outcome is binary: Accurate versus Inaccurate. CORRECT responses are Accurate; every other successfully generated factual-task outcome is Inaccurate. Runtime failures are reported separately and are not counted as factual inaccuracies.</p>",
        "<p>Increasing context length substantially reduced factual accuracy in both Llama-3.2-3B-Instruct and Qwen3.5-2B. Llama inaccuracy increased from 49.6% at 4K to 70.7% at 82K; Qwen inaccuracy increased from 45.2% to 71.2%. GEE logistic models clustered by question family showed significantly increasing odds of factual inaccuracy per true doubling of rendered input tokens for both models. The model-by-context interaction was not statistically significant for overall inaccuracy, indicating no detectable difference in the overall degradation slope between the two model families in this benchmark.</p>",
        "<h1>Executive Summary</h1>",
        "<div class='callout'><p><b>Central finding.</b> Factual accuracy decreases substantially as context length increases, and this effect replicated across two different model families. The shortest condition produced 49.6% inaccurate Llama responses and 45.2% inaccurate Qwen responses. The longest condition produced 70.7% inaccurate Llama responses and 71.2% inaccurate Qwen responses.</p></div>",
        f"<p>Llama's primary GEE odds ratio was <b>{d_gee['odds_ratio_per_2x_context']:.3f}</b> per true 2x increase in rendered context, 95% CI <b>{ci(d_gee['odds_ratio_ci_low'], d_gee['odds_ratio_ci_high'])}</b>, p = <b>{pval(d_gee['p_value'])}</b>. Qwen's primary GEE odds ratio was <b>{e_gee['odds_ratio_per_2x_context']:.3f}</b>, 95% CI <b>{ci(e_gee['odds_ratio_ci_low'], e_gee['odds_ratio_ci_high'])}</b>, p = <b>{pval(e_gee['p_value'])}</b>.</p>",
        f"<p>The overall model x context interaction was not significant: Qwen-vs-Llama slope OR ratio <b>{inter['interaction_or_ratio']:.3f}</b>, 95% CI <b>{ci(inter['ci_low'], inter['ci_high'])}</b>, p = <b>{pval(inter['p_value'])}</b>. This does not prove identical slopes; it means the experiment did not detect a statistically significant difference in overall degradation rates.</p>",
        "<h1>Research Question and Motivation</h1>",
        "<p>The central research question is how increasing context length affects factual reliability when an LLM must answer factual questions from controlled but information-rich context. The cross-model extension asks whether the Experiment D result in Llama behaviorally replicates in a different model family, Qwen.</p>",
        "<p>This report intentionally frames the main result using the binary factual outcome Accurate versus Inaccurate. The detailed hallucination/grounding taxonomy is retained only as secondary diagnostic information.</p>",
        "<h1>Experimental Design</h1>",
        "<p>Both experiments used the same frozen benchmark information and semantic task. Llama used its native Llama chat template; Qwen used its native Qwen chat template in non-thinking mode. The two models therefore did not receive byte-identical rendered prompts, but they received matched benchmark facts, questions, context construction, answer target, evidence ordering, and output contract.</p>",
        "<h1>Dataset and Question-Family Construction</h1>",
        "<p>The benchmark contains 500 question families and six context conditions, producing 3,000 attempted instances per model. The domains are SEC, FDA/Drugs@FDA, ClinicalTrials.gov, and FRED/ALFRED, with 125 families from each domain. There are 400 answerable and 100 unanswerable families.</p>",
        html_table(pd.DataFrame({
            "Question Type": ["DIRECT_RETRIEVAL", "RETRIEVAL_CALCULATION", "TEMPORAL_VERSION", "ENTITY_UNIT_BINDING", "UNANSWERABLE"],
            "Families": [100, 150, 55, 95, 100],
            "Purpose": ["Retrieve a directly stated fact", "Retrieve values and compute a deterministic result", "Bind answer to the correct period/version", "Bind entity/unit/product/series correctly", "Abstain when required evidence is absent"],
        }), "Frozen benchmark question-type distribution.", table_no),
    ]
    table_no += 1
    parts += [
        "<h1>Context-Length Conditions</h1>",
        "<p>The six benchmark conditions are 4K, 8K, 16K, 32K, 64K, and 82K. These labels describe matched benchmark conditions, not guaranteed tokenizer-identical lengths. Statistical trend models use each model's actual <code>log2(rendered_input_tokens)</code>, so +1 corresponds to a true doubling of rendered tokens for that model.</p>",
        "<h1>Models</h1>",
        "<h2>Llama-3.2-3B-Instruct</h2><p>Experiment D used <code>meta-llama/Llama-3.2-3B-Instruct</code>. It produced 2,998 successful generations out of 3,000 attempts, with two CUDA OOM runtime failures at 82K.</p>",
        f"<h2>Qwen3.5-2B</h2><p>Experiment E used <code>Qwen/Qwen3.5-2B</code> at revision <code>{QWEN_REVISION}</code>. It produced 3,000 successful generations out of 3,000 attempts, with zero instance-level runtime failures.</p>",
        "<h1>Inference Configuration and Reproducibility</h1>",
        f"<p>Qwen was run with Transformers 5.14.1, PyTorch 2.5.1+cu121, CUDA runtime 12.1, NVIDIA GeForce RTX 4090, driver 550.163.01, <code>Qwen2Tokenizer</code>, <code>Qwen3_5ForCausalLM</code>, BF16, DynamicCache, SDPA, greedy decoding, and no thinking mode. The Qwen prompt version was <code>qwen35_chat_v1</code>, prompt hash <code>{QWEN_PROMPT_HASH}</code>. The frozen benchmark hash was <code>{BENCHMARK_HASH}</code>, and the frozen grader hash was <code>{GRADER_HASH}</code>.</p>",
        "<h1>Factual Accuracy Definition</h1>",
        "<p><b>Accurate</b> means the deterministic grader labeled the successful response CORRECT. <b>Inaccurate</b> means any other successfully generated factual-task outcome. Runtime failures are separate operational failures and are not factual inaccuracies.</p>",
        "<h1>Statistical Methodology</h1>",
        "<p>The primary model for each experiment was GEE logistic regression clustered by <code>question_family_id</code>. The outcome was <code>INACCURATE</code>. The predictor was <code>log2(rendered_input_tokens)</code>, so a one-unit increase represents a true doubling of rendered input tokens. A combined long-form model tested the interaction <code>log2(rendered_input_tokens) x model</code>.</p>",
        html_table(tables["gee_primary"], "Primary GEE logistic models for overall factual inaccuracy.", table_no),
    ]
    table_no += 1
    parts += [
        "<h1>Llama Results</h1>",
        "<p>Llama factual inaccuracy increased from 49.6% at 4K to 70.7% at 82K. The primary GEE OR was 1.232 per doubling of rendered context, corresponding to approximately a 23.2% increase in the odds of factual inaccuracy.</p>",
        "<h1>Qwen Results</h1>",
        "<p>Qwen factual inaccuracy increased from 45.2% at 4K to 71.2% at 82K. The primary GEE OR was 1.276 per doubling of rendered Qwen context, corresponding to approximately a 27.6% increase in the odds of factual inaccuracy.</p>",
        html_table(tables["primary_binary_results"], "Binary Accurate/Inaccurate results by context.", table_no),
    ]
    table_no += 1
    parts += [
        figure_html(figs[0], fig_no),
    ]
    fig_no += 1
    parts += [figure_html(figs[1], fig_no)]
    fig_no += 1
    parts += [
        "<h1>Cross-Model Comparison</h1>",
        "<p>Increasing context length substantially reduced factual accuracy in both Llama-3.2-3B-Instruct and Qwen3.5-2B. The models differ in family, tokenizer, architecture, training, native chat template, and actual rendered token counts, so the comparison is behavioral rather than architectural.</p>",
        figure_html(figs[2], fig_no),
    ]
    fig_no += 1
    parts += [
        "<h1>Model x Context Interaction</h1>",
        "<p>The most important cross-model test is the context-by-model interaction. The interaction was not statistically significant for overall factual inaccuracy. Therefore, although Qwen's point estimate was slightly larger, this experiment does not provide evidence that the overall context-length degradation slope differs between the two models.</p>",
        html_table(tables["interaction"], "Combined model interaction test for overall factual inaccuracy.", table_no),
        figure_html(figs[3], fig_no),
    ]
    table_no += 1
    fig_no += 1
    parts += [
        "<h1>Paired Context Comparisons</h1>",
        "<p>Paired McNemar tests compared 4K against each higher context condition within the same question families. For both Llama and Qwen, 4K versus every higher context showed significant increases in overall inaccuracy after Holm correction.</p>",
        html_table(tables["paired_mcnemar"], "Paired McNemar tests for overall inaccuracy.", table_no, small=True),
    ]
    table_no += 1
    parts += [
        "<h1>Question-Type Analysis</h1>",
        "<p>Question-type analyses are exploratory. Direct retrieval, temporal/version, and entity/unit binding showed clear degradation in one or both models; retrieval/calculation had high baseline error rates; unanswerable behavior differed between models.</p>",
        html_table(tables["question_type_summary"], "Exploratory question-type summary, shortest versus longest context.", table_no, small=True),
        figure_html(figs[4], fig_no),
    ]
    table_no += 1
    fig_no += 1
    parts += [
        "<h1>Domain Analysis</h1>",
        "<p>Domain analyses are exploratory. Both models showed higher inaccuracy at 82K than 4K across SEC, FDA, ClinicalTrials, and FRED/ALFRED, with the magnitude differing by model and domain.</p>",
        html_table(tables["domain_summary"], "Exploratory domain summary, shortest versus longest context.", table_no, small=True),
        figure_html(figs[5], fig_no),
    ]
    table_no += 1
    fig_no += 1
    parts += [
        "<h1>Latency and Runtime Behavior</h1>",
        "<p>Llama had 3,000 attempted generations, 2,998 successes, and two CUDA OOM failures at 82K. Qwen had 3,000 attempted generations, 3,000 successes, and zero instance-level runtime failures. Qwen full inference had process-level segmentation faults after flushed rows at 943, 1831, 1846, and 2952; the run resumed with identical pinned settings and skipped completed IDs. These process interruptions are not counted as factual failures. Transformers also fell back from Qwen's optional fast path to the torch implementation because optional packages were unavailable.</p>",
        html_table(tables["latency"], "Latency and rendered-token summaries.", table_no),
        figure_html(figs[6], fig_no),
    ]
    table_no += 1
    fig_no += 1
    parts += [
        "<h1>Secondary Error Diagnostics</h1>",
        "<p>The deterministic grader also categorized inaccuracies into detailed failure types. These analyses are secondary diagnostics and do not dominate the primary scientific framing. They suggest that the broad Accurate/Inaccurate degradation can arise from different mechanisms across models.</p>",
        html_table(tables["secondary_error_diagnostics"], "Secondary detailed error taxonomy, 4K to 82K changes.", table_no, small=True),
    ]
    table_no += 1
    parts += [
        "<h1>Discussion</h1>",
        "<p>Both models show strong factual-reliability degradation with longer context, and the degradation is statistically strong within each model. The overall context-length slopes are not significantly different between Llama and Qwen, so the observed degradation replicated behaviorally across two model families. This study does not identify the internal architectural cause.</p>",
        "<p>Tokenization and prompt-template differences prevent claiming that the two models saw byte-identical rendered prompts. Nevertheless, they received the same frozen benchmark information and semantic task under their native templates. A third model family would be a natural next step for assessing broader generalizability.</p>",
        "<h1>Limitations</h1>",
        "<ul><li>Only two model families were tested.</li><li>The tested models are relatively small, approximately 2B-3B scale.</li><li>The benchmark is one controlled construction over four source domains.</li><li>Inference used deterministic greedy decoding.</li><li>Only one hardware configuration was used.</li><li>Tokenizer and native prompt-template differences mean contexts are matched semantically rather than token-for-token.</li><li>Subgroup analyses are exploratory.</li><li>The study is behavioral and does not establish an internal mechanism.</li><li>Qwen had process-level segfault/resume behavior; Llama had two 82K CUDA OOM failures.</li><li>No claim is made that all LLMs necessarily behave this way.</li></ul>",
        "<h1>Conclusion</h1>",
        "<p><b>Across two independently trained model families, increasing context length substantially reduced factual accuracy. Llama-3.2-3B-Instruct increased from 49.6% inaccurate at the shortest context condition to 70.7% at the longest, while Qwen3.5-2B increased from 45.2% to 71.2%. GEE models showed significantly increasing odds of factual inaccuracy with each doubling of rendered context for both models, and the model-by-context interaction was not significant. These results provide cross-model evidence that longer context can reduce factual reliability even when the information required to answer the task is held within a controlled benchmark.</b></p>",
        "<h1>Reproducibility / Artifact Manifest</h1>",
        f"<ul><li>Benchmark hash: <code>{BENCHMARK_HASH}</code></li><li>Frozen grader hash: <code>{GRADER_HASH}</code></li><li>Qwen revision: <code>{QWEN_REVISION}</code></li><li>Qwen prompt hash: <code>{QWEN_PROMPT_HASH}</code></li><li>Qwen raw results hash: <code>{sha256_file(E_INFERENCE / 'results.jsonl')}</code></li><li>Qwen scored results hash: <code>{sha256_file(E_GRADING / 'scored_results.jsonl')}</code></li><li>Experiment D scored CSV: <code>{sha256_file(D_GRADING / 'final_scored_results.csv')}</code></li></ul>",
        "<h1>Appendix</h1>",
        "<p>Exact source CSV files copied into the report output directory contain the full GEE tables, paired tests, subgroup summaries, latency summaries, and secondary error diagnostics. The DOCX and manifest hashes are recorded in <code>report_manifest.json</code>.</p>",
        "</body></html>",
    ]
    return "\n".join(parts)


def convert_with_libreoffice(html_path: Path) -> tuple[Path, Path | None]:
    docx_path = OUT / "final_cross_model_report.docx"
    pdf_path = OUT / "final_cross_model_report.pdf"
    odt_path = OUT / "final_cross_model_report.odt"
    env = os.environ.copy()
    env["HOME"] = "/tmp/final_report_cross_model_lohome"
    env["MPLCONFIGDIR"] = str((OUT / ".mplconfig").resolve())
    Path(env["HOME"]).mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["libreoffice", "--headless", "--convert-to", "odt", "--outdir", str(OUT), str(html_path)],
        check=True,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    generated_odt = OUT / (html_path.stem + ".odt")
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
    return docx_path, pdf_path if pdf_path and pdf_path.exists() else None


def xml_escape(text: object) -> str:
    return html.escape("" if text is None else str(text), quote=True)


def w_p(text: str = "", style: str | None = None, page_break_before: bool = False, align: str | None = None) -> str:
    ppr = []
    if style:
        ppr.append(f'<w:pStyle w:val="{style}"/>')
    if page_break_before:
        ppr.append("<w:pageBreakBefore/>")
    if align:
        ppr.append(f'<w:jc w:val="{align}"/>')
    ppr_xml = f"<w:pPr>{''.join(ppr)}</w:pPr>" if ppr else ""
    if not text:
        return f"<w:p>{ppr_xml}</w:p>"
    runs = []
    parts = str(text).split("\n")
    for idx, part in enumerate(parts):
        runs.append(f'<w:r><w:t xml:space="preserve">{xml_escape(part)}</w:t></w:r>')
        if idx != len(parts) - 1:
            runs.append("<w:r><w:br/></w:r>")
    return f"<w:p>{ppr_xml}{''.join(runs)}</w:p>"


def w_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    width = max(900, int(9200 / max(1, len(cols))))

    def cell(value: object, header: bool = False) -> str:
        shade = '<w:shd w:fill="E8EEF6"/>' if header else ""
        bold = "<w:rPr><w:b/></w:rPr>" if header else ""
        return (
            f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{shade}</w:tcPr>'
            f'<w:p><w:r>{bold}<w:t xml:space="preserve">{xml_escape(value)}</w:t></w:r></w:p></w:tc>'
        )

    rows = ["<w:tr>" + "".join(cell(c, True) for c in cols) + "</w:tr>"]
    for _, row in df.iterrows():
        rows.append("<w:tr>" + "".join(cell(v) for v in row.tolist()) + "</w:tr>")
    borders = (
        '<w:tblBorders><w:top w:val="single" w:sz="4" w:color="8FA7C0"/>'
        '<w:left w:val="single" w:sz="4" w:color="8FA7C0"/>'
        '<w:bottom w:val="single" w:sz="4" w:color="8FA7C0"/>'
        '<w:right w:val="single" w:sz="4" w:color="8FA7C0"/>'
        '<w:insideH w:val="single" w:sz="4" w:color="C8D2DD"/>'
        '<w:insideV w:val="single" w:sz="4" w:color="C8D2DD"/></w:tblBorders>'
    )
    return f'<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/>{borders}</w:tblPr>{"".join(rows)}</w:tbl>'


def image_xml(rel_id: str, path: Path, doc_pr_id: int, max_width_in: float = 6.35) -> str:
    with Image.open(path) as im:
        width_px, height_px = im.size
    width_in = min(max_width_in, width_px / 155.0)
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


def direct_docx(src: dict[str, Any], tables: dict[str, pd.DataFrame], figs: list[dict[str, str]], docx_path: Path) -> Path:
    d_gee = src["d_gee"]
    e_gee = src["e_gee"]
    inter = src["interaction"]
    rels = ['<Relationship Id="rFooter1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>']
    fig_rel: dict[str, str] = {}
    for i, fig in enumerate(figs, start=1):
        rid = f"rImg{i}"
        fig_rel[fig["name"]] = rid
        rels.append(f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/{Path(fig["png"]).name}"/>')

    body: list[str] = [
        w_p("Long-Context Factual Reliability Across Model Families", "Title", align="center"),
        w_p("A binary Accurate/Inaccurate cross-model replication of Experiment D and Experiment E", "Subtitle", align="center"),
        w_p(f"Final Cross-Model Report\nGenerated: {date.today().isoformat()}\nBenchmark hash: {BENCHMARK_HASH}\nPrimary outcome: Accurate vs Inaccurate", align="center"),
        w_p("Table of Contents", "Heading1", page_break_before=True),
    ]
    toc = [
        "Abstract", "Executive Summary", "Research Question and Motivation", "Experimental Design",
        "Dataset and Question-Family Construction", "Context-Length Conditions", "Models",
        "Inference Configuration and Reproducibility", "Factual Accuracy Definition", "Statistical Methodology",
        "Llama Results", "Qwen Results", "Cross-Model Comparison", "Model x Context Interaction",
        "Paired Context Comparisons", "Question-Type Analysis", "Domain Analysis", "Latency and Runtime Behavior",
        "Secondary Error Diagnostics", "Discussion", "Limitations", "Conclusion", "Reproducibility / Artifact Manifest", "Appendix",
    ]
    body.extend(w_p(item, "TOCLine") for item in toc)

    def heading(text: str) -> None:
        body.append(w_p(text, "Heading1", page_break_before=True))

    def table(caption: str, df: pd.DataFrame) -> None:
        body.append(w_p(caption, "Caption"))
        body.append(w_table(df))

    def figure(n: int, fig: dict[str, str]) -> None:
        body.append(image_xml(fig_rel[fig["name"]], Path(fig["png"]), n))
        body.append(w_p(f"Figure {n}. {fig['caption']}", "Caption"))

    heading("Abstract")
    body.append(w_p("This report summarizes two completed long-context factual-reliability experiments using a shared frozen benchmark. The primary scientific outcome is binary: Accurate versus Inaccurate. CORRECT responses are Accurate; every other successfully generated factual-task outcome is Inaccurate. Runtime failures are reported separately and are not counted as factual inaccuracies."))
    body.append(w_p("Increasing context length substantially reduced factual accuracy in both Llama-3.2-3B-Instruct and Qwen3.5-2B. Llama inaccuracy increased from 49.6% at 4K to 70.7% at 82K; Qwen inaccuracy increased from 45.2% to 71.2%. GEE logistic models clustered by question family showed significantly increasing odds of factual inaccuracy per true doubling of rendered input tokens for both models. The model-by-context interaction was not statistically significant for overall inaccuracy, indicating no detectable difference in the overall degradation slope between the two model families in this benchmark."))

    heading("Executive Summary")
    body.append(w_p("Central finding: factual accuracy decreases substantially as context length increases, and this effect replicated across two different model families. The shortest condition produced 49.6% inaccurate Llama responses and 45.2% inaccurate Qwen responses. The longest condition produced 70.7% inaccurate Llama responses and 71.2% inaccurate Qwen responses."))
    body.append(w_p(f"Llama's primary GEE odds ratio was {d_gee['odds_ratio_per_2x_context']:.3f} per true 2x increase in rendered context, 95% CI {ci(d_gee['odds_ratio_ci_low'], d_gee['odds_ratio_ci_high'])}, p = {pval(d_gee['p_value'])}. Qwen's primary GEE odds ratio was {e_gee['odds_ratio_per_2x_context']:.3f}, 95% CI {ci(e_gee['odds_ratio_ci_low'], e_gee['odds_ratio_ci_high'])}, p = {pval(e_gee['p_value'])}."))
    body.append(w_p(f"The overall model x context interaction was not significant: Qwen-vs-Llama slope OR ratio {inter['interaction_or_ratio']:.3f}, 95% CI {ci(inter['ci_low'], inter['ci_high'])}, p = {pval(inter['p_value'])}. This does not prove identical slopes; it means the experiment did not detect a statistically significant difference in overall degradation rates."))

    heading("Research Question and Motivation")
    body.append(w_p("The central research question is how increasing context length affects factual reliability when an LLM must answer factual questions from controlled but information-rich context. The cross-model extension asks whether the Experiment D result in Llama behaviorally replicates in a different model family, Qwen. This report intentionally frames the main result using the binary factual outcome Accurate versus Inaccurate."))

    heading("Experimental Design")
    body.append(w_p("Both experiments used the same frozen benchmark information and semantic task. Llama used its native Llama chat template; Qwen used its native Qwen chat template in non-thinking mode. The two models therefore did not receive byte-identical rendered prompts, but they received matched benchmark facts, questions, context construction, answer target, evidence ordering, and output contract."))

    heading("Dataset and Question-Family Construction")
    body.append(w_p("The benchmark contains 500 question families and six context conditions, producing 3,000 attempted instances per model. The domains are SEC, FDA/Drugs@FDA, ClinicalTrials.gov, and FRED/ALFRED, with 125 families from each domain. There are 400 answerable and 100 unanswerable families."))
    table("Table 1. Frozen benchmark question-type distribution.", pd.DataFrame({
        "Question Type": ["DIRECT_RETRIEVAL", "RETRIEVAL_CALCULATION", "TEMPORAL_VERSION", "ENTITY_UNIT_BINDING", "UNANSWERABLE"],
        "Families": [100, 150, 55, 95, 100],
        "Purpose": ["Retrieve a directly stated fact", "Retrieve values and compute a deterministic result", "Bind answer to the correct period/version", "Bind entity/unit/product/series correctly", "Abstain when required evidence is absent"],
    }))

    heading("Context-Length Conditions")
    body.append(w_p("The six benchmark conditions are 4K, 8K, 16K, 32K, 64K, and 82K. These labels describe matched benchmark conditions, not guaranteed tokenizer-identical lengths. Statistical trend models use each model's actual log2(rendered_input_tokens), so +1 corresponds to a true doubling of rendered tokens for that model."))

    heading("Models")
    body.append(w_p("Llama-3.2-3B-Instruct: Experiment D used meta-llama/Llama-3.2-3B-Instruct. It produced 2,998 successful generations out of 3,000 attempts, with two CUDA OOM runtime failures at 82K."))
    body.append(w_p(f"Qwen3.5-2B: Experiment E used Qwen/Qwen3.5-2B at revision {QWEN_REVISION}. It produced 3,000 successful generations out of 3,000 attempts, with zero instance-level runtime failures."))

    heading("Inference Configuration and Reproducibility")
    body.append(w_p(f"Qwen was run with Transformers 5.14.1, PyTorch 2.5.1+cu121, CUDA runtime 12.1, NVIDIA GeForce RTX 4090, driver 550.163.01, Qwen2Tokenizer, Qwen3_5ForCausalLM, BF16, DynamicCache, SDPA, greedy decoding, and no thinking mode. The Qwen prompt version was qwen35_chat_v1, prompt hash {QWEN_PROMPT_HASH}. The frozen benchmark hash was {BENCHMARK_HASH}, and the frozen grader hash was {GRADER_HASH}."))

    heading("Factual Accuracy Definition")
    body.append(w_p("Accurate means the deterministic grader labeled the successful response CORRECT. Inaccurate means any other successfully generated factual-task outcome. Runtime failures are separate operational failures and are not factual inaccuracies."))

    heading("Statistical Methodology")
    body.append(w_p("The primary model for each experiment was GEE logistic regression clustered by question_family_id. The outcome was INACCURATE. The predictor was log2(rendered_input_tokens), so a one-unit increase represents a true doubling of rendered input tokens. A combined long-form model tested the interaction log2(rendered_input_tokens) x model."))
    table("Table 2. Primary GEE logistic models for overall factual inaccuracy.", tables["gee_primary"])

    heading("Llama Results")
    body.append(w_p("Llama factual inaccuracy increased from 49.6% at 4K to 70.7% at 82K. The primary GEE OR was 1.232 per doubling of rendered context, corresponding to approximately a 23.2% increase in the odds of factual inaccuracy."))

    heading("Qwen Results")
    body.append(w_p("Qwen factual inaccuracy increased from 45.2% at 4K to 71.2% at 82K. The primary GEE OR was 1.276 per doubling of rendered Qwen context, corresponding to approximately a 27.6% increase in the odds of factual inaccuracy."))
    table("Table 3. Binary Accurate/Inaccurate results by context.", tables["primary_binary_results"])
    figure(1, figs[0])
    figure(2, figs[1])

    heading("Cross-Model Comparison")
    body.append(w_p("Increasing context length substantially reduced factual accuracy in both Llama-3.2-3B-Instruct and Qwen3.5-2B. The models differ in family, tokenizer, architecture, training, native chat template, and actual rendered token counts, so the comparison is behavioral rather than architectural."))
    figure(3, figs[2])

    heading("Model x Context Interaction")
    body.append(w_p("The most important cross-model test is the context-by-model interaction. The interaction was not statistically significant for overall factual inaccuracy. Therefore, although Qwen's point estimate was slightly larger, this experiment does not provide evidence that the overall context-length degradation slope differs between the two models."))
    table("Table 4. Combined model interaction test for overall factual inaccuracy.", tables["interaction"])
    figure(4, figs[3])

    heading("Paired Context Comparisons")
    body.append(w_p("Paired McNemar tests compared 4K against each higher context condition within the same question families. For both Llama and Qwen, 4K versus every higher context showed significant increases in overall inaccuracy after Holm correction."))
    table("Table 5. Paired McNemar tests for overall inaccuracy.", tables["paired_mcnemar"])

    heading("Question-Type Analysis")
    body.append(w_p("Question-type analyses are exploratory. Direct retrieval, temporal/version, and entity/unit binding showed clear degradation in one or both models; retrieval/calculation had high baseline error rates; unanswerable behavior differed between models."))
    table("Table 6. Exploratory question-type summary, shortest versus longest context.", tables["question_type_summary"])
    figure(5, figs[4])

    heading("Domain Analysis")
    body.append(w_p("Domain analyses are exploratory. Both models showed higher inaccuracy at 82K than 4K across SEC, FDA, ClinicalTrials, and FRED/ALFRED, with the magnitude differing by model and domain."))
    table("Table 7. Exploratory domain summary, shortest versus longest context.", tables["domain_summary"])
    figure(6, figs[5])

    heading("Latency and Runtime Behavior")
    body.append(w_p("Llama had 3,000 attempted generations, 2,998 successes, and two CUDA OOM failures at 82K. Qwen had 3,000 attempted generations, 3,000 successes, and zero instance-level runtime failures. Qwen full inference had process-level segmentation faults after flushed rows at 943, 1831, 1846, and 2952; the run resumed with identical pinned settings and skipped completed IDs. These process interruptions are not counted as factual failures. Transformers also fell back from Qwen's optional fast path to the torch implementation because optional packages were unavailable."))
    table("Table 8. Latency and rendered-token summaries.", tables["latency"])
    figure(7, figs[6])

    heading("Secondary Error Diagnostics")
    body.append(w_p("The deterministic grader also categorized inaccuracies into detailed failure types. These analyses are secondary diagnostics and do not dominate the primary scientific framing. They suggest that the broad Accurate/Inaccurate degradation can arise from different mechanisms across models."))
    table("Table 9. Secondary detailed error taxonomy, 4K to 82K changes.", tables["secondary_error_diagnostics"])

    heading("Discussion")
    body.append(w_p("Both models show strong factual-reliability degradation with longer context, and the degradation is statistically strong within each model. The overall context-length slopes are not significantly different between Llama and Qwen, so the observed degradation replicated behaviorally across two model families. This study does not identify the internal architectural cause."))
    body.append(w_p("Tokenization and prompt-template differences prevent claiming that the two models saw byte-identical rendered prompts. Nevertheless, they received the same frozen benchmark information and semantic task under their native templates. A third model family would be a natural next step for assessing broader generalizability."))

    heading("Limitations")
    body.append(w_p("Limitations include: only two model families; relatively small 2B-3B scale models; one benchmark construction; four source domains; deterministic greedy decoding; one hardware configuration; tokenizer differences; native prompt-template differences; semantically matched rather than token-for-token context conditions; exploratory subgroup analyses; behavioral design that does not establish internal mechanism; Qwen process-level segfault/resume behavior; Llama's two 82K OOMs; and no claim that all LLMs necessarily behave this way."))

    heading("Conclusion")
    body.append(w_p("Across two independently trained model families, increasing context length substantially reduced factual accuracy. Llama-3.2-3B-Instruct increased from 49.6% inaccurate at the shortest context condition to 70.7% at the longest, while Qwen3.5-2B increased from 45.2% to 71.2%. GEE models showed significantly increasing odds of factual inaccuracy with each doubling of rendered context for both models, and the model-by-context interaction was not significant. These results provide cross-model evidence that longer context can reduce factual reliability even when the information required to answer the task is held within a controlled benchmark."))

    heading("Reproducibility / Artifact Manifest")
    body.append(w_p(f"Benchmark hash: {BENCHMARK_HASH}\nFrozen grader hash: {GRADER_HASH}\nQwen revision: {QWEN_REVISION}\nQwen prompt hash: {QWEN_PROMPT_HASH}\nQwen raw results hash: {sha256_file(E_INFERENCE / 'results.jsonl')}\nQwen scored results hash: {sha256_file(E_GRADING / 'scored_results.jsonl')}\nExperiment D scored CSV hash: {sha256_file(D_GRADING / 'final_scored_results.csv')}"))

    heading("Appendix")
    body.append(w_p("Exact source CSV files copied into the report output directory contain the full GEE tables, paired tests, subgroup summaries, latency summaries, and secondary error diagnostics. The DOCX and manifest hashes are recorded in report_manifest.json."))

    sect = (
        '<w:sectPr><w:footerReference w:type="default" r:id="rFooter1"/>'
        '<w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1008" w:right="1008" w:bottom="1008" w:left="1008" w:header="432" w:footer="432" w:gutter="0"/>'
        '<w:cols w:space="720"/><w:docGrid w:linePitch="360"/></w:sectPr>'
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas" '
        'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
        'xmlns:o="urn:schemas-microsoft-com:office:office" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
        'xmlns:v="urn:schemas-microsoft-com:vml" '
        'xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing" '
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
        'xmlns:w10="urn:schemas-microsoft-com:office:word" '
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" '
        'mc:Ignorable="w14 wp14"><w:body>'
        + "".join(body)
        + sect
        + "</w:body></w:document>"
    )
    styles = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:rPr><w:rFonts w:ascii="Aptos" w:hAnsi="Aptos"/><w:sz w:val="21"/></w:rPr></w:style>
      <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:pPr><w:spacing w:after="240"/></w:pPr><w:rPr><w:rFonts w:ascii="Aptos Display" w:hAnsi="Aptos Display"/><w:b/><w:color w:val="163B63"/><w:sz w:val="48"/></w:rPr></w:style>
      <w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:rPr><w:color w:val="4B5563"/><w:sz w:val="28"/></w:rPr></w:style>
      <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/></w:pPr><w:rPr><w:b/><w:color w:val="163B63"/><w:sz w:val="32"/></w:rPr></w:style>
      <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:pPr><w:keepNext/><w:spacing w:before="160" w:after="80"/></w:pPr><w:rPr><w:b/><w:color w:val="244B73"/><w:sz w:val="25"/></w:rPr></w:style>
      <w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="Caption"/><w:rPr><w:b/><w:color w:val="38465A"/><w:sz w:val="18"/></w:rPr></w:style>
      <w:style w:type="paragraph" w:styleId="TOCLine"><w:name w:val="TOCLine"/><w:pPr><w:spacing w:after="50"/></w:pPr><w:rPr><w:sz w:val="20"/></w:rPr></w:style>
    </w:styles>"""
    footer = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:p><w:pPr><w:jc w:val="center"/></w:pPr>
        <w:r><w:t>Final cross-model long-context factual-reliability report | Page </w:t></w:r>
        <w:r><w:fldChar w:fldCharType="begin"/></w:r>
        <w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>
        <w:r><w:fldChar w:fldCharType="separate"/></w:r>
        <w:r><w:t>1</w:t></w:r>
        <w:r><w:fldChar w:fldCharType="end"/></w:r>
      </w:p>
    </w:ftr>"""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
      <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
      <Default Extension="xml" ContentType="application/xml"/>
      <Default Extension="png" ContentType="image/png"/>
      <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
      <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
      <Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
    </Types>"""
    root_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
      <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
    </Relationships>"""
    doc_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(rels)
        + "</Relationships>"
    )
    if docx_path.exists():
        docx_path.unlink()
    with zipfile.ZipFile(docx_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("word/document.xml", document)
        zf.writestr("word/styles.xml", styles)
        zf.writestr("word/footer1.xml", footer)
        zf.writestr("word/_rels/document.xml.rels", doc_rels)
        for fig in figs:
            p = Path(fig["png"])
            zf.write(p, f"word/media/{p.name}")
    return docx_path


def pdf_from_docx(docx_path: Path) -> Path | None:
    env = os.environ.copy()
    env["HOME"] = "/tmp/final_report_cross_model_lohome"
    Path(env["HOME"]).mkdir(parents=True, exist_ok=True)
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
        return None
    pdf_path = OUT / (docx_path.stem + ".pdf")
    return pdf_path if pdf_path.exists() else None


def validate_docx(docx_path: Path, pdf_path: Path | None, figs: list[dict[str, str]]) -> dict[str, Any]:
    with zipfile.ZipFile(docx_path) as zf:
        names = zf.namelist()
        media = [n for n in names if n.startswith("word/media/")]
        document_xml = zf.read("word/document.xml").decode("utf-8", errors="replace")
    page_count = None
    if pdf_path is not None:
        out = subprocess.run(["pdfinfo", str(pdf_path)], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for line in out.stdout.splitlines():
            if line.startswith("Pages:"):
                page_count = int(line.split(":", 1)[1].strip())
                break
    required_phrases = ["Accurate", "Inaccurate", "not significant", "process-level segmentation faults", QWEN_REVISION, BENCHMARK_HASH]
    missing = [p for p in required_phrases if p not in document_xml]
    return {
        "docx_opens_as_zip": True,
        "embedded_media_count": len(media),
        "expected_figure_count": len(figs),
        "all_figures_embedded": len(media) >= len(figs),
        "pdf_page_count": page_count,
        "required_phrase_check_passed": not missing,
        "missing_required_phrases": missing,
        "docx_size_bytes": docx_path.stat().st_size,
        "pdf_size_bytes": pdf_path.stat().st_size if pdf_path and pdf_path.exists() else None,
    }


def write_manifest(src: dict[str, Any], tables: dict[str, pd.DataFrame], figs: list[dict[str, str]], docx: Path, pdf: Path | None, validation: dict[str, Any]) -> Path:
    artifacts = [docx, OUT / "final_cross_model_report.html", *[Path(f["png"]) for f in figs], *[Path(f["pdf"]) for f in figs], *sorted(TABLES.glob("*.csv"))]
    if pdf is not None:
        artifacts.append(pdf)
    hashes = {p.as_posix(): sha256_file(p) for p in artifacts if p.exists()}
    manifest = {
        "created_at": now(),
        "docx_path": docx.as_posix(),
        "pdf_path": pdf.as_posix() if pdf else None,
        "benchmark_hash": BENCHMARK_HASH,
        "grader_hash": GRADER_HASH,
        "qwen_revision": QWEN_REVISION,
        "qwen_prompt_hash": QWEN_PROMPT_HASH,
        "primary_outcome": "Accurate vs Inaccurate",
        "runtime_failures_counted_as_factual_inaccuracies": False,
        "source_artifacts": {
            "llama_primary": (D_ANALYSIS / "primary_results.csv").as_posix(),
            "qwen_primary": (E_ANALYSIS / "overall_context_results.csv").as_posix(),
            "cross_model_interaction": (E_ANALYSIS / "cross_model_interaction_models.csv").as_posix(),
        },
        "figures_included": [f["title"] for f in figs],
        "tables_included": list(tables),
        "validation": validation,
        "hashes": hashes,
        "platform": platform.platform(),
    }
    path = OUT / "report_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest["hashes"][path.as_posix()] = sha256_file(path)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> int:
    prepare()
    src = load_sources()
    tables = build_tables(src)
    figs = make_figures(src)
    html_text = build_html(src, tables, figs)
    html_path = OUT / "final_cross_model_report.html"
    html_path.write_text(html_text, encoding="utf-8")
    docx_path = direct_docx(src, tables, figs, OUT / "final_cross_model_report.docx")
    pdf_path = pdf_from_docx(docx_path)
    validation = validate_docx(docx_path, pdf_path, figs)
    manifest_path = write_manifest(src, tables, figs, docx_path, pdf_path, validation)
    print(json.dumps({
        "docx": docx_path.as_posix(),
        "pdf": pdf_path.as_posix() if pdf_path else None,
        "manifest": manifest_path.as_posix(),
        "docx_sha256": sha256_file(docx_path),
        "manifest_sha256": sha256_file(manifest_path),
        "validation": validation,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
