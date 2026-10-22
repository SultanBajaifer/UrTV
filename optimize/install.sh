#!/usr/bin/env bash
# Download the latest APKs from GitHub and install them on the TV.
#   optimize/install.sh saver      شاشة تلفزيونك: install + make it the screensaver
#   optimize/install.sh launcher   the home screen: install + make it the default Home
#   optimize/install.sh all        both
#   optimize/install.sh extras     TV Bro (a TV web browser, github.com/truefedex/tv-bro) and SmartTube (YouTube
#                                  without ads, github.com/yuliskov/SmartTube): only the versions pinned in
#                                  optimize/lists/extras.lock, SHA-256 checked
# Our APKs are checked against the release's SHA256SUMS.txt. An app on the TV signed with another key is never
# replaced unless ALLOW_REPLACE=1 (that would remove it and its settings).
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-optimize/venv/bin/python}"
REL=https://github.com/SultanBajaifer/UrTV/releases/download/${APK_TAG:-apk-latest}   # APK_TAG=v3.N: that numbered build
what="${1:?usage: optimize/install.sh saver|launcher|all|extras}"
failed=0   # an extra that did not install: the rest are still tried, then run.sh must not count the step as done

sha256() { if command -v sha256sum > /dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi | awk '{print $1}'; }

# Every installed APK is kept in optimize/apks/<package>/ (newest last): optimize/rollback.sh app goes back to one.
keep_apk() {   # $1 file, $2 package
  local dir="optimize/apks/$2" h
  h=$(sha256 "$1")
  mkdir -p "$dir"
  [ -f "$dir/$h.apk" ] || cp "$1" "$dir/$h.apk"
  printf '%s %s\n' "$(date +%Y%m%d-%H%M%S)" "$h" >> "$dir/installed.txt"
}

# $1 local apk file, $2 package. Android itself refuses an update signed with another key: that is the check that
# a swapped APK can't pass, so a mismatch stops here. ALLOW_REPLACE=1 removes the installed app (and its settings)
# first; only for a key you changed on purpose.
install_apk() {
  local out
  "$PY" -I optimize/tv.py --push-b64 "$1" "/data/local/tmp/$(basename "$1")"
  local flags="-r"; [ "${DOWNGRADE:-}" = 1 ] && flags="-r -d"
  out=$("$PY" -I optimize/tv.py "pm install $flags /data/local/tmp/$(basename "$1")")
  if [ "${DOWNGRADE:-}" = 1 ] && grep -q VERSION_DOWNGRADE <<< "$out"; then
    # Android only takes an older version over a newer one for debug builds: remove the app but keep its data
    # (-k), then install the older one, which finds its settings again
    echo "Going back a version: removing $2 (its settings are kept), then installing the older one."
    [ "$2" = sa.urtv.home ] && "$PY" -I optimize/tv.py "pm enable ${STOCK%%/*}" > /dev/null || true
    "$PY" -I optimize/tv.py "pm uninstall -k $2" || true
    out=$("$PY" -I optimize/tv.py "pm install -r /data/local/tmp/$(basename "$1")")
  fi
  if ! grep -q Success <<< "$out" && grep -qE 'UPDATE_INCOMPATIBLE|signatures do not match' <<< "$out"; then
    if [ "${ALLOW_REPLACE:-}" != 1 ]; then
      "$PY" -I optimize/tv.py "rm -f /data/local/tmp/$(basename "$1")" > /dev/null
      echo "!! $2 on the TV is signed with a different key than this APK. Refusing: a different key means it was not"
      echo "   built by your repo's key (or the key changed). If you changed the key on purpose:"
      echo "   ALLOW_REPLACE=1 $0 $what   (removes $2 and its settings first)"
      return 2
    fi
    echo "ALLOW_REPLACE=1: removing $2 (signed with another key), then installing again."
    # removing the home app while the stock one is off would leave the TV with no home at all
    [ "$2" = sa.urtv.home ] && "$PY" -I optimize/tv.py "pm enable ${STOCK%%/*}" > /dev/null || true
    "$PY" -I optimize/tv.py "pm uninstall $2" || true
    out=$("$PY" -I optimize/tv.py "pm install -r /data/local/tmp/$(basename "$1")")
  fi
  "$PY" -I optimize/tv.py "rm -f /data/local/tmp/$(basename "$1")" > /dev/null
  if ! grep -q Success <<< "$out"; then echo "!! Install of $(basename "$1") failed: $out"; return 1; fi
  keep_apk "$1" "$2"
}

push_install() {   # $1 apk name, $2 package
  if [ -n "${LOCAL_APK:-}" ]; then   # optimize/rollback.sh app: a version kept in optimize/apks/, named by its SHA-256
    if [ "$(sha256 "$LOCAL_APK")" != "$(basename "$LOCAL_APK" .apk)" ]; then echo "!! $LOCAL_APK changed since it was kept: not installed"; exit 1; fi
    cp "$LOCAL_APK" "optimize/$1"
    install_apk "optimize/$1" "$2" || { rm -f "optimize/$1"; exit 1; }
    rm -f "optimize/$1"
    return 0
  fi
  if ! curl -fsSL -o "optimize/$1" "$REL/$1"; then
    echo "!! Could not download $REL/$1 (tag ${APK_TAG:-apk-latest}): no such build, or no internet"; exit 1
  fi
  # the release's SHA256SUMS.txt (written by the build): catches a broken or swapped download
  local sums want got
  sums=$(curl -fsSL "$REL/SHA256SUMS.txt" 2> /dev/null || true)
  want=$(awk -v f="$1" '$2 == f {print $1}' <<< "$sums")
  got=$(sha256 "optimize/$1")
  if [ -z "$want" ]; then
    echo "!! $REL has no SHA256SUMS.txt entry for $1: refusing an unchecked APK"; rm -f "optimize/$1"; exit 1
  elif [ "$want" != "$got" ]; then
    echo "!! $1 does not match its SHA-256 ($got, expected $want): not installed"; rm -f "optimize/$1"; exit 1
  fi
  install_apk "optimize/$1" "$2" || { rm -f "optimize/$1"; exit 1; }
  rm -f "optimize/$1"
}

# TV Bro and SmartTube: only the exact files pinned in optimize/lists/extras.lock (optimize/pin-extras.sh), each
# checked against its SHA-256 there. Never "the latest release".
from_lock() {   # $1 package
  local abis line url want name got
  abis=$("$PY" -I optimize/tv.py "getprop ro.product.cpu.abilist" | tr -d '\r')
  line=$(awk -v p="$1" -v abis="$abis,universal" '
    $1 == p { u[$2] = $0 }
    END { n = split(abis, a, ","); for (i = 1; i <= n; i++) if (a[i] in u) { print u[a[i]]; exit } }
  ' optimize/lists/extras.lock)
  if [ -z "$line" ]; then echo "!! No pinned build of $1 for this TV ($abis) in optimize/lists/extras.lock: skipped"; failed=1; return 0; fi
  read -r _ _ _ url want <<< "$line"
  name=$(basename "$url")
  if ! curl -fsSL -o "optimize/$name" "$url"; then echo "!! Could not download $url"; failed=1; return 0; fi
  got=$(sha256 "optimize/$name")
  if [ "$got" != "$want" ]; then
    echo "!! $name does not match its pinned SHA-256 ($got, expected $want): not installed"
    rm -f "optimize/$name"; failed=1; return 0
  fi
  local rc=0; install_apk "optimize/$name" "$1" || rc=$?
  rm -f "optimize/$name"
  if [ "$rc" = 0 ]; then echo "Installed $name"
  elif [ "$rc" = 2 ]; then echo "$1 is already installed from somewhere else: left as it is (with its settings)."
  else failed=1; fi
}

if [ "$what" = extras ]; then
  if [ ! -f optimize/lists/extras.lock ]; then
    echo "!! optimize/lists/extras.lock is missing: run optimize/pin-extras.sh first (or SKIP_EXTRAS=1)"; exit 1
  fi
  from_lock com.phlox.tvwebbrowser
  from_lock org.smarttube.stable
  [ "$failed" = 0 ] || exit 1
fi

if [ "$what" = saver ] || [ "$what" = all ]; then
  push_install urtv-screensaver.apk sa.urtv.screensaver
  printf '%s\n' \
    "settings put secure screensaver_enabled 1" \
    "settings put secure screensaver_components sa.urtv.screensaver/.ScreenDream" \
    "settings put secure screensaver_default_component sa.urtv.screensaver/.ScreenDream" \
    "am start -n sa.urtv.screensaver/.SettingsActivity" \
    | "$PY" -I optimize/tv.py --batch
  echo "Screensaver installed and selected. Its settings screen is open on the TV."
fi

if [ "$what" = launcher ] || [ "$what" = all ]; then
  # Which stock home does this TV have? Google TV sets: launcherx. Older Android TV: tvlauncher.
  if "$PY" -I optimize/tv.py "pm list packages com.google.android.apps.tv.launcherx" | grep -q launcherx; then
    STOCK=com.google.android.apps.tv.launcherx/com.google.android.apps.tv.launcherx.home.HomeActivity
  else
    STOCK=com.google.android.tvlauncher/.MainActivity
  fi
  echo "Stock home: $STOCK"

  # 1. The new home must be installed and working BEFORE anything is disabled.
  push_install urtv-home.apk sa.urtv.home
  # an older build asked for location (only to show the Wi-Fi name): take it back if it was granted
  "$PY" -I optimize/tv.py "pm revoke sa.urtv.home android.permission.ACCESS_FINE_LOCATION" > /dev/null 2>&1 || true

  # Steps 2-4 as one function, so an ADB drop in the middle (TCL G08: Wi-Fi fell during the batch) can be retried.
  # "verify" as $1: only step 4 (the switch is armed already and the batch may have run).
  # Returns 0: the new home is on screen and the switch is disarmed; 1: tv.py failed (connection lost);
  # 2: Home did not open the new launcher; 3: the safety switch fired first.
  switch_home() {
    local top res ours=no _
    if [ "${1:-}" != verify ]; then
      # 2. Arm the safety switch on the TV: it restores the stock home in 300 s unless we confirm (slow ADB needs time).
      "$PY" -I optimize/tv.py --push-b64 optimize/deadman.sh /data/local/tmp/deadman.sh || return 1
      printf '%s\n' \
        "rm -f /data/local/tmp/home_ok" \
        "nohup sh /data/local/tmp/deadman.sh $STOCK 300 > /dev/null 2>&1 &" \
        | "$PY" -I optimize/tv.py --batch || return 1
      echo "Safety switch armed: the stock home comes back by itself in 5 minutes unless the new home works."

      # 3. Switch: the HOME role (Android 10+; the classic set-home-activity for older sets and as a backup), then
      #    the setup app off, then the stock home (this order avoided the black screen).
      printf '%s\n' \
        "cmd role add-role-holder --user 0 android.app.role.HOME sa.urtv.home" \
        "cmd package set-home-activity --user 0 sa.urtv.home/.MainActivity" \
        "pm disable-user --user 0 com.google.android.tungsten.setupwraith" \
        "pm disable-user --user 0 ${STOCK%%/*}" \
        "cmd package set-home-activity --user 0 sa.urtv.home/.MainActivity" \
        "am force-stop com.android.tv.settings" \
        "input keyevent KEYCODE_HOME" \
        | "$PY" -I optimize/tv.py --batch || return 1
    fi
    # 4. Verify Home really opens the new launcher (a few tries: a slow TV), then disarm the switch.
    for _ in 1 2 3; do
      sleep 6
      top=$("$PY" -I optimize/tv.py "dumpsys activity activities | grep -E 'mResumedActivity|topResumedActivity'") || return 1
      if grep -q sa.urtv.home <<< "$top"; then ours=yes; break; fi
      "$PY" -I optimize/tv.py "input keyevent KEYCODE_HOME" > /dev/null || return 1
    done
    [ "$ours" = yes ] || return 2
    "$PY" -I optimize/tv.py "touch /data/local/tmp/home_ok" || return 1
    # the switch may have fired already if ADB was very slow: then the stock home is back
    res=$("$PY" -I optimize/tv.py "cmd package resolve-activity --brief -c android.intent.category.HOME -a android.intent.action.MAIN") || return 1
    grep -q sa.urtv.home <<< "$res" || return 3
  }

  rc=0; switch_home || rc=$?
  if [ "$rc" = 1 ]; then   # ADB dropped: wait for the TV, see what Home is now, and go on or start the switch again
    back=no
    for _ in $(seq 36); do   # every 10 s, about 6 minutes
      if "$PY" -I optimize/tv.py "getprop ro.serialno" > /dev/null 2>&1; then back=yes; break; fi
      sleep 10
    done
    if [ "$back" = no ]; then
      echo "!! The TV did not come back within 6 minutes. Check it is on and on Wi-Fi: the safety switch restores the stock home."
      echo "   Then run the same command again."
      exit 1
    fi
    res=$("$PY" -I optimize/tv.py "cmd package resolve-activity --brief -c android.intent.category.HOME -a android.intent.action.MAIN" 2> /dev/null) || res=""
    rc=0
    if grep -q sa.urtv.home <<< "$res"; then
      echo "ADB dropped during the switch; the TV is back and the new home is already set: checking it"
      switch_home verify || rc=$?
    else
      echo "ADB dropped during the switch; the TV is back, trying the switch again"
      switch_home || rc=$?   # arms the switch again first
    fi
  fi
  case "$rc" in
    0) ;;
    2) echo "!! Home did not open the new launcher. Leave the TV alone: the stock home returns within 5 minutes."
       echo "   Some TCL firmware pins Home to the stock launcher; on those sets keep the stock home."
       exit 1 ;;
    *) echo "!! The safety switch put the stock home back (ADB was too slow). Nothing is broken: run the same command again."
       exit 1 ;;
  esac
  # 5. Only now: the stock home's helpers are dead weight (restore.sh brings them back).
  grep -vE '^\s*(#|$)' optimize/lists/home-replaced.txt | awk '{print "pm disable-user --user 0 " $1}' \
    | "$PY" -I optimize/tv.py --batch > /dev/null || true
  echo "Launcher is home. Press Home from inside an app to double-check."
  echo "Undo everything: optimize/reset.sh"
fi
