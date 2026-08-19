"""Model-facing prompt rendering and token accounting.

The dataset stores record contexts separately, but inference sees the complete chat
prompt: common instruction, user message labels, question, response contract, and the
model tokenizer's chat-template special tokens. This module is the single frozen place
where that prompt is assembled.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List

from .config import PipelineConfig
from .context.tokenizer import Tokenizer, TokenizerUnavailable
from .prompts import EVALUATION_PROMPT_VERSION, load_evaluation_prompt

LLAMA_PROMPT_VERSION = "llama_chat_v4"
RESPONSE_FORMAT_VERSION = "answer_only_line_v1"

RESPONSE_FORMAT_INSTRUCTIONS = """Return only one short line:
ANSWER: <answer>

If the supplied records are insufficient, return exactly:
ANSWER: INSUFFICIENT_EVIDENCE

Do not output JSON. Do not output evidence IDs, citations, explanations, reasoning, booleans, or extra lines."""


@dataclass(frozen=True)
class RenderedPrompt:
    messages: List[Dict[str, str]]
    token_count: int
    prompt_version: str
    prompt_hash: str
    response_format_version: str
    system_prompt_version: str
    template_date: str


def prompt_hash(system_prompt: str | None = None, template_date: str = "09 Aug 2026") -> str:
    system = system_prompt if system_prompt is not None else load_evaluation_prompt()
    payload = "\n\n".join([
        f"prompt_version={LLAMA_PROMPT_VERSION}",
        f"system_prompt_version={EVALUATION_PROMPT_VERSION}",
        f"template_date={template_date}",
        system,
        f"response_format_version={RESPONSE_FORMAT_VERSION}",
        RESPONSE_FORMAT_INSTRUCTIONS,
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class PromptRenderer:
    """Render the frozen benchmark prompt through the configured tokenizer."""

    def __init__(self, cfg: PipelineConfig, tokenizer: Tokenizer):
        self.cfg = cfg
        self.tokenizer = tokenizer
        self.system_prompt = load_evaluation_prompt()
        self.template_date = cfg.model_prompt.template_date
        self.prompt_hash = prompt_hash(self.system_prompt, self.template_date)
        if cfg.model.id:
            expected = f"hf:{cfg.model.id}"
            if tokenizer.tokenizer_id != expected:
                raise TokenizerUnavailable(
                    f"model {cfg.model.id!r} requires tokenizer {expected!r}, "
                    f"got {tokenizer.tokenizer_id!r}"
                )
            if not tokenizer.has_chat_template:
                raise TokenizerUnavailable(
                    f"tokenizer {tokenizer.tokenizer_id!r} has no native chat template"
                )
            if tokenizer.model_context_limit is None:
                raise TokenizerUnavailable(
                    f"tokenizer {tokenizer.tokenizer_id!r} did not expose a verified context limit"
                )

    def messages(self, *, context: str, question: str) -> List[Dict[str, str]]:
        user = "\n\n".join([
            "KNOWLEDGE RECORDS:",
            context,
            "TARGET QUESTION:",
            question,
            "OUTPUT FORMAT:",
            RESPONSE_FORMAT_INSTRUCTIONS,
        ])
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user},
        ]

    def render(self, *, context: str, question: str) -> RenderedPrompt:
        messages = self.messages(context=context, question=question)
        input_ids = self.render_token_ids(context=context, question=question)
        return RenderedPrompt(
            messages=messages,
            token_count=len(input_ids),
            prompt_version=LLAMA_PROMPT_VERSION,
            prompt_hash=self.prompt_hash,
            response_format_version=RESPONSE_FORMAT_VERSION,
            system_prompt_version=EVALUATION_PROMPT_VERSION,
            template_date=self.template_date,
        )

    def render_token_ids(self, *, context: str, question: str) -> List[int]:
        messages = self.messages(context=context, question=question)
        tokens = self.tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            date_string=self.template_date,
        )
        return _input_ids(tokens)

    def render_text_preview(self, *, context: str, question: str) -> str:
        messages = self.messages(context=context, question=question)
        return self.tokenizer.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=False,
            date_string=self.template_date,
        )


def _input_ids(tokenized: Any) -> List[int]:
    """Normalize HF v4/v5 chat-template return values to one input-id list."""
    if isinstance(tokenized, list):
        if tokenized and isinstance(tokenized[0], list):
            if len(tokenized) != 1:
                raise ValueError("batched chat-template token output is not supported")
            return list(tokenized[0])
        return list(tokenized)
    if isinstance(tokenized, dict):
        ids = tokenized.get("input_ids")
        if ids is None:
            raise ValueError("chat-template token output did not include input_ids")
        if ids and isinstance(ids[0], list):
            if len(ids) != 1:
                raise ValueError("batched chat-template input_ids are not supported")
            return list(ids[0])
        return list(ids)
    ids = getattr(tokenized, "input_ids", None)
    if ids is not None:
        if ids and isinstance(ids[0], list):
            if len(ids) != 1:
                raise ValueError("batched chat-template input_ids are not supported")
            return list(ids[0])
        return list(ids)
    raise TypeError(f"unsupported chat-template token output type: {type(tokenized).__name__}")
