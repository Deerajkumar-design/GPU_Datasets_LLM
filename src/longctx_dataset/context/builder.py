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
from ..evidence import build_equivalence_groups
from ..normalize.common import RecordPool
from ..prompt_renderer import LLAMA_PROMPT_VERSION, RESPONSE_FORMAT_VERSION, PromptRenderer
from ..schemas import (
    ContextStats,
    DistractorRef,
    DistractorType,
    GoldEvidenceDisplayMapping,
    Instance,
    NormalizedRecord,
    QuestionFamily,
    UnavailableVariant,
)
from .display_ids import DisplayIdMapper
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
        self.display_ids = DisplayIdMapper(cfg, pool.records)
        # Enough candidates to fill the largest target even with very small records.
        self._candidate_limit = max(cfg.context.lengths) // 24 + 256
        self.prompt_renderer = PromptRenderer(cfg, tokenizer) if cfg.model.id else None
        self._model_context_limit = tokenizer.model_context_limit if cfg.model.id else None
        self._input_token_budget: Optional[int] = None
        if cfg.model.id:
            if self._model_context_limit is None:
                raise ValueError(f"{tokenizer.tokenizer_id} did not expose a model context limit")
            self._input_token_budget = self._model_context_limit - cfg.model.max_new_tokens
            if cfg.model_prompt.max_rendered_input_tokens is not None:
                self._input_token_budget = min(
                    self._input_token_budget,
                    cfg.model_prompt.max_rendered_input_tokens,
                )
            if self._input_token_budget <= 0:
                raise ValueError(
                    f"generation reserve {cfg.model.max_new_tokens} leaves no input budget "
                    f"inside context limit {self._model_context_limit}"
                )

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

        display_id = self.display_ids.display_id(rec.record_id)
        open_tag = self.cfg.context.record_open_template.format(record_id=display_id, source=rec.source)
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

            rendered_tokens = self._rendered_input_tokens(text, family.question)
            while (
                self._input_token_budget is not None
                and rendered_tokens is not None
                and rendered_tokens > self._input_token_budget
                and (state.before_rev or state.after)
            ):
                self._shrink_one(state, cand_tokens)
                parts, ids, sides = self._assemble(state, candidates, gold_parts, gold_records)
                text = self.sep.join(parts)
                actual = self.tok.count(text)
                rendered_tokens = self._rendered_input_tokens(text, family.question)

            if (
                self._input_token_budget is not None
                and rendered_tokens is not None
                and rendered_tokens > self._input_token_budget
            ):
                exhausted_at = nominal
                unavailable.append(self._unavailable(
                    family, nominal, "PROMPT_BUDGET_EXCEEDED",
                    f"The gold/context prompt alone required {rendered_tokens} rendered input "
                    f"tokens, exceeding the safe input budget of {self._input_token_budget} "
                    f"after reserving {self.cfg.model.max_new_tokens} generation tokens. "
                    "No records were truncated.",
                    tokens_achieved=actual, records_available=len(candidates),
                ))
                continue

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
                rendered_tokens,
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

    def _rendered_input_tokens(self, context: str, question: str) -> Optional[int]:
        if self.prompt_renderer is None:
            return None
        return self.prompt_renderer.render(context=context, question=question).token_count

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
                # Nothing in the window fits the remaining budget. Reach past it for the
                # next candidate that does -- but never drop the oversized ones, because
                # a record too large for this length will fit comfortably at the next.
                nxt = next((i for i in state.pending if cand_tokens[i] <= budget), None)
                if nxt is None:
                    break
                affordable = [nxt]

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
        rendered_tokens: Optional[int],
    ) -> Instance:
        by_id = {c.record.record_id: c for c in candidates}
        distractors: List[DistractorRef] = []
        counts: Dict[str, int] = {t.value: 0 for t in DistractorType}
        display_ids = [self.display_ids.display_id(rid) for rid in ids]
        display_map = {did: rid for did, rid in zip(display_ids, ids)}
        canonical_to_display = {rid: did for did, rid in zip(display_ids, ids)}
        for pos, (rid, side) in enumerate(zip(ids, sides)):
            if side == "gold":
                continue
            cand = by_id[rid]
            counts[cand.distractor_type.value] += 1
            distractors.append(DistractorRef(
                record_id=rid,
                display_id=self.display_ids.display_id(rid),
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

        context_label = length_label(nominal)
        near_model_maximum = nominal == max(self.cfg.context.lengths)
        prompt_overhead = (
            rendered_tokens - actual
            if rendered_tokens is not None
            else None
        )
        remaining_margin = (
            self._input_token_budget - rendered_tokens
            if self._input_token_budget is not None and rendered_tokens is not None
            else None
        )
        prompt_version = prompt_hash = response_version = None
        if self.prompt_renderer is not None:
            prompt_version = LLAMA_PROMPT_VERSION
            prompt_hash = self.prompt_renderer.prompt_hash
            response_version = RESPONSE_FORMAT_VERSION

        stats = ContextStats(
            context_length_nominal=nominal,
            context_length_label=context_label,
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
            rendered_input_tokens_actual=rendered_tokens,
            prompt_overhead_tokens=prompt_overhead,
            generation_tokens_reserved=self.cfg.model.max_new_tokens if self.cfg.model.id else None,
            model_context_limit=self._model_context_limit,
            remaining_context_margin=remaining_margin,
            near_model_maximum=near_model_maximum,
        )

        context_records = [self.pool.get(rid) for rid in ids]
        equivalence_groups = build_equivalence_groups(
            family,
            [r for r in context_records if r is not None],
            canonical_to_display,
        )
        gold_display_ids = [self.display_ids.display_id(rid) for rid in family.gold_evidence_ids]
        eq_by_gold = {g.gold_record_id: g for g in equivalence_groups}
        gold_display_map = []
        for rid in family.gold_evidence_ids:
            group = eq_by_gold.get(rid)
            gold_display_map.append(GoldEvidenceDisplayMapping(
                canonical_record_id=rid,
                display_id=canonical_to_display.get(rid),
                equivalent_canonical_ids=list(group.canonical_record_ids) if group else [rid],
                equivalent_display_ids=list(group.display_ids) if group else [canonical_to_display[rid]],
            ))

        return Instance(
            instance_id=f"{family.question_family_id}_{length_label(nominal)}",
            question_family_id=family.question_family_id,
            domain=family.domain,
            question_type=family.question_type,
            question=family.question,
            context_length_nominal=nominal,
            context_length_label=context_label,
            context_tokens_actual=actual,
            tokenizer=self.tok.tokenizer_id,
            tokenizer_version=self.tok.version,
            tokenizer_revision=self.tok.tokenizer_revision,
            tokenizer_class=self.tok.tokenizer_class,
            model_id=self.cfg.model.id,
            model_config_revision=self.tok.model_config_revision,
            rendered_input_tokens_actual=rendered_tokens,
            prompt_overhead_tokens=prompt_overhead,
            generation_tokens_reserved=self.cfg.model.max_new_tokens if self.cfg.model.id else None,
            model_context_limit=self._model_context_limit,
            remaining_context_margin=remaining_margin,
            near_model_maximum=near_model_maximum,
            prompt_version=prompt_version,
            prompt_hash=prompt_hash,
            response_format_version=response_version,
            target_evidence_start_token=start,
            target_evidence_end_token=end,
            target_position_relative=rel,
            target_position_relative_in_records_context=rel,
            target_position_relative_in_rendered_input=None,
            answerable=family.answerable,
            gold_answer=family.gold_answer,
            gold_answer_normalized=family.gold_answer_normalized,
            answer_type=family.answer_type,
            answer_unit=family.answer_unit,
            numeric_tolerance=family.numeric_tolerance,
            gold_evidence_ids=list(family.gold_evidence_ids),
            gold_evidence_display_ids=gold_display_ids,
            gold_evidence_canonical_ids=list(family.gold_evidence_ids),
            gold_evidence_equivalence_groups=equivalence_groups,
            gold_evidence_display_map=gold_display_map,
            distractor_counts={k: v for k, v in counts.items() if v},
            distractors=distractors,
            context=text,
            context_record_ids=ids,
            context_display_ids=display_ids,
            display_id_to_record_id=display_map,
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
