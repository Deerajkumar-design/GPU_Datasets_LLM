"""Leakage detection.

Two distinct failure modes are covered:

Unanswerable leakage
    A family declared unanswerable stops measuring abstention the moment any context
    variant contains a record that would answer it. This checks the rendered record set
    of every variant against the family's target conditions and its declared forbidden
    concept aliases.

Answerable duplication
    An answerable family should have exactly one source of truth in the context. A second
    record satisfying the same target conditions makes "which record did the model use"
    unanswerable, and can make a wrong-looking answer actually defensible.

Both operate on normalized records rather than on raw text, so the checks are exact
rather than string-matching heuristics.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Sequence

from ..distractors.taxonomy import condition_satisfied_by
from ..normalize.common import RecordPool
from ..schemas import QuestionFamily


def _conditions(family: QuestionFamily) -> List[Dict[str, Any]]:
    return list(family.target_conditions.get("records") or [])


def check_unanswerable_leakage(
    family: QuestionFamily,
    context_record_ids: Sequence[str],
    pool: RecordPool,
) -> List[str]:
    """Any record in this context that would disclose the withheld answer."""
    if family.answerable:
        return []
    problems: List[str] = []
    spec = family.unanswerable_spec
    aliases = set(spec.forbidden_concept_aliases or []) if spec else set()
    if spec and spec.missing_concept:
        aliases.add(spec.missing_concept)
    target_entity = spec.missing_entity_id if spec else None
    # Mirrors DistractorSelector.forbidden_record_ids: an alias concept only leaks when
    # it is for the same entity *and* the period the question names (or any period, when
    # the question names none because the entity never reports that concept).
    target_period = spec.missing_period if spec else None
    conditions = _conditions(family)

    for rid in context_record_ids:
        rec = pool.get(rid)
        if rec is None:
            problems.append(f"context record {rid} is not in the normalized pool")
            continue
        for cond in conditions:
            if condition_satisfied_by(rec, cond):
                problems.append(
                    f"record {rid} ({rec.concept} / {rec.entity_id} / {rec.period}) satisfies the "
                    f"target conditions of an unanswerable family and would disclose the answer"
                )
                break
        else:
            if (
                aliases
                and rec.concept in aliases
                and (target_entity is None or rec.entity_id == target_entity)
                and (target_period is None or rec.period == target_period)
            ):
                problems.append(
                    f"record {rid} uses forbidden concept alias {rec.concept!r} for the target entity "
                    f"{rec.entity_id}, which would disclose the withheld answer"
                )
    return problems


def check_answerable_duplication(
    family: QuestionFamily,
    context_record_ids: Sequence[str],
    pool: RecordPool,
) -> List[str]:
    """A second record answering the same question makes the gold answer ambiguous."""
    if not family.answerable:
        return []
    problems: List[str] = []
    gold = set(family.gold_evidence_ids)
    for cond in _conditions(family):
        matches = []
        for rid in context_record_ids:
            if rid in gold:
                continue
            rec = pool.get(rid)
            if rec is not None and condition_satisfied_by(rec, cond):
                matches.append(rid)
        if matches:
            problems.append(
                f"non-gold records {matches[:5]} also satisfy target condition "
                f"{ {k: v for k, v in cond.items() if k != 'entity_name'} }"
            )
    return problems


def check_gold_present(
    family: QuestionFamily, context_record_ids: Sequence[str]
) -> List[str]:
    """Every gold evidence record must be present in every answerable context."""
    if not family.answerable:
        return []
    present = set(context_record_ids)
    missing = [rid for rid in family.gold_evidence_ids if rid not in present]
    return (
        [f"gold evidence missing from context: {missing}"] if missing else []
    )


def check_gold_absent(
    family: QuestionFamily, context_record_ids: Sequence[str]
) -> List[str]:
    """Unanswerable families must carry no gold evidence into any context."""
    if family.answerable:
        return []
    present = set(context_record_ids) & set(family.gold_evidence_ids)
    return [f"unanswerable family has gold evidence in context: {sorted(present)}"] if present else []
