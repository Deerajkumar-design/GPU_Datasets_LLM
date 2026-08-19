from __future__ import annotations

import gc
import argparse
import json
import re
import time
import traceback
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM

from longctx_dataset.config import load_config
from longctx_dataset.context.tokenizer import get_tokenizer
from longctx_dataset.prompt_renderer import PromptRenderer
from longctx_dataset.schemas import Instance


DATASET_PATH = Path("data/preproduction_llama32_3b_v2/instances.jsonl")
CONFIG_PATH = "config/preproduction_llama32_3b_v2.yaml"


def _record_blocks(instance: Instance) -> list[dict[str, str]]:
    pattern = re.compile(r'<RECORD id="([^"]+)"[^>]*>.*?</RECORD>', re.S)
    blocks: list[dict[str, str]] = []
    for match in pattern.finditer(instance.context):
        display_id = match.group(1)
        blocks.append(
            {
                "display_id": display_id,
                "record_id": instance.display_id_to_record_id[display_id],
                "text": match.group(0),
            }
        )
    if len(blocks) != len(instance.context_record_ids):
        raise RuntimeError(
            f"parsed {len(blocks)} records, expected {len(instance.context_record_ids)}"
        )
    return blocks


def _trim_to_target(
    *,
    base: Instance,
    renderer: PromptRenderer,
    target_tokens: int,
) -> tuple[str, int, int]:
    kept = _record_blocks(base)
    gold = set(base.gold_evidence_ids)
    remove_left = True

    def make_context() -> str:
        return "\n".join(block["text"] for block in kept)

    context = make_context()
    token_count = renderer.render(context=context, question=base.question).token_count
    while token_count > target_tokens:
        idx = None
        if remove_left:
            for i, block in enumerate(kept):
                if block["record_id"] not in gold:
                    idx = i
                    break
        else:
            for i in range(len(kept) - 1, -1, -1):
                if kept[i]["record_id"] not in gold:
                    idx = i
                    break
        remove_left = not remove_left
        if idx is None:
            raise RuntimeError("no removable non-gold records remain")
        kept.pop(idx)
        context = make_context()
        token_count = renderer.render(context=context, question=base.question).token_count

    kept_record_ids = {block["record_id"] for block in kept}
    if not gold <= kept_record_ids:
        raise RuntimeError("trimming removed target evidence")
    return context, token_count, len(kept)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-k", type=int, default=96)
    args = parser.parse_args()
    target_rendered_tokens = args.target_k * 1024

    cfg = load_config(CONFIG_PATH)
    tokenizer = get_tokenizer(cfg.tokenizer)
    renderer = PromptRenderer(cfg, tokenizer)
    rows = [json.loads(line) for line in DATASET_PATH.read_text(encoding="utf-8").splitlines()]
    base = Instance.model_validate(
        max(
            (row for row in rows if row["context_length_label"] == "128K"),
            key=lambda row: row["rendered_input_tokens_actual"],
        )
    )

    context, rendered_tokens, _record_count = _trim_to_target(
        base=base,
        renderer=renderer,
        target_tokens=target_rendered_tokens,
    )
    input_ids = renderer.render_token_ids(context=context, question=base.question)
    if len(input_ids) != rendered_tokens:
        raise RuntimeError(f"token mismatch: {len(input_ids)} != {rendered_tokens}")

    result = {
        "instance_id": base.instance_id,
        "rendered_input_tokens": rendered_tokens,
        "generation_completed": False,
        "cuda_oom": False,
        "generated_token_count": 0,
        "peak_allocated_vram_bytes": None,
        "peak_reserved_vram_bytes": None,
        "latency_seconds": None,
        "error_message": None,
    }

    model = AutoModelForCausalLM.from_pretrained(
        "meta-llama/Llama-3.2-3B-Instruct",
        local_files_only=True,
        dtype=torch.bfloat16,
        use_safetensors=True,
    )
    model.to("cuda")
    model.eval()

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    gc.collect()

    input_tensor = None
    start = time.time()
    try:
        input_tensor = torch.tensor([input_ids], dtype=torch.long, device="cuda")
        with torch.inference_mode():
            output = model.generate(
                input_ids=input_tensor,
                do_sample=False,
                num_beams=1,
                max_new_tokens=512,
                use_cache=True,
            )
        result["generated_token_count"] = int(output.shape[1] - input_tensor.shape[1])
        result["generation_completed"] = True
        del output
    except torch.cuda.OutOfMemoryError as exc:
        result["cuda_oom"] = True
        result["error_message"] = str(exc)
    except BaseException as exc:  # noqa: BLE001
        result["error_message"] = f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=4)}"
    finally:
        result["latency_seconds"] = time.time() - start
        result["peak_allocated_vram_bytes"] = int(torch.cuda.max_memory_allocated())
        result["peak_reserved_vram_bytes"] = int(torch.cuda.max_memory_reserved())
        if input_tensor is not None:
            del input_tensor
        gc.collect()
        torch.cuda.empty_cache()

    print(json.dumps(result, indent=2), flush=True)
    return 0 if result["generation_completed"] or result["cuda_oom"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
