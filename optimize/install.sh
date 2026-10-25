#!/usr/bin/env bash
# Download the latest APKs from GitHub and install them on the TV.
#   optimize/install.sh saver      شاشة تلفزيونك: install + make it the screensaver
#   optimize/install.sh launcher   the home screen: install + make it the default Home
#                                  (it carries the «تلاوة» screens: the Quran recitations and the radio)
#   optimize/install.sh extras     TV Bro (a TV web browser, github.com/truefedex/tv-bro) and SmartTube (YouTube
#                                  without ads, github.com/yuliskov/SmartTube): only the versions pinned in
#                                  optimize/lists/extras.lock (optimize/pin-extras.sh), SHA-256 checked
#   optimize/install.sh all        both (saver, launcher)
# Our APKs are checked against the release's SHA256SUMS.txt: that catches a broken or cut-off download, not a swapped
# release (whoever can replace the APK can replace that file too). What a swapped APK can't pass is Android's own
# check that an update is signed with the same key: so our app on the TV signed with another key is never replaced
# unless ALLOW_REPLACE=1 (that removes it and its settings; TV Bro and SmartTube are never removed). A release from
# before SHA256SUMS.txt existed (an older APK_TAG) installs only with ALLOW_NO_SUMS=1.
# Play Protect's check is never switched off: when it objects, the person presses «تثبيت على أي حال» on the TV.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-optimize/venv/bin/python}"
REL=https://github.com/SultanBajaifer/UrTV/releases/download/${APK_TAG:-apk-latest}   # APK_TAG=v3.N: that numbered build
what="${1:?usage: optimize/install.sh saver|launcher|extras|all}"
case "$what" in saver|launcher|extras|all) ;; *) echo "usage: optimize/install.sh saver|launcher|extras|all" >&2; exit 2;; esac
failed=0   # an extra that did not install: the rest are still tried, then run.sh must not count the step as done

# curl with up to 3 tries. A Windows curl (Schannel) that can't reach the certificate revocation server fails every
# download; on that error, and only if this curl has the flag, the next try skips just that check.
curl_get() {
  local i rc=0 errf extra=()
  errf=$(mktemp)
  for i in 1 2 3; do
    rc=0; curl "${extra[@]+"${extra[@]}"}" "$@" 2> "$errf" || rc=$?
    [ "$rc" = 0 ] && { rm -f "$errf"; return 0; }
    [ "$rc" = 22 ] && break   # the server answered with an error (no such file): another try gives the same
    if [ "${#extra[@]}" = 0 ] && grep -qiE 'revocation|CRYPT_E_' "$errf" \
       && curl -V 2> /dev/null | grep -qi schannel && curl --help all 2> /dev/null | grep -q ssl-revoke-best-effort; then
      echo "Windows could not check the certificate revocation list: trying again without that check." >&2
      extra=(--ssl-revoke-best-effort)
    fi
    [ "$i" = 3 ] || sleep $((i * 2))
  done
  cat "$errf" >&2; rm -f "$errf"
  return "$rc"
}

sha256() { if command -v sha256sum > /dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi | awk '{print $1}'; }


pm_install() {   # $1 file name in /data/local/tmp, $2 package: pm's answer. A big APK can install silently for over a
  # minute, which ADB takes for a dead TV: it runs in the background on the TV and is polled (tv.py --bg).
  # Some operator TVs have a system service that removes apps installed from ADB seconds later; installed with the
  # Play Store as the installer they stay. So: still there after 3 s? If not, install once more that way, and say so.
  local out
  out=$("$PY" -I optimize/tv.py --bg install "pm install -r /data/local/tmp/$1")
  if grep -q Success <<< "$out"; then
    sleep 3
    if ! "$PY" -I optimize/tv.py "pm list packages $2" | tr -d '\r' | grep -qx "package:$2"; then
      echo "$2 was removed right after the install (a service of this TV does that to apps installed over ADB): installing it again as if from the Play Store." >&2
      out=$("$PY" -I optimize/tv.py --bg install "pm install -i com.android.vending -r /data/local/tmp/$1")
      sleep 3
      if grep -q Success <<< "$out" && ! "$PY" -I optimize/tv.py "pm list packages $2" | tr -d '\r' | grep -qx "package:$2"; then
        out="Failure [$2 is removed by this TV right after every install]"
      fi
    fi
  fi
  printf '%s\n' "$out"
}

push_install() {   # $1 apk name, $2 package
  if [ "$2" = sa.urtv.home ]; then   # the home app targets an older SDK than Play Protect likes (seen on Android 12-14)
    echo "للشخص: بعد لحظات ممكن تطلع على التلفزيون رسالة من Play Protect؛ إذا طلعت اضغط «تثبيت على أي حال» (Install anyway)."
  fi
  if ! curl_get -fsSL -o "optimize/$1" "$REL/$1"; then
    echo "!! Could not download $REL/$1 (tag ${APK_TAG:-apk-latest}): no such build, or no internet"; exit 1
  fi
  local sums want got
  sums=$(curl_get -fsSL "$REL/SHA256SUMS.txt" 2> /dev/null || true)
  want=$(awk -v f="$1" '$2 == f {print $1}' <<< "$sums")
  got=$(sha256 "optimize/$1")
  if [ -z "$want" ] && [ "${ALLOW_NO_SUMS:-}" = 1 ]; then
    echo "ALLOW_NO_SUMS=1: $REL has no SHA256SUMS.txt (a release from before it existed): $1 installs unchecked."
  elif [ -z "$want" ]; then
    echo "!! $REL has no SHA256SUMS.txt entry for $1: refusing an unchecked APK (an older release? ALLOW_NO_SUMS=1)"
    rm -f "optimize/$1"; exit 1
  elif [ "$want" != "$got" ]; then
    echo "!! $1 does not match its SHA-256 ($got, expected $want): not installed"; rm -f "optimize/$1"; exit 1
  fi
  "$PY" -I optimize/tv.py --push-b64 "optimize/$1" "/data/local/tmp/$1"
  local out
  out=$(pm_install "$1" "$2")
  if grep -q INSTALL_FAILED_VERIFICATION_FAILURE <<< "$out"; then
    # Play Protect stopped it. Its check stays on: the person decides, on the TV, and the install is tried once more
    echo "Play Protect stopped the install. Its check is left on: the person decides on the TV."
    echo "للشخص: انتبه للتلفزيون الحين: لو طلعت رسالة من Play Protect (التطبيق «غير آمن» أو «مبني لإصدار قديم»)، اضغط «تثبيت على أي حال» (Install anyway) بالريموت. هذا تطبيق تلفزيونك، والرسالة تطلع لأن الشاشة الرئيسية مبنية لإصدار أندرويد أقدم."
    sleep 20
    out=$(pm_install "$1" "$2")
  fi
  if ! grep -q Success <<< "$out"; then
    # a signing-key clash: the app on the TV was not built with this repo's key. Android's own refusal is the check a
    # swapped APK can't pass, so it stands unless the owner changed the key on purpose (ALLOW_REPLACE=1)
    if grep -qE 'UPDATE_INCOMPATIBLE|signatures do not match' <<< "$out" && [ "${ALLOW_REPLACE:-}" != 1 ]; then
      "$PY" -I optimize/tv.py "rm -f /data/local/tmp/$1" > /dev/null || true
      echo "!! $2 on the TV is signed with a different key than this APK. Refusing: a different key means it was not"
      echo "   built with your repo's key (or the key changed). If you changed the key on purpose:"
      echo "   ALLOW_REPLACE=1 $0 $what   (removes $2 and its settings first)"
      exit 1
    elif grep -qE 'UPDATE_INCOMPATIBLE|signatures do not match' <<< "$out"; then
      echo "ALLOW_REPLACE=1: $2 is signed with another key: removing it, then installing again."
      # removing the home app while the stock one is off would leave the TV with no home at all
      [ "$2" = sa.urtv.home ] && "$PY" -I optimize/tv.py "pm enable ${STOCK%%/*}" > /dev/null || true
      "$PY" -I optimize/tv.py "pm uninstall $2" || true
      out=$(pm_install "$1" "$2")
      grep -q Success <<< "$out" || { echo "!! Install of $1 failed again: $out"; exit 1; }
    else
      echo "!! Install of $1 failed: $out"
      if grep -q INSTALL_FAILED_VERIFICATION_FAILURE <<< "$out"; then
        echo "   Play Protect still stops it. Tell the person, in Arabic: «لما نعيد المحاولة، انتبه للتلفزيون واضغط «تثبيت على أي حال» لما تطلع رسالة Play Protect». Then the same command once more."
        echo "   Never switch Play Protect or its checks off (package_verifier_enable, verifier_verify_adb_installs), and never ask the person to: if it keeps refusing, stop and tell them."
      fi
      exit 1
    fi
  fi
  "$PY" -I optimize/tv.py "rm -f /data/local/tmp/$1"
  rm -f "optimize/$1"
}

# TV Bro and SmartTube: only the exact files pinned in optimize/lists/extras.lock (optimize/pin-extras.sh), each
# checked against its SHA-256 there; never "the latest release". An app already on the TV is left as it is.
from_lock() {   # $1 package
  local abis line url want name got out
  if "$PY" -I optimize/tv.py "pm list packages $1" | tr -d '\r' | grep -qx "package:$1"; then
    echo "$1 is already on the TV: left as it is (it updates itself)."; return 0
  fi
  abis=$("$PY" -I optimize/tv.py "getprop ro.product.cpu.abilist" | tr -d '\r')
  line=$(awk -v p="$1" -v abis="$abis,universal" '
    $1 == p { u[$2] = $0 }
    END { n = split(abis, a, ","); for (i = 1; i <= n; i++) if (a[i] in u) { print u[a[i]]; exit } }
  ' optimize/lists/extras.lock)
  if [ -z "$line" ]; then echo "!! No pinned build of $1 for this TV ($abis) in optimize/lists/extras.lock: skipped"; failed=1; return 0; fi
  read -r _ _ _ url want <<< "$line"
  name=$(basename "$url")
  # a file an earlier try downloaded in full (an upload cut off by a flaky Wi-Fi) is not downloaded again
  if [ -f "optimize/$name" ] && [ "$(sha256 "optimize/$name")" = "$want" ]; then
    echo "$name is already downloaded: not downloading it again."
  elif ! curl_get -fsSL -o "optimize/$name" "$url"; then echo "!! Could not download $url"; failed=1; return 0; fi
  got=$(sha256 "optimize/$name")
  if [ "$got" != "$want" ]; then
    echo "!! $name does not match its pinned SHA-256 ($got, expected $want): not installed"
    rm -f "optimize/$name"; failed=1; return 0
  fi
  "$PY" -I optimize/tv.py --push-b64 "optimize/$name" "/data/local/tmp/$name"
  out=$(pm_install "$name" "$1")
  "$PY" -I optimize/tv.py "rm -f /data/local/tmp/$name" > /dev/null
  if grep -q Success <<< "$out"; then echo "Installed $name"
  elif grep -qE 'UPDATE_INCOMPATIBLE|signatures do not match' <<< "$out"; then
    echo "$1 is already installed from somewhere else: left as it is (with its settings)."   # never removed
  else echo "!! Install of $name failed: $out"; failed=1; fi
  rm -f "optimize/$name"
}

if [ "$what" = extras ]; then
  if [ ! -s optimize/lists/extras.lock ]; then   # not pinned yet: skipped, so the rest of the setup goes on
    echo "TV Bro and SmartTube skipped: not pinned yet. To add them later: optimize/pin-extras.sh, then optimize/install.sh extras"
    exit 0
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
    "am start --activity-clear-task -n sa.urtv.screensaver/.SettingsActivity" \
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
  # exact alarms for the adhan (Android 12 and newer; older TVs need nothing)
  "$PY" -I optimize/tv.py "appops set sa.urtv.home SCHEDULE_EXACT_ALARM allow" || true

  # The setup wizard (setupwraith) is turned off only when it really answers Home. Disabling it can delete the Wi-Fi network
  # that was saved during the first-run wizard (CleanYourTV's README, github.com/Gathin23/cleanyourtv, MIT: a network saved
  # then belongs to the wizard, and Android removes an app's saved networks when it is disabled; two TCL sets lost their
  # Wi-Fi password at the first restart, and a Nokia refused it). Their guard asks `dumpsys wifi` who owns the networks.
  WRAITH=com.google.android.tungsten.setupwraith
  wraith_answers_home() {   # the apps that answer HOME, all of them (resolve-activity only names the winner)
    "$PY" -I optimize/tv.py "cmd package query-activities --brief -a android.intent.action.MAIN -c android.intent.category.HOME 2> /dev/null; cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME" \
      | grep "$WRAITH" > /dev/null   # no grep -q: with pipefail its early exit would SIGPIPE the command before it
  }
  wifi_owner() {   # owned: a saved network belongs to the wizard; other: none does; unknown: the TV did not say
    local w owners
    w=$("$PY" -I optimize/tv.py "dumpsys wifi") || { echo unknown; return; }
    owners=$(grep -o 'cname=[^ ]*' <<< "$w" || true)
    if [ -z "$owners" ]; then echo unknown
    elif grep -q setupwraith <<< "$owners"; then echo owned
    else echo other; fi
  }
  wraith_off() {   # 0: turned off; 1: left on (owns the Wi-Fi, or it could not be told)
    case "$(wifi_owner)" in
      other) "$PY" -I optimize/tv.py "pm disable-user --user 0 $WRAITH" > /dev/null || true; return 0 ;;
      owned) echo "The setup wizard of this TV owns its saved Wi-Fi network: left on, so the network is not lost." ;;
      *)     echo "Could not tell who owns the saved Wi-Fi network: the setup wizard is left on." ;;
    esac
    return 1
  }

  # Steps 2-4 as one function, so an ADB drop in the middle (TCL G08: Wi-Fi fell during the batch) can be retried.
  # "verify" as $1: only step 4 (the switch is armed already and the batch may have run).
  # Returns 0: the new home is on screen and the switch is disarmed; 1: tv.py failed (connection lost);
  # 2: Home did not open the new launcher; 3: the safety switch fired first.
  switch_home() {
    local top res stepout ours=no _ wraith=no cmds
    if [ "${1:-}" != verify ]; then
      # before anything is changed: does the wizard answer Home, and can it go without taking the Wi-Fi with it?
      if wraith_answers_home; then
        case "$(wifi_owner)" in
          owned) return 5 ;;
          other) wraith=listed ;;
          *) echo "The setup wizard answers Home, but the TV did not say who owns its saved Wi-Fi: the wizard is left on, so the network is not lost." ;;
        esac
      fi
      # 2. Arm the safety switch on the TV: it restores the stock home in 300 s unless we confirm (slow ADB needs time).
      "$PY" -I optimize/tv.py --push-b64 optimize/deadman.sh /data/local/tmp/deadman.sh || return 1
      printf '%s\n' \
        "rm -f /data/local/tmp/home_ok" \
        "nohup sh /data/local/tmp/deadman.sh $STOCK 300 > /dev/null 2>&1 &" \
        | "$PY" -I optimize/tv.py --batch || return 1
      echo "Safety switch armed: the stock home comes back by itself in 5 minutes unless the new home works."

      # 3. Switch: the HOME role (Android 10+; the classic set-home-activity for older sets and as a backup), then
      #    the setup app off, then the stock home (this order avoided the black screen).
      cmds=("cmd role add-role-holder --user 0 android.app.role.HOME sa.urtv.home"
            "cmd package set-home-activity --user 0 sa.urtv.home/.MainActivity")
      [ "$wraith" != listed ] || cmds+=("pm disable-user --user 0 $WRAITH")
      cmds+=("pm disable-user --user 0 ${STOCK%%/*}"
             "cmd package set-home-activity --user 0 sa.urtv.home/.MainActivity"
             "am force-stop com.android.tv.settings"
             "input keyevent KEYCODE_HOME")
      stepout=$(printf '%s\n' "${cmds[@]}" | "$PY" -I optimize/tv.py --batch) || return 1
      printf '%s\n' "$stepout"
      # Nokia Streaming Box 8000 answers «This command is illegal» to pm disable-user for its own launcher: no switch there.
      # Put the stock home back as it was and stop the switch (4); nothing else of the setup depends on it.
      if grep -A2 -F "\$ pm disable-user --user 0 ${STOCK%%/*}" <<< "$stepout" | grep -qi 'illegal'; then
        printf '%s\n' "cmd role add-role-holder --user 0 android.app.role.HOME ${STOCK%%/*}" \
          "cmd package set-home-activity --user 0 $STOCK" "pm enable com.google.android.tungsten.setupwraith" \
          "touch /data/local/tmp/home_ok" "input keyevent KEYCODE_HOME" | "$PY" -I optimize/tv.py --batch > /dev/null || true
        return 4
      fi
    fi
    # 4. Verify Home really opens the new launcher (a few tries: a slow TV), then disarm the switch.
    for _ in 1 2 3; do
      sleep 6
      top=$("$PY" -I optimize/tv.py "dumpsys activity activities | grep -E 'mResumedActivity|topResumedActivity'") || return 1
      if grep -q sa.urtv.home <<< "$top"; then ours=yes; break; fi
      "$PY" -I optimize/tv.py "input keyevent KEYCODE_HOME" > /dev/null || return 1
      # it took Home back after the switch: now it has to go (only if that cannot cost the Wi-Fi)
      if [ "$wraith" = no ] && wraith_answers_home; then wraith=listed; wraith_off || true; fi
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
  home_skipped=0
  case "$rc" in
    0) ;;
    5) echo "!! The setup wizard of this TV answers Home and owns its saved Wi-Fi network: turning it off would delete the network and take the TV off Wi-Fi. Nothing was changed."
       echo "   Tell the person, in Arabic: «على التلفزيون: الإعدادات ← الشبكة والإنترنت، انسَ شبكة الواي فاي (Forget) واتصل فيها من جديد، وقلّي «تم»» (the network then belongs to the system, not the wizard). Then the same command."
       exit 1 ;;
    4) home_skipped=1
       echo "Home switch skipped: this TV refuses to turn its own home screen off («This command is illegal», seen on a Nokia Streaming Box 8000). It keeps its own home; the stock home is back as it was. The screensaver and the rest of the setup work without it."
       mkdir -p "${URTV_RUN_DIR:-optimize/run}"
       echo "Home switch: skipped, this TV refuses to turn its own home screen off" > "${URTV_RUN_DIR:-optimize/run}/home-skipped.txt" ;;
    2) echo "!! Home did not open the new launcher. Leave the TV alone: the stock home returns within 5 minutes."
       echo "   Some TCL firmware pins Home to the stock launcher; on those sets keep the stock home."
       exit 1 ;;
    *) echo "!! The safety switch put the stock home back (ADB was too slow). Nothing is broken: run the same command again."
       exit 1 ;;
  esac
  if [ "$home_skipped" = 0 ]; then
    # 5. Only now: the stock home's helpers are dead weight (restore.sh brings them back).
    grep -vE '^\s*(#|$)' optimize/lists/home-replaced.txt | awk '{print "pm disable-user --user 0 " $1}' \
      | "$PY" -I optimize/tv.py --batch > /dev/null || true
    rm -f "${URTV_RUN_DIR:-optimize/run}/home-skipped.txt"
    echo "Launcher is home. Press Home from inside an app to double-check."
  fi
  echo "Undo everything: optimize/reset.sh"
fi

# The report's «Versions:» line was written by run.sh before this install: say what is on the TV now, so run.sh's report
# agrees with the TV. (Only when the report exists; no report, nothing to correct.)
if [ "$what" != extras ] && [ -f "${URTV_RUN_DIR:-optimize/run}/report.md" ]; then
  rep="${URTV_RUN_DIR:-optimize/run}/report.md"
  vs=$("$PY" -I optimize/tv.py "dumpsys package sa.urtv.screensaver 2> /dev/null | grep -m1 versionName" 2> /dev/null | sed 's/.*=//' | tr -d '\r ') || vs=""
  vh=$("$PY" -I optimize/tv.py "dumpsys package sa.urtv.home 2> /dev/null | grep -m1 versionName" 2> /dev/null | sed 's/.*=//' | tr -d '\r ') || vh=""
  if [ -n "$vs$vh" ]; then
    line="Versions: screensaver ${vs:-none}, home ${vh:-none}"
    if grep -q '^Versions:' "$rep"; then
      awk -v l="$line" '/^Versions:/ { print l; next } { print }' "$rep" > "$rep.tmp" && mv "$rep.tmp" "$rep"
    else
      printf '%s\n' "$line" >> "$rep"
    fi
  fi
fi
