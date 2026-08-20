from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts" / "b200"
sys.path.insert(0, str(SCRIPTS))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


common = load_module("b200_common", SCRIPTS / "common.py")
safe_terminate = load_module("b200_safe_terminate", SCRIPTS / "safe_terminate.py")


def test_frozen_artifact_hashes_are_cross_platform_stable():
    assert common.verify_frozen(ROOT) == {
        "benchmark": common.BENCHMARK_HASH,
        "grader": common.GRADER_HASH,
    }


def test_model_revisions_remain_frozen():
    assert common.MODELS == {
        "llama": ("meta-llama/Llama-3.2-3B-Instruct", "0cb88a4f764b7a12671c53f0838cd831a0843b95"),
        "qwen": ("Qwen/Qwen3.5-2B", "15852e8c16360a2fea060d615a32b45270f8a8fc"),
    }


def test_b200_paths_are_isolated_from_historical_data(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNPOD_WORKSPACE", str(tmp_path))
    resolved = common.paths()
    assert resolved["results"] == tmp_path / "long-context-reliability" / "results"
    assert ROOT / "data" not in resolved["results"].parents


def _model_layout(tmp_path: Path) -> dict[str, Path]:
    return {"models": tmp_path / "models"}


def test_qwen_only_does_not_require_llama(tmp_path):
    qwen = common.model_path("qwen", _model_layout(tmp_path))
    qwen.mkdir(parents=True)
    assert common.verify_selected_model_paths("qwen", _model_layout(tmp_path)) == {"qwen": qwen}


def test_llama_only_does_not_require_qwen(tmp_path):
    llama = common.model_path("llama", _model_layout(tmp_path))
    llama.mkdir(parents=True)
    assert common.verify_selected_model_paths("llama", _model_layout(tmp_path)) == {"llama": llama}


def test_all_requires_both_models(tmp_path):
    common.model_path("qwen", _model_layout(tmp_path)).mkdir(parents=True)
    with pytest.raises(FileNotFoundError, match="llama model is not staged"):
        common.verify_selected_model_paths("all", _model_layout(tmp_path))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _persistent_success_fixture(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("RUNPOD_WORKSPACE", str(tmp_path))
    layout = common.ensure_layout()
    models = ("llama", "qwen")
    _write_json(layout["manifests"] / "b200_preflight_all.json", {
        "status": "PASS",
        "models": {name: {} for name in models},
    })
    for mode, expected in (("preflight", 1), ("smoke", 12), ("full", 3000)):
        _write_json(layout["manifests"] / f"b200_validation_all_{mode}.json", {
            "status": "PASS",
            "models": {
                name: {
                    "expected": expected,
                    "attempted": expected,
                    "successful": expected,
                    "runtime_failures": 0,
                }
                for name in models
            },
        })
    hashes = {}
    for name in models:
        output = common.output_path(name, layout)
        output.mkdir(parents=True)
        rows = [json.dumps({"instance_id": f"{name}-{index}"}) for index in range(3000)]
        (output / "results.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")
        (output / "failures.jsonl").write_text("", encoding="utf-8")
        _write_json(output / "integrity_report.json", {"passed": True})
        _write_json(output / "run_manifest.json", {"model_revision": common.MODELS[name][1]})
        hashes[name] = {"root": str(output), "sha256": common.hash_tree(output)}
    _write_json(layout["manifests"] / "b200_inference_hashes_all.json", {
        "status": "PASS",
        "models": hashes,
    })
    _write_json(layout["manifests"] / "b200_inference_complete_all.json", {
        "status": "COMPLETE",
        "model_selection": "all",
        "hashed_models": list(models),
        "validation": {
            name: {
                "expected": 3000,
                "attempted": 3000,
                "successful": 3000,
                "runtime_failures": 0,
            }
            for name in models
        },
    })
    return layout


def test_success_allows_termination(monkeypatch, tmp_path):
    _persistent_success_fixture(monkeypatch, tmp_path)
    monkeypatch.setattr(
        safe_terminate,
        "verify_persistent_success",
        lambda _model: {"verified": True},
    )
    calls = []

    class Response:
        status = 204

        def read(self, _size):
            return b""

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def opener(request, timeout):
        calls.append((request, timeout))
        return Response()

    safe_terminate.terminate_pod(
        "all",
        env={"RUNPOD_POD_ID": "pod-123", "RUNPOD_API_KEY": "secret"},
        opener=opener,
    )
    request, timeout = calls[0]
    assert request.method == "DELETE"
    assert request.full_url.endswith("/pods/pod-123")
    assert request.get_header("Authorization") == "Bearer secret"
    assert timeout == 30


def test_persistent_success_gate_accepts_complete_outputs(monkeypatch, tmp_path):
    _persistent_success_fixture(monkeypatch, tmp_path)
    verified = safe_terminate.verify_persistent_success("all", workspace=tmp_path)
    assert verified["models"] == ["llama", "qwen"]


@pytest.mark.parametrize(
    ("manifest", "error"),
    [
        ("b200_preflight_all.json", "preflight manifest"),
        ("b200_validation_all_smoke.json", "smoke validation manifest"),
    ],
)
def test_failed_preflight_or_smoke_blocks_termination(monkeypatch, tmp_path, manifest, error):
    layout = _persistent_success_fixture(monkeypatch, tmp_path)
    _write_json(layout["manifests"] / manifest, {"status": "FAIL"})
    with pytest.raises(RuntimeError, match=error):
        safe_terminate.verify_persistent_success("all", workspace=tmp_path)


@pytest.mark.parametrize("model", ["llama", "qwen"])
def test_incomplete_model_blocks_termination(monkeypatch, tmp_path, model):
    layout = _persistent_success_fixture(monkeypatch, tmp_path)
    path = layout["manifests"] / "b200_validation_all_full.json"
    validation = json.loads(path.read_text())
    validation["models"][model]["attempted"] = 2999
    _write_json(path, validation)
    with pytest.raises(RuntimeError, match=f"{model} inference is incomplete"):
        safe_terminate.verify_persistent_success("all", workspace=tmp_path)


@pytest.mark.parametrize("model", ["llama", "qwen"])
def test_runtime_failure_blocks_termination(monkeypatch, tmp_path, model):
    layout = _persistent_success_fixture(monkeypatch, tmp_path)
    path = layout["manifests"] / "b200_validation_all_full.json"
    validation = json.loads(path.read_text())
    validation["models"][model]["successful"] = 2999
    validation["models"][model]["runtime_failures"] = 1
    _write_json(path, validation)
    with pytest.raises(RuntimeError, match=f"{model} inference is incomplete"):
        safe_terminate.verify_persistent_success("all", workspace=tmp_path)


def test_missing_manifest_blocks_termination(monkeypatch, tmp_path):
    layout = _persistent_success_fixture(monkeypatch, tmp_path)
    (layout["manifests"] / "b200_inference_hashes_all.json").unlink()
    with pytest.raises(RuntimeError, match="inference hash manifest is missing"):
        safe_terminate.verify_persistent_success("all", workspace=tmp_path)


def test_missing_completion_marker_blocks_termination(monkeypatch, tmp_path):
    layout = _persistent_success_fixture(monkeypatch, tmp_path)
    (layout["manifests"] / "b200_inference_complete_all.json").unlink()
    with pytest.raises(RuntimeError, match="completion marker is missing"):
        safe_terminate.verify_persistent_success("all", workspace=tmp_path)


@pytest.mark.parametrize(
    ("env", "error"),
    [
        ({"RUNPOD_API_KEY": "secret"}, "RUNPOD_POD_ID is missing"),
        ({"RUNPOD_POD_ID": "pod-123"}, "RUNPOD_API_KEY is missing"),
    ],
)
def test_missing_api_credentials_block_termination(monkeypatch, env, error):
    monkeypatch.setattr(safe_terminate, "verify_persistent_success", lambda _model: {})
    with pytest.raises(RuntimeError, match=error):
        safe_terminate.terminate_pod("all", env=env)


def test_resume_does_not_duplicate_outputs():
    launcher = (SCRIPTS / "run_b200_inference.sh").read_text()
    assert "run_llama_500f_6ctx_experiment_d.py --mode full --resume" in launcher
    assert "run_qwen35_2b_experiment_e.py --mode full --resume" in launcher
