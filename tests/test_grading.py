import json

from longctx_dataset.grading import (
    ERROR_AMBIGUOUS,
    ERROR_CALCULATION_ERROR,
    ERROR_FAILED_TO_ABSTAIN,
    ERROR_FORMAT_FAILURE,
    ERROR_UNNECESSARY_ABSTENTION,
    ERROR_UNSUPPORTED_VALUE,
    answers_equal,
    evidence_details,
    grade_answer_only_response,
    grade_response,
    normalize_answer,
    parse_model_json,
)
from longctx_dataset.schemas import AnswerType, Domain, DistractorType, Instance, QuestionType


def inst(**overrides):
    base = {
        "instance_id": "T_4K",
        "question_family_id": "T",
        "domain": Domain.SEC,
        "question_type": QuestionType.DIRECT_RETRIEVAL,
        "question": "Q?",
        "context_length_nominal": 4096,
        "context_length_label": "4K",
        "context_tokens_actual": 100,
        "tokenizer": "hf:test",
        "answerable": True,
        "gold_answer": "100",
        "gold_answer_normalized": 100.0,
        "answer_type": AnswerType.NUMERIC,
        "answer_unit": "USD",
        "numeric_tolerance": 0.0,
        "gold_evidence_ids": ["G"],
        "gold_evidence_canonical_ids": ["G"],
        "gold_evidence_display_ids": ["RG"],
        "gold_evidence_display_map": [
            {
                "canonical_record_id": "G",
                "display_id": "RG",
                "equivalent_canonical_ids": ["G"],
                "equivalent_display_ids": ["RG"],
            }
        ],
        "context": '<RECORD id="RG">\nfield: Target [x]\nvalue: 100\n</RECORD>',
        "context_record_ids": ["G"],
        "context_display_ids": ["RG"],
        "display_id_to_record_id": {"RG": "G"},
    }
    base.update(overrides)
    return Instance.model_validate(base)


def result(answer, evidence=None, insufficient=False):
    raw = json.dumps(
        {
            "selected_evidence": [] if evidence is None else evidence,
            "answer": answer,
            "insufficient_evidence": insufficient,
        }
    )
    return {"raw_output_text": raw}


def answer_only(answer):
    return {"raw_output_text": f"ANSWER: {answer}"}


def test_answer_normalization_strings_dates_numbers_percentages():
    assert normalize_answer("  TABLET ", AnswerType.CATEGORICAL).value == "tablet"
    assert normalize_answer("August 9, 2026", AnswerType.DATE).value == "2026-08-09"
    assert normalize_answer("$1,234.00", AnswerType.NUMERIC, "USD").value == 1234.0
    assert normalize_answer("12%", AnswerType.PERCENT).value == 12.0
    assert normalize_answer("24", AnswerType.INTEGER).value == 24


def test_numeric_tolerance_and_calculation_answer():
    gold = normalize_answer(12.35, AnswerType.NUMERIC)
    model = normalize_answer("12.350", AnswerType.NUMERIC)
    assert answers_equal(model, gold, answer_type=AnswerType.NUMERIC, tolerance=0.0)
    model2 = normalize_answer("12.36", AnswerType.NUMERIC)
    assert answers_equal(model2, gold, answer_type=AnswerType.NUMERIC, tolerance=0.02)


def test_correct_evidence_and_equivalent_evidence():
    i = inst(
        gold_evidence_display_map=[
            {
                "canonical_record_id": "G",
                "display_id": "RG",
                "equivalent_canonical_ids": ["G", "GEQ"],
                "equivalent_display_ids": ["RG", "REQ"],
            }
        ],
        context_record_ids=["G", "GEQ"],
        context_display_ids=["RG", "REQ"],
        display_id_to_record_id={"RG": "G", "REQ": "GEQ"},
        context='<RECORD id="RG">\nvalue: 100\n</RECORD>\n<RECORD id="REQ">\nvalue: 100\n</RECORD>',
    )
    assert evidence_details(i, ["REQ"])["evidence_correct"]


def test_wrong_and_nonexistent_evidence():
    i = inst(
        context_record_ids=["G", "D"],
        context_display_ids=["RG", "RD"],
        display_id_to_record_id={"RG": "G", "RD": "D"},
        distractors=[{"record_id": "D", "display_id": "RD", "distractor_type": "WRONG_ENTITY"}],
        context='<RECORD id="RG">\nvalue: 100\n</RECORD>\n<RECORD id="RD">\nvalue: 200\n</RECORD>',
    )
    details = evidence_details(i, ["RD", "NOPE"])
    assert not details["evidence_correct"]
    assert details["unknown_evidence_ids"] == ["NOPE"]
    assert details["distractor_evidence"] == {"RD": "WRONG_ENTITY"}


def test_wrong_period_contextual_answer_is_not_hallucination():
    i = inst(
        context_record_ids=["G", "D"],
        context_display_ids=["RG", "RD"],
        display_id_to_record_id={"RG": "G", "RD": "D"},
        distractors=[{"record_id": "D", "display_id": "RD", "distractor_type": DistractorType.WRONG_PERIOD}],
        context='<RECORD id="RG">\nvalue: 100\n</RECORD>\n<RECORD id="RD">\nvalue: 90\n</RECORD>',
    )
    row = grade_response(i, result("90", ["RD"]))
    assert not row["answer_correct"]
    assert row["error_type"] == "WRONG_PERIOD"
    assert row["hallucination"] is False


def test_wrong_entity_contextual_answer_is_not_hallucination():
    i = inst(
        context_record_ids=["G", "D"],
        context_display_ids=["RG", "RD"],
        display_id_to_record_id={"RG": "G", "RD": "D"},
        distractors=[{"record_id": "D", "display_id": "RD", "distractor_type": DistractorType.WRONG_ENTITY}],
        context='<RECORD id="RG">\nvalue: 100\n</RECORD>\n<RECORD id="RD">\nvalue: 80\n</RECORD>',
    )
    row = grade_response(i, result("80", ["RD"]))
    assert row["error_type"] == "WRONG_ENTITY"
    assert row["hallucination"] is False


def test_wrong_version_contextual_answer_is_not_hallucination():
    i = inst(
        context_record_ids=["G", "D"],
        context_display_ids=["RG", "RD"],
        display_id_to_record_id={"RG": "G", "RD": "D"},
        distractors=[{"record_id": "D", "display_id": "RD", "distractor_type": DistractorType.WRONG_VERSION}],
        context='<RECORD id="RG">\nvalue: 100\n</RECORD>\n<RECORD id="RD">\nvalue: 70\n</RECORD>',
    )
    row = grade_response(i, result("70", ["RD"]))
    assert row["error_type"] == "WRONG_VERSION"
    assert row["hallucination"] is False


def test_unsupported_numeric_answer_is_hallucination():
    row = grade_response(inst(), result("999", ["RG"]))
    assert row["error_type"] == ERROR_UNSUPPORTED_VALUE
    assert row["hallucination"] is True


def test_correct_abstention_and_failed_to_abstain():
    i = inst(
        answerable=False,
        question_type=QuestionType.UNANSWERABLE,
        gold_answer=None,
        gold_answer_normalized="INSUFFICIENT_EVIDENCE",
        answer_type=AnswerType.INSUFFICIENT_EVIDENCE,
        gold_evidence_ids=[],
        gold_evidence_canonical_ids=[],
        gold_evidence_display_ids=[],
        gold_evidence_display_map=[],
    )
    ok = grade_response(i, result("INSUFFICIENT_EVIDENCE", [], True))
    assert ok["answer_correct"]
    assert ok["abstention_correct"]
    bad = grade_response(i, result("123", [], False))
    assert bad["error_type"] == ERROR_FAILED_TO_ABSTAIN
    assert bad["hallucination"] is True


def test_unnecessary_abstention():
    row = grade_response(inst(), result("INSUFFICIENT_EVIDENCE", [], True))
    assert row["error_type"] == ERROR_UNNECESSARY_ABSTENTION
    assert row["hallucination"] is False


def test_malformed_json_format_failure():
    row = grade_response(inst(), {"raw_output_text": '{"selected_evidence": ['})
    assert row["json_valid"] is False
    assert row["error_type"] == ERROR_FORMAT_FAILURE
    assert row["needs_semantic_review"] is True


def test_recovers_json_wrapped_in_code_fence():
    parsed = parse_model_json(
        '```json\n{"selected_evidence":["R1"],"answer":"A","insufficient_evidence":false}\n```'
    )
    assert parsed["json_valid"]
    assert parsed["recovery_success"]
    assert parsed["recovery_method"] == "strip_markdown_json_fence"
    assert parsed["parsed_answer"] == "A"


def test_recovers_json_with_trailing_text():
    parsed = parse_model_json(
        '{"selected_evidence":["R1"],"answer":"A","insufficient_evidence":false}\nDone.'
    )
    assert parsed["json_valid"]
    assert parsed["recovery_success"]
    assert parsed["recovery_method"] == "extract_first_complete_json_object"


def test_recovers_missing_final_structural_closers():
    parsed = parse_model_json(
        '{"selected_evidence":["R1"],"answer":"A","insufficient_evidence":false'
    )
    assert parsed["json_valid"]
    assert parsed["recovery_success"]
    assert parsed["recovery_method"] == "add_missing_structural_closers"
    assert parsed["parsed_insufficient_evidence"] is False


def test_recovers_obvious_json_boolean_case():
    parsed = parse_model_json(
        '{"selected_evidence":["R1"],"answer":"A","insufficient_evidence":False}'
    )
    assert parsed["json_valid"]
    assert parsed["recovery_success"]
    assert parsed["recovery_method"] == "normalize_json_booleans"


def test_rejects_degenerate_truncated_selected_evidence_without_answer():
    raw = '{"selected_evidence":[' + ",".join(['"R123456789A"'] * 70)
    parsed = parse_model_json(raw, generated_tokens_count=512)
    assert parsed["json_valid"] is False
    assert parsed["recovery_success"] is False
    assert parsed["output_truncated"] is True
    assert parsed["degenerate_output"] is True
    assert parsed["malformed_output_pattern"] == "repetitive_truncated_selected_evidence"


def test_answer_only_correct_direct_answer():
    row = grade_answer_only_response(inst(), answer_only("100"))
    assert row["answer_correct"]
    assert row["error_type"] == "CORRECT"
    assert row["hallucination"] is False
    assert row["evidence_correct"] is None


def test_answer_only_normalized_string_answer():
    i = inst(
        gold_answer="TABLET",
        gold_answer_normalized="TABLET",
        answer_type=AnswerType.CATEGORICAL,
        answer_unit=None,
        context='<RECORD id="RG">\nvalue: TABLET\n</RECORD>',
    )
    row = grade_answer_only_response(i, answer_only("  tablet "))
    assert row["answer_correct"]


def test_answer_only_date_answer():
    i = inst(
        gold_answer="2026-08-09",
        gold_answer_normalized="2026-08-09",
        answer_type=AnswerType.DATE,
        answer_unit=None,
        context='<RECORD id="RG">\nvalue: 2026-08-09\n</RECORD>',
    )
    row = grade_answer_only_response(i, answer_only("August 9, 2026"))
    assert row["answer_correct"]


def test_answer_only_numeric_percentage_currency_answers():
    row = grade_answer_only_response(inst(gold_answer="$1,234.00", gold_answer_normalized=1234.0), answer_only("$1,234"))
    assert row["answer_correct"]
    pct = inst(
        gold_answer="12%",
        gold_answer_normalized=12.0,
        answer_type=AnswerType.PERCENT,
        answer_unit="percent",
        context='<RECORD id="RG">\nvalue: 12%\n</RECORD>',
    )
    assert grade_answer_only_response(pct, answer_only("12"))["answer_correct"]


def test_answer_only_correct_calculation():
    i = inst(
        question_type=QuestionType.RETRIEVAL_CALCULATION,
        gold_answer=80,
        gold_answer_normalized=80.0,
        answer_type=AnswerType.INTEGER,
        answer_unit="participants",
        context='<RECORD id="RG">\nvalue: 180\n</RECORD>\n<RECORD id="R2">\nvalue: 100\n</RECORD>',
    )
    row = grade_answer_only_response(i, answer_only("80"))
    assert row["answer_correct"]


def test_answer_only_arithmetic_calculation_error_is_not_hallucination():
    i = inst(
        question_type=QuestionType.RETRIEVAL_CALCULATION,
        gold_answer=12.35,
        gold_answer_normalized=12.35,
        answer_type=AnswerType.NUMERIC,
        answer_unit=None,
        context='<RECORD id="RG">\nvalue: 100\n</RECORD>\n<RECORD id="R2">\nvalue: 8.1\n</RECORD>',
    )
    family = {"calculation_spec": {"raw_result": 12.345, "rounded_result": 12.35, "round_decimals": 2}}
    row = grade_answer_only_response(i, answer_only("12.345"), family=family)
    assert not row["answer_correct"]
    assert row["error_type"] == ERROR_CALCULATION_ERROR
    assert row["hallucination"] is False


def test_answer_only_calculation_operand_value_is_calculation_error_not_review():
    i = inst(
        question_type=QuestionType.RETRIEVAL_CALCULATION,
        gold_answer=80,
        gold_answer_normalized=80.0,
        answer_type=AnswerType.INTEGER,
        answer_unit="participants",
        context='<RECORD id="RG">\nvalue: 180\n</RECORD>\n<RECORD id="R2">\nvalue: 100\n</RECORD>',
    )
    row = grade_answer_only_response(i, answer_only("180"))
    assert row["error_type"] == ERROR_CALCULATION_ERROR
    assert row["hallucination"] is False
    assert row["needs_semantic_review"] is False


def test_answer_only_wrong_period_contextual_answer_is_not_hallucination():
    i = inst(
        context_record_ids=["G", "D"],
        context_display_ids=["RG", "RD"],
        display_id_to_record_id={"RG": "G", "RD": "D"},
        distractors=[{"record_id": "D", "display_id": "RD", "distractor_type": DistractorType.WRONG_PERIOD}],
        context='<RECORD id="RG">\nvalue: 100\n</RECORD>\n<RECORD id="RD">\nvalue: 90\n</RECORD>',
    )
    row = grade_answer_only_response(i, answer_only("90"))
    assert row["error_type"] == "WRONG_PERIOD"
    assert row["hallucination"] is False
    assert row["answer_correct"] is False


def test_answer_only_wrong_entity_contextual_answer_is_not_hallucination():
    i = inst(
        context_record_ids=["G", "D"],
        context_display_ids=["RG", "RD"],
        display_id_to_record_id={"RG": "G", "RD": "D"},
        distractors=[{"record_id": "D", "display_id": "RD", "distractor_type": DistractorType.WRONG_ENTITY}],
        context='<RECORD id="RG">\nvalue: 100\n</RECORD>\n<RECORD id="RD">\nvalue: 80\n</RECORD>',
    )
    row = grade_answer_only_response(i, answer_only("80"))
    assert row["error_type"] == "WRONG_ENTITY"
    assert row["hallucination"] is False


def test_answer_only_wrong_version_contextual_answer_is_not_hallucination():
    i = inst(
        context_record_ids=["G", "D"],
        context_display_ids=["RG", "RD"],
        display_id_to_record_id={"RG": "G", "RD": "D"},
        distractors=[{"record_id": "D", "display_id": "RD", "distractor_type": DistractorType.WRONG_VERSION}],
        context='<RECORD id="RG">\nvalue: 100\n</RECORD>\n<RECORD id="RD">\nvalue: 70\n</RECORD>',
    )
    row = grade_answer_only_response(i, answer_only("70"))
    assert row["error_type"] == "WRONG_VERSION"
    assert row["hallucination"] is False


def test_answer_only_wrong_series_variant_contextual_answer_is_not_hallucination():
    i = inst(
        context_record_ids=["G", "D"],
        context_display_ids=["RG", "RD"],
        display_id_to_record_id={"RG": "G", "RD": "D"},
        distractors=[{"record_id": "D", "display_id": "RD", "distractor_type": DistractorType.WRONG_SERIES_VARIANT}],
        context='<RECORD id="RG">\nvalue: 100\n</RECORD>\n<RECORD id="RD">\nvalue: 60\n</RECORD>',
    )
    row = grade_answer_only_response(i, answer_only("60"))
    assert row["error_type"] == "WRONG_SERIES_VARIANT"
    assert row["hallucination"] is False


def test_answer_only_unsupported_answers_are_hallucinations():
    row = grade_answer_only_response(inst(), answer_only("999"))
    assert row["error_type"] == ERROR_UNSUPPORTED_VALUE
    assert row["hallucination"] is True
    text = inst(
        gold_answer="TABLET",
        gold_answer_normalized="TABLET",
        answer_type=AnswerType.CATEGORICAL,
        answer_unit=None,
        context='<RECORD id="RG">\nvalue: TABLET\n</RECORD>',
    )
    row2 = grade_answer_only_response(text, answer_only("CAPSULE"))
    assert row2["error_type"] == ERROR_UNSUPPORTED_VALUE
    assert row2["hallucination"] is True


def test_answer_only_abstention_cases():
    unanswerable = inst(
        answerable=False,
        question_type=QuestionType.UNANSWERABLE,
        gold_answer=None,
        gold_answer_normalized="INSUFFICIENT_EVIDENCE",
        answer_type=AnswerType.INSUFFICIENT_EVIDENCE,
        gold_evidence_ids=[],
        gold_evidence_canonical_ids=[],
        gold_evidence_display_ids=[],
        gold_evidence_display_map=[],
    )
    ok = grade_answer_only_response(unanswerable, answer_only("INSUFFICIENT_EVIDENCE"))
    assert ok["answer_correct"]
    assert ok["abstention_correct"]
    assert ok["hallucination"] is False
    bad = grade_answer_only_response(unanswerable, answer_only("123"))
    assert bad["error_type"] == ERROR_FAILED_TO_ABSTAIN
    assert bad["hallucination"] is True
    unnecessary = grade_answer_only_response(inst(), answer_only("INSUFFICIENT_EVIDENCE"))
    assert unnecessary["error_type"] == ERROR_UNNECESSARY_ABSTENTION
    assert unnecessary["hallucination"] is False


def test_answer_only_context_value_without_taxonomy_requires_review():
    i = inst(
        context='<RECORD id="RG">\nvalue: 100\n</RECORD>\n<RECORD id="R2">\nvalue: 55\n</RECORD>',
        context_display_ids=["RG", "R2"],
        display_id_to_record_id={"RG": "G", "R2": "U"},
    )
    row = grade_answer_only_response(i, answer_only("55"))
    assert row["error_type"] == ERROR_AMBIGUOUS
    assert row["needs_semantic_review"] is True
    assert row["hallucination"] is False
