from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
SWEEP = ROOT / "experiments" / "context_sweep"
sys.path.insert(0, str(SWEEP))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


common = load_module("context_sweep_common", SWEEP / "common.py")
staging = load_module("context_sweep_staging", SWEEP / "stage_dataset.py")
validation = load_module("context_sweep_validation", SWEEP / "validate_results.py")
extension = load_module("context_sweep_128k_extension", SWEEP / "build_128k_dataset.py")


def synthetic_instances(families: int = 2) -> list[dict]:
    return [
        {
            "instance_id": f"F{family:04d}_{label}",
            "question_family_id": f"F{family:04d}",
            "domain": "SEC",
            "question_type": "DIRECT_RETRIEVAL",
            "context_length_label": label,
            "answerable": True,
            "context": "record",
            "question": "question",
        }
        for family in range(families)
        for label in ("8K", "16K", "32K")
    ]


def passing_rows(instances: list[dict]) -> list[dict]:
    config = common.load_config()
    return [
        {
            "status": "SUCCESS",
            "instance_id": instance["instance_id"],
            "question_family_id": instance["question_family_id"],
            "domain": instance["domain"],
            "question_type": instance["question_type"],
            "context_length_label": instance["context_length_label"],
            "answerable": instance["answerable"],
            "model_id": config["model"]["repo"],
            "model_revision": config["model"]["revision"],
            "prompt_version": config["prompt"]["version"],
            "prompt_hash": common.experiment_prompt_hash(),
            "response_format_version": config["prompt"]["response_format_version"],
            "generation_settings": config["decoding"],
            "execution_seed": config["execution_seed"],
            "input_tokens": 8000,
            "generated_tokens_count": 10,
            "raw_output_text": "ANSWER: generated answer",
            "usable_answer_output": True,
            "hit_max_new_tokens_128": False,
            "generation_latency_seconds": 1.0,
            "peak_reserved_vram_bytes": 1000,
        }
        for instance in instances
    ]


def test_protocol_uses_exact_gpu_datasets_subset():
    config = common.load_config()
    assert config["context_labels"] == ["8K", "16K", "32K"]
    assert config["instances_per_context"] == 500
    assert config["source_benchmark"]["families"] == 500
    assert config["source_benchmark"]["selected_instances"] == 1500
    assert config["source_benchmark"]["dataset_sha256"] == (
        "dc2c4194dedb090198e6883735257908ce274bebc8611b40d958dbd026aa1fe6"
    )
    assert "question" not in config


def test_protocol_pins_cp_model_and_generation():
    config = common.load_config()
    assert config["model"] == {
        "repo": "Qwen/Qwen2.5-7B-Instruct-1M",
        "revision": "e28526f7bb80e2a9c8af03b831a9af3812f18fba",
    }
    assert config["execution_seed"] == 20260812
    assert config["zigzag"] is True
    assert config["decoding"]["strategy"] == "greedy"
    assert config["max_new_tokens"] == 128
    assert config["prompt"]["version"] == "qwen25_cp_chat_v1"
    assert config["prompt"]["system_prompt_version"] == "evaluation_v1"
    assert config["prompt"]["response_format_version"] == "answer_only_line_v1"


def test_frozen_artifact_hashes_match():
    assert common.verify_frozen_artifacts() == common.load_config()["frozen_artifacts"]


def test_complete_subset_rows_validate():
    instances = synthetic_instances()
    report = validation.validate_rows(passing_rows(instances), instances, common.load_config())
    assert report["status"] == "PASS"
    assert report["families"] == 2
    assert report["attempted"] == 6
    assert set(report["contexts"]) == {"8K", "16K", "32K"}


def test_missing_instance_is_rejected():
    instances = synthetic_instances()
    with pytest.raises(RuntimeError, match="instance accounting failure"):
        validation.validate_rows(passing_rows(instances)[:-1], instances, common.load_config())


def test_duplicate_instance_is_rejected():
    instances = synthetic_instances()
    rows = passing_rows(instances)
    rows[-1] = rows[0].copy()
    with pytest.raises(RuntimeError, match="duplicate instance IDs"):
        validation.validate_rows(rows, instances, common.load_config())


def test_malformed_answer_is_rejected():
    instances = synthetic_instances()
    rows = passing_rows(instances)
    rows[0]["usable_answer_output"] = False
    with pytest.raises(RuntimeError, match="usable_answer_output"):
        validation.validate_rows(rows, instances, common.load_config())


def test_dataset_verifier_requires_frozen_hash(monkeypatch, tmp_path):
    (tmp_path / "question_families.jsonl").write_text("{}\n", encoding="utf-8")
    (tmp_path / "instances.jsonl").write_text("{}\n", encoding="utf-8")
    monkeypatch.setitem(common.load_config()["source_benchmark"], "dataset_sha256", "unused")
    with pytest.raises(RuntimeError, match="dataset hash mismatch"):
        staging.verify_dataset(tmp_path)


def test_launcher_runs_smoke_then_full_and_does_not_enable_bucketing():
    launcher = (SWEEP / "run_context_sweep.sh").read_text(encoding="utf-8")
    runner = (SWEEP / "run_context_sweep.py").read_text(encoding="utf-8")
    assert 'run_context_sweep.py" --mode smoke' in launcher
    assert 'validate_results.py" --mode smoke' in launcher
    assert "torchrun --standalone --nproc_per_node=3" in launcher
    assert "instance_id in completed" in runner
    assert "append_jsonl(results_path, row)" in runner
    assert "book.txt" not in runner
    assert "apply_chat_template" in runner
    assert 'instance["context"]' in runner
    assert 'instance["question"]' in runner
    assert "bucket" not in launcher.lower()


def test_64k_128k_wrappers_pin_preparation_and_launch_paths():
    prepare = (SWEEP / "prepare_64k_128k.sh").read_text(encoding="utf-8")
    launch = (SWEEP / "run_64k_128k.sh").read_text(encoding="utf-8")
    assert "build_128k_dataset.py" in prepare
    assert "stage_dataset.py\" --verify-only" in prepare
    assert "git -C \"$REPO\" status --porcelain" in prepare
    assert "preproduction_llama32_3b_500f_128k_v1" in launch
    assert "CP_EXPERIMENT_CONFIG" in launch
    assert 'exec bash "$SCRIPT_DIR/run_context_sweep.sh"' in launch


def test_runtime_uses_answer_only_format_without_gpu_grading():
    runner = (SWEEP / "run_context_sweep.py").read_text(encoding="utf-8")
    assert "grade_answer_only_response" not in runner
    assert "RESPONSE_FORMAT_INSTRUCTIONS" in runner
    assert "usable_answer_output" in runner


def test_cpu_grading_pins_the_existing_frozen_grader():
    source = (SWEEP / "grade_results.py").read_text(encoding="utf-8")
    assert 'GRADER_SHA256 = "d9282a0ccc50daba3bfd232c058dfbab63a5c19a7323d585a7c2236b3a6c4ba8"' in source
    assert "grade_answer_only_response" in source


def test_cp_infer_pins_model_revision_and_supports_offline_snapshot():
    source = (ROOT / "cp_infer.py").read_text(encoding="utf-8")
    assert 'MODEL_REVISION = "e28526f7bb80e2a9c8af03b831a9af3812f18fba"' in source
    assert 'MODEL_SOURCE = os.environ.get("CP_MODEL_PATH", MODEL)' in source
    assert "local_files_only=LOCAL_MODEL" in source


def test_config_is_canonical_json():
    source = (SWEEP / "experiment_config.json").read_text(encoding="utf-8")
    assert source == json.dumps(json.loads(source), indent=2) + "\n"


def test_external_config_supports_independent_extension(monkeypatch, tmp_path):
    payload = common.load_config()
    payload["experiment_id"] = "external-test"
    external = tmp_path / "experiment.json"
    external.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("CP_EXPERIMENT_CONFIG", str(external))
    assert common.config_path() == external.resolve()
    assert common.load_config()["experiment_id"] == "external-test"


def test_64k_128k_template_is_unpinned_until_dataset_build():
    template = json.loads(
        (SWEEP / "experiment_config_64k_128k.template.json").read_text(encoding="utf-8")
    )
    assert template["experiment_id"] == "qwen25_7b_cp_gpu_dataset_64k_128k_v1"
    assert template["context_labels"] == ["64K", "128K"]
    assert template["source_benchmark"]["selected_instances"] == 1000
    assert template["source_benchmark"]["source_instances"] == 3000
    assert template["source_benchmark"]["dataset_sha256"] is None
    assert template["source_benchmark"]["parent_dataset_sha256"] == (
        "dc2c4194dedb090198e6883735257908ce274bebc8611b40d958dbd026aa1fe6"
    )


def test_128k_builder_derives_safe_output_config(tmp_path):
    output = tmp_path / extension.NEW_DATASET_NAME
    output.mkdir()
    derived = extension.derive_pipeline_config(
        ROOT.parents[1] / "config" / "preproduction_llama32_3b_500f_6ctx_v1.yaml",
        output,
    )
    payload = yaml.safe_load(derived.read_text(encoding="utf-8"))
    assert payload["data_root"] == str(tmp_path)
    assert payload["output_subdir"] == extension.NEW_DATASET_NAME
    assert payload["context"]["lengths"] == [4096, 8192, 16384, 32768, 65536, 131072]
    assert payload["model_prompt"]["max_rendered_input_tokens"] == 131072 - 128
