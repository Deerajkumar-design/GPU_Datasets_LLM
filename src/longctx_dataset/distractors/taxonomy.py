"""Distractor taxonomy: what a non-gold record's relationship to the target is.

Every record inserted into a context is classified, and the classification is stored on
the instance. That is what makes the eventual analysis able to ask *which kind* of
interference drives errors, rather than only *how much* context there was.

All distractors are real records from the same primary source. Source values are never
altered to manufacture a decoy; a synthetic-adversarial mode would have to be a separate,
explicitly labelled feature.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Sequence

from ..schemas import DistractorType, NormalizedRecord

# Ordered most-interfering first. The context builder emits distractors in roughly this
# priority so even a 4K context is genuinely hard, then degrades to weaker relationships
# as the length grows and the strong tiers are exhausted.
DISTRACTOR_TIERS: List[DistractorType] = [
    DistractorType.WRONG_VERSION,
    DistractorType.WRONG_UNIT,
    DistractorType.WRONG_SERIES_VARIANT,
    DistractorType.WRONG_PERIOD,
    DistractorType.WRONG_ENTITY,
    DistractorType.WRONG_FIELD,
    DistractorType.NEAR_MATCH_VALUE,
    DistractorType.OTHER_SAME_DOMAIN,
]

# How many of each tier to emit per interleaving cycle. Keeps a mix present at every
# length rather than exhausting one tier before starting the next.
TIER_WEIGHTS: Dict[DistractorType, int] = {
    DistractorType.WRONG_VERSION: 2,
    DistractorType.WRONG_UNIT: 2,
    DistractorType.WRONG_SERIES_VARIANT: 2,
    DistractorType.WRONG_PERIOD: 3,
    DistractorType.WRONG_ENTITY: 3,
    DistractorType.WRONG_FIELD: 3,
    DistractorType.NEAR_MATCH_VALUE: 2,
    DistractorType.OTHER_SAME_DOMAIN: 4,
}

NEAR_MATCH_REL_TOLERANCE = 0.05
"""A record whose value is within 5% of a target value is a plausible wrong answer."""

_TRAILING_PAREN = re.compile(r"\s*\([^)]*\)\s*$")


def _base_label(label: str) -> str:
    """Concept label with its trailing unit parenthetical removed.

    "GDP (current US$)" and "GDP (constant 2015 US$)" both reduce to "GDP". Sources
    routinely encode the measurement basis this way, so two records that agree on the
    base label but disagree on unit are unit variants of one quantity even though they
    carry different concept codes.
    """
    return _TRAILING_PAREN.sub("", label or "").strip().casefold()


def _is_unit_variant(record: NormalizedRecord, target: NormalizedRecord) -> bool:
    if record.concept == target.concept:
        return False
    base = _base_label(record.concept_label)
    if not base or base != _base_label(target.concept_label):
        return False
    return record.unit != target.unit


def _family(record: NormalizedRecord) -> Optional[str]:
    """Declared grouping of series that measure the same underlying quantity.

    Sources publish one quantity under several identifiers -- seasonally adjusted and
    not, nominal and chained-dollar, daily and monthly, national and per-state. Those
    share a family, which lets the taxonomy see them as competing measurements of one
    thing rather than as unrelated fields.
    """
    fam = record.metadata.get("series_family")
    return str(fam) if fam else None


def _same_measure(record: NormalizedRecord, target: NormalizedRecord) -> bool:
    """Same concept code, or two concept codes declared to measure the same quantity."""
    if record.concept == target.concept:
        return True
    fam = _family(record)
    return bool(fam) and fam == _family(target)


def _series_variant_differs(record: NormalizedRecord, target: NormalizedRecord) -> bool:
    """Same quantity and unit, but a different measurement basis or series variant."""
    if record.unit != target.unit:
        return False
    for key in ("seasonal_adjustment", "frequency"):
        a, b = record.metadata.get(key), target.metadata.get(key)
        if a is not None and b is not None and a != b:
            return True
    for key in ("basis", "transformation", "price_basis"):
        a, b = record.metadata.get(key), target.metadata.get(key)
        if a is not None and b is not None and a != b:
            return True
    return False


@dataclass(frozen=True)
class RelationshipFlags:
    """Exactly how a distractor relates to the target it competes with."""

    same_entity: bool = False
    same_metric: bool = False
    same_period: bool = False
    same_unit: bool = False
    same_version: bool = False
    different_entity: bool = False
    different_period: bool = False
    different_unit: bool = False
    different_version: bool = False
    different_metric: bool = False
    value_within_5_percent: bool = False

    def as_dict(self) -> Dict[str, bool]:
        return {k: bool(v) for k, v in asdict(self).items()}


def condition_satisfied_by(record: NormalizedRecord, condition: Dict[str, Any]) -> bool:
    """Would ``record`` be a valid source for the fact ``condition`` describes?

    Only keys that are present and non-null in the condition are compared, so a
    condition can be as coarse as ``{entity_id, concept}`` (used to prove absence for
    unanswerable families) or as precise as a full entity/concept/period/unit/version
    tuple plus metadata discriminators (used to bind to one arm of a trial).
    """
    for key in ("entity_id", "concept", "period", "unit", "version"):
        want = condition.get(key)
        if want is None:
            continue
        if getattr(record, key, None) != want:
            return False
    for key, want in (condition.get("metadata_match") or {}).items():
        if record.metadata.get(key) != want:
            return False
    return True


def _rel_close(a: Optional[float], b: Optional[float], tol: float = NEAR_MATCH_REL_TOLERANCE) -> bool:
    if a is None or b is None:
        return False
    if b == 0:
        return a == 0
    return abs(a - b) / abs(b) <= tol


def classify_distractor(
    record: NormalizedRecord,
    targets: Sequence[NormalizedRecord],
    target_values: Sequence[float] = (),
    allow_near_match: bool = True,
) -> tuple[DistractorType, Dict[str, bool]]:
    """Assign the strongest applicable taxonomy label relative to the nearest target.

    "Strongest" means most confusable: a record differing from the target only by
    accession number is a harder distractor than one merely from the same domain, so
    WRONG_VERSION is checked before WRONG_PERIOD, and so on down the tiers.
    """
    if not targets:
        near = allow_near_match and any(_rel_close(record.value_numeric, t) for t in target_values)
        flags = RelationshipFlags(value_within_5_percent=near)
        return (
            DistractorType.NEAR_MATCH_VALUE if near else DistractorType.OTHER_SAME_DOMAIN,
            flags.as_dict(),
        )

    best: Optional[tuple[int, DistractorType, RelationshipFlags]] = None
    for tgt in targets:
        same_entity = record.entity_id == tgt.entity_id
        same_metric = record.concept == tgt.concept
        same_period = record.period == tgt.period
        same_unit = record.unit == tgt.unit
        same_version = record.version == tgt.version
        near = allow_near_match and same_unit and (_rel_close(record.value_numeric, tgt.value_numeric) or any(
            _rel_close(record.value_numeric, v) for v in target_values
        ))
        flags = RelationshipFlags(
            same_entity=same_entity, same_metric=same_metric, same_period=same_period,
            same_unit=same_unit, same_version=same_version,
            different_entity=not same_entity, different_period=not same_period,
            different_unit=not same_unit, different_version=not same_version,
            different_metric=not same_metric, value_within_5_percent=near,
        )

        same_measure = _same_measure(record, tgt)

        if same_entity and same_metric and same_period and same_unit and not same_version:
            dtype = DistractorType.WRONG_VERSION
        elif same_entity and same_metric and same_period and not same_unit:
            dtype = DistractorType.WRONG_UNIT
        elif same_entity and same_period and not same_metric and same_measure and record.unit != tgt.unit:
            dtype = DistractorType.WRONG_UNIT
        elif (
            same_entity and same_period and not same_metric
            and same_measure and _series_variant_differs(record, tgt)
        ):
            # Same quantity and unit for the same entity and period, but a different
            # published basis: seasonally adjusted vs not, daily vs monthly, etc.
            dtype = DistractorType.WRONG_SERIES_VARIANT
        elif same_entity and same_period and _is_unit_variant(record, tgt):
            # Label-based fallback for sources that encode the basis in the concept
            # label's trailing parenthetical rather than in a declared family.
            dtype = DistractorType.WRONG_UNIT
        elif same_entity and same_measure and not same_period:
            dtype = DistractorType.WRONG_PERIOD
        elif same_measure and same_period and not same_entity:
            dtype = DistractorType.WRONG_ENTITY
        elif same_entity and not same_metric:
            dtype = DistractorType.WRONG_FIELD
        elif near:
            dtype = DistractorType.NEAR_MATCH_VALUE
        else:
            dtype = DistractorType.OTHER_SAME_DOMAIN

        rank = DISTRACTOR_TIERS.index(dtype)
        if best is None or rank < best[0]:
            best = (rank, dtype, flags)

    assert best is not None
    return best[1], best[2].as_dict()


def describe_taxonomy() -> Dict[str, str]:
    """Human-readable definitions, emitted into the pilot report."""
    return {
        DistractorType.WRONG_VERSION.value:
            "Same entity, metric, period and unit, but a different filing/revision/submission version.",
        DistractorType.WRONG_UNIT.value:
            "Same entity, metric and period, reported in a genuinely different unit.",
        DistractorType.WRONG_SERIES_VARIANT.value:
            "Same entity, period, unit and underlying measure, but a different series variant or "
            "measurement basis such as seasonal adjustment, frequency, nominal/real basis, or transform.",
        DistractorType.WRONG_PERIOD.value:
            "Same entity and metric, a different period (other year, quarter, or instant).",
        DistractorType.WRONG_ENTITY.value:
            "Same metric and period, a different entity (other company, country, trial, product).",
        DistractorType.WRONG_FIELD.value:
            "Same entity, a different field/concept.",
        DistractorType.NEAR_MATCH_VALUE.value:
            f"Numerically within {NEAR_MATCH_REL_TOLERANCE:.0%} of a target value while being a "
            "different fact -- a plausible-looking wrong answer.",
        DistractorType.OTHER_SAME_DOMAIN.value:
            "A real record from the same primary source with no closer relationship to the target.",
    }
