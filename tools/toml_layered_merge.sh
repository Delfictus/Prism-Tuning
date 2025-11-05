#!/usr/bin/env bash
set -euo pipefail
BASE="${1:?Usage: toml_layered_merge.sh BASE.toml OUT.toml [LAYER1.toml ...] }"
OUT="${2:?Usage: toml_layered_merge.sh BASE.toml OUT.toml [LAYER1.toml ...] }"
shift 2
LAYERS=( "$@" )

if ! command -v toml >/dev/null 2>&1; then
  echo "[toml-cli] not found; install with: cargo install toml-cli" >&2
  exit 2
fi

tmp="$(mktemp)"; cp "$BASE" "$tmp"

merge_one() {
  local OVR="$1"
  awk 'BEGIN{sec=""}
  {
    line=$0
    if(line~/^[ \t]*#/) next
    if(line~/^[ \t]*\[/) {
      gsub(/^[ \t]*\[/, "", line)
      gsub(/\][ \t]*$/, "", line)
      sec=line
      next
    }
    noc=line
    sub(/#.*/, "", noc)
    if(noc~/^[ \t]*[A-Za-z0-9_.-]+[ \t]*=/) {
      gsub(/^[ \t]*/, "", noc)
      split(noc, parts, "=")
      key=parts[1]
      val=parts[2]
      gsub(/[ \t]*$/, "", key)
      gsub(/^[ \t]*/, "", val)
      if(length(key) > 0 && length(val) > 0) {
        print (sec==""?"ROOT":sec) "\t" key "\t" val
      }
    }
  }
  ' "$OVR" | while IFS=$'\t' read -r sec key val; do
    path=$([[ "$sec" == "ROOT" ]] && echo "$key" || echo "${sec}.${key}")
    if toml get "$tmp" "$path" >/dev/null 2>&1; then
      toml set "$tmp" "$path" "$val" > "${tmp}.new" && mv "${tmp}.new" "$tmp"
    fi
  done
}

for ovr in "${LAYERS[@]}"; do
  [[ -f "$ovr" ]] || { echo "[merge] skip missing $ovr"; continue; }
  echo "[merge] applying layer: $ovr"
  merge_one "$ovr"
done

mv "$tmp" "$OUT"
echo "[merge] wrote $OUT"