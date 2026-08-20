#!/usr/bin/env bash
set -euo pipefail
MODEL="all"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --model)
      [[ -n "${2:-}" ]] || { echo "--model requires llama, qwen, or all" >&2; exit 2; }
      MODEL="$2"
      shift 2
      ;;
    *)
      echo "usage: $0 [--model llama|qwen|all]" >&2
      exit 2
      ;;
  esac
done
[[ "$MODEL" =~ ^(llama|qwen|all)$ ]] || { echo "invalid model: $MODEL" >&2; exit 2; }
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO"
eval "$(python "$SCRIPT_DIR/print_env.py")"
START="$(date -u +%FT%TZ)"
echo "B200 inference started: $START model=$MODEL"
"$SCRIPT_DIR/preflight.sh" --model "$MODEL"
if [[ "${B200_SKIP_SMOKE:-0}" != "1" ]]; then
  "$SCRIPT_DIR/smoke_test.sh" --model "$MODEL"
fi
if [[ "$MODEL" == "llama" || "$MODEL" == "all" ]]; then
  echo "LLAMA INFERENCE START $(date -u +%FT%TZ)"
  python scripts/run_llama_500f_6ctx_experiment_d.py --mode full --resume
  echo "LLAMA INFERENCE END $(date -u +%FT%TZ)"
fi
if [[ "$MODEL" == "qwen" || "$MODEL" == "all" ]]; then
  echo "QWEN INFERENCE START $(date -u +%FT%TZ)"
  python scripts/run_qwen35_2b_experiment_e.py --mode full --resume
  echo "QWEN INFERENCE END $(date -u +%FT%TZ)"
fi
echo "FULL OUTPUT VALIDATION START $(date -u +%FT%TZ)"
python "$SCRIPT_DIR/validate_outputs.py" --mode full --model "$MODEL"
echo "FULL OUTPUT VALIDATION END $(date -u +%FT%TZ)"
python "$SCRIPT_DIR/write_hashes.py" --model "$MODEL"
python "$SCRIPT_DIR/mark_completion.py" --model "$MODEL"
echo "GPU INFERENCE COMPLETE - SAFE TO TERMINATE POD AFTER VERIFYING PERSISTENT OUTPUTS"
