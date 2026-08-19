"""Question-template guards against explicit distractor hints."""

from __future__ import annotations

from pathlib import Path

from longctx_dataset.prompts import EVALUATION_PROMPT_VERSION, load_evaluation_prompt
from longctx_dataset.validation.question_leakage import answerability_leakage_phrases


FORBIDDEN_PROMPT_SNIPPETS = [
    "not the answer",
    "those are not the answer",
    "is not the answer",
    "none of which is",
    "context also contains",
    "also has arms labelled",
    "different strengths (",
    "earlier filing",
    "later vintages report",
    "state that the evidence is insufficient",
    "do not infer",
    "cannot be determined",
]


def test_question_templates_do_not_embed_explicit_foil_hints():
    root = Path("src/longctx_dataset/questions")
    offenders = []
    for path in sorted(root.glob("*_templates.py")):
        text = path.read_text(encoding="utf-8").lower()
        for snippet in FORBIDDEN_PROMPT_SNIPPETS:
            if snippet in text:
                offenders.append(f"{path}:{snippet}")
    assert offenders == []


def test_answerability_leakage_checker_flags_abstention_only_phrases():
    assert answerability_leakage_phrases(
        "What is the date? If the supplied records do not contain it, state insufficient evidence."
    )
    assert answerability_leakage_phrases("Do not infer it from another date or another trial.")
    assert answerability_leakage_phrases("If missing, return INSUFFICIENT_EVIDENCE.")
    assert answerability_leakage_phrases("The answer cannot be determined from the context.")


def test_answerability_leakage_checker_allows_ordinary_factual_questions():
    question = (
        "Using only the ClinicalTrials.gov records supplied in the context, what is the date "
        "on which results were first posted for trial NCT02339493?"
    )
    assert answerability_leakage_phrases(question) == []


def test_common_evaluation_prompt_contains_uniform_abstention_instruction():
    prompt = load_evaluation_prompt()
    assert EVALUATION_PROMPT_VERSION == "evaluation_v1"
    assert "INSUFFICIENT_EVIDENCE" in prompt
    assert "Do not infer or fabricate" in prompt
    assert "answerable" not in prompt.lower()
    assert "{answerable" not in prompt


def test_fda_strength_binding_keeps_required_target_conditions():
    text = Path("src/longctx_dataset/questions/fda_templates.py").read_text(encoding="utf-8")
    assert "product number" in text
    assert "under FDA application" in text
    assert "dosage form" in text
    assert "route" in text
    assert "record_conditions(target, STRENGTH_KEYS)" in text
