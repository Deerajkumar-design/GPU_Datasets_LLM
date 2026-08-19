from __future__ import annotations

import csv
import gc
import hashlib
import json
import os
import platform
import random
import re
import resource
import statistics
import subprocess
import sys
import time
import traceback
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import torch
from transformers import AutoConfig, AutoModelForCausalLM

from longctx_dataset.config import git_commit, load_config
from longctx_dataset.context.tokenizer import get_tokenizer
from longctx_dataset.inference import sha256_ints, sha256_text
from longctx_dataset.pipeline import families_path, instances_path
from longctx_dataset.prompts import EVALUATION_PROMPT_VERSION, load_evaluation_prompt
from longctx_dataset.prompt_renderer import _input_ids
from longctx_dataset.schemas import Instance, QuestionFamily
from longctx_dataset.storage.io import iter_jsonl, read_models, write_json


MODEL_ID = "meta-llama/Llama-3.2-3B-Instruct"
MODEL_REVISION = "0cb88a4f764b7a12671c53f0838cd831a0843b95"
TOKENIZER_ID = f"hf:{MODEL_ID}"
PROMPT_VERSION = "llama_chat_v4"
RESPONSE_FORMAT_VERSION = "answer_only_line_v1"
TEMPLATE_DATE = "09 Aug 2026"
MAX_NEW_TOKENS = 128
EXECUTION_SEED = 20260810
SMOKE_SEED = 20260810
RUN_ID = "llama32_3b_4k64k_v3"
OUT_DIR = Path("data/inference_llama32_3b_4k64k_v3")
CONFIG_PATH = "config/preproduction_llama32_3b_v2.yaml"
CONTEXT_LABELS = ["4K", "8K", "16K", "32K", "64K"]
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


def prompt_hash(system_prompt: str | None = None) -> str:
    system = system_prompt if system_prompt is not None else load_evaluation_prompt()
    payload = "\n\n".join([
        f"prompt_version={PROMPT_VERSION}",
        f"system_prompt_version={EVALUATION_PROMPT_VERSION}",
        f"template_date={TEMPLATE_DATE}",
        system,
        f"response_format_version={RESPONSE_FORMAT_VERSION}",
        RESPONSE_FORMAT_INSTRUCTIONS,
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


PROMPT_HASH = prompt_hash()


@dataclass(frozen=True)
class CPromptRenderer:
    tokenizer: Any
    system_prompt: str
    prompt_hash: str = PROMPT_HASH

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
            date_string=TEMPLATE_DATE,
        ))

    def render_text_preview(self, *, context: str, question: str) -> str:
        return self.tokenizer.apply_chat_template(
            self.messages(context=context, question=question),
            add_generation_prompt=True,
            tokenize=False,
            date_string=TEMPLATE_DATE,
        )


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def gpu_metadata() -> dict[str, Any]:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            name, total, driver = [p.strip() for p in out.stdout.strip().split(",", 2)]
            return {"gpu_name": name, "gpu_total_vram_mib": int(total), "cuda_driver_version": driver}
    except Exception:
        pass
    return {}


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


def load_dataset() -> tuple[Any, list[QuestionFamily], list[Instance]]:
    cfg = load_config(CONFIG_PATH)
    families = read_models(families_path(cfg), QuestionFamily)
    instances = [
        Instance.model_validate(row)
        for row in iter_jsonl(instances_path(cfg))
        if row.get("context_length_label") in CONTEXT_LABELS
    ]
    return cfg, families, instances


def verify_dataset(cfg: Any, families: Sequence[QuestionFamily], instances: Sequence[Instance]) -> dict[str, Any]:
    counts = Counter(inst.context_length_label for inst in instances)
    failures = []
    if len(families) != 100:
        failures.append({"field": "families", "expected": 100, "actual": len(families)})
    if len(instances) != 500:
        failures.append({"field": "instances", "expected": 500, "actual": len(instances)})
    for label in CONTEXT_LABELS:
        if counts.get(label) != 100:
            failures.append({"field": label, "expected": 100, "actual": counts.get(label, 0)})
    if cfg.model.id != MODEL_ID or cfg.tokenizer.id != TOKENIZER_ID or cfg.model_prompt.template_date != TEMPLATE_DATE:
        failures.append({"field": "model_tokenizer_or_date"})
    return {"passed": not failures, "failures": failures, "instances_by_context": dict(counts)}


def load_model_and_tokenizer(cfg: Any) -> tuple[Any, Any, str]:
    tok = get_tokenizer(cfg.tokenizer)
    hf_cfg = AutoConfig.from_pretrained(MODEL_ID, revision=MODEL_REVISION, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        revision=MODEL_REVISION,
        local_files_only=True,
        dtype=torch.bfloat16,
        use_safetensors=True,
    )
    model.to("cuda")
    model.eval()
    return model, tok, getattr(hf_cfg, "_commit_hash", None) or MODEL_REVISION


def parse_answer_only(raw_text: str, generated_count: int) -> dict[str, Any]:
    text = (raw_text or "").strip()
    answer_match = re.search(r"(?im)^\s*ANSWER:\s*(.+?)\s*$", text)
    contains_answer = bool(answer_match)
    parsed_answer = answer_match.group(1).strip() if answer_match else None
    has_json = "{" in text or "}" in text or re.search(r'"selected_evidence"|"insufficient_evidence"', text) is not None
    has_evidence_id = re.search(r"\bR[A-Z0-9]{8,12}\b", text) is not None
    extra_lines = [ln for ln in text.splitlines() if ln.strip()]
    prose_or_extra = len(extra_lines) > 1 or (extra_lines and not extra_lines[0].lstrip().startswith("ANSWER:"))
    degenerate = _degenerate_text(text)
    hit_limit = generated_count == MAX_NEW_TOKENS
    usable = contains_answer and bool(parsed_answer) and not has_json and not has_evidence_id and not prose_or_extra and not degenerate
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
        "contains_prose_or_extra_lines": prose_or_extra,
        "malformed_output_pattern": (
            "usable_answer_line" if usable else
            "degenerate_generation" if degenerate else
            "missing_answer_prefix" if not contains_answer else
            "empty_answer" if not parsed_answer else
            "unwanted_json_or_evidence" if has_json or has_evidence_id else
            "extra_prose_or_lines"
        ),
    }


def _degenerate_text(text: str) -> bool:
    toks = re.findall(r"[A-Za-z0-9_.:-]+", text)
    if len(toks) < 20:
        return False
    c = Counter(toks)
    return max(c.values(), default=0) >= 12


def prepare_input(inst: Instance, renderer: CPromptRenderer) -> tuple[list[int], str, str]:
    ids = renderer.render_token_ids(context=inst.context, question=inst.question)
    if len(ids) > 131072 - MAX_NEW_TOKENS:
        raise ValueError(f"{inst.instance_id}: input token budget exceeded: {len(ids)}")
    return ids, sha256_text(renderer.render_text_preview(context=inst.context, question=inst.question)), sha256_ints(ids)


def decode(tok: Any, ids: Sequence[int]) -> str:
    backend = getattr(tok, "_tok", None)
    if backend is None:
        raise RuntimeError("HF tokenizer backend unavailable")
    return backend.decode(list(ids), skip_special_tokens=True)


def run_generate(model: Any, input_ids: Sequence[int]) -> tuple[list[int], float, int, int]:
    input_tensor = torch.tensor([input_ids], dtype=torch.long, device="cuda")
    torch.cuda.reset_peak_memory_stats()
    torch.cuda.synchronize()
    start = time.perf_counter()
    with torch.inference_mode():
        output = model.generate(input_ids=input_tensor, do_sample=False, num_beams=1, max_new_tokens=MAX_NEW_TOKENS, use_cache=True)
    torch.cuda.synchronize()
    latency = time.perf_counter() - start
    generated = output[0, input_tensor.shape[1]:].detach().cpu().tolist()
    peak_alloc = int(torch.cuda.max_memory_allocated())
    peak_reserved = int(torch.cuda.max_memory_reserved())
    del input_tensor, output
    return generated, latency, peak_alloc, peak_reserved


def result_row(inst: Instance, order_row: dict[str, Any], model_revision: str, input_ids: list[int], prompt_text_hash: str, input_hash: str, generated_ids: list[int], raw_text: str, latency: float, peak_alloc: int, peak_reserved: int) -> dict[str, Any]:
    checks = parse_answer_only(raw_text, len(generated_ids))
    row = {
        "run_id": RUN_ID,
        "instance_id": inst.instance_id,
        "question_family_id": inst.question_family_id,
        "domain": inst.domain.value,
        "question_type": inst.question_type.value,
        "context_length_label": inst.context_length_label,
        "answerable": inst.answerable,
        "input_tokens": len(input_ids),
        "rendered_input_tokens": len(input_ids),
        "rendered_prompt_hash": prompt_text_hash,
        "input_token_ids_hash": input_hash,
        "model_id": MODEL_ID,
        "model_revision": model_revision,
        "tokenizer_id": TOKENIZER_ID,
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": PROMPT_HASH,
        "template_date": TEMPLATE_DATE,
        "response_format_version": RESPONSE_FORMAT_VERSION,
        "generation_settings": GENERATION_SETTINGS,
        "cache_implementation": "DynamicCache",
        "model_dtype": "bfloat16",
        "batch_size": 1,
        "execution_seed": EXECUTION_SEED,
        "execution_order_index": order_row["execution_order_index"],
        "generation_latency_seconds": latency,
        "latency_seconds": latency,
        "generated_token_ids": generated_ids,
        "generated_token_ids_hash": sha256_ints(generated_ids),
        "generated_tokens_count": len(generated_ids),
        "generated_tokens_per_second": len(generated_ids) / latency if latency else None,
        "peak_allocated_vram_bytes": peak_alloc,
        "peak_reserved_vram_bytes": peak_reserved,
        "raw_output_text": raw_text,
        "status": "SUCCESS",
        "error_type": None,
        "error_message": None,
    }
    row.update(checks)
    row.update(ram_metadata())
    return row


def failure_row(inst: Instance, order_row: dict[str, Any], model_revision: str, exc: BaseException, input_ids: list[int] | None = None) -> dict[str, Any]:
    msg = str(exc).lower()
    status = "CUDA_OOM" if "cuda" in msg and "out of memory" in msg else "GENERATION_ERROR"
    return {
        "run_id": RUN_ID,
        "instance_id": inst.instance_id,
        "question_family_id": inst.question_family_id,
        "domain": inst.domain.value,
        "question_type": inst.question_type.value,
        "context_length_label": inst.context_length_label,
        "answerable": inst.answerable,
        "input_tokens": len(input_ids or []),
        "model_id": MODEL_ID,
        "model_revision": model_revision,
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": PROMPT_HASH,
        "generation_settings": GENERATION_SETTINGS,
        "cache_implementation": "DynamicCache",
        "model_dtype": "bfloat16",
        "batch_size": 1,
        "execution_order_index": order_row["execution_order_index"],
        "generated_tokens_count": 0,
        "raw_output_text": None,
        "status": status,
        "error_type": type(exc).__name__,
        "error_message": f"{exc}\n{traceback.format_exc()[:4000]}",
    }


def smoke_order(instances: Sequence[Instance]) -> list[Instance]:
    selected: list[Instance] = []
    seen: set[str] = set()

    def add(match) -> None:
        for inst in sorted(instances, key=lambda x: x.instance_id):
            if inst.instance_id not in seen and match(inst):
                selected.append(inst)
                seen.add(inst.instance_id)
                return

    for label in CONTEXT_LABELS:
        add(lambda i, label=label: i.context_length_label == label)
    for domain in ["SEC", "FDA", "CLINICAL_TRIALS", "FRED"]:
        add(lambda i, domain=domain: i.domain.value == domain)
    for qtype in ["DIRECT_RETRIEVAL", "RETRIEVAL_CALCULATION", "TEMPORAL_VERSION", "ENTITY_UNIT_BINDING", "UNANSWERABLE"]:
        add(lambda i, qtype=qtype: i.question_type.value == qtype)
    add(lambda i: i.answerable)
    add(lambda i: not i.answerable)
    add(lambda i: i.question_type.value == "RETRIEVAL_CALCULATION")
    pool = list(instances)
    random.Random(SMOKE_SEED).shuffle(pool)
    for inst in pool:
        if len(selected) >= 30:
            break
        if inst.instance_id not in seen:
            selected.append(inst)
            seen.add(inst.instance_id)
    return selected


def build_execution_order(instances: Sequence[Instance]) -> list[dict[str, Any]]:
    rows = list(instances)
    random.Random(EXECUTION_SEED).shuffle(rows)
    return [{"execution_order_index": idx, "instance_id": inst.instance_id} for idx, inst in enumerate(rows)]


def completed_ids(results_path: Path, failures_path: Path) -> set[str]:
    ids = set()
    for path in [results_path, failures_path]:
        if path.exists():
            for row in iter_jsonl(path):
                ids.add(row["instance_id"])
    return ids


def run_instances(model: Any, tok: Any, renderer: CPromptRenderer, by_id: dict[str, Instance], order: Sequence[dict[str, Any]], model_revision: str, results_path: Path, failures_path: Path) -> None:
    done = completed_ids(results_path, failures_path)
    total = len(order)
    for row in order:
        iid = row["instance_id"]
        if iid in done:
            continue
        inst = by_id[iid]
        input_ids: list[int] = []
        try:
            input_ids, prompt_text_hash, input_hash = prepare_input(inst, renderer)
            gen_ids, latency, peak_alloc, peak_reserved = run_generate(model, input_ids)
            raw = decode(tok, gen_ids)
            out = result_row(inst, row, model_revision, input_ids, prompt_text_hash, input_hash, gen_ids, raw, latency, peak_alloc, peak_reserved)
            append_jsonl(results_path, out)
        except BaseException as exc:  # noqa: BLE001
            out = failure_row(inst, row, model_revision, exc, input_ids)
            append_jsonl(failures_path, out)
            gc.collect()
            torch.cuda.empty_cache()
        done.add(iid)
        print(f"[{len(done)}/{total}] {iid} {inst.context_length_label} status={out['status']} usable={out.get('usable_answer_output')} gen={out.get('generated_tokens_count')} lat={out.get('generation_latency_seconds')}", flush=True)


def warmup(model: Any) -> dict[str, Any]:
    t = torch.tensor([[128000, 271, 128009]], dtype=torch.long, device="cuda")
    torch.cuda.synchronize()
    with torch.inference_mode():
        _ = model.generate(input_ids=t, do_sample=False, num_beams=1, max_new_tokens=4, use_cache=True)
    torch.cuda.synchronize()
    del t
    torch.cuda.empty_cache()
    return {"performed": True, "max_new_tokens": 4, "timestamp": utc_now()}


def prompt_budget_report(instances: Sequence[Instance], renderer: CPromptRenderer, out_dir: Path) -> dict[str, Any]:
    rows = []
    for inst in instances:
        ids = renderer.render_token_ids(context=inst.context, question=inst.question)
        rows.append({
            "instance_id": inst.instance_id,
            "context_length_label": inst.context_length_label,
            "v2_rendered_input_tokens": inst.rendered_input_tokens_actual,
            "v4_rendered_input_tokens": len(ids),
            "delta_tokens": len(ids) - (inst.rendered_input_tokens_actual or 0),
            "fits_budget": len(ids) <= 131072 - MAX_NEW_TOKENS,
        })
    summary = {
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": PROMPT_HASH,
        "max_v4_rendered_input_tokens": max(r["v4_rendered_input_tokens"] for r in rows),
        "max_delta_tokens": max(r["delta_tokens"] for r in rows),
        "overflow_count": sum(not r["fits_budget"] for r in rows),
        "by_context": {
            label: {
                "min": min(r["v4_rendered_input_tokens"] for r in rows if r["context_length_label"] == label),
                "mean": statistics.mean(r["v4_rendered_input_tokens"] for r in rows if r["context_length_label"] == label),
                "max": max(r["v4_rendered_input_tokens"] for r in rows if r["context_length_label"] == label),
            }
            for label in CONTEXT_LABELS
        },
    }
    write_json(out_dir / "prompt_budget_report.json", {"summary": summary, "instances": rows})
    return summary


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for label in CONTEXT_LABELS:
        group = [r for r in rows if r["context_length_label"] == label]
        lat = [r["generation_latency_seconds"] for r in group if r.get("generation_latency_seconds") is not None]
        gen = [r["generated_tokens_count"] for r in group]
        out.append({
            "context_length": label,
            "total": len(group),
            "usable_outputs": sum(r.get("usable_answer_output") for r in group),
            "format_failures": sum(not r.get("usable_answer_output") for r in group),
            "hit_128": sum(r.get("hit_max_new_tokens_128") for r in group),
            "degenerate_outputs": sum(r.get("degenerate_output") for r in group),
            "mean_generated_tokens": statistics.mean(gen) if gen else None,
            "mean_inference_seconds": statistics.mean(lat) if lat else None,
            "median_inference_seconds": statistics.median(lat) if lat else None,
            "p95_inference_seconds": sorted(lat)[int((len(lat)-1)*0.95)] if lat else None,
        })
    return out


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_manifest(out_dir: Path, cfg: Any, model_revision: str, instances: Sequence[Instance], gate: dict[str, Any]) -> None:
    env = {
        "run_id": RUN_ID,
        "created_at": utc_now(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "torch_version": torch.__version__,
        "cuda_runtime_version": torch.version.cuda,
        "gpu": gpu_metadata(),
        "ram": ram_metadata(),
        "git_commit": git_commit(Path.cwd()),
        "git_dirty_status": subprocess.run(["git", "status", "--short"], capture_output=True, text=True, check=False).stdout,
        "model_id": MODEL_ID,
        "model_revision": model_revision,
        "tokenizer_id": TOKENIZER_ID,
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": PROMPT_HASH,
        "template_date": TEMPLATE_DATE,
        "response_format_version": RESPONSE_FORMAT_VERSION,
        "response_format_instructions": RESPONSE_FORMAT_INSTRUCTIONS,
        "generation_settings": GENERATION_SETTINGS,
        "cache_implementation": "DynamicCache",
        "model_dtype": "bfloat16",
        "dataset_config": CONFIG_PATH,
    }
    write_json(out_dir / "environment.json", env)
    write_json(out_dir / "run_manifest.json", {
        "run_id": RUN_ID,
        "dataset": "data/preproduction_llama32_3b_v2/",
        "n_instances": len(instances),
        "context_lengths": CONTEXT_LABELS,
        "model_id": MODEL_ID,
        "model_revision": model_revision,
        "tokenizer_id": TOKENIZER_ID,
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": PROMPT_HASH,
        "template_date": TEMPLATE_DATE,
        "response_format_version": RESPONSE_FORMAT_VERSION,
        "generation_settings": GENERATION_SETTINGS,
        "cache_implementation": "DynamicCache",
        "model_dtype": "bfloat16",
        "batch_size": 1,
        "execution_seed": EXECUTION_SEED,
        "pre_run_gate": gate,
    })


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cfg, families, instances = load_dataset()
    gate = verify_dataset(cfg, families, instances)
    write_json(OUT_DIR / "pre_run_gate.json", gate)
    if not gate["passed"]:
        raise SystemExit(f"dataset gate failed: {gate['failures']}")
    model, tok, model_revision = load_model_and_tokenizer(cfg)
    if model_revision != MODEL_REVISION:
        raise SystemExit(f"model revision mismatch: {model_revision}")
    renderer = CPromptRenderer(tokenizer=tok, system_prompt=load_evaluation_prompt())
    budget = prompt_budget_report(instances, renderer, OUT_DIR)
    if budget["overflow_count"]:
        raise SystemExit("v4 prompt budget overflow")
    write_manifest(OUT_DIR, cfg, model_revision, instances, gate)
    write_json(OUT_DIR / "warmup.json", warmup(model))

    by_id = {inst.instance_id: inst for inst in instances}
    smoke_instances = smoke_order(instances)
    smoke_order_rows = [{"execution_order_index": idx, "instance_id": inst.instance_id} for idx, inst in enumerate(smoke_instances)]
    smoke_dir = OUT_DIR / "smoke"
    smoke_dir.mkdir(parents=True, exist_ok=True)
    write_json(smoke_dir / "smoke_order.json", {"seed": SMOKE_SEED, "instances": [r["instance_id"] for r in smoke_order_rows]})
    run_instances(model, tok, renderer, by_id, smoke_order_rows, model_revision, smoke_dir / "results.jsonl", smoke_dir / "failures.jsonl")
    smoke_rows = list(iter_jsonl(smoke_dir / "results.jsonl")) if (smoke_dir / "results.jsonl").exists() else []
    smoke_summary = {
        "sample_size": len(smoke_rows),
        "usable_outputs": sum(r.get("usable_answer_output") for r in smoke_rows),
        "usable_output_rate": (sum(r.get("usable_answer_output") for r in smoke_rows) / len(smoke_rows)) if smoke_rows else None,
        "format_failures": sum(not r.get("usable_answer_output") for r in smoke_rows),
        "degeneration_count": sum(r.get("degenerate_output") for r in smoke_rows),
        "hit_128_count": sum(r.get("hit_max_new_tokens_128") for r in smoke_rows),
        "unwanted_json_or_evidence_count": sum(r.get("contains_unwanted_json") or r.get("contains_evidence_id") for r in smoke_rows),
        "by_context": summarize(smoke_rows),
    }
    smoke_summary["passed"] = (
        smoke_summary["sample_size"] == 30
        and smoke_summary["usable_output_rate"] is not None
        and smoke_summary["usable_output_rate"] >= 0.95
        and smoke_summary["degeneration_count"] == 0
        and smoke_summary["hit_128_count"] == 0
    )
    write_json(smoke_dir / "smoke_summary.json", smoke_summary)
    if not smoke_summary["passed"]:
        write_json(OUT_DIR / "run_summary.json", {"full_run_launched": False, "smoke": smoke_summary, "prompt_version": PROMPT_VERSION, "prompt_hash": PROMPT_HASH})
        raise SystemExit("Experiment C smoke gate failed; stopping before full run")

    order_path = OUT_DIR / "execution_order.json"
    if order_path.exists():
        order = json.loads(order_path.read_text(encoding="utf-8"))["order"]
    else:
        order = build_execution_order(instances)
        write_json(order_path, {"seed": EXECUTION_SEED, "context_lengths": CONTEXT_LABELS, "order": order})
    start = time.perf_counter()
    run_instances(model, tok, renderer, by_id, order, model_revision, OUT_DIR / "results.jsonl", OUT_DIR / "failures.jsonl")
    wall = time.perf_counter() - start
    result_rows = list(iter_jsonl(OUT_DIR / "results.jsonl")) if (OUT_DIR / "results.jsonl").exists() else []
    failure_rows = list(iter_jsonl(OUT_DIR / "failures.jsonl")) if (OUT_DIR / "failures.jsonl").exists() else []
    if not (OUT_DIR / "failures.jsonl").exists():
        (OUT_DIR / "failures.jsonl").touch()
    timing = summarize(result_rows)
    write_csv(OUT_DIR / "timing_by_context.csv", timing)
    write_json(OUT_DIR / "timing_by_context.json", {"rows": timing})
    integrity = {
        "passed": len(result_rows) + len(failure_rows) == 500 and len({r["instance_id"] for r in result_rows + failure_rows}) == 500,
        "expected_instances": 500,
        "attempted": len(result_rows) + len(failure_rows),
        "successful": len(result_rows),
        "failed": len(failure_rows),
        "failure_breakdown": dict(Counter(r.get("status") for r in failure_rows)),
        "experiment_a_untouched": Path("data/inference_llama32_3b_4k64k_v1/results.jsonl").exists(),
        "experiment_b_untouched": Path("data/inference_llama32_3b_4k64k_v2/smoke/results.jsonl").exists(),
        "no_scoring_performed": True,
    }
    write_json(OUT_DIR / "integrity_report.json", integrity)
    summary = {
        "run_id": RUN_ID,
        "full_run_launched": True,
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": PROMPT_HASH,
        "smoke": smoke_summary,
        "successful": len(result_rows),
        "failed": len(failure_rows),
        "total_wall_clock_seconds": wall,
        "timing_by_context": timing,
        "integrity": integrity,
        "no_correctness_or_hallucination_scoring_performed": True,
    }
    write_json(OUT_DIR / "run_summary.json", summary)
    lines = [
        "# Experiment C Llama 4K-64K Raw Inference",
        "",
        f"- prompt: `{PROMPT_VERSION}` / `{PROMPT_HASH}`",
        f"- smoke passed: `{smoke_summary['passed']}`",
        f"- successful: `{len(result_rows)}`",
        f"- failed: `{len(failure_rows)}`",
        "",
        "| Context | Usable | Format failures | Hit 128 | Degenerate | Mean tokens | Mean latency | Median latency | P95 latency |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in timing:
        lines.append(
            f"| {r['context_length']} | {r['usable_outputs']} | {r['format_failures']} | {r['hit_128']} | "
            f"{r['degenerate_outputs']} | {r['mean_generated_tokens']:.1f} | {r['mean_inference_seconds']:.3f}s | "
            f"{r['median_inference_seconds']:.3f}s | {r['p95_inference_seconds']:.3f}s |"
        )
    lines.append("\nNo correctness or hallucination scoring was performed.\n")
    (OUT_DIR / "run_summary.md").write_text("\n".join(lines), encoding="utf-8")
    return 0 if integrity["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
