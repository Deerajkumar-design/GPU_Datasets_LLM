from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("b200_common", ROOT / "scripts" / "b200" / "common.py")
assert SPEC and SPEC.loader
common = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(common)


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
