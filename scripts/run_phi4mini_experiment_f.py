#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gc
import hashlib
import json
import os
import platform
import random
import re
import resource
import subprocess
import sys
import time
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import torch
from huggingface_hub import HfApi
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

from longctx_dataset.config import git_commit
from longctx_dataset.inference import sha256_ints, sha256_text
from longctx_dataset.prompts import EVALUATION_PROMPT_VERSION, load_evaluation_prompt
from longctx_dataset.prompt_renderer import _input_ids
from longctx_dataset.schemas import Instance
from longctx_dataset.storage.io import iter_jsonl, write_json


DATASET_DIR = Path("data/preproduction_llama32_3b_500f_6ctx_v1")
EXPECTED_DATASET_HASH = "dc2c4194dedb090198e6883735257908ce274bebc8611b40d958dbd026aa1fe6"
MODEL_ID = "microsoft/Phi-4-mini-instruct"
MODEL_REVISION = "cfbefacb99257ffa30c83adab238a50856ac3083"
TOKENIZER_ID = f"hf:{MODEL_ID}"
PROMPT_VERSION = "phi4mini_chat_v1"
RESPONSE_FORMAT_VERSION = "answer_only_line_v1"
TEMPLATE_DATE = "09 Aug 2026"
MAX_NEW_TOKENS = 128
EXECUTION_SEED = 20260812
RUN_ID = "phi4mini_500f_6ctx_v1"
OUT_DIR = Path("data/inference_phi4mini_500f_6ctx_v1")
CONTEXT_LABELS = ["4K", "8K", "16K", "32K", "64K", "82K"]
GENERATION_SETTINGS = {
    "do_sample": False,
    "num_beams": 1,
    "max_new_tokens": MAX_NEW_TOKENS,
    "use_cache": True,
}

RESPONSE_FORMAT_INSTRUCTIONS = """Return only one short line:
ANSWER: <answer>

If the supplied records are insufficient, return exactly:
ANSWER: INSUFFICIENT_EVIDENCE

Do not output JSON. Do not output evidence IDs, citations, explanations, reasoning, booleans, or extra lines."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def dataset_hash() -> str:
    h = hashlib.sha256()
    for path in [DATASET_DIR / "question_families.jsonl", DATASET_DIR / "instances.jsonl"]:
        h.update(path.as_posix().encode("utf-8"))
        h.update(b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(chunk)
        h.update(b"\0")
    return h.hexdigest()


def phi_prompt_hash(system_prompt: str | None = None) -> str:
    system = system_prompt if system_prompt is not None else load_evaluation_prompt()
    payload = "\n\n".join([
        f"prompt_version={PROMPT_VERSION}",
        f"system_prompt_version={EVALUATION_PROMPT_VERSION}",
        f"template_date={TEMPLATE_DATE}",
        "native_template=microsoft/Phi-4-mini-instruct apply_chat_template",
        "trust_remote_code=True",
        system,
        f"response_format_version={RESPONSE_FORMAT_VERSION}",
        RESPONSE_FORMAT_INSTRUCTIONS,
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class PhiPromptRenderer:
    def __init__(self, tokenizer: Any, system_prompt: str):
        self.tokenizer = tokenizer
        self.system_prompt = system_prompt
        self.prompt_hash = phi_prompt_hash(system_prompt)

    def messages(self, *, context: str, question: str) -> list[dict[str, str]]:
        user = "\n\n".join([
            "KNOWLEDGE RECORDS:",
            context,
            "TARGET QUESTION:",
            question,
            "OUTPUT FORMAT:",
            RESPONSE_FORMAT_INSTRUCTIONS,
        ])
        return [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": user}]

    def render_token_ids(self, *, context: str, question: str) -> list[int]:
        return _input_ids(self.tokenizer.apply_chat_template(
            self.messages(context=context, question=question),
            add_generation_prompt=True,
            tokenize=True,
        ))

    def render_text_preview(self, *, context: str, question: str) -> str:
        return self.tokenizer.apply_chat_template(
            self.messages(context=context, question=question),
            add_generation_prompt=True,
            tokenize=False,
        )


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def gpu_metadata() -> dict[str, Any]:
    meta: dict[str, Any] = {}
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free,driver_version", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            name, total, free, driver = [p.strip() for p in out.stdout.strip().split(",", 3)]
            meta.update({"gpu_name": name, "gpu_total_vram_mib": int(total), "gpu_free_vram_mib": int(free), "cuda_driver_version": driver})
    except Exception:
        pass
    return meta


def ram_metadata() -> dict[str, Any]:
    meta = {"process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    try:
        import psutil

        proc = psutil.Process()
        vm = psutil.virtual_memory()
        meta.update({"process_rss_bytes": proc.memory_info().rss, "available_ram_bytes": vm.available, "total_ram_bytes": vm.total})
    except Exception:
        pass
    return meta


def package_environment() -> dict[str, str]:
    proc = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True, check=False)
    return {"pip_freeze": proc.stdout}


def load_instances() -> list[Instance]:
    return [Instance.model_validate(row) for row in iter_jsonl(DATASET_DIR / "instances.jsonl")]


def verify_dataset(instances: Sequence[Instance]) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    observed_hash = dataset_hash()
    counts = Counter(inst.context_length_label for inst in instances)
    family_counts = Counter(inst.question_family_id for inst in instances)
    if observed_hash != EXPECTED_DATASET_HASH:
        failures.append({"field": "dataset_hash", "expected": EXPECTED_DATASET_HASH, "actual": observed_hash})
    if len(family_counts) != 500:
        failures.append({"field": "families", "expected": 500, "actual": len(family_counts)})
    if len(instances) != 3000:
        failures.append({"field": "instances", "expected": 3000, "actual": len(instances)})
    if any(n != 6 for n in family_counts.values()):
        failures.append({"field": "contexts_per_family", "expected": 6, "bad_count": sum(n != 6 for n in family_counts.values())})
    for label in CONTEXT_LABELS:
        if counts.get(label, 0) != 500:
            failures.append({"field": f"context_{label}", "expected": 500, "actual": counts.get(label, 0)})
    prompts = Counter((inst.prompt_version, inst.prompt_hash) for inst in instances)
    return {
        "passed": not failures,
        "failures": failures,
        "dataset_hash": observed_hash,
        "instances_by_context": dict(counts),
        "families": len(family_counts),
        "instances": len(instances),
        "source_prompt_versions": {f"{k[0]}:{k[1]}": v for k, v in prompts.items()},
    }


def resolve_model_revision() -> str:
    try:
        return HfApi().model_info(MODEL_ID, revision="main").sha
    except Exception:
        return MODEL_REVISION


def load_model_and_tokenizer() -> tuple[Any, Any, Any, str, dict[str, Any]]:
    resolved = resolve_model_revision()
    if resolved != MODEL_REVISION:
        raise SystemExit(f"Phi revision drift: resolved {resolved}, expected {MODEL_REVISION}")
    tok = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION, trust_remote_code=True)
    hf_cfg = AutoConfig.from_pretrained(MODEL_ID, revision=MODEL_REVISION, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        revision=MODEL_REVISION,
        torch_dtype=torch.bfloat16,
        use_safetensors=True,
        trust_remote_code=True,
    )
    model.to("cuda")
    model.eval()
    meta = {
        "resolved_revision": resolved,
        "config_class": hf_cfg.__class__.__name__,
        "model_type": getattr(hf_cfg, "model_type", None),
        "model_config_revision": getattr(hf_cfg, "_commit_hash", None),
        "tokenizer_class": tok.__class__.__name__,
        "tokenizer_revision": getattr(tok, "init_kwargs", {}).get("_commit_hash"),
        "model_class": model.__class__.__name__,
        "model_context_limit": getattr(tok, "model_max_length", None),
        "max_position_embeddings": getattr(hf_cfg, "max_position_embeddings", None),
        "sliding_window": getattr(hf_cfg, "sliding_window", None),
        "attention_implementation": getattr(model.config, "_attn_implementation", None),
        "cache_config": getattr(model.config, "cache_config", None),
    }
    return model, tok, hf_cfg, resolved, meta


def parse_answer_only(raw_text: str, generated_count: int) -> dict[str, Any]:
    text = (raw_text or "").strip()
    match = re.search(r"(?im)^\s*ANSWER:\s*(.+?)\s*$", text)
    contains_answer = bool(match)
    parsed_answer = match.group(1).strip() if match else None
    has_json = "{" in text or "}" in text or re.search(r'"selected_evidence"|"insufficient_evidence"', text) is not None
    has_evidence_id = re.search(r"\bR[A-Z0-9]{8,12}\b", text) is not None
    has_thinking = bool(re.search(r"</?think>", text, flags=re.I))
    nonempty_lines = [line for line in text.splitlines() if line.strip()]
    extra_lines = len(nonempty_lines) > 1 or (nonempty_lines and not nonempty_lines[0].lstrip().startswith("ANSWER:"))
    degenerate = degenerate_text(text)
    hit_limit = generated_count == MAX_NEW_TOKENS
    usable = contains_answer and bool(parsed_answer) and not has_json and not has_evidence_id and not extra_lines and not degenerate and not has_thinking
    return {
        "contains_answer_prefix": contains_answer,
        "parsed_answer": parsed_answer,
        "usable_answer_output": usable,
        "format_failure": not usable,
        "hit_max_new_tokens_128": hit_limit,
        "output_truncated": hit_limit,
        "degenerate_output": degenerate,
        "contains_unwanted_json": has_json,
        "contains_evidence_id": has_evidence_id,
        "contains_prose_or_extra_lines": extra_lines,
        "contains_thinking_trace": has_thinking,
        "malformed_output_pattern": (
            "usable_answer_line" if usable else
            "thinking_trace" if has_thinking else
            "degenerate_generation" if degenerate else
            "missing_answer_prefix" if not contains_answer else
            "empty_answer" if not parsed_answer else
            "unwanted_json_or_evidence" if has_json or has_evidence_id else
            "extra_prose_or_lines"
        ),
    }


def degenerate_text(text: str) -> bool:
    toks = re.findall(r"[A-Za-z0-9_.:-]+", text)
    if len(toks) < 20:
        return False
    return max(Counter(toks).values(), default=0) >= 12


def prepare_input(inst: Instance, renderer: PhiPromptRenderer, model_limit: int | None) -> tuple[list[int], str, str]:
    ids = renderer.render_token_ids(context=inst.context, question=inst.question)
    if model_limit and len(ids) + MAX_NEW_TOKENS > model_limit:
        raise ValueError(f"{inst.instance_id}: Phi rendered input {len(ids)} + generation budget exceeds model limit {model_limit}")
    return ids, sha256_text(renderer.render_text_preview(context=inst.context, question=inst.question)), sha256_ints(ids)


def decode(tok: Any, ids: Sequence[int]) -> str:
    return tok.decode(list(ids), skip_special_tokens=True)


def run_generate(model: Any, input_ids: Sequence[int]) -> tuple[list[int], float, int, int, str]:
    input_tensor = torch.tensor([input_ids], dtype=torch.long, device="cuda")
    attention_mask = torch.ones_like(input_tensor, dtype=torch.long, device="cuda")
    torch.cuda.reset_peak_memory_stats()
    torch.cuda.synchronize()
    start = time.perf_counter()
    with torch.inference_mode():
        output = model.generate(input_ids=input_tensor, attention_mask=attention_mask, **GENERATION_SETTINGS)
    torch.cuda.synchronize()
    latency = time.perf_counter() - start
    generated = output[0, input_tensor.shape[1]:].detach().cpu().tolist()
    peak_alloc = int(torch.cuda.max_memory_allocated())
    peak_reserved = int(torch.cuda.max_memory_reserved())
    cache_name = "DynamicCache"
    try:
        with torch.inference_mode():
            small = model(
                input_ids=input_tensor[:, : min(16, input_tensor.shape[1])],
                attention_mask=attention_mask[:, : min(16, input_tensor.shape[1])],
                use_cache=True,
            )
        pkv = getattr(small, "past_key_values", None)
        cache_name = pkv.__class__.__name__ if pkv is not None else None
        del small
    except Exception:
        pass
    del input_tensor, attention_mask, output
    return generated, latency, peak_alloc, peak_reserved, cache_name


def base_result(inst: Instance, order_row: dict[str, Any], model_revision: str, input_ids: list[int], prompt_hash: str) -> dict[str, Any]:
    return {
        "run_id": RUN_ID,
        "instance_id": inst.instance_id,
        "question_family_id": inst.question_family_id,
        "domain": inst.domain.value,
        "question_type": inst.question_type.value,
        "context_length_label": inst.context_length_label,
        "answerable": inst.answerable,
        "input_tokens": len(input_ids),
        "rendered_input_tokens": len(input_ids),
        "model_id": MODEL_ID,
        "model_revision": model_revision,
        "tokenizer_id": TOKENIZER_ID,
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": prompt_hash,
        "template_date": TEMPLATE_DATE,
        "response_format_version": RESPONSE_FORMAT_VERSION,
        "generation_settings": GENERATION_SETTINGS,
        "cache_implementation": "DynamicCache",
        "model_dtype": "bfloat16",
        "batch_size": 1,
        "execution_seed": EXECUTION_SEED,
        "execution_order_index": order_row["execution_order_index"],
    }


def success_row(inst: Instance, order_row: dict[str, Any], model_revision: str, input_ids: list[int], prompt_hash: str, prompt_text_hash: str, input_hash: str, generated_ids: list[int], raw_text: str, latency: float, peak_alloc: int, peak_reserved: int, cache_name: str, start_timestamp: str, end_timestamp: str) -> dict[str, Any]:
    row = base_result(inst, order_row, model_revision, input_ids, prompt_hash)
    row.update({
        "generation_start_timestamp": start_timestamp,
        "generation_end_timestamp": end_timestamp,
        "generation_latency_seconds": latency,
        "latency_seconds": latency,
        "rendered_prompt_hash": prompt_text_hash,
        "input_token_ids_hash": input_hash,
        "generated_token_ids": generated_ids,
        "generated_token_ids_hash": sha256_ints(generated_ids),
        "generated_tokens_count": len(generated_ids),
        "generated_tokens_per_second": len(generated_ids) / latency if latency else None,
        "input_tokens_per_second": len(input_ids) / latency if latency else None,
        "peak_allocated_vram_bytes": peak_alloc,
        "peak_reserved_vram_bytes": peak_reserved,
        "observed_cache_class": cache_name,
        "raw_output_text": raw_text,
        "status": "SUCCESS",
        "error_type": None,
        "error_message": None,
    })
    row.update(parse_answer_only(raw_text, len(generated_ids)))
    row.update(ram_metadata())
    return row


def classify_exception(exc: BaseException) -> str:
    msg = str(exc).lower()
    if "cuda" in msg and "out of memory" in msg:
        return "CUDA_OOM"
    if "out of memory" in msg or "cannot allocate memory" in msg:
        return "CPU_OOM"
    if isinstance(exc, ValueError) and "token" in msg:
        return "TOKEN_BUDGET_FAILURE"
    return "GENERATION_ERROR"


def failure_row(inst: Instance, order_row: dict[str, Any], model_revision: str, exc: BaseException, input_ids: list[int] | None, prompt_hash: str, attempt_index: int) -> dict[str, Any]:
    row = base_result(inst, order_row, model_revision, input_ids or [], prompt_hash)
    status = classify_exception(exc)
    row.update({
        "attempt_index": attempt_index,
        "generation_start_timestamp": None,
        "generation_end_timestamp": utc_now(),
        "generation_latency_seconds": None,
        "latency_seconds": None,
        "generated_token_ids": [],
        "generated_token_ids_hash": None,
        "generated_tokens_count": 0,
        "peak_allocated_vram_bytes": torch.cuda.max_memory_allocated() if torch.cuda.is_available() else None,
        "peak_reserved_vram_bytes": torch.cuda.max_memory_reserved() if torch.cuda.is_available() else None,
        "raw_output_text": None,
        "status": status,
        "error_type": type(exc).__name__,
        "error_message": f"{exc}\n{traceback.format_exc()[:4000]}",
        "usable_answer_output": False,
        "format_failure": True,
    })
    row.update(ram_metadata())
    return row


def warmup(model: Any, tok: Any) -> dict[str, Any]:
    ids = tok.apply_chat_template([{"role": "user", "content": "Return exactly: ANSWER: ok"}], tokenize=True, add_generation_prompt=True)
    tensor = torch.tensor([_input_ids(ids)], dtype=torch.long, device="cuda")
    attention_mask = torch.ones_like(tensor, dtype=torch.long, device="cuda")
    torch.cuda.synchronize()
    with torch.inference_mode():
        _ = model.generate(input_ids=tensor, attention_mask=attention_mask, do_sample=False, num_beams=1, max_new_tokens=4, use_cache=True)
    torch.cuda.synchronize()
    del tensor, attention_mask
    torch.cuda.empty_cache()
    return {"performed": True, "max_new_tokens": 4, "timestamp": utc_now()}


def build_execution_order(instances: Sequence[Instance], mode: str) -> list[dict[str, Any]]:
    if mode == "preflight":
        selected = []
        for label in CONTEXT_LABELS:
            selected.append(next(inst for inst in instances if inst.context_length_label == label))
    elif mode == "smoke":
        families = []
        seen = set()
        for inst in instances:
            if inst.question_family_id not in seen:
                seen.add(inst.question_family_id)
                families.append(inst.question_family_id)
            if len(families) == 10:
                break
        selected = [inst for inst in instances if inst.question_family_id in set(families)]
    else:
        selected = list(instances)
        random.Random(EXECUTION_SEED).shuffle(selected)
    return [{"execution_order_index": idx, "instance_id": inst.instance_id} for idx, inst in enumerate(selected)]


def completed_ids(results_path: Path, failures_path: Path) -> set[str]:
    ids: set[str] = set()
    for path in [results_path, failures_path]:
        if path.exists():
            for row in iter_jsonl(path):
                ids.add(row["instance_id"])
    return ids


def verify_prompt_budget(instances: Sequence[Instance], renderer: PhiPromptRenderer, out_dir: Path, model_limit: int | None) -> dict[str, Any]:
    rows = []
    for idx, inst in enumerate(instances, 1):
        ids = renderer.render_token_ids(context=inst.context, question=inst.question)
        rows.append({
            "instance_id": inst.instance_id,
            "context_length_label": inst.context_length_label,
            "source_llama_rendered_input_tokens": inst.rendered_input_tokens_actual,
            "Phi_rendered_input_tokens": len(ids),
            "fits_model_limit": (not model_limit) or (len(ids) + MAX_NEW_TOKENS <= model_limit),
        })
        if idx % 250 == 0:
            print(f"Phi prompt counted {idx}/{len(instances)}", flush=True)
    summary = {
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": renderer.prompt_hash,
        "instances": len(rows),
        "model_context_limit": model_limit,
        "overflow_count": sum(not r["fits_model_limit"] for r in rows),
        "max_rendered_input_tokens": max(r["Phi_rendered_input_tokens"] for r in rows),
        "by_context": token_count_stats(rows),
    }
    write_json(out_dir / "Phi_prompt_budget_verification.json", {"summary": summary, "instances": rows})
    return summary


def token_count_stats(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    import statistics

    out = {}
    for label in CONTEXT_LABELS:
        vals = [int(r.get("Phi_rendered_input_tokens", r.get("input_tokens"))) for r in rows if r["context_length_label"] == label]
        out[label] = {
            "n": len(vals),
            "mean": statistics.mean(vals) if vals else None,
            "median": statistics.median(vals) if vals else None,
            "sd": statistics.stdev(vals) if len(vals) > 1 else 0.0 if vals else None,
            "min": min(vals) if vals else None,
            "max": max(vals) if vals else None,
        }
    return out


def run_instances(model: Any, tok: Any, renderer: PhiPromptRenderer, by_id: dict[str, Instance], order: Sequence[dict[str, Any]], model_revision: str, results_path: Path, failures_path: Path, model_limit: int | None, resume: bool) -> None:
    done = completed_ids(results_path, failures_path) if resume else set()
    total = len(order)
    for row in order:
        iid = row["instance_id"]
        if iid in done:
            continue
        inst = by_id[iid]
        input_ids: list[int] = []
        out: dict[str, Any] | None = None
        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                input_ids, prompt_text_hash, input_hash = prepare_input(inst, renderer, model_limit)
                start_ts = utc_now()
                generated_ids, latency, peak_alloc, peak_reserved, cache_name = run_generate(model, input_ids)
                end_ts = utc_now()
                raw = decode(tok, generated_ids)
                out = success_row(inst, row, model_revision, input_ids, renderer.prompt_hash, prompt_text_hash, input_hash, generated_ids, raw, latency, peak_alloc, peak_reserved, cache_name, start_ts, end_ts)
                append_jsonl(results_path, out)
                break
            except BaseException as exc:  # noqa: BLE001
                out = failure_row(inst, row, model_revision, exc, input_ids, renderer.prompt_hash, attempt)
                if out["status"] != "CUDA_OOM" or attempt == max_attempts:
                    append_jsonl(failures_path, out)
                    break
                gc.collect()
                torch.cuda.empty_cache()
                append_jsonl(failures_path.with_suffix(".attempts.jsonl"), out)
        done.add(iid)
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print(
            f"[{len(done)}/{total}] instance={iid} context={inst.context_length_label} "
            f"input={out.get('input_tokens') if out else None} gen={out.get('generated_tokens_count') if out else None} "
            f"lat={out.get('generation_latency_seconds') if out else None} peak_reserved={out.get('peak_reserved_vram_bytes') if out else None} "
            f"status={out.get('status') if out else None}",
            flush=True,
        )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("")
        return
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    idx = (len(values) - 1) * q
    lo = int(idx)
    hi = min(lo + 1, len(values) - 1)
    frac = idx - lo
    return values[lo] * (1 - frac) + values[hi] * frac


def summarize(result_rows: list[dict[str, Any]], failure_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    import statistics

    rows_by_context: list[dict[str, Any]] = []
    all_rows = result_rows + failure_rows
    for label in CONTEXT_LABELS:
        success = [r for r in result_rows if r["context_length_label"] == label]
        failures = [r for r in failure_rows if r["context_length_label"] == label]
        lat = [float(r["generation_latency_seconds"]) for r in success if r.get("generation_latency_seconds") is not None]
        inputs = [int(r["input_tokens"]) for r in success]
        gen = [int(r["generated_tokens_count"]) for r in success]
        peak_alloc = [(r.get("peak_allocated_vram_bytes") or 0) / (1024 ** 3) for r in success]
        peak_reserved = [(r.get("peak_reserved_vram_bytes") or 0) / (1024 ** 3) for r in success]
        rows_by_context.append({
            "context_length": label,
            "attempted": len(success) + len(failures),
            "runtime_successful": len(success),
            "runtime_failed": len(failures),
            "cuda_oom_count": sum(r.get("status") == "CUDA_OOM" for r in failures),
            "usable_answer_outputs": sum(bool(r.get("usable_answer_output")) for r in success),
            "malformed_outputs": sum(not bool(r.get("usable_answer_output")) for r in success),
            "thinking_trace_outputs": sum(bool(r.get("contains_thinking_trace")) for r in success),
            "hit_128": sum(bool(r.get("hit_max_new_tokens_128")) for r in success),
            "degenerate_outputs": sum(bool(r.get("degenerate_output")) for r in success),
            "mean_input_tokens": statistics.mean(inputs) if inputs else None,
            "min_input_tokens": min(inputs) if inputs else None,
            "median_input_tokens": statistics.median(inputs) if inputs else None,
            "max_input_tokens": max(inputs) if inputs else None,
            "sd_input_tokens": statistics.stdev(inputs) if len(inputs) > 1 else 0.0 if inputs else None,
            "mean_generated_tokens": statistics.mean(gen) if gen else None,
            "median_generated_tokens": statistics.median(gen) if gen else None,
            "mean_latency_seconds": statistics.mean(lat) if lat else None,
            "median_latency_seconds": statistics.median(lat) if lat else None,
            "std_latency_seconds": statistics.stdev(lat) if len(lat) > 1 else 0.0 if lat else None,
            "p95_latency_seconds": percentile(lat, 0.95),
            "total_generation_seconds": sum(lat),
            "mean_peak_allocated_vram_gib": statistics.mean(peak_alloc) if peak_alloc else None,
            "max_peak_allocated_vram_gib": max(peak_alloc) if peak_alloc else None,
            "mean_peak_reserved_vram_gib": statistics.mean(peak_reserved) if peak_reserved else None,
            "max_peak_reserved_vram_gib": max(peak_reserved) if peak_reserved else None,
        })
    structural = {
        "overall": {
            "attempted": len(all_rows),
            "runtime_successful": len(result_rows),
            "runtime_failed": len(failure_rows),
            "cuda_oom_count": sum(r.get("status") == "CUDA_OOM" for r in failure_rows),
            "usable_answer_outputs": sum(bool(r.get("usable_answer_output")) for r in result_rows),
            "malformed_outputs": sum(not bool(r.get("usable_answer_output")) for r in result_rows),
            "thinking_trace_outputs": sum(bool(r.get("contains_thinking_trace")) for r in result_rows),
            "hit_128": sum(bool(r.get("hit_max_new_tokens_128")) for r in result_rows),
            "degenerate_outputs": sum(bool(r.get("degenerate_output")) for r in result_rows),
            "malformed_patterns": dict(Counter(r.get("malformed_output_pattern") for r in result_rows)),
        },
        "by_context": rows_by_context,
    }
    return rows_by_context, structural


def write_environment(out_dir: Path, model_revision: str, gate: dict[str, Any], runner_hash: str, model_meta: dict[str, Any], renderer: PhiPromptRenderer) -> None:
    import tokenizers
    import transformers

    env = {
        "run_id": RUN_ID,
        "created_at": utc_now(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "hostname": platform.node(),
        "torch_version": torch.__version__,
        "transformers_version": transformers.__version__,
        "transformers_commit": getattr(transformers, "__commit__", None),
        "tokenizers_version": tokenizers.__version__,
        "cuda_runtime_version": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
        "gpu": gpu_metadata(),
        "ram": ram_metadata(),
        "git_commit": git_commit(Path.cwd()),
        "git_dirty_status": subprocess.run(["git", "status", "--short"], capture_output=True, text=True, check=False).stdout,
        "model_id": MODEL_ID,
        "model_revision": model_revision,
        "tokenizer_id": TOKENIZER_ID,
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": renderer.prompt_hash,
        "template_date": TEMPLATE_DATE,
        "response_format_version": RESPONSE_FORMAT_VERSION,
        "response_format_instructions": RESPONSE_FORMAT_INSTRUCTIONS,
        "generation_settings": GENERATION_SETTINGS,
        "cache_implementation": "DynamicCache",
        "model_dtype": "bfloat16",
        "no_quantization": True,
        "no_offloading": True,
        "no_sampling": True,
        "no_thinking_mode": True,
        "dataset_path": str(DATASET_DIR / "instances.jsonl"),
        "dataset_hash": gate["dataset_hash"],
        "runner_code_hash": runner_hash,
        "model_metadata": model_meta,
        "package_environment": package_environment(),
    }
    write_json(out_dir / "environment.json", env)


def integrity_report(instances: Sequence[Instance], result_rows: list[dict[str, Any]], failure_rows: list[dict[str, Any]], gate: dict[str, Any], expected_count: int, renderer: PhiPromptRenderer) -> dict[str, Any]:
    expected = {inst.instance_id for inst in instances}
    if expected_count != len(instances):
        expected = {r["instance_id"] for r in result_rows + failure_rows}
    rows = result_rows + failure_rows
    ids = [r["instance_id"] for r in rows]
    duplicate_ids = [iid for iid, n in Counter(ids).items() if n > 1]
    problems = []
    if len(rows) != expected_count:
        problems.append({"kind": "attempt_count", "expected": expected_count, "actual": len(rows)})
    if set(ids) != expected:
        problems.append({"kind": "instance_accounting", "missing": sorted(expected - set(ids))[:50], "extra": sorted(set(ids) - expected)[:50]})
    if duplicate_ids:
        problems.append({"kind": "duplicate_results", "instance_ids": duplicate_ids[:50]})
    if any(r.get("prompt_hash") != renderer.prompt_hash for r in rows):
        problems.append({"kind": "prompt_hash_drift"})
    if any(r.get("model_revision") != MODEL_REVISION for r in rows):
        problems.append({"kind": "model_revision_drift"})
    if any(r.get("model_dtype") != "bfloat16" for r in rows):
        problems.append({"kind": "dtype_drift"})
    if any(r.get("generation_settings") != GENERATION_SETTINGS for r in rows):
        problems.append({"kind": "generation_settings_drift"})
    return {
        "passed": not problems,
        "problems": problems,
        "expected_instances": expected_count,
        "attempted": len(rows),
        "successful": len(result_rows),
        "failed": len(failure_rows),
        "failure_breakdown": dict(Counter(r.get("status") for r in failure_rows)),
        "malformed_outputs": sum(not bool(r.get("usable_answer_output")) for r in result_rows),
        "thinking_trace_outputs": sum(bool(r.get("contains_thinking_trace")) for r in result_rows),
        "hit_128_outputs": sum(bool(r.get("hit_max_new_tokens_128")) for r in result_rows),
        "dataset_hash": gate["dataset_hash"],
        "source_dataset_hash_unchanged": gate["dataset_hash"] == EXPECTED_DATASET_HASH,
        "no_grading_or_statistical_analysis_performed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["preflight", "smoke", "full"], default="full")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    out_dir = OUT_DIR if args.mode == "full" else OUT_DIR / args.mode
    out_dir.mkdir(parents=True, exist_ok=True)
    if not args.resume:
        for p in ["results.jsonl", "failures.jsonl", "failures.attempts.jsonl"]:
            path = out_dir / p
            if path.exists():
                raise SystemExit(f"{path} exists; use --resume or remove the mode directory")

    instances = load_instances()
    gate = verify_dataset(instances)
    write_json(out_dir / "pre_run_dataset_gate.json", gate)
    if not gate["passed"]:
        raise SystemExit(f"dataset gate failed: {gate['failures']}")

    model, tok, _hf_cfg, model_revision, model_meta = load_model_and_tokenizer()
    renderer = PhiPromptRenderer(tok, load_evaluation_prompt())
    model_limit = model_meta.get("model_context_limit")
    budget = verify_prompt_budget(instances, renderer, out_dir, model_limit)
    if budget["overflow_count"]:
        raise SystemExit(f"Phi prompt budget verification failed: {budget}")

    runner_hash = sha256_file(Path(__file__))
    write_environment(out_dir, model_revision, gate, runner_hash, model_meta, renderer)
    write_json(out_dir / "warmup.json", warmup(model, tok))

    order = build_execution_order(instances, args.mode)
    write_json(out_dir / "execution_order.json", {"seed": EXECUTION_SEED, "mode": args.mode, "context_lengths": CONTEXT_LABELS, "order": order})
    write_json(out_dir / "run_manifest.json", {
        "run_id": RUN_ID,
        "mode": args.mode,
        "dataset_path": str(DATASET_DIR / "instances.jsonl"),
        "dataset_hash": gate["dataset_hash"],
        "model_id": MODEL_ID,
        "model_revision": model_revision,
        "tokenizer_id": TOKENIZER_ID,
        "tokenizer_class": model_meta.get("tokenizer_class"),
        "model_class": model_meta.get("model_class"),
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": renderer.prompt_hash,
        "template_date": TEMPLATE_DATE,
        "response_format_version": RESPONSE_FORMAT_VERSION,
        "dtype": "bfloat16",
        "cache_implementation": "DynamicCache",
        "attention_implementation": model_meta.get("attention_implementation"),
        "batch_size": 1,
        "generation_settings": GENERATION_SETTINGS,
        "execution_seed": EXECUTION_SEED,
        "started_at": utc_now(),
        "runner_code_hash": runner_hash,
        "model_metadata": model_meta,
    })

    start = time.perf_counter()
    run_instances(model, tok, renderer, {inst.instance_id: inst for inst in instances}, order, model_revision, out_dir / "results.jsonl", out_dir / "failures.jsonl", model_limit, args.resume)
    wall = time.perf_counter() - start
    if not (out_dir / "failures.jsonl").exists():
        (out_dir / "failures.jsonl").touch()

    result_rows = list(iter_jsonl(out_dir / "results.jsonl")) if (out_dir / "results.jsonl").exists() else []
    failure_rows = list(iter_jsonl(out_dir / "failures.jsonl")) if (out_dir / "failures.jsonl").exists() else []
    timing_rows, structural = summarize(result_rows, failure_rows)
    write_csv(out_dir / "timing_by_context.csv", timing_rows)
    write_json(out_dir / "timing_summary.json", {"rows": timing_rows})
    write_json(out_dir / "structural_output_diagnostics.json", structural)
    integrity = integrity_report(instances, result_rows, failure_rows, gate, len(order), renderer)
    write_json(out_dir / "integrity_report.json", integrity)
    total_sync = sum(r.get("generation_latency_seconds") or 0 for r in result_rows)
    summary = {
        "run_id": RUN_ID,
        "mode": args.mode,
        "expected_instances": len(order),
        "attempted": len(result_rows) + len(failure_rows),
        "successful": len(result_rows),
        "failed": len(failure_rows),
        "failure_breakdown": dict(Counter(r.get("status") for r in failure_rows)),
        "cuda_oom_failures": sum(r.get("status") == "CUDA_OOM" for r in failure_rows),
        "total_synchronized_inference_seconds": total_sync,
        "total_wall_clock_seconds": wall,
        "timing_by_context": timing_rows,
        "structural_output_diagnostics": structural,
        "integrity": integrity,
        "no_grading_or_statistical_analysis_performed": True,
    }
    write_json(out_dir / "run_summary.json", summary)
    return 0 if integrity["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
