"""Local Hugging Face inference runner for the validated Llama preproduction dataset.

This module deliberately stops at raw response capture. It does not compare model
outputs with gold answers, score hallucinations, or retry malformed JSON.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import platform
import random
import resource
import subprocess
import sys
import time
import traceback
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .config import PipelineConfig, git_commit, load_config
from .context.tokenizer import get_tokenizer
from .pipeline import families_path, instances_path
from .prompt_renderer import LLAMA_PROMPT_VERSION, PromptRenderer
from .schemas import Instance, QuestionFamily
from .storage.io import iter_jsonl, read_models, write_json

MODEL_ID = "meta-llama/Llama-3.2-3B-Instruct"
TOKENIZER_ID = f"hf:{MODEL_ID}"
PROMPT_VERSION = "llama_chat_v2"
TEMPLATE_DATE = "09 Aug 2026"
PROMPT_HASH = "14cc206955296997"
MAX_NEW_TOKENS = 512
EXECUTION_SEED = 20260809
RUN_ID = "llama32_3b_preproduction_v1"
RESULT_DIR = Path("data/inference_llama32_3b_preproduction_v1")

GENERATION_SETTINGS = {
    "do_sample": False,
    "num_beams": 1,
    "max_new_tokens": MAX_NEW_TOKENS,
    "use_cache": True,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha256_ints(ids: Sequence[int]) -> str:
    payload = ",".join(str(int(i)) for i in ids)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def parse_response_json(text: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {
            "json_parse_success": False,
            "parsed_selected_evidence": None,
            "parsed_answer": None,
            "parsed_insufficient_evidence": None,
        }
    return {
        "json_parse_success": isinstance(parsed, dict),
        "parsed_selected_evidence": parsed.get("selected_evidence") if isinstance(parsed, dict) else None,
        "parsed_answer": parsed.get("answer") if isinstance(parsed, dict) else None,
        "parsed_insufficient_evidence": parsed.get("insufficient_evidence") if isinstance(parsed, dict) else None,
    }


def load_instances(cfg: PipelineConfig) -> List[Instance]:
    return [Instance.model_validate(row) for row in iter_jsonl(instances_path(cfg))]


def dataset_counts(cfg: PipelineConfig) -> Dict[str, Any]:
    families = read_models(families_path(cfg), QuestionFamily)
    instances = load_instances(cfg)
    return {
        "families": len(families),
        "instances": len(instances),
        "families_by_domain": dict(Counter(f.domain.value for f in families)),
        "families_by_question_type": dict(Counter(f.question_type.value for f in families)),
        "families_answerable": sum(1 for f in families if f.answerable),
        "families_unanswerable": sum(1 for f in families if not f.answerable),
        "instances_by_length": dict(Counter(i.context_length_label for i in instances)),
        "max_rendered_input_tokens": max((i.rendered_input_tokens_actual or 0 for i in instances), default=0),
        "min_remaining_context_margin": min((i.remaining_context_margin or 0 for i in instances), default=0),
    }


def verify_dataset_gate(cfg: PipelineConfig) -> Dict[str, Any]:
    counts = dataset_counts(cfg)
    expected = {
        "families": 100,
        "instances": 600,
        "families_by_domain": {"SEC": 25, "FDA": 25, "CLINICAL_TRIALS": 25, "FRED": 25},
        "families_by_question_type": {
            "DIRECT_RETRIEVAL": 20,
            "RETRIEVAL_CALCULATION": 30,
            "TEMPORAL_VERSION": 11,
            "ENTITY_UNIT_BINDING": 19,
            "UNANSWERABLE": 20,
        },
        "families_answerable": 80,
        "families_unanswerable": 20,
    }
    failures = []
    for key, value in expected.items():
        if counts.get(key) != value:
            failures.append({"field": key, "expected": value, "actual": counts.get(key)})
    if cfg.model.id != MODEL_ID:
        failures.append({"field": "model.id", "expected": MODEL_ID, "actual": cfg.model.id})
    if cfg.tokenizer.id != TOKENIZER_ID:
        failures.append({"field": "tokenizer.id", "expected": TOKENIZER_ID, "actual": cfg.tokenizer.id})
    if cfg.model_prompt.template_date != TEMPLATE_DATE:
        failures.append({
            "field": "model_prompt.template_date",
            "expected": TEMPLATE_DATE,
            "actual": cfg.model_prompt.template_date,
        })
    if cfg.model.max_new_tokens != MAX_NEW_TOKENS:
        failures.append({"field": "model.max_new_tokens", "expected": MAX_NEW_TOKENS, "actual": cfg.model.max_new_tokens})
    if counts["max_rendered_input_tokens"] > 131072 - MAX_NEW_TOKENS:
        failures.append({
            "field": "max_rendered_input_tokens",
            "expected_lte": 131072 - MAX_NEW_TOKENS,
            "actual": counts["max_rendered_input_tokens"],
        })
    return {"passed": not failures, "failures": failures, "counts": counts}


def build_execution_order(instances: Sequence[Instance], seed: int = EXECUTION_SEED) -> List[Dict[str, Any]]:
    rows = list(instances)
    rng = random.Random(seed)
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


def completed_instance_ids(results_path: Path, failures_path: Path) -> set[str]:
    done = set()
    for path in (results_path, failures_path):
        if not path.exists():
            continue
        for row in iter_jsonl(path):
            iid = row.get("instance_id")
            if iid:
                done.add(iid)
    return done


def safe_run_dir(path: Path, resume: bool) -> None:
    path.mkdir(parents=True, exist_ok=True)
    manifest = path / "run_manifest.json"
    if manifest.exists() and not resume:
        raise SystemExit(f"run directory already exists with manifest: {path}; use --resume")


def get_gpu_metadata() -> Dict[str, Any]:
    meta: Dict[str, Any] = {}
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            name, total, driver = [x.strip() for x in out.stdout.strip().split(",", 2)]
            meta.update({"gpu_name": name, "gpu_total_vram_mib": int(total), "cuda_driver_version": driver})
    except Exception:
        pass
    return meta


def get_ram_metadata() -> Dict[str, Any]:
    meta: Dict[str, Any] = {"process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
    try:
        import psutil  # noqa: PLC0415
        vm = psutil.virtual_memory()
        meta.update({"available_ram_bytes": vm.available, "total_ram_bytes": vm.total})
    except Exception:
        pass
    return meta


def environment_payload(cfg: PipelineConfig, model_revision: Optional[str], local_cache_only: bool) -> Dict[str, Any]:
    import torch  # noqa: PLC0415
    import transformers  # noqa: PLC0415
    import tokenizers  # noqa: PLC0415

    return {
        "run_id": RUN_ID,
        "created_at": utc_now(),
        "python_version": sys.version,
        "platform": platform.platform(),
        "torch_version": torch.__version__,
        "transformers_version": transformers.__version__,
        "tokenizers_version": tokenizers.__version__,
        "cuda_runtime_version": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
        "gpu": get_gpu_metadata(),
        "ram": get_ram_metadata(),
        "git_commit": git_commit(Path.cwd()),
        "git_dirty_status": subprocess.run(["git", "status", "--short"], capture_output=True, text=True).stdout,
        "model_id": MODEL_ID,
        "model_revision": model_revision,
        "tokenizer_id": TOKENIZER_ID,
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": PROMPT_HASH,
        "template_date": TEMPLATE_DATE,
        "generation_settings": GENERATION_SETTINGS,
        "cache_implementation": "offloaded",
        "model_dtype": "bfloat16",
        "local_cache_only": local_cache_only,
        "dataset_config": str(cfg.config_path),
        "dataset_output": str(cfg.out_dir),
    }


def load_model_and_tokenizer(cfg: PipelineConfig, *, local_files_only: bool = True):
    import torch  # noqa: PLC0415
    from transformers import AutoConfig, AutoModelForCausalLM  # noqa: PLC0415

    tok = get_tokenizer(cfg.tokenizer)
    hf_cfg = AutoConfig.from_pretrained(MODEL_ID, local_files_only=local_files_only)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        local_files_only=local_files_only,
        dtype=torch.bfloat16,
        use_safetensors=True,
    )
    model.to("cuda")
    model.eval()
    return model, tok, getattr(hf_cfg, "_commit_hash", None)


@dataclass
class PreparedInput:
    inst: Instance
    input_ids: List[int]
    rendered_prompt_hash: str
    input_token_ids_hash: str


def prepare_input(inst: Instance, renderer: PromptRenderer) -> PreparedInput:
    ids = renderer.render_token_ids(context=inst.context, question=inst.question)
    if len(ids) != inst.rendered_input_tokens_actual:
        raise ValueError(
            f"{inst.instance_id}: rendered token count {len(ids)} != dataset {inst.rendered_input_tokens_actual}"
        )
    if renderer.prompt_hash != inst.prompt_hash:
        raise ValueError(f"{inst.instance_id}: prompt hash {renderer.prompt_hash} != dataset {inst.prompt_hash}")
    return PreparedInput(
        inst=inst,
        input_ids=ids,
        rendered_prompt_hash=sha256_text(renderer.render_text_preview(context=inst.context, question=inst.question)),
        input_token_ids_hash=sha256_ints(ids),
    )


def generate_one(
    model: Any,
    prepared: PreparedInput,
    *,
    cache_implementation: str,
    max_new_tokens: int = MAX_NEW_TOKENS,
) -> Dict[str, Any]:
    import torch  # noqa: PLC0415

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    input_tensor = torch.tensor([prepared.input_ids], dtype=torch.long, device="cuda")
    with torch.inference_mode():
        output = model.generate(
            input_ids=input_tensor,
            do_sample=False,
            num_beams=1,
            max_new_tokens=max_new_tokens,
            use_cache=True,
            cache_implementation=cache_implementation,
        )
    generated = output[0, input_tensor.shape[1]:].detach().cpu().tolist()
    peak_alloc = torch.cuda.max_memory_allocated() if torch.cuda.is_available() else None
    peak_reserved = torch.cuda.max_memory_reserved() if torch.cuda.is_available() else None
    del input_tensor, output
    return {
        "generated_token_ids": generated,
        "generated_token_ids_hash": sha256_ints(generated),
        "generated_tokens_count": len(generated),
        "gpu_peak_allocated_bytes": peak_alloc,
        "gpu_peak_reserved_bytes": peak_reserved,
    }


def decode_output(tok: Any, generated_ids: Sequence[int]) -> str:
    backend = getattr(tok, "_tok", None)
    if backend is None:
        raise RuntimeError("HF tokenizer backend not available for decode")
    return backend.decode(list(generated_ids), skip_special_tokens=True)


def base_result(
    inst: Instance,
    order_row: Dict[str, Any],
    prepared: PreparedInput,
    *,
    model_revision: Optional[str],
    cache_implementation: str,
    status: str,
    start: str,
    end: str,
    latency: float,
) -> Dict[str, Any]:
    return {
        "run_id": RUN_ID,
        "instance_id": inst.instance_id,
        "question_family_id": inst.question_family_id,
        "domain": inst.domain.value,
        "question_type": inst.question_type.value,
        "context_length_label": inst.context_length_label,
        "model_id": MODEL_ID,
        "model_revision": model_revision,
        "tokenizer_id": TOKENIZER_ID,
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": PROMPT_HASH,
        "input_tokens": len(prepared.input_ids),
        "reserved_generation_tokens": MAX_NEW_TOKENS,
        "generation_settings": GENERATION_SETTINGS,
        "cache_implementation": cache_implementation,
        "model_dtype": "bfloat16",
        "execution_order_index": order_row["execution_order_index"],
        "execution_seed": EXECUTION_SEED,
        "start_timestamp": start,
        "end_timestamp": end,
        "latency_seconds": latency,
        "rendered_prompt_hash": prepared.rendered_prompt_hash,
        "input_token_ids_hash": prepared.input_token_ids_hash,
        "status": status,
    }


def result_success(
    inst: Instance,
    order_row: Dict[str, Any],
    prepared: PreparedInput,
    gen: Dict[str, Any],
    raw_output_text: str,
    *,
    model_revision: Optional[str],
    cache_implementation: str,
    start: str,
    end: str,
    latency: float,
) -> Dict[str, Any]:
    row = base_result(
        inst, order_row, prepared, model_revision=model_revision,
        cache_implementation=cache_implementation, status="SUCCESS", start=start, end=end, latency=latency,
    )
    row.update(gen)
    row["raw_output_text"] = raw_output_text
    row.update(parse_response_json(raw_output_text))
    row.update(get_ram_metadata())
    return row


def result_failure(
    inst: Instance,
    order_row: Dict[str, Any],
    prepared: PreparedInput,
    *,
    model_revision: Optional[str],
    cache_implementation: str,
    status: str,
    error_type: str,
    error_message: str,
    start: str,
    end: str,
    latency: float,
) -> Dict[str, Any]:
    row = base_result(
        inst, order_row, prepared, model_revision=model_revision,
        cache_implementation=cache_implementation, status=status, start=start, end=end, latency=latency,
    )
    row.update({
        "error_type": error_type,
        "error_message": error_message,
        "raw_output_text": None,
        "generated_tokens_count": 0,
        "generated_token_ids": [],
        "generated_token_ids_hash": None,
        "json_parse_success": False,
        "parsed_selected_evidence": None,
        "parsed_answer": None,
        "parsed_insufficient_evidence": None,
    })
    row.update(get_ram_metadata())
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


def write_run_files(cfg: PipelineConfig, out_dir: Path, instances: Sequence[Instance], model_revision: Optional[str]) -> None:
    env = environment_payload(cfg, model_revision, local_cache_only=True)
    write_json(out_dir / "environment.json", env)
    write_json(out_dir / "run_manifest.json", {
        "run_id": RUN_ID,
        "dataset": str(cfg.out_dir),
        "n_instances": len(instances),
        "model_id": MODEL_ID,
        "model_revision": model_revision,
        "tokenizer_id": TOKENIZER_ID,
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": PROMPT_HASH,
        "template_date": TEMPLATE_DATE,
        "generation_settings": GENERATION_SETTINGS,
        "cache_implementation": "offloaded",
        "model_dtype": "bfloat16",
        "execution_seed": EXECUTION_SEED,
        "created_at": utc_now(),
    })


def write_execution_order(out_dir: Path, order: Sequence[Dict[str, Any]]) -> None:
    write_json(out_dir / "execution_order.json", {"seed": EXECUTION_SEED, "order": list(order)})


def select_instance(instances: Sequence[Instance], label: str, family_ids: Optional[set[str]] = None) -> Instance:
    candidates = [i for i in instances if i.context_length_label == label and (family_ids is None or i.question_family_id in family_ids)]
    if not candidates:
        raise ValueError(f"no instance found for label {label}")
    return sorted(candidates, key=lambda i: i.instance_id)[0]


def cache_equivalence(
    cfg: PipelineConfig,
    out_dir: Path,
    model: Any,
    tok: Any,
    renderer: PromptRenderer,
    instances: Sequence[Instance],
    model_revision: Optional[str],
) -> Dict[str, Any]:
    audited = {"SEC_0006", "FDA_0003", "FRED_0007", "CT_0007"}
    chosen = [select_instance(instances, "4K", audited), select_instance(instances, "8K", audited)]
    rows = []
    passed = True
    for idx, inst in enumerate(chosen):
        prepared = prepare_input(inst, renderer)
        dyn = generate_one(model, prepared, cache_implementation="dynamic", max_new_tokens=MAX_NEW_TOKENS)
        off = generate_one(model, prepared, cache_implementation="offloaded", max_new_tokens=MAX_NEW_TOKENS)
        dyn_text = decode_output(tok, dyn["generated_token_ids"])
        off_text = decode_output(tok, off["generated_token_ids"])
        row = {
            "instance_id": inst.instance_id,
            "context_length_label": inst.context_length_label,
            "input_tokens": len(prepared.input_ids),
            "dynamic_cache_generated_token_ids_hash": dyn["generated_token_ids_hash"],
            "offloaded_cache_generated_token_ids_hash": off["generated_token_ids_hash"],
            "token_ids_equal": dyn["generated_token_ids"] == off["generated_token_ids"],
            "decoded_text_equal": dyn_text == off_text,
            "dynamic_output_text": dyn_text,
            "offloaded_output_text": off_text,
        }
        rows.append(row)
        passed = passed and row["token_ids_equal"] and row["decoded_text_equal"]
        gc.collect()
    report = {"passed": passed, "model_revision": model_revision, "instances": rows}
    write_json(out_dir / "cache_equivalence_report.json", report)
    return report


def run_instance(
    model: Any,
    tok: Any,
    renderer: PromptRenderer,
    inst: Instance,
    order_row: Dict[str, Any],
    model_revision: Optional[str],
    results_path: Path,
    failures_path: Path,
    *,
    cache_implementation: str = "offloaded",
) -> Dict[str, Any]:
    start = utc_now()
    t0 = time.time()
    try:
        prepared = prepare_input(inst, renderer)
        if len(prepared.input_ids) > 131072 - MAX_NEW_TOKENS:
            raise ValueError(f"input token budget exceeded: {len(prepared.input_ids)}")
        gen = generate_one(model, prepared, cache_implementation=cache_implementation)
        raw = decode_output(tok, gen["generated_token_ids"])
        end = utc_now()
        row = result_success(
            inst, order_row, prepared, gen, raw, model_revision=model_revision,
            cache_implementation=cache_implementation, start=start, end=end, latency=time.time() - t0,
        )
        append_jsonl(results_path, row)
        return row
    except BaseException as exc:  # noqa: BLE001
        end = utc_now()
        prepared = locals().get("prepared")
        if prepared is None:
            prepared = PreparedInput(inst=inst, input_ids=[], rendered_prompt_hash="", input_token_ids_hash="")
        status = classify_exception(exc)
        row = result_failure(
            inst, order_row, prepared, model_revision=model_revision,
            cache_implementation=cache_implementation, status=status,
            error_type=type(exc).__name__, error_message=f"{exc}\n{traceback.format_exc()[:4000]}",
            start=start, end=end, latency=time.time() - t0,
        )
        append_jsonl(failures_path, row)
        try:
            import torch  # noqa: PLC0415
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
        return row


def hardware_smoke(
    cfg: PipelineConfig,
    out_dir: Path,
    model: Any,
    tok: Any,
    renderer: PromptRenderer,
    instances: Sequence[Instance],
    model_revision: Optional[str],
) -> Dict[str, Any]:
    selected = [
        select_instance(instances, "4K"),
        select_instance(instances, "64K"),
        select_instance(instances, "128K"),
    ]
    tmp_results = out_dir / "smoke_results.jsonl"
    tmp_failures = out_dir / "smoke_failures.jsonl"
    rows = []
    for idx, inst in enumerate(selected):
        row = run_instance(
            model, tok, renderer, inst,
            {"execution_order_index": idx},
            model_revision, tmp_results, tmp_failures,
            cache_implementation="offloaded",
        )
        rows.append(row)
        if row["status"] != "SUCCESS":
            break
    report = {"passed": all(r["status"] == "SUCCESS" for r in rows), "instances": rows}
    write_json(out_dir / "smoke_test_report.json", report)
    return report


def integrity_report(cfg: PipelineConfig, out_dir: Path, instances: Sequence[Instance]) -> Dict[str, Any]:
    order = {r["instance_id"]: r["execution_order_index"] for r in json.loads((out_dir / "execution_order.json").read_text())["order"]}
    result_rows = list(iter_jsonl(out_dir / "results.jsonl")) if (out_dir / "results.jsonl").exists() else []
    failure_rows = list(iter_jsonl(out_dir / "failures.jsonl")) if (out_dir / "failures.jsonl").exists() else []
    all_rows = result_rows + failure_rows
    expected_ids = {i.instance_id for i in instances}
    seen_ids = [r.get("instance_id") for r in all_rows]
    dupes = [iid for iid, n in Counter(seen_ids).items() if n > 1]
    problems = []
    if set(seen_ids) != expected_ids:
        problems.append({"kind": "instance_accounting", "missing": sorted(expected_ids - set(seen_ids))[:20],
                         "extra": sorted(set(seen_ids) - expected_ids)[:20]})
    if dupes:
        problems.append({"kind": "duplicate_attempts", "instances": dupes[:20]})
    for r in all_rows:
        if r.get("execution_order_index") != order.get(r.get("instance_id")):
            problems.append({"kind": "execution_order_mismatch", "instance_id": r.get("instance_id")})
            break
        if r.get("prompt_hash") != PROMPT_HASH:
            problems.append({"kind": "prompt_hash_mismatch", "instance_id": r.get("instance_id")})
            break
        if r.get("input_tokens", 0) > 131072 - MAX_NEW_TOKENS:
            problems.append({"kind": "token_budget_overflow", "instance_id": r.get("instance_id")})
            break
        if r.get("cache_implementation") != "offloaded":
            problems.append({"kind": "cache_drift", "instance_id": r.get("instance_id")})
            break
    report = {
        "passed": not problems,
        "problems": problems,
        "expected_instances": len(instances),
        "attempted": len(all_rows),
        "success": len(result_rows),
        "failed": len(failure_rows),
        "failure_breakdown": dict(Counter(r.get("status") for r in failure_rows)),
    }
    write_json(out_dir / "integrity_report.json", report)
    return report


def summarize_run(out_dir: Path) -> Dict[str, Any]:
    result_rows = list(iter_jsonl(out_dir / "results.jsonl")) if (out_dir / "results.jsonl").exists() else []
    failure_rows = list(iter_jsonl(out_dir / "failures.jsonl")) if (out_dir / "failures.jsonl").exists() else []
    all_rows = result_rows + failure_rows
    by_len = defaultdict(list)
    for r in result_rows:
        by_len[r["context_length_label"]].append(r)
    len_stats = {}
    for label, rows in sorted(by_len.items()):
        lat = sorted(r["latency_seconds"] for r in rows)
        gen = [r.get("generated_tokens_count", 0) for r in rows]
        peak = [r.get("gpu_peak_reserved_bytes") or 0 for r in rows]
        len_stats[label] = {
            "successful": len(rows),
            "mean_latency_seconds": sum(lat) / len(lat) if lat else None,
            "median_latency_seconds": lat[len(lat)//2] if lat else None,
            "mean_generated_tokens": sum(gen) / len(gen) if gen else None,
            "peak_gpu_reserved_bytes": max(peak) if peak else None,
        }
    summary = {
        "run_id": RUN_ID,
        "total_attempted": len(all_rows),
        "successful": len(result_rows),
        "failed": len(failure_rows),
        "failure_breakdown": dict(Counter(r.get("status") for r in failure_rows)),
        "by_context_length": len_stats,
        "generated_at": utc_now(),
    }
    write_json(out_dir / "run_summary.json", summary)
    lines = [
        "# Llama 3.2 3B Preproduction Inference Run Summary",
        "",
        f"- attempted: `{summary['total_attempted']}`",
        f"- successful: `{summary['successful']}`",
        f"- failed: `{summary['failed']}`",
        f"- failure breakdown: `{summary['failure_breakdown']}`",
        "",
        "| context | successful | mean latency s | median latency s | mean generated tokens | peak GPU reserved bytes |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, st in len_stats.items():
        lines.append(
            f"| {label} | {st['successful']} | {st['mean_latency_seconds']:.3f} | "
            f"{st['median_latency_seconds']:.3f} | {st['mean_generated_tokens']:.1f} | "
            f"{st['peak_gpu_reserved_bytes']} |"
        )
    lines.append("")
    lines.append("No correctness scoring, hallucination analysis, or statistical analysis was performed.")
    (out_dir / "run_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def run_full(cfg: PipelineConfig, out_dir: Path, resume: bool = False) -> None:
    safe_run_dir(out_dir, resume)
    instances = load_instances(cfg)
    gate = verify_dataset_gate(cfg)
    write_json(out_dir / "pre_run_dataset_gate.json", gate)
    if not gate["passed"]:
        raise SystemExit(f"dataset gate failed: {gate['failures']}")
    order_path = out_dir / "execution_order.json"
    if order_path.exists():
        order = json.loads(order_path.read_text())["order"]
    else:
        order = build_execution_order(instances)
        write_execution_order(out_dir, order)
    by_id = {i.instance_id: i for i in instances}

    model, tok, model_revision = load_model_and_tokenizer(cfg, local_files_only=True)
    renderer = PromptRenderer(cfg, tok)
    write_run_files(cfg, out_dir, instances, model_revision)

    cache_report = cache_equivalence(cfg, out_dir, model, tok, renderer, instances, model_revision)
    if not cache_report["passed"]:
        raise SystemExit("cache equivalence failed; stopping before full run")
    smoke_report = hardware_smoke(cfg, out_dir, model, tok, renderer, instances, model_revision)
    if not smoke_report["passed"]:
        raise SystemExit("hardware smoke failed; stopping before full run")

    results_path = out_dir / "results.jsonl"
    failures_path = out_dir / "failures.jsonl"
    done = completed_instance_ids(results_path, failures_path)
    total = len(order)
    for row in order:
        iid = row["instance_id"]
        if iid in done:
            continue
        inst = by_id[iid]
        result = run_instance(model, tok, renderer, inst, row, model_revision, results_path, failures_path)
        done.add(iid)
        print(
            f"completed {len(done)}/{total} status={result['status']} "
            f"len={inst.context_length_label} input={result.get('input_tokens')} "
            f"latency={result.get('latency_seconds'):.2f}s "
            f"gpu_peak={result.get('gpu_peak_reserved_bytes')}",
            flush=True,
        )
    integrity_report(cfg, out_dir, instances)
    summarize_run(out_dir)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="config/preproduction_llama32_3b_v2.yaml")
    p.add_argument("--out", default=str(RESULT_DIR))
    p.add_argument("--resume", action="store_true")
    args = p.parse_args(argv)
    cfg = load_config(args.config)
    run_full(cfg, Path(args.out), resume=args.resume)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
