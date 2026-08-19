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
from longctx_dataset.schemas import (
    AnswerType, DistractorType, Domain, NormalizedRecord, QuestionType, UnanswerableSpec,
    INSUFFICIENT_EVIDENCE,
)


def rec(rid, *, domain=Domain.SEC, entity="E1", concept="c1", period="CY2024", unit="USD", version="v1",
        value=100.0, label="Concept One", meta=None) -> NormalizedRecord:
    return NormalizedRecord(record_id=rid, domain=domain, source="s", entity_id=entity,
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


def test_measurement_basis_variants_are_not_wrong_unit_when_unit_matches():
    target = rec("T", domain=Domain.FRED, entity="US", concept="CPIAUCSL",
                 label="Consumer Price Index (Seasonally Adjusted)",
                 unit="Index 1982-1984=100",
                 meta={"series_family": "cpi", "seasonal_adjustment": "Seasonally Adjusted"})
    variant = rec("V", domain=Domain.FRED, entity="US", concept="CPIAUCNS",
                  label="Consumer Price Index (Not Seasonally Adjusted)",
                  unit="Index 1982-1984=100",
                  meta={"series_family": "cpi", "seasonal_adjustment": "Not Seasonally Adjusted"})
    assert classify_distractor(variant, [target])[0] is DistractorType.WRONG_SERIES_VARIANT


def test_actual_unit_mismatch_remains_wrong_unit():
    """Sources publish current vs constant dollars under distinct units."""
    target = rec("T", concept="NY.GDP.MKTP.CD", label="GDP (current US$)", unit="current US$")
    variant = rec("V", concept="NY.GDP.MKTP.KD", label="GDP (constant 2015 US$)",
                  unit="constant 2015 US$")
    assert classify_distractor(variant, [target])[0] is DistractorType.WRONG_UNIT

    # A genuinely different quantity must NOT be swept into WRONG_UNIT.
    other = rec("O", concept="NY.GDP.PCAP.CD", label="GDP per capita (current US$)",
                unit="current US$")
    assert classify_distractor(other, [target])[0] is not DistractorType.WRONG_UNIT


def test_no_near_match_without_meaningful_target_value():
    near = rec("N", value=100.1)
    dtype, flags = classify_distractor(near, [], target_values=(), allow_near_match=False)
    assert dtype is DistractorType.OTHER_SAME_DOMAIN
    assert flags["value_within_5_percent"] is False


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


def test_unanswerable_selector_does_not_emit_near_match_value(cfg):
    anchor = rec("ANCHOR", value=100.0)
    close = rec("CLOSE", concept="other", value=101.0)
    pool = RecordPool([TARGET, anchor, close, rec("FAR", entity="E2", concept="other2", value=999.0)])
    fam = _family(
        pool,
        question_type=QuestionType.UNANSWERABLE,
        answerable=False,
        gold_answer=None,
        gold_answer_normalized=INSUFFICIENT_EVIDENCE,
        answer_type=AnswerType.INSUFFICIENT_EVIDENCE,
        numeric_tolerance=None,
        gold_evidence=[],
        gold_evidence_ids=[],
        unanswerable_spec=UnanswerableSpec(
            reason_code="ABSENT", reason="missing", missing_concept="missing",
            missing_entity_id="E1", verified_absent_in_pool=True,
            forbidden_concept_aliases=["missing"],
        ),
        target_conditions={"records": [{"entity_id": "E1", "concept": "missing"}]},
    )
    kinds = {c.distractor_type for c in DistractorSelector(cfg, pool).build(fam)}
    assert DistractorType.NEAR_MATCH_VALUE not in kinds


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


def test_explicitly_named_foils_are_placed_first(cfg):
    """A question that names a competing record by value must actually contain it.

    Foils with no period (FDA products, trial arms) are the case an earlier key
    mismatch silently dropped: the condition carried ``None`` while the record was
    compared as ``""``.
    """
    target = rec("TGT", period=None)
    foil = rec("FOIL", period=None, entity="E1", concept="c2")
    filler = [rec(f"Z{i}", entity=f"E{i + 5}", concept="c9", period=None, value=1e6 + i)
              for i in range(40)]
    pool = RecordPool([target, foil] + filler)
    fam = _family(pool, gold_evidence_ids=["TGT"],
                  target_conditions={
                      "records": [{"entity_id": "E1", "concept": "c1", "period": None,
                                   "unit": "USD", "version": "v1"}],
                      "explicit_foils": [{"entity_id": "E1", "concept": "c2", "period": None}],
                  })
    ordered = DistractorSelector(cfg, pool).build(fam)
    same_tier = [c for c in ordered if c.distractor_type is
                 next(x.distractor_type for x in ordered if x.record.record_id == "FOIL")]
    assert same_tier[0].record.record_id == "FOIL", \
        "a foil named in the question must lead its tier so it survives the shortest context"
