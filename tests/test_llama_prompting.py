from __future__ import annotations

from pathlib import Path

from longctx_dataset.config import ModelConfig, ModelPromptConfig, PipelineConfig, TokenizerConfig, load_config
from longctx_dataset.context.tokenizer import Tokenizer
from longctx_dataset.prompt_renderer import (
    LLAMA_PROMPT_VERSION,
    RESPONSE_FORMAT_INSTRUCTIONS,
    RESPONSE_FORMAT_VERSION,
    PromptRenderer,
    _input_ids,
    prompt_hash,
)
from longctx_dataset.schemas import AnswerType, Domain, Instance, QuestionType, INSUFFICIENT_EVIDENCE
from longctx_dataset.validation.dataset import _model_prompt_problems


class FakeLlamaTokenizer(Tokenizer):
    tokenizer_id = "hf:meta-llama/Llama-3.2-3B-Instruct"
    version = "transformers==test; tokenizers==test"
    tokenizer_class = "FakeLlamaTokenizer"
    tokenizer_revision = "tokrev"
    model_config_revision = "cfgrev"
    model_context_limit = 512
    has_chat_template = True
    is_approximate = False

    def encode(self, text: str):
        return [1] * len(text.split())

    def count(self, text: str) -> int:
        return len(self.encode(text))

    def apply_chat_template(self, messages, *, add_generation_prompt: bool, tokenize: bool, **template_kwargs):
        date = template_kwargs.get("date_string", "WALL CLOCK DATE")
        rendered = f"<|start_header_id|>system<|end_header_id|>\n\nToday Date: {date}\n\n"
        rendered += "".join(
            f"<|start_header_id|>{m['role']}<|end_header_id|>\n\n{m['content']}<|eot_id|>"
            for m in messages
        )
        if add_generation_prompt:
            rendered += "<|start_header_id|>assistant<|end_header_id|>\n\n"
        if tokenize:
            return [1] * max(1, len(rendered.split()))
        return rendered


def _cfg() -> PipelineConfig:
    c = PipelineConfig(
        name="llama-test",
        tokenizer=TokenizerConfig(
            id="hf:meta-llama/Llama-3.2-3B-Instruct",
            allow_fallback=False,
        ),
        model=ModelConfig(
            id="meta-llama/Llama-3.2-3B-Instruct",
            max_new_tokens=32,
        ),
        model_prompt=ModelPromptConfig(template_date="09 Aug 2026"),
    )
    c.config_hash = c.compute_hash()
    return c


def test_llama_prompt_renderer_uses_native_chat_template_and_uniform_contract():
    renderer = PromptRenderer(_cfg(), FakeLlamaTokenizer())
    rendered = renderer.render(context='<RECORD id="R000001">value: 7</RECORD>', question="What is the value?")
    assert rendered.prompt_version == LLAMA_PROMPT_VERSION
    assert rendered.response_format_version == RESPONSE_FORMAT_VERSION
    assert rendered.prompt_hash == prompt_hash(template_date="09 Aug 2026")
    assert rendered.token_count > 0

    preview = renderer.render_text_preview(
        context='<RECORD id="R000001">value: 7</RECORD>',
        question="What is the value?",
    )
    assert "<|start_header_id|>system" in preview
    assert "Today Date: 09 Aug 2026" in preview
    assert "INSUFFICIENT_EVIDENCE" in preview
    assert RESPONSE_FORMAT_INSTRUCTIONS in preview
    assert "answerable" not in preview.lower()
    assert "gold_answer" not in preview.lower()
    assert "question_type" not in preview.lower()


def test_llama_prompt_renderer_freezes_native_template_date(monkeypatch):
    cfg = _cfg()
    tok = FakeLlamaTokenizer()
    renderer = PromptRenderer(cfg, tok)
    first = renderer.render_text_preview(context="ctx", question="q")
    monkeypatch.setenv("TZ", "Pacific/Kiritimati")
    second = renderer.render_text_preview(context="ctx", question="q")
    assert first == second
    assert "Today Date: 09 Aug 2026" in first
    assert "WALL CLOCK DATE" not in first


def test_chat_template_token_container_uses_input_ids_not_container_length():
    assert _input_ids({"input_ids": [1, 2, 3], "attention_mask": [1, 1, 1]}) == [1, 2, 3]
    assert _input_ids({"input_ids": [[1, 2, 3]], "attention_mask": [[1, 1, 1]]}) == [1, 2, 3]


def test_model_prompt_validation_recomputes_rendered_tokens_and_margin():
    cfg = _cfg()
    tok = FakeLlamaTokenizer()
    renderer = PromptRenderer(cfg, tok)
    context = '<RECORD id="R000001">value: 7</RECORD>'
    question = "What is the value?"
    rendered = renderer.render(context=context, question=question)
    inst = Instance(
        instance_id="SEC_0001_4K",
        question_family_id="SEC_0001",
        domain=Domain.SEC,
        question_type=QuestionType.UNANSWERABLE,
        question=question,
        context_length_nominal=4096,
        context_length_label="4K",
        context_tokens_actual=tok.count(context),
        tokenizer=tok.tokenizer_id,
        tokenizer_version=tok.version,
        tokenizer_revision=tok.tokenizer_revision,
        tokenizer_class=tok.tokenizer_class,
        model_id=cfg.model.id,
        model_config_revision=tok.model_config_revision,
        rendered_input_tokens_actual=rendered.token_count,
        prompt_overhead_tokens=rendered.token_count - tok.count(context),
        generation_tokens_reserved=cfg.model.max_new_tokens,
        model_context_limit=tok.model_context_limit,
        remaining_context_margin=tok.model_context_limit - cfg.model.max_new_tokens - rendered.token_count,
        prompt_version=LLAMA_PROMPT_VERSION,
        prompt_hash=renderer.prompt_hash,
        response_format_version=RESPONSE_FORMAT_VERSION,
        answerable=False,
        gold_answer=None,
        gold_answer_normalized=INSUFFICIENT_EVIDENCE,
        answer_type=AnswerType.INSUFFICIENT_EVIDENCE,
        context=context,
        context_record_ids=[],
    )
    assert _model_prompt_problems(inst, cfg, tok, renderer) == []

    bad = inst.model_copy(update={"rendered_input_tokens_actual": rendered.token_count + 1})
    assert any("rendered_input_tokens_actual" in p for p in _model_prompt_problems(bad, cfg, tok, renderer))


def test_prompt_hash_changes_with_template_date():
    assert prompt_hash(template_date="09 Aug 2026") != prompt_hash(template_date="10 Aug 2026")


def test_preproduction_and_production_configs_use_exact_llama_tokenizer():
    for path in ("config/preproduction.yaml", "config/production.yaml"):
        cfg = load_config(Path(path))
        assert cfg.model.id == "meta-llama/Llama-3.2-3B-Instruct"
        assert cfg.model.max_new_tokens == 512
        assert cfg.model_prompt.template_date == "09 Aug 2026"
        assert cfg.tokenizer.id == "hf:meta-llama/Llama-3.2-3B-Instruct"
        assert cfg.tokenizer.allow_fallback is False


def test_historical_pilot_config_keeps_original_tokenizer():
    cfg = load_config("config/pilot.yaml")
    assert cfg.tokenizer.id == "tiktoken:cl100k_base"
