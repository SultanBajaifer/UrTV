#!/usr/bin/env bash
# Put the TV back to A: exactly as it was before UrTV changed anything, whatever was installed or updated since.
# A is saved once, by optimize/run.sh before its first change (optimize/state-A.txt), and never replaced.
#   optimize/rollback.sh preview   what would change, without changing anything
#   optimize/rollback.sh           back to A: apps on/off as in A, the TV's own Home and screensaver, our apps (and TV
#                                  Bro, SmartTube if they were not there in A) removed, speed tweaks undone
# Your own apps, logins and data are never touched. It needs ADB on: Settings > Developer options > USB debugging,
# then optimize/find-tv.sh and Allow on the TV. A is kept, so the TV can be set up again and go back to A again.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-optimize/venv/bin/python}"
A=optimize/state-A.txt

if [ ! -s "$A" ]; then
  echo "!! No $A here: this folder never saw the TV before its first change (or the file was lost)."
  echo "   If you have a copy (optimize/backup-copy.sh), put state-A.txt back in optimize/. Without it,"
  echo "   optimize/reset.sh puts the TV back to a plain, like-new state instead."
  exit 1
fi
case "${1:-}" in
  preview)
    echo "Back to A would:"
    "$PY" -I optimize/snapshot.py diff "$A" ;;
  "")
    echo "Back to A (the TV as it was before UrTV, saved $(date -r "$A" '+%Y-%m-%d %H:%M' 2> /dev/null || echo earlier)):"
    "$PY" -I optimize/snapshot.py restore "$A"
    # the setup's marks start over (A stays): optimize/run.sh would set the TV up again from the first step
    if [ -d optimize/run ]; then mv optimize/run "optimize/run-$(date +%Y%m%d-%H%M%S)"; fi
    echo "Your apps, logins and data were not touched. To set it up again: optimize/run.sh" ;;
  *)
    sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
