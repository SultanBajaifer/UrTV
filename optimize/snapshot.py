#!/usr/bin/env python3
"""The TV as it was before UrTV changed anything ("A"), and putting it back (optimize/rollback.sh).

    snapshot.py save <file>        once, before the first change: packages (all, disabled), Home, screensaver,
                                   animation, Play Store limits, freezer, accessibility; refuses to replace a file
    snapshot.py diff <file>        what restore would do, without doing it
    snapshot.py restore <file>     put the TV back to <file>
    snapshot.py same <file>        exit 0 if <file> is this TV's (or either serial is unknown), 1 if another TV's

Restore never disables anything in lists/keep.txt and only uninstalls apps UrTV installs (ours, TV Bro, SmartTube)
that were not there in <file>; the owner's own apps, logins and data are never touched. It refuses another TV.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable
OURS = ["sa.urtv.screensaver", "sa.urtv.home", "com.phlox.tvwebbrowser", "org.smarttube.stable",
        "sa.yourtv.home", "sa.yourtv.screensaver", "com.abdullah.tvhome", "com.abdullah.tvsaver"]   # and older names
STOCK_HOMES = [   # the stock homes, best first: what Home goes back to when A's own entry is not a home app
    "com.google.android.apps.tv.launcherx/com.google.android.apps.tv.launcherx.home.HomeActivity",
    "com.google.android.tvlauncher/.MainActivity",
]
LISTENER = "com.google.android.apps.tv.launcherx/.coreservices.notificationlistener.TvNotificationListenerService"
SETTINGS = [   # namespace, key: as `settings get`
    ("global", "window_animation_scale"), ("global", "transition_animation_scale"),
    ("global", "animator_duration_scale"), ("global", "cached_apps_freezer"),
    ("secure", "screensaver_enabled"), ("secure", "screensaver_components"),
    ("secure", "screensaver_default_component"), ("system", "screen_off_timeout"),
    ("secure", "enabled_accessibility_services"),   # the sleep timer's screen-off service
]
HOME_QUERY = "cmd package resolve-activity --brief -c android.intent.category.HOME -a android.intent.action.MAIN"
QUERIES = {
    "serial": "getprop ro.serialno",
    "packages": "pm list packages",
    "disabled": "pm list packages -d",
    "home": HOME_QUERY,
    "vending_bucket": "am get-standby-bucket com.android.vending",
    "vending_bg": "cmd appops get com.android.vending RUN_IN_BACKGROUND",
    "vending_any_bg": "cmd appops get com.android.vending RUN_ANY_IN_BACKGROUND",
    "cached_limit": "device_config get activity_manager max_cached_processes",
    **{f"{ns}/{k}": f"settings get {ns} {k}" for ns, k in SETTINGS},
}


def batch(cmds):
    out = subprocess.run([PY, "-I", str(HERE / "tv.py"), "--batch"], input="\n".join(cmds) + "\n",
                         capture_output=True, text=True, check=True).stdout
    res, cur = {}, None
    for line in out.replace("\r", "").splitlines():
        if line.startswith("$ ") and line[2:] in cmds:
            cur = line[2:]
            res[cur] = []
        elif cur is not None:
            res[cur].append(line)
    return {c: "\n".join(v).strip() for c, v in res.items()}


def read_state():
    got = batch(list(QUERIES.values()))
    missing = [q for q in QUERIES.values() if q not in got]
    if missing:   # the connection dropped in the middle: a partial picture must never become A, or be restored to
        raise RuntimeError(f"the TV did not answer {len(missing)} of the questions (ADB dropped?)")
    return {k: got[q] for k, q in QUERIES.items()}


def pkgs(text):
    return {m for m in re.findall(r"^package:(\S+)", text, re.M)}


def save(path):
    path = Path(path)
    if path.exists():
        sys.exit(f"!! {path} already exists: A is saved once, before the first change, and never replaced")
    state = read_state()
    if not pkgs(state["packages"]):
        sys.exit("!! the TV listed no packages: nothing saved")
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for k, v in state.items():
            f.write(f"== {k}\n{v}\n")
    os.replace(tmp, path)
    print(f"Saved the TV as it is now (A): {path}")


def load(path):
    state, cur = {}, None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith("== "):
            cur = line[3:]
            state[cur] = []
        elif cur is not None:
            state[cur].append(line)
    state = {k: "\n".join(v).strip() for k, v in state.items()}
    for k in QUERIES:   # a file from an older version lacks a few keys: those are left as they are
        state.setdefault(k, "")
    return state


def keep_list():
    lines = (HERE / "lists" / "keep.txt").read_text(encoding="utf-8").splitlines()
    return {l.split()[0] for l in lines if l.strip() and not l.lstrip().startswith("#")}


def bucket(text):
    m = re.search(r"\b(\d+)\b", text)
    return m.group(1) if m else ""


def mode(text):   # "RUN_IN_BACKGROUND: ignore" -> ignore
    m = re.search(r":\s*(\w+)", text)
    return m.group(1) if m else ""


def last_line(text):
    return text.splitlines()[-1].strip() if text else ""


def home_target(before, now):
    """The Home to go back to: A's, when it was a real home app (not Android's chooser, not ours); else the stock one."""
    home = last_line(before["home"])
    pkg = home.split("/")[0]
    if "/" in home and pkg != "android" and "ResolverActivity" not in home and not pkg.startswith("sa.urtv."):
        return home
    installed = pkgs(now["packages"]) | pkgs(before["packages"])
    return next((h for h in STOCK_HOMES if h.split("/")[0] in installed), "")


def home_cmds(home):
    pkg = home.split("/")[0]
    cmds = ["touch /data/local/tmp/home_ok",   # stop a safety switch that may still be counting
            f"pm enable {pkg}",
            f"cmd role add-role-holder --user 0 android.app.role.HOME {pkg}",
            f"cmd package set-home-activity --user 0 {home}"]
    if pkg == LISTENER.split("/")[0]:   # Google TV's home can come back without its notification access
        cmds.append(f"cmd notification allow_listener {LISTENER}")
    return cmds + ["input keyevent KEYCODE_HOME"]


def plan(before, now):
    """Shell commands that take `now` back to `before`, in three phases: (1) apps back on and Home back, (2) our apps
    removed, (3) settings. Phase 2 runs only once Home is no longer ours (restore checks), so the TV is never left
    without a home screen."""
    phases, notes = ([], [], []), []
    keep = keep_list()
    was_off, is_off = pkgs(before["disabled"]), pkgs(now["disabled"])
    for p in sorted(is_off - was_off):
        phases[0].append(f"pm enable {p}")
        notes.append(f"turn back on {p}")
    for p in sorted((was_off - is_off) & pkgs(now["packages"])):
        if p in keep:
            notes.append(f"leave on {p} (protected, though it was off before)")
            continue
        phases[0].append(f"pm disable-user --user 0 {p}")
        notes.append(f"turn off again {p} (it was off in A)")

    home = home_target(before, now)
    if home and home != last_line(now["home"]):
        phases[0].extend(home_cmds(home))
        notes.append(f"Home back to {home}")

    added = pkgs(now["packages"]) - pkgs(before["packages"])
    for p in OURS:
        if p in added:
            phases[1].append(f"pm uninstall {p}")
            notes.append(f"remove {p} (not on the TV in A)")

    for ns, k in SETTINGS:
        b, n = before.get(f"{ns}/{k}", ""), now.get(f"{ns}/{k}", "")
        if b != n and b != "":
            phases[2].append(f"settings delete {ns} {k}" if b == "null" else f"settings put {ns} {k} {b}")
            notes.append(f"{k}: {n or '?'} -> {b}")
    if bucket(before["vending_bucket"]) and bucket(before["vending_bucket"]) != bucket(now["vending_bucket"]):
        phases[2].append(f"am set-standby-bucket com.android.vending {bucket(before['vending_bucket'])}")
        notes.append("Play Store background limit undone")
    for key, op in (("vending_bg", "RUN_IN_BACKGROUND"), ("vending_any_bg", "RUN_ANY_IN_BACKGROUND")):
        b = mode(before[key])
        if b and b != mode(now[key]):
            phases[2].append(f"cmd appops set com.android.vending {op} {b}")
    b, n = before["cached_limit"], now["cached_limit"]
    if b != n and before["serial"]:   # only from a full A (an empty value in an old file is not "unset")
        phases[2].append("device_config delete activity_manager max_cached_processes" if b in ("", "null")
                         else f"device_config put activity_manager max_cached_processes {b}")
        notes.append("closed-apps limit back")
    return phases, notes


def essential_left(before, now):
    """what still differs that matters: apps on/off, Home, our apps (a setting Android resets by itself does not)"""
    phases, _ = plan(before, now)
    return [c for c in phases[0] + phases[1] if c.startswith(("pm ", "cmd role"))]


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("save", "diff", "restore", "same"):
        sys.exit(__doc__)
    what, path = sys.argv[1:]
    if what == "save":
        return save(path)
    if what == "same":
        a = load(path)["serial"]
        now = batch(["getprop ro.serialno"]).get("getprop ro.serialno", "")
        sys.exit(0 if not a or not now or a == now else 1)
    before, now = load(path), read_state()
    if before["serial"] and now["serial"] and before["serial"] != now["serial"]:
        sys.exit(f"!! {path} is another TV's (serial {before['serial']}, this one {now['serial']}): nothing changed")
    phases, notes = plan(before, now)
    if not any(phases):
        print("Nothing to change: the TV already matches A.")
        return
    print("\n".join(f"   {n}" for n in notes))
    if what == "diff":
        return
    if phases[0]:
        batch(phases[0])
    now = read_state()
    if last_line(now["home"]).split("/")[0] == "sa.urtv.home" and "pm uninstall sa.urtv.home" in phases[1]:
        sys.exit("!! Home is still our home screen: it is not removed, so the TV keeps a home. Press Home on the remote, "
                 "then run the same command again.")
    phases, _ = plan(before, now)
    for ph in phases[1:]:
        if ph:
            batch(ph)
    left = essential_left(before, read_state())
    if left:
        print("!! Not everything went back (ADB dropped?). Run the same command again. Still to do:")
        print("\n".join(f"   {c}" for c in left))
        sys.exit(1)
    print("Done: the TV matches A.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as e:
        sys.exit(f"!! {e}. Nothing more was changed; run the same command again.")
