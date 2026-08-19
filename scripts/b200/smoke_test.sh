#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO"
eval "$(python "$SCRIPT_DIR/print_env.py")"
: "${B200_SMOKE_FAMILIES:=2}"
export B200_SMOKE_FAMILIES
python scripts/run_llama_500f_6ctx_experiment_d.py --mode smoke --smoke-families "$B200_SMOKE_FAMILIES" --resume
python scripts/run_qwen35_2b_experiment_e.py --mode smoke --smoke-families "$B200_SMOKE_FAMILIES" --resume
python "$SCRIPT_DIR/validate_outputs.py" --mode smoke
echo "PASS: SIX-CONTEXT SCIENTIFIC SMOKE TEST COMPLETE"
