#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd -- "$SCRIPT_DIR/../../../.." && pwd)"
export CP_WORKSPACE="${CP_WORKSPACE:-/workspace/context-parallel-repro}"
if [[ -z "${CUDA_HOME:-}" && -n "${CONDA_PREFIX:-}" && -x "$CONDA_PREFIX/bin/nvcc" ]]; then
  export CUDA_HOME="$CONDA_PREFIX"
fi

SOURCE_DATASET="${CP_SOURCE_DATASET:-$REPO/data/preproduction_llama32_3b_500f_6ctx_v1}"
DERIVED_DATASET="$CP_WORKSPACE/datasets/preproduction_qwen25_7b_500f_128k_v1"
CONFIG="$DERIVED_DATASET/cp2_experiment_config.json"
TEMPLATE_CONFIG="$SCRIPT_DIR/experiment_config_64k_128k.template.json"
EXPERIMENT_ID="qwen25_7b_cp_gpu_dataset_64k_128k_v1"

if [[ -n "$(git -C "$REPO" status --porcelain)" ]]; then
  echo "ERROR: repository must be clean before freezing the 128K dataset." >&2
  echo "Commit, remove, or move local changes, then rerun this command." >&2
  exit 1
fi

mkdir -p "$CP_WORKSPACE/datasets"
if grep -q '^version https://git-lfs.github.com/spec/v1$' "$SOURCE_DATASET/instances.jsonl"; then
  echo "ERROR: frozen instances.jsonl is still a Git LFS pointer." >&2
  echo "Run 'git lfs pull' in the repository, then rerun this command." >&2
  exit 1
fi

AVAILABLE_KIB="$(df -Pk "$CP_WORKSPACE" | awk 'NR==2 {print $4}')"
REQUIRED_KIB=$((30 * 1024 * 1024))
if (( AVAILABLE_KIB < REQUIRED_KIB )); then
  echo "ERROR: CP_WORKSPACE requires at least 30 GiB free before preparation." >&2
  echo "available_kib=$AVAILABLE_KIB workspace=$CP_WORKSPACE" >&2
  exit 1
fi

export CP_EXPERIMENT_CONFIG="$TEMPLATE_CONFIG"
python "$SCRIPT_DIR/check_environment.py"

python "$SCRIPT_DIR/stage_model.py"
HF_HUB_OFFLINE=1 python "$SCRIPT_DIR/stage_model.py" --verify-only

python "$SCRIPT_DIR/build_128k_dataset.py" \
  --source "$SOURCE_DATASET" \
  --out "$DERIVED_DATASET"

if [[ ! -f "$CONFIG" ]]; then
  echo "ERROR: finalized experiment configuration was not created: $CONFIG" >&2
  exit 1
fi

export CP_EXPERIMENT_CONFIG="$CONFIG"
python "$SCRIPT_DIR/stage_dataset.py" --verify-only

ENV_DIR="$CP_WORKSPACE/manifests/$EXPERIMENT_ID"
mkdir -p "$ENV_DIR"
printf 'export CP_WORKSPACE=%q\nexport CP_EXPERIMENT_CONFIG=%q\n' \
  "$CP_WORKSPACE" "$CONFIG" > "$ENV_DIR/launch_env.sh"

echo
echo "64K/128K DATASET PREPARATION COMPLETE"
echo "dataset=$DERIVED_DATASET"
echo "config=$CONFIG"
echo "launch_environment=$ENV_DIR/launch_env.sh"
echo
echo "After attaching three A100 80GB GPUs, run:"
echo "  bash $SCRIPT_DIR/run_64k_128k.sh"
