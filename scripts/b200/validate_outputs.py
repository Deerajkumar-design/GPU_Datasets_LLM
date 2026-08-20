#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path

from common import MODEL_CHOICES, environment, selected_models, write_manifest


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["preflight", "smoke", "full"], required=True)
    parser.add_argument("--model", choices=MODEL_CHOICES, default="all")
    args = parser.parse_args()
    env = environment()
    expected = 1 if args.mode == "preflight" else int(os.environ.get("B200_SMOKE_FAMILIES", "2")) * 6 if args.mode == "smoke" else 3000
    labels = {"4K", "8K", "16K", "32K", "64K", "82K"}
    reports = {}
    output_keys = {"llama": "B200_LLAMA_OUT_DIR", "qwen": "B200_QWEN_OUT_DIR"}
    for model in selected_models(args.model):
        key = output_keys[model]
        root = Path(env[key])
        out = root if args.mode == "full" else root / args.mode
        successes = read_jsonl(out / "results.jsonl")
        failures = read_jsonl(out / "failures.jsonl")
        rows = successes + failures
        ids = [row["instance_id"] for row in rows]
        if len(rows) != expected or len(ids) != len(set(ids)):
            raise SystemExit(f"{key}: accounting failure rows={len(rows)} expected={expected}")
        if args.mode == "smoke" and {row["context_length_label"] for row in rows} != labels:
            raise SystemExit(f"{key}: smoke test did not cover all contexts")
        if failures:
            raise SystemExit(f"{key}: runtime failures: {Counter(row['status'] for row in failures)}")
        if any(not row.get("usable_answer_output") for row in successes):
            raise SystemExit(f"{key}: unusable ANSWER output")
        if any(row.get("hit_max_new_tokens_128") or row.get("output_truncated") for row in successes):
            raise SystemExit(f"{key}: max-token/truncation failure")
        print(
            f"PASS: {key} {args.mode}: {len(successes)} successful, "
            f"{len(failures)} runtime failures, {len(rows)} unique attempted rows"
        )
        reports[model] = {
            "expected": expected,
            "attempted": len(rows),
            "successful": len(successes),
            "runtime_failures": len(failures),
            "output_dir": str(out),
        }
    write_manifest(
        f"b200_validation_{args.model}_{args.mode}.json",
        {"status": "PASS", "model_selection": args.model, "mode": args.mode, "models": reports},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
