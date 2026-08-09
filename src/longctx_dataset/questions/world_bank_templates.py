"""World Bank Indicators question templates.

Interference here comes from the indicator space itself: the same concept measured in
current vs constant dollars, per-capita vs total, and % of GDP variants all sit side by
side with near-identical names, across 20 countries and 35 years.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

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

SOURCE = "WORLD_BANK_INDICATORS_V2"
API_VERSION = "v2"
LICENSE = "World Bank Open Data, CC BY-4.0"

# Indicator pairs that a careless reader conflates: same underlying quantity, different
# unit or basis. These drive the ENTITY_UNIT_BINDING questions and the WRONG_UNIT
# distractors, and are declared here rather than inferred so the intent is auditable.
CONFUSABLE_PAIRS: List[Tuple[str, str, str]] = [
    ("NY.GDP.MKTP.KD", "NY.GDP.MKTP.CD", "constant 2015 US$ versus current US$"),
    ("NY.GDP.PCAP.CD", "NY.GDP.MKTP.CD", "per-capita versus total GDP"),
    ("NE.EXP.GNFS.ZS", "NE.IMP.GNFS.ZS", "exports versus imports, both as % of GDP"),
    ("SP.POP.GROW", "NY.GDP.MKTP.KD.ZG", "population growth versus GDP growth"),
]


def _valued(records: List[NormalizedRecord]) -> List[NormalizedRecord]:
    return [r for r in records if r.record_type == "indicator_observation" and r.value_numeric is not None]


def _index(records: List[NormalizedRecord]) -> Dict[Tuple[str, str, str], NormalizedRecord]:
    return {(r.entity_id, r.concept, r.period): r for r in records}


def _unit_phrase(rec: NormalizedRecord) -> str:
    return f" (unit: {rec.unit})" if rec.unit else ""


@register_template
class WBDirectRetrieval(QuestionTemplate):
    template_id = "WB_DIRECT_INDICATOR_VALUE"
    domain = Domain.WORLD_BANK
    question_type = QuestionType.DIRECT_RETRIEVAL
    id_prefix = "WB"

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        pool = _valued(ctx.records)
        if not pool:
            return []
        rng = ctx.rng(self.template_id)
        # Prefer recent, widely-populated observations so the question is unambiguous.
        candidates = sorted(
            [r for r in pool if r.period and r.period >= "2005"],
            key=lambda r: r.record_id,
        ) or sorted(pool, key=lambda r: r.record_id)
        rng.shuffle(candidates)

        out: List[QuestionFamily] = []
        seen: set = set()
        for rec in candidates:
            if len(out) >= n:
                break
            key = (rec.entity_id, rec.concept)
            if key in seen:
                continue  # one family per country x indicator keeps the pilot diverse
            seen.add(key)
            value = float(rec.value_numeric)
            decimals = None if float(value).is_integer() else 3
            question = (
                f"Using the World Bank Indicators data supplied in the context, what value is "
                f"reported for the indicator \"{rec.concept_label}\" (indicator code {rec.concept}) "
                f"for {rec.entity_name} ({rec.entity_id}) in the year {rec.period}? "
                f"Report the value exactly as recorded{_unit_phrase(rec)}."
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
class WBGrowthCalculation(QuestionTemplate):
    template_id = "WB_INDICATOR_GROWTH_PERCENT"
    domain = Domain.WORLD_BANK
    question_type = QuestionType.RETRIEVAL_CALCULATION
    id_prefix = "WB"

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        pool = _valued(ctx.records)
        idx = _index(pool)
        rng = ctx.rng(self.template_id)
        pairs: List[Tuple[NormalizedRecord, NormalizedRecord]] = []
        for rec in pool:
            if not rec.period or not rec.period.isdigit():
                continue
            prev_key = (rec.entity_id, rec.concept, str(int(rec.period) - 1))
            prev = idx.get(prev_key)
            if prev is not None and prev.value_numeric not in (None, 0):
                pairs.append((rec, prev))
        pairs.sort(key=lambda p: (p[0].record_id, p[1].record_id))
        rng.shuffle(pairs)

        out: List[QuestionFamily] = []
        seen: set = set()
        for cur, prev in pairs:
            if len(out) >= n:
                break
            key = (cur.entity_id, cur.concept)
            if key in seen:
                continue
            try:
                spec = build_calculation(
                    CalculationOp.GROWTH_PERCENT,
                    {"current": cur, "previous": prev},
                    decimals=2, result_unit="percent",
                )
            except CalculationError:
                continue
            seen.add(key)
            question = (
                f"Using only the World Bank Indicators records supplied in the context, calculate the "
                f"percentage change in \"{cur.concept_label}\" (indicator code {cur.concept}) for "
                f"{cur.entity_name} ({cur.entity_id}) from {prev.period} to {cur.period}. "
                f"Use the formula ((value_{cur.period} - value_{prev.period}) / value_{prev.period}) * 100 "
                f"and round the result to two decimal places."
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
class WBCrossIndicatorRatio(QuestionTemplate):
    """GDP per capita recomputed from total GDP and population.

    Deliberately a *cross-indicator* calculation: the answer cannot be copied from any
    single record, and the World Bank's own per-capita indicator sits in the context as
    a NEAR_MATCH_VALUE distractor.
    """

    template_id = "WB_CROSS_INDICATOR_RATIO"
    domain = Domain.WORLD_BANK
    question_type = QuestionType.RETRIEVAL_CALCULATION
    id_prefix = "WB"

    NUM = "NY.GDP.MKTP.CD"
    DEN = "SP.POP.TOTL"

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        pool = _valued(ctx.records)
        idx = _index(pool)
        rng = ctx.rng(self.template_id)
        combos = sorted(
            {(r.entity_id, r.period) for r in pool if r.concept == self.NUM and r.period}
        )
        rng.shuffle(combos)

        out: List[QuestionFamily] = []
        for entity, period in combos:
            if len(out) >= n:
                break
            num = idx.get((entity, self.NUM, period))
            den = idx.get((entity, self.DEN, period))
            if num is None or den is None:
                continue
            try:
                spec = build_calculation(
                    CalculationOp.RATIO,
                    {"numerator": num, "denominator": den},
                    decimals=2, result_unit="current US$ per person",
                )
            except CalculationError:
                continue
            question = (
                f"Using only the World Bank Indicators records supplied in the context, compute GDP per "
                f"person for {num.entity_name} ({entity}) in {period} by dividing \"{num.concept_label}\" "
                f"(indicator {self.NUM}) by \"{den.concept_label}\" (indicator {self.DEN}) for that same "
                f"country and year. Round the result to two decimal places and report it in current US$ "
                f"per person. Do not copy a pre-computed per-capita indicator; derive the value."
            )
            out.append(self.make_answerable(
                ctx,
                family_id=ctx.next_family_id(self.id_prefix),
                question=question,
                evidence=[(num, "numerator"), (den, "denominator")],
                gold_answer=f"{spec.rounded_result:,.2f} current US$ per person",
                gold_answer_normalized=spec.rounded_result,
                answer_type=AnswerType.NUMERIC,
                answer_unit="current US$ per person",
                numeric_tolerance=numeric_tolerance_for(spec.rounded_result, 2),
                target_conditions={"match_mode": "all",
                                   "records": [record_conditions(num), record_conditions(den)]},
                source_name=SOURCE, calculation_spec=spec,
                api_version=API_VERSION, license_note=LICENSE,
                note="cross-indicator ratio; the World Bank's own NY.GDP.PCAP.CD is a near-match distractor",
            ))
        return out


@register_template
class WBTemporalSelection(QuestionTemplate):
    """Pick the year, among several supplied, at which an indicator peaked."""

    template_id = "WB_TEMPORAL_MAX_YEAR"
    domain = Domain.WORLD_BANK
    question_type = QuestionType.TEMPORAL_VERSION
    id_prefix = "WB"

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        pool = _valued(ctx.records)
        by_series: Dict[Tuple[str, str], List[NormalizedRecord]] = {}
        for r in pool:
            if r.period and r.period.isdigit():
                by_series.setdefault((r.entity_id, r.concept), []).append(r)
        rng = ctx.rng(self.template_id)
        series_keys = sorted(k for k, v in by_series.items() if len(v) >= 6)
        rng.shuffle(series_keys)

        out: List[QuestionFamily] = []
        for key in series_keys:
            if len(out) >= n:
                break
            recs = sorted(by_series[key], key=lambda r: r.period)
            window = [r for r in recs if r.period >= "2010"] or recs[-6:]
            if len(window) < 4:
                continue
            chosen = sorted(rng.sample(window, 4), key=lambda r: r.period)
            values = [r.value_numeric for r in chosen]
            best = max(chosen, key=lambda r: r.value_numeric)
            # Reject ties: the answer must be unique to be gradable.
            if sum(1 for v in values if v == best.value_numeric) != 1:
                continue
            years = ", ".join(r.period for r in chosen)
            question = (
                f"Using only the World Bank Indicators records supplied in the context, in which of the "
                f"following years did {best.entity_name} ({best.entity_id}) record its highest value of "
                f"\"{best.concept_label}\" (indicator code {best.concept})? Consider only these years: "
                f"{years}. Answer with the four-digit year."
            )
            out.append(self.make_answerable(
                ctx,
                family_id=ctx.next_family_id(self.id_prefix),
                question=question,
                evidence=[(r, "candidate_year" if r is not best else "max_year") for r in chosen],
                gold_answer=best.period,
                gold_answer_normalized=best.period,
                answer_type=AnswerType.CATEGORICAL,
                answer_unit=None,
                numeric_tolerance=None,
                target_conditions={"match_mode": "all",
                                   "records": [record_conditions(r) for r in chosen]},
                source_name=SOURCE, api_version=API_VERSION, license_note=LICENSE,
                note="temporal selection among four same-series observations",
            ))
        return out


@register_template
class WBUnitBinding(QuestionTemplate):
    """Bind to the exact indicator when a near-twin with a different unit is present."""

    template_id = "WB_UNIT_BASIS_BINDING"
    domain = Domain.WORLD_BANK
    question_type = QuestionType.ENTITY_UNIT_BINDING
    id_prefix = "WB"

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        pool = _valued(ctx.records)
        idx = _index(pool)
        rng = ctx.rng(self.template_id)
        combos: List[Tuple[str, str, str, str, str]] = []
        for target_ind, foil_ind, note in CONFUSABLE_PAIRS:
            for r in pool:
                if r.concept != target_ind or not r.period:
                    continue
                if (r.entity_id, foil_ind, r.period) in idx:
                    combos.append((r.entity_id, r.period, target_ind, foil_ind, note))
        combos.sort()
        rng.shuffle(combos)

        out: List[QuestionFamily] = []
        seen: set = set()
        for entity, period, target_ind, foil_ind, note in combos:
            if len(out) >= n:
                break
            if (entity, target_ind) in seen:
                continue
            target = idx[(entity, target_ind, period)]
            foil = idx[(entity, foil_ind, period)]
            seen.add((entity, target_ind))
            value = float(target.value_numeric)
            decimals = None if float(value).is_integer() else 3
            question = (
                f"Using only the World Bank Indicators records supplied in the context, report the value of "
                f"\"{target.concept_label}\" — indicator code {target.concept}, unit "
                f"{target.unit or 'as recorded'} — for {target.entity_name} ({entity}) in {period}. "
                f"Note that the context also contains \"{foil.concept_label}\" (indicator code {foil.concept}) "
                f"for the same country and year; that is a different measure ({note}) and is not the answer."
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
                                   "explicit_foils": [record_conditions(foil)]},
                source_name=SOURCE, api_version=API_VERSION, license_note=LICENSE,
                note=f"unit/basis binding against {foil_ind} ({note})",
            ))
        return out


@register_template
class WBUnanswerableMissingObservation(QuestionTemplate):
    """Ask for a country-year the World Bank genuinely does not report.

    This is authentically unanswerable rather than relabelled: the API returned an
    observation object with ``value: null``, which the adapter preserved as an
    ``observation_missing`` record. Such records are never rendered into a context, so
    no context variant at any length can contain the value.
    """

    template_id = "WB_UNANSWERABLE_NO_OBSERVATION"
    domain = Domain.WORLD_BANK
    question_type = QuestionType.UNANSWERABLE
    id_prefix = "WB"

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        missing = sorted(
            [r for r in ctx.records if r.record_type == "observation_missing"],
            key=lambda r: r.record_id,
        )
        if not missing:
            return []
        rng = ctx.rng(self.template_id)
        # Prefer recent years: a missing recent observation is a more natural question
        # than one from a decade the dataset barely covers.
        missing.sort(key=lambda r: (r.period or "", r.record_id), reverse=True)
        head = missing[: max(200, n * 20)]
        rng.shuffle(head)

        out: List[QuestionFamily] = []
        seen: set = set()
        for rec in head:
            if len(out) >= n:
                break
            key = (rec.entity_id, rec.concept)
            if key in seen:
                continue
            # Hard requirement: nothing in the pool may satisfy these conditions.
            present = [
                r for r in ctx.pool.matches_target(
                    entity_id=rec.entity_id, concept=rec.concept, period=rec.period
                )
                if r.value_numeric is not None
            ]
            if present:
                continue
            seen.add(key)
            question = (
                f"Using only the World Bank Indicators records supplied in the context, what value is "
                f"reported for the indicator \"{rec.concept_label}\" (indicator code {rec.concept}) for "
                f"{rec.entity_name} ({rec.entity_id}) in the year {rec.period}? If the supplied records do "
                f"not contain this value, state that the evidence is insufficient rather than estimating."
            )
            spec = UnanswerableSpec(
                reason_code="NO_VALUE_REPORTED_IN_SOURCE",
                reason=(
                    f"The World Bank Indicators API returned an observation for "
                    f"{rec.entity_id}/{rec.concept}/{rec.period} with a null value, so the primary source "
                    f"itself reports no figure. No record with a value satisfying these conditions exists "
                    f"anywhere in the normalized pool, and null observations are never rendered into a context."
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
                    "concept": rec.concept, "period": rec.period, "unit": rec.unit, "version": None,
                }]},
                source_name=SOURCE, context_records=[rec],
                api_version=API_VERSION, license_note=LICENSE,
            ))
        return out
