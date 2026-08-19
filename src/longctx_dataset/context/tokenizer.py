"""Tokenizer abstraction.

Token counts are the independent variable of this experiment, so the tokenizer is a
configured parameter with a recorded identity -- never a hard-coded constant. The model
under test has not been chosen yet; when it is, changing ``tokenizer.id`` in the config
and re-running ``build-contexts`` is the only change required.

Backends use a ``backend:name`` id scheme:

    tiktoken:cl100k_base    tiktoken BPE (offline after first download)
    hf:<model-id>           HuggingFace AutoTokenizer (requires `transformers`)
    whitespace:v1           deterministic, dependency-free approximation

``whitespace:v1`` is explicitly *not* scientifically authoritative. It exists so unit
tests never require a network or a model download, and it is only used for real data
when ``tokenizer.allow_fallback`` is set -- in which case the id recorded in every
instance says so plainly.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Sequence

from ..config import TokenizerConfig


class TokenizerUnavailable(RuntimeError):
    """The configured tokenizer backend could not be loaded."""


class Tokenizer(ABC):
    """Minimal interface the context builder depends on."""

    tokenizer_id: str
    version: Optional[str] = None
    is_approximate: bool = False
    tokenizer_class: Optional[str] = None
    tokenizer_revision: Optional[str] = None
    model_config_revision: Optional[str] = None
    model_context_limit: Optional[int] = None
    has_chat_template: bool = False

    @abstractmethod
    def encode(self, text: str) -> List[int]:
        ...

    @abstractmethod
    def count(self, text: str) -> int:
        """Number of tokens in ``text``. Must be deterministic."""

    def count_all(self, texts: List[str]) -> List[int]:
        return [self.count(t) for t in texts]

    def apply_chat_template(
        self,
        messages: Sequence[Dict[str, str]],
        *,
        add_generation_prompt: bool,
        tokenize: bool,
        **template_kwargs: Any,
    ) -> Any:
        raise TokenizerUnavailable(
            f"tokenizer {self.tokenizer_id!r} does not expose a native chat template"
        )

    def provenance(self) -> Dict[str, Any]:
        return {
            "tokenizer_id": self.tokenizer_id,
            "tokenizer_class": self.tokenizer_class,
            "tokenizer_version": self.version,
            "tokenizer_revision": self.tokenizer_revision,
            "model_config_revision": self.model_config_revision,
            "model_context_limit": self.model_context_limit,
            "chat_template_used": self.has_chat_template,
            "is_approximate": self.is_approximate,
        }


class TiktokenTokenizer(Tokenizer):
    """OpenAI BPE encodings via ``tiktoken``."""

    is_approximate = False

    def __init__(self, encoding_name: str):
        try:
            import tiktoken  # noqa: PLC0415
        except ImportError as exc:
            raise TokenizerUnavailable(f"tiktoken is not installed: {exc}") from exc
        try:
            self._enc = tiktoken.get_encoding(encoding_name)
        except Exception as exc:  # noqa: BLE001 - includes network errors on first use
            raise TokenizerUnavailable(
                f"could not load tiktoken encoding {encoding_name!r}: {exc}"
            ) from exc
        self.tokenizer_id = f"tiktoken:{encoding_name}"
        try:
            import tiktoken as _t  # noqa: PLC0415
            self.version = f"tiktoken=={getattr(_t, '__version__', 'unknown')}"
        except ImportError:
            self.version = None

    def encode(self, text: str) -> List[int]:
        return self._enc.encode(text, disallowed_special=())

    def count(self, text: str) -> int:
        return len(self.encode(text))


class HFTokenizer(Tokenizer):
    """HuggingFace ``AutoTokenizer``, for when the model under test is HF-hosted."""

    is_approximate = False

    def __init__(self, model_id: str):
        try:
            from transformers import AutoConfig, AutoTokenizer  # noqa: PLC0415
        except ImportError as exc:
            raise TokenizerUnavailable(
                f"transformers is not installed (pip install 'longctx-dataset[hf]'): {exc}"
            ) from exc
        try:
            self._tok = AutoTokenizer.from_pretrained(model_id)
            self._cfg = AutoConfig.from_pretrained(model_id)
        except Exception as exc:  # noqa: BLE001
            raise TokenizerUnavailable(f"could not load HF tokenizer {model_id!r}: {exc}") from exc
        self.tokenizer_id = f"hf:{model_id}"
        self.tokenizer_class = self._tok.__class__.__name__
        self.tokenizer_revision = getattr(self._tok, "init_kwargs", {}).get("_commit_hash")
        self.model_config_revision = getattr(self._cfg, "_commit_hash", None)
        self.model_context_limit = _derive_context_limit(self._tok, self._cfg, model_id)
        self.has_chat_template = bool(getattr(self._tok, "chat_template", None))
        try:
            import transformers  # noqa: PLC0415
            import tokenizers  # noqa: PLC0415
            self.version = (
                f"transformers=={transformers.__version__}; "
                f"tokenizers=={tokenizers.__version__}"
            )
        except ImportError:
            self.version = None

    def encode(self, text: str) -> List[int]:
        return self._tok.encode(text, add_special_tokens=False)

    def count(self, text: str) -> int:
        return len(self.encode(text))

    def apply_chat_template(
        self,
        messages: Sequence[Dict[str, str]],
        *,
        add_generation_prompt: bool,
        tokenize: bool,
        **template_kwargs: Any,
    ) -> Any:
        if not self.has_chat_template:
            raise TokenizerUnavailable(f"HF tokenizer {self.tokenizer_id!r} has no chat_template")
        return self._tok.apply_chat_template(
            list(messages),
            add_generation_prompt=add_generation_prompt,
            tokenize=tokenize,
            **template_kwargs,
        )


def _usable_limit(value: Any) -> Optional[int]:
    if not isinstance(value, int) or value <= 0:
        return None
    # Hugging Face sometimes uses huge sentinels when the true limit is unknown.
    if value > 10_000_000:
        return None
    return value


def _derive_context_limit(tok: Any, cfg: Any, model_id: str) -> Optional[int]:
    candidates: Dict[str, int] = {}
    cfg_limit = _usable_limit(getattr(cfg, "max_position_embeddings", None))
    tok_limit = _usable_limit(getattr(tok, "model_max_length", None))
    if cfg_limit is not None:
        candidates["config.max_position_embeddings"] = cfg_limit
    if tok_limit is not None:
        candidates["tokenizer.model_max_length"] = tok_limit
    if not candidates:
        return None
    vals = set(candidates.values())
    if len(vals) != 1:
        raise TokenizerUnavailable(
            f"context-limit fields disagree for {model_id!r}: {candidates}"
        )
    return vals.pop()


_WS_SPLIT = re.compile(r"\s+|(?<=[^\w\s])|(?=[^\w\s])")


class WhitespaceTokenizer(Tokenizer):
    """Dependency-free deterministic approximation.

    Splits on whitespace and punctuation boundaries, then charges one token per 4
    characters of any long chunk. Correlates with BPE counts closely enough to exercise
    the context-building logic in tests, and is marked ``is_approximate`` so nothing
    downstream can mistake it for a real tokenizer.
    """

    is_approximate = True

    def __init__(self):
        self.tokenizer_id = "whitespace:v1"
        self.version = "v1"

    def _pieces(self, text: str) -> List[str]:
        return [p for p in _WS_SPLIT.split(text) if p and not p.isspace()]

    def encode(self, text: str) -> List[int]:
        # Stable pseudo-ids; only the count is meaningful for this backend.
        return [hash(p) & 0xFFFF for p in self._pieces(text) for _ in range(max(1, len(p) // 4))]

    def count(self, text: str) -> int:
        return sum(max(1, len(p) // 4) for p in self._pieces(text))


def _build(tokenizer_id: str) -> Tokenizer:
    if ":" not in tokenizer_id:
        raise TokenizerUnavailable(
            f"tokenizer id {tokenizer_id!r} must be 'backend:name' "
            "(e.g. 'tiktoken:cl100k_base', 'hf:meta-llama/Llama-3-8B', 'whitespace:v1')"
        )
    backend, name = tokenizer_id.split(":", 1)
    backend = backend.lower()
    if backend == "tiktoken":
        return TiktokenTokenizer(name)
    if backend == "hf":
        return HFTokenizer(name)
    if backend == "whitespace":
        return WhitespaceTokenizer()
    raise TokenizerUnavailable(f"unknown tokenizer backend {backend!r} in {tokenizer_id!r}")


def get_tokenizer(cfg: TokenizerConfig) -> Tokenizer:
    """Load the configured tokenizer, honouring the explicit fallback policy."""
    try:
        return _build(cfg.id)
    except TokenizerUnavailable:
        if not cfg.allow_fallback or not cfg.fallback_id:
            raise
        return _build(cfg.fallback_id)
