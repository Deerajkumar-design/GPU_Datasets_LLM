"""Tokenizer abstraction.

The tokenizer is an experimental parameter, so the contract that matters is: it is
selected by configured id, its identity is reported, and the fallback policy is explicit
rather than silent.
"""

from __future__ import annotations

import pytest

from longctx_dataset.config import TokenizerConfig
from longctx_dataset.context.tokenizer import (
    TokenizerUnavailable,
    WhitespaceTokenizer,
    get_tokenizer,
)


def test_whitespace_backend_is_deterministic():
    t = WhitespaceTokenizer()
    text = "<RECORD id=\"X\">\nvalue: 1234\n</RECORD>"
    assert t.count(text) == t.count(text)
    assert t.count(text) > 0


def test_whitespace_backend_declares_itself_approximate():
    assert WhitespaceTokenizer().is_approximate is True
    assert get_tokenizer(TokenizerConfig(id="tiktoken:cl100k_base")).is_approximate is False


def test_count_grows_monotonically_with_text():
    t = WhitespaceTokenizer()
    short = "alpha beta"
    assert t.count(short + " gamma delta") > t.count(short)


def test_backend_selected_by_configured_id():
    assert get_tokenizer(TokenizerConfig(id="whitespace:v1")).tokenizer_id == "whitespace:v1"
    tok = get_tokenizer(TokenizerConfig(id="tiktoken:cl100k_base"))
    assert tok.tokenizer_id == "tiktoken:cl100k_base"
    assert tok.version and "tiktoken" in tok.version


def test_tokenizer_id_must_be_backend_qualified():
    with pytest.raises(TokenizerUnavailable, match="backend:name"):
        get_tokenizer(TokenizerConfig(id="cl100k_base", allow_fallback=False))


def test_unknown_backend_is_rejected():
    with pytest.raises(TokenizerUnavailable, match="unknown tokenizer backend"):
        get_tokenizer(TokenizerConfig(id="magic:thing", allow_fallback=False))


def test_fallback_is_opt_in_only():
    """An unavailable tokenizer must fail loudly unless fallback was explicitly allowed."""
    strict = TokenizerConfig(id="magic:thing", allow_fallback=False)
    with pytest.raises(TokenizerUnavailable):
        get_tokenizer(strict)

    lenient = TokenizerConfig(id="magic:thing",
                              fallback_id="whitespace:v1", allow_fallback=True)
    tok = get_tokenizer(lenient)
    assert tok.tokenizer_id == "whitespace:v1"
    # The instance records the tokenizer actually used, never the one that was requested.
    assert tok.is_approximate is True


def test_tiktoken_counts_are_stable_and_reasonable():
    tok = get_tokenizer(TokenizerConfig(id="tiktoken:cl100k_base"))
    text = "The quick brown fox jumps over the lazy dog."
    assert tok.count(text) == tok.count(text)
    assert 8 <= tok.count(text) <= 14
    assert len(tok.encode(text)) == tok.count(text)
