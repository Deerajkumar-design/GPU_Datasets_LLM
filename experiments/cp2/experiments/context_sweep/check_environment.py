#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

from common import load_config


def fail(message: str) -> None:
    raise RuntimeError(message)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the pinned CP2 software environment.")
    parser.parse_args()
    config = load_config()
    expected = config["software"]

    if not platform.python_version().startswith(f"{expected['python']}."):
        fail(f"Python must be {expected['python']}.x; observed {platform.python_version()}")

    import torch
    import transformers

    if torch.__version__ != expected["torch"]:
        fail(f"PyTorch must be {expected['torch']}; observed {torch.__version__}")
    if not transformers.__version__.startswith(f"{expected['transformers']}."):
        fail(
            f"Transformers must be {expected['transformers']}.x; "
            f"observed {transformers.__version__}"
        )
    if torch.version.cuda != expected["cuda"]:
        fail(f"PyTorch CUDA runtime must be {expected['cuda']}; observed {torch.version.cuda}")
    if shutil.which("ninja") is None:
        fail("ninja is required to build the CP2 CUDA extension")

    cuda_home = os.environ.get("CUDA_HOME")
    if not cuda_home:
        fail("CUDA_HOME is unset; set it to the CUDA 13.0 toolkit directory")
    nvcc = Path(cuda_home) / "bin" / "nvcc"
    if not nvcc.is_file():
        fail(f"nvcc was not found under CUDA_HOME: {nvcc}")
    completed = subprocess.run(
        [str(nvcc), "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    nvcc_output = f"{completed.stdout}\n{completed.stderr}".strip()
    if completed.returncode != 0:
        fail(f"nvcc failed with exit code {completed.returncode}: {nvcc_output}")
    release = re.search(r"\brelease\s+(\d+\.\d+)", nvcc_output)
    observed_cuda = release.group(1) if release else "unknown"
    if observed_cuda != expected["cuda"]:
        fail(f"nvcc must be CUDA {expected['cuda']}; observed {observed_cuda}")

    print(
        "PASS: CP2 SOFTWARE ENVIRONMENT "
        f"(python={platform.python_version()}, torch={torch.__version__}, "
        f"transformers={transformers.__version__}, cuda={torch.version.cuda}, "
        f"CUDA_HOME={cuda_home})"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
