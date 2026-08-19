"""Conservative semantic equivalence for evidence records."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .schemas import EvidenceEquivalenceGroup, NormalizedRecord, QuestionFamily

_Q_FRAME_RE = re.compile(r"^CY(?P<year>\d{4})Q(?P<q>[1-4])(?P<instant>I)?$")
_Y_FRAME_RE = re.compile(r"^CY(?P<year>\d{4})(?P<instant>I)?$")
_DATE_RANGE_RE = re.compile(r"^(?P<start>\d{4}-\d{2}-\d{2})\.\.(?P<end>\d{4}-\d{2}-\d{2})$")


def _quarter_span(year: int, q: int) -> Tuple[str, str]:
    starts = {1: "01-01", 2: "04-01", 3: "07-01", 4: "10-01"}
    ends = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}
    return f"{year}-{starts[q]}", f"{year}-{ends[q]}"


def semantic_period_key(rec: NormalizedRecord) -> Optional[Tuple[str, str]]:
    """Canonical period span when two source encodings describe the same duration."""
    period = rec.period or ""
    m = _Q_FRAME_RE.match(period)
    if m and not m.group("instant"):
        return _quarter_span(int(m.group("year")), int(m.group("q")))
    m = _Y_FRAME_RE.match(period)
    if m and not m.group("instant"):
        year = int(m.group("year"))
        return f"{year}-01-01", f"{year}-12-31"
    m = _DATE_RANGE_RE.match(period)
    if m:
        return m.group("start"), m.group("end")
    if rec.period_start and rec.period_end and rec.period_start != rec.period_end:
        return str(rec.period_start), str(rec.period_end)
    if period:
        return period, period
    return None


def _same_value(a: NormalizedRecord, b: NormalizedRecord) -> bool:
    if a.value_numeric is not None and b.value_numeric is not None:
        return math.isclose(float(a.value_numeric), float(b.value_numeric), rel_tol=1e-12, abs_tol=1e-9)
    return str(a.value) == str(b.value)


def _metadata_match(rec: NormalizedRecord, condition: Dict[str, Any]) -> bool:
    for key, want in (condition.get("metadata_match") or {}).items():
        if rec.metadata.get(key) != want:
            return False
    return True


def records_equivalent(
    a: NormalizedRecord,
    b: NormalizedRecord,
    *,
    target_condition: Optional[Dict[str, Any]] = None,
    require_version: bool = True,
) -> bool:
    """True when two records are alternate representations of the same fact.

    Numeric equality alone is intentionally insufficient. Version must match whenever
    both records carry a version; this prevents amended/vintage evidence from collapsing.
    """
    if a.record_id == b.record_id:
        return True
    if a.domain != b.domain or a.source != b.source:
        return False
    if a.entity_id != b.entity_id or a.concept != b.concept or a.unit != b.unit:
        return False
    if not _same_value(a, b):
        return False
    if semantic_period_key(a) != semantic_period_key(b):
        return False
    if require_version and a.version is not None and b.version is not None and a.version != b.version:
        return False
    if target_condition and not (_metadata_match(a, target_condition) and _metadata_match(b, target_condition)):
        return False
    return True


def equivalence_group_id(gold_record_id: str, canonical_ids: Sequence[str]) -> str:
    payload = "|".join([gold_record_id] + sorted(canonical_ids))
    return "EG" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:10].upper()


def build_equivalence_groups(
    family: QuestionFamily,
    records: Iterable[NormalizedRecord],
    display_ids: Optional[Dict[str, str]] = None,
) -> List[EvidenceEquivalenceGroup]:
    by_id = {r.record_id: r for r in records}
    conditions = list(family.target_conditions.get("records") or [])
    require_version = family_requires_version_equivalence(family)
    groups: List[EvidenceEquivalenceGroup] = []
    for i, gold_id in enumerate(family.gold_evidence_ids):
        gold = by_id.get(gold_id)
        if gold is None:
            continue
        cond = conditions[i] if i < len(conditions) else None
        equivalent = sorted(
            r.record_id for r in by_id.values()
            if records_equivalent(gold, r, target_condition=cond, require_version=require_version)
        )
        disp = [display_ids[rid] for rid in equivalent if display_ids and rid in display_ids]
        groups.append(EvidenceEquivalenceGroup(
            group_id=equivalence_group_id(gold_id, equivalent),
            gold_record_id=gold_id,
            canonical_record_ids=equivalent,
            display_ids=disp,
        ))
    return groups


def family_requires_version_equivalence(family: QuestionFamily) -> bool:
    """Whether evidence equivalence must preserve source version/vintage."""
    template_id = family.generation_metadata.template_id.upper()
    version_markers = ("FILING_VERSION", "VINTAGE", "ORIGINAL_VS_SUPPLEMENT")
    return any(marker in template_id for marker in version_markers)
