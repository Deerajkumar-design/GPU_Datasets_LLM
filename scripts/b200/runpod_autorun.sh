#!/usr/bin/env bash
set -euo pipefail

export RUNPOD_WORKSPACE=/workspace
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1

PROJECT_ROOT="/workspace/long-context-reliability"
REPO="$PROJECT_ROOT/repo"
LOG_DIR="$PROJECT_ROOT/logs/b200_autorun"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/autorun_$(date -u +%Y%m%dT%H%M%SZ).log"

exec > >(tee -a "$LOG_FILE") 2>&1

blocked() {
  local code=$?
  local line="${BASH_LINENO[0]:-unknown}"
  echo "AUTOMATIC TERMINATION BLOCKED: autorun failed with exit code $code at line $line; command=$BASH_COMMAND"
  echo "No further termination request will be made. Check Pod state and logs manually."
  exit "$code"
}
trap blocked ERR

echo "B200 AUTORUN START $(date -u +%FT%TZ)"
echo "Pod ID: ${RUNPOD_POD_ID:-MISSING}"
echo "Persistent log: $LOG_FILE"

[[ -n "${RUNPOD_POD_ID:-}" ]] || { echo "RUNPOD_POD_ID is missing" >&2; false; }
[[ -n "${RUNPOD_API_KEY:-}" ]] || { echo "RUNPOD_API_KEY is missing" >&2; false; }
[[ -d "$REPO" ]] || { echo "repository is missing: $REPO" >&2; false; }
cd "$REPO"
export PYTHONPATH="$REPO/src${PYTHONPATH:+:$PYTHONPATH}"

python scripts/b200/record_autorun_metadata.py
./scripts/b200/run_b200_inference.sh --model all
python scripts/b200/safe_terminate.py --model all
