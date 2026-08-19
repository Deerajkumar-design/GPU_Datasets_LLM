#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO"
eval "$(python "$SCRIPT_DIR/print_env.py")"
python "$SCRIPT_DIR/analyze_results.py"
