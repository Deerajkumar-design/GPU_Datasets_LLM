#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from huggingface_hub import snapshot_download
from transformers import AutoConfig, AutoTokenizer

from common import MODEL_CHOICES, MODELS, ensure_layout, selected_models, write_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--model", choices=MODEL_CHOICES, default="all")
    args = parser.parse_args()
    layout = ensure_layout()
    records = {}
    for name in selected_models(args.model):
        repo, revision = MODELS[name]
        local_dir = layout["models"] / name / revision
        if not args.verify_only:
            snapshot = Path(snapshot_download(
                repo_id=repo,
                revision=revision,
                cache_dir=layout["hf_cache"] / "hub",
                token=os.environ.get("HF_TOKEN"),
            ))
            local_dir.parent.mkdir(parents=True, exist_ok=True)
            if not local_dir.exists():
                local_dir.symlink_to(snapshot, target_is_directory=True)
        if not local_dir.exists():
            raise SystemExit(f"{name}: staged snapshot link is missing: {local_dir}")
        config = AutoConfig.from_pretrained(local_dir, local_files_only=True, trust_remote_code=False)
        tokenizer = AutoTokenizer.from_pretrained(local_dir, local_files_only=True, trust_remote_code=False)
        observed = getattr(config, "_commit_hash", None)
        if observed and observed != revision:
            raise SystemExit(f"{name}: revision mismatch {observed} != {revision}")
        records[name] = {
            "repo": repo,
            "revision": revision,
            "local_path": str(local_dir),
            "config_class": config.__class__.__name__,
            "tokenizer_class": tokenizer.__class__.__name__,
            "verified_offline": True,
        }
    manifest = write_manifest("staged_models.json", {"models": records})
    print(json.dumps(records, indent=2))
    print(f"PASS: exact model snapshots are available offline; manifest={manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
