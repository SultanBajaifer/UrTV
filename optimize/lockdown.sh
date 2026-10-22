#!/usr/bin/env bash
# The last step: close the door the setup opened. Turns ADB (network and USB debugging) off on the TV and, unless
# KEEP_KEY=1, deletes this computer's ADB key (optimize/adbkey/). After this nothing on your network can control
# the TV, and neither can this computer until you turn debugging back on and press Allow again.
#   optimize/lockdown.sh
# To use rollback.sh, reset.sh or install.sh later: on the TV, Settings > System > Developer options > USB debugging
# on, then optimize/find-tv.sh, and press Allow on the TV.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-optimize/venv/bin/python}"

if ! ls optimize/backup-*.txt > /dev/null 2>&1 || [ ! -d optimize/run ]; then
  echo "!! No backup in optimize/ yet: run optimize/run.sh first (undo needs it)."; exit 1
fi
echo "Before ADB goes off, make sure the backups have a second copy: optimize/backup-copy.sh <folder>"

# the last command this computer sends: the connection drops as soon as the TV applies it
printf '%s\n' "settings put global adb_wifi_enabled 0" "settings put global adb_enabled 0" \
  | "$PY" -I optimize/tv.py --batch > /dev/null 2>&1 || true
sleep 3
if "$PY" -I -c '
import socket, sys
s = socket.socket(); s.settimeout(3)
sys.exit(0 if s.connect_ex((sys.argv[1], int(sys.argv[2]))) else 1)' "${TV_HOST:-$(cat optimize/.tv_host 2> /dev/null)}" "${TV_PORT:-5555}"; then
  echo "ADB is off: the TV no longer answers on the network."
else
  echo "!! The TV still answers on its ADB port. Turn it off by hand: Settings > System > Developer options >"
  echo "   USB debugging (and Network debugging if listed) off."
fi

if [ "${KEEP_KEY:-}" != 1 ] && [ -d optimize/adbkey ]; then
  rm -rf optimize/adbkey
  echo "This computer's ADB key is deleted: next time, the TV asks Allow again."
fi
cat <<'MSG'

One more thing on the TV (it forgets every computer it allowed):
  Settings > System > Developer options > Revoke USB debugging authorizations

Later, to undo or update: turn USB debugging back on, run optimize/find-tv.sh, press Allow on the TV,
then optimize/rollback.sh / optimize/reset.sh / optimize/install.sh. Run optimize/lockdown.sh again when done.
MSG
