"""Re-render the existing Llama preproduction dataset with frozen prompt metadata.

This utility intentionally does not fetch sources, regenerate questions, or resample
families. It preserves the existing 100-family dataset semantics and writes a corrected
versioned artifact with deterministic Llama chat-template date handling.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from longctx_dataset.config import load_config
from longctx_dataset.context.tokenizer import get_tokenizer
from longctx_dataset.pipeline import (
    build_manifest,
    families_path,
    instances_path,
    unavailable_path,
)
from longctx_dataset.prompt_renderer import LLAMA_PROMPT_VERSION, RESPONSE_FORMAT_VERSION, PromptRenderer
from longctx_dataset.schemas import (
    GoldEvidenceDisplayMapping,
    Instance,
    QuestionFamily,
    QuestionType,
    UnavailableVariant,
)
from longctx_dataset.storage.io import iter_jsonl, read_models, write_jsonl, write_parquet


def _reclassify_family(fam: QuestionFamily, config_hash: str) -> QuestionFamily:
    update = {}
    if fam.generation_metadata.template_id == "CT_DATE_FIELD_SELECTION":
        update["question_type"] = QuestionType.ENTITY_UNIT_BINDING
    meta = fam.generation_metadata.model_copy(update={
        "config_hash": config_hash,
        "tokenizer_id": "hf:meta-llama/Llama-3.2-3B-Instruct",
    })
    update["generation_metadata"] = meta
    return fam.model_copy(update=update)


def _gold_display_map(inst: Instance) -> list[GoldEvidenceDisplayMapping]:
    by_gold = {g.gold_record_id: g for g in inst.gold_evidence_equivalence_groups}
    out: list[GoldEvidenceDisplayMapping] = []
    for rid in inst.gold_evidence_ids:
        display_id = next((d for d, c in inst.display_id_to_record_id.items() if c == rid), None)
        group = by_gold.get(rid)
        out.append(GoldEvidenceDisplayMapping(
            canonical_record_id=rid,
            display_id=display_id,
            equivalent_canonical_ids=list(group.canonical_record_ids) if group else [rid],
            equivalent_display_ids=list(group.display_ids) if group else ([display_id] if display_id else []),
        ))
    return out


def rerender(source_config: str, dest_config: str) -> None:
    src = load_config(source_config)
    dst = load_config(dest_config)
    dst.ensure_dirs()
    tok = get_tokenizer(dst.tokenizer)
    renderer = PromptRenderer(dst, tok)
    safe_budget = (tok.model_context_limit or 0) - dst.model.max_new_tokens
    if safe_budget <= 0:
        raise RuntimeError("invalid model input budget")

    families = [_reclassify_family(f, dst.config_hash) for f in read_models(families_path(src), QuestionFamily)]
    fam_by_id = {f.question_family_id: f for f in families}
    write_jsonl(families_path(dst), families)

    out_instances: list[Instance] = []
    overflows: list[str] = []
    for row in iter_jsonl(instances_path(src)):
        inst = Instance.model_validate(row)
        fam = fam_by_id[inst.question_family_id]
        context_tokens = tok.count(inst.context)
        rendered = renderer.render(context=inst.context, question=inst.question).token_count
        if rendered > safe_budget:
            overflows.append(f"{inst.instance_id}: rendered {rendered} > budget {safe_budget}")
        update = {
            "question_type": fam.question_type,
            "context_tokens_actual": context_tokens,
            "tokenizer": tok.tokenizer_id,
            "tokenizer_version": tok.version,
            "tokenizer_revision": tok.tokenizer_revision,
            "tokenizer_class": tok.tokenizer_class,
            "model_id": dst.model.id,
            "model_config_revision": tok.model_config_revision,
            "rendered_input_tokens_actual": rendered,
            "prompt_overhead_tokens": rendered - context_tokens,
            "generation_tokens_reserved": dst.model.max_new_tokens,
            "model_context_limit": tok.model_context_limit,
            "remaining_context_margin": safe_budget - rendered,
            "near_model_maximum": inst.context_length_nominal == max(dst.context.lengths),
            "prompt_version": LLAMA_PROMPT_VERSION,
            "prompt_hash": renderer.prompt_hash,
            "response_format_version": RESPONSE_FORMAT_VERSION,
            "target_position_relative_in_records_context": inst.target_position_relative,
            "gold_evidence_display_map": _gold_display_map(inst),
            "context_sha256": hashlib.sha256(inst.context.encode("utf-8")).hexdigest(),
            "generation_metadata": fam.generation_metadata,
        }
        if inst.stats is not None:
            stats = inst.stats.model_copy(update={
                "context_tokens_actual": context_tokens,
                "tokenizer_id": tok.tokenizer_id,
                "tokenizer_version": tok.version,
                "rendered_input_tokens_actual": rendered,
                "prompt_overhead_tokens": rendered - context_tokens,
                "generation_tokens_reserved": dst.model.max_new_tokens,
                "model_context_limit": tok.model_context_limit,
                "remaining_context_margin": safe_budget - rendered,
                "near_model_maximum": inst.context_length_nominal == max(dst.context.lengths),
            })
            update["stats"] = stats
        out_instances.append(inst.model_copy(update=update))
    if overflows:
        raise RuntimeError("prompt budget overflow after frozen-date rerender:\n" + "\n".join(overflows[:20]))
    write_jsonl(instances_path(dst), out_instances)

    unavailable = [UnavailableVariant.model_validate(r) for r in iter_jsonl(unavailable_path(src))]
    write_jsonl(unavailable_path(dst), unavailable)
    if dst.write_parquet:
        write_parquet(dst.out_dir / "instances.parquet", [i.model_dump(mode="json") for i in out_instances])
        write_parquet(dst.out_dir / "question_families.parquet", [f.model_dump(mode="json") for f in families])
    build_manifest(dst)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--source-config", default="config/preproduction.yaml")
    p.add_argument("--dest-config", default="config/preproduction_llama32_3b_v2.yaml")
    args = p.parse_args()
    rerender(args.source_config, args.dest_config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
