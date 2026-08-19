#!/usr/bin/env python3
"""Run Experiment D final statistical analysis from the frozen scored dataset."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import platform
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
import scipy.stats as st
import seaborn as sns
import statsmodels
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.contingency_tables import mcnemar
from statsmodels.stats.multitest import multipletests


IN_CSV = Path("data/grading_experiment_d_final_v1/final_scored_results.csv")
RUNTIME_FAILURES = Path("data/grading_experiment_d_final_v1/runtime_failures.jsonl")
DATASET = Path("data/preproduction_llama32_3b_500f_6ctx_v1/instances.jsonl")
OUT = Path("data/analysis_experiment_d_final_v1")
FIG = OUT / "figures"
BOOT_SEED = 20260811
BOOT_REPS = 10000
CONTEXTS = ["4K", "8K", "16K", "32K", "64K", "82K"]
NOMINAL_TOKENS = {"4K": 4096, "8K": 8192, "16K": 16384, "32K": 32768, "64K": 65536, "82K": 81920}
GRADER_HASH = "d9282a0ccc50daba3bfd232c058dfbab63a5c19a7323d585a7c2236b3a6c4ba8"
BENCHMARK_HASH = "dc2c4194dedb090198e6883735257908ce274bebc8611b40d958dbd026aa1fe6"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def p_fmt(p: float) -> str:
    if pd.isna(p):
        return "NA"
    if p < 1e-4:
        return f"{p:.3e}"
    return f"{p:.4f}"


def ci_fmt(lo: float, hi: float) -> str:
    return f"[{lo:.3f}, {hi:.3f}]"


def load_data() -> tuple[pd.DataFrame, list[dict]]:
    df = pd.read_csv(IN_CSV)
    failures = [json.loads(line) for line in RUNTIME_FAILURES.read_text().splitlines() if line.strip()]
    for col in ["answer_correct", "hallucination", "manual_adjudication"]:
        df[col] = df[col].map(lambda x: str(x).lower() == "true")
    df["context_length_label"] = pd.Categorical(df["context_length_label"], CONTEXTS, ordered=True)
    df["inaccurate"] = (~df["answer_correct"]).astype(int)
    df["hallucinatory_inaccuracy"] = ((~df["answer_correct"]) & df["hallucination"]).astype(int)
    df["grounded_inaccuracy"] = ((~df["answer_correct"]) & (~df["hallucination"])).astype(int)
    df["correct"] = df["answer_correct"].astype(int)
    df["context_log2"] = np.log2(df["input_tokens"].astype(float))
    df["nominal_context_log2"] = df["context_length_label"].astype(str).map(lambda x: math.log2(NOMINAL_TOKENS[x])).astype(float)
    df["original_100_subset"] = df["question_family_id"].map(is_original_family)
    return df, failures


def is_original_family(family_id: str) -> bool:
    try:
        suffix = int(family_id.split("_")[-1])
    except Exception:
        return False
    return suffix <= 25


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
        "manual_adjudications": int(df["manual_adjudication"].sum()),
    }
    expected_counts = {"4K": 500, "8K": 500, "16K": 500, "32K": 500, "64K": 500, "82K": 498}
    if checks["rows"] != 2998 or checks["unique_instance_ids"] != 2998 or checks["families"] != 500:
        raise SystemExit(f"Integrity failure: {checks}")
    if checks["context_counts"] != expected_counts:
        raise SystemExit(f"Context-count failure: {checks['context_counts']}")
    if checks["runtime_failures"] != 2 or checks["ambiguous"] != 0 or checks["manual_adjudications"] != 19:
        raise SystemExit(f"Integrity failure: {checks}")
    fam_counts = df.groupby("question_family_id", observed=False)["context_length_label"].nunique()
    if int((fam_counts < 5).sum()) != 0:
        raise SystemExit("Every family should have at least five successful contexts")
    return checks


def clustered_bootstrap_cis(df: pd.DataFrame, outcomes: list[str]) -> dict:
    rng = np.random.default_rng(BOOT_SEED)
    families = sorted(df["question_family_id"].unique())
    fam_index = {fam: i for i, fam in enumerate(families)}
    ctx_index = {ctx: i for i, ctx in enumerate(CONTEXTS)}
    den = np.zeros((len(families), len(CONTEXTS)), dtype=float)
    nums = {out: np.zeros((len(families), len(CONTEXTS)), dtype=float) for out in outcomes}
    grouped = df.groupby(["question_family_id", "context_length_label"], observed=False)
    for (fam, ctx), sub in grouped:
        if len(sub) == 0:
            continue
        i = fam_index[fam]
        j = ctx_index[str(ctx)]
        den[i, j] = len(sub)
        for out in outcomes:
            nums[out][i, j] = float(sub[out].sum())

    samples = {(ctx, out): [] for ctx in CONTEXTS for out in outcomes}
    for _ in range(BOOT_REPS):
        sampled_idx = rng.integers(0, len(families), size=len(families))
        den_sum = den[sampled_idx].sum(axis=0)
        for out in outcomes:
            num_sum = nums[out][sampled_idx].sum(axis=0)
            rates = np.divide(num_sum, den_sum, out=np.full_like(num_sum, np.nan), where=den_sum > 0)
            for ctx, rate in zip(CONTEXTS, rates):
                samples[(ctx, out)].append(float(rate))
    cis = {}
    for key, vals in samples.items():
        arr = np.asarray(vals, dtype=float)
        cis[key] = {
            "low": float(np.nanpercentile(arr, 2.5)),
            "high": float(np.nanpercentile(arr, 97.5)),
        }
    return cis


def descriptive(df: pd.DataFrame, failures: list[dict]) -> pd.DataFrame:
    cis = clustered_bootstrap_cis(df, ["correct", "inaccurate", "hallucinatory_inaccuracy", "grounded_inaccuracy"])
    failure_counts = Counter((f.get("context_length_label") or f.get("context_label")) for f in failures)
    rows = []
    for ctx in CONTEXTS:
        sub = df[df["context_length_label"].astype(str) == ctx]
        n = len(sub)
        row = {
            "context": ctx,
            "gradable_n": n,
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
            "runtime_failure_rate_attempted": float(failure_counts.get(ctx, 0) / (n + failure_counts.get(ctx, 0))),
            "mean_latency": float(sub["generation_latency_seconds"].mean()),
            "mean_input_tokens": float(sub["input_tokens"].mean()),
            "mean_generated_tokens": float(sub["generated_tokens_count"].mean()),
        }
        rows.append(row)
    return pd.DataFrame(rows)


def fit_gee(df: pd.DataFrame, outcome: str, predictor: str = "context_log2", label: str | None = None) -> dict:
    model = smf.gee(
        f"{outcome} ~ {predictor}",
        groups="question_family_id",
        data=df,
        family=sm.families.Binomial(),
        cov_struct=sm.cov_struct.Exchangeable(),
    )
    result = model.fit()
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


def fit_composition_gee(df: pd.DataFrame) -> dict:
    sub = df[df["inaccurate"] == 1].copy()
    sub["hallucinatory_vs_grounded"] = sub["hallucinatory_inaccuracy"]
    return fit_gee(sub, "hallucinatory_vs_grounded", "context_log2", "hallucinatory_vs_grounded_among_inaccurate")


def fit_categorical(df: pd.DataFrame, outcome: str) -> dict:
    tmp = df.copy()
    tmp["context_label_str"] = pd.Categorical(tmp["context_length_label"].astype(str), CONTEXTS, ordered=True)
    model = smf.gee(
        f"{outcome} ~ C(context_label_str, Treatment(reference='4K'))",
        groups="question_family_id",
        data=tmp,
        family=sm.families.Binomial(),
        cov_struct=sm.cov_struct.Exchangeable(),
    )
    result = model.fit()
    rows = []
    for name, coef in result.params.items():
        if name == "Intercept":
            continue
        lo, hi = result.conf_int().loc[name].tolist()
        rows.append(
            {
                "outcome": outcome,
                "term": name,
                "coefficient": float(coef),
                "robust_se": float(result.bse[name]),
                "odds_ratio_vs_4K": float(math.exp(coef)),
                "ci_low": float(math.exp(lo)),
                "ci_high": float(math.exp(hi)),
                "p_value": float(result.pvalues[name]),
            }
        )
    try:
        wt = result.wald_test_terms(skip_single=False)
        omnibus_p = float(wt.table.loc["C(context_label_str, Treatment(reference='4K'))", "pvalue"])
    except Exception:
        omnibus_p = float("nan")
    return {"rows": rows, "omnibus_p_value": omnibus_p}


def paired_tests(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    outcomes = {
        "inaccurate": "inaccurate",
        "hallucinatory_inaccuracy": "hallucinatory_inaccuracy",
        "grounded_inaccuracy": "grounded_inaccuracy",
    }
    for outcome, col in outcomes.items():
        raw_rows = []
        wide = df.pivot(index="question_family_id", columns="context_length_label", values=col)
        for ctx in ["8K", "16K", "32K", "64K", "82K"]:
            pair = wide[["4K", ctx]].dropna()
            a = pair["4K"].astype(int)
            b = pair[ctx].astype(int)
            n01 = int(((a == 0) & (b == 1)).sum())
            n10 = int(((a == 1) & (b == 0)).sum())
            table = [[int(((a == 0) & (b == 0)).sum()), n01], [n10, int(((a == 1) & (b == 1)).sum())]]
            res = mcnemar(table, exact=True)
            raw_rows.append(
                {
                    "outcome": outcome,
                    "comparison": f"4K_vs_{ctx}",
                    "paired_n": int(len(pair)),
                    "event_rate_4K": float(a.mean()),
                    "event_rate_comparison": float(b.mean()),
                    "absolute_percentage_point_difference": float((b.mean() - a.mean()) * 100),
                    "discordant_4K0_cmp1": n01,
                    "discordant_4K1_cmp0": n10,
                    "raw_p_value": float(res.pvalue),
                }
            )
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
        rows.append(
            {
                by: group,
                "context": str(ctx),
                "n": int(len(sub)),
                "correct_rate": float(sub["correct"].mean()),
                "inaccuracy_rate": float(sub["inaccurate"].mean()),
                "hallucinatory_rate": float(sub["hallucinatory_inaccuracy"].mean()),
                "grounded_rate": float(sub["grounded_inaccuracy"].mean()),
            }
        )
    return pd.DataFrame(rows)


def interaction_model(df: pd.DataFrame, outcome: str, factor: str) -> dict:
    try:
        result = smf.gee(
            f"{outcome} ~ context_log2 * C({factor})",
            groups="question_family_id",
            data=df,
            family=sm.families.Binomial(),
            cov_struct=sm.cov_struct.Exchangeable(),
        ).fit()
        wt = result.wald_test_terms(skip_single=False)
        interaction_term = f"context_log2:C({factor})"
        p = float(wt.table.loc[interaction_term, "pvalue"]) if interaction_term in wt.table.index else float("nan")
        return {
            "outcome": outcome,
            "factor": factor,
            "formula": f"{outcome} ~ context_log2 * C({factor})",
            "interaction_p_value": p,
            "converged": bool(getattr(result, "converged", True)),
        }
    except Exception as exc:
        return {"outcome": outcome, "factor": factor, "error": repr(exc), "converged": False}


def error_type_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    error_types = [
        "UNSUPPORTED_VALUE",
        "FAILED_TO_ABSTAIN",
        "WRONG_ENTITY",
        "WRONG_PERIOD",
        "WRONG_VERSION",
        "WRONG_FIELD",
        "WRONG_UNIT",
        "WRONG_SERIES_VARIANT",
        "CALCULATION_ERROR",
        "UNNECESSARY_ABSTENTION",
    ]
    for ctx in CONTEXTS:
        sub = df[df["context_length_label"].astype(str) == ctx]
        n = len(sub)
        for err in error_types:
            count = int((sub["error_type"] == err).sum())
            rows.append({"context": ctx, "error_type": err, "count": count, "rate_of_gradable": count / n})
    return pd.DataFrame(rows)


def family_transitions(df: pd.DataFrame) -> pd.DataFrame:
    rows = []

    def classify(seq: list[int | None], event_name: str) -> str:
        vals = [v for v in seq if v is not None]
        if all(v == 0 for v in vals):
            return f"never_{event_name}"
        if all(v == 1 for v in vals):
            return f"{event_name}_all_available_contexts"
        first = next((i for i, v in enumerate(seq) if v == 1), None)
        if first is None:
            return f"never_{event_name}"
        later = [v for v in seq[first:] if v is not None]
        if any(v == 0 for v in later):
            return f"non_monotonic_or_recovered_after_{event_name}"
        return f"first_{event_name}_at_{CONTEXTS[first]}"

    for fam, g in df.groupby("question_family_id", observed=False):
        by_ctx = {str(r["context_length_label"]): r for _, r in g.iterrows()}
        states = []
        inaccurate_seq = []
        hall_seq = []
        grounded_seq = []
        for ctx in CONTEXTS:
            r = by_ctx.get(ctx)
            if r is None:
                states.append("MISSING")
                inaccurate_seq.append(None)
                hall_seq.append(None)
                grounded_seq.append(None)
            elif bool(r["correct"]):
                states.append("CORRECT")
                inaccurate_seq.append(0)
                hall_seq.append(0)
                grounded_seq.append(0)
            elif bool(r["hallucinatory_inaccuracy"]):
                states.append("HALLUCINATORY_INACCURACY")
                inaccurate_seq.append(1)
                hall_seq.append(1)
                grounded_seq.append(0)
            else:
                states.append("GROUNDED_INACCURACY")
                inaccurate_seq.append(1)
                hall_seq.append(0)
                grounded_seq.append(1)
        rows.append(
            {
                "question_family_id": fam,
                "domain": g["domain"].iloc[0],
                "question_type": g["question_type"].iloc[0],
                "state_sequence": "|".join(states),
                "inaccuracy_transition": classify(inaccurate_seq, "inaccurate"),
                "hallucinatory_transition": classify(hall_seq, "hallucinatory"),
                "grounded_transition": classify(grounded_seq, "grounded"),
                **{f"state_{ctx}": state for ctx, state in zip(CONTEXTS, states)},
            }
        )
    return pd.DataFrame(rows)


def latency_table(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    rows = []
    for ctx in CONTEXTS:
        sub = df[df["context_length_label"].astype(str) == ctx]
        lat = sub["generation_latency_seconds"]
        rows.append(
            {
                "context": ctx,
                "n_successful": int(len(sub)),
                "mean_latency": float(lat.mean()),
                "median_latency": float(lat.median()),
                "std_latency": float(lat.std(ddof=1)),
                "p90_latency": float(lat.quantile(0.90)),
                "p95_latency": float(lat.quantile(0.95)),
                "p99_latency": float(lat.quantile(0.99)),
                "total_latency": float(lat.sum()),
                "mean_input_tokens": float(sub["input_tokens"].mean()),
                "mean_generated_tokens": float(sub["generated_tokens_count"].mean()),
                "max_peak_allocated_vram_gib": float(sub["peak_allocated_vram_bytes"].max() / (1024**3)),
                "mean_peak_allocated_vram_gib": float(sub["peak_allocated_vram_bytes"].mean() / (1024**3)),
                "max_peak_reserved_vram_gib": float(sub["peak_reserved_vram_bytes"].max() / (1024**3)),
                "mean_peak_reserved_vram_gib": float(sub["peak_reserved_vram_bytes"].mean() / (1024**3)),
            }
        )
    X = sm.add_constant(df[["input_tokens", "generated_tokens_count"]].astype(float))
    y = df["generation_latency_seconds"].astype(float)
    lm = sm.OLS(y, X).fit()
    log_df = df[(df["input_tokens"] > 0) & (df["generated_tokens_count"] > 0)].copy()
    Xlog = sm.add_constant(pd.DataFrame({
        "log_input_tokens": np.log(log_df["input_tokens"].astype(float)),
        "log_generated_tokens": np.log(log_df["generated_tokens_count"].astype(float)),
    }))
    ylog = np.log(log_df["generation_latency_seconds"].astype(float))
    log_lm = sm.OLS(ylog, Xlog).fit()
    models = {
        "linear_latency_model": {
            "formula": "generation_latency_seconds ~ input_tokens + generated_tokens_count",
            "params": {k: float(v) for k, v in lm.params.items()},
            "r_squared": float(lm.rsquared),
        },
        "log_log_latency_model": {
            "formula": "log(latency) ~ log(input_tokens) + log(generated_tokens_count)",
            "params": {k: float(v) for k, v in log_lm.params.items()},
            "r_squared": float(log_lm.rsquared),
        },
    }
    return pd.DataFrame(rows), models


def sensitivity(df: pd.DataFrame) -> dict:
    complete_families = (
        df.groupby("question_family_id", observed=False)["context_length_label"]
        .nunique()
        .loc[lambda s: s == 6]
        .index
    )
    complete = df[df["question_family_id"].isin(complete_families)].copy()
    non_unanswerable = df[df["question_type"] != "UNANSWERABLE"].copy()
    nominal = [fit_gee(df, out, "nominal_context_log2", f"{out}_nominal") for out in ["inaccurate", "hallucinatory_inaccuracy", "grounded_inaccuracy"]]
    original_results = {
        subset: [fit_gee(g, out, "context_log2", f"{out}_{subset}") for out in ["inaccurate", "hallucinatory_inaccuracy", "grounded_inaccuracy"]]
        for subset, g in [("original_100", df[df["original_100_subset"]]), ("new_400", df[~df["original_100_subset"]])]
    }
    return {
        "complete_case_family_count": int(len(complete_families)),
        "complete_case_observations": int(len(complete)),
        "complete_case": [fit_gee(complete, out) for out in ["inaccurate", "hallucinatory_inaccuracy", "grounded_inaccuracy"]],
        "exclude_unanswerable_observations": int(len(non_unanswerable)),
        "exclude_unanswerable": [fit_gee(non_unanswerable, out) for out in ["inaccurate", "hallucinatory_inaccuracy", "grounded_inaccuracy"]],
        "nominal_context_log2": nominal,
        "original_100_vs_new_400": original_results,
    }


def save_plot(fig: plt.Figure, name: str) -> None:
    fig.tight_layout()
    fig.savefig(FIG / f"{name}.png", dpi=220)
    fig.savefig(FIG / f"{name}.pdf")
    plt.close(fig)


def plots(df: pd.DataFrame, primary: pd.DataFrame, err: pd.DataFrame, qt: pd.DataFrame, dom: pd.DataFrame, transitions: pd.DataFrame, latency: pd.DataFrame, trend: dict) -> None:
    sns.set_theme(style="whitegrid", context="paper")
    palette = {"Correct": "#4C78A8", "Hallucinatory Inaccuracy": "#E45756", "Grounded Inaccuracy": "#72B7B2"}

    # Figure 1
    fig, ax = plt.subplots(figsize=(8, 4.6))
    x = np.arange(len(CONTEXTS))
    bottom = np.zeros(len(CONTEXTS))
    series = [
        ("Correct", primary["correct_rate"].values),
        ("Hallucinatory Inaccuracy", primary["hallucinatory_rate"].values),
        ("Grounded Inaccuracy", primary["grounded_rate"].values),
    ]
    for label, vals in series:
        ax.bar(x, vals * 100, bottom=bottom * 100, label=label, color=palette[label])
        bottom += vals
    ax.set_xticks(x, CONTEXTS)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Percent of gradable responses")
    ax.set_xlabel("Context length")
    ax.legend(loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.16), frameon=False)
    ax.set_title("Factual reliability decomposition by context length")
    save_plot(fig, "figure_01_factual_reliability_decomposition")

    def rate_plot(name: str, rate_col: str, lo_col: str, hi_col: str, ylabel: str, outcome_key: str, color: str):
        fig, ax = plt.subplots(figsize=(7, 4.2))
        y = primary[rate_col].values * 100
        yerr = np.vstack([(primary[rate_col] - primary[lo_col]).values * 100, (primary[hi_col] - primary[rate_col]).values * 100])
        ax.errorbar(CONTEXTS, y, yerr=yerr, marker="o", capsize=4, linewidth=2, color=color)
        ax.set_ylim(0, 100)
        ax.set_ylabel(ylabel)
        ax.set_xlabel("Context length")
        res = trend[outcome_key]
        ax.set_title(
            f"{ylabel} vs context\nOR per 2x={res['odds_ratio_per_2x_context']:.3f}, "
            f"95% CI [{res['odds_ratio_ci_low']:.3f}, {res['odds_ratio_ci_high']:.3f}], p={p_fmt(res['p_value'])}"
        )
        save_plot(fig, name)

    rate_plot("figure_02_overall_inaccuracy", "inaccuracy_rate", "inaccuracy_ci_low", "inaccuracy_ci_high", "Inaccuracy rate (%)", "inaccurate", "#E45756")
    rate_plot("figure_03_hallucinatory_inaccuracy", "hallucinatory_rate", "hallucinatory_ci_low", "hallucinatory_ci_high", "Hallucinatory inaccuracy rate (%)", "hallucinatory_inaccuracy", "#F58518")
    rate_plot("figure_04_grounded_inaccuracy", "grounded_rate", "grounded_ci_low", "grounded_ci_high", "Grounded inaccuracy rate (%)", "grounded_inaccuracy", "#72B7B2")

    # Figure 5
    pivot = err.pivot(index="context", columns="error_type", values="rate_of_gradable").loc[CONTEXTS]
    fig, ax = plt.subplots(figsize=(10, 5.3))
    pivot.plot(kind="bar", stacked=True, ax=ax, colormap="tab20")
    ax.set_ylabel("Rate of gradable responses")
    ax.set_xlabel("Context length")
    ax.set_title("Error-type composition by context length")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    save_plot(fig, "figure_05_error_type_composition")

    # Figure 6 and 7
    for fig_name, value, title in [
        ("figure_06_inaccuracy_by_question_type", "inaccuracy_rate", "Inaccuracy by question type"),
        ("figure_07_grounded_inaccuracy_by_question_type", "grounded_rate", "Grounded inaccuracy by question type"),
    ]:
        fig, ax = plt.subplots(figsize=(9, 4.8))
        sns.lineplot(data=qt, x="context", y=value, hue="question_type", marker="o", ax=ax)
        ax.set_ylim(0, 1)
        ax.set_ylabel("Rate")
        ax.set_xlabel("Context length")
        ax.set_title(title)
        ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
        save_plot(fig, fig_name)

    # Figure 8 and 9
    for fig_name, value, title in [
        ("figure_08_inaccuracy_by_domain", "inaccuracy_rate", "Inaccuracy by domain"),
        ("figure_09_grounded_inaccuracy_by_domain", "grounded_rate", "Grounded inaccuracy by domain"),
    ]:
        fig, ax = plt.subplots(figsize=(8, 4.6))
        sns.lineplot(data=dom, x="context", y=value, hue="domain", marker="o", ax=ax)
        ax.set_ylim(0, 1)
        ax.set_ylabel("Rate")
        ax.set_xlabel("Context length")
        ax.set_title(title)
        ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
        save_plot(fig, fig_name)

    # Figure 10
    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    sns.scatterplot(data=df, x="input_tokens", y="generation_latency_seconds", hue="context_length_label", alpha=0.35, ax=ax)
    sns.lineplot(data=latency, x="mean_input_tokens", y="mean_latency", marker="o", color="black", ax=ax, label="Context mean")
    ax.set_xscale("log", base=2)
    ax.set_xlabel("Rendered input tokens")
    ax.set_ylabel("Synchronized generation latency (s)")
    ax.set_title("Inference latency vs rendered context tokens")
    save_plot(fig, "figure_10_latency_vs_context_tokens")

    # Figure 11
    state_map = {"CORRECT": 0, "HALLUCINATORY_INACCURACY": 1, "GROUNDED_INACCURACY": 2, "MISSING": np.nan}
    mat = transitions[[f"state_{ctx}" for ctx in CONTEXTS]].replace(state_map).to_numpy(dtype=float)
    order = np.lexsort([np.nan_to_num(mat[:, i], nan=9) for i in range(mat.shape[1] - 1, -1, -1)])
    mat = mat[order]
    fig, ax = plt.subplots(figsize=(7.5, 8))
    cmap = matplotlib.colors.ListedColormap(["#4C78A8", "#E45756", "#72B7B2"])
    ax.imshow(mat, aspect="auto", interpolation="nearest", cmap=cmap, vmin=0, vmax=2)
    ax.set_xticks(np.arange(len(CONTEXTS)), CONTEXTS)
    ax.set_yticks([])
    ax.set_xlabel("Context length")
    ax.set_ylabel("Question families")
    ax.set_title("Family-level outcome transitions")
    handles = [plt.Rectangle((0, 0), 1, 1, color=palette[k]) for k in palette]
    ax.legend(handles, list(palette), loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.08), frameon=False)
    save_plot(fig, "figure_11_family_transition_heatmap")


def report(primary: pd.DataFrame, trend: dict, paired: pd.DataFrame, sens: dict, qt: pd.DataFrame, dom: pd.DataFrame, err: pd.DataFrame, latency: pd.DataFrame, summary_table: pd.DataFrame) -> str:
    lines = [
        "# Experiment D Final Statistical Analysis",
        "",
        "Analysis used only the frozen final scored dataset. Runtime OOM failures were reported separately and excluded from factual outcomes.",
        "",
        "## Primary Results",
        "",
        summary_table.to_markdown(index=False),
        "",
        "## GEE Trend Results",
        "",
    ]
    trend_rows = []
    for key in ["inaccurate", "hallucinatory_inaccuracy", "grounded_inaccuracy", "composition"]:
        res = trend[key]
        trend_rows.append(
            {
                "Outcome": res["outcome"],
                "OR per 2x context": f"{res['odds_ratio_per_2x_context']:.3f}",
                "95% CI": ci_fmt(res["odds_ratio_ci_low"], res["odds_ratio_ci_high"]),
                "p-value": p_fmt(res["p_value"]),
            }
        )
    lines += [pd.DataFrame(trend_rows).to_markdown(index=False), ""]
    lines += [
        "## Paired McNemar Tests",
        "",
        paired.to_markdown(index=False),
        "",
        "## Sensitivity Analyses",
        "",
        f"Complete-case families: {sens['complete_case_family_count']}; observations: {sens['complete_case_observations']}.",
        f"Excluding UNANSWERABLE observations: {sens['exclude_unanswerable_observations']}.",
        "",
        "## Question-Type and Domain Tables",
        "",
        "Question-type and domain breakdowns are saved as CSV files in this output directory.",
        "",
        "## Runtime Failures",
        "",
        "There were two runtime failures, both CUDA OOM at 82K. They were not treated as factual inaccuracies.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    df, failures = load_data()
    checks = integrity(df, failures)
    final_hash = sha256(IN_CSV)

    primary = descriptive(df, failures)
    primary.to_csv(OUT / "primary_results.csv", index=False)
    (OUT / "primary_results.json").write_text(primary.to_json(orient="records", indent=2) + "\n")

    trend = {
        "inaccurate": fit_gee(df, "inaccurate"),
        "hallucinatory_inaccuracy": fit_gee(df, "hallucinatory_inaccuracy"),
        "grounded_inaccuracy": fit_gee(df, "grounded_inaccuracy"),
        "composition": fit_composition_gee(df),
    }
    (OUT / "gee_trend_results.json").write_text(json.dumps(trend, indent=2, sort_keys=True) + "\n")

    categorical_rows = []
    categorical_meta = {}
    for outcome in ["inaccurate", "hallucinatory_inaccuracy", "grounded_inaccuracy"]:
        res = fit_categorical(df, outcome)
        categorical_rows.extend(res["rows"])
        categorical_meta[outcome] = {"omnibus_p_value": res["omnibus_p_value"]}
    pd.DataFrame(categorical_rows).to_csv(OUT / "categorical_context_results.csv", index=False)
    (OUT / "categorical_context_results.json").write_text(json.dumps(categorical_meta, indent=2, sort_keys=True) + "\n")

    paired = paired_tests(df)
    paired.to_csv(OUT / "paired_tests.csv", index=False)

    sens = sensitivity(df)
    (OUT / "complete_case_sensitivity.json").write_text(json.dumps({k: sens[k] for k in ["complete_case_family_count", "complete_case_observations", "complete_case"]}, indent=2, sort_keys=True) + "\n")
    (OUT / "unanswerable_exclusion_sensitivity.json").write_text(json.dumps({k: sens[k] for k in ["exclude_unanswerable_observations", "exclude_unanswerable"]}, indent=2, sort_keys=True) + "\n")
    (OUT / "sensitivity_analysis.json").write_text(json.dumps(sens, indent=2, sort_keys=True) + "\n")

    qt = subgroup_table(df, "question_type")
    qt.to_csv(OUT / "question_type_results.csv", index=False)
    dom = subgroup_table(df, "domain")
    dom.to_csv(OUT / "domain_results.csv", index=False)
    interactions = {
        "question_type": [interaction_model(df, out, "question_type") for out in ["inaccurate", "hallucinatory_inaccuracy", "grounded_inaccuracy"]],
        "domain": [interaction_model(df, out, "domain") for out in ["inaccurate", "hallucinatory_inaccuracy", "grounded_inaccuracy"]],
    }
    (OUT / "exploratory_interaction_models.json").write_text(json.dumps(interactions, indent=2, sort_keys=True) + "\n")

    err = error_type_table(df)
    err.to_csv(OUT / "error_type_by_context.csv", index=False)

    trans = family_transitions(df)
    trans.to_csv(OUT / "family_transitions.csv", index=False)
    transition_summary = {
        "inaccuracy": dict(Counter(trans["inaccuracy_transition"])),
        "hallucinatory": dict(Counter(trans["hallucinatory_transition"])),
        "grounded": dict(Counter(trans["grounded_transition"])),
    }
    (OUT / "family_transition_summary.json").write_text(json.dumps(transition_summary, indent=2, sort_keys=True) + "\n")

    latency, latency_models = latency_table(df)
    latency.to_csv(OUT / "latency_analysis.csv", index=False)
    (OUT / "latency_models.json").write_text(json.dumps(latency_models, indent=2, sort_keys=True) + "\n")

    stat_rows = []
    for key in ["inaccurate", "hallucinatory_inaccuracy", "grounded_inaccuracy", "composition"]:
        res = trend[key]
        stat_rows.append(
            {
                "outcome": res["outcome"],
                "or_per_2x_context": res["odds_ratio_per_2x_context"],
                "ci_low": res["odds_ratio_ci_low"],
                "ci_high": res["odds_ratio_ci_high"],
                "p_value": res["p_value"],
                "interpretation": "odds ratio per doubling of rendered input tokens",
            }
        )
    stat_summary = pd.DataFrame(stat_rows)
    stat_summary.to_csv(OUT / "statistical_summary.csv", index=False)

    summary_table = primary[
        [
            "context",
            "gradable_n",
            "correct_rate",
            "inaccuracy_rate",
            "inaccuracy_ci_low",
            "inaccuracy_ci_high",
            "hallucinatory_rate",
            "grounded_rate",
            "runtime_failures",
            "mean_latency",
        ]
    ].copy()
    summary_table["correct_pct"] = summary_table["correct_rate"] * 100
    summary_table["inaccurate_pct"] = summary_table["inaccuracy_rate"] * 100
    summary_table["inaccuracy_95_ci"] = summary_table.apply(lambda r: f"{r['inaccuracy_ci_low']*100:.1f}%-{r['inaccuracy_ci_high']*100:.1f}%", axis=1)
    summary_table["hallucinatory_pct"] = summary_table["hallucinatory_rate"] * 100
    summary_table["grounded_pct"] = summary_table["grounded_rate"] * 100
    summary_table = summary_table[["context", "gradable_n", "correct_pct", "inaccurate_pct", "inaccuracy_95_ci", "hallucinatory_pct", "grounded_pct", "runtime_failures", "mean_latency"]]
    summary_table.to_csv(OUT / "primary_summary_table.csv", index=False)

    plots(df, primary, err, qt, dom, trans, latency, trend)

    report_md = report(primary, trend, paired, sens, qt, dom, err, latency, summary_table)
    (OUT / "statistical_analysis_report.md").write_text(report_md)

    shutil.copyfile(Path(__file__), OUT / "analysis_script.py")
    analysis_script_hash = sha256(OUT / "analysis_script.py")
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "final_scored_dataset": str(IN_CSV),
        "final_scored_dataset_hash": final_hash,
        "runtime_failure_file": str(RUNTIME_FAILURES),
        "benchmark_instances": str(DATASET),
        "benchmark_hash": BENCHMARK_HASH,
        "grader_hash": GRADER_HASH,
        "manual_adjudication_count": int(df["manual_adjudication"].sum()),
        "analysis_code_hash": analysis_script_hash,
        "bootstrap_seed": BOOT_SEED,
        "bootstrap_replicates": BOOT_REPS,
        "context_log2_field": "log2(input_tokens)",
        "rendered_input_token_field_used": "input_tokens",
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
        "figure_files": sorted(str(p) for p in FIG.iterdir()),
    }
    (OUT / "analysis_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    final = {
        "final_scored_dataset_hash": final_hash,
        "primary_results": primary.to_dict(orient="records"),
        "gee_trend_results": trend,
        "paired_significant_after_holm": paired[paired["significant_after_holm_0_05"]].to_dict(orient="records"),
        "sensitivity": sens,
        "latency": latency.to_dict(orient="records"),
        "runtime_failures": len(failures),
        "output_dir": str(OUT),
    }
    print(json.dumps(final, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
