"""Nested context construction, evidence placement and pool-exhaustion behaviour.

These tests defend the experiment's core invariant: across lengths, only the surrounding
distractor material may change.
"""

from __future__ import annotations

import pytest

from longctx_dataset.context.builder import ContextBuilder, length_label
from longctx_dataset.context.tokenizer import get_tokenizer
from longctx_dataset.normalize.common import RecordPool
from longctx_dataset.questions import generate_families_for_domain
from longctx_dataset.schemas import (
    AnswerType, Domain, GenerationMetadata, GoldEvidence, NormalizedRecord,
    QuestionFamily, QuestionType, UnanswerableSpec, INSUFFICIENT_EVIDENCE,
)
from longctx_dataset.validation.contexts import (
    check_nesting, check_no_truncation, check_record_boundaries,
    check_target_position, check_token_compliance, is_subsequence,
)


def rec(rid, *, entity="E1", concept="c1", period="CY2024", value=100.0, unit="USD") -> NormalizedRecord:
    return NormalizedRecord(record_id=rid, domain=Domain.SEC, source="SRC", entity_id=entity,
                            entity_name=f"Entity {entity}", record_type="t", concept=concept,
                            concept_label="Concept One", value=value, unit=unit,
                            period=period, version="v1")


def big_pool(n: int = 3000) -> RecordPool:
    """A target plus a deep pool of authentic-shaped distractors."""
    records = [rec("TGT", value=42.0)]
    records += [rec(f"P{i}", period=f"CY{1900 + i}") for i in range(n // 2)]
    records += [rec(f"E{i}", entity=f"X{i}", value=1000.0 + i) for i in range(n // 2)]
    return RecordPool(records)


def answerable_family(pool: RecordPool) -> QuestionFamily:
    tgt = pool.get("TGT")
    return QuestionFamily(
        question_family_id="F_0001", domain=Domain.SEC, source_name="SRC",
        question_type=QuestionType.DIRECT_RETRIEVAL, question="What is the value?",
        answerable=True, gold_answer="42", gold_answer_normalized=42.0,
        answer_type=AnswerType.NUMERIC, answer_unit="USD", numeric_tolerance=0.01,
        gold_evidence=[GoldEvidence.from_record(tgt, "target_value")], gold_evidence_ids=["TGT"],
        target_conditions={"records": [{"entity_id": "E1", "concept": "c1",
                                        "period": "CY2024", "unit": "USD", "version": "v1"}]},
        generation_metadata=GenerationMetadata(template_id="T", seed=1, config_hash="h"),
    )


def unanswerable_family() -> QuestionFamily:
    return QuestionFamily(
        question_family_id="F_0002", domain=Domain.SEC, source_name="SRC",
        question_type=QuestionType.UNANSWERABLE, question="What is the missing value?",
        answerable=False, gold_answer=None, gold_answer_normalized=INSUFFICIENT_EVIDENCE,
        answer_type=AnswerType.INSUFFICIENT_EVIDENCE, gold_evidence=[], gold_evidence_ids=[],
        unanswerable_spec=UnanswerableSpec(reason_code="ABSENT", reason="not reported",
                                           missing_concept="c_absent", missing_entity_id="E1",
                                           verified_absent_in_pool=True,
                                           forbidden_concept_aliases=["c_absent"]),
        target_conditions={"records": [{"entity_id": "E1", "concept": "c_absent"}]},
        generation_metadata=GenerationMetadata(template_id="T", seed=1, config_hash="h"),
    )


@pytest.fixture
def builder(cfg):
    pool = big_pool()
    return ContextBuilder(cfg, pool, get_tokenizer(cfg.tokenizer)), pool


def test_length_label():
    assert length_label(4096) == "4K" and length_label(131072) == "128K"


def test_all_configured_lengths_are_built(builder, cfg):
    b, pool = builder
    instances, unavailable = b.build_family(answerable_family(pool))
    assert [i.context_length_nominal for i in instances] == cfg.context.lengths
    assert not unavailable


def test_contexts_are_ordered_subsequences_of_the_next(builder, cfg):
    b, pool = builder
    instances, _ = b.build_family(answerable_family(pool))
    for shorter, longer in zip(instances, instances[1:]):
        assert set(shorter.context_record_ids) <= set(longer.context_record_ids)
        assert is_subsequence(shorter.context_record_ids, longer.context_record_ids), \
            "growth must preserve the relative order of retained records"
        assert len(longer.context_record_ids) > len(shorter.context_record_ids)
    assert check_nesting(instances) == []


def test_lineage_records_the_parent_variant(builder, cfg):
    b, pool = builder
    instances, _ = b.build_family(answerable_family(pool))
    assert instances[0].lineage["extends_instance_id"] is None
    for shorter, longer in zip(instances, instances[1:]):
        assert longer.lineage["extends_instance_id"] == shorter.instance_id
        assert longer.lineage["added_record_ids"]


def test_gold_block_is_byte_identical_across_lengths(builder, cfg):
    b, pool = builder
    instances, _ = b.build_family(answerable_family(pool))
    hashes = {i.lineage["gold_block_sha256"] for i in instances}
    assert len(hashes) == 1, "the gold evidence block must not change with context length"
    gold_text = b.render_record(pool.get("TGT"))
    for inst in instances:
        assert inst.context.count(gold_text) == 1


def test_question_and_answer_are_invariant_across_lengths(builder, cfg):
    b, pool = builder
    fam = answerable_family(pool)
    instances, _ = b.build_family(fam)
    assert {i.question for i in instances} == {fam.question}
    assert {i.gold_answer_normalized for i in instances} == {fam.gold_answer_normalized}
    assert {tuple(i.gold_evidence_ids) for i in instances} == {tuple(fam.gold_evidence_ids)}


def test_evidence_sits_at_the_configured_position(builder, cfg):
    b, pool = builder
    instances, _ = b.build_family(answerable_family(pool))
    for inst in instances:
        assert check_target_position(inst, cfg.context.target_position,
                                     cfg.context.position_tolerance) == []
        assert abs(inst.target_position_relative - 0.5) <= cfg.context.position_tolerance
        assert inst.target_evidence_end_token <= inst.context_tokens_actual


def test_contexts_never_exceed_their_nominal_target(builder, cfg):
    b, pool = builder
    instances, _ = b.build_family(answerable_family(pool))
    for inst in instances:
        assert inst.context_tokens_actual <= inst.context_length_nominal
        assert check_token_compliance(inst, cfg.context.min_fill_ratio) == []


def test_record_boundaries_are_well_formed(builder, cfg):
    b, pool = builder
    instances, _ = b.build_family(answerable_family(pool))
    for inst in instances:
        assert check_record_boundaries(inst) == []
        assert inst.context.count("<RECORD id=") == len(inst.context_record_ids)
        assert inst.context.count("</RECORD>") == len(inst.context_record_ids)


def test_truncation_check_catches_a_damaged_gold_block(builder, cfg):
    b, pool = builder
    inst = b.build_family(answerable_family(pool))[0][0]
    gold_text = b.render_record(pool.get("TGT"))
    damaged = inst.model_copy(update={"context": inst.context.replace("value: 42.0", "value: 4")})
    assert check_no_truncation(inst, {"TGT": gold_text}) == []
    assert check_no_truncation(damaged, {"TGT": gold_text}) != []


def test_distractor_metadata_is_complete_and_counted(builder, cfg):
    b, pool = builder
    inst = b.build_family(answerable_family(pool))[0][-1]
    assert len(inst.distractors) == len(inst.context_record_ids) - len(inst.gold_evidence_ids)
    assert sum(inst.distractor_counts.values()) == len(inst.distractors)
    for d in inst.distractors:
        assert d.relationship_to_target and d.position_index is not None
        assert d.side in ("before", "after")


def test_distractors_flank_the_target_on_both_sides(builder, cfg):
    b, pool = builder
    inst = b.build_family(answerable_family(pool))[0][-1]
    sides = {d.side for d in inst.distractors}
    assert sides == {"before", "after"}


def test_unanswerable_context_excludes_the_missing_concept(cfg):
    pool = big_pool(400)
    pool.add(rec("LEAK", concept="c_absent", entity="E1"))
    b = ContextBuilder(cfg, pool, get_tokenizer(cfg.tokenizer))
    instances, _ = b.build_family(unanswerable_family())
    assert instances
    for inst in instances:
        assert "LEAK" not in inst.context_record_ids, "the answer leaked into an unanswerable context"
        assert inst.gold_evidence_ids == []
        assert inst.target_position_relative is None


def test_insufficient_pool_marks_variants_unavailable_without_padding(cfg):
    """A shallow pool must yield fewer honest variants, never padded ones."""
    pool = RecordPool([rec("TGT", value=42.0)] + [rec(f"P{i}", period=f"CY{1900 + i}")
                                                  for i in range(12)])
    b = ContextBuilder(cfg, pool, get_tokenizer(cfg.tokenizer))
    instances, unavailable = b.build_family(answerable_family(pool))
    assert unavailable, "a shallow pool must produce unavailable variants"
    assert {u.reason_code for u in unavailable} == {"POOL_EXHAUSTED"}
    for u in unavailable:
        assert u.reason and "no filler" in u.reason.lower() or "padding" in u.reason.lower()
    built = {i.context_length_nominal for i in instances}
    missing = {u.context_length_nominal for u in unavailable}
    assert built.isdisjoint(missing)
    assert built | missing == set(cfg.context.lengths)
    # Whatever was built must still be honest about its length.
    for inst in instances:
        assert inst.context_tokens_actual >= cfg.context.min_fill_ratio * inst.context_length_nominal


def test_position_unsatisfiable_variants_are_reported_not_emitted(cfg):
    """When whole records cannot place the evidence at the target depth, say so.

    At very short targets one record is a large fraction of the context, so the
    position tolerance is sometimes arithmetically unreachable. Such a variant must be
    recorded as unavailable rather than emitted out of spec -- that is what lets the
    target-position check stay an absolute invariant for everything emitted.
    """
    # One oversized gold record plus a couple of distractors in a tiny budget.
    big = rec("TGT", value=42.0, concept="c1")
    pool = RecordPool([big] + [rec(f"P{i}", period=f"CY{1900 + i}") for i in range(40)])
    cfg.context.lengths = [200, 4096]
    cfg.context.min_fill_ratio = 0.5
    b = ContextBuilder(cfg, pool, get_tokenizer(cfg.tokenizer))
    instances, unavailable = b.build_family(answerable_family(pool))
    reasons = {u.reason_code for u in unavailable}
    assert reasons <= {"POSITION_TOLERANCE_UNSATISFIABLE", "POOL_EXHAUSTED"}
    for inst in instances:
        assert check_target_position(inst, cfg.context.target_position,
                                     cfg.context.position_tolerance) == [], \
            "an emitted instance must always satisfy the position invariant"


def test_empty_pool_yields_no_instances_at_all(cfg):
    pool = RecordPool([rec("TGT", value=42.0)])
    b = ContextBuilder(cfg, pool, get_tokenizer(cfg.tokenizer))
    instances, unavailable = b.build_family(answerable_family(pool))
    assert instances == []
    assert len(unavailable) == len(cfg.context.lengths)


def test_missing_gold_record_fails_loudly(cfg):
    pool = big_pool(200)
    fam = answerable_family(pool)
    stripped = RecordPool([r for r in pool.records if r.record_id != "TGT"])
    b = ContextBuilder(cfg, stripped, get_tokenizer(cfg.tokenizer))
    with pytest.raises(KeyError, match="gold evidence not found"):
        b.build_family(fam)


def test_building_is_reproducible_for_a_seed(cfg):
    pool = big_pool(800)
    fam = answerable_family(pool)
    a = ContextBuilder(cfg, pool, get_tokenizer(cfg.tokenizer)).build_family(fam)[0]
    b = ContextBuilder(cfg, pool, get_tokenizer(cfg.tokenizer)).build_family(fam)[0]
    assert [i.context_sha256 for i in a] == [i.context_sha256 for i in b]


def test_changing_the_seed_changes_the_context_but_not_the_gold(cfg):
    pool = big_pool(800)
    fam = answerable_family(pool)
    a = ContextBuilder(cfg, pool, get_tokenizer(cfg.tokenizer)).build_family(fam)[0]
    cfg.seed += 1
    b = ContextBuilder(cfg, pool, get_tokenizer(cfg.tokenizer)).build_family(fam)[0]
    assert [i.context_sha256 for i in a] != [i.context_sha256 for i in b]
    assert [i.gold_answer_normalized for i in a] == [i.gold_answer_normalized for i in b]
    assert {i.lineage["gold_block_sha256"] for i in a} == {i.lineage["gold_block_sha256"] for i in b}


def test_changing_the_tokenizer_changes_measured_lengths_not_gold(cfg):
    pool = big_pool(800)
    fam = answerable_family(pool)
    a = ContextBuilder(cfg, pool, get_tokenizer(cfg.tokenizer)).build_family(fam)[0]
    cfg.tokenizer.id = "tiktoken:cl100k_base"
    b = ContextBuilder(cfg, pool, get_tokenizer(cfg.tokenizer)).build_family(fam)[0]
    assert {i.tokenizer for i in a} == {"whitespace:v1"}
    assert {i.tokenizer for i in b} == {"tiktoken:cl100k_base"}
    assert [i.gold_answer_normalized for i in a] == [i.gold_answer_normalized for i in b]


def test_oversized_candidates_are_retained_for_longer_variants(cfg):
    """A record too large for 4K must still be available at 8K.

    Regression guard: an earlier look-ahead implementation pruned candidates that did
    not fit the *current* budget, permanently shrinking the pool and causing premature
    POOL_EXHAUSTED at the longer lengths.
    """
    records = [rec("TGT", value=42.0)]
    # A handful of very large records interleaved with ordinary ones.
    for i in range(200):
        pad = "x" * (1200 if i % 7 == 0 else 10)
        records.append(rec(f"R{i}", period=f"CY{1800 + i}", value=float(i), entity=f"E{pad[:40]}{i}"))
    pool = RecordPool(records)
    cfg.context.lengths = [512, 1024, 2048, 4096]
    b = ContextBuilder(cfg, pool, get_tokenizer(cfg.tokenizer))
    instances, _ = b.build_family(answerable_family(pool))
    assert len(instances) >= 3
    assert check_nesting(instances) == []
    # Every length must still fill honestly rather than starving on a pruned pool.
    for inst in instances:
        assert inst.context_tokens_actual >= cfg.context.min_fill_ratio * inst.context_length_nominal
