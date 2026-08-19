"""Versioned prompt artifacts for future model evaluation."""

from __future__ import annotations

from pathlib import Path

EVALUATION_PROMPT_VERSION = "evaluation_v1"
EVALUATION_PROMPT_PATH = Path("prompts/evaluation_v1.txt")


def load_evaluation_prompt() -> str:
    return EVALUATION_PROMPT_PATH.read_text(encoding="utf-8")

