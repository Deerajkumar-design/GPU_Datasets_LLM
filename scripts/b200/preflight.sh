#!/usr/bin/env bash
set -euo pipefail
MODEL="all"
if [[ "${1:-}" == "--model" && -n "${2:-}" ]]; then MODEL="$2"; shift 2; fi
[[ $# -eq 0 ]] || { echo "usage: $0 [--model llama|qwen|all]" >&2; exit 2; }
[[ "$MODEL" =~ ^(llama|qwen|all)$ ]] || { echo "invalid model: $MODEL" >&2; exit 2; }
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO"
export PYTHONPATH="$REPO/src${PYTHONPATH:+:$PYTHONPATH}"
eval "$(python "$SCRIPT_DIR/print_env.py")"
python "$SCRIPT_DIR/preflight.py" --model "$MODEL"
if [[ "$MODEL" == "llama" || "$MODEL" == "all" ]]; then
  python scripts/run_llama_500f_6ctx_experiment_d.py --mode preflight --resume
fi
if [[ "$MODEL" == "qwen" || "$MODEL" == "all" ]]; then
  python scripts/run_qwen35_2b_experiment_e.py --mode preflight --resume
fi
python "$SCRIPT_DIR/validate_outputs.py" --mode preflight --model "$MODEL"
echo "PASS: B200 PREFLIGHT COMPLETE"
