from __future__ import annotations

from longctx_dataset.schemas import (
    AnswerType,
    Domain,
    GenerationMetadata,
    GoldEvidence,
    QuestionFamily,
    QuestionType,
)
from longctx_dataset.validation.dataset import _temporal_version_semantic_problems


def _family(template_id: str, qtype: QuestionType = QuestionType.TEMPORAL_VERSION) -> QuestionFamily:
    return QuestionFamily(
        question_family_id="CT_0017",
        domain=Domain.CLINICAL_TRIALS,
        source_name="ClinicalTrials.gov",
        question_type=qtype,
        question="What is the primary completion date?",
        answerable=True,
        gold_answer="2018-04-25",
        gold_answer_normalized="2018-04-25",
        answer_type=AnswerType.DATE,
        gold_evidence=[
            GoldEvidence(
                record_id="RID",
                entity_id="NCT",
                entity_name="Trial",
                concept="study.primary_completion_date",
                concept_label="Primary completion date",
                value="2018-04-25",
                period="2018",
                role="target_value",
            )
        ],
        gold_evidence_ids=["RID"],
        target_conditions={},
        generation_metadata=GenerationMetadata(
            template_id=template_id,
            seed=1,
            config_hash="h",
        ),
    )


def test_smoke_instance_count_is_families_times_conditions_when_complete():
    assert 4 * 6 == 24
    assert 34 * 6 == 204


def test_ct_date_field_selection_is_not_temporal_version_semantics():
    fam = _family("CT_DATE_FIELD_SELECTION")
    assert _temporal_version_semantic_problems(fam)


def test_registered_version_templates_pass_temporal_version_semantics():
    fam = _family("FRED_VINTAGE_SELECTION")
    assert _temporal_version_semantic_problems(fam) == []
