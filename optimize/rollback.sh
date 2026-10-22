#!/usr/bin/env bash
# Undo part of the setup. Before each step that changes the TV, optimize/run.sh saves the TV's state
# (optimize/run/snap-<step>.txt); these put it back.
#   optimize/rollback.sh show            the steps that can be undone, newest first
#   optimize/rollback.sh diff            what undoing the last step would change, without changing anything
#   optimize/rollback.sh last            undo the last step (run it again to go one step further back)
#   optimize/rollback.sh to <step>       undo every step back to and including <step> (e.g. to safe)
#   optimize/rollback.sh tweaks          only the speed tweaks, back to Android's defaults
#   optimize/rollback.sh enable <pkg>    turn one app back on (the one thing you miss after the debloat)
#   optimize/rollback.sh app <pkg>       the previous version of sa.urtv.screensaver or sa.urtv.home (kept in
#                                        optimize/apks/ at every install); settings stay
#   optimize/rollback.sh all             everything, back to the TV as it came (optimize/reset.sh)
# Your own apps, accounts and data are never touched. Needs ADB on (Settings > Developer options > USB debugging).
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-optimize/venv/bin/python}"
RUN=optimize/run
LOG="$RUN/changes.log"   # "<date> <time> <step>" per step, "<date> <time> undone <step>" once undone

pending() {   # steps not undone yet, newest first
  [ -f "$LOG" ] || return 0
  awk '$3 == "undone" { u[$4] = NR; next } { s[NR] = $3 } END {
    for (i = NR; i >= 1; i--) if ((i in s) && !(s[i] in u && u[s[i]] > i)) { if (!(s[i] in seen)) print s[i]; seen[s[i]] = 1 }
  }' "$LOG"
}

undo_last() {
  local step
  step=$(pending | head -1)
  if [ -z "$step" ]; then echo "Nothing left to undo from optimize/run.sh. For everything: optimize/rollback.sh all"; return 1; fi
  echo "Undoing: $step"
  "$PY" -I optimize/snapshot.py restore "$RUN/snap-$step.txt"
  rm -f "$RUN/.done-$step"
  echo "$(date '+%Y-%m-%d %H:%M:%S') undone $step" >> "$LOG"
  echo "Undone: $step (optimize/run.sh would do it again)"
}

case "${1:-}" in
  show)
    steps=$(pending)
    if [ -z "$steps" ]; then echo "Nothing to undo."; else echo "Can be undone, newest first:"; printf '   %s\n' $steps; fi ;;
  diff)
    step=$(pending | head -1)
    [ -n "$step" ] || { echo "Nothing to undo."; exit 0; }
    echo "Undoing $step would:"
    "$PY" -I optimize/snapshot.py diff "$RUN/snap-$step.txt" ;;
  last)
    undo_last ;;
  to)
    target="${2:?usage: optimize/rollback.sh to <step>}"
    pending | grep -qx "$target" || { echo "!! $target is not among: $(pending | tr '\n' ' ')"; exit 1; }
    while pending | grep -qx "$target"; do undo_last; done ;;
  tweaks)
    optimize/tweaks.sh restore
    rm -f "$RUN/.done-tweaks" ;;
  enable)
    pkg="${2:?usage: optimize/rollback.sh enable <package>}"
    from=$(grep -lE "^$pkg(\s|$)" optimize/lists/*.txt 2> /dev/null | xargs -n1 basename 2> /dev/null | tr '\n' ' ' || true)
    "$PY" -I optimize/tv.py "pm enable $pkg"
    echo "Turned on $pkg${from:+ (it is in: $from)}. To keep it on after optimize/run.sh again, take it out of that list." ;;
  app)
    pkg="${2:?usage: optimize/rollback.sh app sa.urtv.screensaver|sa.urtv.home}"
    case "$pkg" in sa.urtv.screensaver) what=saver ;; sa.urtv.home) what=launcher ;;
      *) echo "!! only sa.urtv.screensaver or sa.urtv.home (TV Bro and SmartTube: pin an older version with optimize/pin-extras.sh)"; exit 1 ;; esac
    list="optimize/apks/$pkg/installed.txt"
    # the newest install, then the one before it with a different file
    cur=$(tail -1 "$list" 2> /dev/null | awk '{print $2}')
    prev=$(awk -v c="$cur" '$2 != c {p = $2} END {print p}' "$list" 2> /dev/null || true)
    if [ -z "$prev" ]; then echo "!! No earlier version of $pkg kept in optimize/apks/ (only one was ever installed from here)."; exit 1; fi
    echo "Going back to the $pkg installed before ($(grep -m1 "$prev" "$list" | awk '{print $1}'))"
    LOCAL_APK="optimize/apks/$pkg/$prev.apk" DOWNGRADE=1 optimize/install.sh "$what" ;;
  all)
    optimize/reset.sh ;;
  *)
    sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
