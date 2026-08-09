"""Deterministic re-verification of gold answers.

Nothing here trusts the generator. Every calculated answer is recomputed from the stored
operand values, every operand value is re-checked against the normalized source record it
claims to come from, and every direct-lookup answer is re-checked against its record.
A mismatch is a CRITICAL failure: it means gold data is corrupt, which would silently
invalidate the whole experiment.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from ..normalize.common import RecordPool
from ..schemas import (
    AnswerType,
    CalculationOp,
    CalculationSpec,
    QuestionFamily,
    QuestionType,
)

# Operations whose operand values are deliberately a projection of the record value
# rather than the value itself, and how to reproduce that projection.
_PROJECTED_OPS = {CalculationOp.DAYS_BETWEEN, CalculationOp.COUNT}


def epoch_days(iso: Any) -> Optional[float]:
    try:
        parts = [int(p) for p in str(iso).split("-")]
    except (ValueError, TypeError):
        return None
    if len(parts) == 2:
        parts.append(1)
    if len(parts) != 3:
        return None
    try:
        return float((date(*parts) - date(1970, 1, 1)).days)
    except ValueError:
        return None


def recompute_calculation(spec: CalculationSpec) -> float:
    """Re-apply the declared operation to the stored operand values."""
    v = spec.operand_values
    op = spec.operation
    if op is CalculationOp.RATIO_PERCENT:
        return (v["numerator"] / v["denominator"]) * 100.0
    if op is CalculationOp.GROWTH_PERCENT:
        return ((v["current"] - v["previous"]) / v["previous"]) * 100.0
    if op is CalculationOp.DIFFERENCE:
        return v["minuend"] - v["subtrahend"]
    if op is CalculationOp.RATIO:
        return v["numerator"] / v["denominator"]
    if op is CalculationOp.SUM:
        return sum(v.values())
    if op is CalculationOp.COUNT:
        return float(len(v))
    if op is CalculationOp.DAYS_BETWEEN:
        return v["end"] - v["start"]
    raise ValueError(f"unknown operation {op}")


def _close(a: float, b: float, rel_tol: float) -> bool:
    return math.isclose(a, b, rel_tol=rel_tol, abs_tol=max(rel_tol, 1e-9))


def verify_calculation(spec: CalculationSpec, pool: RecordPool, rel_tol: float) -> List[str]:
    """Check the arithmetic *and* that operands still match their source records."""
    problems: List[str] = []
    try:
        expected = recompute_calculation(spec)
    except (KeyError, ZeroDivisionError, ValueError) as exc:
        return [f"recomputation raised {type(exc).__name__}: {exc}"]

    if not math.isfinite(expected):
        problems.append(f"recomputed result is not finite: {expected}")
    elif not _close(expected, spec.raw_result, rel_tol):
        problems.append(
            f"raw_result {spec.raw_result} != recomputed {expected} "
            f"(formula {spec.formula!r}, operands {spec.operand_values})"
        )
    if math.isfinite(expected):
        expected_round = round(expected, spec.round_decimals)
        if not _close(expected_round, spec.rounded_result, rel_tol):
            problems.append(
                f"rounded_result {spec.rounded_result} != round(recomputed, {spec.round_decimals}) "
                f"= {expected_round}"
            )

    for role, record_id in spec.operands.items():
        rec = pool.get(record_id)
        if rec is None:
            problems.append(f"operand {role!r} references record {record_id} which is not in the pool")
            continue
        if spec.operation in _PROJECTED_OPS:
            if spec.operation is CalculationOp.DAYS_BETWEEN:
                proj = epoch_days(rec.value)
                if proj is None or not _close(proj, spec.operand_values[role], rel_tol):
                    problems.append(
                        f"operand {role!r} epoch-day projection of record {record_id} "
                        f"({rec.value!r} -> {proj}) != stored {spec.operand_values[role]}"
                    )
            continue
        if rec.value_numeric is None:
            problems.append(f"operand {role!r} record {record_id} has no numeric value")
        elif not _close(float(rec.value_numeric), spec.operand_values[role], rel_tol):
            problems.append(
                f"operand {role!r} stored value {spec.operand_values[role]} != source record "
                f"{record_id} value {rec.value_numeric}"
            )
    return problems


def verify_direct_answer(family: QuestionFamily, pool: RecordPool, rel_tol: float) -> List[str]:
    """For non-calculated answers, the gold must literally be a source record's value."""
    problems: List[str] = []
    targets = [t for t in (family.target_conditions.get("records") or [])]
    role_target = [e for e in family.gold_evidence if e.role == "target_value"]
    if not role_target:
        return problems  # multi-evidence selection questions are checked separately

    ev = role_target[0]
    rec = pool.get(ev.record_id)
    if rec is None:
        return [f"gold evidence record {ev.record_id} is not in the normalized pool"]

    if family.answer_type in (AnswerType.NUMERIC, AnswerType.PERCENT, AnswerType.INTEGER):
        if rec.value_numeric is None:
            problems.append(f"numeric answer but source record {rec.record_id} has no numeric value")
        elif not isinstance(family.gold_answer_normalized, (int, float)):
            problems.append(
                f"answer_type {family.answer_type.value} but gold_answer_normalized is "
                f"{type(family.gold_answer_normalized).__name__}"
            )
        elif not _close(float(family.gold_answer_normalized), float(rec.value_numeric), rel_tol):
            problems.append(
                f"gold_answer_normalized {family.gold_answer_normalized} != source record "
                f"{rec.record_id} value {rec.value_numeric}"
            )
    else:
        got = str(family.gold_answer_normalized)
        src = str(rec.value)
        variants = {src, src.upper(), src.upper().replace(" ", ""), src.strip()}
        if got not in variants:
            problems.append(
                f"gold_answer_normalized {got!r} is not a canonical form of source record "
                f"{rec.record_id} value {src!r}"
            )

    if family.answer_unit and rec.unit and family.answer_unit != rec.unit:
        # Percent/ratio answers legitimately carry a derived unit; direct lookups must not.
        if family.answer_type not in (AnswerType.PERCENT,):
            problems.append(
                f"answer_unit {family.answer_unit!r} disagrees with source record unit {rec.unit!r}"
            )
    return problems


def verify_selection_answer(family: QuestionFamily, pool: RecordPool) -> List[str]:
    """Answers that select among supplied records (max-year, argmax) must be recomputable."""
    if family.generation_metadata.template_id != "WB_TEMPORAL_MAX_YEAR":
        return []
    recs = [pool.get(rid) for rid in family.gold_evidence_ids]
    if any(r is None for r in recs):
        return ["one or more candidate records for the selection are missing from the pool"]
    valued = [r for r in recs if r.value_numeric is not None]
    if len(valued) != len(recs):
        return ["a candidate record has no numeric value; argmax is undefined"]
    best = max(valued, key=lambda r: r.value_numeric)
    ties = [r for r in valued if r.value_numeric == best.value_numeric]
    problems = []
    if len(ties) != 1:
        problems.append(f"argmax is ambiguous: {len(ties)} records tie at {best.value_numeric}")
    if str(family.gold_answer_normalized) != str(best.period):
        problems.append(
            f"gold answer {family.gold_answer_normalized!r} != recomputed argmax period {best.period!r}"
        )
    return problems


def verify_family(family: QuestionFamily, pool: RecordPool, rel_tol: float) -> List[str]:
    """All gold-integrity checks for one family."""
    problems: List[str] = []

    if not family.answerable:
        if family.gold_answer is not None or family.gold_evidence_ids:
            problems.append("unanswerable family carries a gold answer or gold evidence")
        return problems

    for ev in family.gold_evidence:
        rec = pool.get(ev.record_id)
        if rec is None:
            problems.append(f"gold evidence {ev.record_id} is not in the normalized pool")
            continue
        if rec.value != ev.value:
            problems.append(
                f"gold evidence {ev.record_id} value {ev.value!r} drifted from source record "
                f"value {rec.value!r}"
            )
        if rec.entity_id != ev.entity_id or rec.concept != ev.concept or rec.period != ev.period:
            problems.append(
                f"gold evidence {ev.record_id} coordinates drifted from the source record"
            )

    if family.calculation_spec is not None:
        problems.extend(verify_calculation(family.calculation_spec, pool, rel_tol))
        if isinstance(family.gold_answer_normalized, (int, float)):
            if not _close(float(family.gold_answer_normalized),
                          float(family.calculation_spec.rounded_result), rel_tol):
                problems.append(
                    f"gold_answer_normalized {family.gold_answer_normalized} != calculation "
                    f"rounded_result {family.calculation_spec.rounded_result}"
                )
        spec_ids = set(family.calculation_spec.operands.values())
        if not spec_ids.issubset(set(family.gold_evidence_ids)):
            problems.append(
                f"calculation operands {sorted(spec_ids - set(family.gold_evidence_ids))} "
                "are not listed as gold evidence"
            )
    else:
        problems.extend(verify_direct_answer(family, pool, rel_tol))
        problems.extend(verify_selection_answer(family, pool))

    if isinstance(family.gold_answer_normalized, float) and not math.isfinite(family.gold_answer_normalized):
        problems.append(f"gold_answer_normalized is not finite: {family.gold_answer_normalized}")
    return problems
