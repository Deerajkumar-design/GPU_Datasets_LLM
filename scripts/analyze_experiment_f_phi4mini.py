#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import platform
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
import scipy.stats
import seaborn as sns
import statsmodels
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.contingency_tables import mcnemar
from statsmodels.stats.multitest import multipletests


PHI_CSV = Path("data/grading_experiment_f_phi4mini_v1/scored_results.csv")
PHI_FAILURES = Path("data/grading_experiment_f_phi4mini_v1/runtime_failures.jsonl")
PHI_INFERENCE = Path("data/inference_phi4mini_500f_6ctx_v1")
LLAMA_CSV = Path("data/grading_experiment_d_final_v1/final_scored_results.csv")
LLAMA_FAILURES = Path("data/grading_experiment_d_final_v1/runtime_failures.jsonl")
QWEN_CSV = Path("data/grading_experiment_e_qwen35_2b_v1/scored_results.csv")
QWEN_FAILURES = Path("data/grading_experiment_e_qwen35_2b_v1/runtime_failures.jsonl")
OUT = Path("data/analysis_experiment_f_phi4mini_v1")
FIG = OUT / "figures"
CONTEXTS = ["4K", "8K", "16K", "32K", "64K", "82K"]
MODEL_LABELS = {
    "llama32_3b": "Llama-3.2-3B-Instruct",
    "qwen35_2b": "Qwen3.5-2B",
    "phi4mini": "Phi-4-mini-instruct",
}
GRADER_HASH = "d9282a0ccc50daba3bfd232c058dfbab63a5c19a7323d585a7c2236b3a6c4ba8"
BENCHMARK_HASH = "dc2c4194dedb090198e6883735257908ce274bebc8611b40d958dbd026aa1fe6"
MODEL_REVISION = "cfbefacb99257ffa30c83adab238a50856ac3083"
PROMPT_VERSION = "phi4mini_chat_v1"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def load_failures(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def bool_series(s: pd.Series) -> pd.Series:
    return s.map(lambda x: str(x).strip().lower() == "true")


def load_scored(path: Path, model: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["answer_correct"] = bool_series(df["answer_correct"])
    df["model"] = model
    df["model_label"] = MODEL_LABELS[model]
    df["context_length_label"] = pd.Categorical(df["context_length_label"], CONTEXTS, ordered=True)
    df["accurate"] = df["answer_correct"].astype(int)
    df["inaccurate"] = (~df["answer_correct"]).astype(int)
    df["context_log2"] = np.log2(df["input_tokens"].astype(float))
    return df


def context_sort(df: pd.DataFrame) -> pd.DataFrame:
    col = "context_length_label" if "context_length_label" in df.columns else "context"
    return df.sort_values(col, key=lambda s: pd.Categorical(s, CONTEXTS, ordered=True))


def fit_gee(df: pd.DataFrame, outcome: str = "inaccurate", label: str = "primary") -> dict:
    if df.empty or df["question_family_id"].nunique() < 2 or df[outcome].nunique() < 2:
        return {
            "analysis": label,
            "outcome": outcome,
            "n_observations": int(len(df)),
            "n_families": int(df["question_family_id"].nunique()),
            "estimable": False,
            "reason": "insufficient variation or clusters",
        }
    res = smf.gee(
        f"{outcome} ~ context_log2",
        groups="question_family_id",
        data=df,
        family=sm.families.Binomial(),
        cov_struct=sm.cov_struct.Exchangeable(),
    ).fit()
    coef = float(res.params["context_log2"])
    se = float(res.bse["context_log2"])
    lo, hi = res.conf_int().loc["context_log2"].tolist()
    return {
        "analysis": label,
        "outcome": outcome,
        "formula": f"{outcome} ~ context_log2",
        "working_correlation": "Exchangeable",
        "n_observations": int(res.nobs),
        "n_families": int(df["question_family_id"].nunique()),
        "estimable": True,
        "coefficient": coef,
        "robust_se": se,
        "odds_ratio_per_2x_context": float(math.exp(coef)),
        "odds_ratio_ci_low": float(math.exp(lo)),
        "odds_ratio_ci_high": float(math.exp(hi)),
        "p_value": float(res.pvalues["context_log2"]),
    }


def context_accuracy(df: pd.DataFrame, failures: list[dict], token_stats: pd.DataFrame) -> pd.DataFrame:
    failure_counts = Counter(f.get("context_length_label") for f in failures)
    rows = []
    for ctx in CONTEXTS:
        sub = df[df["context_length_label"].astype(str) == ctx]
        toks = token_stats[token_stats["context_length_label"] == ctx]
        mean_tokens = float(toks["mean"].iloc[0]) if not toks.empty else float(sub["input_tokens"].mean()) if len(sub) else np.nan
        rows.append({
            "context": ctx,
            "successful_n": int(len(sub)),
            "runtime_failures": int(failure_counts.get(ctx, 0)),
            "accurate_count": int(sub["accurate"].sum()) if len(sub) else 0,
            "inaccurate_count": int(sub["inaccurate"].sum()) if len(sub) else 0,
            "accurate_rate": float(sub["accurate"].mean()) if len(sub) else np.nan,
            "inaccuracy_rate": float(sub["inaccurate"].mean()) if len(sub) else np.nan,
            "mean_rendered_phi_tokens": mean_tokens,
            "mean_latency_seconds": float(sub["generation_latency_seconds"].mean()) if len(sub) else np.nan,
        })
    return pd.DataFrame(rows)


def token_stats_from_inference() -> pd.DataFrame:
    p = PHI_INFERENCE / "Phi_prompt_budget_verification.json"
    if p.exists():
        data = load_json(p)
        stats_by_context = data.get("token_stats_by_context") or data.get("summary", {}).get("by_context", {})
        rows = []
        for ctx, stats in stats_by_context.items():
            rows.append({
                "context_length_label": ctx,
                "n": int(stats["n"]),
                "mean": float(stats["mean"]),
                "median": float(stats["median"]),
                "sd": float(stats["sd"]),
                "min": int(stats["min"]),
                "max": int(stats["max"]),
            })
        return pd.DataFrame(rows)
    df = load_scored(PHI_CSV, "phi4mini")
    return df.groupby("context_length_label", observed=False)["input_tokens"].agg(["count", "mean", "median", "std", "min", "max"]).reset_index()


def latency_stats(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ctx in CONTEXTS:
        sub = df[df["context_length_label"].astype(str) == ctx]["generation_latency_seconds"].dropna()
        rows.append({
            "context": ctx,
            "n_successful": int(len(sub)),
            "mean_seconds": float(sub.mean()) if len(sub) else np.nan,
            "median_seconds": float(sub.median()) if len(sub) else np.nan,
            "sd_seconds": float(sub.std(ddof=1)) if len(sub) > 1 else np.nan,
            "p95_seconds": float(sub.quantile(0.95)) if len(sub) else np.nan,
        })
    return pd.DataFrame(rows)


def paired_tests(df: pd.DataFrame) -> pd.DataFrame:
    wide = df.pivot(index="question_family_id", columns="context_length_label", values="inaccurate")
    raw = []
    for ctx in ["8K", "16K", "32K", "64K", "82K"]:
        if "4K" not in wide.columns or ctx not in wide.columns:
            raw.append({
                "comparison": f"4K_vs_{ctx}",
                "paired_n": 0,
                "estimable": False,
                "reason": "no families with successful outputs in both conditions",
            })
            continue
        pair = wide[["4K", ctx]].dropna()
        row = {"comparison": f"4K_vs_{ctx}", "paired_n": int(len(pair))}
        if len(pair) == 0:
            row.update({"estimable": False, "reason": "no families with successful outputs in both conditions"})
            raw.append(row)
            continue
        a = pair["4K"].astype(int)
        b = pair[ctx].astype(int)
        table = [[int(((a == 0) & (b == 0)).sum()), int(((a == 0) & (b == 1)).sum())],
                 [int(((a == 1) & (b == 0)).sum()), int(((a == 1) & (b == 1)).sum())]]
        res = mcnemar(table, exact=True)
        row.update({
            "estimable": True,
            "event_rate_4K": float(a.mean()),
            "event_rate_comparison": float(b.mean()),
            "absolute_percentage_point_difference": float((b.mean() - a.mean()) * 100),
            "discordant_4K_accurate_comparison_inaccurate": table[0][1],
            "discordant_4K_inaccurate_comparison_accurate": table[1][0],
            "raw_p_value": float(res.pvalue),
        })
        raw.append(row)
    estimable = [r for r in raw if r.get("estimable")]
    if estimable:
        _, adj, _, _ = multipletests([r["raw_p_value"] for r in estimable], method="holm")
        for r, p in zip(estimable, adj):
            r["holm_adjusted_p_value"] = float(p)
            r["significant_after_holm_0_05"] = bool(p < 0.05)
    return pd.DataFrame(raw)


def subgroup(df: pd.DataFrame, by: str) -> pd.DataFrame:
    rows = []
    for (grp, ctx), sub in df.groupby([by, "context_length_label"], observed=False):
        if len(sub) == 0:
            continue
        rows.append({
            by: grp,
            "context": str(ctx),
            "n": int(len(sub)),
            "accurate_count": int(sub["accurate"].sum()),
            "inaccurate_count": int(sub["inaccurate"].sum()),
            "accurate_rate": float(sub["accurate"].mean()),
            "inaccuracy_rate": float(sub["inaccurate"].mean()),
        })
    return context_sort(pd.DataFrame(rows))


def model_context_table(dfs: list[pd.DataFrame], failures_by_model: dict[str, list[dict]]) -> pd.DataFrame:
    rows = []
    for df in dfs:
        model = str(df["model"].iloc[0])
        fcounts = Counter(f.get("context_length_label") for f in failures_by_model.get(model, []))
        for ctx in CONTEXTS:
            sub = df[df["context_length_label"].astype(str) == ctx]
            rows.append({
                "model": model,
                "model_label": MODEL_LABELS[model],
                "context": ctx,
                "successful_n": int(len(sub)),
                "runtime_failures": int(fcounts.get(ctx, 0)),
                "accurate_rate": float(sub["accurate"].mean()) if len(sub) else np.nan,
                "inaccuracy_rate": float(sub["inaccurate"].mean()) if len(sub) else np.nan,
                "mean_rendered_tokens": float(sub["input_tokens"].mean()) if len(sub) else np.nan,
            })
    return pd.DataFrame(rows)


def pairwise_interaction(df: pd.DataFrame, reference: str, comparison: str) -> dict:
    sub = df[df["model"].isin([reference, comparison])].copy()
    sub["model"] = pd.Categorical(sub["model"], [reference, comparison])
    term = f"context_log2:C(model)[T.{comparison}]"
    res = smf.gee(
        "inaccurate ~ context_log2 * C(model)",
        groups="question_family_id",
        data=sub,
        family=sm.families.Binomial(),
        cov_struct=sm.cov_struct.Exchangeable(),
    ).fit()
    coef = float(res.params[term])
    se = float(res.bse[term])
    lo, hi = res.conf_int().loc[term].tolist()
    return {
        "comparison": f"{MODEL_LABELS[comparison]} vs {MODEL_LABELS[reference]}",
        "reference_model": reference,
        "comparison_model": comparison,
        "term": term,
        "n_observations": int(res.nobs),
        "coefficient": coef,
        "robust_se": se,
        "or_ratio": float(math.exp(coef)),
        "or_ratio_ci_low": float(math.exp(lo)),
        "or_ratio_ci_high": float(math.exp(hi)),
        "p_value": float(res.pvalues[term]),
    }


def joint_interaction(df: pd.DataFrame) -> dict:
    sub = df.copy()
    sub["model"] = pd.Categorical(sub["model"], ["llama32_3b", "qwen35_2b", "phi4mini"])
    res = smf.gee(
        "inaccurate ~ context_log2 * C(model)",
        groups="question_family_id",
        data=sub,
        family=sm.families.Binomial(),
        cov_struct=sm.cov_struct.Exchangeable(),
    ).fit()
    terms = [t for t in res.params.index if t.startswith("context_log2:C(model)")]
    b = res.params.loc[terms].to_numpy()
    v = res.cov_params().loc[terms, terms].to_numpy()
    stat = float(b.T @ np.linalg.inv(v) @ b)
    p = float(scipy.stats.chi2.sf(stat, len(terms)))
    return {
        "comparison": "joint_three_model_context_slope_interaction",
        "terms": ";".join(terms),
        "n_observations": int(res.nobs),
        "df": int(len(terms)),
        "wald_chi2": stat,
        "p_value": p,
    }


def save_lineplot(data: pd.DataFrame, y: str, ylabel: str, path: Path, hue: str | None = None) -> None:
    plt.figure(figsize=(8, 5))
    sns.lineplot(data=data, x="context", y=y, hue=hue, marker="o", linewidth=2.2)
    plt.ylabel(ylabel)
    plt.xlabel("Matched context condition")
    plt.ylim(0, 1)
    plt.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(path.with_suffix(".png"), dpi=300)
    plt.savefig(path.with_suffix(".pdf"))
    plt.close()


def make_figures(phi: pd.DataFrame, phi_context: pd.DataFrame, qtype: pd.DataFrame, domain: pd.DataFrame, three: pd.DataFrame, gee_rows: pd.DataFrame, latency: pd.DataFrame) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    plot_ctx = phi_context.copy()
    plot_ctx["accurate_rate_pct"] = plot_ctx["accurate_rate"] * 100
    plot_ctx["inaccuracy_rate_pct"] = plot_ctx["inaccuracy_rate"] * 100
    plt.figure(figsize=(8, 5))
    x = np.arange(len(CONTEXTS))
    acc = [float(plot_ctx.loc[plot_ctx.context == c, "accurate_rate"].iloc[0]) if not plot_ctx.loc[plot_ctx.context == c].empty else np.nan for c in CONTEXTS]
    inc = [float(plot_ctx.loc[plot_ctx.context == c, "inaccuracy_rate"].iloc[0]) if not plot_ctx.loc[plot_ctx.context == c].empty else np.nan for c in CONTEXTS]
    plt.bar(x, acc, label="Accurate", color="#4C78A8")
    plt.bar(x, inc, bottom=acc, label="Inaccurate", color="#F58518")
    plt.xticks(x, CONTEXTS)
    plt.ylim(0, 1)
    plt.ylabel("Proportion of successful factual outputs")
    plt.xlabel("Matched context condition")
    plt.legend(frameon=False)
    plt.tight_layout()
    plt.savefig(FIG / "figure_01_phi_accurate_inaccurate_by_context.png", dpi=300)
    plt.savefig(FIG / "figure_01_phi_accurate_inaccurate_by_context.pdf")
    plt.close()

    plt.figure(figsize=(8, 5))
    sns.regplot(data=phi, x="context_log2", y="inaccurate", logistic=True, scatter_kws={"alpha": 0.25, "s": 18}, line_kws={"linewidth": 2.5, "color": "#E45756"})
    plt.xlabel("log2(rendered Phi input tokens)")
    plt.ylabel("Factual inaccuracy")
    plt.ylim(-0.05, 1.05)
    plt.tight_layout()
    plt.savefig(FIG / "figure_02_phi_inaccuracy_vs_actual_tokens.png", dpi=300)
    plt.savefig(FIG / "figure_02_phi_inaccuracy_vs_actual_tokens.pdf")
    plt.close()

    save_lineplot(three, "accurate_rate", "Accuracy rate", FIG / "figure_03_three_model_accuracy_by_context", hue="model_label")
    save_lineplot(three, "inaccuracy_rate", "Inaccuracy rate", FIG / "figure_04_three_model_inaccuracy_by_context", hue="model_label")

    plt.figure(figsize=(8, 5))
    for model, sub in three.dropna(subset=["inaccuracy_rate", "mean_rendered_tokens"]).groupby("model"):
        plt.plot(np.log2(sub["mean_rendered_tokens"]), sub["inaccuracy_rate"], marker="o", linewidth=2.2, label=MODEL_LABELS[model])
    plt.xlabel("log2(mean rendered input tokens)")
    plt.ylabel("Inaccuracy rate")
    plt.ylim(0, 1)
    plt.legend(frameon=False)
    plt.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(FIG / "figure_05_three_model_inaccuracy_actual_token_trend.png", dpi=300)
    plt.savefig(FIG / "figure_05_three_model_inaccuracy_actual_token_trend.pdf")
    plt.close()

    ors = gee_rows[gee_rows["analysis"].isin(["llama_primary", "qwen_primary", "phi_primary"])].copy()
    ors["model_label"] = ors["analysis"].map({
        "llama_primary": MODEL_LABELS["llama32_3b"],
        "qwen_primary": MODEL_LABELS["qwen35_2b"],
        "phi_primary": MODEL_LABELS["phi4mini"],
    })
    plt.figure(figsize=(7, 4.5))
    y = np.arange(len(ors))
    plt.errorbar(ors["odds_ratio_per_2x_context"], y, xerr=[ors["odds_ratio_per_2x_context"] - ors["odds_ratio_ci_low"], ors["odds_ratio_ci_high"] - ors["odds_ratio_per_2x_context"]], fmt="o", color="#333333", capsize=4)
    plt.axvline(1, color="#888888", linestyle="--")
    plt.yticks(y, ors["model_label"])
    plt.xlabel("Odds ratio per 2x rendered context")
    plt.tight_layout()
    plt.savefig(FIG / "figure_06_three_model_or_per_doubling.png", dpi=300)
    plt.savefig(FIG / "figure_06_three_model_or_per_doubling.pdf")
    plt.close()

    save_lineplot(qtype.rename(columns={"question_type": "group"}), "accurate_rate", "Accuracy rate", FIG / "figure_07_phi_question_type_accuracy", hue="group")
    save_lineplot(domain.rename(columns={"domain": "group"}), "accurate_rate", "Accuracy rate", FIG / "figure_08_phi_domain_accuracy", hue="group")

    plt.figure(figsize=(8, 5))
    sns.lineplot(data=latency, x="context", y="mean_seconds", marker="o", linewidth=2.2, color="#4C78A8")
    plt.ylabel("Mean latency, successful generations (s)")
    plt.xlabel("Matched context condition")
    plt.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(FIG / "figure_09_phi_latency_by_context.png", dpi=300)
    plt.savefig(FIG / "figure_09_phi_latency_by_context.pdf")
    plt.close()


def write_report(phi_context: pd.DataFrame, gee_phi: dict, complete: dict, paired: pd.DataFrame, qtype: pd.DataFrame, domain: pd.DataFrame, interactions: pd.DataFrame, token_stats: pd.DataFrame, latency: pd.DataFrame, manifest: dict) -> None:
    def pct(x: float) -> str:
        return "NA" if pd.isna(x) else f"{100*x:.1f}%"

    p4 = phi_context[phi_context.context == "4K"].iloc[0]
    p16 = phi_context[phi_context.context == "16K"].iloc[0]
    long_fail = phi_context[phi_context.context.isin(["32K", "64K", "82K"])]["runtime_failures"].sum()
    sig_pairs = paired[(paired.get("estimable", False) == True) & (paired.get("significant_after_holm_0_05", False) == True)]
    report = [
        "# Experiment F -- Phi-4-mini-instruct Cross-Model Replication",
        "",
        "## Executive Summary",
        "",
        f"Experiment F attempted all 3,000 frozen benchmark instances with `microsoft/Phi-4-mini-instruct` pinned to revision `{MODEL_REVISION}`. Under the required BF16, greedy, no-offload, cached Transformers configuration on the RTX 4090, Phi completed the 4K, 8K, and 16K matched context conditions and reproducibly failed with CUDA OOM at 32K, 64K, and 82K. Runtime failures are not counted as factual inaccuracies.",
        "",
        f"Across successful factual runs, inaccuracy increased from {pct(p4.inaccuracy_rate)} at 4K to {pct(p16.inaccuracy_rate)} at 16K. The primary GEE over successful Phi outputs estimated OR={gee_phi.get('odds_ratio_per_2x_context', float('nan')):.3f} per true doubling of rendered Phi tokens, 95% CI [{gee_phi.get('odds_ratio_ci_low', float('nan')):.3f}, {gee_phi.get('odds_ratio_ci_high', float('nan')):.3f}], p={gee_phi.get('p_value', float('nan')):.3g}. This supports increasing factual inaccuracy over the feasible 4K-16K range, but the full six-condition Phi factual trend is not estimable on this hardware because {int(long_fail)} long-context attempts ended as runtime failures.",
        "",
        "## Design",
        "",
        f"The frozen benchmark hash was `{BENCHMARK_HASH}` and the frozen deterministic grader hash was `{GRADER_HASH}`. The benchmark contains 500 question families crossed with six matched context conditions: 4K, 8K, 16K, 32K, 64K, and 82K. Domains were balanced across SEC, FDA / Drugs@FDA, ClinicalTrials, and FRED / ALFRED. The primary outcome is binary: `CORRECT` is Accurate; every other successfully generated factual-task grade is Inaccurate. Runtime failures are analyzed separately.",
        "",
        "## Phi Context Results",
        "",
        phi_context.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## Primary GEE",
        "",
        pd.DataFrame([gee_phi]).to_markdown(index=False, floatfmt=".6g"),
        "",
        "A +1 change in `log2(rendered_input_tokens)` represents a true doubling of rendered Phi input tokens.",
        "",
        "## Complete-Case Sensitivity",
        "",
        pd.DataFrame([complete]).to_markdown(index=False, floatfmt=".6g"),
        "",
        "## Paired McNemar Tests",
        "",
        paired.to_markdown(index=False, floatfmt=".6g"),
        "",
        "## Exploratory Question-Type Results",
        "",
        qtype.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## Exploratory Domain Results",
        "",
        domain.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## Latency",
        "",
        latency.to_markdown(index=False, floatfmt=".4f"),
        "",
        "## Three-Model Comparison",
        "",
        interactions.to_markdown(index=False, floatfmt=".6g"),
        "",
        "The three-model interaction analysis uses actual rendered token counts for each model and native prompt template. Because Phi has no successful factual observations at 32K, 64K, or 82K on this RTX 4090 under protocol settings, Phi slope comparisons are limited by non-overlapping long-context support and should be interpreted as available-case comparisons rather than a complete six-condition behavioral replication.",
        "",
        "## Required Questions",
        "",
        f"1. Does Phi factual accuracy decline with increasing context? Yes over successful 4K-16K runs: accuracy changed from {pct(p4.accurate_rate)} at 4K to {pct(p16.accurate_rate)} at 16K. The 32K-82K factual outcomes were not observable because of runtime OOM.",
        "2. Accurate/Inaccurate rates at each context condition are listed in the Phi Context Results table; long-context rates are NA because runtime failures are separate from factual outcomes.",
        f"3. Phi's OR per true doubling of rendered input was {gee_phi.get('odds_ratio_per_2x_context', float('nan')):.3f} over successful outputs.",
        f"4. The trend p-value was {gee_phi.get('p_value', float('nan')):.3g}.",
        f"5. Significant Holm-corrected paired comparisons: {', '.join(sig_pairs['comparison'].tolist()) if len(sig_pairs) else 'none among estimable comparisons'}.",
        f"6. Complete-case analysis: {complete.get('reason', 'see table') if not complete.get('estimable', False) else 'see table'}.",
        "7. Question-type patterns are exploratory and listed above.",
        "8. Domain patterns are exploratory and listed above.",
        "9. Phi-vs-Llama slope comparison is reported in the interaction table.",
        "10. Phi-vs-Qwen slope comparison is reported in the interaction table.",
        "11. The joint three-model context-slope test is reported in the interaction table.",
        "12. The central degradation result replicated over Phi's feasible 4K-16K factual range, but a complete six-condition Phi behavioral replication was blocked by hardware/runtime OOM at 32K and above under the required configuration.",
        "",
        "## Runtime and Deviations",
        "",
        "Material deviation/blocker: Phi rendered prompts were within the model's declared context window, but the RTX 4090 could not execute the 32K, 64K, or 82K conditions with BF16, use_cache=True, no quantization, and no offloading. The protocol prohibited shortening, quantizing, or offloading to salvage these instances. Each runtime failure was kept separate from factual accuracy.",
        "",
        "## Reproducibility Manifest Summary",
        "",
        "```json",
        json.dumps(manifest, indent=2, sort_keys=True)[:12000],
        "```",
    ]
    (OUT / "EXPERIMENT_F_REPORT.md").write_text("\n".join(report) + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)

    phi = load_scored(PHI_CSV, "phi4mini")
    llama = load_scored(LLAMA_CSV, "llama32_3b")
    qwen = load_scored(QWEN_CSV, "qwen35_2b")
    phi_failures = load_failures(PHI_FAILURES)
    llama_failures = load_failures(LLAMA_FAILURES)
    qwen_failures = load_failures(QWEN_FAILURES)
    token_stats = token_stats_from_inference()

    if int(len(phi) + len(phi_failures)) != 3000:
        raise SystemExit(f"Phi scored+failure coverage is {len(phi) + len(phi_failures)}, expected 3000")

    phi_context = context_accuracy(phi, phi_failures, token_stats)
    gee_phi = fit_gee(phi, label="phi_primary")
    complete_fams = phi.groupby("question_family_id")["context_length_label"].nunique()
    complete_ids = complete_fams[complete_fams == 6].index
    complete_df = phi[phi["question_family_id"].isin(complete_ids)]
    complete = fit_gee(complete_df, label="complete_case")
    complete["complete_families"] = int(len(complete_ids))
    if len(complete_ids) == 0:
        complete.update({"estimable": False, "reason": "no question families had successful outputs at all six conditions"})
    paired = paired_tests(phi)
    qtype = subgroup(phi, "question_type")
    domain = subgroup(phi, "domain")
    latency = latency_stats(phi)

    gee_llama = fit_gee(llama, label="llama_primary")
    gee_qwen = fit_gee(qwen, label="qwen_primary")
    gee_rows = pd.DataFrame([gee_llama, gee_qwen, gee_phi, complete])
    combined = pd.concat([llama, qwen, phi], ignore_index=True)
    three_context = model_context_table([llama, qwen, phi], {
        "llama32_3b": llama_failures,
        "qwen35_2b": qwen_failures,
        "phi4mini": phi_failures,
    })
    interaction_rows = [
        pairwise_interaction(combined, "llama32_3b", "phi4mini"),
        pairwise_interaction(combined, "qwen35_2b", "phi4mini"),
        joint_interaction(combined),
    ]
    interactions = pd.DataFrame(interaction_rows)

    phi_context.to_csv(OUT / "phi_context_accuracy.csv", index=False)
    gee_rows.to_csv(OUT / "phi_primary_gee.csv", index=False)
    paired.to_csv(OUT / "phi_paired_tests.csv", index=False)
    pd.DataFrame([complete]).to_csv(OUT / "phi_complete_case_analysis.csv", index=False)
    qtype.to_csv(OUT / "phi_question_type_results.csv", index=False)
    domain.to_csv(OUT / "phi_domain_results.csv", index=False)
    token_stats.to_csv(OUT / "phi_token_count_statistics.csv", index=False)
    latency.to_csv(OUT / "phi_latency_statistics.csv", index=False)
    three_context.to_csv(OUT / "three_model_condition_comparison.csv", index=False)
    interactions.to_csv(OUT / "three_model_gee_interaction_analysis.csv", index=False)
    combined[["model", "model_label", "instance_id", "question_family_id", "context_length_label", "domain", "question_type", "answer_correct", "accurate", "inaccurate", "input_tokens", "context_log2"]].to_csv(OUT / "three_model_longform.csv", index=False)

    make_figures(phi, phi_context, qtype, domain, three_context, gee_rows, latency)

    inference_manifest = load_json(PHI_INFERENCE / "run_manifest.json")
    run_summary = load_json(PHI_INFERENCE / "run_summary.json")
    grading_summary = load_json(Path("data/grading_experiment_f_phi4mini_v1/grading_summary.json"))
    manifest = {
        "experiment": "Experiment F -- Phi-4-mini-instruct Cross-Model Replication",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_id": "microsoft/Phi-4-mini-instruct",
        "model_revision": MODEL_REVISION,
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": inference_manifest.get("prompt_hash"),
        "benchmark_hash": BENCHMARK_HASH,
        "grader_hash": GRADER_HASH,
        "python": platform.python_version(),
        "packages": {
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "statsmodels": statsmodels.__version__,
            "matplotlib": matplotlib.__version__,
            "seaborn": sns.__version__,
        },
        "inference_summary": run_summary,
        "grading_summary": grading_summary,
        "runtime_failure_policy": "Runtime failures are separate from factual inaccuracies.",
        "primary_outcome": "INACCURATE = successful grade != CORRECT",
    }
    write_report(phi_context, gee_phi, complete, paired, qtype, domain, interactions, token_stats, latency, manifest)

    files = [p for p in OUT.rglob("*") if p.is_file() and p.name not in {"artifact_hashes.json", "run_manifest.json"}]
    hashes = {str(p.relative_to(OUT)): sha256(p) for p in sorted(files)}
    (OUT / "artifact_hashes.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n")
    manifest["artifact_hashes_sha256"] = hashes
    (OUT / "run_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    print(json.dumps({
        "analysis_dir": str(OUT),
        "phi_successful": int(len(phi)),
        "phi_runtime_failures": int(len(phi_failures)),
        "primary_or": gee_phi.get("odds_ratio_per_2x_context"),
        "primary_p": gee_phi.get("p_value"),
    }, indent=2))


if __name__ == "__main__":
    main()
