#!/usr/bin/env python3
from __future__ import annotations

import os
import platform
import subprocess
import sys

import torch
import transformers

from common import write_manifest


def main() -> int:
    smi = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=name,driver_version,memory.total",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    payload = {
        "status": "STARTED",
        "pod_id": os.environ.get("RUNPOD_POD_ID"),
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python": sys.version,
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "cuda_runtime": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
        "gpu": smi.stdout.strip() if smi.returncode == 0 else None,
    }
    manifest = write_manifest("b200_autorun_start.json", payload)
    print(f"Autorun metadata: {manifest}")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
