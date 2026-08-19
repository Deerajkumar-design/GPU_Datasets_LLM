from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("b200_common", ROOT / "scripts" / "b200" / "common.py")
assert SPEC and SPEC.loader
common = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(common)
sys.path.insert(0, str(ROOT / "scripts" / "b200"))
AUTO_STOP_SPEC = importlib.util.spec_from_file_location(
    "b200_auto_stop", ROOT / "scripts" / "b200" / "auto_stop.py"
)
assert AUTO_STOP_SPEC and AUTO_STOP_SPEC.loader
auto_stop = importlib.util.module_from_spec(AUTO_STOP_SPEC)
AUTO_STOP_SPEC.loader.exec_module(auto_stop)


def test_frozen_artifact_hashes_are_cross_platform_stable():
    assert common.verify_frozen(ROOT) == {
        "benchmark": common.BENCHMARK_HASH,
        "grader": common.GRADER_HASH,
    }


def test_b200_model_revisions_are_immutable_commits():
    for _name, (_repo, revision) in common.MODELS.items():
        assert len(revision) == 40
        int(revision, 16)


def test_b200_paths_are_isolated_from_historical_data(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNPOD_WORKSPACE", str(tmp_path))
    resolved = common.paths()
    assert resolved["results"] == tmp_path / "long-context-reliability" / "results"
    assert ROOT / "data" not in resolved["results"].parents


def _layout(tmp_path: Path) -> dict[str, Path]:
    return {"models": tmp_path / "models"}


def test_qwen_only_does_not_require_llama(tmp_path):
    qwen = common.model_path("qwen", _layout(tmp_path))
    qwen.mkdir(parents=True)
    assert common.verify_selected_model_paths("qwen", _layout(tmp_path)) == {"qwen": qwen}


def test_llama_only_does_not_require_qwen(tmp_path):
    llama = common.model_path("llama", _layout(tmp_path))
    llama.mkdir(parents=True)
    assert common.verify_selected_model_paths("llama", _layout(tmp_path)) == {"llama": llama}


def test_all_requires_both_models(tmp_path):
    common.model_path("qwen", _layout(tmp_path)).mkdir(parents=True)
    with pytest.raises(FileNotFoundError, match="llama model is not staged"):
        common.verify_selected_model_paths("all", _layout(tmp_path))


def test_auto_stop_cannot_request_stop_after_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNPOD_WORKSPACE", str(tmp_path))
    manifests = common.paths()["manifests"]
    manifests.mkdir(parents=True)
    completion = manifests / "b200_inference_complete_qwen.json"
    completion.write_text(json.dumps({
        "status": "FAILED",
        "model_selection": "qwen",
        "hashed_models": ["qwen"],
    }))
    calls = []

    def opener(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("stop request must not be sent")

    with pytest.raises(RuntimeError, match="valid terminal completion"):
        auto_stop.request_stop(
            "qwen",
            env={"RUNPOD_POD_ID": "pod", "RUNPOD_API_KEY": "secret"},
            opener=opener,
        )
    assert calls == []


def test_auto_stop_requests_stop_after_valid_qwen_completion(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNPOD_WORKSPACE", str(tmp_path))
    manifests = common.paths()["manifests"]
    manifests.mkdir(parents=True)
    completion = manifests / "b200_inference_complete_qwen.json"
    completion.write_text(json.dumps({
        "status": "COMPLETE",
        "model_selection": "qwen",
        "hashed_models": ["qwen"],
        "validation": {"qwen": {"attempted": 3000, "expected": 3000}},
    }))
    calls = []

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def opener(request, timeout):
        calls.append((request, timeout))
        return Response()

    auto_stop.request_stop(
        "qwen",
        env={"RUNPOD_POD_ID": "test-pod", "RUNPOD_API_KEY": "test-api-key"},
        opener=opener,
    )
    assert len(calls) == 1
    assert calls[0][0].full_url.endswith("/pods/test-pod/stop")
    assert calls[0][0].get_header("Authorization") == "Bearer test-api-key"


def test_model_selective_launcher_preserves_resume():
    launcher = (ROOT / "scripts" / "b200" / "run_b200_inference.sh").read_text()
    assert "run_llama_500f_6ctx_experiment_d.py --mode full --resume" in launcher
    assert "run_qwen35_2b_experiment_e.py --mode full --resume" in launcher
