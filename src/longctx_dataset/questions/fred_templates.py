"""FRED / ALFRED question templates.

FRED contributes something no other source in this benchmark can: the *same* observation
legitimately carries different values depending on which vintage you consult. That makes
version selection a real retrieval problem rather than a synthetic one, and it is why
the TEMPORAL_VERSION template here binds to an ALFRED vintage date.

Every gold answer is a value the St. Louis Fed published, or an arithmetic combination of
two such values recorded operand-by-operand.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from ..schemas import (
    AnswerType,
    CalculationOp,
    Domain,
    NormalizedRecord,
    QuestionFamily,
    QuestionType,
    UnanswerableSpec,
)
from .base import (
    CalculationError,
    QuestionTemplate,
    TemplateContext,
    build_calculation,
    format_number,
    numeric_tolerance_for,
    record_conditions,
    register_template,
)

SOURCE = "FRED_STLOUISFED"
API_VERSION = "fred-v1"
LICENSE = ("Federal Reserve Bank of St. Louis (FRED/ALFRED). See "
           "https://fred.stlouisfed.org/legal/")

# Frequency -> how to describe an observation date in a question, so that a quarterly
# date like 2021-01-01 is not mistaken for a January reading.
_PERIOD_PHRASE = {
    "Quarterly": "the quarter beginning {date}",
    "Monthly": "the month beginning {date}",
    "Weekly": "the week beginning {date}",
    "Daily": "{date}",
    "Annual": "the year beginning {date}",
}


def _period_phrase(rec: NormalizedRecord) -> str:
    """A gloss on the observation date, or '' when the date already speaks for itself.

    A quarterly observation dated 2021-01-01 covers a quarter, not a January -- saying so
    removes a real ambiguity. For a daily series the gloss would just repeat the date.
    """
    freq = rec.metadata.get("frequency") or "Monthly"
    phrase = _PERIOD_PHRASE.get(freq, "{date}").format(date=rec.period)
    return "" if phrase == rec.period else phrase


def _observations(records: List[NormalizedRecord]) -> List[NormalizedRecord]:
    """Current-vintage observations that carry a value."""
    return [r for r in records if r.record_type == "fred_observation" and r.value_numeric is not None]


def _describe(rec: NormalizedRecord) -> str:
    """Unambiguous identification of a series: id, title, unit, adjustment, frequency."""
    title = rec.metadata.get("series_title") or rec.concept_label
    bits = [f'FRED series {rec.concept} ("{title}")']
    if rec.unit:
        bits.append(f"measured in {rec.unit}")
    sa = rec.metadata.get("seasonal_adjustment")
    if sa:
        bits.append(sa.lower())
    freq = rec.metadata.get("frequency")
    if freq:
        bits.append(f"{freq.lower()} frequency")
    return ", ".join(bits)


@register_template
class FREDDirectObservation(QuestionTemplate):
    template_id = "FRED_DIRECT_OBSERVATION"
    domain = Domain.FRED
    question_type = QuestionType.DIRECT_RETRIEVAL
    id_prefix = "FRED"

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        pool = [r for r in _observations(ctx.records) if r.period >= "2015-01-01"]
        pool.sort(key=lambda r: r.record_id)
        rng = ctx.rng(self.template_id)
        rng.shuffle(pool)

        # Prefer observations that FRED actually revised. This is a selection rule, not a
        # fabrication -- the vintages are real either way. It matters for correctness as
        # much as for difficulty: the question tells the model to report the current
        # vintage "not a value from an earlier vintage", which is only a meaningful
        # instruction when earlier vintages are in the context to be confused with.
        revised = {
            (r.concept, r.period)
            for r in ctx.records
            if r.record_type == "fred_vintage_observation" and r.value_numeric is not None
        }
        pool.sort(key=lambda r: (r.concept, r.period) not in revised)

        out: List[QuestionFamily] = []
        seen: set = set()
        for rec in pool:
            if len(out) >= n:
                break
            key = (rec.entity_id, rec.concept, rec.period)
            if key in seen:
                continue
            seen.add(key)
            value = float(rec.value_numeric)
            decimals = None if float(value).is_integer() else 3
            question = (
                f"Using only the FRED records supplied in the context, what value does the "
                f"most recent vintage report for {_describe(rec)}, for the observation dated "
                f"{rec.period}"
                + (f" ({_period_phrase(rec)})" if _period_phrase(rec) else "")
                + "? Report the currently published figure exactly."
            )
            out.append(self.make_answerable(
                ctx,
                family_id=ctx.next_family_id(self.id_prefix),
                question=question,
                evidence=[(rec, "target_value")],
                gold_answer=format_number(value, decimals),
                gold_answer_normalized=value,
                answer_type=AnswerType.NUMERIC,
                answer_unit=rec.unit,
                numeric_tolerance=numeric_tolerance_for(value, decimals),
                target_conditions={"match_mode": "all", "records": [record_conditions(rec)]},
                source_name=SOURCE, api_version=API_VERSION, license_note=LICENSE,
            ))
        return out


@register_template
class FREDPercentChange(QuestionTemplate):
    template_id = "FRED_PERCENT_CHANGE"
    domain = Domain.FRED
    question_type = QuestionType.RETRIEVAL_CALCULATION
    id_prefix = "FRED"

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        by_series: Dict[Tuple[str, str], List[NormalizedRecord]] = defaultdict(list)
        for r in _observations(ctx.records):
            by_series[(r.entity_id, r.concept)].append(r)
        rng = ctx.rng(self.template_id)
        pairs: List[Tuple[NormalizedRecord, NormalizedRecord]] = []
        for key, values in by_series.items():
            series = sorted(values, key=lambda r: r.period)
            recent = [r for r in series if r.period >= "2015-01-01"] or series[-24:]
            if len(recent) < 2:
                continue
            for idx in range(1, len(recent)):
                cur = recent[idx]
                prev = next((r for r in reversed(recent[:idx]) if r.value_numeric), None)
                if prev is not None and prev.value_numeric:
                    pairs.append((cur, prev))
        pairs.sort(key=lambda pair: (pair[0].concept, pair[0].period, pair[1].period))
        rng.shuffle(pairs)

        out: List[QuestionFamily] = []
        seen: set = set()
        for cur, prev in pairs:
            if len(out) >= n:
                break
            key = (cur.concept, cur.period, prev.period)
            if key in seen:
                continue
            seen.add(key)
            try:
                spec = build_calculation(
                    CalculationOp.GROWTH_PERCENT, {"current": cur, "previous": prev},
                    decimals=2, result_unit="percent",
                )
            except CalculationError:
                continue
            question = (
                f"Using only the FRED records supplied in the context, calculate the percentage "
                f"change in {_describe(cur)} between the observation dated {prev.period} and the "
                f"observation dated {cur.period}. Use both values from the most recent vintage, "
                f"apply ((value_{cur.period} - value_{prev.period}) / value_{prev.period}) * 100, "
                f"and round to two decimal places."
            )
            out.append(self.make_answerable(
                ctx,
                family_id=ctx.next_family_id(self.id_prefix),
                question=question,
                evidence=[(cur, "current"), (prev, "previous")],
                gold_answer=f"{spec.rounded_result:.2f}%",
                gold_answer_normalized=spec.rounded_result,
                answer_type=AnswerType.PERCENT,
                answer_unit="percent",
                numeric_tolerance=numeric_tolerance_for(spec.rounded_result, 2),
                target_conditions={"match_mode": "all",
                                   "records": [record_conditions(cur), record_conditions(prev)]},
                source_name=SOURCE, calculation_spec=spec,
                api_version=API_VERSION, license_note=LICENSE,
            ))
        return out


@register_template
class FREDSpread(QuestionTemplate):
    """A genuine economic spread: two different series, same observation date, same unit."""

    template_id = "FRED_SERIES_SPREAD"
    domain = Domain.FRED
    question_type = QuestionType.RETRIEVAL_CALCULATION
    id_prefix = "FRED"

    # Pairs that are economically meaningful to subtract and share a unit.
    PAIRS = [("DGS10", "FEDFUNDS"), ("GS10", "FEDFUNDS"), ("UNRATE", "UNRATENSA"),
             ("CAUR", "TXUR"), ("NYUR", "FLUR")]

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        idx: Dict[Tuple[str, str], NormalizedRecord] = {
            (r.concept, r.period): r for r in _observations(ctx.records)
        }
        rng = ctx.rng(self.template_id)
        out: List[QuestionFamily] = []

        pair_periods: List[Tuple[str, str, str]] = []
        for a_id, b_id in self.PAIRS:
            shared = sorted({p for (c, p) in idx if c == a_id} & {p for (c, p) in idx if c == b_id})
            shared = [p for p in shared if p >= "2015-01-01"]
            pair_periods.extend((a_id, b_id, period) for period in shared)
        pair_periods.sort()
        rng.shuffle(pair_periods)

        seen: set = set()
        for a_id, b_id, period in pair_periods:
            if len(out) >= n:
                break
            key = (a_id, b_id, period)
            if key in seen:
                continue
            seen.add(key)
            a, b = idx[(a_id, period)], idx[(b_id, period)]
            if a.unit != b.unit or a.value_numeric == b.value_numeric:
                continue  # a spread across different units would be meaningless
            try:
                spec = build_calculation(
                    CalculationOp.DIFFERENCE, {"minuend": a, "subtrahend": b},
                    decimals=2, result_unit=a.unit,
                )
            except CalculationError:
                continue
            question = (
                f"Using only the FRED records supplied in the context, subtract the value of "
                f"{_describe(b)} from the value of {_describe(a)}, both for the observation dated "
                f"{period} and both taken from the most recent vintage. Report the difference in "
                f"{a.unit}, rounded to two decimal places."
            )
            out.append(self.make_answerable(
                ctx,
                family_id=ctx.next_family_id(self.id_prefix),
                question=question,
                evidence=[(a, "minuend"), (b, "subtrahend")],
                gold_answer=f"{spec.rounded_result:.2f}",
                gold_answer_normalized=spec.rounded_result,
                answer_type=AnswerType.NUMERIC,
                answer_unit=a.unit,
                numeric_tolerance=numeric_tolerance_for(spec.rounded_result, 2),
                target_conditions={"match_mode": "all",
                                   "records": [record_conditions(a), record_conditions(b)]},
                source_name=SOURCE, calculation_spec=spec,
                api_version=API_VERSION, license_note=LICENSE,
                note="cross-series spread; both operands share a unit by construction",
            ))
        return out


@register_template
class FREDVintageSelection(QuestionTemplate):
    """Bind to one ALFRED vintage of a revised observation.

    This is the strongest version-selection question in the benchmark because the
    competing values are all real: FRED genuinely published each of them, and only the
    named vintage is correct.
    """

    template_id = "FRED_VINTAGE_SELECTION"
    domain = Domain.FRED
    question_type = QuestionType.TEMPORAL_VERSION
    id_prefix = "FRED"

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        by_obs: Dict[Tuple[str, str], List[NormalizedRecord]] = defaultdict(list)
        for r in ctx.records:
            if r.record_type == "fred_vintage_observation" and r.value_numeric is not None:
                by_obs[(r.concept, r.period)].append(r)
        latest = {(r.concept, r.period): r for r in _observations(ctx.records)}

        rng = ctx.rng(self.template_id)
        # Only observations that were genuinely revised: at least two distinct values.
        keys = sorted(k for k, v in by_obs.items() if len({x.value_numeric for x in v}) >= 2)
        rng.shuffle(keys)

        out: List[QuestionFamily] = []
        seen: set = set()
        for key in keys:
            if len(out) >= n:
                break
            series_id, period = key
            if key in seen:
                continue
            vintages = sorted(by_obs[key], key=lambda r: str(r.metadata.get("vintage_date")))
            target = vintages[0]  # the earliest vintage: the value as first published here
            others = [v for v in vintages[1:] if v.value_numeric != target.value_numeric]
            if not others:
                continue
            seen.add(key)
            value = float(target.value_numeric)
            vdate = target.metadata.get("vintage_date")
            cur = latest.get(key)
            question = (
                f"Using only the FRED/ALFRED records supplied in the context, what value did "
                f"{_describe(target)} show for the observation dated {period} **as of the vintage "
                f"date {vdate}**? Report the value from that vintage exactly."
            )
            out.append(self.make_answerable(
                ctx,
                family_id=ctx.next_family_id(self.id_prefix),
                question=question,
                evidence=[(target, "target_value")],
                gold_answer=format_number(value, 3 if not float(value).is_integer() else None),
                gold_answer_normalized=value,
                answer_type=AnswerType.NUMERIC,
                answer_unit=target.unit,
                numeric_tolerance=numeric_tolerance_for(
                    value, 3 if not float(value).is_integer() else None),
                target_conditions={
                    "match_mode": "all",
                    "records": [record_conditions(target)],
                    "explicit_foils": [record_conditions(v) for v in others]
                                      + ([record_conditions(cur)] if cur else []),
                },
                source_name=SOURCE, api_version=API_VERSION, license_note=LICENSE,
                note="ALFRED vintage selection over an authentically revised observation",
            ))
        return out


@register_template
class FREDBasisBinding(QuestionTemplate):
    """Bind to the exact measurement basis when a same-family twin is in the context.

    Seasonally adjusted vs not, nominal vs chained dollars, national vs one state --
    all published by FRED under distinct series IDs for the same quantity.
    """

    template_id = "FRED_BASIS_BINDING"
    domain = Domain.FRED
    question_type = QuestionType.ENTITY_UNIT_BINDING
    id_prefix = "FRED"

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        obs = _observations(ctx.records)
        by_family_period: Dict[Tuple[str, str], List[NormalizedRecord]] = defaultdict(list)
        for r in obs:
            fam = r.metadata.get("series_family")
            if fam:
                by_family_period[(str(fam), r.period)].append(r)

        rng = ctx.rng(self.template_id)
        keys = sorted(k for k, v in by_family_period.items() if len({x.concept for x in v}) >= 2)
        keys = [k for k in keys if k[1] >= "2015-01-01"]
        rng.shuffle(keys)

        out: List[QuestionFamily] = []
        seen: set = set()
        for fam, period in keys:
            if len(out) >= n:
                break
            group = sorted(by_family_period[(fam, period)], key=lambda r: r.record_id)
            target = group[rng.randrange(len(group))]
            others = [g for g in group if g.concept != target.concept]
            if not others or (target.entity_id, target.concept) in seen:
                continue
            seen.add((target.entity_id, target.concept))
            value = float(target.value_numeric)
            decimals = None if float(value).is_integer() else 3
            question = (
                f"Using only the FRED records supplied in the context, report the value of "
                f"{_describe(target)} for {target.entity_name} on the observation dated {period}. "
                f"Report the value for series {target.concept} exactly."
            )
            out.append(self.make_answerable(
                ctx,
                family_id=ctx.next_family_id(self.id_prefix),
                question=question,
                evidence=[(target, "target_value")],
                gold_answer=format_number(value, decimals),
                gold_answer_normalized=value,
                answer_type=AnswerType.NUMERIC,
                answer_unit=target.unit,
                numeric_tolerance=numeric_tolerance_for(value, decimals),
                target_conditions={"match_mode": "all", "records": [record_conditions(target)],
                                   "explicit_foils": [record_conditions(o) for o in others]},
                source_name=SOURCE, api_version=API_VERSION, license_note=LICENSE,
                note=f"basis binding within series family {fam!r}",
            ))
        return out


@register_template
class FREDUnanswerableMissingObservation(QuestionTemplate):
    """Ask for a date on which FRED publishes no observation for that series.

    Authentic rather than relabelled: the St. Louis Fed CSV returns an empty cell for
    these dates (market holidays for daily series, dates outside a series' published
    range). The adapter preserves them as ``observation_missing`` records, which are
    never rendered into a context, so no variant at any length can contain the value.
    """

    template_id = "FRED_UNANSWERABLE_NO_OBSERVATION"
    domain = Domain.FRED
    question_type = QuestionType.UNANSWERABLE
    id_prefix = "FRED"

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        missing = sorted(
            [r for r in ctx.records if r.record_type == "observation_missing"],
            key=lambda r: (r.period or "", r.record_id), reverse=True,
        )
        if not missing:
            return []
        rng = ctx.rng(self.template_id)
        head = missing[: max(200, n * 25)]
        rng.shuffle(head)

        out: List[QuestionFamily] = []
        seen: set = set()
        for rec in head:
            if len(out) >= n:
                break
            key = (rec.concept, rec.period)
            if key in seen:
                continue
            # Absence must be provable: no valued record may share these coordinates.
            present = [
                r for r in ctx.pool.matches_target(
                    entity_id=rec.entity_id, concept=rec.concept, period=rec.period)
                if r.value_numeric is not None
            ]
            if present:
                continue
            seen.add(key)
            question = (
                f"Using only the FRED records supplied in the context, what value does FRED "
                f"report for {_describe(rec)}, for the observation dated {rec.period}?"
            )
            spec = UnanswerableSpec(
                reason_code="NO_OBSERVATION_PUBLISHED",
                reason=(
                    f"The St. Louis Fed returns an empty observation for {rec.concept} on "
                    f"{rec.period} — the series publishes no value for that date (a non-trading "
                    f"day for daily series, or a date outside the published range). Verified by "
                    f"exhaustive scan of the normalized pool: zero valued records match "
                    f"entity_id={rec.entity_id}, concept={rec.concept}, period={rec.period}. "
                    f"Empty observations are never rendered into a context."
                ),
                missing_concept=rec.concept,
                missing_period=rec.period,
                missing_entity_id=rec.entity_id,
                verified_absent_in_pool=True,
                forbidden_concept_aliases=[rec.concept],
            )
            out.append(self.make_unanswerable(
                ctx,
                family_id=ctx.next_family_id(self.id_prefix),
                question=question,
                spec=spec,
                target_conditions={"match_mode": "all", "records": [{
                    "entity_id": rec.entity_id, "entity_name": rec.entity_name,
                    "concept": rec.concept, "period": rec.period, "unit": rec.unit,
                    "version": None,
                }]},
                source_name=SOURCE, context_records=[rec],
                api_version=API_VERSION, license_note=LICENSE,
            ))
        return out
