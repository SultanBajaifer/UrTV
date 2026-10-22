#!/usr/bin/env bash
# Copy what undo needs to a second place (a USB stick, a cloud-synced folder): the TV's saved state, the per-step
# snapshots, the kept APKs and your optional picks. If this folder is ever lost, copy them back into optimize/.
#   optimize/backup-copy.sh <folder>
set -euo pipefail
cd "$(dirname "$0")/.."
DEST="${1:?usage: optimize/backup-copy.sh <folder, e.g. a USB stick>}"
[ -d "$DEST" ] || { echo "!! $DEST is not a folder"; exit 1; }
OUT="$DEST/urtv-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"
for p in optimize/run optimize/backup-*.txt optimize/apks optimize/lists/mine.txt optimize/lists/extras.lock; do
  [ -e "$p" ] && cp -R "$p" "$OUT/"
done
# never the ADB key: whoever has it can control the TV while ADB is on
rm -rf "$OUT/adbkey"
echo "Copied to $OUT"
echo "To use it again: copy its contents back into $(pwd)/optimize/ (run/, apks/, backup-*.txt; mine.txt and extras.lock into lists/)."
