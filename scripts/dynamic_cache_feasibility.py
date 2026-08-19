from __future__ import annotations

import gc
import json
import re
import resource
import time
import traceback
from pathlib import Path

import psutil
import torch
from transformers import AutoModelForCausalLM

from longctx_dataset.config import load_config
from longctx_dataset.context.tokenizer import get_tokenizer
from longctx_dataset.prompt_renderer import PromptRenderer
from longctx_dataset.schemas import Instance


def main() -> int:
    cfg = load_config("config/preproduction_llama32_3b_v2.yaml")
    tok = get_tokenizer(cfg.tokenizer)
    renderer = PromptRenderer(cfg, tok)
    rows = [json.loads(l) for l in Path("data/preproduction_llama32_3b_v2/instances.jsonl").read_text().splitlines()]
    base_row = max([r for r in rows if r["context_length_label"] == "128K"],
                   key=lambda r: r["rendered_input_tokens_actual"])
    base = Instance.model_validate(base_row)
    print("base_instance", base.instance_id, "base_tokens", base.rendered_input_tokens_actual, flush=True)

    pattern = re.compile(r'<RECORD id="([^"]+)"[^>]*>.*?</RECORD>', re.S)
    blocks = []
    for m in pattern.finditer(base.context):
        did = m.group(1)
        rid = base.display_id_to_record_id[did]
        blocks.append({"display_id": did, "record_id": rid, "text": m.group(0)})
    assert len(blocks) == len(base.context_record_ids), (len(blocks), len(base.context_record_ids))
    gold = set(base.gold_evidence_ids)
    sep = "\n"

    def make_context(target_tokens: int):
        kept = list(blocks)

        def text_for(k):
            return sep.join(b["text"] for b in k)

        current = text_for(kept)
        current_tokens = renderer.render(context=current, question=base.question).token_count
        remove_left = True
        while current_tokens > target_tokens:
            idx = None
            if remove_left:
                for i, b in enumerate(kept):
                    if b["record_id"] not in gold:
                        idx = i
                        break
            else:
                for i in range(len(kept) - 1, -1, -1):
                    if kept[i]["record_id"] not in gold:
                        idx = i
                        break
            remove_left = not remove_left
            if idx is None:
                raise RuntimeError("no removable distractor records remain")
            kept.pop(idx)
            current = text_for(kept)
            current_tokens = renderer.render(context=current, question=base.question).token_count
        assert gold <= {b["record_id"] for b in kept}
        return current, current_tokens, len(kept)

    def run_test(label: str, target_tokens: int, model):
        context, input_tokens, n_records = make_context(target_tokens)
        ids = renderer.render_token_ids(context=context, question=base.question)
        assert len(ids) == input_tokens
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        gc.collect()
        proc = psutil.Process()
        result = {
            "label": label,
            "target_tokens": target_tokens,
            "rendered_input_tokens": input_tokens,
            "n_records": n_records,
            "success": False,
            "cuda_oom": False,
            "generated_token_count": 0,
            "latency_seconds": None,
            "peak_allocated_vram_bytes": None,
            "peak_reserved_vram_bytes": None,
            "process_rss_before_bytes": proc.memory_info().rss,
            "process_rss_after_bytes": None,
            "process_peak_rss_kib": None,
            "available_ram_before_bytes": psutil.virtual_memory().available,
            "available_ram_after_bytes": None,
            "error_type": None,
            "error_message": None,
        }
        t0 = time.time()
        input_tensor = None
        try:
            input_tensor = torch.tensor([ids], dtype=torch.long, device="cuda")
            with torch.inference_mode():
                out = model.generate(
                    input_ids=input_tensor,
                    do_sample=False,
                    num_beams=1,
                    max_new_tokens=512,
                    use_cache=True,
                )
            gen = out[0, input_tensor.shape[1]:].detach().cpu().tolist()
            result.update({"success": True, "generated_token_count": len(gen)})
            del out
        except torch.cuda.OutOfMemoryError as exc:
            result.update({"cuda_oom": True, "error_type": type(exc).__name__, "error_message": str(exc)})
        except BaseException as exc:  # noqa: BLE001
            result.update({
                "error_type": type(exc).__name__,
                "error_message": str(exc) + "\n" + traceback.format_exc()[:1500],
            })
        finally:
            result["latency_seconds"] = time.time() - t0
            result["peak_allocated_vram_bytes"] = torch.cuda.max_memory_allocated()
            result["peak_reserved_vram_bytes"] = torch.cuda.max_memory_reserved()
            result["process_rss_after_bytes"] = proc.memory_info().rss
            result["process_peak_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            result["available_ram_after_bytes"] = psutil.virtual_memory().available
            if input_tensor is not None:
                del input_tensor
            gc.collect()
            torch.cuda.empty_cache()
        print(json.dumps(result), flush=True)
        return result

    print("loading_model", flush=True)
    model = AutoModelForCausalLM.from_pretrained(
        "meta-llama/Llama-3.2-3B-Instruct",
        local_files_only=True,
        dtype=torch.bfloat16,
        use_safetensors=True,
    )
    model.to("cuda")
    model.eval()
    print("model_loaded", flush=True)

    results = []
    first = run_test("96K", 96 * 1024, model)
    results.append(first)
    if first["success"]:
        second = run_test("112K", 112 * 1024, model)
        results.append(second)
        if second["success"]:
            for label, target in [("120K", 120 * 1024), ("124K", 124 * 1024),
                                  ("126K", 126 * 1024), ("127K", 127 * 1024)]:
                res = run_test(label, target, model)
                results.append(res)
                if not res["success"]:
                    break
        else:
            for label, target in [("104K", 104 * 1024), ("108K", 108 * 1024), ("110K", 110 * 1024)]:
                results.append(run_test(label, target, model))
    else:
        second = run_test("80K", 80 * 1024, model)
        results.append(second)
        if second["success"]:
            for label, target in [("88K", 88 * 1024), ("92K", 92 * 1024), ("94K", 94 * 1024)]:
                res = run_test(label, target, model)
                results.append(res)
                if not res["success"]:
                    break
        else:
            for label, target in [("64K", 64 * 1024), ("72K", 72 * 1024), ("76K", 76 * 1024)]:
                res = run_test(label, target, model)
                results.append(res)
                if res["success"]:
                    break

    out = Path("data/inference_llama32_3b_preproduction_v1")
    out.mkdir(parents=True, exist_ok=True)
    (out / "dynamic_cache_feasibility_sweep.json").write_text(
        json.dumps({
            "base_instance": base.instance_id,
            "base_rendered_tokens": base.rendered_input_tokens_actual,
            "results": results,
        }, indent=2),
        encoding="utf-8",
    )
    print("wrote", out / "dynamic_cache_feasibility_sweep.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
