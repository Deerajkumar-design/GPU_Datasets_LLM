#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys

import torch
import transformers
from transformers import AutoConfig

from common import MODELS, ensure_layout, environment, paths, repo_root, verify_frozen, write_manifest


def main() -> int:
    checks = []

    def check(name: str, passed: bool, detail: object) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})
        if not passed:
            raise RuntimeError(f"{name}: {detail}")

    try:
        layout = ensure_layout()
        hashes = verify_frozen()
        check("frozen hashes", True, hashes)
        check("CUDA available", torch.cuda.is_available(), torch.version.cuda)
        name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else ""
        capability = torch.cuda.get_device_capability(0) if torch.cuda.is_available() else None
        check("B200 detected", "B200" in name.upper(), name)
        check("compute capability", capability == (10, 0), capability)
        check("BF16 supported", torch.cuda.is_bf16_supported(), torch.cuda.is_bf16_supported())
        arches = torch.cuda.get_arch_list()
        check("PyTorch SM100 support", any(arch in arches for arch in ("sm_100", "compute_100")), arches)
        tensor = torch.ones((32, 32), device="cuda", dtype=torch.bfloat16)
        check("BF16 matmul", torch.isfinite(tensor @ tensor).all().item(), "32x32")
        free, total = torch.cuda.mem_get_info()
        check("GPU memory", total >= 150 * 1024**3, {"free": free, "total": total})
        disk = shutil.disk_usage(layout["results"])
        check("persistent disk free", disk.free >= 50 * 1024**3, disk.free)
        probe = layout["results"] / ".preflight-write"
        probe.write_text("ok", encoding="ascii")
        probe.unlink()
        env = environment()
        smi = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=False,
        )
        model_details = {}
        for key, (repo, revision) in MODELS.items():
            cfg = AutoConfig.from_pretrained(repo, revision=revision, local_files_only=True, trust_remote_code=False)
            observed = getattr(cfg, "_commit_hash", None) or revision
            check(f"{key} exact revision", observed == revision, observed)
            model_details[key] = {"repo": repo, "revision": observed}
        manifest = {
            "status": "PASS",
            "checks": checks,
            "gpu": {
                "name": name,
                "count": torch.cuda.device_count(),
                "capability": capability,
                "free_vram": free,
                "total_vram": total,
                "driver": smi.stdout.strip() if smi.returncode == 0 else None,
            },
            "software": {
                "python": sys.version,
                "torch": torch.__version__,
                "cuda_runtime": torch.version.cuda,
                "transformers": transformers.__version__,
            },
            "models": model_details,
        }
        write_manifest("b200_preflight.json", manifest)
        print(json.dumps(manifest, indent=2, default=str))
        print("PASS: static B200 preflight")
        return 0
    except Exception as exc:
        write_manifest("b200_preflight.json", {"status": "FAIL", "checks": checks, "error": str(exc)})
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
