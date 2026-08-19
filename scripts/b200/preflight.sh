#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO"
export PYTHONPATH="$REPO/src${PYTHONPATH:+:$PYTHONPATH}"
eval "$(python "$SCRIPT_DIR/print_env.py")"
python "$SCRIPT_DIR/preflight.py"
python scripts/run_llama_500f_6ctx_experiment_d.py --mode preflight --resume
python scripts/run_qwen35_2b_experiment_e.py --mode preflight --resume
python "$SCRIPT_DIR/validate_outputs.py" --mode preflight
echo "PASS: B200 PREFLIGHT COMPLETE"
