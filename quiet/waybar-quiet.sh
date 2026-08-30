#!/usr/bin/env bash
# Waybar module for quiet. Prints JSON; empty text means the module disappears.
# A status bar that is usually blank is the correct rendering of this tool.
set -euo pipefail
OUT="$(python3 "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/quiet.py" 2>/dev/null | tr -d '\n' | sed 's/^ *//;s/ *$//')"
if [ -z "$OUT" ]; then
  printf '{"text":"","tooltip":"quiet — nothing to say","class":"silent"}\n'
else
  SHORT="$(printf '%s' "$OUT" | cut -c1-48)"
  printf '{"text":"● %s","tooltip":%s,"class":"speaking"}\n' \
    "$SHORT" "$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$OUT")"
fi
