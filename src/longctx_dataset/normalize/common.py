"""Cross-domain normalization utilities and the in-memory record pool.

Record IDs are deterministic functions of the source coordinates. That matters for
reproducibility: regenerating from the same raw payloads must yield the same IDs, so
gold-evidence references stay valid across runs.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence

from ..schemas import Domain, NormalizedRecord

_SLUG_RE = re.compile(r"[^A-Za-z0-9]+")


def slugify(text: Any, max_len: int = 40) -> str:
    """ASCII-safe, whitespace-free token suitable for embedding in a record ID."""
    s = _SLUG_RE.sub("-", str(text)).strip("-")
    return s[:max_len] if len(s) > max_len else s


def make_record_id(prefix: str, *parts: Any, hash_len: int = 8) -> str:
    """Build ``PREFIX_slug1_slug2_<hash>``.

    The trailing hash of the *full* joined key guarantees uniqueness even when the
    readable slugs are truncated, while keeping IDs human-inspectable in a context.
    """
    joined = "|".join("" if p is None else str(p) for p in parts)
    digest = hashlib.sha1(joined.encode("utf-8")).hexdigest()[:hash_len]
    readable = "_".join(slugify(p, 24) for p in parts if p not in (None, ""))
    rid = f"{prefix}_{readable}_{digest}" if readable else f"{prefix}_{digest}"
    return _SLUG_RE.sub("-", rid).strip("-").replace("--", "-")


def canonical_number(value: Any) -> Optional[float]:
    """Coerce to float, returning ``None`` for anything non-finite or non-numeric."""
    if value is None or isinstance(value, bool):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):  # NaN / inf
        return None
    return f


def canonical_date(value: Any) -> Optional[str]:
    """Normalize common source date spellings to ISO ``YYYY-MM-DD`` / ``YYYY-MM``."""
    if not value:
        return None
    s = str(value).strip()
    if re.fullmatch(r"\d{8}", s):  # openFDA style: 20050729
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) or re.fullmatch(r"\d{4}-\d{2}", s) or re.fullmatch(r"\d{4}", s):
        return s
    return s


_STRENGTH_RE = re.compile(r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>MG|MCG|G|ML|IU|UNITS?|%)", re.IGNORECASE)


def parse_fda_strength(strength: str) -> Dict[str, Any]:
    """Extract the leading numeric magnitude and unit from an FDA strength string.

    FDA strength strings are free-form (``"20MG"``, ``"5MG/ML"``, ``"EQ 10MG BASE"``).
    Only the first magnitude/unit pair is extracted, and the original string is always
    preserved, so a question never depends on an over-clever parse.
    """
    out: Dict[str, Any] = {"strength_raw": strength, "magnitude": None, "strength_unit": None}
    if not strength:
        return out
    m = _STRENGTH_RE.search(strength)
    if m:
        out["magnitude"] = float(m.group("num"))
        out["strength_unit"] = m.group("unit").upper()
    return out


class RecordPool:
    """Indexed collection of normalized records for one or more domains.

    The indices exist so distractor selection can find *related* records cheaply:
    same entity, same concept, same period. Random same-domain records are the
    last-resort tier, never the first.
    """

    def __init__(self, records: Iterable[NormalizedRecord] = ()):
        self.records: List[NormalizedRecord] = []
        self.by_id: Dict[str, NormalizedRecord] = {}
        self.by_entity: Dict[str, List[str]] = defaultdict(list)
        self.by_concept: Dict[str, List[str]] = defaultdict(list)
        self.by_entity_concept: Dict[tuple, List[str]] = defaultdict(list)
        self.by_domain: Dict[Domain, List[str]] = defaultdict(list)
        self.by_target_key: Dict[tuple, List[str]] = defaultdict(list)
        for r in records:
            self.add(r)

    def add(self, rec: NormalizedRecord) -> None:
        if rec.record_id in self.by_id:
            return  # idempotent; duplicate IDs are caught by the validator, not here
        self.records.append(rec)
        self.by_id[rec.record_id] = rec
        self.by_entity[rec.entity_id].append(rec.record_id)
        self.by_concept[rec.concept].append(rec.record_id)
        self.by_entity_concept[(rec.entity_id, rec.concept)].append(rec.record_id)
        self.by_domain[rec.domain].append(rec.record_id)
        tk = rec.target_key()
        self.by_target_key[(tk["entity_id"], tk["concept"], tk["period"], tk["unit"])].append(rec.record_id)

    def get(self, record_id: str) -> Optional[NormalizedRecord]:
        return self.by_id.get(record_id)

    def resolve(self, record_ids: Sequence[str]) -> List[NormalizedRecord]:
        out = []
        for rid in record_ids:
            rec = self.by_id.get(rid)
            if rec is None:
                raise KeyError(f"record_id not in pool: {rid}")
            out.append(rec)
        return out

    def domain_records(self, domain: Domain) -> List[NormalizedRecord]:
        return [self.by_id[r] for r in self.by_domain.get(domain, [])]

    def matches_target(
        self,
        *,
        entity_id: Optional[str] = None,
        concept: Optional[str] = None,
        concepts: Optional[Sequence[str]] = None,
        period: Optional[str] = None,
        unit: Optional[str] = None,
    ) -> List[NormalizedRecord]:
        """Every record satisfying the given (partial) target conditions.

        Used both to find gold evidence and -- crucially -- to prove that no record
        satisfying an unanswerable family's conditions exists in the pool.
        """
        wanted = set(concepts) if concepts else ({concept} if concept else None)
        out = []
        for rec in self.records:
            if entity_id is not None and rec.entity_id != entity_id:
                continue
            if wanted is not None and rec.concept not in wanted:
                continue
            if period is not None and rec.period != period:
                continue
            if unit is not None and rec.unit != unit:
                continue
            out.append(rec)
        return out

    def __len__(self) -> int:
        return len(self.records)
