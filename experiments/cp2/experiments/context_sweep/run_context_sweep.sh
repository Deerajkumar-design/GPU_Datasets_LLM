#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
export CP_WORKSPACE="${CP_WORKSPACE:-/workspace/context-parallel-repro}"
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF="${PYTORCH_CUDA_ALLOC_CONF:-expandable_segments:True}"
export PYTHONPATH="$SCRIPT_DIR:$REPO${PYTHONPATH:+:$PYTHONPATH}"

mkdir -p "$CP_WORKSPACE/logs/qwen25_7b_cp_gpu_dataset_8k_32k_v1"
LOG="$CP_WORKSPACE/logs/qwen25_7b_cp_gpu_dataset_8k_32k_v1/run_$(date -u +%Y%m%dT%H%M%SZ).log"
exec > >(tee -a "$LOG") 2>&1

echo "CONTEXT SWEEP START $(date -u +%FT%TZ)"
echo "repository=$REPO"
echo "workspace=$CP_WORKSPACE"
cd "$REPO"

python "$SCRIPT_DIR/preflight.py"
torchrun --standalone --nproc_per_node=3 "$SCRIPT_DIR/run_context_sweep.py" --mode smoke
python "$SCRIPT_DIR/validate_results.py" --mode smoke
torchrun --standalone --nproc_per_node=3 "$SCRIPT_DIR/run_context_sweep.py"
python "$SCRIPT_DIR/validate_results.py"
python "$SCRIPT_DIR/finalize_results.py"
echo "CONTEXT SWEEP COMPLETE $(date -u +%FT%TZ)"
