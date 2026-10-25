#!/usr/bin/env bash
# «تسريع» from the computer: frees memory on the TV now, on any Android version (the home screen's «تسريع» pill can
# do it only up to Android 13). Stops the background processes of every app Android itself calls safe to stop
# (am kill-all: never the app on screen, music playing, or the system), and prints the free memory before and after.
# Nothing is uninstalled, disabled or cleared: a stopped app starts again normally, with its logins and data.
#   optimize/boost.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-optimize/venv/bin/python}"
avail() { "$PY" -I optimize/tv.py "grep MemAvailable /proc/meminfo" | tr -dc '0-9'; }
before=$(avail)
"$PY" -I optimize/tv.py "am kill-all" > /dev/null
sleep 2   # the memory comes back over a moment
after=$(avail)
if [ -z "$before" ] || [ -z "$after" ]; then echo "!! The TV did not say how much memory is free"; exit 1; fi
freed=$(( (after - before) / 1024 )); [ "$freed" -lt 0 ] && freed=0
echo "Free memory: $((before / 1024)) MB -> $((after / 1024)) MB (freed ${freed} MB)"
