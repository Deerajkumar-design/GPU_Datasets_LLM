"""Distractor classification and selection."""

from __future__ import annotations

import pytest

from longctx_dataset.distractors.selector import DistractorSelector
from longctx_dataset.distractors.taxonomy import (
    DISTRACTOR_TIERS,
    classify_distractor,
    condition_satisfied_by,
    describe_taxonomy,
)
from longctx_dataset.normalize.common import RecordPool
from longctx_dataset.schemas import DistractorType, Domain, NormalizedRecord


def rec(rid, *, entity="E1", concept="c1", period="CY2024", unit="USD", version="v1",
        value=100.0, label="Concept One", meta=None) -> NormalizedRecord:
    return NormalizedRecord(record_id=rid, domain=Domain.SEC, source="s", entity_id=entity,
                            entity_name=entity, record_type="t", concept=concept,
                            concept_label=label, value=value, unit=unit, period=period,
                            version=version, metadata=meta or {})


TARGET = rec("TGT")


@pytest.mark.parametrize("candidate,expected", [
    (rec("A", version="v2"),                         DistractorType.WRONG_VERSION),
    (rec("B", unit="shares"),                        DistractorType.WRONG_UNIT),
    (rec("C", period="CY2023"),                      DistractorType.WRONG_PERIOD),
    (rec("D", entity="E2"),                          DistractorType.WRONG_ENTITY),
    (rec("E", concept="c2", period="CY2023"),        DistractorType.WRONG_FIELD),
    (rec("F", entity="E2", concept="c2", period="CY2020", value=100.5),
                                                     DistractorType.NEAR_MATCH_VALUE),
    (rec("G", entity="E2", concept="c2", period="CY2020", value=999999.0),
                                                     DistractorType.OTHER_SAME_DOMAIN),
])
def test_each_taxonomy_class_is_reachable(candidate, expected):
    dtype, flags = classify_distractor(candidate, [TARGET])
    assert dtype is expected
    assert flags, "every classification must carry relationship metadata"


def test_unit_basis_variants_are_classified_as_wrong_unit():
    """Sources publish current vs constant dollars under distinct concept codes."""
    target = rec("T", concept="NY.GDP.MKTP.CD", label="GDP (current US$)", unit="current US$")
    variant = rec("V", concept="NY.GDP.MKTP.KD", label="GDP (constant 2015 US$)",
                  unit="constant 2015 US$")
    assert classify_distractor(variant, [target])[0] is DistractorType.WRONG_UNIT

    # A genuinely different quantity must NOT be swept into WRONG_UNIT.
    other = rec("O", concept="NY.GDP.PCAP.CD", label="GDP per capita (current US$)",
                unit="current US$")
    assert classify_distractor(other, [target])[0] is not DistractorType.WRONG_UNIT


def test_relationship_flags_describe_the_actual_difference():
    _, flags = classify_distractor(rec("A", period="CY2020"), [TARGET])
    assert flags["same_entity"] and flags["same_metric"] and flags["different_period"]
    assert not flags["same_period"]


def test_strongest_relationship_wins_across_multiple_targets():
    targets = [rec("T1", entity="E9", concept="zzz"), TARGET]
    dtype, _ = classify_distractor(rec("A", version="v2"), targets)
    assert dtype is DistractorType.WRONG_VERSION
    assert DISTRACTOR_TIERS.index(DistractorType.WRONG_VERSION) == 0


def test_taxonomy_documents_every_type():
    assert set(describe_taxonomy()) == {t.value for t in DistractorType}


# ---- condition matching --------------------------------------------------------------


def test_condition_matching_ignores_unspecified_keys():
    assert condition_satisfied_by(TARGET, {"entity_id": "E1", "concept": "c1"})
    assert condition_satisfied_by(TARGET, {"entity_id": "E1", "period": None})
    assert not condition_satisfied_by(TARGET, {"entity_id": "E2"})


def test_metadata_discriminator_separates_sibling_records():
    """Arms of one trial share every coarse key; only the label tells them apart."""
    a = rec("A", meta={"arm_label": "Group I"})
    b = rec("B", meta={"arm_label": "Group II"})
    cond = {"entity_id": "E1", "concept": "c1", "metadata_match": {"arm_label": "Group I"}}
    assert condition_satisfied_by(a, cond)
    assert not condition_satisfied_by(b, cond)


# ---- selection -----------------------------------------------------------------------


def _family(pool, **over):
    from longctx_dataset.schemas import (AnswerType, GenerationMetadata, GoldEvidence,
                                         QuestionFamily, QuestionType)
    tgt = pool.get("TGT")
    base = dict(
        question_family_id="F_0001", domain=Domain.SEC, source_name="s",
        question_type=QuestionType.DIRECT_RETRIEVAL, question="q?", answerable=True,
        gold_answer="100", gold_answer_normalized=100.0, answer_type=AnswerType.NUMERIC,
        numeric_tolerance=0.01,
        gold_evidence=[GoldEvidence.from_record(tgt, "target_value")],
        gold_evidence_ids=["TGT"],
        target_conditions={"records": [{"entity_id": "E1", "concept": "c1",
                                        "period": "CY2024", "unit": "USD", "version": "v1"}]},
        generation_metadata=GenerationMetadata(template_id="T", seed=1, config_hash="h"),
    )
    base.update(over)
    return QuestionFamily(**base)


def test_selector_excludes_gold_and_duplicate_answer_sources(cfg):
    duplicate = rec("DUP")  # identical coordinates to TARGET: would answer the question
    pool = RecordPool([TARGET, duplicate, rec("OK", period="CY2023")])
    fam = _family(pool)
    ids = {c.record.record_id for c in DistractorSelector(cfg, pool).build(fam)}
    assert "TGT" not in ids, "gold evidence must never be offered as a distractor"
    assert "DUP" not in ids, "a second record answering the question must be excluded"
    assert "OK" in ids


def test_selector_never_renders_null_observation_records(cfg):
    null_rec = NormalizedRecord(record_id="NULL1", domain=Domain.SEC, source="s", entity_id="E1",
                                entity_name="E1", record_type="observation_missing",
                                concept="c9", concept_label="C", value=None, period="CY2000")
    pool = RecordPool([TARGET, null_rec, rec("OK", period="CY2023")])
    ids = {c.record.record_id for c in DistractorSelector(cfg, pool).build(_family(pool))}
    assert "NULL1" not in ids


def test_selector_is_deterministic_for_a_seed(cfg):
    pool = RecordPool([TARGET] + [rec(f"R{i}", period=f"CY{2000 + i}") for i in range(30)])
    fam = _family(pool)
    a = [c.record.record_id for c in DistractorSelector(cfg, pool).build(fam)]
    b = [c.record.record_id for c in DistractorSelector(cfg, pool).build(fam)]
    assert a == b


def test_selector_order_changes_with_the_seed(cfg):
    pool = RecordPool([TARGET] + [rec(f"R{i}", period=f"CY{2000 + i}") for i in range(30)])
    fam = _family(pool)
    a = [c.record.record_id for c in DistractorSelector(cfg, pool).build(fam)]
    cfg.seed = cfg.seed + 1
    b = [c.record.record_id for c in DistractorSelector(cfg, pool).build(fam)]
    assert set(a) == set(b), "a different seed should reorder, not change the eligible pool"
    assert a != b, "a different seed must produce a different ordering"


def test_selector_interleaves_tiers_rather_than_draining_one(cfg):
    records = [TARGET]
    records += [rec(f"P{i}", period=f"CY{2000 + i}") for i in range(20)]      # WRONG_PERIOD
    records += [rec(f"E{i}", entity=f"X{i}") for i in range(20)]              # WRONG_ENTITY
    records += [rec(f"O{i}", entity=f"Y{i}", concept="zz", period="CY1990",
                    value=10.0 * (i + 3)) for i in range(20)]                 # OTHER
    pool = RecordPool(records)
    head = DistractorSelector(cfg, pool).build(_family(pool))[:12]
    kinds = {c.distractor_type for c in head}
    assert len(kinds) >= 3, f"expected a mix of tiers early, got {kinds}"
