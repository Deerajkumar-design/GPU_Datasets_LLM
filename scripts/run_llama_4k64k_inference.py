from __future__ import annotations

import csv
import gc
import hashlib
import json
import os
import platform
import random
import resource
import statistics
import subprocess
import sys
import time
import traceback
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import torch
from transformers import AutoConfig, AutoModelForCausalLM

from longctx_dataset.config import git_commit, load_config
from longctx_dataset.context.tokenizer import get_tokenizer
from longctx_dataset.inference import parse_response_json, sha256_ints, sha256_text
from longctx_dataset.pipeline import families_path, instances_path
from longctx_dataset.prompt_renderer import LLAMA_PROMPT_VERSION, PromptRenderer
from longctx_dataset.schemas import Instance, QuestionFamily
from longctx_dataset.storage.io import iter_jsonl, read_models, write_json


MODEL_ID = "meta-llama/Llama-3.2-3B-Instruct"
MODEL_REVISION = "0cb88a4f764b7a12671c53f0838cd831a0843b95"
TOKENIZER_ID = f"hf:{MODEL_ID}"
PROMPT_VERSION = "llama_chat_v2"
PROMPT_HASH = "14cc206955296997"
TEMPLATE_DATE = "09 Aug 2026"
MAX_NEW_TOKENS = 512
EXECUTION_SEED = 20260809
RUN_ID = "llama32_3b_4k64k_v1"
OUT_DIR = Path("data/inference_llama32_3b_4k64k_v1")
CONFIG_PATH = "config/preproduction_llama32_3b_v2.yaml"
CONTEXT_LABELS = ["4K", "8K", "16K", "32K", "64K"]
GENERATION_SETTINGS = {
    "do_sample": False,
    "num_beams": 1,
    "max_new_tokens": MAX_NEW_TOKENS,
    "use_cache": True,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def read_completed(paths: Sequence[Path]) -> set[str]:
    done: set[str] = set()
    for path in paths:
        if not path.exists():
            continue
        for row in iter_jsonl(path):
            iid = row.get("instance_id")
            if iid:
                done.add(iid)
    return done


def gpu_metadata() -> dict[str, Any]:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            name, total, driver = [part.strip() for part in out.stdout.strip().split(",", 2)]
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
        meta.update(
            {
                "process_rss_bytes": proc.memory_info().rss,
                "available_ram_bytes": vm.available,
                "total_ram_bytes": vm.total,
            }
        )
    except Exception:
        pass
    return meta


def load_instances() -> tuple[Any, list[QuestionFamily], list[Instance]]:
    cfg = load_config(CONFIG_PATH)
    families = read_models(families_path(cfg), QuestionFamily)
    instances = [
        Instance.model_validate(row)
        for row in iter_jsonl(instances_path(cfg))
        if row.get("context_length_label") in CONTEXT_LABELS
    ]
    return cfg, families, instances


def verify_pre_run(cfg: Any, families: Sequence[QuestionFamily], instances: Sequence[Instance]) -> dict[str, Any]:
    counts = Counter(inst.context_length_label for inst in instances)
    family_ids = {fam.question_family_id for fam in families}
    instance_family_ids = {inst.question_family_id for inst in instances}
    failures: list[dict[str, Any]] = []
    if len(families) != 100:
        failures.append({"field": "families", "expected": 100, "actual": len(families)})
    if instance_family_ids != family_ids:
        failures.append(
            {
                "field": "instance_family_ids",
                "missing": sorted(family_ids - instance_family_ids)[:20],
                "extra": sorted(instance_family_ids - family_ids)[:20],
            }
        )
    if len(instances) != 500:
        failures.append({"field": "instances", "expected": 500, "actual": len(instances)})
    for label in CONTEXT_LABELS:
        if counts.get(label) != 100:
            failures.append({"field": f"instances_by_length.{label}", "expected": 100, "actual": counts.get(label, 0)})
    if any(label not in CONTEXT_LABELS for label in counts):
        failures.append({"field": "context_labels", "expected_only": CONTEXT_LABELS, "actual": dict(counts)})
    if cfg.model.id != MODEL_ID:
        failures.append({"field": "model.id", "expected": MODEL_ID, "actual": cfg.model.id})
    if cfg.tokenizer.id != TOKENIZER_ID:
        failures.append({"field": "tokenizer.id", "expected": TOKENIZER_ID, "actual": cfg.tokenizer.id})
    if cfg.model_prompt.template_date != TEMPLATE_DATE:
        failures.append({"field": "template_date", "expected": TEMPLATE_DATE, "actual": cfg.model_prompt.template_date})
    if cfg.model.max_new_tokens != MAX_NEW_TOKENS:
        failures.append({"field": "max_new_tokens", "expected": MAX_NEW_TOKENS, "actual": cfg.model.max_new_tokens})
    if any(inst.context_length_label == "128K" for inst in instances):
        failures.append({"field": "128K", "expected": 0, "actual": "present"})
    return {
        "passed": not failures,
        "failures": failures,
        "families": len(families),
        "instances": len(instances),
        "instances_by_context_length": dict(counts),
    }


def build_execution_order(instances: Sequence[Instance]) -> list[dict[str, Any]]:
    rows = list(instances)
    rng = random.Random(EXECUTION_SEED)
    rng.shuffle(rows)
    return [
        {
            "execution_order_index": idx,
            "instance_id": inst.instance_id,
            "question_family_id": inst.question_family_id,
            "domain": inst.domain.value,
            "question_type": inst.question_type.value,
            "context_length_label": inst.context_length_label,
            "answerable": inst.answerable,
            "rendered_input_tokens_actual": inst.rendered_input_tokens_actual,
        }
        for idx, inst in enumerate(rows)
    ]


def ensure_execution_order(out_dir: Path, instances: Sequence[Instance]) -> list[dict[str, Any]]:
    path = out_dir / "execution_order.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["order"]
    order = build_execution_order(instances)
    write_json(path, {"seed": EXECUTION_SEED, "context_lengths": CONTEXT_LABELS, "order": order})
    return order


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


def prepare_input(inst: Instance, renderer: PromptRenderer) -> tuple[list[int], str, str]:
    if inst.prompt_version != PROMPT_VERSION:
        raise ValueError(f"{inst.instance_id}: prompt_version {inst.prompt_version!r} != {PROMPT_VERSION!r}")
    if inst.prompt_hash != PROMPT_HASH:
        raise ValueError(f"{inst.instance_id}: prompt_hash {inst.prompt_hash!r} != {PROMPT_HASH!r}")
    ids = renderer.render_token_ids(context=inst.context, question=inst.question)
    if len(ids) != inst.rendered_input_tokens_actual:
        raise ValueError(f"{inst.instance_id}: rendered tokens {len(ids)} != metadata {inst.rendered_input_tokens_actual}")
    if len(ids) > 131072 - MAX_NEW_TOKENS:
        raise ValueError(f"{inst.instance_id}: input token budget exceeded: {len(ids)}")
    prompt_text_hash = sha256_text(renderer.render_text_preview(context=inst.context, question=inst.question))
    return ids, prompt_text_hash, sha256_ints(ids)


def decode_output(tok: Any, generated_ids: Sequence[int]) -> str:
    backend = getattr(tok, "_tok", None)
    if backend is None:
        raise RuntimeError("HF tokenizer backend not available for decode")
    return backend.decode(list(generated_ids), skip_special_tokens=True)


def warmup(model: Any) -> dict[str, Any]:
    started = utc_now()
    input_tensor = torch.tensor([[128000, 271, 128009]], dtype=torch.long, device="cuda")
    torch.cuda.synchronize()
    with torch.inference_mode():
        _ = model.generate(
            input_ids=input_tensor,
            do_sample=False,
            num_beams=1,
            max_new_tokens=4,
            use_cache=True,
        )
    torch.cuda.synchronize()
    del input_tensor
    torch.cuda.empty_cache()
    return {"performed": True, "started_at": started, "ended_at": utc_now(), "max_new_tokens": 4}


def base_row(
    *,
    inst: Instance,
    order_row: dict[str, Any],
    model_revision: str,
    input_ids: Sequence[int],
    rendered_prompt_hash: str,
    input_token_ids_hash: str,
    status: str,
    start_ts: str,
    end_ts: str,
    generation_latency_seconds: float | None,
    end_to_end_latency_seconds: float,
) -> dict[str, Any]:
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
        "rendered_prompt_hash": rendered_prompt_hash,
        "input_token_ids_hash": input_token_ids_hash,
        "model_id": MODEL_ID,
        "model_revision": model_revision,
        "tokenizer_id": TOKENIZER_ID,
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": PROMPT_HASH,
        "template_date": TEMPLATE_DATE,
        "generation_settings": GENERATION_SETTINGS,
        "cache_implementation": "DynamicCache",
        "model_dtype": "bfloat16",
        "batch_size": 1,
        "execution_seed": EXECUTION_SEED,
        "execution_order_index": order_row["execution_order_index"],
        "generation_start_timestamp": start_ts,
        "generation_end_timestamp": end_ts,
        "generation_latency_seconds": generation_latency_seconds,
        "latency_seconds": generation_latency_seconds,
        "end_to_end_instance_latency_seconds": end_to_end_latency_seconds,
        "status": status,
    }


def run_one(
    *,
    model: Any,
    tok: Any,
    renderer: PromptRenderer,
    inst: Instance,
    order_row: dict[str, Any],
    model_revision: str,
    results_path: Path,
    failures_path: Path,
) -> dict[str, Any]:
    e2e_start = time.perf_counter()
    input_ids: list[int] = []
    rendered_prompt_hash = ""
    input_token_ids_hash = ""
    gen_start_ts = utc_now()
    gen_end_ts = gen_start_ts
    generation_latency: float | None = None
    try:
        input_ids, rendered_prompt_hash, input_token_ids_hash = prepare_input(inst, renderer)
        input_tensor = torch.tensor([input_ids], dtype=torch.long, device="cuda")
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
        gen_start_ts = utc_now()
        start = time.perf_counter()
        with torch.inference_mode():
            output = model.generate(
                input_ids=input_tensor,
                do_sample=False,
                num_beams=1,
                max_new_tokens=MAX_NEW_TOKENS,
                use_cache=True,
            )
        torch.cuda.synchronize()
        generation_latency = time.perf_counter() - start
        gen_end_ts = utc_now()
        generated_ids = output[0, input_tensor.shape[1] :].detach().cpu().tolist()
        raw_output = decode_output(tok, generated_ids)
        row = base_row(
            inst=inst,
            order_row=order_row,
            model_revision=model_revision,
            input_ids=input_ids,
            rendered_prompt_hash=rendered_prompt_hash,
            input_token_ids_hash=input_token_ids_hash,
            status="SUCCESS",
            start_ts=gen_start_ts,
            end_ts=gen_end_ts,
            generation_latency_seconds=generation_latency,
            end_to_end_latency_seconds=time.perf_counter() - e2e_start,
        )
        row.update(
            {
                "generated_token_ids": generated_ids,
                "generated_token_ids_hash": sha256_ints(generated_ids),
                "generated_tokens_count": len(generated_ids),
                "raw_output_text": raw_output,
                "peak_allocated_vram_bytes": int(torch.cuda.max_memory_allocated()),
                "peak_reserved_vram_bytes": int(torch.cuda.max_memory_reserved()),
                "input_tokens_per_second": len(input_ids) / generation_latency if generation_latency else None,
                "generated_tokens_per_second": len(generated_ids) / generation_latency if generation_latency else None,
                "error_type": None,
                "error_message": None,
            }
        )
        row.update(parse_response_json(raw_output))
        row.update(ram_metadata())
        append_jsonl(results_path, row)
        del input_tensor, output
        return row
    except BaseException as exc:  # noqa: BLE001
        try:
            torch.cuda.synchronize()
        except Exception:
            pass
        gen_end_ts = utc_now()
        msg = str(exc).lower()
        status = "CUDA_OOM" if "cuda" in msg and "out of memory" in msg else "GENERATION_ERROR"
        row = base_row(
            inst=inst,
            order_row=order_row,
            model_revision=model_revision,
            input_ids=input_ids,
            rendered_prompt_hash=rendered_prompt_hash,
            input_token_ids_hash=input_token_ids_hash,
            status=status,
            start_ts=gen_start_ts,
            end_ts=gen_end_ts,
            generation_latency_seconds=generation_latency,
            end_to_end_latency_seconds=time.perf_counter() - e2e_start,
        )
        row.update(
            {
                "generated_token_ids": [],
                "generated_token_ids_hash": None,
                "generated_tokens_count": 0,
                "raw_output_text": None,
                "peak_allocated_vram_bytes": int(torch.cuda.max_memory_allocated()) if torch.cuda.is_available() else None,
                "peak_reserved_vram_bytes": int(torch.cuda.max_memory_reserved()) if torch.cuda.is_available() else None,
                "input_tokens_per_second": None,
                "generated_tokens_per_second": None,
                "json_parse_success": False,
                "parsed_selected_evidence": None,
                "parsed_answer": None,
                "parsed_insufficient_evidence": None,
                "error_type": type(exc).__name__,
                "error_message": f"{exc}\n{traceback.format_exc()[:4000]}",
            }
        )
        row.update(ram_metadata())
        append_jsonl(failures_path, row)
        gc.collect()
        torch.cuda.empty_cache()
        return row


def percentile(values: Sequence[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int((len(ordered) - 1) * p))
    return ordered[idx]


def gib(value: float | int | None) -> float | None:
    return None if value is None else float(value) / (1024**3)


def timing_reports(out_dir: Path) -> dict[str, Any]:
    successes = list(iter_jsonl(out_dir / "results.jsonl")) if (out_dir / "results.jsonl").exists() else []
    failures = list(iter_jsonl(out_dir / "failures.jsonl")) if (out_dir / "failures.jsonl").exists() else []
    by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in successes:
        by_label[row["context_length_label"]].append(row)
    attempted = Counter(row["context_length_label"] for row in successes + failures)
    report_rows = []
    for label in CONTEXT_LABELS:
        rows = by_label.get(label, [])
        lat = [float(row["generation_latency_seconds"]) for row in rows if row.get("generation_latency_seconds") is not None]
        gen = [int(row.get("generated_tokens_count") or 0) for row in rows]
        input_tokens = [int(row.get("input_tokens") or 0) for row in rows]
        gen_tps = [float(row["generated_tokens_per_second"]) for row in rows if row.get("generated_tokens_per_second") is not None]
        alloc = [int(row.get("peak_allocated_vram_bytes") or 0) for row in rows]
        reserved = [int(row.get("peak_reserved_vram_bytes") or 0) for row in rows]
        report_rows.append(
            {
                "context_length": label,
                "attempted": attempted.get(label, 0),
                "successful": len(rows),
                "total_generation_seconds": sum(lat),
                "mean_generation_seconds": statistics.mean(lat) if lat else None,
                "median_generation_seconds": statistics.median(lat) if lat else None,
                "std_generation_seconds": statistics.stdev(lat) if len(lat) > 1 else 0.0 if lat else None,
                "min_generation_seconds": min(lat) if lat else None,
                "max_generation_seconds": max(lat) if lat else None,
                "p90_generation_seconds": percentile(lat, 0.90),
                "p95_generation_seconds": percentile(lat, 0.95),
                "mean_input_tokens": statistics.mean(input_tokens) if input_tokens else None,
                "mean_generated_tokens": statistics.mean(gen) if gen else None,
                "total_generated_tokens": sum(gen),
                "mean_generated_tokens_per_second": statistics.mean(gen_tps) if gen_tps else None,
                "mean_peak_allocated_vram_gib": gib(statistics.mean(alloc)) if alloc else None,
                "max_peak_allocated_vram_gib": gib(max(alloc)) if alloc else None,
                "mean_peak_reserved_vram_gib": gib(statistics.mean(reserved)) if reserved else None,
                "max_peak_reserved_vram_gib": gib(max(reserved)) if reserved else None,
            }
        )
    report = {
        "total_synchronized_inference_seconds": sum(row["total_generation_seconds"] for row in report_rows),
        "rows": report_rows,
    }
    write_json(out_dir / "timing_by_context.json", report)
    with (out_dir / "timing_by_context.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(report_rows[0].keys()))
        writer.writeheader()
        writer.writerows(report_rows)
    return report


def integrity_report(out_dir: Path, instances: Sequence[Instance], order: Sequence[dict[str, Any]]) -> dict[str, Any]:
    successes = list(iter_jsonl(out_dir / "results.jsonl")) if (out_dir / "results.jsonl").exists() else []
    failures = list(iter_jsonl(out_dir / "failures.jsonl")) if (out_dir / "failures.jsonl").exists() else []
    rows = successes + failures
    expected_ids = {inst.instance_id for inst in instances}
    seen_ids = [row.get("instance_id") for row in rows]
    seen_set = set(seen_ids)
    order_by_id = {row["instance_id"]: row["execution_order_index"] for row in order}
    problems = []
    if len(expected_ids) != 500:
        problems.append({"kind": "expected_size", "actual": len(expected_ids)})
    if seen_set != expected_ids:
        problems.append({"kind": "accounting", "missing": sorted(expected_ids - seen_set), "extra": sorted(seen_set - expected_ids)})
    dupes = [iid for iid, count in Counter(seen_ids).items() if count > 1]
    if dupes:
        problems.append({"kind": "duplicate_instance_ids", "instances": dupes})
    if any(row.get("context_length_label") not in CONTEXT_LABELS for row in rows):
        problems.append({"kind": "invalid_context_label"})
    if any(row.get("context_length_label") == "128K" for row in rows):
        problems.append({"kind": "executed_128k"})
    if any(row.get("cache_implementation") != "DynamicCache" for row in rows):
        problems.append({"kind": "cache_drift"})
    if any(row.get("model_dtype") != "bfloat16" for row in rows):
        problems.append({"kind": "dtype_drift"})
    if any(row.get("batch_size") != 1 for row in rows):
        problems.append({"kind": "batch_size_drift"})
    if any(row.get("prompt_version") != PROMPT_VERSION or row.get("prompt_hash") != PROMPT_HASH for row in rows):
        problems.append({"kind": "prompt_drift"})
    if any(row.get("model_revision") != MODEL_REVISION for row in rows):
        problems.append({"kind": "model_revision_drift"})
    if any(row.get("generation_settings") != GENERATION_SETTINGS for row in rows):
        problems.append({"kind": "generation_settings_drift"})
    if any(row.get("input_tokens", 0) != row.get("rendered_input_tokens", 0) for row in rows):
        problems.append({"kind": "input_token_metadata_mismatch"})
    if any(row.get("input_tokens", 0) > 131072 - MAX_NEW_TOKENS for row in rows):
        problems.append({"kind": "token_budget_overflow"})
    if any(row.get("execution_order_index") != order_by_id.get(row.get("instance_id")) for row in rows):
        problems.append({"kind": "execution_order_mismatch"})
    if any(row.get("status") == "SUCCESS" and not row.get("raw_output_text") for row in successes):
        problems.append({"kind": "missing_raw_output"})
    if any(row.get("status") == "SUCCESS" and row.get("generation_latency_seconds") is None for row in successes):
        problems.append({"kind": "missing_generation_latency"})
    report = {
        "passed": not problems,
        "problems": problems,
        "expected_instances": 500,
        "attempted": len(rows),
        "successful": len(successes),
        "failed": len(failures),
        "failure_breakdown": dict(Counter(row.get("status") for row in failures)),
        "context_lengths_executed": sorted(set(row.get("context_length_label") for row in rows)),
        "executed_128k_instances": sum(1 for row in rows if row.get("context_length_label") == "128K"),
        "no_scoring_performed": True,
        "synchronized_cuda_timing": True,
        "truncation_occurred": False,
        "configuration_drift": bool([p for p in problems if "drift" in p["kind"]]),
    }
    write_json(out_dir / "integrity_report.json", report)
    return report


def run_summary(out_dir: Path, timing: dict[str, Any], integrity: dict[str, Any], wall_clock: float) -> dict[str, Any]:
    rows = timing["rows"]
    summary = {
        "run_id": RUN_ID,
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "gpu": gpu_metadata(),
        "dtype": "bfloat16",
        "cache_implementation": "DynamicCache",
        "decoding_configuration": GENERATION_SETTINGS,
        "dataset_path": "data/preproduction_llama32_3b_v2/",
        "context_lengths_run": CONTEXT_LABELS,
        "expected_instances": 500,
        "attempted": integrity["attempted"],
        "successful": integrity["successful"],
        "failed": integrity["failed"],
        "failure_breakdown": integrity["failure_breakdown"],
        "total_synchronized_inference_seconds": timing["total_synchronized_inference_seconds"],
        "total_wall_clock_experiment_seconds": wall_clock,
        "timing_by_context": rows,
        "no_scoring_performed": True,
    }
    write_json(out_dir / "run_summary.json", summary)
    lines = [
        "# Llama 3.2 3B 4K-64K Raw Inference Run",
        "",
        f"- model: `{MODEL_ID}`",
        f"- revision: `{MODEL_REVISION}`",
        "- dtype: `bfloat16`",
        "- cache: `DynamicCache`",
        f"- attempted: `{summary['attempted']}`",
        f"- successful: `{summary['successful']}`",
        f"- failed: `{summary['failed']}`",
        f"- total synchronized inference time: `{summary['total_synchronized_inference_seconds']:.3f}` seconds",
        f"- total wall-clock experiment time: `{wall_clock:.3f}` seconds",
        "",
        "| Context | Success | Total inference time | Mean | Median | P95 | Mean generated tokens | Peak VRAM |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['context_length']} | {row['successful']} | {row['total_generation_seconds']:.3f}s | "
            f"{row['mean_generation_seconds']:.3f}s | {row['median_generation_seconds']:.3f}s | "
            f"{row['p95_generation_seconds']:.3f}s | {row['mean_generated_tokens']:.1f} | "
            f"{row['max_peak_reserved_vram_gib']:.2f} GiB |"
        )
    lines.extend(["", "No scoring or hallucination analysis was performed."])
    (out_dir / "run_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cfg, families, instances = load_instances()
    gate = verify_pre_run(cfg, families, instances)
    write_json(OUT_DIR / "pre_run_gate.json", gate)
    if not gate["passed"]:
        raise SystemExit(f"pre-run gate failed: {gate['failures']}")

    order = ensure_execution_order(OUT_DIR, instances)
    by_id = {inst.instance_id: inst for inst in instances}
    model, tok, resolved_revision = load_model_and_tokenizer(cfg)
    if resolved_revision != MODEL_REVISION:
        raise SystemExit(f"resolved revision {resolved_revision} != expected {MODEL_REVISION}")
    renderer = PromptRenderer(cfg, tok)
    if renderer.prompt_hash != PROMPT_HASH or LLAMA_PROMPT_VERSION != PROMPT_VERSION:
        raise SystemExit("prompt renderer does not match frozen prompt contract")

    env = {
        "run_id": RUN_ID,
        "created_at": utc_now(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "torch_version": torch.__version__,
        "cuda_runtime_version": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
        "transformers_model_revision": resolved_revision,
        "gpu": gpu_metadata(),
        "ram": ram_metadata(),
        "git_commit": git_commit(Path.cwd()),
        "git_dirty_status": subprocess.run(["git", "status", "--short"], capture_output=True, text=True, check=False).stdout,
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "tokenizer_id": TOKENIZER_ID,
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": PROMPT_HASH,
        "template_date": TEMPLATE_DATE,
        "generation_settings": GENERATION_SETTINGS,
        "cache_implementation": "DynamicCache",
        "model_dtype": "bfloat16",
        "local_files_only": True,
    }
    write_json(OUT_DIR / "environment.json", env)
    warm = warmup(model)
    write_json(OUT_DIR / "warmup.json", warm)
    write_json(
        OUT_DIR / "run_manifest.json",
        {
            "run_id": RUN_ID,
            "dataset": "data/preproduction_llama32_3b_v2/",
            "n_instances": len(instances),
            "context_lengths": CONTEXT_LABELS,
            "model_id": MODEL_ID,
            "model_revision": MODEL_REVISION,
            "tokenizer_id": TOKENIZER_ID,
            "prompt_version": PROMPT_VERSION,
            "prompt_hash": PROMPT_HASH,
            "template_date": TEMPLATE_DATE,
            "generation_settings": GENERATION_SETTINGS,
            "cache_implementation": "DynamicCache",
            "model_dtype": "bfloat16",
            "batch_size": 1,
            "execution_seed": EXECUTION_SEED,
            "warmup_performed": True,
        },
    )

    results_path = OUT_DIR / "results.jsonl"
    failures_path = OUT_DIR / "failures.jsonl"
    done = read_completed([results_path, failures_path])
    run_start = time.perf_counter()
    total = len(order)
    for order_row in order:
        iid = order_row["instance_id"]
        if iid in done:
            continue
        inst = by_id[iid]
        row = run_one(
            model=model,
            tok=tok,
            renderer=renderer,
            inst=inst,
            order_row=order_row,
            model_revision=MODEL_REVISION,
            results_path=results_path,
            failures_path=failures_path,
        )
        done.add(iid)
        peak_gib = gib(row.get("peak_reserved_vram_bytes"))
        print(
            f"[{len(done)}/{total}]\n"
            f"instance: {iid}\n"
            f"context: {inst.context_length_label}\n"
            f"input tokens: {row.get('input_tokens'):,}\n"
            f"generated tokens: {row.get('generated_tokens_count')}\n"
            f"inference: {row.get('generation_latency_seconds') if row.get('generation_latency_seconds') is not None else 'NA'} s\n"
            f"peak VRAM: {peak_gib:.2f} GiB\n"
            f"status: {row.get('status')}",
            flush=True,
        )
        if len([r for r in iter_jsonl(failures_path)]) >= 10 if failures_path.exists() else False:
            raise SystemExit("stopping after 10 failures; systemic failure suspected")

    wall_clock = time.perf_counter() - run_start
    timing = timing_reports(OUT_DIR)
    integrity = integrity_report(OUT_DIR, instances, order)
    run_summary(OUT_DIR, timing, integrity, wall_clock)
    return 0 if integrity["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
