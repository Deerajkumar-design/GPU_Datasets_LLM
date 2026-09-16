#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd -- "$SCRIPT_DIR/../../../.." && pwd)"
export CP_WORKSPACE="${CP_WORKSPACE:-/workspace/context-parallel-repro}"

SOURCE_DATASET="${CP_SOURCE_DATASET:-$REPO/data/preproduction_llama32_3b_500f_6ctx_v1}"
NORMALIZED_DIR="${CP_NORMALIZED_DIR:-$REPO/data/normalized}"
DERIVED_DATASET="$CP_WORKSPACE/datasets/preproduction_llama32_3b_500f_128k_v1"
CONFIG="$DERIVED_DATASET/cp2_experiment_config.json"
EXPERIMENT_ID="qwen25_7b_cp_gpu_dataset_64k_128k_v1"

if [[ -n "$(git -C "$REPO" status --porcelain)" ]]; then
  echo "ERROR: repository must be clean before freezing the 128K dataset." >&2
  echo "Commit, remove, or move local changes, then rerun this command." >&2
  exit 1
fi

for name in sec.jsonl fda.jsonl clinical_trials.jsonl fred.jsonl; do
  if [[ ! -f "$NORMALIZED_DIR/$name" ]]; then
    echo "ERROR: missing normalized source cache: $NORMALIZED_DIR/$name" >&2
    echo "Restore the original data/normalized cache or run fetch and normalize first." >&2
    exit 1
  fi
done

python -c "import pandas, pyarrow, transformers, yaml"
mkdir -p "$CP_WORKSPACE/datasets"

python "$SCRIPT_DIR/build_128k_dataset.py" \
  --source "$SOURCE_DATASET" \
  --normalized-dir "$NORMALIZED_DIR" \
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
