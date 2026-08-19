from __future__ import annotations

import json
from pathlib import Path

import pytest

from longctx_dataset.config import ModelConfig, ModelPromptConfig, PipelineConfig, TokenizerConfig
from longctx_dataset.context.tokenizer import Tokenizer
from longctx_dataset.inference import (
    EXECUTION_SEED,
    append_jsonl,
    build_execution_order,
    completed_instance_ids,
    parse_response_json,
    prepare_input,
    safe_run_dir,
    sha256_ints,
    verify_dataset_gate,
)
from longctx_dataset.prompt_renderer import PromptRenderer
from longctx_dataset.schemas import AnswerType, Domain, Instance, QuestionType


class FakeLlamaTokenizer(Tokenizer):
    tokenizer_id = "hf:meta-llama/Llama-3.2-3B-Instruct"
    version = "test"
    tokenizer_class = "Fake"
    model_context_limit = 131072
    has_chat_template = True
    is_approximate = False

    def encode(self, text: str):
        return [1] * len(text.split())

    def count(self, text: str) -> int:
        return len(self.encode(text))

    def apply_chat_template(self, messages, *, add_generation_prompt: bool, tokenize: bool, **kwargs):
        rendered = f"Today Date: {kwargs.get('date_string')}\n" + "\n".join(m["content"] for m in messages)
        if add_generation_prompt:
            rendered += "\nassistant:"
        if tokenize:
            return [abs(hash(x)) % 1000 for x in rendered.split()]
        return rendered


def _cfg(tmp_path: Path) -> PipelineConfig:
    c = PipelineConfig(
        name="preproduction_llama32_3b_v2",
        data_root=tmp_path,
        output_subdir="preproduction_llama32_3b_v2",
        tokenizer=TokenizerConfig(id="hf:meta-llama/Llama-3.2-3B-Instruct", allow_fallback=False),
        model=ModelConfig(id="meta-llama/Llama-3.2-3B-Instruct", max_new_tokens=512),
        model_prompt=ModelPromptConfig(template_date="09 Aug 2026"),
    )
    c.config_hash = c.compute_hash()
    return c


def _inst(i: int, renderer: PromptRenderer | None = None) -> Instance:
    context = f'<RECORD id="R{i:010X}">value: {i}</RECORD>'
    question = "What is the value?"
    tokens = renderer.render(context=context, question=question).token_count if renderer else 10
    return Instance(
        instance_id=f"SEC_{i:04d}_4K",
        question_family_id=f"SEC_{i:04d}",
        domain=Domain.SEC,
        question_type=QuestionType.DIRECT_RETRIEVAL,
        question=question,
        context_length_nominal=4096,
        context_length_label="4K",
        context_tokens_actual=5,
        tokenizer="hf:meta-llama/Llama-3.2-3B-Instruct",
        rendered_input_tokens_actual=tokens,
        prompt_hash=renderer.prompt_hash if renderer else None,
        prompt_version="llama_chat_v4",
        remaining_context_margin=130560 - tokens,
        generation_tokens_reserved=512,
        model_context_limit=131072,
        answerable=True,
        gold_answer="1",
        gold_answer_normalized="1",
        answer_type=AnswerType.STRING,
        gold_evidence_ids=["RID"],
        context=context,
        context_record_ids=["RID"],
    )


def test_json_parse_failure_is_recorded_without_retry():
    bad = parse_response_json("not json")
    assert bad["json_parse_success"] is False
    good = parse_response_json('{"selected_evidence":["R1"],"answer":"x","insufficient_evidence":false}')
    assert good["json_parse_success"] is True
    assert good["parsed_answer"] == "x"


def test_append_jsonl_and_resume_completed_ids(tmp_path: Path):
    results = tmp_path / "results.jsonl"
    failures = tmp_path / "failures.jsonl"
    append_jsonl(results, {"instance_id": "A", "status": "SUCCESS"})
    append_jsonl(failures, {"instance_id": "B", "status": "GENERATION_ERROR"})
    assert completed_instance_ids(results, failures) == {"A", "B"}
    assert json.loads(results.read_text().splitlines()[0])["status"] == "SUCCESS"


def test_safe_run_dir_refuses_silent_overwrite(tmp_path: Path):
    d = tmp_path / "run"
    d.mkdir()
    (d / "run_manifest.json").write_text("{}")
    with pytest.raises(SystemExit):
        safe_run_dir(d, resume=False)
    safe_run_dir(d, resume=True)


def test_execution_order_is_deterministic_and_mixed():
    inst = [_inst(i) for i in range(20)]
    a = build_execution_order(inst, seed=EXECUTION_SEED)
    b = build_execution_order(inst, seed=EXECUTION_SEED)
    assert a == b
    assert [r["instance_id"] for r in a] != [i.instance_id for i in inst]


def test_prompt_and_input_hash_verification_uses_shared_renderer(tmp_path: Path):
    cfg = _cfg(tmp_path)
    renderer = PromptRenderer(cfg, FakeLlamaTokenizer())
    inst = _inst(1, renderer)
    prepared = prepare_input(inst, renderer)
    assert len(prepared.input_ids) == inst.rendered_input_tokens_actual
    assert prepared.input_token_ids_hash == sha256_ints(prepared.input_ids)
    bad = inst.model_copy(update={"prompt_hash": "wrong"})
    with pytest.raises(ValueError, match="prompt hash"):
        prepare_input(bad, renderer)


def test_dataset_gate_detects_count_mismatch(tmp_path: Path):
    cfg = _cfg(tmp_path)
    cfg.ensure_dirs()
    (cfg.out_dir / "question_families.jsonl").write_text("")
    (cfg.out_dir / "instances.jsonl").write_text("")
    gate = verify_dataset_gate(cfg)
    assert gate["passed"] is False
    assert any(f["field"] == "families" for f in gate["failures"])
