"""Model-facing question leakage checks."""

from __future__ import annotations

import re
from typing import List, Pattern


ANSWERABILITY_LEAK_PATTERNS: tuple[Pattern[str], ...] = (
    re.compile(r"\bif\b.{0,80}\b(?:do|does|did|contain|list|include|provide|available|missing)", re.I),
    re.compile(r"\binsufficient[_ -]evidence\b", re.I),
    re.compile(r"\bif\s+(?:unavailable|missing)\b", re.I),
    re.compile(r"\bdo not infer\b", re.I),
    re.compile(r"\bdo not fabricate\b", re.I),
    re.compile(r"\brather than\b", re.I),
    re.compile(r"\bcannot be determined\b", re.I),
    re.compile(r"\bfrom another (?:date|trial|product|series|record|concept)\b", re.I),
)


def answerability_leakage_phrases(question: str) -> List[str]:
    """Return suspicious abstention-only phrases in a model-facing question."""
    hits: List[str] = []
    for pattern in ANSWERABILITY_LEAK_PATTERNS:
        m = pattern.search(question)
        if m:
            hits.append(m.group(0))
    return hits

