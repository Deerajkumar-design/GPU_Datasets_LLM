"""SEC EDGAR XBRL question templates.

Every question is phrased against an XBRL *frame* (``CY2023``, ``CY2023Q2``,
``CY2023Q4I``) because frames are calendar-aligned and unique per company/concept/unit.
That removes the fiscal-calendar ambiguity that would otherwise make a gold answer
arguable, which matters more here than surface naturalness.
"""

from __future__ import annotations

import re
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

SOURCE = "SEC_EDGAR_XBRL_COMPANYFACTS"
API_VERSION = "xbrl-companyfacts-v1"
LICENSE = "US SEC EDGAR, public domain"

REVENUE_CONCEPTS = [
    "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
    "us-gaap:Revenues",
]
_ANNUAL_FRAME = re.compile(r"^CY\d{4}$")
_QUARTER_FRAME = re.compile(r"^CY(\d{4})(Q[1-3])$")


def _framed(records: List[NormalizedRecord], kind: Optional[str] = None) -> List[NormalizedRecord]:
    """Facts carrying an SEC calendar frame, optionally restricted to a period kind."""
    out = [r for r in records if r.metadata.get("has_frame") and r.value_numeric is not None]
    if kind:
        out = [r for r in out if r.metadata.get("period_kind") == kind]
    return out


def _key_index(records: List[NormalizedRecord]) -> Dict[Tuple[str, str, str, str], NormalizedRecord]:
    return {(r.entity_id, r.concept, r.period, r.unit or ""): r for r in records}


def _short_name(rec: NormalizedRecord) -> str:
    return rec.entity_name


@register_template
class SECDirectFact(QuestionTemplate):
    template_id = "SEC_DIRECT_XBRL_FACT"
    domain = Domain.SEC
    question_type = QuestionType.DIRECT_RETRIEVAL
    id_prefix = "SEC"

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        pool = [r for r in _framed(ctx.records, "annual") if r.unit == "USD"]
        if not pool:
            pool = _framed(ctx.records, "annual")
        pool = [r for r in pool if r.period >= "CY2015"] or pool
        pool.sort(key=lambda r: r.record_id)
        rng = ctx.rng(self.template_id)
        rng.shuffle(pool)

        out: List[QuestionFamily] = []
        seen: set = set()
        for rec in pool:
            if len(out) >= n:
                break
            key = (rec.entity_id, rec.concept)
            if key in seen:
                continue
            seen.add(key)
            value = float(rec.value_numeric)
            question = (
                f"Using only the SEC XBRL company-facts records supplied in the context, what value did "
                f"{_short_name(rec)} (CIK {rec.entity_id}) report for the us-gaap concept "
                f"\"{rec.metadata.get('tag')}\" ({rec.concept_label}) for the annual XBRL frame "
                f"{rec.period}, in {rec.unit}? Report the exact reported figure."
            )
            out.append(self.make_answerable(
                ctx,
                family_id=ctx.next_family_id(self.id_prefix),
                question=question,
                evidence=[(rec, "target_value")],
                gold_answer=format_number(value),
                gold_answer_normalized=value,
                answer_type=AnswerType.NUMERIC,
                answer_unit=rec.unit,
                numeric_tolerance=numeric_tolerance_for(value, None),
                target_conditions={"match_mode": "all", "records": [record_conditions(rec)]},
                source_name=SOURCE, api_version=API_VERSION, license_note=LICENSE,
            ))
        return out


@register_template
class SECOperatingMargin(QuestionTemplate):
    """The canonical two-operand financial ratio, computed from two real XBRL facts."""

    template_id = "SEC_OPERATING_MARGIN"
    domain = Domain.SEC
    question_type = QuestionType.RETRIEVAL_CALCULATION
    id_prefix = "SEC"

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        annual = [r for r in _framed(ctx.records, "annual") if r.unit == "USD"]
        idx = _key_index(annual)
        rng = ctx.rng(self.template_id)
        combos = sorted({(r.entity_id, r.period) for r in annual
                         if r.concept == "us-gaap:OperatingIncomeLoss"})
        rng.shuffle(combos)

        out: List[QuestionFamily] = []
        seen: set = set()
        for cik, frame in combos:
            if len(out) >= n:
                break
            op = idx.get((cik, "us-gaap:OperatingIncomeLoss", frame, "USD"))
            rev = next((idx[(cik, c, frame, "USD")] for c in REVENUE_CONCEPTS
                        if (cik, c, frame, "USD") in idx), None)
            if op is None or rev is None or (cik in seen):
                continue
            try:
                spec = build_calculation(
                    CalculationOp.RATIO_PERCENT,
                    {"numerator": op, "denominator": rev},
                    decimals=2, result_unit="percent",
                )
            except CalculationError:
                continue
            seen.add(cik)
            question = (
                f"Using only the SEC XBRL company-facts records supplied in the context, calculate "
                f"{_short_name(op)}'s (CIK {cik}) operating margin for the annual XBRL frame {frame}. "
                f"Divide us-gaap:OperatingIncomeLoss by {rev.metadata.get('tag')} for that same company "
                f"and frame, both in USD, multiply by 100, and round to two decimal places."
            )
            out.append(self.make_answerable(
                ctx,
                family_id=ctx.next_family_id(self.id_prefix),
                question=question,
                evidence=[(op, "numerator"), (rev, "denominator")],
                gold_answer=f"{spec.rounded_result:.2f}%",
                gold_answer_normalized=spec.rounded_result,
                answer_type=AnswerType.PERCENT,
                answer_unit="percent",
                numeric_tolerance=numeric_tolerance_for(spec.rounded_result, 2),
                target_conditions={"match_mode": "all",
                                   "records": [record_conditions(op), record_conditions(rev)]},
                source_name=SOURCE, calculation_spec=spec,
                api_version=API_VERSION, license_note=LICENSE,
            ))
        return out


@register_template
class SECYoYGrowth(QuestionTemplate):
    template_id = "SEC_YOY_GROWTH_PERCENT"
    domain = Domain.SEC
    question_type = QuestionType.RETRIEVAL_CALCULATION
    id_prefix = "SEC"

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        annual = [r for r in _framed(ctx.records, "annual") if r.unit == "USD"]
        idx = _key_index(annual)
        rng = ctx.rng(self.template_id)
        pairs: List[Tuple[NormalizedRecord, NormalizedRecord]] = []
        for rec in annual:
            m = _ANNUAL_FRAME.match(rec.period or "")
            if not m:
                continue
            prev = idx.get((rec.entity_id, rec.concept, f"CY{int(rec.period[2:]) - 1}", "USD"))
            if prev is not None and prev.value_numeric:
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
                f"Using only the SEC XBRL company-facts records supplied in the context, calculate the "
                f"year-over-year percentage change in {_short_name(cur)}'s (CIK {cur.entity_id}) reported "
                f"us-gaap:{cur.metadata.get('tag')} from annual XBRL frame {prev.period} to annual XBRL "
                f"frame {cur.period}, both in USD. Use ((current - previous) / previous) * 100 and round "
                f"to two decimal places."
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
class SECQuarterVsAnnual(QuestionTemplate):
    """Force a choice between a quarter and the full year that contains it."""

    template_id = "SEC_QUARTER_VS_ANNUAL_FRAME"
    domain = Domain.SEC
    question_type = QuestionType.TEMPORAL_VERSION
    id_prefix = "SEC"

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        framed = _framed(ctx.records)
        idx = _key_index(framed)
        quarters = [r for r in framed if r.metadata.get("period_kind") == "quarterly" and r.unit == "USD"]
        quarters.sort(key=lambda r: r.record_id)
        rng = ctx.rng(self.template_id)
        rng.shuffle(quarters)

        out: List[QuestionFamily] = []
        seen: set = set()
        for q in quarters:
            if len(out) >= n:
                break
            m = _QUARTER_FRAME.match(q.period or "")
            if not m:
                continue
            annual = idx.get((q.entity_id, q.concept, f"CY{m.group(1)}", "USD"))
            if annual is None or annual.value_numeric == q.value_numeric:
                continue
            key = (q.entity_id, q.concept)
            if key in seen:
                continue
            seen.add(key)
            value = float(q.value_numeric)
            question = (
                f"Using only the SEC XBRL company-facts records supplied in the context, what did "
                f"{_short_name(q)} (CIK {q.entity_id}) report for us-gaap:{q.metadata.get('tag')} for the "
                f"single quarterly XBRL frame {q.period}, in USD? Report the quarterly figure exactly."
            )
            out.append(self.make_answerable(
                ctx,
                family_id=ctx.next_family_id(self.id_prefix),
                question=question,
                evidence=[(q, "target_value")],
                gold_answer=format_number(value),
                gold_answer_normalized=value,
                answer_type=AnswerType.NUMERIC,
                answer_unit=q.unit,
                numeric_tolerance=numeric_tolerance_for(value, None),
                target_conditions={"match_mode": "all", "records": [record_conditions(q)],
                                   "explicit_foils": [record_conditions(annual)]},
                source_name=SOURCE, api_version=API_VERSION, license_note=LICENSE,
                note="quarterly vs annual frame disambiguation",
            ))
        return out


@register_template
class SECRestatementVersion(QuestionTemplate):
    """Same company, concept and period reported with different values in different filings.

    These are authentic restatements/revisions: two accession numbers, two values. Only
    emitted when such pairs genuinely exist in the retrieved facts.
    """

    template_id = "SEC_FILING_VERSION_SELECTION"
    domain = Domain.SEC
    question_type = QuestionType.TEMPORAL_VERSION
    id_prefix = "SEC"

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        groups: Dict[Tuple, List[NormalizedRecord]] = defaultdict(list)
        for r in ctx.records:
            if r.value_numeric is None or not r.period_end:
                continue
            groups[(r.entity_id, r.concept, r.unit, r.period_start, r.period_end)].append(r)

        rng = ctx.rng(self.template_id)
        candidates = []
        for key, recs in groups.items():
            values = {r.value_numeric for r in recs}
            accns = {r.metadata.get("accn") for r in recs}
            if len(values) >= 2 and len(accns) >= 2:
                candidates.append((key, sorted(recs, key=lambda r: (str(r.metadata.get("filed")), r.record_id))))
        candidates.sort(key=lambda c: str(c[0]))
        rng.shuffle(candidates)

        out: List[QuestionFamily] = []
        seen: set = set()
        for key, recs in candidates:
            if len(out) >= n:
                break
            first, last = recs[0], recs[-1]
            if first.value_numeric == last.value_numeric or key[0] in seen:
                continue
            seen.add(key[0])
            value = float(last.value_numeric)
            question = (
                f"Using only the SEC XBRL company-facts records supplied in the context, what value did "
                f"{_short_name(last)} (CIK {last.entity_id}) report for us-gaap:{last.metadata.get('tag')} "
                f"for the period ending {last.period_end} in the MOST RECENTLY FILED version of that fact "
                f"— accession {last.metadata.get('accn')}, form {last.metadata.get('form')}, filed "
                f"{last.metadata.get('filed')} — in {last.unit}? Report the exact value from that version."
            )
            out.append(self.make_answerable(
                ctx,
                family_id=ctx.next_family_id(self.id_prefix),
                question=question,
                evidence=[(last, "target_value")],
                gold_answer=format_number(value),
                gold_answer_normalized=value,
                answer_type=AnswerType.NUMERIC,
                answer_unit=last.unit,
                numeric_tolerance=numeric_tolerance_for(value, None),
                target_conditions={"match_mode": "all", "records": [record_conditions(last)],
                                   "explicit_foils": [record_conditions(first)]},
                source_name=SOURCE, api_version=API_VERSION, license_note=LICENSE,
                note="authentic restatement: same concept/period, two accession numbers, two values",
            ))
        return out


@register_template
class SECEntityBinding(QuestionTemplate):
    """Same concept and frame across several filers; the question names one CIK."""

    template_id = "SEC_ENTITY_BINDING"
    domain = Domain.SEC
    question_type = QuestionType.ENTITY_UNIT_BINDING
    id_prefix = "SEC"

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        annual = [r for r in _framed(ctx.records, "annual") if r.unit == "USD"]
        by_cf: Dict[Tuple[str, str], List[NormalizedRecord]] = defaultdict(list)
        for r in annual:
            by_cf[(r.concept, r.period)].append(r)
        rng = ctx.rng(self.template_id)
        keys = sorted(k for k, v in by_cf.items() if len({x.entity_id for x in v}) >= 3)
        rng.shuffle(keys)

        out: List[QuestionFamily] = []
        seen: set = set()
        for concept, frame in keys:
            if len(out) >= n:
                break
            peers = sorted(by_cf[(concept, frame)], key=lambda r: r.record_id)
            target = peers[rng.randrange(len(peers))]
            if (target.entity_id, concept) in seen:
                continue
            others = [p for p in peers if p.entity_id != target.entity_id][:3]
            if not others:
                continue
            seen.add((target.entity_id, concept))
            value = float(target.value_numeric)
            question = (
                f"Using only the SEC XBRL company-facts records supplied in the context, what value did "
                f"{_short_name(target)} (CIK {target.entity_id}) "
                f"report for us-gaap:{target.metadata.get('tag')} for the annual XBRL frame {frame}, in "
                f"{target.unit}? Report the exact value for that filer."
            )
            out.append(self.make_answerable(
                ctx,
                family_id=ctx.next_family_id(self.id_prefix),
                question=question,
                evidence=[(target, "target_value")],
                gold_answer=format_number(value),
                gold_answer_normalized=value,
                answer_type=AnswerType.NUMERIC,
                answer_unit=target.unit,
                numeric_tolerance=numeric_tolerance_for(value, None),
                target_conditions={"match_mode": "all", "records": [record_conditions(target)],
                                   "explicit_foils": [record_conditions(p) for p in others]},
                source_name=SOURCE, api_version=API_VERSION, license_note=LICENSE,
                note="entity binding across same-concept, same-frame peer filers",
            ))
        return out


@register_template
class SECUnanswerableConceptNotReported(QuestionTemplate):
    """Ask a filer for a us-gaap concept it does not report, or for a frame it predates.

    Absence is verified against the whole normalized pool before the family is emitted,
    so no context at any length can contain a satisfying record.
    """

    template_id = "SEC_UNANSWERABLE_CONCEPT_OR_PERIOD_ABSENT"
    domain = Domain.SEC
    question_type = QuestionType.UNANSWERABLE
    id_prefix = "SEC"

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        records = ctx.records
        if not records:
            return []
        entities = sorted({(r.entity_id, r.entity_name) for r in records})
        concepts = sorted({r.concept for r in records})
        labels = {r.concept: r.concept_label for r in records}
        tags = {r.concept: r.metadata.get("tag") for r in records}
        reported: Dict[str, set] = defaultdict(set)
        for r in records:
            reported[r.entity_id].add(r.concept)

        rng = ctx.rng(self.template_id)
        combos = [(cik, name, c) for cik, name in entities for c in concepts if c not in reported[cik]]
        combos.sort()
        rng.shuffle(combos)

        out: List[QuestionFamily] = []
        seen: set = set()
        frame = "CY2023"
        for cik, name, concept in combos:
            if len(out) >= n:
                break
            key = (cik, concept)
            if key in seen:
                continue
            if ctx.pool.matches_target(entity_id=cik, concept=concept):
                continue  # absence must be provable, not assumed
            seen.add(key)
            question = (
                f"Using only the SEC XBRL company-facts records supplied in the context, what value did "
                f"{name} (CIK {cik}) report for the us-gaap concept \"{tags.get(concept) or concept}\" "
                f"({labels.get(concept, concept)}) for the annual XBRL frame {frame}?"
            )
            spec = UnanswerableSpec(
                reason_code="CONCEPT_NOT_REPORTED_BY_FILER",
                reason=(
                    f"CIK {cik} reports no facts under {concept} anywhere in the retrieved company-facts "
                    f"payload, while other filers in the pool do. Verified by exhaustive scan of the "
                    f"normalized pool: zero records match entity_id={cik} and concept={concept}."
                ),
                missing_concept=concept,
                missing_period=frame,
                missing_entity_id=cik,
                verified_absent_in_pool=True,
                forbidden_concept_aliases=[concept],
            )
            out.append(self.make_unanswerable(
                ctx,
                family_id=ctx.next_family_id(self.id_prefix),
                question=question,
                spec=spec,
                target_conditions={"match_mode": "all", "records": [{
                    "entity_id": cik, "entity_name": name, "concept": concept,
                    "period": frame, "unit": None, "version": None,
                }]},
                source_name=SOURCE,
                context_records=[r for r in records if r.entity_id == cik][:1],
                api_version=API_VERSION, license_note=LICENSE,
            ))
        return out
