#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
import re
import socket
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import (
    REPO_ROOT,
    append_jsonl,
    atomic_write_json,
    config_sha256,
    dataset_sha256,
    ensure_layout,
    evaluation_prompt,
    experiment_prompt_hash,
    expected_instance_ids,
    git_commit,
    load_config,
    read_jsonl,
    RESPONSE_FORMAT_INSTRUCTIONS,
    selected_instances,
    sha256_file,
    verify_frozen_artifacts,
)
from stage_dataset import verify_dataset


config = load_config()
layout = ensure_layout()
os.environ["CP_MODEL_PATH"] = str(layout["model"])
os.environ["HF_HOME"] = str(layout["hf_cache"])
os.environ["HF_HUB_CACHE"] = str(layout["hf_cache"] / "hub")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
sys.path.insert(0, str(REPO_ROOT))

import torch
import torch.distributed as dist

import cp_infer
from cp_infer import DEV, RANK, WORLD, cp_generate, tok


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha256_ints(ids: list[int]) -> str:
    return hashlib.sha256(",".join(str(value) for value in ids).encode("ascii")).hexdigest()


def prompt_hash() -> str:
    return experiment_prompt_hash()


def render_input(instance: dict[str, Any]) -> tuple[list[int], str]:
    user = "\n\n".join(
        [
            "KNOWLEDGE RECORDS:",
            instance["context"],
            "TARGET QUESTION:",
            instance["question"],
            "OUTPUT FORMAT:",
            RESPONSE_FORMAT_INSTRUCTIONS,
        ]
    )
    messages = [
        {"role": "system", "content": evaluation_prompt()},
        {"role": "user", "content": user},
    ]
    ids = tok.apply_chat_template(messages, add_generation_prompt=True, tokenize=True)
    if ids and isinstance(ids[0], list):
        ids = ids[0]
    rendered = tok.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
    return list(ids), hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def parse_answer(raw_text: str, generated_count: int) -> dict[str, Any]:
    text = (raw_text or "").strip()
    match = re.search(r"(?im)^\s*ANSWER:\s*(.+?)\s*$", text)
    parsed_answer = match.group(1).strip() if match else None
    nonempty_lines = [line for line in text.splitlines() if line.strip()]
    has_json = "{" in text or "}" in text
    has_evidence_id = re.search(r"\bR[A-Z0-9]{8,12}\b", text) is not None
    has_thinking = bool(re.search(r"</?think>", text, flags=re.I))
    tokens = re.findall(r"[A-Za-z0-9_.:-]+", text)
    degenerate = len(tokens) >= 20 and max(Counter(tokens).values(), default=0) >= 12
    extra_lines = len(nonempty_lines) > 1 or (
        bool(nonempty_lines) and not nonempty_lines[0].lstrip().startswith("ANSWER:")
    )
    usable = (
        bool(parsed_answer)
        and not has_json
        and not has_evidence_id
        and not has_thinking
        and not degenerate
        and not extra_lines
    )
    hit_limit = generated_count == config["max_new_tokens"]
    return {
        "contains_answer_prefix": bool(match),
        "parsed_answer": parsed_answer,
        "usable_answer_output": usable,
        "format_failure": not usable,
        "contains_unwanted_json": has_json,
        "contains_evidence_id": has_evidence_id,
        "contains_thinking_trace": has_thinking,
        "degenerate_output": degenerate,
        "contains_prose_or_extra_lines": extra_lines,
        "hit_max_new_tokens_128": hit_limit,
        "output_truncated": hit_limit,
    }


def execution_order(instances: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = list(instances)
    random.Random(config["execution_seed"]).shuffle(rows)
    return [
        {
            "execution_order_index": index,
            "instance_id": row["instance_id"],
            "question_family_id": row["question_family_id"],
            "context_length_label": row["context_length_label"],
        }
        for index, row in enumerate(rows)
    ]


def synchronize_startup(value: Any) -> Any:
    payload = [value if RANK == 0 else None]
    dist.broadcast_object_list(payload, src=0)
    return payload[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("smoke", "full"), default="full")
    parser.add_argument("--smoke-families", type=int, default=2)
    args = parser.parse_args()
    if WORLD != config["hardware"]["gpu_count"]:
        raise RuntimeError(f"world size {WORLD} does not match frozen value {config['hardware']['gpu_count']}")
    verify_frozen_artifacts()
    gate = verify_dataset(layout["dataset"])
    instances = selected_instances(layout["dataset"])
    if args.mode == "smoke":
        family_ids = list(dict.fromkeys(row["question_family_id"] for row in instances))[: args.smoke_families]
        instances = [row for row in instances if row["question_family_id"] in set(family_ids)]
    output = layout["results"] if args.mode == "full" else layout["results"] / "smoke"
    output.mkdir(parents=True, exist_ok=True)
    results_path = output / "results.jsonl"

    if RANK == 0:
        try:
            existing = read_jsonl(results_path)
            ids = [row.get("instance_id") for row in existing]
            if None in ids or len(ids) != len(set(ids)):
                raise RuntimeError("existing results contain a missing or duplicate instance_id")
            expected = expected_instance_ids(instances)
            if set(ids) - expected:
                raise RuntimeError("existing results contain IDs outside this execution mode")
            startup = {"error": None, "completed": set(ids)}
        except Exception as exc:
            startup = {"error": str(exc), "completed": set()}
    else:
        startup = None
    startup = synchronize_startup(startup)
    if startup["error"]:
        raise RuntimeError(startup["error"])
    completed = startup["completed"]

    order_path = output / "execution_order.json"
    if RANK == 0:
        try:
            if order_path.is_file():
                order = json.loads(order_path.read_text(encoding="utf-8"))["order"]
            else:
                order = execution_order(instances)
                atomic_write_json(
                    order_path,
                    {"seed": config["execution_seed"], "mode": args.mode, "order": order},
                )
            if {row["instance_id"] for row in order} != expected_instance_ids(instances):
                raise RuntimeError("execution order does not match selected benchmark instances")
            startup_order = {"error": None, "order": order}
        except Exception as exc:
            startup_order = {"error": str(exc), "order": []}
    else:
        startup_order = None
    startup_order = synchronize_startup(startup_order)
    if startup_order["error"]:
        raise RuntimeError(startup_order["error"])
    order = startup_order["order"]
    by_id = {row["instance_id"]: row for row in instances}

    manifest_path = output / "run_manifest.json"
    current_manifest = {
        "schema_version": 1,
        "experiment_id": config["experiment_id"],
        "mode": args.mode,
        "config": config,
        "config_sha256": config_sha256(),
        "dataset_sha256": dataset_sha256(layout["dataset"]),
        "selected_instances": len(instances),
        "model": config["model"],
        "prompt_hash": prompt_hash(),
        "runner_sha256": sha256_file(Path(__file__), normalize_text=True),
        "attention_source_sha256": sha256_file(REPO_ROOT / "ring_attention.py", normalize_text=True),
    }
    if RANK == 0:
        try:
            if manifest_path.is_file():
                previous = json.loads(manifest_path.read_text(encoding="utf-8"))
                frozen_keys = (
                    "config_sha256",
                    "dataset_sha256",
                    "selected_instances",
                    "model",
                    "prompt_hash",
                    "runner_sha256",
                    "attention_source_sha256",
                )
                drift = [key for key in frozen_keys if previous.get(key) != current_manifest.get(key)]
                if drift:
                    raise RuntimeError(f"resume metadata mismatch: {drift}")
            else:
                atomic_write_json(
                    manifest_path,
                    {
                        **current_manifest,
                        "created_at": utc_now(),
                        "git_commit": git_commit(),
                        "hostname": socket.gethostname(),
                        "platform": platform.platform(),
                        "software": {
                            "python": sys.version,
                            "torch": torch.__version__,
                            "cuda_runtime": torch.version.cuda,
                        },
                        "gpus": [
                            {
                                "rank": index,
                                "name": torch.cuda.get_device_name(index),
                                "total_vram": torch.cuda.get_device_properties(index).total_memory,
                            }
                            for index in range(WORLD)
                        ],
                    },
                )
            manifest_error = None
        except Exception as exc:
            manifest_error = str(exc)
    else:
        manifest_error = None
    manifest_error = synchronize_startup(manifest_error)
    if manifest_error:
        raise RuntimeError(manifest_error)

    torch.manual_seed(config["execution_seed"])
    torch.cuda.manual_seed_all(config["execution_seed"])
    if len(completed) < len(order):
        warmup_ids = tok.apply_chat_template(
            [{"role": "user", "content": "Return exactly: ANSWER: ok"}],
            add_generation_prompt=True,
            tokenize=True,
        )
        cp_generate(torch.tensor([warmup_ids], dtype=torch.long), max_new=4, zigzag=config["zigzag"])
        cp_infer.KV.clear()
        torch.cuda.empty_cache()
        dist.barrier()

    for order_row in order:
        instance_id = order_row["instance_id"]
        if instance_id in completed:
            if RANK == 0:
                print(f"RESUME: skipping {instance_id}", flush=True)
            continue
        instance = by_id[instance_id]
        input_ids, rendered_hash = render_input(instance)
        input_tensor = torch.tensor([input_ids], dtype=torch.long)
        cp_infer.KV.clear()
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(DEV)
        dist.barrier()
        torch.cuda.synchronize(DEV)
        started = utc_now()
        start = time.perf_counter()
        generated = cp_generate(
            input_tensor,
            max_new=config["max_new_tokens"],
            zigzag=config["zigzag"],
        )
        torch.cuda.synchronize(DEV)
        dist.barrier()
        elapsed = time.perf_counter() - start
        peak_allocated = torch.cuda.max_memory_allocated(DEV)
        peak_reserved = torch.cuda.max_memory_reserved(DEV)
        elapsed_by_rank: list[float] = [0.0] * WORLD
        allocated_by_rank: list[int] = [0] * WORLD
        reserved_by_rank: list[int] = [0] * WORLD
        dist.all_gather_object(elapsed_by_rank, elapsed)
        dist.all_gather_object(allocated_by_rank, peak_allocated)
        dist.all_gather_object(reserved_by_rank, peak_reserved)
        if RANK == 0:
            generated_ids = generated[0].detach().cpu().tolist()
            raw = tok.decode(generated_ids, skip_special_tokens=True)
            row = {
                "run_id": config["experiment_id"],
                "instance_id": instance_id,
                "question_family_id": instance["question_family_id"],
                "domain": instance["domain"],
                "question_type": instance["question_type"],
                "context_length_label": instance["context_length_label"],
                "answerable": instance["answerable"],
                "input_tokens": len(input_ids),
                "rendered_input_tokens": len(input_ids),
                "model_id": config["model"]["repo"],
                "model_revision": config["model"]["revision"],
                "prompt_version": config["prompt"]["version"],
                "prompt_hash": prompt_hash(),
                "rendered_prompt_hash": rendered_hash,
                "input_token_ids_hash": sha256_ints(input_ids),
                "response_format_version": config["prompt"]["response_format_version"],
                "generation_settings": config["decoding"],
                "execution_seed": config["execution_seed"],
                "execution_order_index": order_row["execution_order_index"],
                "generated_token_ids": generated_ids,
                "generated_token_ids_hash": sha256_ints(generated_ids),
                "generated_tokens_count": len(generated_ids),
                "raw_output_text": raw,
                "generation_latency_seconds": max(elapsed_by_rank),
                "elapsed_seconds_by_rank": elapsed_by_rank,
                "peak_allocated_vram_bytes": max(allocated_by_rank),
                "peak_allocated_vram_bytes_by_rank": allocated_by_rank,
                "peak_reserved_vram_bytes": max(reserved_by_rank),
                "peak_reserved_vram_bytes_by_rank": reserved_by_rank,
                "generation_start_timestamp": started,
                "generation_end_timestamp": utc_now(),
                "status": "SUCCESS",
            }
            row.update(parse_answer(raw, len(generated_ids)))
            append_jsonl(results_path, row)
            completed.add(instance_id)
            print(
                f"[{len(completed)}/{len(order)}] instance={instance_id} "
                f"context={instance['context_length_label']} input={len(input_ids)} "
                f"latency={max(elapsed_by_rank):.3f}s generated={len(generated_ids)}",
                flush=True,
            )
        dist.barrier()
    if RANK == 0:
        print(f"INFERENCE COMPLETE: {len(completed)}/{len(order)}", flush=True)
    dist.destroy_process_group()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
