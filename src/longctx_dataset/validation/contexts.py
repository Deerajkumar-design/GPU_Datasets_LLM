"""Context-level structural validation.

These checks defend the properties that make the length variable interpretable:
the contexts nest, the gold block survives intact and centred, and the record
boundaries the eventual experiment relies on for citation are well-formed.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..schemas import Instance, QuestionFamily

_OPEN_RE = re.compile(r'<RECORD id="([^"]+)"[^>]*>')
_CLOSE_TOKEN = "</RECORD>"


def check_record_boundaries(instance: Instance) -> List[str]:
    """Open/close tags must balance and match the declared record-id sequence exactly."""
    problems: List[str] = []
    opens = _OPEN_RE.findall(instance.context)
    n_close = instance.context.count(_CLOSE_TOKEN)

    if len(opens) != n_close:
        problems.append(f"{len(opens)} <RECORD> open tags vs {n_close} {_CLOSE_TOKEN} close tags")
    declared_display = instance.context_display_ids or instance.context_record_ids
    if len(opens) != len(declared_display):
        problems.append(
            f"{len(opens)} rendered records vs {len(declared_display)} declared context_display_ids"
        )
    if opens != list(declared_display):
        first_bad = next(
            (i for i, (a, b) in enumerate(zip(opens, declared_display)) if a != b), None
        )
        problems.append(
            "rendered record-id sequence differs from context_display_ids"
            + (f" (first difference at index {first_bad})" if first_bad is not None else "")
        )
    dupes = {r for r in opens if opens.count(r) > 1} if len(opens) < 5000 else set()
    if dupes:
        problems.append(f"duplicate record IDs rendered into one context: {sorted(dupes)[:5]}")
    return problems


def check_no_truncation(instance: Instance, gold_blocks: Dict[str, str]) -> List[str]:
    """The full rendered text of each gold record must appear intact in the context.

    Presence of the ID is not enough: a context truncated mid-record would still show the
    opening tag while losing the value line, which is exactly the corruption that would
    turn an answerable item into a silently unanswerable one.
    """
    problems: List[str] = []
    if not instance.answerable:
        return problems
    for rid in instance.gold_evidence_ids:
        block = gold_blocks.get(rid)
        if block is None:
            problems.append(f"no rendered gold block available for {rid} (cannot verify integrity)")
            continue
        if instance.context.count(block) != 1:
            problems.append(
                f"gold record {rid} does not appear exactly once as an intact block "
                f"(found {instance.context.count(block)} occurrences)"
            )
    return problems


def is_subsequence(shorter: Sequence[str], longer: Sequence[str]) -> bool:
    """True when ``shorter`` appears inside ``longer`` in order (gaps allowed)."""
    it = iter(longer)
    return all(any(x == y for y in it) for x in shorter)


def check_nesting(variants: List[Instance]) -> List[str]:
    """C4K subset of C8K subset of ... verified as an ordered subsequence.

    Subsequence rather than mere set inclusion: the builder only ever prepends before the
    current head or appends after the current tail, so preserved records must also keep
    their relative order. Checking the stronger property catches a whole class of
    "regenerated independently" bugs that a set check would miss.
    """
    problems: List[str] = []
    ordered = sorted(variants, key=lambda i: i.context_length_nominal)
    for shorter, longer in zip(ordered, ordered[1:]):
        s_ids, l_ids = shorter.context_record_ids, longer.context_record_ids
        missing = set(s_ids) - set(l_ids)
        if missing:
            problems.append(
                f"{shorter.instance_id} -> {longer.instance_id}: {len(missing)} records dropped when "
                f"growing (e.g. {sorted(missing)[:3]}); contexts are not nested"
            )
            continue
        if not is_subsequence(s_ids, l_ids):
            problems.append(
                f"{shorter.instance_id} -> {longer.instance_id}: records are a subset but their "
                "relative order changed; nesting requires an ordered subsequence"
            )
        if len(l_ids) <= len(s_ids):
            problems.append(
                f"{shorter.instance_id} ({len(s_ids)} records) -> {longer.instance_id} "
                f"({len(l_ids)} records): longer variant did not grow"
            )
        declared = longer.lineage.get("extends_instance_id")
        if declared != shorter.instance_id:
            problems.append(
                f"{longer.instance_id} declares lineage parent {declared!r}, expected "
                f"{shorter.instance_id!r}"
            )
    return problems


def check_token_compliance(instance: Instance, min_fill_ratio: float) -> List[str]:
    """Actual length must never exceed nominal, and must be honestly close to it."""
    problems: List[str] = []
    nominal, actual = instance.context_length_nominal, instance.context_tokens_actual
    if actual > nominal:
        problems.append(f"context is {actual} tokens, exceeding its {nominal}-token target")
    ratio = actual / nominal if nominal else 0.0
    if ratio < min_fill_ratio:
        problems.append(
            f"context reached only {actual} tokens ({ratio:.1%} of {nominal}); a variant this far "
            f"below target must be recorded as unavailable, not emitted"
        )
    return problems


def check_target_position(instance: Instance, target: float, tolerance: float) -> List[str]:
    """Gold evidence must sit at the configured relative depth (default ~50%)."""
    if not instance.answerable:
        return []
    rel = instance.target_position_relative
    if rel is None:
        return ["answerable instance has no measured target position"]
    if abs(rel - target) > tolerance:
        return [f"target position {rel:.4f} is outside {target:.2f} +/- {tolerance:.2f}"]
    start, end = instance.target_evidence_start_token, instance.target_evidence_end_token
    if start is None or end is None or end <= start:
        return [f"invalid target evidence token span: start={start} end={end}"]
    if end > instance.context_tokens_actual:
        return [
            f"target evidence ends at token {end}, past the end of a "
            f"{instance.context_tokens_actual}-token context (evidence would be truncated)"
        ]
    return []


def check_variant_invariants(family: QuestionFamily, variants: List[Instance]) -> Dict[str, List[str]]:
    """Question, gold answer and gold evidence must be identical across all lengths."""
    out: Dict[str, List[str]] = {"question": [], "answer": [], "evidence": []}
    for inst in variants:
        if inst.question != family.question:
            out["question"].append(
                f"{inst.instance_id}: question text differs from its family"
            )
        if inst.gold_answer != family.gold_answer or (
            inst.gold_answer_normalized != family.gold_answer_normalized
        ):
            out["answer"].append(
                f"{inst.instance_id}: gold answer {inst.gold_answer!r}/"
                f"{inst.gold_answer_normalized!r} differs from family "
                f"{family.gold_answer!r}/{family.gold_answer_normalized!r}"
            )
        if list(inst.gold_evidence_ids) != list(family.gold_evidence_ids):
            out["evidence"].append(
                f"{inst.instance_id}: gold evidence IDs differ from its family"
            )
    questions = {i.question for i in variants}
    if len(questions) > 1:
        out["question"].append(f"{family.question_family_id}: {len(questions)} distinct question texts across variants")
    answers = {(str(i.gold_answer), str(i.gold_answer_normalized)) for i in variants}
    if len(answers) > 1:
        out["answer"].append(f"{family.question_family_id}: {len(answers)} distinct gold answers across variants")
    evidence = {tuple(i.gold_evidence_ids) for i in variants}
    if len(evidence) > 1:
        out["evidence"].append(
            f"{family.question_family_id}: {len(evidence)} distinct gold evidence sets across variants"
        )
    gold_hashes = {i.lineage.get("gold_block_sha256") for i in variants}
    if len(gold_hashes) > 1:
        out["evidence"].append(
            f"{family.question_family_id}: gold evidence block is not byte-identical across variants "
            f"({len(gold_hashes)} distinct hashes)"
        )
    return out
