#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/run_b200_inference.sh"
"$SCRIPT_DIR/analyze_b200_results.sh"
