"""Versioned schemas for the long-context hallucination dataset.

Three layers are modelled here, and they must never be collapsed into one another:

1. :class:`NormalizedRecord` -- one atomic, re-verifiable fact from a primary source.
2. :class:`QuestionFamily`   -- one question + one deterministically derived gold answer.
3. :class:`Instance`         -- one (question family, context length) pair.

A question family is the experimental unit. Every instance derived from it must carry
byte-identical question text, gold answer and gold evidence IDs; only surrounding
same-domain distractor context may change. The validators in
:mod:`longctx_dataset.validation` enforce that invariant and fail hard when it breaks.
"""

from __future__ import annotations

import enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from . import GENERATOR_VERSION, SCHEMA_VERSION

# --------------------------------------------------------------------------------------
# Enumerations
# --------------------------------------------------------------------------------------


class Domain(str, enum.Enum):
    """Domains with an implemented source adapter."""

    SEC = "SEC"
    FDA = "FDA"
    CLINICAL_TRIALS = "CLINICAL_TRIALS"
    WORLD_BANK = "WORLD_BANK"
    # Reserved for the fifth production slot (NASA / FRED / NIST / regulatory / ...).
    EXTENSION = "EXTENSION"


class QuestionType(str, enum.Enum):
    """The five question categories the study distinguishes."""

    DIRECT_RETRIEVAL = "DIRECT_RETRIEVAL"
    RETRIEVAL_CALCULATION = "RETRIEVAL_CALCULATION"
    TEMPORAL_VERSION = "TEMPORAL_VERSION"
    ENTITY_UNIT_BINDING = "ENTITY_UNIT_BINDING"
    UNANSWERABLE = "UNANSWERABLE"


class AnswerType(str, enum.Enum):
    NUMERIC = "NUMERIC"
    PERCENT = "PERCENT"
    INTEGER = "INTEGER"
    STRING = "STRING"
    DATE = "DATE"
    CATEGORICAL = "CATEGORICAL"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class DistractorType(str, enum.Enum):
    """Why a non-gold record was placed into the context.

    The taxonomy is deliberately about the *relationship to the target*, not about
    surface form, because that is what makes evidence selection hard.
    """

    WRONG_ENTITY = "WRONG_ENTITY"
    WRONG_PERIOD = "WRONG_PERIOD"
    WRONG_VERSION = "WRONG_VERSION"
    WRONG_FIELD = "WRONG_FIELD"
    WRONG_UNIT = "WRONG_UNIT"
    NEAR_MATCH_VALUE = "NEAR_MATCH_VALUE"
    OTHER_SAME_DOMAIN = "OTHER_SAME_DOMAIN"


class CalculationOp(str, enum.Enum):
    """Deterministic operations permitted for RETRIEVAL_CALCULATION gold answers."""

    RATIO_PERCENT = "ratio_percent"
    GROWTH_PERCENT = "growth_percent"
    DIFFERENCE = "difference"
    RATIO = "ratio"
    SUM = "sum"
    COUNT = "count"
    DAYS_BETWEEN = "days_between"


INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
"""Canonical normalized gold answer for every unanswerable family."""


# --------------------------------------------------------------------------------------
# Layer 2: normalized source records
# --------------------------------------------------------------------------------------


class RawReference(BaseModel):
    """Pointer back into the raw layer so any record can be re-verified."""

    model_config = ConfigDict(extra="forbid")

    source_url: Optional[str] = Field(
        None, description="API endpoint or document URL the record was derived from."
    )
    raw_file: Optional[str] = Field(
        None, description="Path (relative to the data root) of the cached raw payload."
    )
    raw_pointer: Optional[str] = Field(
        None, description="JSON-pointer-ish path locating the record inside the payload."
    )
    retrieved_at: Optional[str] = Field(
        None, description="UTC ISO-8601 timestamp of retrieval."
    )


class NormalizedRecord(BaseModel):
    """A single atomic fact, in a common envelope shared across every domain.

    One record must be small enough to be rendered into a context as a self-contained
    ``<RECORD>`` block, and complete enough that a human can re-verify it from the
    primary source without consulting anything else.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    record_id: str = Field(..., description="Globally unique, stable, deterministic ID.")
    domain: Domain
    source: str = Field(..., description="Concrete source name, e.g. 'SEC_EDGAR_XBRL'.")

    entity_id: str = Field(..., description="Canonical source-side entity key (CIK, NCT ID, ISO3, application number).")
    entity_name: str

    record_type: str = Field(..., description="Adapter-specific record family, e.g. 'xbrl_fact'.")
    concept: str = Field(..., description="Canonical field/concept key, e.g. 'us-gaap:Revenues'.")
    concept_label: str = Field(..., description="Human-readable concept name.")

    value: Union[float, int, str, None] = Field(
        ..., description="The fact value. Numeric where the source is numeric."
    )
    value_numeric: Optional[float] = Field(
        None, description="Numeric projection of `value`, when one exists."
    )
    unit: Optional[str] = Field(None, description="Unit string, e.g. 'USD', 'percent', 'mg'.")

    period: Optional[str] = Field(None, description="Canonical period label, e.g. 'FY2024', '2024', '2024-Q3'.")
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    version: Optional[str] = Field(
        None,
        description="Revision discriminator: accession number, label version, amendment tag.",
    )

    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Source-specific fields preserved verbatim."
    )
    raw_reference: RawReference = Field(default_factory=RawReference)

    @field_validator("record_id")
    @classmethod
    def _record_id_shape(cls, v: str) -> str:
        if not v or any(c.isspace() for c in v):
            raise ValueError(f"record_id must be non-empty and whitespace-free, got {v!r}")
        return v

    @model_validator(mode="after")
    def _numeric_projection(self) -> "NormalizedRecord":
        if self.value_numeric is None and isinstance(self.value, (int, float)):
            object.__setattr__(self, "value_numeric", float(self.value))
        return self

    def target_key(self) -> Dict[str, Any]:
        """The tuple that identifies *what fact this is*, ignoring provenance.

        Two records with equal target keys answer the same question; the leakage
        checker uses this to detect an answer sneaking in through a duplicate.
        """
        return {
            "entity_id": self.entity_id,
            "concept": self.concept,
            "period": self.period,
            "unit": self.unit,
        }


# --------------------------------------------------------------------------------------
# Layer 3: question families
# --------------------------------------------------------------------------------------


class GoldEvidence(BaseModel):
    """A record the gold answer is derived from, denormalized for re-verification.

    Denormalization is deliberate: the family file must stay self-verifiable even if
    the normalized layer is regenerated from refreshed live data.
    """

    model_config = ConfigDict(extra="forbid")

    record_id: str
    source_url: Optional[str] = None
    entity_id: str
    entity_name: str
    concept: str
    concept_label: str
    value: Union[float, int, str, None]
    value_numeric: Optional[float] = None
    unit: Optional[str] = None
    period: Optional[str] = None
    version: Optional[str] = None
    role: str = Field("evidence", description="Role in the answer, e.g. 'numerator'.")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_record(cls, rec: NormalizedRecord, role: str = "evidence") -> "GoldEvidence":
        return cls(
            record_id=rec.record_id,
            source_url=rec.raw_reference.source_url,
            entity_id=rec.entity_id,
            entity_name=rec.entity_name,
            concept=rec.concept,
            concept_label=rec.concept_label,
            value=rec.value,
            value_numeric=rec.value_numeric,
            unit=rec.unit,
            period=rec.period,
            version=rec.version,
            role=role,
            metadata=dict(rec.metadata),
        )


class CalculationSpec(BaseModel):
    """Explicit, replayable definition of a derived gold answer.

    ``operands`` maps a role name to a record ID; ``operand_values`` maps the same role
    to the numeric value used. The validator recomputes the answer from these and fails
    hard on mismatch, so an answer can never drift away from its source records.
    """

    model_config = ConfigDict(extra="forbid")

    operation: CalculationOp
    formula: str
    operands: Dict[str, str] = Field(..., description="role -> record_id")
    operand_values: Dict[str, float] = Field(..., description="role -> numeric value")
    raw_result: float
    rounded_result: float
    round_decimals: int = 2
    result_unit: Optional[str] = None

    # Convenience aliases for the two-operand operations, kept for readability.
    numerator_record_id: Optional[str] = None
    denominator_record_id: Optional[str] = None


class SourceProvenance(BaseModel):
    """Where the family's data came from, at API-call granularity."""

    model_config = ConfigDict(extra="forbid")

    source: str
    endpoint: Optional[str] = None
    request_url: Optional[str] = None
    retrieved_at: Optional[str] = None
    record_ids: List[str] = Field(default_factory=list)
    api_version: Optional[str] = None
    license_note: Optional[str] = None


class GenerationMetadata(BaseModel):
    """Everything required to reproduce this family bit-for-bit."""

    model_config = ConfigDict(extra="forbid")

    generator_version: str = GENERATOR_VERSION
    schema_version: str = SCHEMA_VERSION
    template_id: str
    template_version: str = "1.0.0"
    seed: int
    config_hash: str
    git_commit: Optional[str] = None
    generated_at: Optional[str] = None
    tokenizer_id: Optional[str] = None
    notes: Optional[str] = None


class UnanswerableSpec(BaseModel):
    """Why a family is unanswerable, and what must stay absent for it to remain so."""

    model_config = ConfigDict(extra="forbid")

    reason_code: str = Field(
        ...,
        description="e.g. 'FIELD_NOT_REPORTED_BY_ENTITY', 'PERIOD_NOT_COVERED', 'RESULTS_NOT_POSTED'.",
    )
    reason: str = Field(..., description="Human-readable justification.")
    missing_concept: Optional[str] = None
    missing_period: Optional[str] = None
    missing_entity_id: Optional[str] = None
    verified_absent_in_pool: bool = Field(
        False,
        description="True once the generator has confirmed no record in the domain pool "
        "satisfies the target conditions.",
    )
    forbidden_concept_aliases: List[str] = Field(
        default_factory=list,
        description="Concepts that would disclose the answer if present; the leakage "
        "checker treats any of these matching the target conditions as a failure.",
    )


class QuestionFamily(BaseModel):
    """The experimental unit: one question, one gold answer, many context lengths."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    question_family_id: str
    domain: Domain
    source_name: str

    question_type: QuestionType
    question: str

    answerable: bool

    gold_answer: Union[float, int, str, None]
    gold_answer_normalized: Union[float, int, str]
    answer_type: AnswerType
    answer_unit: Optional[str] = None
    numeric_tolerance: Optional[float] = Field(
        None, description="Absolute tolerance for numeric grading; None for non-numeric."
    )

    gold_evidence: List[GoldEvidence] = Field(default_factory=list)
    gold_evidence_ids: List[str] = Field(default_factory=list)

    calculation_spec: Optional[CalculationSpec] = None
    unanswerable_spec: Optional[UnanswerableSpec] = None

    target_conditions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured description of exactly which record(s) answer the "
        "question. Drives both distractor selection and leakage detection.",
    )

    source_provenance: List[SourceProvenance] = Field(default_factory=list)
    generation_metadata: GenerationMetadata

    @model_validator(mode="after")
    def _consistency(self) -> "QuestionFamily":
        if self.answerable:
            if self.gold_answer is None:
                raise ValueError(f"{self.question_family_id}: answerable family has null gold_answer")
            if not self.gold_evidence_ids:
                raise ValueError(f"{self.question_family_id}: answerable family has no gold evidence")
            if self.gold_answer_normalized == INSUFFICIENT_EVIDENCE:
                raise ValueError(
                    f"{self.question_family_id}: answerable family normalized to INSUFFICIENT_EVIDENCE"
                )
            if self.question_type is QuestionType.UNANSWERABLE:
                raise ValueError(
                    f"{self.question_family_id}: question_type UNANSWERABLE but answerable=True"
                )
        else:
            if self.gold_answer is not None:
                raise ValueError(f"{self.question_family_id}: unanswerable family must have gold_answer=None")
            if self.gold_answer_normalized != INSUFFICIENT_EVIDENCE:
                raise ValueError(
                    f"{self.question_family_id}: unanswerable family must normalize to "
                    f"{INSUFFICIENT_EVIDENCE}, got {self.gold_answer_normalized!r}"
                )
            if self.gold_evidence_ids:
                raise ValueError(
                    f"{self.question_family_id}: unanswerable family must not carry gold evidence"
                )
            if self.unanswerable_spec is None:
                raise ValueError(f"{self.question_family_id}: unanswerable family needs an unanswerable_spec")
            if self.question_type is not QuestionType.UNANSWERABLE:
                raise ValueError(
                    f"{self.question_family_id}: answerable=False requires question_type=UNANSWERABLE"
                )

        if self.question_type is QuestionType.RETRIEVAL_CALCULATION and self.calculation_spec is None:
            raise ValueError(
                f"{self.question_family_id}: RETRIEVAL_CALCULATION requires a calculation_spec"
            )

        ev_ids = [e.record_id for e in self.gold_evidence]
        if ev_ids != self.gold_evidence_ids:
            raise ValueError(
                f"{self.question_family_id}: gold_evidence_ids {self.gold_evidence_ids} "
                f"disagree with gold_evidence {ev_ids}"
            )
        return self


# --------------------------------------------------------------------------------------
# Layer 3b: context instances
# --------------------------------------------------------------------------------------


class DistractorRef(BaseModel):
    """One inserted non-gold record, with the reason it was chosen."""

    model_config = ConfigDict(extra="forbid")

    record_id: str
    distractor_type: DistractorType
    relationship_to_target: Dict[str, bool] = Field(default_factory=dict)
    position_index: Optional[int] = Field(
        None, description="0-based index of the record within the rendered context."
    )
    side: Optional[str] = Field(None, description="'before' or 'after' the gold block.")


class ContextStats(BaseModel):
    """Measured properties of one built context."""

    model_config = ConfigDict(extra="forbid")

    context_length_nominal: int
    context_tokens_actual: int
    fill_ratio: float
    tokenizer_id: str
    tokenizer_version: Optional[str] = None

    n_records_total: int
    n_records_before_target: int
    n_records_after_target: int

    target_evidence_start_token: Optional[int] = None
    target_evidence_end_token: Optional[int] = None
    target_position_relative: Optional[float] = None
    target_position_tolerance: Optional[float] = None
    target_position_ok: Optional[bool] = None


class Instance(BaseModel):
    """One (question family x context length) row -- what the LLM will eventually see."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    instance_id: str
    question_family_id: str
    domain: Domain
    question_type: QuestionType

    question: str

    context_length_nominal: int
    context_tokens_actual: int
    tokenizer: str
    tokenizer_version: Optional[str] = None

    target_evidence_start_token: Optional[int] = None
    target_evidence_end_token: Optional[int] = None
    target_position_relative: Optional[float] = None

    answerable: bool
    gold_answer: Union[float, int, str, None]
    gold_answer_normalized: Union[float, int, str]
    answer_type: AnswerType
    answer_unit: Optional[str] = None
    numeric_tolerance: Optional[float] = None

    gold_evidence_ids: List[str] = Field(default_factory=list)
    distractor_counts: Dict[str, int] = Field(default_factory=dict)
    distractors: List[DistractorRef] = Field(default_factory=list)

    context: str
    context_record_ids: List[str] = Field(
        default_factory=list,
        description="Rendered record IDs in context order. Nesting is verified on this.",
    )
    context_sha256: Optional[str] = None

    lineage: Dict[str, Any] = Field(
        default_factory=dict,
        description="Nesting lineage: the shorter variant this context extends.",
    )
    stats: Optional[ContextStats] = None
    source_provenance: List[SourceProvenance] = Field(default_factory=list)
    generation_metadata: Optional[GenerationMetadata] = None

    @model_validator(mode="after")
    def _instance_consistency(self) -> "Instance":
        if self.context_tokens_actual < 0:
            raise ValueError(f"{self.instance_id}: negative token count")
        if self.answerable and not self.gold_evidence_ids:
            raise ValueError(f"{self.instance_id}: answerable instance without gold evidence IDs")
        if not self.answerable and self.gold_evidence_ids:
            raise ValueError(f"{self.instance_id}: unanswerable instance carries gold evidence IDs")
        return self


class UnavailableVariant(BaseModel):
    """A context length that could NOT be built honestly.

    Recording these is mandatory: the alternative is padding with filler, which would
    silently corrupt the independent variable of the experiment.
    """

    model_config = ConfigDict(extra="forbid")

    question_family_id: str
    domain: Domain
    context_length_nominal: int
    reason_code: str
    reason: str
    tokens_achieved: Optional[int] = None
    records_available: Optional[int] = None


# --------------------------------------------------------------------------------------
# JSON Schema export
# --------------------------------------------------------------------------------------

EXPORTED_MODELS = {
    "normalized_record": NormalizedRecord,
    "question_family": QuestionFamily,
    "instance": Instance,
    "unavailable_variant": UnavailableVariant,
}


def export_json_schemas() -> Dict[str, Dict[str, Any]]:
    """Return ``{name: json_schema}`` for every externally consumed model."""
    return {name: model.model_json_schema() for name, model in EXPORTED_MODELS.items()}
