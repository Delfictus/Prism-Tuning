#!/usr/bin/env bash
set -euo pipefail
LOG="${1:?Usage: monitor_wr.sh LOGFILE}"
echo "[monitor] tailing $LOG"
rg "INTERIM RESULT|\[IMPROVE\]|FINAL RESULT" "$LOG" || true
echo "---- live ----"
tail -f "$LOG" | rg "INTERIM RESULT|\[IMPROVE\]|FINAL RESULT"