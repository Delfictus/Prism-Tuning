#!/usr/bin/env bash
set -euo pipefail
OVR="${1:?Usage: lint_overrides.sh OVERRIDES.toml}"
bad=0
while IFS= read -r k; do
  [[ -z "$k" ]] && continue
  sec="${k%.*}"; key="${k##*.}"
  if rg -n "^[[:space:]]*\[${sec//./\\.}\]" "$OVR" -A999 | rg -n "^[[:space:]]*${key}[[:space:]]*=" -m1 >/dev/null; then
    echo "[lint] override touches ignored key: $k"; bad=1
  fi
done < tools/IGNORED_KEYS.txt
exit $bad