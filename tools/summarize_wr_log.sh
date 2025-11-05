#!/usr/bin/env bash
set -euo pipefail
LOG="${1:?Usage: summarize_wr_log.sh LOG [BASE_CONFIG] [CSV_PATH]}"
BASE_CONFIG="${2:-}"
CSV_PATH="${3:-results/summaries/wr_hyper_summary.csv}"
mkdir -p results/summaries
ts="$(date -Iseconds)"
JSON_OUT="results/summaries/$(basename "${LOG%.*}")_${ts}.json"
if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi
"$PY" tools/summarize_wr_log.py "$LOG" \
  ${BASE_CONFIG:+--base-config "$BASE_CONFIG"} \
  --csv-append "$CSV_PATH" \
  --json-out "$JSON_OUT"