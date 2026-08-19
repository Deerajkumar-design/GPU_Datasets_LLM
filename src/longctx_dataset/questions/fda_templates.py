"""Drugs@FDA question templates.

The interference here is near-duplication: one active ingredient appears under dozens of
application numbers, from different sponsors, at several strengths, in several dosage
forms and routes. Answering requires binding to an exact (application, product) pair
rather than to the drug name.
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

SOURCE = "OPENFDA_DRUGSFDA"
API_VERSION = "openfda-drugsfda"
LICENSE = "openFDA (public domain); results are unvalidated per openFDA terms."

# A single product may list several active ingredients under one concept, so the
# ingredient identity is needed to pin a strength question to exactly one record.
STRENGTH_KEYS = ("ingredient_name", "ingredient_index")


def _by_concept(records: List[NormalizedRecord], concept: str) -> List[NormalizedRecord]:
    return [r for r in records if r.concept == concept]


def _entity_index(records: List[NormalizedRecord]) -> Dict[Tuple[str, str], NormalizedRecord]:
    return {(r.entity_id, r.concept): r for r in records}


@register_template
class FDADirectProductAttribute(QuestionTemplate):
    template_id = "FDA_DIRECT_PRODUCT_ATTRIBUTE"
    domain = Domain.FDA
    question_type = QuestionType.DIRECT_RETRIEVAL
    id_prefix = "FDA"

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        pool = sorted(_by_concept(ctx.records, "product.dosage_form"), key=lambda r: r.record_id)
        rng = ctx.rng(self.template_id)
        rng.shuffle(pool)

        out: List[QuestionFamily] = []
        seen: set = set()
        for rec in pool:
            if len(out) >= n:
                break
            appno = rec.metadata.get("application_number")
            prodno = rec.metadata.get("product_number")
            if appno in seen:
                continue
            seen.add(appno)
            ing = ", ".join(rec.metadata.get("active_ingredients") or []) or "the listed ingredient"
            question = (
                f"Using only the Drugs@FDA records supplied in the context, what DOSAGE FORM is listed for "
                f"product number {prodno} under FDA application {appno} (brand name "
                f"\"{rec.metadata.get('brand_name')}\", active ingredient {ing})? Answer with the dosage "
                f"form exactly as recorded."
            )
            out.append(self.make_answerable(
                ctx,
                family_id=ctx.next_family_id(self.id_prefix),
                question=question,
                evidence=[(rec, "target_value")],
                gold_answer=str(rec.value),
                gold_answer_normalized=str(rec.value).upper(),
                answer_type=AnswerType.CATEGORICAL,
                answer_unit=None,
                numeric_tolerance=None,
                target_conditions={"match_mode": "all", "records": [record_conditions(rec)]},
                source_name=SOURCE, api_version=API_VERSION, license_note=LICENSE,
            ))
        return out


@register_template
class FDAProductCount(QuestionTemplate):
    """Count the distinct products under one application -- an aggregation over records."""

    template_id = "FDA_PRODUCT_COUNT"
    domain = Domain.FDA
    question_type = QuestionType.RETRIEVAL_CALCULATION
    id_prefix = "FDA"

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        by_app: Dict[str, List[NormalizedRecord]] = defaultdict(list)
        for r in _by_concept(ctx.records, "product.dosage_form"):
            by_app[str(r.metadata.get("application_number"))].append(r)
        rng = ctx.rng(self.template_id)
        keys = sorted(k for k, v in by_app.items() if 2 <= len(v) <= 12)
        rng.shuffle(keys)

        out: List[QuestionFamily] = []
        for appno in keys:
            if len(out) >= n:
                break
            prods = sorted(by_app[appno], key=lambda r: str(r.metadata.get("product_number")))
            operands = {f"product_{i}": r for i, r in enumerate(prods)}
            try:
                spec = build_calculation(
                    CalculationOp.COUNT, operands, decimals=0, result_unit="products",
                    values_override={k: 1.0 for k in operands},
                )
            except CalculationError:
                continue
            sponsor = prods[0].metadata.get("sponsor_name")
            question = (
                f"Using only the Drugs@FDA records supplied in the context, how many distinct product "
                f"entries are listed under FDA application {appno} (sponsor: {sponsor})? Count the "
                f"products belonging to that application number only, and answer with an integer."
            )
            out.append(self.make_answerable(
                ctx,
                family_id=ctx.next_family_id(self.id_prefix),
                question=question,
                evidence=[(r, f"product_{i}") for i, r in enumerate(prods)],
                gold_answer=format_number(spec.rounded_result),
                gold_answer_normalized=spec.rounded_result,
                answer_type=AnswerType.INTEGER,
                answer_unit="products",
                numeric_tolerance=0.0,
                target_conditions={"match_mode": "all", "records": [record_conditions(r) for r in prods]},
                source_name=SOURCE, calculation_spec=spec,
                api_version=API_VERSION, license_note=LICENSE,
                note="aggregation over every product record of one application",
            ))
        return out


@register_template
class FDAStrengthRatio(QuestionTemplate):
    """Ratio between two authentic strengths of the same ingredient in the same unit."""

    template_id = "FDA_STRENGTH_RATIO"
    domain = Domain.FDA
    question_type = QuestionType.RETRIEVAL_CALCULATION
    id_prefix = "FDA"

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        pool = [
            r for r in _by_concept(ctx.records, "product.active_ingredient_strength")
            if r.value_numeric and r.unit
        ]
        by_ing: Dict[Tuple[str, str], List[NormalizedRecord]] = defaultdict(list)
        for r in pool:
            by_ing[(str(r.metadata.get("ingredient_name")).upper(), r.unit)].append(r)
        rng = ctx.rng(self.template_id)
        keys = sorted(k for k, v in by_ing.items() if len({x.value_numeric for x in v}) >= 2)
        rng.shuffle(keys)

        out: List[QuestionFamily] = []
        used: set = set()
        for ing, unit in keys:
            if len(out) >= n:
                break
            group = sorted(by_ing[(ing, unit)], key=lambda r: (-float(r.value_numeric), r.record_id))
            hi = group[0]
            lo = next((r for r in reversed(group) if r.value_numeric != hi.value_numeric), None)
            if lo is None or hi.entity_id in used or lo.entity_id in used:
                continue
            try:
                spec = build_calculation(
                    CalculationOp.RATIO, {"numerator": hi, "denominator": lo},
                    decimals=4, result_unit="ratio (dimensionless)",
                )
            except CalculationError:
                continue
            used.update({hi.entity_id, lo.entity_id})
            question = (
                f"Using only the Drugs@FDA records supplied in the context, divide the {ing} strength of "
                f"product {hi.metadata.get('product_number')} under application "
                f"{hi.metadata.get('application_number')} by the {ing} strength of product "
                f"{lo.metadata.get('product_number')} under application "
                f"{lo.metadata.get('application_number')}. Both strengths are expressed in {unit}; report "
                f"the dimensionless ratio rounded to four decimal places."
            )
            out.append(self.make_answerable(
                ctx,
                family_id=ctx.next_family_id(self.id_prefix),
                question=question,
                evidence=[(hi, "numerator"), (lo, "denominator")],
                gold_answer=f"{spec.rounded_result:.4f}",
                gold_answer_normalized=spec.rounded_result,
                answer_type=AnswerType.NUMERIC,
                answer_unit="ratio",
                numeric_tolerance=numeric_tolerance_for(spec.rounded_result, 4),
                target_conditions={"match_mode": "all",
                                   "records": [record_conditions(hi, STRENGTH_KEYS),
                                               record_conditions(lo, STRENGTH_KEYS)]},
                source_name=SOURCE, calculation_spec=spec,
                api_version=API_VERSION, license_note=LICENSE,
                note="operand magnitudes are parsed from the FDA strength strings; unit equality enforced",
            ))
        return out


@register_template
class FDAOriginalVsSupplement(QuestionTemplate):
    """The original submission's date, among many later supplements for the same application."""

    template_id = "FDA_ORIGINAL_VS_SUPPLEMENT"
    domain = Domain.FDA
    question_type = QuestionType.TEMPORAL_VERSION
    id_prefix = "FDA"

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        by_app: Dict[str, List[NormalizedRecord]] = defaultdict(list)
        for r in _by_concept(ctx.records, "submission.status_date"):
            by_app[str(r.metadata.get("application_number"))].append(r)
        rng = ctx.rng(self.template_id)
        keys = sorted(by_app)
        rng.shuffle(keys)

        out: List[QuestionFamily] = []
        for appno in keys:
            if len(out) >= n:
                break
            subs = by_app[appno]
            orig = next((s for s in subs if s.metadata.get("is_original")), None)
            supps = [s for s in subs if not s.metadata.get("is_original")]
            if orig is None or len(supps) < 2:
                continue
            question = (
                f"Using only the Drugs@FDA records supplied in the context, what is the submission status "
                f"date of the ORIGINAL submission (submission type ORIG) for FDA application {appno} "
                f"(sponsor: {orig.metadata.get('sponsor_name')})? Answer in YYYY-MM-DD form."
            )
            out.append(self.make_answerable(
                ctx,
                family_id=ctx.next_family_id(self.id_prefix),
                question=question,
                evidence=[(orig, "target_value")],
                gold_answer=str(orig.value),
                gold_answer_normalized=str(orig.value),
                answer_type=AnswerType.DATE,
                answer_unit=None,
                numeric_tolerance=None,
                target_conditions={"match_mode": "all", "records": [record_conditions(orig)],
                                   "explicit_foils": [record_conditions(s) for s in supps]},
                source_name=SOURCE, api_version=API_VERSION, license_note=LICENSE,
                note="original vs supplement version selection within one application",
            ))
        return out


@register_template
class FDAStrengthBinding(QuestionTemplate):
    """Bind to one product's strength when its siblings differ only by strength."""

    template_id = "FDA_STRENGTH_PRODUCT_BINDING"
    domain = Domain.FDA
    question_type = QuestionType.ENTITY_UNIT_BINDING
    id_prefix = "FDA"

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        by_app: Dict[str, List[NormalizedRecord]] = defaultdict(list)
        for r in _by_concept(ctx.records, "product.active_ingredient_strength"):
            by_app[str(r.metadata.get("application_number"))].append(r)
        idx = _entity_index(ctx.records)
        rng = ctx.rng(self.template_id)
        keys = sorted(k for k, v in by_app.items() if len({str(x.value) for x in v}) >= 3)
        rng.shuffle(keys)

        out: List[QuestionFamily] = []
        for appno in keys:
            if len(out) >= n:
                break
            group = sorted(by_app[appno], key=lambda r: str(r.metadata.get("product_number")))
            target = group[rng.randrange(len(group))]
            others = [g for g in group if g.entity_id != target.entity_id]
            if not others:
                continue
            form = idx.get((target.entity_id, "product.dosage_form"))
            route = idx.get((target.entity_id, "product.route"))
            qualifiers = []
            if form:
                qualifiers.append(f"dosage form {form.value}")
            if route:
                qualifiers.append(f"route {route.value}")
            qual = f" ({', '.join(qualifiers)})" if qualifiers else ""
            question = (
                f"Using only the Drugs@FDA records supplied in the context, what is the listed strength of "
                f"{target.metadata.get('ingredient_name')} in product number "
                f"{target.metadata.get('product_number')} under FDA application {appno}{qual}? Report the "
                f"strength string exactly as recorded."
            )
            out.append(self.make_answerable(
                ctx,
                family_id=ctx.next_family_id(self.id_prefix),
                question=question,
                evidence=[(target, "target_value")],
                gold_answer=str(target.value),
                gold_answer_normalized=str(target.value).upper().replace(" ", ""),
                answer_type=AnswerType.STRING,
                answer_unit=target.unit,
                numeric_tolerance=None,
                target_conditions={
                    "match_mode": "all",
                    "records": [record_conditions(target, STRENGTH_KEYS)],
                    "explicit_foils": [record_conditions(o, STRENGTH_KEYS) for o in others],
                },
                source_name=SOURCE, api_version=API_VERSION, license_note=LICENSE,
                note="product-level strength binding among same-application siblings",
            ))
        return out


@register_template
class FDAUnanswerableMissingAttribute(QuestionTemplate):
    """Ask for a product attribute Drugs@FDA does not list for that product.

    openFDA genuinely omits ``route`` (and sometimes ``marketing_status``) for some
    products. Absence is verified against the pool before the family is emitted.
    """

    template_id = "FDA_UNANSWERABLE_ATTRIBUTE_ABSENT"
    domain = Domain.FDA
    question_type = QuestionType.UNANSWERABLE
    id_prefix = "FDA"

    CANDIDATES = [
        ("product.route", "the route of administration", "ATTRIBUTE_NOT_LISTED_FOR_PRODUCT"),
        ("product.marketing_status", "the marketing status", "ATTRIBUTE_NOT_LISTED_FOR_PRODUCT"),
    ]

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        present: Dict[Tuple[str, str], bool] = {}
        entities: Dict[str, NormalizedRecord] = {}
        for r in ctx.records:
            present[(r.entity_id, r.concept)] = True
            if r.concept == "product.dosage_form":
                entities[r.entity_id] = r
        rng = ctx.rng(self.template_id)
        keys = sorted(entities)
        rng.shuffle(keys)

        out: List[QuestionFamily] = []
        for entity_id in keys:
            if len(out) >= n:
                break
            anchor = entities[entity_id]
            for concept, phrase, code in self.CANDIDATES:
                if present.get((entity_id, concept)):
                    continue
                if ctx.pool.matches_target(entity_id=entity_id, concept=concept):
                    continue
                appno = anchor.metadata.get("application_number")
                prodno = anchor.metadata.get("product_number")
                question = (
                    f"Using only the Drugs@FDA records supplied in the context, what is {phrase} for "
                    f"product number {prodno} under FDA application {appno} (brand name "
                    f"\"{anchor.metadata.get('brand_name')}\")?"
                )
                spec = UnanswerableSpec(
                    reason_code=code,
                    reason=(
                        f"The Drugs@FDA record for product {entity_id} omits {concept}; openFDA returns no "
                        f"such field for this product. Verified by exhaustive scan of the normalized pool: "
                        f"zero records match entity_id={entity_id} and concept={concept}. Other products in "
                        f"the pool do carry this attribute, so the omission is a property of this product."
                    ),
                    missing_concept=concept,
                    missing_entity_id=entity_id,
                    verified_absent_in_pool=True,
                    forbidden_concept_aliases=[concept],
                )
                out.append(self.make_unanswerable(
                    ctx,
                    family_id=ctx.next_family_id(self.id_prefix),
                    question=question,
                    spec=spec,
                    target_conditions={"match_mode": "all", "records": [{
                        "entity_id": entity_id, "entity_name": anchor.entity_name, "concept": concept,
                        "period": None, "unit": None, "version": None,
                    }]},
                    source_name=SOURCE, context_records=[anchor],
                    api_version=API_VERSION, license_note=LICENSE,
                ))
                break
        return out
