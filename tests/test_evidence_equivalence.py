"""Semantic evidence-equivalence rules."""

from __future__ import annotations

from longctx_dataset.evidence import build_equivalence_groups, records_equivalent, semantic_period_key
from longctx_dataset.schemas import (
    AnswerType, Domain, GenerationMetadata, GoldEvidence, NormalizedRecord, QuestionFamily, QuestionType,
)


def rec(rid, *, entity="E1", concept="us-gaap:NetCash", period="CY2021Q3",
        start=None, end=None, unit="USD", version="10-Q|0001", value=-16276000000.0):
    return NormalizedRecord(
        record_id=rid, domain=Domain.SEC, source="SEC_EDGAR_XBRL_COMPANYFACTS",
        entity_id=entity, entity_name=entity, record_type="xbrl_fact",
        concept=concept, concept_label="Net cash", value=value, value_numeric=float(value),
        unit=unit, period=period, period_start=start, period_end=end, version=version,
    )


def family(gold):
    return QuestionFamily(
        question_family_id="SEC_9999", domain=Domain.SEC, source_name="SEC",
        question_type=QuestionType.TEMPORAL_VERSION, question="q?", answerable=True,
        gold_answer="-16,276,000,000", gold_answer_normalized=-16276000000.0,
        answer_type=AnswerType.NUMERIC, answer_unit="USD", numeric_tolerance=0.5,
        gold_evidence=[GoldEvidence.from_record(gold, "target_value")],
        gold_evidence_ids=[gold.record_id],
        target_conditions={"records": [{"entity_id": gold.entity_id, "concept": gold.concept,
                                        "period": gold.period, "unit": gold.unit,
                                        "version": gold.version}]},
        generation_metadata=GenerationMetadata(template_id="T", seed=1, config_hash="h"),
    )


def test_frame_and_date_interval_for_same_fact_are_equivalent():
    framed = rec("FRAME", period="CY2021Q3")
    ranged = rec("RANGE", period="2021-07-01..2021-09-30",
                 start="2021-07-01", end="2021-09-30")
    assert semantic_period_key(framed) == ("2021-07-01", "2021-09-30")
    assert records_equivalent(framed, ranged)
    groups = build_equivalence_groups(family(framed), [framed, ranged])
    assert groups[0].canonical_record_ids == ["FRAME", "RANGE"]


def test_same_number_different_period_is_not_equivalent():
    assert not records_equivalent(rec("A", period="CY2021Q3"), rec("B", period="CY2021Q2"))


def test_same_number_different_entity_is_not_equivalent():
    assert not records_equivalent(rec("A", entity="E1"), rec("B", entity="E2"))


def test_same_metric_version_difference_is_not_equivalent():
    assert not records_equivalent(rec("A", version="10-Q|old"), rec("B", version="10-Q|new"))


def test_identical_duplicate_source_representation_is_equivalent():
    a = rec("A", period="2021-07-01..2021-09-30", start="2021-07-01", end="2021-09-30")
    b = rec("B", period="2021-07-01..2021-09-30", start="2021-07-01", end="2021-09-30")
    assert records_equivalent(a, b)
