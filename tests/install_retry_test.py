"""optimize/install.sh launcher when ADB drops during the switch: a stub tv.py, no TV needed.

    python3 tests/install_retry_test.py

Each case copies install.sh into a scratch tree, puts a fake `python` (PY), `curl` and `sleep` first, and checks
what the script printed, how it ended and how often it armed the safety switch.
"""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

STUB_PY = r'''#!/usr/bin/env bash
# fake: python -I optimize/tv.py <args>; state files live in $T
shift 2
log() { echo "$*" >> "$T/log"; }
case "$1" in
  --push-b64) exit 0 ;;
  --batch)
    in=$(cat)
    case "$in" in
      *nohup*) log arm; rm -f "$T/home_ok" ;;
      *setupwraith*)
        n=$(( $(cat "$T/switches" 2>/dev/null || echo 0) + 1 )); echo $n > "$T/switches"
        if [ "$n" -le "$FAIL_SWITCHES" ]; then   # the connection drops in this batch
          [ "$FIRST_DROP" = ours ] && [ "$n" = 1 ] && echo ours > "$T/home"
          [ "$FIRST_DROP" = stock ] && [ "$n" = 1 ] && echo stock > "$T/home"
          log drop; exit 1
        fi
        echo ours > "$T/home" ;;
      *) log other-batch ;;
    esac
    exit 0 ;;
esac
case "$1" in
  *launcherx*) echo "package:com.google.android.apps.tv.launcherx" ;;
  "pm install"*) echo "${INSTALL_OUT:-Success}" ;;
  "pm uninstall"*) log uninstall ;;
  "getprop ro.serialno")
    n=$(( $(cat "$T/polls" 2>/dev/null || echo 0) + 1 )); echo $n > "$T/polls"
    [ "$n" -le "$DOWN_POLLS" ] && exit 1
    echo 0123456789 ;;
  *resolve-activity*) [ "$(cat "$T/home" 2>/dev/null)" = ours ] && echo sa.urtv.home/.MainActivity || echo stock/.Home ;;
  *dumpsys*) [ "$(cat "$T/home" 2>/dev/null)" = ours ] && echo "mResumedActivity: sa.urtv.home" ;;
  "touch /data/local/tmp/home_ok") log disarm; touch "$T/home_ok" ;;
esac
exit 0
'''

EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"   # SHA-256 of the stub's empty APK

def run(name, fail_switches, first_drop, down_polls=0, what="launcher", **extra):
    t = Path(tempfile.mkdtemp())
    tree, bin_ = t / "tree", t / "bin"
    (tree / "optimize" / "lists").mkdir(parents=True); bin_.mkdir()
    shutil.copy(ROOT / "optimize" / "install.sh", tree / "optimize")
    shutil.copy(ROOT / "optimize" / "deadman.sh", tree / "optimize")
    (tree / "optimize" / "lists" / "home-replaced.txt").write_text("# none\n")
    for f, body in (("py", STUB_PY), ("curl", '#!/bin/sh\n'   # an empty APK, and the release's SHA256SUMS.txt that lists it
                     'case "$*" in *SHA256SUMS.txt*) printf "%s  urtv-home.apk\\n%s  urtv-screensaver.apk\\n" "${SUM:-$EMPTY}" "${SUM:-$EMPTY}"; exit 0 ;; esac\n'
                     'while [ $# -gt 0 ]; do [ "$1" = -o ] && : > "$2"; shift; done\n'),
                    ("sleep", "#!/bin/sh\nexit 0\n")):
        (bin_ / f).write_text(body); (bin_ / f).chmod(0o755)
    env = dict(os.environ, PATH=f"{bin_}:{os.environ['PATH']}", PY=str(bin_ / "py"), T=str(t),
               FAIL_SWITCHES=str(fail_switches), FIRST_DROP=first_drop, DOWN_POLLS=str(down_polls), EMPTY=EMPTY, **extra)
    r = subprocess.run(["bash", str(tree / "optimize" / "install.sh"), what], env=env, capture_output=True, text=True)
    log = (t / "log").read_text().split() if (t / "log").exists() else []
    shutil.rmtree(t)
    return r.returncode, r.stdout + r.stderr, log

AGAIN = "the TV is back, trying the switch again"
CHECK = "already set: checking it"
cases = [
    ("no drop", run("a", 0, ""), lambda c, o, l: c == 0 and "ADB dropped" not in o and l.count("arm") == 1),
    ("drop, stock home back: switch again", run("b", 1, "stock", down_polls=2),
     lambda c, o, l: c == 0 and AGAIN in o and l.count("arm") == 2 and l.count("drop") == 1 and "Launcher is home" in o),
    ("drop, new home already set: only verify", run("c", 1, "ours"),
     lambda c, o, l: c == 0 and CHECK in o and l.count("arm") == 1 and l.count("disarm") == 1),
    ("two drops: gives up, exits 1", run("d", 2, "stock"),
     lambda c, o, l: c == 1 and l.count("arm") == 2 and "!! The safety switch put the stock home back" in o),
    ("TV never answers: exits 1", run("e", 1, "stock", down_polls=99),
     lambda c, o, l: c == 1 and "did not come back within 6 minutes" in o and l.count("arm") == 1),
    # checksums and signing keys: a swapped or broken APK never reaches the TV, nothing is removed to make room
    ("saver: SHA-256 mismatch refuses", run("f", 0, "", what="saver", SUM="0" * 64),
     lambda c, o, l: c == 1 and "does not match its SHA-256" in o and "uninstall" not in l),
    ("saver: other signing key refuses, removes nothing",
     run("g", 0, "", what="saver", INSTALL_OUT="Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE: signatures do not match]"),
     lambda c, o, l: c == 1 and "Refusing" in o and "uninstall" not in l),
    ("saver: other signing key with ALLOW_REPLACE=1 replaces",
     run("h", 0, "", what="saver", ALLOW_REPLACE="1",
         INSTALL_OUT="Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE: signatures do not match]"),
     lambda c, o, l: "uninstall" in l),
]
bad = [n for n, (c, o, l), ok in cases if not ok(c, o, l)]
for n, (c, o, l), ok in cases:
    print(f"install.sh: {n}: " + ("ok" if ok(c, o, l) else f"WRONG (exit {c}, log {l})\n{o}"))
sys.exit(1 if bad else 0)
