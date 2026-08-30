#!/usr/bin/env bash
# Lay scriptorium's rules and agent definitions into an existing vault.
# Copies only; never overwrites a file that is already there.
set -euo pipefail

VAULT="${1:-}"
if [ -z "$VAULT" ]; then
  echo "usage: ./install.sh /path/to/vault" >&2
  exit 1
fi
if [ ! -d "$VAULT" ]; then
  echo "no such directory: $VAULT" >&2
  exit 1
fi

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DST="$VAULT/.scriptorium"

mkdir -p "$DST/rules" "$DST/agents"

copied=0; skipped=0
for f in "$SRC"/rules/*.md "$SRC"/agents/*.md; do
  rel="${f#$SRC/}"
  if [ -e "$DST/$rel" ]; then
    echo "  skip    .scriptorium/$rel (already present)"
    skipped=$((skipped+1))
  else
    cp "$f" "$DST/$rel"
    echo "  copied  .scriptorium/$rel"
    copied=$((copied+1))
  fi
done

if [ ! -e "$VAULT/.scriptorium.json" ]; then
  cp "$SRC/.scriptorium.example.json" "$VAULT/.scriptorium.json"
  echo "  copied  .scriptorium.json  <- edit this if your layout differs"
else
  echo "  skip    .scriptorium.json (already present)"
fi

echo
echo "$copied copied, $skipped left alone."
echo
echo "Check it against your vault:"
echo "  python3 $SRC/scriptorium.py --vault \"$VAULT\" --status"
echo "  python3 $SRC/scriptorium.py --vault \"$VAULT\" --lint"
echo
echo "Register it with Claude Code:"
echo "  claude mcp add scriptorium -- python3 $SRC/scriptorium.py --vault \"$VAULT\""
