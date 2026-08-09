"""Leakage detection for unanswerable families and duplicate answer sources."""

from __future__ import annotations

import pytest

from longctx_dataset.normalize.common import RecordPool
from longctx_dataset.schemas import (
    AnswerType, Domain, GenerationMetadata, GoldEvidence, NormalizedRecord,
    QuestionFamily, QuestionType, UnanswerableSpec, INSUFFICIENT_EVIDENCE,
)
from longctx_dataset.validation.leakage import (
    check_answerable_duplication, check_gold_absent, check_gold_present,
    check_unanswerable_leakage,
)


def rec(rid, *, entity="E1", concept="c1", period="CY2024", value=1.0) -> NormalizedRecord:
    return NormalizedRecord(record_id=rid, domain=Domain.SEC, source="s", entity_id=entity,
                            entity_name=entity, record_type="t", concept=concept,
                            concept_label="C", value=value, unit="USD", period=period,
                            version="v1")


def unanswerable(**over) -> QuestionFamily:
    base = dict(
        question_family_id="U1", domain=Domain.SEC, source_name="s",
        question_type=QuestionType.UNANSWERABLE, question="q?", answerable=False,
        gold_answer=None, gold_answer_normalized=INSUFFICIENT_EVIDENCE,
        answer_type=AnswerType.INSUFFICIENT_EVIDENCE, gold_evidence=[], gold_evidence_ids=[],
        unanswerable_spec=UnanswerableSpec(
            reason_code="ABSENT", reason="not reported", missing_concept="c_missing",
            missing_entity_id="E1", verified_absent_in_pool=True,
            forbidden_concept_aliases=["c_missing", "c_alias"]),
        target_conditions={"records": [{"entity_id": "E1", "concept": "c_missing"}]},
        generation_metadata=GenerationMetadata(template_id="T", seed=1, config_hash="h"),
    )
    base.update(over)
    return QuestionFamily(**base)


def answerable(**over) -> QuestionFamily:
    tgt = rec("TGT", value=42.0)
    base = dict(
        question_family_id="A1", domain=Domain.SEC, source_name="s",
        question_type=QuestionType.DIRECT_RETRIEVAL, question="q?", answerable=True,
        gold_answer="42", gold_answer_normalized=42.0, answer_type=AnswerType.NUMERIC,
        numeric_tolerance=0.01,
        gold_evidence=[GoldEvidence.from_record(tgt, "target_value")], gold_evidence_ids=["TGT"],
        target_conditions={"records": [{"entity_id": "E1", "concept": "c1",
                                        "period": "CY2024", "unit": "USD", "version": "v1"}]},
        generation_metadata=GenerationMetadata(template_id="T", seed=1, config_hash="h"),
    )
    base.update(over)
    return QuestionFamily(**base)


def test_clean_unanswerable_context_passes():
    pool = RecordPool([rec("A", concept="c1"), rec("B", concept="c2", entity="E2")])
    assert check_unanswerable_leakage(unanswerable(), ["A", "B"], pool) == []


def test_record_satisfying_the_target_conditions_is_flagged():
    pool = RecordPool([rec("LEAK", concept="c_missing", entity="E1")])
    problems = check_unanswerable_leakage(unanswerable(), ["LEAK"], pool)
    assert problems and "disclose the answer" in problems[0]


def test_forbidden_alias_concept_is_flagged():
    """A synonym concept for the same entity leaks just as surely as the concept itself."""
    pool = RecordPool([rec("ALIAS", concept="c_alias", entity="E1")])
    problems = check_unanswerable_leakage(unanswerable(), ["ALIAS"], pool)
    assert problems and "forbidden concept alias" in problems[0]


def test_same_concept_for_a_different_entity_does_not_leak():
    pool = RecordPool([rec("OTHER", concept="c_missing", entity="E2")])
    assert check_unanswerable_leakage(unanswerable(), ["OTHER"], pool) == []


def test_context_record_missing_from_the_pool_is_reported():
    problems = check_unanswerable_leakage(unanswerable(), ["GHOST"], RecordPool([]))
    assert problems and "not in the normalized pool" in problems[0]


def test_leakage_check_is_a_no_op_for_answerable_families():
    pool = RecordPool([rec("X")])
    assert check_unanswerable_leakage(answerable(), ["X"], pool) == []


def test_duplicate_answer_source_is_flagged_for_answerable_families():
    dup = rec("DUP", value=42.0)  # identical coordinates to the gold record
    pool = RecordPool([rec("TGT", value=42.0), dup])
    problems = check_answerable_duplication(answerable(), ["TGT", "DUP"], pool)
    assert problems and "DUP" in problems[0]


def test_gold_record_itself_is_not_treated_as_a_duplicate():
    pool = RecordPool([rec("TGT", value=42.0), rec("OTH", period="CY2023")])
    assert check_answerable_duplication(answerable(), ["TGT", "OTH"], pool) == []


def test_gold_presence_and_absence_checks():
    fam = answerable()
    assert check_gold_present(fam, ["A", "TGT", "B"]) == []
    assert check_gold_present(fam, ["A", "B"]) != []
    u = unanswerable()
    assert check_gold_absent(u, ["A", "B"]) == []
