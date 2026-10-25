#!/usr/bin/env bash
# Copy what the way back needs to a second place (a USB stick, a cloud-synced folder): A (the TV before UrTV,
# optimize/state-A.txt), the TV's saved state and your optional picks. If this folder is ever lost, copy them back
# into optimize/ and optimize/rollback.sh works again.
#   optimize/backup-copy.sh <folder>
set -euo pipefail
cd "$(dirname "$0")/.."
DEST="${1:?usage: optimize/backup-copy.sh <folder, e.g. a USB stick>}"
[ -d "$DEST" ] || { echo "!! $DEST is not a folder"; exit 1; }
[ -s optimize/state-A.txt ] || echo "(no optimize/state-A.txt yet: optimize/run.sh saves it before its first change)"
OUT="$DEST/urtv-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT/lists"
for p in optimize/state-A.txt optimize/run optimize/backup-*.txt; do
  [ -e "$p" ] && cp -R "$p" "$OUT/"
done
for p in optimize/lists/mine*.txt optimize/lists/extras.lock; do
  [ -e "$p" ] && cp "$p" "$OUT/lists/"
done
# never the ADB key: whoever has it can control the TV while ADB is on
rm -rf "$OUT/adbkey" "$OUT/run/adbkey"
echo "Copied to $OUT"
echo "To use it again: copy state-A.txt, run/ and backup-*.txt back into $(pwd)/optimize/, and lists/* into optimize/lists/."
