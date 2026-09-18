#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export CP_WORKSPACE="${CP_WORKSPACE:-/workspace/context-parallel-repro}"
export CP_EXPERIMENT_CONFIG="$CP_WORKSPACE/datasets/preproduction_qwen25_7b_500f_128k_v1/cp2_experiment_config.json"

if [[ ! -f "$CP_EXPERIMENT_CONFIG" ]]; then
  echo "ERROR: prepared 64K/128K configuration is missing:" >&2
  echo "  $CP_EXPERIMENT_CONFIG" >&2
  echo "Run prepare_64k_128k.sh on the persistent volume before launching the A100 run." >&2
  exit 1
fi

exec bash "$SCRIPT_DIR/run_context_sweep.sh"
