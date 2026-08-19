#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO"
eval "$(python "$SCRIPT_DIR/print_env.py")"
START="$(date -u +%FT%TZ)"
echo "B200 inference started: $START"
"$SCRIPT_DIR/preflight.sh"
if [[ "${B200_SKIP_SMOKE:-0}" != "1" ]]; then "$SCRIPT_DIR/smoke_test.sh"; fi
python scripts/run_llama_500f_6ctx_experiment_d.py --mode full --resume
python scripts/run_qwen35_2b_experiment_e.py --mode full --resume
python "$SCRIPT_DIR/validate_outputs.py" --mode full
python "$SCRIPT_DIR/write_hashes.py"
echo "GPU INFERENCE COMPLETE - SAFE TO TERMINATE POD AFTER VERIFYING PERSISTENT OUTPUTS"
