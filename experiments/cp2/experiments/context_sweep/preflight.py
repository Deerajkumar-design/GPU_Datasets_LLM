#!/usr/bin/env python3
from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys

from common import config_sha256, ensure_layout, load_config, verify_frozen_artifacts, write_manifest
from stage_dataset import verify_dataset


def main() -> int:
    config = load_config()
    layout = ensure_layout()
    checks: list[dict[str, object]] = []

    def check(name: str, passed: bool, detail: object) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})
        if not passed:
            raise RuntimeError(f"{name}: {detail}")

    try:
        import torch
        import transformers
        from transformers import AutoConfig, AutoTokenizer

        check("frozen artifact hashes", True, verify_frozen_artifacts())
        check("frozen GPU_Datasets benchmark", True, verify_dataset(layout["dataset"]))
        check("Linux runtime", platform.system() == "Linux", platform.platform())
        check("CUDA available", torch.cuda.is_available(), torch.version.cuda)
        check("NCCL available", torch.distributed.is_nccl_available(), torch.distributed.is_nccl_available())
        expected_gpus = config["hardware"]["gpu_count"]
        check("GPU count", torch.cuda.device_count() == expected_gpus, torch.cuda.device_count())
        gpu_details = []
        for index in range(torch.cuda.device_count()):
            name = torch.cuda.get_device_name(index)
            total = torch.cuda.get_device_properties(index).total_memory
            check(f"GPU {index} family", "A100" in name.upper(), name)
            check(
                f"GPU {index} VRAM",
                total >= config["hardware"]["minimum_vram_bytes_per_gpu"],
                total,
            )
            check(f"GPU {index} BF16", torch.cuda.is_bf16_supported(), True)
            with torch.cuda.device(index):
                q = torch.randn((1, 1, 16, 128), device=f"cuda:{index}", dtype=torch.bfloat16)
                flash = torch.ops.aten._scaled_dot_product_flash_attention(
                    q, q, q, 0.0, True, False, scale=128**-0.5
                )
                check(
                    f"GPU {index} Flash Attention with LSE",
                    len(flash) >= 2 and flash[1].dtype == torch.float32,
                    {"outputs": len(flash), "lse_dtype": str(flash[1].dtype)},
                )
            gpu_details.append({"index": index, "name": name, "total_vram": total})
        peer_matrix = [
            [index == peer or torch.cuda.can_device_access_peer(index, peer) for peer in range(expected_gpus)]
            for index in range(expected_gpus)
        ]
        check("GPU peer access", all(all(row) for row in peer_matrix), peer_matrix)
        check("Python version", platform.python_version().startswith("3.12."), platform.python_version())
        check("PyTorch version", torch.__version__ == config["software"]["torch"], torch.__version__)
        check(
            "Transformers version",
            transformers.__version__.startswith(config["software"]["transformers"]),
            transformers.__version__,
        )
        check("CUDA runtime", torch.version.cuda == config["software"]["cuda"], torch.version.cuda)
        check("model directory", layout["model"].is_dir(), str(layout["model"]))
        check("model revision path", layout["model"].name == config["model"]["revision"], layout["model"].name)
        marker_path = layout["model"] / ".pinned_revision.json"
        check("model revision marker", marker_path.is_file(), str(marker_path))
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        check("model revision marker content", marker == config["model"], marker)
        model_config = AutoConfig.from_pretrained(layout["model"], local_files_only=True)
        AutoTokenizer.from_pretrained(layout["model"], local_files_only=True)
        observed_revision = getattr(model_config, "_commit_hash", None)
        check(
            "model revision metadata",
            observed_revision in (None, config["model"]["revision"]),
            observed_revision,
        )
        check("model architecture", model_config.model_type == "qwen2", model_config.model_type)
        free_space = shutil.disk_usage(layout["root"]).free
        check("persistent free space", free_space >= 10 * 1024**3, free_space)
        probe = layout["results"] / ".write-test"
        probe.write_text("ok", encoding="ascii")
        probe.unlink()
        smi = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,driver_version,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=False,
        )
        topology = subprocess.run(
            ["nvidia-smi", "topo", "-m"],
            capture_output=True,
            text=True,
            check=False,
        )
        manifest = {
            "status": "PASS",
            "experiment_id": config["experiment_id"],
            "config_sha256": config_sha256(),
            "checks": checks,
            "gpus": gpu_details,
            "nvidia_smi": smi.stdout.strip() if smi.returncode == 0 else None,
            "nvidia_topology": topology.stdout.strip() if topology.returncode == 0 else None,
            "software": {
                "python": sys.version,
                "torch": torch.__version__,
                "transformers": transformers.__version__,
                "cuda_runtime": torch.version.cuda,
                "nccl": torch.cuda.nccl.version(),
            },
            "model": {
                **config["model"],
                "local_path": str(layout["model"]),
                "observed_revision_metadata": observed_revision,
            },
        }
        write_manifest("preflight.json", manifest)
        print(json.dumps(manifest, indent=2, default=str))
        print("PASS: CONTEXT SWEEP PREFLIGHT")
        return 0
    except Exception as exc:
        write_manifest(
            "preflight.json",
            {
                "status": "FAIL",
                "experiment_id": config["experiment_id"],
                "config_sha256": config_sha256(),
                "checks": checks,
                "error": str(exc),
            },
        )
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
