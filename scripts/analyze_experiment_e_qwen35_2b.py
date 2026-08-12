#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import platform
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
import seaborn as sns
import statsmodels
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.contingency_tables import mcnemar
from statsmodels.stats.multitest import multipletests


QWEN_CSV = Path("data/grading_experiment_e_qwen35_2b_v1/scored_results.csv")
QWEN_FAILURES = Path("data/grading_experiment_e_qwen35_2b_v1/runtime_failures.jsonl")
QWEN_INFERENCE = Path("data/inference_qwen35_2b_500f_6ctx_v1")
LLAMA_CSV = Path("data/grading_experiment_d_final_v1/final_scored_results.csv")
LLAMA_FAILURES = Path("data/grading_experiment_d_final_v1/runtime_failures.jsonl")
OUT = Path("data/analysis_experiment_e_qwen35_2b_v1")
FIG = OUT / "figures"
CONTEXTS = ["4K", "8K", "16K", "32K", "64K", "82K"]
GRADER_HASH = "d9282a0ccc50daba3bfd232c058dfbab63a5c19a7323d585a7c2236b3a6c4ba8"
BENCHMARK_HASH = "dc2c4194dedb090198e6883735257908ce274bebc8611b40d958dbd026aa1fe6"
BOOT_SEED = 20260812
BOOT_REPS = 3000


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_failures(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_scored(path: Path, model: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    for col in ["answer_correct", "hallucination"]:
        df[col] = df[col].map(lambda x: str(x).lower() == "true")
    if "manual_adjudication" in df.columns:
        df["manual_adjudication"] = df["manual_adjudication"].map(lambda x: str(x).lower() == "true")
    else:
        df["manual_adjudication"] = False
    df["model"] = model
    df["context_length_label"] = pd.Categorical(df["context_length_label"], CONTEXTS, ordered=True)
    df["inaccurate"] = (~df["answer_correct"]).astype(int)
    df["hallucinatory_inaccuracy"] = ((~df["answer_correct"]) & df["hallucination"]).astype(int)
    df["grounded_inaccuracy"] = ((~df["answer_correct"]) & (~df["hallucination"])).astype(int)
    df["correct"] = df["answer_correct"].astype(int)
    df["context_log2"] = np.log2(df["input_tokens"].astype(float))
    return df


def integrity(df: pd.DataFrame, failures: list[dict]) -> dict:
    checks = {
        "rows": int(len(df)),
        "unique_instance_ids": int(df["instance_id"].nunique()),
        "families": int(df["question_family_id"].nunique()),
        "runtime_failures": len(failures),
        "context_counts": {str(k): int(v) for k, v in df["context_length_label"].value_counts().sort_index().items()},
        "missing_answer_correct": int(df["answer_correct"].isna().sum()),
        "missing_hallucination": int(df["hallucination"].isna().sum()),
        "ambiguous": int((df["error_type"] == "AMBIGUOUS_REVIEW_REQUIRED").sum()),
        "format_failure": int((df["error_type"] == "FORMAT_FAILURE").sum()),
    }
    expected_ids = set(df["instance_id"]) | {f["instance_id"] for f in failures}
    if len(expected_ids) != 3000:
        raise SystemExit(f"Qwen integrity failure, scored+failure coverage != 3000: {checks}")
    if checks["missing_answer_correct"] or checks["missing_hallucination"] or checks["ambiguous"] or checks["format_failure"]:
        raise SystemExit(f"Qwen integrity failure: {checks}")
    return checks


def clustered_bootstrap_cis(df: pd.DataFrame, outcomes: list[str]) -> dict:
    rng = np.random.default_rng(BOOT_SEED)
    families = sorted(df["question_family_id"].unique())
    fam_index = {fam: i for i, fam in enumerate(families)}
    ctx_index = {ctx: i for i, ctx in enumerate(CONTEXTS)}
    den = np.zeros((len(families), len(CONTEXTS)), dtype=float)
    nums = {out: np.zeros((len(families), len(CONTEXTS)), dtype=float) for out in outcomes}
    for (fam, ctx), sub in df.groupby(["question_family_id", "context_length_label"], observed=False):
        if len(sub) == 0:
            continue
        i = fam_index[fam]
        j = ctx_index[str(ctx)]
        den[i, j] = len(sub)
        for out in outcomes:
            nums[out][i, j] = float(sub[out].sum())
    cis = {}
    for ctx in CONTEXTS:
        for out in outcomes:
            cis[(ctx, out)] = {"low": np.nan, "high": np.nan}
    for key in cis:
        vals = []
        for _ in range(BOOT_REPS):
            sampled_idx = rng.integers(0, len(families), size=len(families))
            den_sum = den[sampled_idx].sum(axis=0)
            num_sum = nums[key[1]][sampled_idx].sum(axis=0)
            j = ctx_index[key[0]]
            vals.append(num_sum[j] / den_sum[j] if den_sum[j] else np.nan)
        arr = np.asarray(vals, dtype=float)
        cis[key] = {"low": float(np.nanpercentile(arr, 2.5)), "high": float(np.nanpercentile(arr, 97.5))}
    return cis


def descriptive(df: pd.DataFrame, failures: list[dict]) -> pd.DataFrame:
    cis = clustered_bootstrap_cis(df, ["correct", "inaccurate", "hallucinatory_inaccuracy", "grounded_inaccuracy"])
    failure_counts = Counter(f.get("context_length_label") for f in failures)
    rows = []
    for ctx in CONTEXTS:
        sub = df[df["context_length_label"].astype(str) == ctx]
        rows.append({
            "context": ctx,
            "gradable_n": int(len(sub)),
            "correct_count": int(sub["correct"].sum()),
            "correct_rate": float(sub["correct"].mean()),
            "correct_ci_low": cis[(ctx, "correct")]["low"],
            "correct_ci_high": cis[(ctx, "correct")]["high"],
            "inaccurate_count": int(sub["inaccurate"].sum()),
            "inaccuracy_rate": float(sub["inaccurate"].mean()),
            "inaccuracy_ci_low": cis[(ctx, "inaccurate")]["low"],
            "inaccuracy_ci_high": cis[(ctx, "inaccurate")]["high"],
            "hallucinatory_count": int(sub["hallucinatory_inaccuracy"].sum()),
            "hallucinatory_rate": float(sub["hallucinatory_inaccuracy"].mean()),
            "hallucinatory_ci_low": cis[(ctx, "hallucinatory_inaccuracy")]["low"],
            "hallucinatory_ci_high": cis[(ctx, "hallucinatory_inaccuracy")]["high"],
            "grounded_count": int(sub["grounded_inaccuracy"].sum()),
            "grounded_rate": float(sub["grounded_inaccuracy"].mean()),
            "grounded_ci_low": cis[(ctx, "grounded_inaccuracy")]["low"],
            "grounded_ci_high": cis[(ctx, "grounded_inaccuracy")]["high"],
            "runtime_failures": int(failure_counts.get(ctx, 0)),
            "mean_latency": float(sub["generation_latency_seconds"].mean()),
            "mean_input_tokens": float(sub["input_tokens"].mean()),
            "median_input_tokens": float(sub["input_tokens"].median()),
        })
    return pd.DataFrame(rows)


def fit_gee(df: pd.DataFrame, outcome: str, predictor: str = "context_log2", label: str | None = None) -> dict:
    result = smf.gee(
        f"{outcome} ~ {predictor}",
        groups="question_family_id",
        data=df,
        family=sm.families.Binomial(),
        cov_struct=sm.cov_struct.Exchangeable(),
    ).fit()
    coef = float(result.params[predictor])
    se = float(result.bse[predictor])
    lo, hi = result.conf_int().loc[predictor].tolist()
    return {
        "outcome": label or outcome,
        "predictor": predictor,
        "formula": f"{outcome} ~ {predictor}",
        "working_correlation": "Exchangeable",
        "n_observations": int(result.nobs),
        "n_families": int(df["question_family_id"].nunique()),
        "coefficient": coef,
        "robust_se": se,
        "odds_ratio_per_2x_context": float(math.exp(coef)),
        "odds_ratio_ci_low": float(math.exp(lo)),
        "odds_ratio_ci_high": float(math.exp(hi)),
        "p_value": float(result.pvalues[predictor]),
        "converged": bool(getattr(result, "converged", True)),
    }


def paired_tests(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for outcome in ["inaccurate", "hallucinatory_inaccuracy", "grounded_inaccuracy"]:
        raw_rows = []
        wide = df.pivot(index="question_family_id", columns="context_length_label", values=outcome)
        for ctx in ["8K", "16K", "32K", "64K", "82K"]:
            pair = wide[["4K", ctx]].dropna()
            a = pair["4K"].astype(int)
            b = pair[ctx].astype(int)
            n01 = int(((a == 0) & (b == 1)).sum())
            n10 = int(((a == 1) & (b == 0)).sum())
            table = [[int(((a == 0) & (b == 0)).sum()), n01], [n10, int(((a == 1) & (b == 1)).sum())]]
            res = mcnemar(table, exact=True)
            raw_rows.append({
                "outcome": outcome,
                "comparison": f"4K_vs_{ctx}",
                "paired_n": int(len(pair)),
                "event_rate_4K": float(a.mean()),
                "event_rate_comparison": float(b.mean()),
                "absolute_percentage_point_difference": float((b.mean() - a.mean()) * 100),
                "discordant_4K0_cmp1": n01,
                "discordant_4K1_cmp0": n10,
                "raw_p_value": float(res.pvalue),
            })
        _, adjusted, _, _ = multipletests([r["raw_p_value"] for r in raw_rows], method="holm")
        for r, adj in zip(raw_rows, adjusted):
            r["holm_adjusted_p_value"] = float(adj)
            r["significant_after_holm_0_05"] = bool(adj < 0.05)
            rows.append(r)
    return pd.DataFrame(rows)


def subgroup_table(df: pd.DataFrame, by: str) -> pd.DataFrame:
    rows = []
    for (group, ctx), sub in df.groupby([by, "context_length_label"], observed=False):
        if len(sub) == 0:
            continue
        rows.append({
            by: group,
            "context": str(ctx),
            "n": int(len(sub)),
            "correct_rate": float(sub["correct"].mean()),
            "inaccuracy_rate": float(sub["inaccurate"].mean()),
            "hallucinatory_rate": float(sub["hallucinatory_inaccuracy"].mean()),
            "grounded_rate": float(sub["grounded_inaccuracy"].mean()),
        })
    return pd.DataFrame(rows)


def error_type_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    error_types = [
        "UNSUPPORTED_VALUE", "FAILED_TO_ABSTAIN", "WRONG_ENTITY", "WRONG_PERIOD", "WRONG_VERSION",
        "WRONG_FIELD", "WRONG_UNIT", "WRONG_SERIES_VARIANT", "CALCULATION_ERROR", "UNNECESSARY_ABSTENTION",
    ]
    for ctx in CONTEXTS:
        sub = df[df["context_length_label"].astype(str) == ctx]
        n = len(sub)
        for err in error_types:
            count = int((sub["error_type"] == err).sum())
            rows.append({"context": ctx, "error_type": err, "count": count, "rate_of_gradable": count / n if n else np.nan})
    return pd.DataFrame(rows)


def token_count_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ctx in CONTEXTS:
        vals = df.loc[df["context_length_label"].astype(str) == ctx, "input_tokens"].astype(float)
        rows.append({
            "context": ctx,
            "n": int(vals.count()),
            "mean": float(vals.mean()),
            "median": float(vals.median()),
            "sd": float(vals.std(ddof=1)),
            "min": int(vals.min()),
            "max": int(vals.max()),
        })
    return pd.DataFrame(rows)


def latency_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ctx in CONTEXTS:
        sub = df[df["context_length_label"].astype(str) == ctx]
        lat = sub["generation_latency_seconds"].astype(float)
        rows.append({
            "context": ctx,
            "n_successful": int(len(sub)),
            "mean_latency": float(lat.mean()),
            "median_latency": float(lat.median()),
            "sd_latency": float(lat.std(ddof=1)),
            "p95_latency": float(lat.quantile(0.95)),
            "total_latency": float(lat.sum()),
            "mean_input_tokens": float(sub["input_tokens"].mean()),
            "mean_generated_tokens": float(sub["generated_tokens_count"].mean()),
            "max_peak_allocated_vram_gib": float(sub["peak_allocated_vram_bytes"].max() / (1024**3)),
            "max_peak_reserved_vram_gib": float(sub["peak_reserved_vram_bytes"].max() / (1024**3)),
        })
    return pd.DataFrame(rows)


def complete_case(df: pd.DataFrame) -> dict:
    complete_families = df.groupby("question_family_id", observed=False)["context_length_label"].nunique().loc[lambda s: s == 6].index
    complete = df[df["question_family_id"].isin(complete_families)].copy()
    return {
        "complete_case_family_count": int(len(complete_families)),
        "complete_case_observations": int(len(complete)),
        "complete_case": [fit_gee(complete, out) for out in ["inaccurate", "hallucinatory_inaccuracy", "grounded_inaccuracy"]],
    }


def interaction_model(combined: pd.DataFrame, outcome: str) -> dict:
    tmp = combined.copy()
    tmp["model"] = pd.Categorical(tmp["model"], ["llama32_3b", "qwen35_2b"])
    tmp["cluster_id"] = tmp["question_family_id"].astype(str)
    result = smf.gee(
        f"{outcome} ~ context_log2 * C(model)",
        groups="cluster_id",
        data=tmp,
        family=sm.families.Binomial(),
        cov_struct=sm.cov_struct.Exchangeable(),
    ).fit()
    term = "context_log2:C(model)[T.qwen35_2b]"
    coef = float(result.params[term])
    lo, hi = result.conf_int().loc[term].tolist()
    return {
        "outcome": outcome,
        "formula": f"{outcome} ~ context_log2 * C(model)",
        "interaction_term": term,
        "interaction_coefficient_qwen_minus_llama": coef,
        "interaction_or_ratio": float(math.exp(coef)),
        "ci_low": float(math.exp(lo)),
        "ci_high": float(math.exp(hi)),
        "p_value": float(result.pvalues[term]),
        "n_observations": int(result.nobs),
        "n_families": int(tmp["question_family_id"].nunique()),
    }


def save_plot(fig: plt.Figure, name: str) -> None:
    fig.tight_layout()
    fig.savefig(FIG / f"{name}.png", dpi=220)
    fig.savefig(FIG / f"{name}.pdf")
    plt.close(fig)


def plots(qwen: pd.DataFrame, primary: pd.DataFrame, err: pd.DataFrame, qt: pd.DataFrame, dom: pd.DataFrame, latency: pd.DataFrame, trend: dict, llama_primary: pd.DataFrame, combined: pd.DataFrame) -> None:
    sns.set_theme(style="whitegrid", context="paper")
    palette = {"Correct": "#4C78A8", "Hallucinatory Inaccuracy": "#E45756", "Grounded Inaccuracy": "#72B7B2"}
    x = np.arange(len(CONTEXTS))
    fig, ax = plt.subplots(figsize=(8, 4.6))
    bottom = np.zeros(len(CONTEXTS))
    for label, col in [("Correct", "correct_rate"), ("Hallucinatory Inaccuracy", "hallucinatory_rate"), ("Grounded Inaccuracy", "grounded_rate")]:
        vals = primary[col].values
        ax.bar(x, vals * 100, bottom=bottom * 100, label=label, color=palette[label])
        bottom += vals
    ax.set_xticks(x, CONTEXTS)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Percent of gradable responses")
    ax.set_title("Qwen factual reliability decomposition")
    ax.legend(loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.16), frameon=False)
    save_plot(fig, "figure_01_qwen_factual_reliability_decomposition")

    def rate_plot(name: str, rate_col: str, lo_col: str, hi_col: str, ylabel: str, key: str, color: str):
        fig, ax = plt.subplots(figsize=(7, 4.2))
        y = primary[rate_col].values * 100
        yerr = np.vstack([(primary[rate_col] - primary[lo_col]).values * 100, (primary[hi_col] - primary[rate_col]).values * 100])
        ax.errorbar(CONTEXTS, y, yerr=yerr, marker="o", capsize=4, linewidth=2, color=color)
        ax.set_ylim(0, 100)
        ax.set_ylabel(ylabel)
        ax.set_xlabel("Context condition")
        res = trend[key]
        ax.set_title(f"Qwen {ylabel}\nOR per 2x={res['odds_ratio_per_2x_context']:.3f}, p={res['p_value']:.3g}")
        save_plot(fig, name)

    rate_plot("figure_02_qwen_overall_inaccuracy", "inaccuracy_rate", "inaccuracy_ci_low", "inaccuracy_ci_high", "Inaccuracy rate (%)", "inaccurate", "#E45756")
    rate_plot("figure_03_qwen_hallucinatory_inaccuracy", "hallucinatory_rate", "hallucinatory_ci_low", "hallucinatory_ci_high", "Hallucinatory rate (%)", "hallucinatory_inaccuracy", "#F58518")
    rate_plot("figure_04_qwen_grounded_inaccuracy", "grounded_rate", "grounded_ci_low", "grounded_ci_high", "Grounded rate (%)", "grounded_inaccuracy", "#72B7B2")

    ans = qwen[qwen["question_type"] != "UNANSWERABLE"].copy()
    ans_tab = descriptive(ans, [])
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot(CONTEXTS, ans_tab["hallucinatory_rate"] * 100, marker="o", label="Answerable only hallucination")
    ax.plot(CONTEXTS, primary["hallucinatory_rate"] * 100, marker="o", label="Full dataset hallucination")
    ax.set_ylabel("Rate (%)")
    ax.set_xlabel("Context condition")
    ax.set_ylim(0, 100)
    ax.legend(frameon=False)
    ax.set_title("Qwen answerable-only hallucination sensitivity")
    save_plot(fig, "figure_05_qwen_answerable_only_sensitivity")

    fig, ax = plt.subplots(figsize=(10, 5.3))
    err.pivot(index="context", columns="error_type", values="rate_of_gradable").loc[CONTEXTS].plot(kind="bar", stacked=True, ax=ax, colormap="tab20")
    ax.set_ylabel("Rate of gradable responses")
    ax.set_title("Qwen detailed error evolution")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    save_plot(fig, "figure_06_qwen_detailed_error_evolution")

    for name, data, hue, title in [
        ("figure_07_qwen_question_type_results", qt, "question_type", "Qwen inaccuracy by question type"),
        ("figure_08_qwen_domain_results", dom, "domain", "Qwen inaccuracy by domain"),
    ]:
        fig, ax = plt.subplots(figsize=(9, 4.8))
        sns.lineplot(data=data, x="context", y="inaccuracy_rate", hue=hue, marker="o", ax=ax)
        ax.set_ylim(0, 1)
        ax.set_ylabel("Inaccuracy rate")
        ax.set_title(title)
        ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
        save_plot(fig, name)

    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    sns.scatterplot(data=qwen, x="input_tokens", y="generation_latency_seconds", hue="context_length_label", alpha=0.35, ax=ax)
    sns.lineplot(data=latency, x="mean_input_tokens", y="mean_latency", marker="o", color="black", ax=ax, label="Context mean")
    ax.set_xscale("log", base=2)
    ax.set_xlabel("Qwen rendered input tokens")
    ax.set_ylabel("Latency (s)")
    ax.set_title("Qwen latency vs rendered context tokens")
    save_plot(fig, "figure_09_qwen_latency")

    for name, col, title in [
        ("figure_10_llama_vs_qwen_overall_inaccuracy", "inaccurate", "Overall inaccuracy"),
        ("figure_11_llama_vs_qwen_grounded_inaccuracy", "grounded_inaccuracy", "Grounded inaccuracy"),
        ("figure_12_llama_vs_qwen_hallucinatory_inaccuracy", "hallucinatory_inaccuracy", "Hallucinatory inaccuracy"),
    ]:
        tab = combined.groupby(["model", "context_length_label"], observed=False)[col].mean().reset_index()
        fig, ax = plt.subplots(figsize=(7.5, 4.4))
        sns.lineplot(data=tab, x="context_length_label", y=col, hue="model", marker="o", ax=ax)
        ax.set_ylim(0, 1)
        ax.set_ylabel("Rate")
        ax.set_xlabel("Condition-matched context")
        ax.set_title(f"Llama vs Qwen: {title}")
        save_plot(fig, name)

    ans_comb = combined[combined["question_type"] != "UNANSWERABLE"].copy()
    tab = ans_comb.groupby(["model", "context_length_label"], observed=False)["hallucinatory_inaccuracy"].mean().reset_index()
    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    sns.lineplot(data=tab, x="context_length_label", y="hallucinatory_inaccuracy", hue="model", marker="o", ax=ax)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Answerable-only hallucination rate")
    ax.set_title("Llama vs Qwen answerable-only hallucination")
    save_plot(fig, "figure_13_llama_vs_qwen_answerable_only_hallucination")

    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    sns.regplot(data=combined[combined["model"] == "llama32_3b"], x="context_log2", y="inaccurate", logistic=True, scatter=False, ax=ax, label="Llama")
    sns.regplot(data=combined[combined["model"] == "qwen35_2b"], x="context_log2", y="inaccurate", logistic=True, scatter=False, ax=ax, label="Qwen")
    ax.set_xlabel("log2(actual rendered input tokens)")
    ax.set_ylabel("Fitted inaccuracy probability")
    ax.legend(frameon=False)
    ax.set_title("Cross-model slope comparison")
    save_plot(fig, "figure_14_cross_model_slope_comparison")


def fmt_p(p: float) -> str:
    return f"{p:.3e}" if p < 1e-4 else f"{p:.4f}"


def report(primary: pd.DataFrame, trend: dict, ans: dict, complete: dict, paired: pd.DataFrame, qt: pd.DataFrame, dom: pd.DataFrame, err: pd.DataFrame, latency: pd.DataFrame, interactions: list[dict], manifest: dict) -> str:
    lines = ["# Experiment E Qwen3.5-2B Report", ""]
    lines += [
        f"- model revision: `{manifest['model_revision']}`",
        f"- prompt version/hash: `{manifest['prompt_version']}` / `{manifest['prompt_hash']}`",
        f"- benchmark hash: `{manifest['benchmark_hash']}`",
        f"- successful/runtime failures: `{manifest['successful']}` / `{manifest['runtime_failures']}`",
        "",
        "## Context Results",
        "",
        primary[["context", "gradable_n", "correct_rate", "inaccuracy_rate", "hallucinatory_rate", "grounded_rate", "mean_input_tokens", "mean_latency"]].to_markdown(index=False),
        "",
        "## Primary GEE",
        "",
    ]
    gee_rows = []
    for key in ["inaccurate", "hallucinatory_inaccuracy", "grounded_inaccuracy"]:
        r = trend[key]
        gee_rows.append({"outcome": key, "OR": r["odds_ratio_per_2x_context"], "CI_low": r["odds_ratio_ci_low"], "CI_high": r["odds_ratio_ci_high"], "p": r["p_value"]})
    lines += [pd.DataFrame(gee_rows).to_markdown(index=False), ""]
    lines += ["## Answerable-Only Sensitivity", "", pd.DataFrame(ans["exclude_unanswerable"]).to_markdown(index=False), ""]
    lines += ["## Complete Case", "", f"Complete families: `{complete['complete_case_family_count']}`; observations: `{complete['complete_case_observations']}`.", pd.DataFrame(complete["complete_case"]).to_markdown(index=False), ""]
    sig = paired[paired["significant_after_holm_0_05"]]
    lines += ["## Paired Tests", "", sig.to_markdown(index=False) if len(sig) else "No Holm-significant paired tests.", ""]
    e4 = err[err["context"] == "4K"].set_index("error_type")
    e82 = err[err["context"] == "82K"].set_index("error_type")
    delta = (e82["rate_of_gradable"] - e4["rate_of_gradable"]).sort_values(key=lambda s: s.abs(), ascending=False)
    lines += ["## Largest Error Changes 4K To 82K", "", delta.reset_index(name="rate_delta").head(10).to_markdown(index=False), ""]
    lines += ["## Question Types And Domains", "", "Full exploratory tables are saved as CSV files. Largest question-type/domain patterns should be interpreted descriptively.", ""]
    lines += ["## Cross-Model Interactions", "", pd.DataFrame(interactions).to_markdown(index=False), ""]
    lines += ["## Key Answers", ""]
    q = {
        "Does factual inaccuracy increase?": trend["inaccurate"],
        "Does grounded inaccuracy increase?": trend["grounded_inaccuracy"],
        "Does full-dataset hallucinatory inaccuracy increase?": trend["hallucinatory_inaccuracy"],
    }
    for text, r in q.items():
        direction = "increases" if r["odds_ratio_per_2x_context"] > 1 else "decreases"
        lines.append(f"- {text} Qwen {direction}: OR `{r['odds_ratio_per_2x_context']:.3f}`, p `{fmt_p(r['p_value'])}`.")
    for r in ans["exclude_unanswerable"]:
        if r["outcome"] == "hallucinatory_inaccuracy":
            direction = "increases" if r["odds_ratio_per_2x_context"] > 1 else "decreases"
            lines.append(f"- After excluding UNANSWERABLE, hallucination {direction}: OR `{r['odds_ratio_per_2x_context']:.3f}`, p `{fmt_p(r['p_value'])}`.")
    fta = err[err["error_type"] == "FAILED_TO_ABSTAIN"].set_index("context")
    lines.append(f"- Failure to abstain changes from `{fta.loc['4K','rate_of_gradable']:.3f}` at 4K to `{fta.loc['82K','rate_of_gradable']:.3f}` at 82K.")
    lines.append("- Cross-model slope interaction results are in the table above; tokenization/template differences mean this is a behavioral replication, not an architectural ablation.")
    return "\n".join(lines) + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    qwen = load_scored(QWEN_CSV, "qwen35_2b")
    qwen_failures = load_failures(QWEN_FAILURES)
    checks = integrity(qwen, qwen_failures)
    llama = load_scored(LLAMA_CSV, "llama32_3b")
    llama_failures = load_failures(LLAMA_FAILURES)

    primary = descriptive(qwen, qwen_failures)
    primary.to_csv(OUT / "overall_context_results.csv", index=False)
    primary.to_csv(OUT / "primary_results.csv", index=False)
    trend = {out: fit_gee(qwen, out) for out in ["inaccurate", "hallucinatory_inaccuracy", "grounded_inaccuracy"]}
    pd.DataFrame(trend.values()).to_csv(OUT / "gee_results.csv", index=False)
    (OUT / "gee_results.json").write_text(json.dumps(trend, indent=2, sort_keys=True) + "\n")

    answerable = qwen[qwen["question_type"] != "UNANSWERABLE"].copy()
    ans = {"exclude_unanswerable_observations": int(len(answerable)), "exclude_unanswerable": [fit_gee(answerable, out) for out in ["inaccurate", "hallucinatory_inaccuracy", "grounded_inaccuracy"]]}
    pd.DataFrame(ans["exclude_unanswerable"]).to_csv(OUT / "answerable_only_sensitivity.csv", index=False)
    (OUT / "answerable_only_sensitivity.json").write_text(json.dumps(ans, indent=2, sort_keys=True) + "\n")

    comp = complete_case(qwen)
    pd.DataFrame(comp["complete_case"]).to_csv(OUT / "complete_case_analysis.csv", index=False)
    (OUT / "complete_case_analysis.json").write_text(json.dumps(comp, indent=2, sort_keys=True) + "\n")

    paired = paired_tests(qwen)
    paired.to_csv(OUT / "paired_tests.csv", index=False)
    qt = subgroup_table(qwen, "question_type")
    qt.to_csv(OUT / "question_type_results.csv", index=False)
    dom = subgroup_table(qwen, "domain")
    dom.to_csv(OUT / "domain_results.csv", index=False)
    err = error_type_table(qwen)
    err.to_csv(OUT / "detailed_error_type_results.csv", index=False)
    err.to_csv(OUT / "error_type_by_context.csv", index=False)
    toks = token_count_table(qwen)
    toks.to_csv(OUT / "token_count_statistics.csv", index=False)
    latency = latency_table(qwen)
    latency.to_csv(OUT / "latency_statistics.csv", index=False)

    llama_primary = descriptive(llama, llama_failures)
    llama_primary.to_csv(OUT / "llama_context_results_for_comparison.csv", index=False)
    combined = pd.concat([llama, qwen], ignore_index=True)
    combined.to_csv(OUT / "cross_model_longform.csv", index=False)
    interactions = [interaction_model(combined, out) for out in ["inaccurate", "grounded_inaccuracy", "hallucinatory_inaccuracy"]]
    pd.DataFrame(interactions).to_csv(OUT / "cross_model_interaction_models.csv", index=False)
    comp_rows = []
    for model, df in [("llama32_3b", llama), ("qwen35_2b", qwen)]:
        for out in ["inaccurate", "grounded_inaccuracy", "hallucinatory_inaccuracy"]:
            r = fit_gee(df, out)
            r["model"] = model
            comp_rows.append(r)
    cross = pd.DataFrame(comp_rows)
    cross.to_csv(OUT / "cross_model_comparison.csv", index=False)

    plots(qwen, primary, err, qt, dom, latency, trend, llama_primary, combined)

    inf_manifest = json.loads((QWEN_INFERENCE / "run_manifest.json").read_text())
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_revision": inf_manifest["model_revision"],
        "transformers_version": json.loads((QWEN_INFERENCE / "environment.json").read_text()).get("transformers_version"),
        "prompt_version": inf_manifest["prompt_version"],
        "prompt_hash": inf_manifest["prompt_hash"],
        "benchmark_hash": BENCHMARK_HASH,
        "qwen_scored_dataset": str(QWEN_CSV),
        "qwen_scored_dataset_hash": sha256(QWEN_CSV),
        "llama_scored_dataset": str(LLAMA_CSV),
        "llama_scored_dataset_hash": sha256(LLAMA_CSV),
        "grader_hash": GRADER_HASH,
        "successful": int(len(qwen)),
        "runtime_failures": len(qwen_failures),
        "malformed_outputs": int(json.loads((QWEN_INFERENCE / "integrity_report.json").read_text()).get("malformed_outputs", 0)),
        "context_log2_field": "log2(input_tokens)",
        "gee_specification": "binary_outcome ~ context_log2, clustered by question_family_id",
        "working_correlation": "Exchangeable",
        "package_versions": {
            "python": platform.python_version(),
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "statsmodels": statsmodels.__version__,
            "matplotlib": matplotlib.__version__,
            "seaborn": sns.__version__,
        },
        "integrity": checks,
    }
    (OUT / "run_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    shutil.copyfile(Path(__file__), OUT / "analysis_script.py")

    report_md = report(primary, trend, ans, comp, paired, qt, dom, err, latency, interactions, manifest)
    (OUT / "EXPERIMENT_E_REPORT.md").write_text(report_md)

    artifact_hashes = {}
    for path in sorted(OUT.glob("*")):
        if path.is_file():
            artifact_hashes[path.name] = sha256(path)
    for path in sorted(FIG.glob("*")):
        if path.is_file():
            artifact_hashes[f"figures/{path.name}"] = sha256(path)
    (OUT / "artifact_hashes.json").write_text(json.dumps(artifact_hashes, indent=2, sort_keys=True) + "\n")

    print(json.dumps({"output_dir": str(OUT), "primary": trend, "answerable_only": ans, "interactions": interactions}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
