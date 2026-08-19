"""Deterministic opaque IDs for model-facing context records."""

from __future__ import annotations

import hashlib
import re
from typing import Dict, Iterable

from ..config import PipelineConfig
from ..schemas import NormalizedRecord

DISPLAY_ID_RE = re.compile(r"^R[0-9A-F]{10,}$")


class DisplayIdMapper:
    """Map canonical record IDs to deterministic opaque display IDs."""

    def __init__(self, cfg: PipelineConfig, records: Iterable[NormalizedRecord]):
        self._canonical_to_display: Dict[str, str] = {}
        self._display_to_canonical: Dict[str, str] = {}
        salt = f"{cfg.seed}|{cfg.config_hash}|display-record-id"
        for rec in sorted(records, key=lambda r: r.record_id):
            display = self._make_unique(salt, rec.record_id)
            self._canonical_to_display[rec.record_id] = display
            self._display_to_canonical[display] = rec.record_id

    def _make_unique(self, salt: str, record_id: str) -> str:
        n = 10
        while True:
            digest = hashlib.sha256(f"{salt}|{record_id}".encode("utf-8")).hexdigest().upper()
            candidate = f"R{digest[:n]}"
            if candidate not in self._display_to_canonical:
                return candidate
            if self._display_to_canonical[candidate] == record_id:
                return candidate
            n += 2

    def display_id(self, record_id: str) -> str:
        return self._canonical_to_display[record_id]

    def canonical_id(self, display_id: str) -> str:
        return self._display_to_canonical[display_id]

