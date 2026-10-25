"""optimize/snapshot.py: going back to A (the TV before UrTV) on made-up TV states, and save/restore with a stub TV.

    python3 tests/snapshot_test.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "optimize"))
import snapshot  # noqa: E402

STOCK = "com.google.android.apps.tv.launcherx/com.google.android.apps.tv.launcherx.home.HomeActivity"
OURS_HOME = "sa.urtv.home/.MainActivity"


def state(packages, disabled=(), home=STOCK, serial="TCL123", **settings):
    s = {k: "" for k in snapshot.QUERIES}
    s.update(serial=serial, packages="\n".join(f"package:{p}" for p in packages),
             disabled="\n".join(f"package:{p}" for p in disabled), home=home, vending_bucket="10",
             vending_bg="RUN_IN_BACKGROUND: allow", vending_any_bg="RUN_ANY_IN_BACKGROUND: allow", cached_limit="null")
    s.update({f"global/{k}": "1.0" for k in ("window_animation_scale", "transition_animation_scale", "animator_duration_scale")})
    s.update(settings)
    return s


BASE = ["com.tcl.bi", "com.google.android.apps.mediashell", "com.netflix.ninja", "com.google.android.apps.tv.launcherx",
        "com.tcl.hearaid", "com.tcl.factorydemo"]
failures = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  -> {detail}"))
    if not ok:
        failures.append(name)


def flat(before, now):
    phases, _ = snapshot.plan(before, now)
    return phases, [c for ph in phases for c in ph]


# after a whole setup (B), then an update (C): back to A in one go
A = state(BASE, disabled=["com.tcl.factorydemo"])   # TCL itself shipped this one off
C = state(BASE + ["sa.urtv.home", "sa.urtv.screensaver", "org.smarttube.stable", "com.example.mine"],
          disabled=["com.tcl.bi", "com.google.android.apps.tv.launcherx", "com.tcl.factorydemo"], home=OURS_HOME,
          vending_bucket="45", vending_bg="RUN_IN_BACKGROUND: ignore",
          **{"global/window_animation_scale": "0.5", "secure/screensaver_components": "sa.urtv.screensaver/.ScreenDream"})
A["secure/screensaver_components"] = "null"
phases, cmds = flat(A, C)
check("apps UrTV turned off come back on", "pm enable com.tcl.bi" in phases[0])
check("an app TCL itself shipped off stays off (A exactly, not 'everything on')", not any("factorydemo" in c for c in cmds))
check("Home goes back to the stock home, with its notification access", f"cmd package set-home-activity --user 0 {STOCK}" in phases[0]
      and any("allow_listener" in c for c in phases[0]))
check("our apps and SmartTube are removed, in phase 2 (after Home is back)",
      {"pm uninstall sa.urtv.home", "pm uninstall sa.urtv.screensaver", "pm uninstall org.smarttube.stable"} <= set(phases[1])
      and not any("uninstall" in c for c in phases[0]))
check("an app the owner installed meanwhile is never removed", not any("example.mine" in c for c in cmds))
check("tweaks and the screensaver back to A", "settings put global window_animation_scale 1.0" in phases[2]
      and "am set-standby-bucket com.android.vending 10" in phases[2]
      and "cmd appops set com.android.vending RUN_IN_BACKGROUND allow" in phases[2]
      and "settings delete secure screensaver_components" in phases[2])
check("an app off in A that something turned on since is turned off again (A exactly)",
      "pm disable-user --user 0 com.tcl.factorydemo" in flat(A, state(BASE))[1])
check("a protected app that was off in A is not turned off again",
      not any("disable-user" in c for c in flat(state(BASE, disabled=["com.google.android.apps.mediashell"]), state(BASE))[1]))

# Home in A was not a real home app: Android's chooser (two homes), or ours (A taken on a TV set up before)
for name, home in (("Android's chooser", "android/com.android.internal.app.ResolverActivity"), ("our own", OURS_HOME)):
    _, cmds = flat(state(BASE, home=home), state(BASE + ["sa.urtv.home"], home=OURS_HOME))
    check(f"Home in A was {name}: the stock home is restored, never 'android' or ours",
          f"cmd package set-home-activity --user 0 {STOCK}" in cmds and "pm enable android" not in cmds
          and not any("role-holder --user 0 android.app.role.HOME android" == c or "HOME sa.urtv" in c for c in cmds), cmds)
check("the TV already matches A: nothing to do", not any(flat(A, A)[0]))

# with a stub TV: save once, never replace; restore refuses another TV and never removes our Home while it is Home
FAKE_TV = r'''# fake optimize/tv.py --batch: answers from $T/tv.json and applies what it is told
import json, os, sys
T = os.environ["T"]; st = json.load(open(T + "/tv.json"))
cmds = [l.strip() for l in sys.stdin.read().splitlines() if l.strip()]
out = []
for c in cmds:
    out.append("$ " + c)
    if c == "getprop ro.serialno": out.append(st["serial"])
    elif c == "pm list packages": out += ["package:" + p for p in st["packages"]]
    elif c == "pm list packages -d": out += ["package:" + p for p in st["disabled"]]
    elif c.startswith("cmd package resolve-activity"): out.append(st["home"])
    elif c.startswith("pm enable "): st["disabled"] = [p for p in st["disabled"] if p != c.split()[-1]]
    elif c.startswith("pm disable-user "): st["disabled"] = sorted(set(st["disabled"]) | {c.split()[-1]})
    elif c.startswith("cmd package set-home-activity") and not st.get("stuck"): st["home"] = c.split()[-1]
    elif c.startswith("pm uninstall "): st["packages"] = [p for p in st["packages"] if p != c.split()[-1]]
    elif c.startswith("settings get ") or c.startswith("device_config get"): out.append("null")
    else: out.append("")
open(T + "/log", "a").write("\n".join(cmds) + "\n")
json.dump(st, open(T + "/tv.json", "w"))
print("\n".join(out))
'''
tmp = Path(tempfile.mkdtemp())
(tmp / "optimize/lists").mkdir(parents=True)
shutil.copy(ROOT / "optimize/snapshot.py", tmp / "optimize")
shutil.copy(ROOT / "optimize/lists/keep.txt", tmp / "optimize/lists")
(tmp / "optimize/tv.py").write_text(FAKE_TV)
env = dict(os.environ, T=str(tmp))


def tv(**st):
    (tmp / "tv.json").write_text(__import__("json").dumps(st))


def snap(*a):
    r = subprocess.run([sys.executable, str(tmp / "optimize/snapshot.py"), *a], capture_output=True, text=True, env=env)
    return r.returncode, r.stdout + r.stderr


A_FILE = str(tmp / "state-A.txt")
tv(serial="TCL123", packages=BASE, disabled=["com.tcl.factorydemo"], home=STOCK)
c, o = snap("save", A_FILE)
check("save: A written", c == 0 and Path(A_FILE).is_file(), o)
c, o = snap("save", A_FILE)
check("save: A is never replaced", c != 0 and "never replaced" in o, o)
tv(serial="TCL123", packages=BASE + ["sa.urtv.home"], disabled=["com.google.android.apps.tv.launcherx"], home=OURS_HOME)
c, o = snap("restore", A_FILE)
st = __import__("json").loads((tmp / "tv.json").read_text())
check("restore: back to A (stock Home, ours removed, launcher on)", c == 0 and "matches A" in o and st["home"] == STOCK
      and "sa.urtv.home" not in st["packages"] and "com.google.android.apps.tv.launcherx" not in st["disabled"], (o, st))
tv(serial="TCL123", packages=BASE + ["sa.urtv.home"], disabled=[], home=OURS_HOME, stuck=True)
c, o = snap("restore", A_FILE)
st = __import__("json").loads((tmp / "tv.json").read_text())
check("restore: Home will not leave ours: our home app is NOT removed (the TV keeps a home)",
      c != 0 and "sa.urtv.home" in st["packages"] and "still our home screen" in o, (o, st))
tv(serial="OTHER9", packages=BASE + ["sa.urtv.home"], disabled=[], home=OURS_HOME)
(tmp / "log").write_text("")
c, o = snap("restore", A_FILE)
check("restore: another TV is refused, nothing sent but questions",
      c != 0 and "another TV" in o and "uninstall" not in (tmp / "log").read_text(), o)
c, _ = snap("same", A_FILE)
check("same: another TV answers 1", c == 1)
shutil.rmtree(tmp)
sys.exit(1 if failures else 0)
