"""ClinicalTrials.gov question templates.

The distinguishing difficulty in this domain is *field* interference: a single trial
carries six different date fields, several arms, and multiple outcome measures, each of
which is a plausible-looking answer to a carelessly-read question.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
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

SOURCE = "CLINICALTRIALS_GOV_V2"
API_VERSION = "v2"
LICENSE = "ClinicalTrials.gov (NLM), public domain"

# Sibling arms of one trial share entity/concept/period/unit/version, so the arm label
# is the only thing that distinguishes the target from its foils.
ARM_KEYS = ("arm_label", "arm_index")

DATE_CONCEPTS = {
    "study.start_date": "study start date",
    "study.primary_completion_date": "primary completion date",
    "study.completion_date": "study completion date",
    "study.first_posted_date": "date the study record was first posted",
    "study.last_update_posted_date": "date the study record was last updated",
    "study.results_first_posted_date": "date results were first posted",
}


def _by_entity_concept(records: List[NormalizedRecord]) -> Dict[Tuple[str, str], List[NormalizedRecord]]:
    idx: Dict[Tuple[str, str], List[NormalizedRecord]] = defaultdict(list)
    for r in records:
        idx[(r.entity_id, r.concept)].append(r)
    return idx


def _epoch_days(iso: str) -> Optional[float]:
    """Days since 1970-01-01, for date arithmetic that stays exact and auditable."""
    try:
        parts = [int(p) for p in str(iso).split("-")]
    except ValueError:
        return None
    if len(parts) == 2:
        parts.append(1)
    if len(parts) != 3:
        return None
    try:
        return float((date(*parts) - date(1970, 1, 1)).days)
    except ValueError:
        return None


@register_template
class CTDirectEnrollment(QuestionTemplate):
    template_id = "CT_DIRECT_ENROLLMENT"
    domain = Domain.CLINICAL_TRIALS
    question_type = QuestionType.DIRECT_RETRIEVAL
    id_prefix = "CT"

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        pool = sorted(
            [r for r in ctx.records if r.concept == "enrollment.count" and r.value_numeric is not None],
            key=lambda r: r.record_id,
        )
        rng = ctx.rng(self.template_id)
        rng.shuffle(pool)

        out: List[QuestionFamily] = []
        for rec in pool:
            if len(out) >= n:
                break
            value = float(rec.value_numeric)
            etype = rec.metadata.get("enrollment_type") or "reported"
            question = (
                f"Using only the ClinicalTrials.gov records supplied in the context, what enrollment "
                f"count is reported for trial {rec.entity_id} (\"{rec.entity_name}\")? Report the "
                f"{str(etype).lower()} number of participants as an integer."
            )
            out.append(self.make_answerable(
                ctx,
                family_id=ctx.next_family_id(self.id_prefix),
                question=question,
                evidence=[(rec, "target_value")],
                gold_answer=format_number(value),
                gold_answer_normalized=value,
                answer_type=AnswerType.INTEGER,
                answer_unit="participants",
                numeric_tolerance=0.0,
                target_conditions={"match_mode": "all", "records": [record_conditions(rec)]},
                source_name=SOURCE, api_version=API_VERSION, license_note=LICENSE,
            ))
        return out


@register_template
class CTEnrollmentDifference(QuestionTemplate):
    """Difference in enrollment between two named trials studying the same condition."""

    template_id = "CT_ENROLLMENT_DIFFERENCE"
    domain = Domain.CLINICAL_TRIALS
    question_type = QuestionType.RETRIEVAL_CALCULATION
    id_prefix = "CT"

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        pool = [r for r in ctx.records if r.concept == "enrollment.count" and r.value_numeric is not None]
        by_condition: Dict[str, List[NormalizedRecord]] = defaultdict(list)
        for r in pool:
            for cond in (r.metadata.get("conditions") or ["(unspecified)"])[:1]:
                by_condition[str(cond).upper()].append(r)
        rng = ctx.rng(self.template_id)
        keys = sorted(k for k, v in by_condition.items() if len(v) >= 2)
        rng.shuffle(keys)

        out: List[QuestionFamily] = []
        used: set = set()
        for cond in keys:
            if len(out) >= n:
                break
            group = sorted(by_condition[cond], key=lambda r: r.record_id)
            pick = [r for r in group if r.entity_id not in used][:2]
            if len(pick) < 2 or pick[0].value_numeric == pick[1].value_numeric:
                continue
            a, b = sorted(pick, key=lambda r: -float(r.value_numeric))
            try:
                spec = build_calculation(
                    CalculationOp.DIFFERENCE, {"minuend": a, "subtrahend": b},
                    decimals=0, result_unit="participants",
                )
            except CalculationError:
                continue
            used.update({a.entity_id, b.entity_id})
            question = (
                f"Using only the ClinicalTrials.gov records supplied in the context, subtract the enrollment "
                f"count of trial {b.entity_id} from the enrollment count of trial {a.entity_id}. Report the "
                f"difference as an integer number of participants."
            )
            out.append(self.make_answerable(
                ctx,
                family_id=ctx.next_family_id(self.id_prefix),
                question=question,
                evidence=[(a, "minuend"), (b, "subtrahend")],
                gold_answer=format_number(spec.rounded_result),
                gold_answer_normalized=spec.rounded_result,
                answer_type=AnswerType.INTEGER,
                answer_unit="participants",
                numeric_tolerance=0.0,
                target_conditions={"match_mode": "all",
                                   "records": [record_conditions(a), record_conditions(b)]},
                source_name=SOURCE, calculation_spec=spec,
                api_version=API_VERSION, license_note=LICENSE,
            ))
        return out


@register_template
class CTStudyDuration(QuestionTemplate):
    """Days between start and primary completion -- date arithmetic over two fields."""

    template_id = "CT_STUDY_DURATION_DAYS"
    domain = Domain.CLINICAL_TRIALS
    question_type = QuestionType.RETRIEVAL_CALCULATION
    id_prefix = "CT"

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        idx = _by_entity_concept(ctx.records)
        entities = sorted({r.entity_id for r in ctx.records})
        rng = ctx.rng(self.template_id)
        rng.shuffle(entities)

        out: List[QuestionFamily] = []
        for nct in entities:
            if len(out) >= n:
                break
            starts = idx.get((nct, "study.start_date")) or []
            ends = idx.get((nct, "study.primary_completion_date")) or []
            if not starts or not ends:
                continue
            s, e = starts[0], ends[0]
            sd, ed = _epoch_days(str(s.value)), _epoch_days(str(e.value))
            if sd is None or ed is None or ed <= sd:
                continue
            # Only use full YYYY-MM-DD dates; a month-precision date would make the
            # day count an artefact of our own imputation rather than the source.
            if len(str(s.value)) != 10 or len(str(e.value)) != 10:
                continue
            try:
                spec = build_calculation(
                    CalculationOp.DAYS_BETWEEN, {"start": s, "end": e},
                    decimals=0, result_unit="days",
                    values_override={"start": sd, "end": ed},
                )
            except CalculationError:
                continue
            question = (
                f"Using only the ClinicalTrials.gov records supplied in the context, calculate the number "
                f"of calendar days between the study start date and the primary completion date of trial "
                f"{nct} (\"{s.entity_name}\"). Report a whole number of days. Use the primary completion "
                f"date, not the overall study completion date and not the last update posted date."
            )
            out.append(self.make_answerable(
                ctx,
                family_id=ctx.next_family_id(self.id_prefix),
                question=question,
                evidence=[(s, "start"), (e, "end")],
                gold_answer=format_number(spec.rounded_result),
                gold_answer_normalized=spec.rounded_result,
                answer_type=AnswerType.INTEGER,
                answer_unit="days",
                numeric_tolerance=0.0,
                target_conditions={"match_mode": "all",
                                   "records": [record_conditions(s), record_conditions(e)]},
                source_name=SOURCE, calculation_spec=spec,
                api_version=API_VERSION, license_note=LICENSE,
                note="operand values are epoch-day projections of the two ISO dates",
            ))
        return out


@register_template
class CTDateFieldSelection(QuestionTemplate):
    """Six sibling date fields on one trial; the question names exactly one."""

    template_id = "CT_DATE_FIELD_SELECTION"
    domain = Domain.CLINICAL_TRIALS
    question_type = QuestionType.ENTITY_UNIT_BINDING
    id_prefix = "CT"

    TARGET = "study.primary_completion_date"

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        idx = _by_entity_concept(ctx.records)
        entities = sorted({r.entity_id for r in ctx.records})
        rng = ctx.rng(self.template_id)
        rng.shuffle(entities)

        out: List[QuestionFamily] = []
        for nct in entities:
            if len(out) >= n:
                break
            target_recs = idx.get((nct, self.TARGET)) or []
            if not target_recs:
                continue
            target = target_recs[0]
            siblings = [
                (c, (idx.get((nct, c)) or [None])[0])
                for c in DATE_CONCEPTS if c != self.TARGET
            ]
            siblings = [(c, r) for c, r in siblings if r is not None and str(r.value) != str(target.value)]
            if len(siblings) < 3:
                continue  # without competing dates the question is not a selection task
            question = (
                f"Using only the ClinicalTrials.gov records supplied in the context, what is the PRIMARY "
                f"COMPLETION DATE of trial {nct} (\"{target.entity_name}\")? Answer in YYYY-MM-DD form."
            )
            out.append(self.make_answerable(
                ctx,
                family_id=ctx.next_family_id(self.id_prefix),
                question=question,
                evidence=[(target, "target_value")],
                gold_answer=str(target.value),
                gold_answer_normalized=str(target.value),
                answer_type=AnswerType.DATE,
                answer_unit=None,
                numeric_tolerance=None,
                target_conditions={"match_mode": "all", "records": [record_conditions(target)],
                                   "explicit_foils": [record_conditions(r) for _, r in siblings]},
                source_name=SOURCE, api_version=API_VERSION, license_note=LICENSE,
                note="selection among six sibling date fields of the same trial",
            ))
        return out


@register_template
class CTArmBinding(QuestionTemplate):
    """Bind to one arm of a multi-arm trial by its exact label."""

    template_id = "CT_ARM_TYPE_BINDING"
    domain = Domain.CLINICAL_TRIALS
    question_type = QuestionType.ENTITY_UNIT_BINDING
    id_prefix = "CT"

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        arms: Dict[str, List[NormalizedRecord]] = defaultdict(list)
        for r in ctx.records:
            if r.concept == "arm.type" and r.metadata.get("arm_label"):
                arms[r.entity_id].append(r)
        rng = ctx.rng(self.template_id)
        keys = sorted(k for k, v in arms.items() if len(v) >= 2)
        rng.shuffle(keys)

        out: List[QuestionFamily] = []
        for nct in keys:
            if len(out) >= n:
                break
            group = sorted(arms[nct], key=lambda r: r.metadata.get("arm_index", 0))
            target = group[rng.randrange(len(group))]
            others = [g for g in group if g.record_id != target.record_id]
            if not others:
                continue
            question = (
                f"Using only the ClinicalTrials.gov records supplied in the context, what is the arm-group "
                f"TYPE of the arm labelled \"{target.metadata.get('arm_label')}\" in trial {nct} "
                f"(\"{target.entity_name}\")? Answer with the ClinicalTrials.gov arm type value (for "
                f"example EXPERIMENTAL, ACTIVE_COMPARATOR, PLACEBO_COMPARATOR, SHAM_COMPARATOR, NO_INTERVENTION "
                f"or OTHER)."
            )
            out.append(self.make_answerable(
                ctx,
                family_id=ctx.next_family_id(self.id_prefix),
                question=question,
                evidence=[(target, "target_value")],
                gold_answer=str(target.value),
                gold_answer_normalized=str(target.value).upper(),
                answer_type=AnswerType.CATEGORICAL,
                answer_unit=None,
                numeric_tolerance=None,
                target_conditions={
                    "match_mode": "all",
                    "records": [record_conditions(target, ARM_KEYS)],
                    "explicit_foils": [record_conditions(o, ARM_KEYS) for o in others],
                },
                source_name=SOURCE, api_version=API_VERSION, license_note=LICENSE,
                note="arm-level attribute binding within a multi-arm trial",
            ))
        return out


@register_template
class CTUnanswerableMissingField(QuestionTemplate):
    """Ask for a field the trial's registry record does not contain.

    Candidate fields are ones ClinicalTrials.gov populates for *some* trials but not this
    one (results-posting date, maximum eligible age), so the question is natural rather
    than contrived. Absence is verified across the whole pool before emission.
    """

    template_id = "CT_UNANSWERABLE_FIELD_ABSENT"
    domain = Domain.CLINICAL_TRIALS
    question_type = QuestionType.UNANSWERABLE
    id_prefix = "CT"

    CANDIDATES = [
        ("study.results_first_posted_date", "the date on which results were first posted",
         "RESULTS_NOT_POSTED"),
        ("eligibility.maximum_age", "the maximum eligible age", "FIELD_NOT_PROVIDED_BY_SPONSOR"),
    ]

    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        idx = _by_entity_concept(ctx.records)
        entities = sorted({r.entity_id for r in ctx.records})
        names = {r.entity_id: r.entity_name for r in ctx.records}
        rng = ctx.rng(self.template_id)
        rng.shuffle(entities)

        out: List[QuestionFamily] = []
        for nct in entities:
            if len(out) >= n:
                break
            for concept, phrase, code in self.CANDIDATES:
                if idx.get((nct, concept)):
                    continue
                if ctx.pool.matches_target(entity_id=nct, concept=concept):
                    continue
                # Require the trial to be otherwise well-populated, so the context has
                # plenty of adjacent-but-wrong fields to tempt a fabricated answer.
                if len([r for r in ctx.records if r.entity_id == nct]) < 8:
                    continue
                question = (
                    f"Using only the ClinicalTrials.gov records supplied in the context, what is {phrase} "
                    f"for trial {nct} (\"{names.get(nct, nct)}\")?"
                )
                spec = UnanswerableSpec(
                    reason_code=code,
                    reason=(
                        f"The ClinicalTrials.gov v2 record for {nct} does not populate {concept}. Verified "
                        f"by exhaustive scan of the normalized pool: zero records match entity_id={nct} "
                        f"and concept={concept}. Other trials in the pool do populate this field, so its "
                        f"absence is a property of this trial rather than of the adapter."
                    ),
                    missing_concept=concept,
                    missing_entity_id=nct,
                    verified_absent_in_pool=True,
                    forbidden_concept_aliases=[concept],
                )
                out.append(self.make_unanswerable(
                    ctx,
                    family_id=ctx.next_family_id(self.id_prefix),
                    question=question,
                    spec=spec,
                    target_conditions={"match_mode": "all", "records": [{
                        "entity_id": nct, "entity_name": names.get(nct, nct), "concept": concept,
                        "period": None, "unit": None, "version": None,
                    }]},
                    source_name=SOURCE,
                    context_records=[r for r in ctx.records if r.entity_id == nct][:1],
                    api_version=API_VERSION, license_note=LICENSE,
                ))
                break
        return out
