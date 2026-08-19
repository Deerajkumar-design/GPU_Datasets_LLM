#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

from common import MODEL_CHOICES, paths, selected_models


def completion_gate(model: str, manifest_path: Path) -> dict:
    if not manifest_path.is_file():
        raise RuntimeError(f"completion manifest is missing: {manifest_path}")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("status") != "COMPLETE" or payload.get("model_selection") != model:
        raise RuntimeError("inference has not reached a valid terminal completion state")
    if sorted(payload.get("hashed_models", [])) != sorted(selected_models(model)):
        raise RuntimeError("completion manifest does not hash every selected model")
    for name in selected_models(model):
        report = payload.get("validation", {}).get(name, {})
        if report.get("attempted") != 3000 or report.get("expected") != 3000:
            raise RuntimeError(f"{name} inference is incomplete")
    return payload


def request_stop(
    model: str,
    *,
    env: dict[str, str] | None = None,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> None:
    env = os.environ if env is None else env
    manifest_path = paths()["manifests"] / f"b200_inference_complete_{model}.json"
    completion_gate(model, manifest_path)
    pod_id = env.get("RUNPOD_POD_ID")
    api_key = env.get("RUNPOD_API_KEY")
    if not pod_id or not api_key:
        raise RuntimeError("--auto-stop requires RUNPOD_POD_ID and RUNPOD_API_KEY")
    request = urllib.request.Request(
        f"https://rest.runpod.io/v1/pods/{pod_id}/stop",
        method="POST",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    with opener(request, timeout=30) as response:
        status = getattr(response, "status", None)
        if status is None or not 200 <= status < 300:
            raise RuntimeError(f"RunPod stop request failed with HTTP {status}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=MODEL_CHOICES, required=True)
    args = parser.parse_args()
    try:
        request_stop(args.model)
    except (RuntimeError, OSError, urllib.error.URLError) as exc:
        raise SystemExit(f"AUTO-STOP NOT REQUESTED: {exc}") from exc
    print("RunPod stop request accepted after validated persistent completion.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
