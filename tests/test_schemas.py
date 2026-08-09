"""Schema-level invariants.

These are the guardrails that stop a malformed family from ever reaching the dataset,
so each one is asserted to *reject*, not merely to warn.
"""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from longctx_dataset.schemas import (
    AnswerType,
    CalculationOp,
    CalculationSpec,
    Domain,
    GenerationMetadata,
    GoldEvidence,
    Instance,
    NormalizedRecord,
    QuestionFamily,
    QuestionType,
    UnanswerableSpec,
    export_json_schemas,
    INSUFFICIENT_EVIDENCE,
)


def _meta() -> GenerationMetadata:
    return GenerationMetadata(template_id="T", seed=1, config_hash="abc")


def _evidence(record_id: str = "R1") -> GoldEvidence:
    return GoldEvidence(record_id=record_id, entity_id="E", entity_name="Entity",
                        concept="c", concept_label="C", value=10.0, value_numeric=10.0)


def _family(**over) -> QuestionFamily:
    base = dict(
        question_family_id="X_0001", domain=Domain.SEC, source_name="S",
        question_type=QuestionType.DIRECT_RETRIEVAL, question="q?", answerable=True,
        gold_answer="10", gold_answer_normalized=10.0, answer_type=AnswerType.NUMERIC,
        numeric_tolerance=0.01, gold_evidence=[_evidence()], gold_evidence_ids=["R1"],
        generation_metadata=_meta(),
    )
    base.update(over)
    return QuestionFamily(**base)


def test_valid_family_round_trips():
    fam = _family()
    assert QuestionFamily.model_validate(fam.model_dump(mode="json")) == fam


def test_answerable_family_requires_gold_answer():
    with pytest.raises(ValidationError, match="null gold_answer"):
        _family(gold_answer=None)


def test_answerable_family_requires_evidence():
    with pytest.raises(ValidationError, match="no gold evidence"):
        _family(gold_evidence=[], gold_evidence_ids=[])


def test_answerable_family_cannot_normalize_to_insufficient_evidence():
    with pytest.raises(ValidationError, match="INSUFFICIENT_EVIDENCE"):
        _family(gold_answer_normalized=INSUFFICIENT_EVIDENCE)


def test_unanswerable_family_must_not_carry_gold():
    with pytest.raises(ValidationError, match="must have gold_answer=None"):
        _family(answerable=False, question_type=QuestionType.UNANSWERABLE,
                gold_answer_normalized=INSUFFICIENT_EVIDENCE,
                answer_type=AnswerType.INSUFFICIENT_EVIDENCE)


def test_unanswerable_family_requires_spec():
    with pytest.raises(ValidationError, match="needs an unanswerable_spec"):
        _family(answerable=False, question_type=QuestionType.UNANSWERABLE, gold_answer=None,
                gold_answer_normalized=INSUFFICIENT_EVIDENCE,
                answer_type=AnswerType.INSUFFICIENT_EVIDENCE,
                gold_evidence=[], gold_evidence_ids=[])


def test_unanswerable_family_is_valid_with_spec():
    fam = _family(
        answerable=False, question_type=QuestionType.UNANSWERABLE, gold_answer=None,
        gold_answer_normalized=INSUFFICIENT_EVIDENCE, answer_type=AnswerType.INSUFFICIENT_EVIDENCE,
        numeric_tolerance=None, gold_evidence=[], gold_evidence_ids=[],
        unanswerable_spec=UnanswerableSpec(reason_code="X", reason="y", verified_absent_in_pool=True),
    )
    assert fam.gold_answer_normalized == INSUFFICIENT_EVIDENCE


def test_answerable_true_with_unanswerable_type_is_rejected():
    with pytest.raises(ValidationError, match="answerable=True"):
        _family(question_type=QuestionType.UNANSWERABLE)


def test_calculation_type_requires_spec():
    with pytest.raises(ValidationError, match="requires a calculation_spec"):
        _family(question_type=QuestionType.RETRIEVAL_CALCULATION)


def test_evidence_ids_must_agree_with_evidence():
    with pytest.raises(ValidationError, match="disagree"):
        _family(gold_evidence_ids=["OTHER"])


def test_record_id_must_be_whitespace_free():
    with pytest.raises(ValidationError, match="whitespace-free"):
        NormalizedRecord(record_id="has space", domain=Domain.SEC, source="s",
                         entity_id="e", entity_name="E", record_type="t",
                         concept="c", concept_label="C", value=1.0)


def test_numeric_projection_is_filled_automatically():
    rec = NormalizedRecord(record_id="R", domain=Domain.SEC, source="s", entity_id="e",
                           entity_name="E", record_type="t", concept="c", concept_label="C",
                           value=42)
    assert rec.value_numeric == 42.0


def test_target_key_ignores_provenance():
    kw = dict(domain=Domain.SEC, source="s", entity_id="e", entity_name="E", record_type="t",
              concept="c", concept_label="C", value=1.0, period="CY2020", unit="USD")
    a = NormalizedRecord(record_id="A", version="v1", **kw)
    b = NormalizedRecord(record_id="B", version="v2", **kw)
    assert a.target_key() == b.target_key()


def test_instance_rejects_unanswerable_with_evidence():
    with pytest.raises(ValidationError, match="carries gold evidence"):
        Instance(instance_id="I", question_family_id="F", domain=Domain.SEC,
                 question_type=QuestionType.UNANSWERABLE, question="q",
                 context_length_nominal=100, context_tokens_actual=99, tokenizer="t",
                 answerable=False, gold_answer=None,
                 gold_answer_normalized=INSUFFICIENT_EVIDENCE,
                 answer_type=AnswerType.INSUFFICIENT_EVIDENCE,
                 gold_evidence_ids=["R1"], context="c")


def test_json_schemas_export_for_every_public_model():
    schemas = export_json_schemas()
    assert set(schemas) == {"normalized_record", "question_family", "instance", "unavailable_variant"}
    for name, schema in schemas.items():
        assert schema.get("properties"), f"{name} exported an empty schema"
