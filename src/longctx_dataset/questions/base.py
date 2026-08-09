"""Question-template framework and deterministic gold-answer derivation.

The central rule of this project lives here: **a gold answer is computed from structured
source records, never authored.** A template may only choose *which* records a question
is about and how to phrase it. The answer itself comes out of :mod:`calculations`, and
:mod:`longctx_dataset.validation.gold` later recomputes it from the stored operands.

Templates are registered per (domain, question_type) so the configured question-type mix
can be satisfied by allocation rather than by hand-picking.
"""

from __future__ import annotations

import hashlib
import math
import random
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from ..config import PipelineConfig
from ..normalize.common import RecordPool
from ..schemas import (
    AnswerType,
    CalculationOp,
    CalculationSpec,
    Domain,
    GenerationMetadata,
    GoldEvidence,
    NormalizedRecord,
    QuestionFamily,
    QuestionType,
    SourceProvenance,
    UnanswerableSpec,
    INSUFFICIENT_EVIDENCE,
)
from ..storage.manifests import utc_now


# --------------------------------------------------------------------------------------
# Deterministic seeding
# --------------------------------------------------------------------------------------


def derive_seed(base_seed: int, *parts: Any) -> int:
    """Stable sub-seed for a (domain, template, ...) coordinate.

    Deriving rather than sharing one global RNG means adding or reordering a template
    does not silently change every other template's output -- an essential property for
    a dataset that must be regenerable.
    """
    key = f"{base_seed}|" + "|".join(str(p) for p in parts)
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:16], 16)


def rng_for(base_seed: int, *parts: Any) -> random.Random:
    return random.Random(derive_seed(base_seed, *parts))


# --------------------------------------------------------------------------------------
# Answer formatting / conditions
# --------------------------------------------------------------------------------------


def record_conditions(
    rec: NormalizedRecord, metadata_keys: Sequence[str] = ()
) -> Dict[str, Any]:
    """The structured identity of the fact a question is asking for.

    ``metadata_keys`` adds source-specific discriminators for records whose
    entity/concept/period tuple is *not* unique -- several arms of one trial, or several
    ingredients of one product. Without them the distractor selector would treat a
    sibling arm as a duplicate of the target and refuse to place it in the context, which
    would remove exactly the interference the question is designed to test.
    """
    cond: Dict[str, Any] = {
        "entity_id": rec.entity_id,
        "entity_name": rec.entity_name,
        "concept": rec.concept,
        "period": rec.period,
        "unit": rec.unit,
        "version": rec.version,
    }
    if metadata_keys:
        cond["metadata_match"] = {k: rec.metadata.get(k) for k in metadata_keys}
    return cond


def format_number(value: float, decimals: Optional[int] = None) -> str:
    """Render a numeric answer without scientific notation or lost precision."""
    if decimals is not None:
        return f"{value:,.{decimals}f}"
    if float(value).is_integer() and abs(value) < 1e18:
        return f"{int(value):,}"
    return f"{value:,.6f}".rstrip("0").rstrip(".")


def numeric_tolerance_for(value: float, decimals: Optional[int]) -> float:
    """Grading tolerance implied by how the answer is presented.

    A value rounded to N decimals can only be graded to half of the last place; an
    unrounded lookup gets a tiny relative tolerance to absorb float representation.
    """
    if decimals is not None:
        return 0.5 * (10.0**-decimals)
    return max(abs(value) * 1e-9, 1e-9)


# --------------------------------------------------------------------------------------
# Calculations -- the only sanctioned way to produce a derived gold answer
# --------------------------------------------------------------------------------------


class CalculationError(ValueError):
    """A calculation could not be performed on the chosen operands (e.g. zero divisor)."""


def _finite(x: Optional[float], role: str) -> float:
    if x is None or not math.isfinite(x):
        raise CalculationError(f"operand {role!r} is not a finite number: {x!r}")
    return float(x)


def build_calculation(
    operation: CalculationOp,
    operands: Dict[str, NormalizedRecord],
    *,
    decimals: int = 2,
    result_unit: Optional[str] = None,
    values_override: Optional[Dict[str, float]] = None,
) -> CalculationSpec:
    """Compute a derived answer and record everything needed to recompute it.

    ``operand_values`` is stored explicitly alongside the record IDs so the validator can
    verify both that the arithmetic is right *and* that the operands still match the
    source records they came from.
    """
    values: Dict[str, float] = {}
    for role, rec in operands.items():
        if values_override and role in values_override:
            values[role] = _finite(values_override[role], role)
        else:
            values[role] = _finite(rec.value_numeric, role)

    if operation is CalculationOp.RATIO_PERCENT:
        num, den = values["numerator"], values["denominator"]
        if den == 0:
            raise CalculationError("ratio_percent: denominator is zero")
        raw = (num / den) * 100.0
        formula = "(numerator / denominator) * 100"
    elif operation is CalculationOp.GROWTH_PERCENT:
        cur, prev = values["current"], values["previous"]
        if prev == 0:
            raise CalculationError("growth_percent: previous value is zero")
        raw = ((cur - prev) / prev) * 100.0
        formula = "((current - previous) / previous) * 100"
    elif operation is CalculationOp.DIFFERENCE:
        raw = values["minuend"] - values["subtrahend"]
        formula = "minuend - subtrahend"
    elif operation is CalculationOp.RATIO:
        num, den = values["numerator"], values["denominator"]
        if den == 0:
            raise CalculationError("ratio: denominator is zero")
        raw = num / den
        formula = "numerator / denominator"
    elif operation is CalculationOp.SUM:
        raw = sum(values.values())
        formula = " + ".join(sorted(values))
    elif operation is CalculationOp.COUNT:
        raw = float(len(values))
        formula = "count(operands)"
    elif operation is CalculationOp.DAYS_BETWEEN:
        raw = values["end"] - values["start"]
        formula = "end_epoch_days - start_epoch_days"
    else:  # pragma: no cover - exhaustive over the enum
        raise CalculationError(f"unsupported operation {operation}")

    if not math.isfinite(raw):
        raise CalculationError(f"{operation.value} produced a non-finite result: {raw}")

    return CalculationSpec(
        operation=operation,
        formula=formula,
        operands={role: rec.record_id for role, rec in operands.items()},
        operand_values=values,
        raw_result=raw,
        rounded_result=round(raw, decimals),
        round_decimals=decimals,
        result_unit=result_unit,
        numerator_record_id=operands["numerator"].record_id if "numerator" in operands else None,
        denominator_record_id=operands["denominator"].record_id if "denominator" in operands else None,
    )


# --------------------------------------------------------------------------------------
# Template contract
# --------------------------------------------------------------------------------------


class TemplateContext:
    """Everything a template needs, bundled so templates stay pure and testable."""

    def __init__(self, cfg: PipelineConfig, pool: RecordPool, domain: Domain, git_sha: Optional[str] = None):
        self.cfg = cfg
        self.pool = pool
        self.domain = domain
        self.git_sha = git_sha
        self.records = pool.domain_records(domain)
        self._counter: Dict[str, int] = defaultdict(int)

    def next_family_id(self, prefix: str) -> str:
        self._counter[prefix] += 1
        return f"{prefix}_{self._counter[prefix]:04d}"

    def rng(self, *parts: Any) -> random.Random:
        return rng_for(self.cfg.seed, self.domain.value, *parts)


class QuestionTemplate(ABC):
    """One way of turning source records into a question family.

    ``generate`` returns *at most* ``n`` families; returning fewer is normal and honest
    (the pool may not contain enough qualifying records) and is reported rather than
    papered over.
    """

    template_id: str
    template_version: str = "1.0.0"
    domain: Domain
    question_type: QuestionType
    id_prefix: str

    @abstractmethod
    def generate(self, ctx: TemplateContext, n: int) -> List[QuestionFamily]:
        ...

    # ---- shared construction helpers -------------------------------------------------

    def _metadata(self, ctx: TemplateContext, note: Optional[str] = None) -> GenerationMetadata:
        return GenerationMetadata(
            template_id=self.template_id,
            template_version=self.template_version,
            seed=ctx.cfg.seed,
            config_hash=ctx.cfg.config_hash,
            git_commit=ctx.git_sha,
            generated_at=utc_now(),
            tokenizer_id=ctx.cfg.tokenizer.id,
            notes=note,
        )

    @staticmethod
    def _provenance(records: Sequence[NormalizedRecord], source_name: str,
                    api_version: Optional[str] = None, license_note: Optional[str] = None
                    ) -> List[SourceProvenance]:
        by_url: Dict[Optional[str], List[str]] = defaultdict(list)
        retrieved: Dict[Optional[str], Optional[str]] = {}
        for r in records:
            by_url[r.raw_reference.source_url].append(r.record_id)
            retrieved[r.raw_reference.source_url] = r.raw_reference.retrieved_at
        return [
            SourceProvenance(
                source=source_name, endpoint=url, request_url=url,
                retrieved_at=retrieved.get(url), record_ids=sorted(ids),
                api_version=api_version, license_note=license_note,
            )
            for url, ids in sorted(by_url.items(), key=lambda kv: (kv[0] or ""))
        ]

    def make_answerable(
        self,
        ctx: TemplateContext,
        *,
        family_id: str,
        question: str,
        evidence: Sequence[Tuple[NormalizedRecord, str]],
        gold_answer: Any,
        gold_answer_normalized: Any,
        answer_type: AnswerType,
        answer_unit: Optional[str],
        numeric_tolerance: Optional[float],
        target_conditions: Dict[str, Any],
        source_name: str,
        calculation_spec: Optional[CalculationSpec] = None,
        api_version: Optional[str] = None,
        license_note: Optional[str] = None,
        note: Optional[str] = None,
    ) -> QuestionFamily:
        recs = [r for r, _ in evidence]
        gold = [GoldEvidence.from_record(r, role) for r, role in evidence]
        return QuestionFamily(
            question_family_id=family_id,
            domain=self.domain,
            source_name=source_name,
            question_type=self.question_type,
            question=question,
            answerable=True,
            gold_answer=gold_answer,
            gold_answer_normalized=gold_answer_normalized,
            answer_type=answer_type,
            answer_unit=answer_unit,
            numeric_tolerance=numeric_tolerance,
            gold_evidence=gold,
            gold_evidence_ids=[g.record_id for g in gold],
            calculation_spec=calculation_spec,
            target_conditions=target_conditions,
            source_provenance=self._provenance(recs, source_name, api_version, license_note),
            generation_metadata=self._metadata(ctx, note),
        )

    def make_unanswerable(
        self,
        ctx: TemplateContext,
        *,
        family_id: str,
        question: str,
        spec: UnanswerableSpec,
        target_conditions: Dict[str, Any],
        source_name: str,
        context_records: Sequence[NormalizedRecord] = (),
        api_version: Optional[str] = None,
        license_note: Optional[str] = None,
        note: Optional[str] = None,
    ) -> QuestionFamily:
        return QuestionFamily(
            question_family_id=family_id,
            domain=self.domain,
            source_name=source_name,
            question_type=QuestionType.UNANSWERABLE,
            question=question,
            answerable=False,
            gold_answer=None,
            gold_answer_normalized=INSUFFICIENT_EVIDENCE,
            answer_type=AnswerType.INSUFFICIENT_EVIDENCE,
            answer_unit=None,
            numeric_tolerance=None,
            gold_evidence=[],
            gold_evidence_ids=[],
            calculation_spec=None,
            unanswerable_spec=spec,
            target_conditions=target_conditions,
            source_provenance=self._provenance(list(context_records), source_name, api_version, license_note),
            generation_metadata=self._metadata(ctx, note),
        )


# --------------------------------------------------------------------------------------
# Registry + allocation
# --------------------------------------------------------------------------------------

_TEMPLATES: Dict[Domain, List[QuestionTemplate]] = defaultdict(list)


def register_template(cls):
    """Class decorator registering a template instance under its domain."""
    _TEMPLATES[cls.domain].append(cls())
    return cls


def templates_for(domain: Domain, question_type: Optional[QuestionType] = None) -> List[QuestionTemplate]:
    items = _TEMPLATES.get(domain, [])
    if question_type is None:
        return list(items)
    return [t for t in items if t.question_type is question_type]


def allocate_counts(mix: Dict[QuestionType, float], total: int) -> Dict[QuestionType, int]:
    """Largest-remainder allocation of ``total`` families across the question-type mix.

    Any type with a nonzero weight is guaranteed at least one family when the budget
    allows, because the pilot must demonstrate every category.
    """
    if total <= 0 or not mix:
        return {}
    weights = {k: v for k, v in mix.items() if v > 0}
    if not weights:
        return {}
    scale = sum(weights.values())
    exact = {k: total * v / scale for k, v in weights.items()}
    counts = {k: int(math.floor(v)) for k, v in exact.items()}

    if total >= len(weights):
        for k in weights:
            if counts[k] == 0:
                counts[k] = 1

    def _order(k: QuestionType) -> Tuple[float, str]:
        return (-(exact[k] - math.floor(exact[k])), k.value)

    ordered = sorted(weights, key=_order)
    i = 0
    while sum(counts.values()) < total:
        counts[ordered[i % len(ordered)]] += 1
        i += 1
    while sum(counts.values()) > total:
        # Trim from the largest allocation that can spare a family.
        k = max(counts, key=lambda x: (counts[x], x.value))
        if counts[k] <= 1 and sum(1 for v in counts.values() if v > 0) <= len(weights):
            counts[k] -= 1
            if counts[k] < 0:
                counts[k] = 0
        else:
            counts[k] -= 1
    return counts
