"""Deterministic grading utilities for raw model responses.

This module intentionally avoids semantic judging. When exact deterministic rules are
not enough, it marks the row for human review instead of guessing.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Sequence

from .inference import parse_response_json
from .schemas import AnswerType, INSUFFICIENT_EVIDENCE, Instance, QuestionType


ERROR_CORRECT = "CORRECT"
ERROR_FORMAT_FAILURE = "FORMAT_FAILURE"
ERROR_WRONG_EVIDENCE = "WRONG_EVIDENCE"
ERROR_UNSUPPORTED_VALUE = "UNSUPPORTED_VALUE"
ERROR_FAILED_TO_ABSTAIN = "FAILED_TO_ABSTAIN"
ERROR_UNNECESSARY_ABSTENTION = "UNNECESSARY_ABSTENTION"
ERROR_CALCULATION_ERROR = "CALCULATION_ERROR"
ERROR_OTHER = "OTHER"
ERROR_AMBIGUOUS = "AMBIGUOUS_REVIEW_REQUIRED"

DISTRACTOR_ERROR_TYPES = {
    "WRONG_ENTITY",
    "WRONG_PERIOD",
    "WRONG_VERSION",
    "WRONG_FIELD",
    "WRONG_UNIT",
    "WRONG_SERIES_VARIANT",
}


@dataclass(frozen=True)
class NormalizedAnswer:
    kind: str
    value: Any
    raw: Any


_RECORD_RE = re.compile(r'<RECORD id="([^"]+)"[^>]*>(.*?)</RECORD>', re.S)
_LINE_RE = re.compile(r"^([^:\n]+):\s*(.*)$")
_ANSWER_LINE_RE = re.compile(r"^\s*ANSWER:\s*(.*?)\s*$", re.S)


def parse_context_records(context: str) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for match in _RECORD_RE.finditer(context):
        display_id = match.group(1)
        body = match.group(2)
        fields: dict[str, Any] = {"display_id": display_id, "body": body}
        for line in body.splitlines():
            m = _LINE_RE.match(line.strip())
            if m:
                fields[m.group(1).strip().lower()] = m.group(2).strip()
        records[display_id] = fields
    return records


def parse_model_json(raw_output_text: str | None, *, generated_tokens_count: int | None = None) -> dict[str, Any]:
    raw = raw_output_text or ""
    recovery = recover_model_json(raw, generated_tokens_count=generated_tokens_count)
    if recovery["parsed"] is not None:
        parsed_obj = recovery["parsed"]
        return {
            "strict_json_valid": recovery["strict_json_valid"],
            "json_valid": True,
            "recovery_attempted": recovery["recovery_attempted"],
            "recovery_success": recovery["recovery_success"],
            "recovery_method": recovery["recovery_method"],
            "malformed_output_pattern": recovery["malformed_output_pattern"],
            "output_truncated": recovery["output_truncated"],
            "degenerate_output": recovery["degenerate_output"],
            "parse_confidence": recovery["parse_confidence"],
            "parse_failure_reason": None,
            "parsed_selected_evidence": parsed_obj.get("selected_evidence"),
            "parsed_answer": parsed_obj.get("answer"),
            "parsed_insufficient_evidence": parsed_obj.get("insufficient_evidence"),
        }

    parsed = parse_response_json(raw)
    return {
        "strict_json_valid": False,
        "json_valid": bool(parsed["json_parse_success"]),
        "recovery_attempted": recovery["recovery_attempted"],
        "recovery_success": False,
        "recovery_method": recovery["recovery_method"],
        "malformed_output_pattern": recovery["malformed_output_pattern"],
        "output_truncated": recovery["output_truncated"],
        "degenerate_output": recovery["degenerate_output"],
        "parse_confidence": recovery["parse_confidence"],
        "parse_failure_reason": recovery["parse_failure_reason"],
        "parsed_selected_evidence": parsed["parsed_selected_evidence"],
        "parsed_answer": parsed["parsed_answer"],
        "parsed_insufficient_evidence": parsed["parsed_insufficient_evidence"],
    }


def parse_answer_only_output(raw_output_text: str | None) -> dict[str, Any]:
    """Parse Experiment C's answer-only response contract.

    The raw output is never repaired. A response is usable only when it contains a
    single ``ANSWER:`` prefix and a non-empty answer payload after it.
    """

    raw = raw_output_text or ""
    match = _ANSWER_LINE_RE.match(raw)
    parsed = match.group(1).strip() if match else None
    return {
        "answer_line_valid": bool(match and parsed),
        "parsed_answer": parsed if parsed else None,
        "parse_failure_reason": None if match and parsed else "missing non-empty ANSWER: line",
    }


def recover_model_json(raw: str, *, generated_tokens_count: int | None = None) -> dict[str, Any]:
    text = raw.strip()
    output_truncated = generated_tokens_count == 512
    degenerate = _degenerate_output(text)
    base = {
        "strict_json_valid": False,
        "recovery_attempted": False,
        "recovery_success": False,
        "recovery_method": None,
        "malformed_output_pattern": "empty_output" if not text else "unknown_malformed_json",
        "output_truncated": output_truncated,
        "degenerate_output": degenerate,
        "parse_confidence": "none",
        "parse_failure_reason": None,
        "parsed": None,
    }
    if not text:
        base["parse_failure_reason"] = "empty output"
        return base

    try:
        parsed = json.loads(text)
        if _valid_response_shape(parsed):
            return {
                **base,
                "strict_json_valid": True,
                "malformed_output_pattern": "valid_json",
                "parse_confidence": "strict",
                "parsed": parsed,
            }
    except json.JSONDecodeError:
        pass

    base["recovery_attempted"] = True
    if degenerate:
        base["malformed_output_pattern"] = (
            "repetitive_truncated_selected_evidence"
            if output_truncated else "repetitive_degenerate_generation"
        )
        base["parse_failure_reason"] = "degenerate repeated evidence IDs; required fields are incomplete"
        return base

    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.S | re.I)
    if fence:
        parsed = _loads_response(fence.group(1).strip())
        if parsed is not None:
            return {
                **base,
                "recovery_success": True,
                "recovery_method": "strip_markdown_json_fence",
                "malformed_output_pattern": "json_wrapped_in_code_fence",
                "parse_confidence": "high",
                "parsed": parsed,
            }

    extracted = _extract_first_complete_object(text)
    if extracted is not None and extracted != text:
        parsed = _loads_response(extracted)
        if parsed is not None:
            return {
                **base,
                "recovery_success": True,
                "recovery_method": "extract_first_complete_json_object",
                "malformed_output_pattern": "valid_json_object_with_surrounding_text",
                "parse_confidence": "high",
                "parsed": parsed,
            }

    normalized = _normalize_json_literals(text)
    if normalized != text:
        parsed = _loads_response(normalized)
        if parsed is not None:
            return {
                **base,
                "recovery_success": True,
                "recovery_method": "normalize_json_booleans",
                "malformed_output_pattern": "obvious_json_boolean_case",
                "parse_confidence": "high",
                "parsed": parsed,
            }

    balanced = _balance_complete_response(text)
    if balanced is not None:
        parsed = _loads_response(balanced)
        if parsed is not None:
            return {
                **base,
                "recovery_success": True,
                "recovery_method": "add_missing_structural_closers",
                "malformed_output_pattern": "missing_final_structural_closers",
                "parse_confidence": "medium",
                "parsed": parsed,
            }

    if output_truncated:
        base["malformed_output_pattern"] = "partially_truncated_json"
    base["parse_failure_reason"] = "no unambiguous complete response object with all required fields"
    return base


def normalize_answer(value: Any, answer_type: AnswerType | str, unit: str | None = None) -> NormalizedAnswer:
    at = AnswerType(answer_type)
    if value is None:
        return NormalizedAnswer(at.value, None, value)
    if at is AnswerType.INSUFFICIENT_EVIDENCE:
        text = _norm_text(value)
        return NormalizedAnswer(at.value, INSUFFICIENT_EVIDENCE if text == "insufficient_evidence" else text, value)
    if isinstance(value, str) and _norm_text(value) == "insufficient_evidence":
        return NormalizedAnswer("INSUFFICIENT_EVIDENCE", INSUFFICIENT_EVIDENCE, value)
    if at in {AnswerType.NUMERIC, AnswerType.PERCENT, AnswerType.INTEGER}:
        num = _to_decimal(value)
        if num is None:
            return NormalizedAnswer(at.value, None, value)
        if at is AnswerType.PERCENT:
            # Metadata stores percent answers on the same scale as source values. A
            # literal "12%" and "12" normalize identically; no 0.12 <-> 12 conversion.
            pass
        if at is AnswerType.INTEGER and num == num.to_integral_value():
            return NormalizedAnswer(at.value, int(num), value)
        return NormalizedAnswer(at.value, float(num), value)
    if at is AnswerType.DATE:
        parsed = _to_date(value)
        return NormalizedAnswer(at.value, parsed.isoformat() if parsed else _norm_text(value), value)
    return NormalizedAnswer(at.value, _norm_text(value), value)


def answers_equal(
    model: NormalizedAnswer,
    gold: NormalizedAnswer,
    *,
    answer_type: AnswerType | str,
    tolerance: float | None,
) -> bool:
    if model.value is None:
        return False
    if model.value == INSUFFICIENT_EVIDENCE or gold.value == INSUFFICIENT_EVIDENCE:
        return model.value == gold.value
    at = AnswerType(answer_type)
    if at in {AnswerType.NUMERIC, AnswerType.PERCENT, AnswerType.INTEGER}:
        try:
            mv = float(model.value)
            gv = float(gold.value)
        except (TypeError, ValueError):
            return False
        tol = float(tolerance or 0.0)
        return math.isclose(mv, gv, rel_tol=0.0, abs_tol=tol)
    return model.value == gold.value


def valid_evidence_sets(inst: Instance) -> list[set[str]]:
    if inst.gold_evidence_display_map:
        return [
            {x for x in [m.display_id, *m.equivalent_display_ids] if x}
            for m in inst.gold_evidence_display_map
        ]
    return [{display_id} for display_id in inst.gold_evidence_display_ids]


def evidence_details(inst: Instance, selected: Any) -> dict[str, Any]:
    selected_list = selected if isinstance(selected, list) else []
    selected_ids = [x for x in selected_list if isinstance(x, str)]
    valid_by_gold = valid_evidence_sets(inst)
    known = set(inst.context_display_ids)
    valid_all = set().union(*valid_by_gold) if valid_by_gold else set()
    matched_by_gold = [
        sorted(group.intersection(selected_ids))
        for group in valid_by_gold
    ]
    missing_gold_groups = [
        idx for idx, matches in enumerate(matched_by_gold) if not matches
    ]
    extra = [x for x in selected_ids if x not in valid_all]
    unknown = [x for x in selected_ids if x not in known]
    distractor_ids = {d.display_id: d.distractor_type.value for d in inst.distractors if d.display_id}
    distractors = {x: distractor_ids[x] for x in selected_ids if x in distractor_ids}
    if not inst.answerable:
        correct = selected_ids == []
    else:
        correct = bool(valid_by_gold) and not missing_gold_groups and not extra and not unknown
    return {
        "selected_evidence": selected_ids,
        "valid_evidence_by_gold_record": [sorted(g) for g in valid_by_gold],
        "matched_by_gold_record": matched_by_gold,
        "missing_gold_group_indexes": missing_gold_groups,
        "extra_evidence_ids": extra,
        "unknown_evidence_ids": unknown,
        "distractor_evidence": distractors,
        "evidence_correct": correct,
    }


def match_context_value(inst: Instance, normalized_model: NormalizedAnswer) -> dict[str, Any] | None:
    if normalized_model.value in (None, INSUFFICIENT_EVIDENCE):
        return None
    records = parse_context_records(inst.context)
    distractor_by_display = {d.display_id: d.distractor_type.value for d in inst.distractors if d.display_id}
    gold_displays = set(inst.gold_evidence_display_ids)
    for display_id, fields in records.items():
        raw_value = fields.get("value")
        if raw_value is None:
            continue
        rec_norm = normalize_answer(raw_value, inst.answer_type, inst.answer_unit)
        if answers_equal(rec_norm, normalized_model, answer_type=inst.answer_type, tolerance=inst.numeric_tolerance):
            return {
                "display_id": display_id,
                "canonical_record_id": inst.display_id_to_record_id.get(display_id),
                "is_gold_or_equivalent": display_id in gold_displays,
                "distractor_type": distractor_by_display.get(display_id),
                "record_value": raw_value,
            }
    return None


def grade_response(inst: Instance, result_row: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_model_json(
        result_row.get("raw_output_text"),
        generated_tokens_count=result_row.get("generated_tokens_count"),
    )
    base = {
        "instance_id": inst.instance_id,
        "question_family_id": inst.question_family_id,
        "domain": inst.domain.value,
        "question_type": inst.question_type.value,
        "context_length_label": inst.context_length_label,
        "answerable": inst.answerable,
        "gold_answer": inst.gold_answer,
        "gold_answer_normalized": inst.gold_answer_normalized,
        "gold_evidence_ids": inst.gold_evidence_ids,
        "gold_evidence_display_ids": inst.gold_evidence_display_ids,
        "equivalent_evidence_ids": [g.display_ids for g in inst.gold_evidence_equivalence_groups],
        "raw_output_text": result_row.get("raw_output_text"),
        "parsed_answer": parsed["parsed_answer"],
        "parsed_selected_evidence": parsed["parsed_selected_evidence"],
        "parsed_insufficient_evidence": parsed["parsed_insufficient_evidence"],
        "strict_json_valid": parsed["strict_json_valid"],
        "recovery_attempted": parsed["recovery_attempted"],
        "recovery_success": parsed["recovery_success"],
        "recovery_method": parsed["recovery_method"],
        "malformed_output_pattern": parsed["malformed_output_pattern"],
        "output_truncated": parsed["output_truncated"],
        "degenerate_output": parsed["degenerate_output"],
        "parse_confidence": parsed["parse_confidence"],
        "parse_failure_reason": parsed["parse_failure_reason"],
    }
    timing = {
        key: result_row.get(key)
        for key in [
            "generation_latency_seconds",
            "input_tokens",
            "generated_tokens_count",
            "generated_tokens_per_second",
            "peak_allocated_vram_bytes",
            "peak_reserved_vram_bytes",
            "execution_order_index",
        ]
        if key in result_row
    }
    base.update(timing)

    if not parsed["json_valid"]:
        base.update(
            {
                "json_valid": False,
                "answer_correct": False,
                "evidence_correct": False,
                "abstention_correct": False if not inst.answerable else None,
                "hallucination": None,
                "error_type": ERROR_FORMAT_FAILURE,
                "needs_semantic_review": True,
                "review_reason": parsed["parse_failure_reason"] or "model output is not parseable JSON; raw output preserved",
                "normalized_gold_answer": normalize_answer(inst.gold_answer_normalized, inst.answer_type, inst.answer_unit).value,
                "normalized_model_answer": None,
                "matched_context_record": None,
                "matched_distractor_type": None,
                "evidence_match_details": evidence_details(inst, parsed["parsed_selected_evidence"]),
                "grading_rule_used": "json_parse_failure",
            }
        )
        return base

    gold_norm = normalize_answer(inst.gold_answer_normalized, inst.answer_type, inst.answer_unit)
    model_norm = normalize_answer(parsed["parsed_answer"], inst.answer_type, inst.answer_unit)
    insufficient_flag = parsed["parsed_insufficient_evidence"] is True or model_norm.value == INSUFFICIENT_EVIDENCE
    ev = evidence_details(inst, parsed["parsed_selected_evidence"])
    answer_correct = answers_equal(
        model_norm,
        gold_norm,
        answer_type=inst.answer_type,
        tolerance=inst.numeric_tolerance,
    )
    abstention_correct = None
    if inst.answerable:
        abstention_correct = not insufficient_flag
    else:
        abstention_correct = insufficient_flag and parsed["parsed_answer"] == INSUFFICIENT_EVIDENCE
        answer_correct = bool(abstention_correct)

    matched = match_context_value(inst, model_norm)
    error_type = ERROR_OTHER
    hallucination: bool | None = False
    needs_review = False
    review_reason = ""
    rule = "deterministic_exact"

    if answer_correct and ev["evidence_correct"]:
        error_type = ERROR_CORRECT
    elif inst.answerable and insufficient_flag:
        error_type = ERROR_UNNECESSARY_ABSTENTION
        hallucination = False
    elif not inst.answerable and not insufficient_flag:
        error_type = ERROR_FAILED_TO_ABSTAIN
        hallucination = matched is None
        if matched is not None:
            rule = "failed_to_abstain_but_value_present_in_context"
        else:
            rule = "failed_to_abstain_unsupported_value"
    elif not answer_correct:
        if matched and matched.get("distractor_type") in DISTRACTOR_ERROR_TYPES:
            error_type = matched["distractor_type"]
            hallucination = False
            rule = "model_answer_matches_context_distractor_value"
        elif matched:
            error_type = ERROR_CALCULATION_ERROR if inst.question_type.value == "RETRIEVAL_CALCULATION" else ERROR_OTHER
            hallucination = False
            needs_review = error_type == ERROR_OTHER
            review_reason = "answer value appears in context but deterministic distractor type is unavailable"
            rule = "model_answer_matches_context_value"
        else:
            error_type = ERROR_UNSUPPORTED_VALUE
            hallucination = True
            rule = "model_answer_not_matched_to_context_value"
    elif answer_correct and not ev["evidence_correct"]:
        error_type = ERROR_WRONG_EVIDENCE
        hallucination = False
        rule = "answer_correct_evidence_incorrect"

    if error_type == ERROR_OTHER and not review_reason:
        needs_review = True
        review_reason = "deterministic rules did not produce a specific error taxonomy"

    base.update(
        {
            "json_valid": True,
            "answer_correct": bool(answer_correct),
            "evidence_correct": bool(ev["evidence_correct"]),
            "abstention_correct": abstention_correct,
            "hallucination": hallucination,
            "error_type": error_type,
            "needs_semantic_review": needs_review,
            "review_reason": review_reason,
            "normalized_gold_answer": gold_norm.value,
            "normalized_model_answer": model_norm.value,
            "matched_context_record": matched,
            "matched_distractor_type": matched.get("distractor_type") if matched else None,
            "evidence_match_details": ev,
            "grading_rule_used": rule,
        }
    )
    return base


def grade_answer_only_response(
    inst: Instance,
    result_row: dict[str, Any],
    *,
    family: Any | None = None,
) -> dict[str, Any]:
    """Grade Experiment C answer-only outputs without evidence-selection scoring."""

    parsed = parse_answer_only_output(result_row.get("raw_output_text"))
    base = _base_answer_only_row(inst, result_row, parsed)
    gold_norm = normalize_answer(inst.gold_answer_normalized, inst.answer_type, inst.answer_unit)

    if not parsed["answer_line_valid"]:
        base.update(
            {
                "answer_correct": False,
                "abstention_correct": False if not inst.answerable else None,
                "hallucination": None,
                "error_type": ERROR_FORMAT_FAILURE,
                "needs_semantic_review": True,
                "review_reason": parsed["parse_failure_reason"],
                "normalized_gold_answer": gold_norm.value,
                "normalized_model_answer": None,
                "matched_context_value": None,
                "matched_context_record": None,
                "matched_distractor_type": None,
                "grading_rule_used": "answer_line_parse_failure",
            }
        )
        return base

    model_norm = normalize_answer(parsed["parsed_answer"], inst.answer_type, inst.answer_unit)
    insufficient_answer = model_norm.value == INSUFFICIENT_EVIDENCE
    answer_correct = answers_equal(
        model_norm,
        gold_norm,
        answer_type=inst.answer_type,
        tolerance=inst.numeric_tolerance,
    )
    abstention_correct = None
    if inst.answerable:
        abstention_correct = not insufficient_answer
    else:
        abstention_correct = insufficient_answer
        answer_correct = bool(abstention_correct)

    matched = match_context_value(inst, model_norm)
    calc_match = _calculation_alternate_match(model_norm, inst, family)

    error_type = ERROR_OTHER
    hallucination: bool | None = False
    needs_review = False
    review_reason = ""
    rule = "answer_only_exact_match"

    if answer_correct:
        error_type = ERROR_CORRECT
    elif inst.answerable and insufficient_answer:
        error_type = ERROR_UNNECESSARY_ABSTENTION
        hallucination = False
        rule = "answerable_instance_unnecessary_abstention"
    elif not inst.answerable and not insufficient_answer:
        error_type = ERROR_FAILED_TO_ABSTAIN
        hallucination = True
        rule = "unanswerable_instance_factual_answer"
    elif matched and matched.get("distractor_type") in DISTRACTOR_ERROR_TYPES:
        error_type = matched["distractor_type"]
        hallucination = False
        rule = "answer_matches_context_distractor_value"
    elif calc_match is not None:
        error_type = ERROR_CALCULATION_ERROR
        hallucination = False
        matched = calc_match
        rule = "calculation_answer_matches_unrounded_or_alternate_rounding"
    elif matched and inst.question_type is QuestionType.RETRIEVAL_CALCULATION:
        error_type = ERROR_CALCULATION_ERROR
        hallucination = False
        rule = "calculation_answer_matches_context_operand_or_value"
    elif matched:
        error_type = ERROR_AMBIGUOUS
        hallucination = False
        needs_review = True
        review_reason = "answer value appears in context but deterministic distractor type is unavailable"
        rule = "answer_matches_context_value_without_taxonomy"
    else:
        error_type = ERROR_UNSUPPORTED_VALUE
        hallucination = True
        rule = "answer_not_matched_to_context_value"

    base.update(
        {
            "answer_correct": bool(answer_correct),
            "abstention_correct": abstention_correct,
            "hallucination": hallucination,
            "error_type": error_type,
            "needs_semantic_review": needs_review,
            "review_reason": review_reason,
            "normalized_gold_answer": gold_norm.value,
            "normalized_model_answer": model_norm.value,
            "matched_context_value": matched.get("record_value") if matched else None,
            "matched_context_record": matched,
            "matched_distractor_type": matched.get("distractor_type") if matched else None,
            "grading_rule_used": rule,
        }
    )
    return base


def _base_answer_only_row(
    inst: Instance,
    result_row: dict[str, Any],
    parsed: dict[str, Any],
) -> dict[str, Any]:
    row = {
        "instance_id": inst.instance_id,
        "question_family_id": inst.question_family_id,
        "domain": inst.domain.value,
        "question_type": inst.question_type.value,
        "context_length_label": inst.context_length_label,
        "answerable": inst.answerable,
        "question": inst.question,
        "gold_answer": inst.gold_answer,
        "gold_answer_normalized": inst.gold_answer_normalized,
        "gold_evidence_ids": inst.gold_evidence_ids,
        "gold_evidence_display_ids": inst.gold_evidence_display_ids,
        "raw_output_text": result_row.get("raw_output_text"),
        "parsed_answer": parsed["parsed_answer"],
        "answer_line_valid": parsed["answer_line_valid"],
        "parse_failure_reason": parsed["parse_failure_reason"],
        "evidence_correct": None,
        "parsed_selected_evidence": None,
    }
    timing = {
        key: result_row.get(key)
        for key in [
            "generation_latency_seconds",
            "input_tokens",
            "generated_tokens_count",
            "generated_tokens_per_second",
            "peak_allocated_vram_bytes",
            "peak_reserved_vram_bytes",
            "execution_order_index",
        ]
        if key in result_row
    }
    row.update(timing)
    return row


def _calculation_alternate_match(
    normalized_model: NormalizedAnswer,
    inst: Instance,
    family: Any | None,
) -> dict[str, Any] | None:
    if normalized_model.value in (None, INSUFFICIENT_EVIDENCE):
        return None
    if inst.question_type is not QuestionType.RETRIEVAL_CALCULATION:
        return None
    spec = _get_calculation_spec(family)
    if spec is None:
        return None
    try:
        model_value = float(normalized_model.value)
    except (TypeError, ValueError):
        return None

    candidates: list[tuple[str, float]] = []
    raw_result = _spec_get(spec, "raw_result")
    rounded_result = _spec_get(spec, "rounded_result")
    round_decimals = _spec_get(spec, "round_decimals")
    if raw_result is not None:
        candidates.append(("raw_result", float(raw_result)))
    if rounded_result is not None:
        candidates.append(("rounded_result", float(rounded_result)))
    if raw_result is not None and isinstance(round_decimals, int):
        for decimals in range(max(0, round_decimals - 2), round_decimals + 3):
            candidates.append((f"raw_result_rounded_{decimals}", round(float(raw_result), decimals)))

    gold_value = float(normalize_answer(inst.gold_answer_normalized, inst.answer_type, inst.answer_unit).value)
    tolerance = float(inst.numeric_tolerance or 0.0)
    for label, candidate in candidates:
        if math.isclose(candidate, gold_value, rel_tol=0.0, abs_tol=tolerance):
            continue
        if math.isclose(model_value, candidate, rel_tol=0.0, abs_tol=tolerance):
            return {
                "display_id": None,
                "canonical_record_id": None,
                "is_gold_or_equivalent": False,
                "distractor_type": None,
                "record_value": candidate,
                "calculation_alternate": label,
            }
    return None


def _get_calculation_spec(family: Any | None) -> Any | None:
    if family is None:
        return None
    if isinstance(family, dict):
        return family.get("calculation_spec")
    return getattr(family, "calculation_spec", None)


def _spec_get(spec: Any, key: str) -> Any:
    if isinstance(spec, dict):
        return spec.get(key)
    return getattr(spec, key, None)


def _norm_text(value: Any) -> str:
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return text.casefold()


def _valid_response_shape(parsed: Any) -> bool:
    return (
        isinstance(parsed, dict)
        and set(["selected_evidence", "answer", "insufficient_evidence"]).issubset(parsed)
        and isinstance(parsed.get("selected_evidence"), list)
        and isinstance(parsed.get("insufficient_evidence"), bool)
    )


def _loads_response(text: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if _valid_response_shape(parsed) else None


def _extract_first_complete_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start: idx + 1]
    return None


def _normalize_json_literals(text: str) -> str:
    normalized = re.sub(r":\s*True\b", ": true", text)
    normalized = re.sub(r":\s*False\b", ": false", normalized)
    normalized = re.sub(r":\s*None\b", ": null", normalized)
    return normalized


def _balance_complete_response(text: str) -> str | None:
    required = ['"selected_evidence"', '"answer"', '"insufficient_evidence"']
    if not all(k in text for k in required):
        return None
    if _ends_inside_string(text):
        return None
    stack: list[str] = []
    in_string = False
    escape = False
    for ch in text:
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch in "[{":
            stack.append("]" if ch == "[" else "}")
        elif ch in "]}":
            if not stack or stack[-1] != ch:
                return None
            stack.pop()
    if len(stack) > 3:
        return None
    return text + "".join(reversed(stack))


def _ends_inside_string(text: str) -> bool:
    in_string = False
    escape = False
    for ch in text:
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
    return in_string


def _degenerate_output(text: str) -> bool:
    ids = re.findall(r'"(R[A-Z0-9]{8,12})"', text)
    if len(ids) < 20:
        return False
    counts: dict[str, int] = {}
    for rid in ids:
        counts[rid] = counts.get(rid, 0) + 1
    return max(counts.values(), default=0) >= 12 or len(ids) >= 60


def _to_decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    text = str(value).strip()
    text = text.replace(",", "")
    text = re.sub(r"^\$", "", text)
    text = re.sub(r"%$", "", text)
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _to_date(value: Any) -> date | None:
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None
