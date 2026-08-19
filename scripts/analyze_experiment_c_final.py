from __future__ import annotations

import hashlib
import json
import math
import os
import platform
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ.setdefault("MPLCONFIGDIR", "/home/srinija/GPU_Datasets/.matplotlib-cache")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.stats.contingency_tables import mcnemar
from statsmodels.stats.multitest import multipletests


INPUT_CSV = Path("data/grading_experiment_c_final_v1/final_scored_results.csv")
INPUT_JSONL = Path("data/grading_experiment_c_final_v1/final_scored_results.jsonl")
OUT_DIR = Path("data/analysis_experiment_c_final_v1")
FIG_DIR = OUT_DIR / "figures"
EXPECTED_JSONL_SHA256 = "6fdfaa035b5da2211e813353916902c871e783ecfa993615db672f62bcb8e327"
CONTEXT_ORDER = ["4K", "8K", "16K", "32K", "64K"]
CONTEXT_LOG2 = {"4K": 0, "8K": 1, "16K": 2, "32K": 3, "64K": 4}
BOOTSTRAP_SEED = 20260810
BOOTSTRAP_REPS = 5000


ERROR_TYPES = [
    "CORRECT",
    "UNSUPPORTED_VALUE",
    "FAILED_TO_ABSTAIN",
    "WRONG_ENTITY",
    "WRONG_PERIOD",
    "WRONG_VERSION",
    "WRONG_FIELD",
    "CALCULATION_ERROR",
    "UNNECESSARY_ABSTENTION",
    "WRONG_UNIT",
    "WRONG_SERIES_VARIANT",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_clean_outdir() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FIG_DIR.mkdir(parents=True, exist_ok=True)


def load_data() -> pd.DataFrame:
    if sha256_file(INPUT_JSONL) != EXPECTED_JSONL_SHA256:
        raise RuntimeError("final scored JSONL hash does not match expected immutable dataset hash")
    df = pd.read_csv(INPUT_CSV)
    df["final_answer_correct"] = df["final_answer_correct"].astype(bool)
    df["final_hallucination"] = df["final_hallucination"].astype(bool)
    df["answerable"] = df["answerable"].astype(bool)
    df["manual_adjudication"] = df["manual_adjudication"].astype(bool)
    df["context_length_label"] = pd.Categorical(df["context_length_label"], categories=CONTEXT_ORDER, ordered=True)
    df["context_log2"] = df["context_length_label"].astype(str).map(CONTEXT_LOG2)
    df["log2_input_tokens"] = np.log2(df["input_tokens"].astype(float))
    df["answer_correct_int"] = df["final_answer_correct"].astype(int)
    df["hallucination_int"] = df["final_hallucination"].astype(int)
    integrity_errors = []
    if len(df) != 500:
        integrity_errors.append(f"expected 500 rows, found {len(df)}")
    if df["instance_id"].nunique() != 500:
        integrity_errors.append("expected 500 unique instance IDs")
    counts = df["context_length_label"].value_counts().to_dict()
    for label in CONTEXT_ORDER:
        if counts.get(label, 0) != 100:
            integrity_errors.append(f"expected 100 rows for {label}, found {counts.get(label, 0)}")
    if df["question_family_id"].nunique() != 100:
        integrity_errors.append(f"expected 100 families, found {df['question_family_id'].nunique()}")
    family_context_counts = df.groupby("question_family_id", observed=True)["context_length_label"].nunique()
    if not (family_context_counts == 5).all():
        integrity_errors.append("not every family has exactly 5 context conditions")
    if df["final_answer_correct"].isna().any():
        integrity_errors.append("missing final correctness labels")
    if df["final_hallucination"].isna().any():
        integrity_errors.append("missing final hallucination labels")
    if integrity_errors:
        raise RuntimeError("; ".join(integrity_errors))
    return df


def clustered_bootstrap_context_ci(df: pd.DataFrame, outcome: str) -> dict[str, tuple[float, float]]:
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    families = np.array(sorted(df["question_family_id"].unique()))
    by_family = {fam: grp for fam, grp in df.groupby("question_family_id", observed=True)}
    values = {label: [] for label in CONTEXT_ORDER}
    for _ in range(BOOTSTRAP_REPS):
        sampled = rng.choice(families, size=len(families), replace=True)
        boot = pd.concat([by_family[fam] for fam in sampled], ignore_index=True)
        rates = boot.groupby("context_length_label", observed=True)[outcome].mean()
        for label in CONTEXT_ORDER:
            values[label].append(float(rates.loc[label]))
    return {
        label: (
            float(np.percentile(values[label], 2.5)),
            float(np.percentile(values[label], 97.5)),
        )
        for label in CONTEXT_ORDER
    }


def descriptive_by_context(df: pd.DataFrame) -> pd.DataFrame:
    acc_ci = clustered_bootstrap_context_ci(df, "answer_correct_int")
    hall_ci = clustered_bootstrap_context_ci(df, "hallucination_int")
    rows = []
    for label in CONTEXT_ORDER:
        g = df[df["context_length_label"].astype(str) == label]
        correct = int(g["final_answer_correct"].sum())
        hall = int(g["final_hallucination"].sum())
        failed_to_abstain = int((g["final_error_type"] == "FAILED_TO_ABSTAIN").sum())
        unnecessary_abstention = int((g["final_error_type"] == "UNNECESSARY_ABSTENTION").sum())
        rows.append(
            {
                "context": label,
                "N": len(g),
                "correct_count": correct,
                "accuracy": correct / len(g),
                "accuracy_ci_low": acc_ci[label][0],
                "accuracy_ci_high": acc_ci[label][1],
                "hallucination_count": hall,
                "hallucination_rate": hall / len(g),
                "hallucination_ci_low": hall_ci[label][0],
                "hallucination_ci_high": hall_ci[label][1],
                "incorrect_non_hallucination_count": int(((~g["final_answer_correct"]) & (~g["final_hallucination"])).sum()),
                "failed_to_abstain_count": failed_to_abstain,
                "unnecessary_abstention_count": unnecessary_abstention,
                "mean_latency": float(g["generation_latency_seconds"].mean()),
            }
        )
    return pd.DataFrame(rows)


def fit_gee(df: pd.DataFrame, formula: str) -> dict[str, Any]:
    model = smf.gee(
        formula,
        groups="question_family_id",
        data=df,
        family=sm.families.Binomial(),
        cov_struct=sm.cov_struct.Exchangeable(),
    )
    result = model.fit()
    key = "context_log2"
    coef = float(result.params[key]) if key in result.params else None
    se = float(result.bse[key]) if key in result.bse else None
    p = float(result.pvalues[key]) if key in result.pvalues else None
    ci = result.conf_int()
    if key in ci.index:
        lo, hi = float(ci.loc[key, 0]), float(ci.loc[key, 1])
        or_ci = [float(math.exp(lo)), float(math.exp(hi))]
        odds_ratio = float(math.exp(coef))
    else:
        or_ci = None
        odds_ratio = None
    return {
        "method": "GEE logistic regression clustered by question_family_id with exchangeable working correlation",
        "formula": formula,
        "coefficient_context_log2": coef,
        "standard_error_context_log2": se,
        "odds_ratio_per_context_doubling": odds_ratio,
        "odds_ratio_95_ci": or_ci,
        "p_value_context_log2": p,
        "converged": bool(getattr(result, "converged", True)),
        "status": "fit_completed",
        "n_observations": int(result.nobs),
        "n_families": int(df["question_family_id"].nunique()),
        "params": {k: float(v) for k, v in result.params.items()},
        "standard_errors": {k: float(v) for k, v in result.bse.items()},
        "p_values": {k: float(v) for k, v in result.pvalues.items()},
    }


def paired_tests(df: pd.DataFrame, outcome: str) -> pd.DataFrame:
    rows = []
    wide = df.pivot(index="question_family_id", columns="context_length_label", values=outcome)
    raw_p = []
    comparisons = []
    for label in ["8K", "16K", "32K", "64K"]:
        a = wide["4K"].astype(bool)
        b = wide[label].astype(bool)
        n01 = int(((~a) & b).sum())
        n10 = int((a & (~b)).sum())
        table = [[int((~a & ~b).sum()), n01], [n10, int((a & b).sum())]]
        test = mcnemar(table, exact=True)
        p = float(test.pvalue)
        raw_p.append(p)
        comparisons.append((label, n01, n10, float(b.mean() - a.mean()), p))
    adjusted = multipletests(raw_p, method="holm")[1]
    for (label, n01, n10, diff, p), adj in zip(comparisons, adjusted):
        rows.append(
            {
                "outcome": outcome,
                "comparison": f"4K_vs_{label}",
                "discordant_4k_false_comparison_true": n01,
                "discordant_4k_true_comparison_false": n10,
                "absolute_paired_rate_difference": diff,
                "raw_p_value": p,
                "holm_adjusted_p_value": float(adj),
            }
        )
    return pd.DataFrame(rows)


def transition_categories(df: pd.DataFrame, outcome: str) -> pd.DataFrame:
    rows = []
    wide = df.pivot(index="question_family_id", columns="context_length_label", values=outcome)
    for fam, vals in wide.iterrows():
        seq = [bool(vals[label]) for label in CONTEXT_ORDER]
        true_indexes = [i for i, v in enumerate(seq) if v]
        if not any(seq):
            category = "never_true"
            first = None
        elif all(seq):
            category = "true_all_contexts"
            first = "4K"
        else:
            first_idx = true_indexes[0]
            first = CONTEXT_ORDER[first_idx]
            if first_idx == 0:
                category = "true_at_shorter_recovered_later"
            else:
                category = f"first_true_at_{first}"
            if any(seq[i] and not seq[j] for i in range(len(seq)) for j in range(i + 1, len(seq))):
                category = "non_monotonic" if first_idx > 0 else "true_at_shorter_recovered_later"
        rows.append(
            {
                "question_family_id": fam,
                "outcome": outcome,
                "sequence": "".join("1" if x else "0" for x in seq),
                "transition_category": category,
                "first_true_context": first,
            }
        )
    return pd.DataFrame(rows)


def subgroup_results(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    rows = []
    for (group, context), g in df.groupby([group_col, "context_length_label"], observed=True):
        rows.append(
            {
                group_col: group,
                "context": str(context),
                "N": len(g),
                "accuracy": float(g["final_answer_correct"].mean()),
                "hallucination_rate": float(g["final_hallucination"].mean()),
                "correct_count": int(g["final_answer_correct"].sum()),
                "hallucination_count": int(g["final_hallucination"].sum()),
            }
        )
    return pd.DataFrame(rows)


def error_type_by_context(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for label in CONTEXT_ORDER:
        g = df[df["context_length_label"].astype(str) == label]
        counts = Counter(g["final_error_type"])
        for err in ERROR_TYPES:
            rows.append(
                {
                    "context": label,
                    "error_type": err,
                    "count": counts.get(err, 0),
                    "percent": counts.get(err, 0) / len(g),
                }
            )
    return pd.DataFrame(rows)


def latency_analysis(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    rows = []
    for label in CONTEXT_ORDER:
        g = df[df["context_length_label"].astype(str) == label]
        rows.append(
            {
                "context": label,
                "N": len(g),
                "mean_latency": float(g["generation_latency_seconds"].mean()),
                "median_latency": float(g["generation_latency_seconds"].median()),
                "std_latency": float(g["generation_latency_seconds"].std(ddof=1)),
                "p90_latency": float(g["generation_latency_seconds"].quantile(0.90)),
                "p95_latency": float(g["generation_latency_seconds"].quantile(0.95)),
                "total_latency": float(g["generation_latency_seconds"].sum()),
                "mean_input_tokens": float(g["input_tokens"].mean()),
                "mean_generated_tokens": float(g["generated_tokens_count"].mean()),
            }
        )
    latency_model = smf.ols("generation_latency_seconds ~ input_tokens + generated_tokens_count", data=df).fit()
    hall_model = smf.ols("generation_latency_seconds ~ log2_input_tokens + hallucination_int", data=df).fit()
    correct_model = smf.ols("generation_latency_seconds ~ log2_input_tokens + answer_correct_int", data=df).fit()
    models = {
        "latency_input_output_tokens": ols_to_dict(latency_model),
        "latency_context_adjusted_hallucination_exploratory": ols_to_dict(hall_model),
        "latency_context_adjusted_correctness_exploratory": ols_to_dict(correct_model),
    }
    return pd.DataFrame(rows), models


def ols_to_dict(result: Any) -> dict[str, Any]:
    return {
        "formula": result.model.formula,
        "n_observations": int(result.nobs),
        "r_squared": float(result.rsquared),
        "adj_r_squared": float(result.rsquared_adj),
        "params": {k: float(v) for k, v in result.params.items()},
        "standard_errors": {k: float(v) for k, v in result.bse.items()},
        "p_values": {k: float(v) for k, v in result.pvalues.items()},
    }


def sensitivity(df: pd.DataFrame) -> dict[str, Any]:
    out = {
        "all_rows_hallucination": fit_gee(df, "hallucination_int ~ context_log2"),
        "excluding_unanswerable_hallucination": fit_gee(df[df["question_type"] != "UNANSWERABLE"], "hallucination_int ~ context_log2"),
        "excluding_manual_adjudication_hallucination": fit_gee(df[~df["manual_adjudication"]], "hallucination_int ~ context_log2"),
    }
    categorical = fit_gee(df, "hallucination_int ~ C(context_length_label)")
    out["categorical_context_hallucination"] = categorical
    return out


def make_plots(
    primary: pd.DataFrame,
    qtype: pd.DataFrame,
    domain: pd.DataFrame,
    errors: pd.DataFrame,
    transitions: pd.DataFrame,
    latency: pd.DataFrame,
) -> None:
    def savefig(name: str) -> None:
        plt.tight_layout()
        plt.savefig(FIG_DIR / f"{name}.png", dpi=200)
        plt.savefig(FIG_DIR / f"{name}.pdf")
        plt.close()

    x = np.arange(len(primary))
    plt.figure(figsize=(7, 4.5))
    plt.errorbar(x, primary["hallucination_rate"], yerr=[
        primary["hallucination_rate"] - primary["hallucination_ci_low"],
        primary["hallucination_ci_high"] - primary["hallucination_rate"],
    ], marker="o", capsize=4)
    plt.xticks(x, primary["context"])
    plt.ylim(0, 1)
    plt.xlabel("Context length")
    plt.ylabel("Hallucination rate")
    plt.title("Hallucination Rate by Context Length")
    savefig("hallucination_rate_by_context")

    plt.figure(figsize=(7, 4.5))
    plt.errorbar(x, primary["accuracy"], yerr=[
        primary["accuracy"] - primary["accuracy_ci_low"],
        primary["accuracy_ci_high"] - primary["accuracy"],
    ], marker="o", capsize=4)
    plt.xticks(x, primary["context"])
    plt.ylim(0, 1)
    plt.xlabel("Context length")
    plt.ylabel("Accuracy")
    plt.title("Accuracy by Context Length")
    savefig("accuracy_by_context")

    plt.figure(figsize=(7, 4.5))
    plt.plot(x, latency["mean_latency"], marker="o")
    plt.xticks(x, latency["context"])
    plt.xlabel("Context length")
    plt.ylabel("Mean synchronized generation latency (s)")
    plt.title("Inference Latency by Context Length")
    savefig("latency_by_context")

    plt.figure(figsize=(9, 5))
    for q, g in qtype.groupby("question_type"):
        g = g.set_index("context").loc[CONTEXT_ORDER].reset_index()
        plt.plot(x, g["hallucination_rate"], marker="o", label=q)
    plt.xticks(x, CONTEXT_ORDER)
    plt.ylim(0, 1)
    plt.xlabel("Context length")
    plt.ylabel("Hallucination rate")
    plt.title("Hallucination Rate by Question Type")
    plt.legend(fontsize=8)
    savefig("hallucination_by_question_type")

    plt.figure(figsize=(8, 5))
    for d, g in domain.groupby("domain"):
        g = g.set_index("context").loc[CONTEXT_ORDER].reset_index()
        plt.plot(x, g["hallucination_rate"], marker="o", label=d)
    plt.xticks(x, CONTEXT_ORDER)
    plt.ylim(0, 1)
    plt.xlabel("Context length")
    plt.ylabel("Hallucination rate")
    plt.title("Hallucination Rate by Domain")
    plt.legend(fontsize=8)
    savefig("hallucination_by_domain")

    pivot = errors.pivot(index="context", columns="error_type", values="percent").loc[CONTEXT_ORDER]
    plt.figure(figsize=(10, 5.5))
    bottom = np.zeros(len(pivot))
    for err in ERROR_TYPES:
        vals = pivot[err].values
        plt.bar(x, vals, bottom=bottom, label=err)
        bottom += vals
    plt.xticks(x, CONTEXT_ORDER)
    plt.ylim(0, 1)
    plt.xlabel("Context length")
    plt.ylabel("Proportion")
    plt.title("Error-Type Distribution by Context")
    plt.legend(fontsize=7, ncol=2, bbox_to_anchor=(1.02, 1), loc="upper left")
    savefig("error_type_distribution_by_context")

    hall = transitions[transitions["outcome"] == "hallucination_int"]
    seq_counts = hall["sequence"].value_counts().sort_index()
    plt.figure(figsize=(10, 4.5))
    plt.bar(seq_counts.index, seq_counts.values)
    plt.xlabel("Family hallucination sequence across 4K,8K,16K,32K,64K")
    plt.ylabel("Number of families")
    plt.title("Family-Level Hallucination Transition Patterns")
    plt.xticks(rotation=45, ha="right")
    savefig("family_hallucination_transitions")


def write_report(
    primary: pd.DataFrame,
    models: dict[str, Any],
    paired: pd.DataFrame,
    transitions: pd.DataFrame,
    qtype: pd.DataFrame,
    domain: pd.DataFrame,
    errors: pd.DataFrame,
    latency: pd.DataFrame,
    sensitivity_results: dict[str, Any],
) -> None:
    hall_model = models["primary_hallucination"]
    acc_model = models["primary_accuracy"]
    hall_pair_sig = paired[(paired["outcome"] == "hallucination_int") & (paired["holm_adjusted_p_value"] < 0.05)]
    acc_pair_sig = paired[(paired["outcome"] == "answer_correct_int") & (paired["holm_adjusted_p_value"] < 0.05)]
    transition_counts = transitions.groupby(["outcome", "transition_category"]).size().to_dict()
    lines = [
        "# Experiment C Final Statistical Analysis",
        "",
        "## Integrity",
        "",
        f"- input CSV: `{INPUT_CSV}`",
        f"- immutable JSONL hash: `{sha256_file(INPUT_JSONL)}`",
        f"- rows: `500`",
        f"- families: `100`",
        f"- bootstrap seed: `{BOOTSTRAP_SEED}`",
        f"- bootstrap replicates: `{BOOTSTRAP_REPS}`",
        "",
        "## Primary Results",
        "",
        primary.to_markdown(index=False, floatfmt=".3f"),
        "",
        "## Primary Hallucination Trend Model",
        "",
        f"- method: {hall_model['method']}",
        f"- coefficient for context_log2: `{hall_model['coefficient_context_log2']:.6g}`",
        f"- SE: `{hall_model['standard_error_context_log2']:.6g}`",
        f"- odds ratio per 2x context increase: `{hall_model['odds_ratio_per_context_doubling']:.6g}`",
        f"- 95% CI for OR: `[{hall_model['odds_ratio_95_ci'][0]:.6g}, {hall_model['odds_ratio_95_ci'][1]:.6g}]`",
        f"- p-value: `{hall_model['p_value_context_log2']:.6g}`",
        f"- status: `{hall_model['status']}`, converged: `{hall_model['converged']}`",
        "",
        "Interpretation: each doubling of context length was associated with "
        f"`{hall_model['odds_ratio_per_context_doubling']:.3f}x` the odds of hallucination.",
        "",
        "## Accuracy Trend Model",
        "",
        f"- coefficient for context_log2: `{acc_model['coefficient_context_log2']:.6g}`",
        f"- SE: `{acc_model['standard_error_context_log2']:.6g}`",
        f"- odds ratio per 2x context increase: `{acc_model['odds_ratio_per_context_doubling']:.6g}`",
        f"- 95% CI for OR: `[{acc_model['odds_ratio_95_ci'][0]:.6g}, {acc_model['odds_ratio_95_ci'][1]:.6g}]`",
        f"- p-value: `{acc_model['p_value_context_log2']:.6g}`",
        f"- status: `{acc_model['status']}`, converged: `{acc_model['converged']}`",
        "",
        "## Paired Comparisons",
        "",
        paired.to_markdown(index=False, floatfmt=".4g"),
        "",
        "Holm-adjusted paired comparisons below 0.05: "
        f"hallucination `{hall_pair_sig['comparison'].tolist()}`, accuracy `{acc_pair_sig['comparison'].tolist()}`.",
        "",
        "## Family-Level Transitions",
        "",
        f"`{transition_counts}`",
        "",
        "## Exploratory Subgroups",
        "",
        "Question-type and domain subgroup tables are saved as CSV files. Interaction GEE models are saved in `mixed_model_results.json`; these are exploratory and not interpreted as confirmatory tests.",
        "",
        "## Error-Type Evolution",
        "",
        errors.to_markdown(index=False, floatfmt=".3f"),
        "",
        "## Latency",
        "",
        latency.to_markdown(index=False, floatfmt=".3f"),
        "",
        "## Sensitivity Checks",
        "",
        f"- excluding UNANSWERABLE hallucination OR per doubling: `{sensitivity_results['excluding_unanswerable_hallucination']['odds_ratio_per_context_doubling']:.6g}`, p=`{sensitivity_results['excluding_unanswerable_hallucination']['p_value_context_log2']:.6g}`",
        f"- excluding manual adjudication hallucination OR per doubling: `{sensitivity_results['excluding_manual_adjudication_hallucination']['odds_ratio_per_context_doubling']:.6g}`, p=`{sensitivity_results['excluding_manual_adjudication_hallucination']['p_value_context_log2']:.6g}`",
        "",
        "## Discipline",
        "",
        "No grading labels were changed, no inference was rerun, and no LLM judge was used. Subgroup and latency analyses are exploratory.",
    ]
    (OUT_DIR / "statistical_analysis_report.md").write_text("\n".join(lines), encoding="utf-8")


def package_versions() -> dict[str, str]:
    import matplotlib
    import statsmodels

    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scipy": scipy.__version__,
        "statsmodels": statsmodels.__version__,
        "matplotlib": matplotlib.__version__,
    }


def main() -> int:
    ensure_clean_outdir()
    df = load_data()
    primary = descriptive_by_context(df)
    primary.to_csv(OUT_DIR / "primary_results.csv", index=False)
    (OUT_DIR / "primary_results.json").write_text(primary.to_json(orient="records", indent=2), encoding="utf-8")

    models = {
        "primary_hallucination": fit_gee(df, "hallucination_int ~ context_log2"),
        "primary_accuracy": fit_gee(df, "answer_correct_int ~ context_log2"),
    }
    try:
        models["exploratory_hallucination_by_question_type"] = fit_gee(df, "hallucination_int ~ context_log2 * C(question_type)")
        models["exploratory_accuracy_by_question_type"] = fit_gee(df, "answer_correct_int ~ context_log2 * C(question_type)")
        models["exploratory_hallucination_by_domain"] = fit_gee(df, "hallucination_int ~ context_log2 * C(domain)")
    except Exception as exc:
        models["exploratory_interaction_error"] = {"status": "fit_failed", "error": str(exc)}

    paired = pd.concat(
        [paired_tests(df, "hallucination_int"), paired_tests(df, "answer_correct_int")],
        ignore_index=True,
    )
    paired.to_csv(OUT_DIR / "paired_tests.csv", index=False)

    transitions = pd.concat(
        [transition_categories(df, "hallucination_int"), transition_categories(df, "answer_correct_int")],
        ignore_index=True,
    )
    transitions.to_csv(OUT_DIR / "family_transitions.csv", index=False)

    qtype = subgroup_results(df, "question_type")
    qtype.to_csv(OUT_DIR / "question_type_results.csv", index=False)
    domain = subgroup_results(df, "domain")
    domain.to_csv(OUT_DIR / "domain_results.csv", index=False)
    errors = error_type_by_context(df)
    errors.to_csv(OUT_DIR / "error_type_by_context.csv", index=False)
    latency, latency_models = latency_analysis(df)
    latency.to_csv(OUT_DIR / "latency_analysis.csv", index=False)
    (OUT_DIR / "latency_models.json").write_text(json.dumps(latency_models, indent=2, sort_keys=True), encoding="utf-8")

    sensitivity_results = sensitivity(df)
    (OUT_DIR / "sensitivity_analysis.json").write_text(
        json.dumps(sensitivity_results, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    models["sensitivity_summary"] = {
        "excluding_unanswerable_hallucination": sensitivity_results["excluding_unanswerable_hallucination"],
        "excluding_manual_adjudication_hallucination": sensitivity_results["excluding_manual_adjudication_hallucination"],
    }
    (OUT_DIR / "mixed_model_results.json").write_text(json.dumps(models, indent=2, sort_keys=True), encoding="utf-8")

    make_plots(primary, qtype, domain, errors, transitions, latency)
    write_report(primary, models, paired, transitions, qtype, domain, errors, latency, sensitivity_results)

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "input_csv": str(INPUT_CSV),
        "input_csv_sha256": sha256_file(INPUT_CSV),
        "input_jsonl": str(INPUT_JSONL),
        "input_jsonl_sha256": sha256_file(INPUT_JSONL),
        "expected_final_dataset_hash": EXPECTED_JSONL_SHA256,
        "analysis_script": "scripts/analyze_experiment_c_final.py",
        "analysis_script_sha256": sha256_file(Path("scripts/analyze_experiment_c_final.py")),
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_reps": BOOTSTRAP_REPS,
        "primary_model_method": models["primary_hallucination"]["method"],
        "package_versions": package_versions(),
        "outputs": {
            "primary_results_csv": str(OUT_DIR / "primary_results.csv"),
            "primary_results_json": str(OUT_DIR / "primary_results.json"),
            "paired_tests_csv": str(OUT_DIR / "paired_tests.csv"),
            "mixed_model_results_json": str(OUT_DIR / "mixed_model_results.json"),
            "question_type_results_csv": str(OUT_DIR / "question_type_results.csv"),
            "domain_results_csv": str(OUT_DIR / "domain_results.csv"),
            "error_type_by_context_csv": str(OUT_DIR / "error_type_by_context.csv"),
            "family_transitions_csv": str(OUT_DIR / "family_transitions.csv"),
            "latency_analysis_csv": str(OUT_DIR / "latency_analysis.csv"),
            "sensitivity_analysis_json": str(OUT_DIR / "sensitivity_analysis.json"),
            "report": str(OUT_DIR / "statistical_analysis_report.md"),
            "figures": str(FIG_DIR),
        },
    }
    (OUT_DIR / "analysis_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    final = {
        "accuracy": dict(zip(primary["context"], primary["accuracy"])),
        "hallucination_rate": dict(zip(primary["context"], primary["hallucination_rate"])),
        "hallucination_or_per_doubling": models["primary_hallucination"]["odds_ratio_per_context_doubling"],
        "hallucination_or_ci": models["primary_hallucination"]["odds_ratio_95_ci"],
        "hallucination_p": models["primary_hallucination"]["p_value_context_log2"],
        "accuracy_or_per_doubling": models["primary_accuracy"]["odds_ratio_per_context_doubling"],
        "accuracy_or_ci": models["primary_accuracy"]["odds_ratio_95_ci"],
        "accuracy_p": models["primary_accuracy"]["p_value_context_log2"],
        "output_dir": str(OUT_DIR),
    }
    print(json.dumps(final, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
