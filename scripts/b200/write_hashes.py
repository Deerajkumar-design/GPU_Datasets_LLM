#!/usr/bin/env python3
import argparse
import json

from common import MODEL_CHOICES, hash_tree, output_path, paths, selected_models, write_manifest

parser = argparse.ArgumentParser()
parser.add_argument("--model", choices=MODEL_CHOICES, default="all")
args = parser.parse_args()
layout = paths()
validation_path = layout["manifests"] / f"b200_validation_{args.model}_full.json"
if not validation_path.is_file() or json.loads(validation_path.read_text()).get("status") != "PASS":
    raise SystemExit(f"successful full validation manifest is missing: {validation_path}")
hashes = {}
for model in selected_models(args.model):
    root = output_path(model, layout)
    missing = [name for name in ("results.jsonl", "failures.jsonl") if not (root / name).is_file()]
    if missing:
        raise SystemExit(f"{model} raw output artifacts are missing: {missing}")
    hashes[model] = {"root": str(root), "sha256": hash_tree(root)}
manifest = write_manifest(
    f"b200_inference_hashes_{args.model}.json",
    {"status": "PASS", "model_selection": args.model, "models": hashes},
)
print(f"Persistent result hashes: {manifest}")
