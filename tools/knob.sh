#!/usr/bin/env bash
set -euo pipefail
CMD="${1:?Usage: knob.sh get|set|reset FILE path [value] [BASE]}"
FILE="${2:?}"; PATH_TOML="${3:-}"; VAL="${4:-}"; BASE="${5:-}"
command -v toml >/dev/null 2>&1 || { echo "toml-cli not installed (cargo install toml-cli)"; exit 2; }

case "$CMD" in
  get)
    toml get "$FILE" "$PATH_TOML"
    ;;
  set)
    [[ -n "$VAL" ]] || { echo "set requires value"; exit 1; }
    tmp="$(mktemp)"; toml set "$FILE" "$PATH_TOML" "$VAL" > "$tmp" && mv "$tmp" "$FILE"
    echo "[knob] set $PATH_TOML=$VAL in $FILE"
    ;;
  reset)
    [[ -n "$BASE" ]] || { echo "reset requires BASE"; exit 1; }
    VAL_B="$(toml get "$BASE" "$PATH_TOML")"
    tmp="$(mktemp)"; toml set "$FILE" "$PATH_TOML" "$VAL_B" > "$tmp" && mv "$tmp" "$FILE"
    echo "[knob] reset $PATH_TOML -> $VAL_B from $BASE"
    ;;
  *)
    echo "unknown cmd: $CMD"; exit 1;;
esac