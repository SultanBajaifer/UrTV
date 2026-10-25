#!/usr/bin/env python3
"""optimize/lockdown.sh with a stub tv.py: it says "ADB is off" and deletes the ADB key only when ADB stopped answering
while the TV is still on the network; never when the TV is merely asleep, still answering, or unknown.

    python3 tests/lockdown_test.py
"""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# fake python: tv.py "echo urtv-ok" answers while $T/on exists; --batch with adb_enabled 0 removes it if OBEYS=1;
# -c (the network check) exits by NET (1 = on the network)
STUB = r'''#!/usr/bin/env bash
[ "$2" = -c ] && { [ "$NET" = 1 ]; exit $?; }
shift 2
case "$1" in
  --batch) in=$(cat); echo "batch" >> "$T/log"; case "$in" in *"adb_enabled 0"*) [ "$OBEYS" = 1 ] && rm -f "$T/on" ;; esac ;;
  "echo urtv-ok") [ -f "$T/on" ] && echo urtv-ok ;;
esac
exit 0
'''
failed = 0


def check(name, ok, detail=""):
    global failed
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  -> {detail}"))
    failed += not ok


def run(on=True, obeys=True, net=True, state_a=True, host="192.0.2.7"):
    t = Path(tempfile.mkdtemp())
    (t / "tree/optimize/adbkey").mkdir(parents=True)
    (t / "tree/optimize/adbkey/adbkey").write_text("key")
    shutil.copy(ROOT / "optimize/lockdown.sh", t / "tree/optimize")
    if state_a:
        (t / "tree/optimize/state-A.txt").write_text("== serial\nx\n")
    if host:
        (t / "tree/optimize/.tv_host").write_text(host + "\n")
    if on:
        (t / "on").write_text("")
    (t / "py").write_text(STUB); (t / "py").chmod(0o755)
    (t / "bin").mkdir(); (t / "bin/sleep").write_text("#!/bin/sh\nexit 0\n"); (t / "bin/sleep").chmod(0o755)
    env = dict(os.environ, PY=str(t / "py"), T=str(t), OBEYS="1" if obeys else "0", NET="1" if net else "0",
               PATH=f"{t / 'bin'}:{os.environ['PATH']}")
    env.pop("TV_HOST", None)
    r = subprocess.run(["bash", str(t / "tree/optimize/lockdown.sh")], capture_output=True, text=True, env=env)
    key = (t / "tree/optimize/adbkey").exists()
    log = (t / "log").read_text() if (t / "log").exists() else ""
    shutil.rmtree(t)
    return r.returncode, r.stdout + r.stderr, key, log


c, o, key, _ = run()
check("ADB really off (TV on the network, ADB silent): says so, deletes the key", c == 0 and "ADB is off" in o and not key, o)
c, o, key, _ = run(obeys=False)
check("TV still answers ADB: says it is still on, keeps the key", c == 1 and "still on" in o and key, o)
c, o, key, _ = run(net=False)
check("no answer at all (asleep): not sure, keeps the key", c == 1 and "Not sure" in o and key, o)
c, o, key, log = run(on=False)
check("TV not answering before: nothing sent, key kept", c == 1 and "nothing changed" in o and key and "batch" not in log, o)
c, o, key, log = run(state_a=False)
check("no state A yet: refuses before touching the TV", c == 1 and "state-A" in o and key and "batch" not in log, o)
c, o, key, log = run(host="")
check("no known address: refuses (never a check against localhost)", c == 1 and "address" in o and key and "batch" not in log, o)
sys.exit(1 if failed else 0)
