"""Distractor selection.

Produces one deterministically ordered candidate list per question family. The order is
the backbone of context nesting: every length takes a growing prefix of the same list,
so C4K's records are always a subset of C8K's, and so on up to 128K.

Two exclusions are absolute and enforced here rather than left to the validator:

* no record that would itself satisfy the question's target conditions (that would give
  a second, unlabelled source of the answer);
* for unanswerable families, no record matching the missing concept or any declared
  alias for the target entity (that would silently make the question answerable).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set

from ..config import PipelineConfig
from ..normalize.common import RecordPool
from ..questions.base import rng_for
from ..schemas import DistractorType, NormalizedRecord, QuestionFamily
from .taxonomy import TIER_WEIGHTS, DISTRACTOR_TIERS, classify_distractor, condition_satisfied_by


@dataclass
class DistractorCandidate:
    record: NormalizedRecord
    distractor_type: DistractorType
    relationship: Dict[str, bool]


class DistractorSelector:
    """Builds the ordered, deduplicated distractor sequence for one family."""

    # Records that carry no value are never rendered: a null observation would be both
    # uninformative as interference and confusing as apparent evidence.
    NON_RENDERABLE_RECORD_TYPES = {"observation_missing"}

    def __init__(self, cfg: PipelineConfig, pool: RecordPool):
        self.cfg = cfg
        self.pool = pool

    # ---- exclusions -----------------------------------------------------------------

    def forbidden_record_ids(self, family: QuestionFamily) -> Set[str]:
        """Every record that must never appear as a distractor for this family."""
        forbidden: Set[str] = set(family.gold_evidence_ids)
        conditions = family.target_conditions.get("records") or []
        domain_records = self.pool.domain_records(family.domain)

        for rec in domain_records:
            if any(condition_satisfied_by(rec, cond) for cond in conditions):
                forbidden.add(rec.record_id)

        spec = family.unanswerable_spec
        if spec is not None:
            aliases = set(spec.forbidden_concept_aliases or [])
            if spec.missing_concept:
                aliases.add(spec.missing_concept)
            for rec in domain_records:
                if rec.concept not in aliases:
                    continue
                if spec.missing_entity_id is not None and rec.entity_id != spec.missing_entity_id:
                    continue
                # Scope to the declared period when the question names one. The same
                # series in *other* periods does not disclose the withheld value, and
                # keeping it is what makes abstention a real test: the model sees the
                # neighbouring years and must decline to interpolate. When no period is
                # declared (a concept the entity never reports at all), every period of
                # that concept is excluded.
                if spec.missing_period is not None and rec.period != spec.missing_period:
                    continue
                forbidden.add(rec.record_id)
        return forbidden

    # ---- ordering -------------------------------------------------------------------

    def build(self, family: QuestionFamily, limit: Optional[int] = None) -> List[DistractorCandidate]:
        """Ordered candidates, strongest interference first, deterministic for a seed."""
        forbidden = self.forbidden_record_ids(family)
        targets = [
            r for r in (self.pool.get(rid) for rid in family.gold_evidence_ids) if r is not None
        ]
        target_values: List[float] = [t.value_numeric for t in targets if t.value_numeric is not None]
        if isinstance(family.gold_answer_normalized, (int, float)) and not isinstance(
            family.gold_answer_normalized, bool
        ):
            target_values.append(float(family.gold_answer_normalized))

        # For unanswerable families there is no gold record to relate distractors to, so
        # anchor the taxonomy on the entity/concept the question asks about.
        anchors = targets
        if not anchors and family.unanswerable_spec is not None:
            eid = family.unanswerable_spec.missing_entity_id
            if eid:
                anchors = [r for r in self.pool.domain_records(family.domain) if r.entity_id == eid][:4]

        buckets: Dict[DistractorType, List[DistractorCandidate]] = defaultdict(list)
        for rec in self.pool.domain_records(family.domain):
            if rec.record_id in forbidden or rec.record_type in self.NON_RENDERABLE_RECORD_TYPES:
                continue
            dtype, flags = classify_distractor(rec, anchors, target_values)
            buckets[dtype].append(DistractorCandidate(rec, dtype, flags))

        rng = rng_for(self.cfg.seed, "distractors", family.question_family_id)
        for dtype, items in buckets.items():
            items.sort(key=lambda c: c.record.record_id)
            rng.shuffle(items)
            # Within each tier, put explicitly named foils first: the question text
            # already references them by name, so they must be present even at 4K or the
            # question would describe a context that does not exist.
            def _foil_key(entity_id, concept, period):
                # Periods are None for records with no period (FDA products, trial arms);
                # both sides are normalized so those foils are not silently missed.
                return (entity_id, concept, period or None)

            explicit = {
                _foil_key(c.get("entity_id"), c.get("concept"), c.get("period"))
                for c in (family.target_conditions.get("explicit_foils") or [])
            }
            if explicit:
                items.sort(key=lambda c: _foil_key(
                    c.record.entity_id, c.record.concept, c.record.period) not in explicit)

        return self._interleave(buckets, limit)

    @staticmethod
    def _interleave(
        buckets: Dict[DistractorType, List[DistractorCandidate]], limit: Optional[int]
    ) -> List[DistractorCandidate]:
        """Weighted round-robin across tiers so every length sees a mix of relationships."""
        cursors = {t: 0 for t in DISTRACTOR_TIERS}
        out: List[DistractorCandidate] = []
        seen: Set[str] = set()
        while True:
            progressed = False
            for tier in DISTRACTOR_TIERS:
                items = buckets.get(tier) or []
                take = TIER_WEIGHTS.get(tier, 1)
                i = cursors[tier]
                for cand in items[i: i + take]:
                    if cand.record.record_id in seen:
                        continue
                    seen.add(cand.record.record_id)
                    out.append(cand)
                    progressed = True
                cursors[tier] = min(i + take, len(items))
                if limit is not None and len(out) >= limit:
                    return out[:limit]
            if not progressed:
                break
        return out
