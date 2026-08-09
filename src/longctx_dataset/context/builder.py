"""Nested context construction.

The experiment varies exactly one thing: how much same-domain material surrounds the
gold evidence. Everything in this module exists to keep that true.

Nesting
    All lengths draw from *one* ordered candidate list per family. A longer context is
    the shorter context plus more records, appended at the two ends. Concretely, the
    record sequence of C4K is a subsequence of C8K's, which is a subsequence of C16K's,
    and so on -- not merely a subset, because new records are only ever prepended before
    the existing head or appended after the existing tail.

Target placement
    Growth alternates sides based on which side currently holds fewer tokens, which
    keeps the gold block near the configured relative position (default 0.50) at every
    length without re-drawing anything.

Honesty about length
    A variant is emitted only if it reaches ``min_fill_ratio`` of its nominal target
    using real records. When the authentic pool runs out, the variant is recorded as
    UNAVAILABLE with the token count actually achieved. Nothing is ever padded.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from ..config import PipelineConfig
from ..distractors.selector import DistractorCandidate, DistractorSelector
from ..normalize.common import RecordPool
from ..schemas import (
    ContextStats,
    DistractorRef,
    DistractorType,
    Instance,
    NormalizedRecord,
    QuestionFamily,
    UnavailableVariant,
)
from .tokenizer import Tokenizer


def length_label(nominal: int) -> str:
    """4096 -> '4K', 131072 -> '128K'. Used in instance IDs."""
    if nominal % 1024 == 0:
        return f"{nominal // 1024}K"
    return str(nominal)


BALANCE_WINDOW = 8
"""How far ahead the builder may look for a record that balances the two sides better.

Picking a nearby candidate out of order is safe for nesting -- records are only ever
prepended before the current head or appended after the current tail, so previously
placed records never move relative to each other. The pay-off is a tighter target
position, which matters most at short lengths where one record is a large fraction of
the whole context.
"""


@dataclass
class _GrowthState:
    """Mutable state carried across lengths; this is what makes contexts nest."""

    before_rev: List[int] = field(default_factory=list)  # candidate indices, nearest-first
    after: List[int] = field(default_factory=list)
    tokens_before: int = 0
    tokens_after: int = 0
    pending: List[int] = field(default_factory=list)     # candidate indices not yet placed


class ContextBuilder:
    """Builds every context variant of one question family."""

    def __init__(self, cfg: PipelineConfig, pool: RecordPool, tokenizer: Tokenizer):
        self.cfg = cfg
        self.pool = pool
        self.tok = tokenizer
        self.selector = DistractorSelector(cfg, pool)
        self.sep = cfg.context.record_separator
        self._sep_tokens = self.tok.count(self.sep) if self.sep else 0
        self._render_cache: Dict[str, str] = {}
        self._token_cache: Dict[str, int] = {}
        # Enough candidates to fill the largest target even with very small records.
        self._candidate_limit = max(cfg.context.lengths) // 24 + 256

    # ---- rendering ------------------------------------------------------------------

    def render_record(self, rec: NormalizedRecord) -> str:
        """One record as a delimited block with a stable, citable ID.

        Machine-readable boundaries are required: the eventual experiment asks the model
        to cite the record IDs it used, which is only possible if the context is not
        anonymous prose.
        """
        cached = self._render_cache.get(rec.record_id)
        if cached is not None:
            return cached

        open_tag = self.cfg.context.record_open_template.format(
            record_id=rec.record_id, source=rec.source
        )
        lines = [open_tag, f"entity: {rec.entity_name} [{rec.entity_id}]"]
        concept_line = f"field: {rec.concept_label} [{rec.concept}]"
        lines.append(concept_line)
        if rec.period:
            lines.append(f"period: {rec.period}")
        if rec.unit:
            lines.append(f"unit: {rec.unit}")
        lines.append(f"value: {rec.value}")
        if rec.version:
            lines.append(f"version: {rec.version}")
        extra = self._extra_lines(rec)
        lines.extend(extra)
        lines.append(self.cfg.context.record_close)
        text = "\n".join(lines)
        self._render_cache[rec.record_id] = text
        return text

    @staticmethod
    def _extra_lines(rec: NormalizedRecord) -> List[str]:
        """A few high-signal, domain-specific fields that make records realistic.

        Kept deliberately short: these are the attributes a reader would actually use to
        tell two near-duplicate records apart (form type, arm label, dosage form), not a
        dump of the whole metadata blob.
        """
        md = rec.metadata
        out: List[str] = []
        for key, label in (
            ("form", "form"), ("accn", "accession"), ("fy", "fiscal_year"), ("fp", "fiscal_period"),
            ("arm_label", "arm"), ("outcome_measure", "outcome"), ("intervention_name", "intervention"),
            ("dosage_form", "dosage_form"), ("route", "route"), ("sponsor_name", "sponsor"),
            ("submission_type", "submission_type"), ("overall_status", "status"),
        ):
            val = md.get(key)
            if val not in (None, "", [], {}):
                out.append(f"{label}: {val}")
            if len(out) >= 4:
                break
        return out

    def token_count(self, rec: NormalizedRecord) -> int:
        cached = self._token_cache.get(rec.record_id)
        if cached is None:
            cached = self.tok.count(self.render_record(rec))
            self._token_cache[rec.record_id] = cached
        return cached

    # ---- building -------------------------------------------------------------------

    def build_family(self, family: QuestionFamily) -> Tuple[List[Instance], List[UnavailableVariant]]:
        gold_records = [self.pool.get(rid) for rid in family.gold_evidence_ids]
        missing = [rid for rid, rec in zip(family.gold_evidence_ids, gold_records) if rec is None]
        if missing:
            raise KeyError(
                f"{family.question_family_id}: gold evidence not found in the normalized pool: {missing}. "
                "Regenerate question families against the current normalized layer."
            )
        gold_records = [r for r in gold_records if r is not None]

        # Rendered once and reused verbatim at every length -- the byte-for-byte
        # identity of the gold block across variants is the invariant the study rests on.
        gold_parts = [self.render_record(r) for r in gold_records]
        gold_block = self.sep.join(gold_parts)
        gold_tokens = self.tok.count(gold_block) if gold_block else 0

        candidates = self.selector.build(family, limit=self._candidate_limit)
        cand_tokens = [self.token_count(c.record) + self._sep_tokens for c in candidates]

        state = _GrowthState(pending=list(range(len(candidates))))
        instances: List[Instance] = []
        unavailable: List[UnavailableVariant] = []
        prev_instance_id: Optional[str] = None
        prev_ids: List[str] = []
        exhausted_at: Optional[int] = None

        for nominal in self.cfg.context.lengths:
            if exhausted_at is not None:
                unavailable.append(self._unavailable(
                    family, nominal, "POOL_EXHAUSTED",
                    f"The authentic same-domain record pool was already exhausted at "
                    f"{length_label(exhausted_at)} ({len(candidates)} candidate records available); "
                    f"reaching {length_label(nominal)} would require padding, which this pipeline "
                    f"does not do.",
                    tokens_achieved=None, records_available=len(candidates),
                ))
                continue

            self._grow(state, candidates, cand_tokens, gold_tokens, nominal)
            parts, ids, sides = self._assemble(state, candidates, gold_parts, gold_records)
            text = self.sep.join(parts)
            actual = self.tok.count(text)

            # Exact measurement can differ slightly from the per-record estimate; trim
            # rather than ever exceed the nominal target.
            while actual > nominal and (state.before_rev or state.after):
                self._shrink_one(state, cand_tokens)
                parts, ids, sides = self._assemble(state, candidates, gold_parts, gold_records)
                text = self.sep.join(parts)
                actual = self.tok.count(text)

            fill = actual / nominal if nominal else 0.0
            if fill < self.cfg.context.min_fill_ratio:
                exhausted_at = nominal
                unavailable.append(self._unavailable(
                    family, nominal, "POOL_EXHAUSTED",
                    f"Only {actual} tokens of authentic same-domain records could be assembled "
                    f"({fill:.1%} of the {nominal}-token target, below the configured minimum fill "
                    f"ratio of {self.cfg.context.min_fill_ratio:.0%}). "
                    f"{len(candidates)} candidate records were available after excluding gold evidence "
                    f"and answer-leaking records. No filler was added.",
                    tokens_achieved=actual, records_available=len(candidates),
                ))
                continue

            instance = self._make_instance(
                family, nominal, actual, text, parts, ids, sides, candidates,
                gold_records, gold_block, gold_tokens, state, prev_instance_id, prev_ids,
            )

            # At very short targets a single record can be a large fraction of the whole
            # context, so the configured position tolerance is not always reachable. That
            # is a property of the length, not a defect to be papered over: the variant is
            # recorded as unavailable rather than emitted out of spec, which keeps the
            # target-position invariant absolute for everything that *is* emitted.
            if instance.stats is not None and instance.stats.target_position_ok is False:
                unavailable.append(self._unavailable(
                    family, nominal, "POSITION_TOLERANCE_UNSATISFIABLE",
                    f"Gold evidence landed at relative position "
                    f"{instance.target_position_relative:.4f}, outside the configured "
                    f"{self.cfg.context.target_position:.2f} +/- "
                    f"{self.cfg.context.position_tolerance:.2f}. Only "
                    f"{len(ids)} records fit in {nominal} tokens, so no placement of whole "
                    f"records puts the evidence closer to the target depth.",
                    tokens_achieved=actual, records_available=len(candidates),
                ))
                continue

            instances.append(instance)
            prev_instance_id = instance.instance_id
            prev_ids = ids

        return instances, unavailable

    # ---- growth mechanics -----------------------------------------------------------

    def _grow(self, state: _GrowthState, candidates: List[DistractorCandidate],
              cand_tokens: List[int], gold_tokens: int, nominal: int) -> None:
        """Extend the current context toward ``nominal``, keeping the gold block centred.

        Records go to whichever side currently holds fewer tokens, which is exactly the
        condition for the gold block's midpoint to sit at 50%. Within a small look-ahead
        window the builder prefers the candidate whose size leaves the two sides most
        evenly matched, so the residual offset stays well inside tolerance instead of
        being bounded by the size of whichever record happened to come next.
        """
        while state.pending:
            total = gold_tokens + state.tokens_before + state.tokens_after
            budget = nominal - total
            window = state.pending[:BALANCE_WINDOW]
            affordable = [i for i in window if cand_tokens[i] <= budget]
            if not affordable:
                # Nothing in the window fits; if nothing at all fits, growth is done.
                if all(cand_tokens[i] > budget for i in state.pending):
                    break
                # Otherwise advance past the oversized head and retry.
                state.pending = [i for i in state.pending if cand_tokens[i] <= budget] or []
                if not state.pending:
                    break
                continue

            to_before = state.tokens_before <= state.tokens_after
            deficit = abs(state.tokens_after - state.tokens_before)
            # Prefer the candidate that best closes the gap between the two sides.
            pick = min(affordable, key=lambda i: (abs(cand_tokens[i] - deficit), i))
            state.pending.remove(pick)
            if to_before:
                state.before_rev.append(pick)
                state.tokens_before += cand_tokens[pick]
            else:
                state.after.append(pick)
                state.tokens_after += cand_tokens[pick]

    def _shrink_one(self, state: _GrowthState, cand_tokens: List[int]) -> None:
        """Remove the most recently added record from the heavier side."""
        if state.tokens_before >= state.tokens_after and state.before_rev:
            idx = state.before_rev.pop()
            state.tokens_before -= cand_tokens[idx]
        elif state.after:
            idx = state.after.pop()
            state.tokens_after -= cand_tokens[idx]
        elif state.before_rev:
            idx = state.before_rev.pop()
            state.tokens_before -= cand_tokens[idx]
        else:
            return
        state.pending.insert(0, idx)

    def _assemble(self, state: _GrowthState, candidates: List[DistractorCandidate],
                  gold_parts: List[str], gold_records: List[NormalizedRecord]
                  ) -> Tuple[List[str], List[str], List[str]]:
        """Materialize the record sequence: before (outermost first), gold, after."""
        before_idx = list(reversed(state.before_rev))
        parts: List[str] = []
        ids: List[str] = []
        sides: List[str] = []
        for i in before_idx:
            parts.append(self.render_record(candidates[i].record))
            ids.append(candidates[i].record.record_id)
            sides.append("before")
        for part, rec in zip(gold_parts, gold_records):
            parts.append(part)
            ids.append(rec.record_id)
            sides.append("gold")
        for i in state.after:
            parts.append(self.render_record(candidates[i].record))
            ids.append(candidates[i].record.record_id)
            sides.append("after")
        return parts, ids, sides

    # ---- instance assembly ----------------------------------------------------------

    def _make_instance(
        self, family: QuestionFamily, nominal: int, actual: int, text: str,
        parts: List[str], ids: List[str], sides: List[str],
        candidates: List[DistractorCandidate], gold_records: List[NormalizedRecord],
        gold_block: str, gold_tokens: int, state: _GrowthState,
        prev_instance_id: Optional[str], prev_ids: List[str],
    ) -> Instance:
        by_id = {c.record.record_id: c for c in candidates}
        distractors: List[DistractorRef] = []
        counts: Dict[str, int] = {t.value: 0 for t in DistractorType}
        for pos, (rid, side) in enumerate(zip(ids, sides)):
            if side == "gold":
                continue
            cand = by_id[rid]
            counts[cand.distractor_type.value] += 1
            distractors.append(DistractorRef(
                record_id=rid,
                distractor_type=cand.distractor_type,
                relationship_to_target=cand.relationship,
                position_index=pos,
                side=side,
            ))

        start = end = rel = None
        pos_ok = None
        if gold_records:
            n_before = sides.count("before")
            prefix = self.sep.join(parts[:n_before])
            start = self.tok.count(prefix + self.sep) if n_before else 0
            end = start + gold_tokens
            rel = ((start + end) / 2.0) / actual if actual else None
            if rel is not None:
                pos_ok = abs(rel - self.cfg.context.target_position) <= self.cfg.context.position_tolerance

        stats = ContextStats(
            context_length_nominal=nominal,
            context_tokens_actual=actual,
            fill_ratio=actual / nominal if nominal else 0.0,
            tokenizer_id=self.tok.tokenizer_id,
            tokenizer_version=self.tok.version,
            n_records_total=len(ids),
            n_records_before_target=sides.count("before"),
            n_records_after_target=sides.count("after"),
            target_evidence_start_token=start,
            target_evidence_end_token=end,
            target_position_relative=rel,
            target_position_tolerance=self.cfg.context.position_tolerance,
            target_position_ok=pos_ok,
        )

        return Instance(
            instance_id=f"{family.question_family_id}_{length_label(nominal)}",
            question_family_id=family.question_family_id,
            domain=family.domain,
            question_type=family.question_type,
            question=family.question,
            context_length_nominal=nominal,
            context_tokens_actual=actual,
            tokenizer=self.tok.tokenizer_id,
            tokenizer_version=self.tok.version,
            target_evidence_start_token=start,
            target_evidence_end_token=end,
            target_position_relative=rel,
            answerable=family.answerable,
            gold_answer=family.gold_answer,
            gold_answer_normalized=family.gold_answer_normalized,
            answer_type=family.answer_type,
            answer_unit=family.answer_unit,
            numeric_tolerance=family.numeric_tolerance,
            gold_evidence_ids=list(family.gold_evidence_ids),
            distractor_counts={k: v for k, v in counts.items() if v},
            distractors=distractors,
            context=text,
            context_record_ids=ids,
            context_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            lineage={
                "extends_instance_id": prev_instance_id,
                "extends_n_records": len(prev_ids),
                "added_record_ids": [r for r in ids if r not in set(prev_ids)],
                "gold_block_sha256": hashlib.sha256(gold_block.encode("utf-8")).hexdigest(),
            },
            stats=stats,
            source_provenance=list(family.source_provenance),
            generation_metadata=family.generation_metadata,
        )

    def _unavailable(self, family: QuestionFamily, nominal: int, code: str, reason: str,
                     tokens_achieved: Optional[int], records_available: int) -> UnavailableVariant:
        return UnavailableVariant(
            question_family_id=family.question_family_id,
            domain=family.domain,
            context_length_nominal=nominal,
            reason_code=code,
            reason=reason,
            tokens_achieved=tokens_achieved,
            records_available=records_available,
        )
