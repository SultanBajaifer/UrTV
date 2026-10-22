#!/usr/bin/env python3
"""Save what a setup step may change on the TV, and put it back from that file (optimize/rollback.sh).

    snapshot.py save <file>        packages (all, disabled), Home, screensaver, animation, Play Store limits, freezer
    snapshot.py diff <file>        what restore would do, without doing it
    snapshot.py restore <file>     put the TV back to <file>

Restore never disables anything in lists/keep.txt and only uninstalls apps the setup installs (ours, TV Bro,
SmartTube) that were not there in <file>; your own apps are never touched.
"""
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable
OURS = ["sa.urtv.screensaver", "sa.urtv.home", "com.phlox.tvwebbrowser", "org.smarttube.stable"]
SETTINGS = [   # namespace, key: as `settings get`
    ("global", "window_animation_scale"), ("global", "transition_animation_scale"),
    ("global", "animator_duration_scale"), ("global", "cached_apps_freezer"),
    ("secure", "screensaver_enabled"), ("secure", "screensaver_components"),
    ("secure", "screensaver_default_component"), ("system", "screen_off_timeout"),
]
HOME_QUERY = "cmd package resolve-activity --brief -c android.intent.category.HOME -a android.intent.action.MAIN"
QUERIES = {
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
    return {k: got.get(q, "") for k, q in QUERIES.items()}


def pkgs(text):
    return {m for m in re.findall(r"^package:(\S+)", text, re.M)}


def save(path):
    state = read_state()
    with open(path, "w", encoding="utf-8") as f:
        for k, v in state.items():
            f.write(f"== {k}\n{v}\n")
    print(f"Saved {path}")


def load(path):
    state, cur = {}, None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith("== "):
            cur = line[3:]
            state[cur] = []
        elif cur is not None:
            state[cur].append(line)
    return {k: "\n".join(v).strip() for k, v in state.items()}


def keep_list():
    lines = (HERE / "lists" / "keep.txt").read_text(encoding="utf-8").splitlines()
    return {l.split()[0] for l in lines if l.strip() and not l.lstrip().startswith("#")}


def bucket(text):
    m = re.search(r"\b(\d+)\b", text)
    return m.group(1) if m else ""


def mode(text):   # "RUN_IN_BACKGROUND: ignore" -> ignore
    m = re.search(r":\s*(\w+)", text)
    return m.group(1) if m else ""


def plan(before, now):
    """Shell commands that take `now` back to `before`, in a safe order: enable, Home, uninstall, settings."""
    cmds, notes = [], []
    keep = keep_list()
    was_off, is_off = pkgs(before["disabled"]), pkgs(now["disabled"])
    for p in sorted(is_off - was_off):
        cmds.append(f"pm enable {p}")
        notes.append(f"turn back on {p}")
    for p in sorted((was_off - is_off) & pkgs(now["packages"])):
        if p in keep:
            notes.append(f"leave on {p} (protected, though it was off before)")
            continue
        cmds.append(f"pm disable-user --user 0 {p}")
        notes.append(f"turn off again {p} (it was off before)")

    home_before = before["home"].splitlines()[-1].strip() if before["home"] else ""
    home_now = now["home"].splitlines()[-1].strip() if now["home"] else ""
    if "/" in home_before and home_before != home_now:
        cmds += ["touch /data/local/tmp/home_ok",   # stop a safety switch that may still be counting
                 f"pm enable {home_before.split('/')[0]}",
                 f"cmd role add-role-holder --user 0 android.app.role.HOME {home_before.split('/')[0]}",
                 f"cmd package set-home-activity --user 0 {home_before}",
                 "input keyevent KEYCODE_HOME"]
        notes.append(f"Home back to {home_before}")

    added = pkgs(now["packages"]) - pkgs(before["packages"])
    for p in OURS:
        if p in added:
            cmds.append(f"pm uninstall {p}")
            notes.append(f"remove {p} (installed by this step)")

    for ns, k in SETTINGS:
        b, n = before.get(f"{ns}/{k}", ""), now.get(f"{ns}/{k}", "")
        if b != n and b != "":
            cmds.append(f"settings delete {ns} {k}" if b == "null" else f"settings put {ns} {k} {b}")
            notes.append(f"{k}: {n or '?'} -> {b}")
    if bucket(before["vending_bucket"]) and bucket(before["vending_bucket"]) != bucket(now["vending_bucket"]):
        cmds.append(f"am set-standby-bucket com.android.vending {bucket(before['vending_bucket'])}")
        notes.append("Play Store background limit undone")
    for key, op in (("vending_bg", "RUN_IN_BACKGROUND"), ("vending_any_bg", "RUN_ANY_IN_BACKGROUND")):
        b = mode(before[key])
        if b and b != mode(now[key]):
            cmds.append(f"cmd appops set com.android.vending {op} {b}")
    b, n = before["cached_limit"], now["cached_limit"]
    if b != n:
        cmds.append("device_config delete activity_manager max_cached_processes" if b in ("", "null")
                    else f"device_config put activity_manager max_cached_processes {b}")
        notes.append("closed-apps limit back")
    return cmds, notes


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ("save", "diff", "restore"):
        sys.exit(__doc__)
    what, path = sys.argv[1:]
    if what == "save":
        return save(path)
    before = load(path)
    cmds, notes = plan(before, read_state())
    if not cmds:
        print("Nothing to undo: the TV already matches it.")
        return
    print("\n".join(f"   {n}" for n in notes))
    if what == "restore":
        batch(cmds)
        # packages and Home must match; a setting Android resets by itself is no reason to fail
        left = [c for c in plan(before, read_state())[0] if c.startswith(("pm ", "cmd role"))]
        if left:
            print("!! Not everything went back (ADB dropped?). Run the same command again.")
            sys.exit(1)
        print("Done.")


if __name__ == "__main__":
    main()
