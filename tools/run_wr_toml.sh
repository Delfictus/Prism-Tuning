#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"; cd "$REPO_ROOT"

BASE="${BASE_CONFIG:-configs/base/wr_sweep_D_aggr_seed_9001.v1.1.toml}"
OUT="${OUT_CONFIG:-configs/wr_hyper_active.toml}"
THREADS="${RAYON_NUM_THREADS:-24}"
TIME_LIM="${TIMEOUT:-90m}"
PRISM_BIN="${PRISM_BIN:-bin/world_record_dsjc1000}"

[[ -x "$PRISM_BIN" ]] || { echo "ERROR: $PRISM_BIN not found/executable"; exit 1; }

if [[ $# -gt 0 ]]; then
  LAYERS=( "$@" )
else
  LAYERS=( configs/global_hyper.toml )
fi

mkdir -p configs results/logs results/summaries run_env/benchmarks/dimacs run_env/anchor/examples

# Ensure dataset at the expected relative path for the example binary
cp -f data/benchmarks/dimacs/DSJC1000.5.col run_env/benchmarks/dimacs/DSJC1000.5.col

tools/toml_layered_merge.sh "$BASE" "$OUT" "${LAYERS[@]}"

ts="$(date -Iseconds)"; LOG="$REPO_ROOT/results/logs/wr_hyper_${ts}.log"
OUT_ABS="$(realpath "$OUT")"

echo "[run] base=$BASE"; echo "[run] out=$OUT_ABS"; echo "[run] log=$LOG"; echo "[run] bin=$PRISM_BIN"

( cd run_env/anchor/examples && \
  RAYON_NUM_THREADS="$THREADS" timeout "$TIME_LIM" \
  "$REPO_ROOT/$PRISM_BIN" "$OUT_ABS" 2>&1 | tee "$LOG" )

if [[ -f tools/summarize_wr_log.py ]]; then
  if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi
  "$PY" tools/summarize_wr_log.py "$LOG" --base-config "$BASE" \
    --csv-append results/summaries/wr_hyper_summary.csv \
    --json-out "results/summaries/wr_hyper_${ts}.json" || true
  echo "[run] summary -> results/summaries/wr_hyper_${ts}.json"
fi