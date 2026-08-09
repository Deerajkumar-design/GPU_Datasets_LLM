"""Deterministic gold-answer arithmetic.

The generator and the validator implement the calculation independently
(``questions.base.build_calculation`` vs ``validation.gold.recompute_calculation``);
these tests pin both, and pin that the validator actually rejects tampered gold.
"""

from __future__ import annotations

import math

import pytest

from longctx_dataset.normalize.common import RecordPool
from longctx_dataset.questions.base import (
    CalculationError,
    build_calculation,
    format_number,
    numeric_tolerance_for,
)
from longctx_dataset.schemas import CalculationOp, Domain, NormalizedRecord
from longctx_dataset.validation.gold import epoch_days, recompute_calculation, verify_calculation


def rec(rid: str, value, unit="USD", period="CY2024", concept="c") -> NormalizedRecord:
    return NormalizedRecord(record_id=rid, domain=Domain.SEC, source="s", entity_id="E",
                            entity_name="Entity", record_type="t", concept=concept,
                            concept_label="C", value=value, unit=unit, period=period)


def test_ratio_percent_matches_hand_computation():
    spec = build_calculation(CalculationOp.RATIO_PERCENT,
                             {"numerator": rec("N", 26491000000.0), "denominator": rec("D", 446509000000.0)})
    assert spec.rounded_result == 5.93
    assert math.isclose(spec.raw_result, 26491000000.0 / 446509000000.0 * 100.0)
    assert spec.formula == "(numerator / denominator) * 100"
    assert spec.numerator_record_id == "N" and spec.denominator_record_id == "D"


def test_growth_percent_handles_negative_change():
    spec = build_calculation(CalculationOp.GROWTH_PERCENT,
                             {"current": rec("C", 80.0), "previous": rec("P", 100.0)})
    assert spec.rounded_result == -20.0


def test_difference_and_ratio():
    assert build_calculation(CalculationOp.DIFFERENCE,
                             {"minuend": rec("A", 500), "subtrahend": rec("B", 120)},
                             decimals=0).rounded_result == 380
    assert build_calculation(CalculationOp.RATIO,
                             {"numerator": rec("A", 3), "denominator": rec("B", 4)},
                             decimals=4).rounded_result == 0.75


def test_count_uses_operand_cardinality():
    spec = build_calculation(CalculationOp.COUNT,
                             {f"p{i}": rec(f"R{i}", None, unit=None) for i in range(4)},
                             decimals=0, values_override={f"p{i}": 1.0 for i in range(4)})
    assert spec.rounded_result == 4


def test_days_between_uses_epoch_day_projection():
    start, end = rec("S", "2021-12-14", unit=None), rec("E", "2022-10-26", unit=None)
    spec = build_calculation(CalculationOp.DAYS_BETWEEN, {"start": start, "end": end}, decimals=0,
                             values_override={"start": epoch_days("2021-12-14"),
                                              "end": epoch_days("2022-10-26")})
    assert spec.rounded_result == 316


@pytest.mark.parametrize("op,operands", [
    (CalculationOp.RATIO_PERCENT, {"numerator": 1.0, "denominator": 0.0}),
    (CalculationOp.GROWTH_PERCENT, {"current": 1.0, "previous": 0.0}),
    (CalculationOp.RATIO, {"numerator": 1.0, "denominator": 0.0}),
])
def test_zero_divisor_is_refused_not_silently_infinite(op, operands):
    with pytest.raises(CalculationError):
        build_calculation(op, {k: rec(k, v) for k, v in operands.items()})


def test_non_numeric_operand_is_refused():
    with pytest.raises(CalculationError, match="not a finite number"):
        build_calculation(CalculationOp.RATIO,
                          {"numerator": rec("N", "TABLET", unit=None), "denominator": rec("D", 2.0)})


def test_verify_calculation_accepts_untampered_spec():
    n, d = rec("N", 50.0), rec("D", 200.0)
    pool = RecordPool([n, d])
    spec = build_calculation(CalculationOp.RATIO_PERCENT, {"numerator": n, "denominator": d})
    assert verify_calculation(spec, pool, 1e-9) == []


def test_verify_calculation_detects_tampered_result():
    n, d = rec("N", 50.0), rec("D", 200.0)
    pool = RecordPool([n, d])
    spec = build_calculation(CalculationOp.RATIO_PERCENT, {"numerator": n, "denominator": d})
    spec.rounded_result = 99.99
    problems = verify_calculation(spec, pool, 1e-9)
    assert any("rounded_result" in p for p in problems)


def test_verify_calculation_detects_operand_drift_from_source():
    """The stored operand no longer matches the record it claims to come from."""
    n, d = rec("N", 50.0), rec("D", 200.0)
    pool = RecordPool([n, d])
    spec = build_calculation(CalculationOp.RATIO_PERCENT, {"numerator": n, "denominator": d})
    spec.operand_values["numerator"] = 75.0        # value drifted
    spec.raw_result = 37.5                          # arithmetic made self-consistent
    spec.rounded_result = 37.5
    problems = verify_calculation(spec, pool, 1e-9)
    assert any("source record" in p for p in problems), problems


def test_verify_calculation_detects_missing_operand_record():
    n, d = rec("N", 50.0), rec("D", 200.0)
    spec = build_calculation(CalculationOp.RATIO_PERCENT, {"numerator": n, "denominator": d})
    problems = verify_calculation(spec, RecordPool([n]), 1e-9)
    assert any("not in the pool" in p for p in problems)


def test_recompute_matches_generator_for_every_operation():
    cases = [
        (CalculationOp.RATIO_PERCENT, {"numerator": rec("a", 3.0), "denominator": rec("b", 8.0)}, None),
        (CalculationOp.GROWTH_PERCENT, {"current": rec("a", 12.0), "previous": rec("b", 10.0)}, None),
        (CalculationOp.DIFFERENCE, {"minuend": rec("a", 9.0), "subtrahend": rec("b", 4.0)}, None),
        (CalculationOp.RATIO, {"numerator": rec("a", 9.0), "denominator": rec("b", 4.0)}, None),
        (CalculationOp.SUM, {"x": rec("a", 1.5), "y": rec("b", 2.5)}, None),
    ]
    for op, operands, override in cases:
        spec = build_calculation(op, operands, values_override=override)
        assert math.isclose(recompute_calculation(spec), spec.raw_result, rel_tol=1e-12)


def test_format_number_avoids_scientific_notation():
    assert format_number(29298013000000.0) == "29,298,013,000,000"
    assert format_number(5.932915, 2) == "5.93"


def test_tolerance_reflects_presented_precision():
    assert numeric_tolerance_for(5.93, 2) == 0.005
    assert numeric_tolerance_for(1000.0, None) < 1e-5


def test_epoch_days_handles_partial_and_invalid_dates():
    assert epoch_days("1970-01-01") == 0.0
    assert epoch_days("2020-02") == epoch_days("2020-02-01")
    assert epoch_days("not-a-date") is None
    assert epoch_days("2021-13-45") is None
