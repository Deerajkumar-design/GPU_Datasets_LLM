#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from common import atomic_write_json, ensure_layout, load_config, write_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage or verify the pinned Qwen snapshot.")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    config = load_config()
    layout = ensure_layout()
    model = config["model"]
    destination = layout["model"]
    try:
        if not args.verify_only:
            from huggingface_hub import snapshot_download

            destination.mkdir(parents=True, exist_ok=True)
            snapshot_download(
                repo_id=model["repo"],
                revision=model["revision"],
                local_dir=destination,
                token=None,
            )
            atomic_write_json(
                destination / ".pinned_revision.json",
                {"repo": model["repo"], "revision": model["revision"]},
            )
        if not destination.is_dir():
            raise FileNotFoundError(f"model snapshot is not staged at {destination}")
        marker_path = destination / ".pinned_revision.json"
        if not marker_path.is_file():
            raise RuntimeError(
                f"pinned revision marker is missing: {marker_path}; stage the model online first"
            )
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        if marker != model:
            raise RuntimeError(f"pinned revision marker mismatch: expected {model}, observed {marker}")
        from transformers import AutoConfig, AutoTokenizer

        loaded_config = AutoConfig.from_pretrained(destination, local_files_only=True)
        AutoTokenizer.from_pretrained(destination, local_files_only=True)
        observed = getattr(loaded_config, "_commit_hash", None)
        if observed is not None and observed != model["revision"]:
            raise RuntimeError(
                f"model revision mismatch: expected {model['revision']}, observed {observed}"
            )
        required = ("config.json", ".pinned_revision.json")
        missing = [name for name in required if not (destination / name).is_file()]
        if missing:
            raise RuntimeError(f"staged model is incomplete; missing {missing}")
        manifest = {
            "status": "PASS",
            "model": model,
            "local_path": str(destination),
            "verified_offline": True,
        }
        write_manifest("model_staging.json", manifest)
        print(json.dumps(manifest, indent=2))
        return 0
    except Exception as exc:
        write_manifest(
            "model_staging.json",
            {"status": "FAIL", "model": model, "local_path": str(destination), "error": str(exc)},
        )
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
