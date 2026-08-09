"""End-to-end integration over the committed fixtures.

Runs normalize -> generate-questions -> build-contexts -> validate entirely offline and
asserts the pipeline's contract, including that validation genuinely *catches* injected
corruption rather than passing everything by construction.
"""

from __future__ import annotations

import json

import pytest

from longctx_dataset.pipeline import (families_path, instances_path, load_pool,
                                      stage_build_contexts, stage_generate_questions,
                                      stage_normalize, unavailable_path)
from longctx_dataset.schemas import Domain, Instance, QuestionFamily, QuestionType
from longctx_dataset.storage.io import read_models, write_jsonl
from longctx_dataset.validation.dataset import run_validation


@pytest.fixture
def built(cfg):
    stage_normalize(cfg, log=lambda *_: None)
    families = stage_generate_questions(cfg, log=lambda *_: None)
    stage_build_contexts(cfg, log=lambda *_: None)
    return cfg, families


def test_pipeline_produces_families_and_instances(built):
    cfg, families = built
    assert families
    instances = read_models(instances_path(cfg), Instance)
    assert instances
    fam_ids = {f.question_family_id for f in families}
    assert {i.question_family_id for i in instances} <= fam_ids


def test_pipeline_covers_all_question_types(built):
    _, families = built
    assert {f.question_type for f in families} == set(QuestionType)


def test_every_domain_contributes_families(built):
    _, families = built
    assert {f.domain for f in families} == {
        Domain.SEC, Domain.FDA, Domain.CLINICAL_TRIALS, Domain.WORLD_BANK}


def test_no_duplicate_questions_within_a_domain(built):
    _, families = built
    seen = set()
    for f in families:
        key = (f.domain, f.question)
        assert key not in seen, f"duplicate question in {f.domain.value}"
        seen.add(key)


def test_full_validation_passes_on_a_clean_build(built):
    cfg, _ = built
    report = run_validation(cfg, log=lambda *_: None)
    failed = [c.check_id for c in report.checks if not c.passed and not c.skipped]
    assert not report.has_critical_failures(), f"unexpected failures: {failed}"
    assert report.counts()["total"] >= 20


def test_generation_is_reproducible_for_a_seed(cfg):
    stage_normalize(cfg, log=lambda *_: None)
    a = stage_generate_questions(cfg, log=lambda *_: None)
    b = stage_generate_questions(cfg, log=lambda *_: None)
    assert [f.question_family_id for f in a] == [f.question_family_id for f in b]
    assert [f.question for f in a] == [f.question for f in b]
    assert [f.gold_answer_normalized for f in a] == [f.gold_answer_normalized for f in b]


def test_changing_the_seed_changes_the_selection(cfg):
    stage_normalize(cfg, log=lambda *_: None)
    a = stage_generate_questions(cfg, log=lambda *_: None)
    cfg.seed += 977
    cfg.config_hash = cfg.compute_hash()
    b = stage_generate_questions(cfg, log=lambda *_: None)
    assert [f.question for f in a] != [f.question for f in b], \
        "a different seed must select different source records"
    assert {f.question_type for f in a} == {f.question_type for f in b}, \
        "the configured question-type mix must not depend on the seed"


# ---- the validator must actually catch corruption -------------------------------------


def _mutate_instances(cfg, fn):
    rows = [json.loads(l) for l in instances_path(cfg).read_text().splitlines() if l.strip()]
    rows = [fn(r) for r in rows]
    write_jsonl(instances_path(cfg), rows)


def test_validator_catches_a_tampered_gold_answer(built):
    cfg, _ = built
    fams = [json.loads(l) for l in families_path(cfg).read_text().splitlines() if l.strip()]
    for f in fams:
        if f["answerable"] and isinstance(f["gold_answer_normalized"], (int, float)):
            f["gold_answer_normalized"] = float(f["gold_answer_normalized"]) + 999.0
            break
    write_jsonl(families_path(cfg), fams)
    report = run_validation(cfg, log=lambda *_: None)
    assert report.has_critical_failures()
    assert not next(c for c in report.checks if c.check_id == "D").passed


def test_validator_catches_a_broken_nesting_chain(built):
    cfg, _ = built

    def drop_records(row):
        if row["context_length_nominal"] == max(cfg.context.lengths):
            row["context_record_ids"] = row["context_record_ids"][:5]
        return row

    _mutate_instances(cfg, drop_records)
    report = run_validation(cfg, log=lambda *_: None)
    assert not next(c for c in report.checks if c.check_id == "J").passed


def test_validator_catches_a_question_that_drifts_across_variants(built):
    cfg, _ = built

    def drift(row):
        if row["context_length_nominal"] == max(cfg.context.lengths):
            row["question"] = row["question"] + " (reworded)"
        return row

    _mutate_instances(cfg, drift)
    report = run_validation(cfg, log=lambda *_: None)
    assert not next(c for c in report.checks if c.check_id == "G").passed


def test_validator_catches_an_over_length_context(built):
    cfg, _ = built

    def inflate(row):
        row["context_tokens_actual"] = row["context_length_nominal"] + 1
        return row

    _mutate_instances(cfg, inflate)
    report = run_validation(cfg, log=lambda *_: None)
    assert not next(c for c in report.checks if c.check_id == "K").passed


def test_validator_catches_displaced_target_evidence(built):
    cfg, _ = built

    def displace(row):
        if row.get("target_position_relative") is not None:
            row["target_position_relative"] = 0.05
        return row

    _mutate_instances(cfg, displace)
    report = run_validation(cfg, log=lambda *_: None)
    assert not next(c for c in report.checks if c.check_id == "L").passed


def test_validator_catches_a_duplicated_question_family(built):
    cfg, _ = built
    fams = [json.loads(l) for l in families_path(cfg).read_text().splitlines() if l.strip()]
    clone = dict(fams[0])
    clone["question_family_id"] = clone["question_family_id"] + "_COPY"
    write_jsonl(families_path(cfg), fams + [clone])
    report = run_validation(cfg, log=lambda *_: None)
    assert not next(c for c in report.checks if c.check_id == "B").passed


def test_unanswerable_families_are_genuinely_unanswerable(built):
    """Every unanswerable family's target must be absent from the whole record pool."""
    cfg, families = built
    pool, _ = load_pool(cfg)
    unanswerable = [f for f in families if not f.answerable]
    assert unanswerable, "the fixtures should support at least one unanswerable family"
    for fam in unanswerable:
        spec = fam.unanswerable_spec
        assert spec.verified_absent_in_pool
        # Records with a null value are precisely *why* the family is unanswerable --
        # the primary source reports no figure. What must not exist is a record that
        # actually carries a value for the requested coordinates.
        matches = [
            r for r in pool.matches_target(entity_id=spec.missing_entity_id,
                                           concept=spec.missing_concept,
                                           period=spec.missing_period)
            if r.value is not None
        ]
        assert not matches, f"{fam.question_family_id} is answerable after all: {matches[:2]}"
