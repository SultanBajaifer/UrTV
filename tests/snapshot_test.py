"""optimize/snapshot.py's undo plan on made-up TV states: no TV needed.

    python3 tests/snapshot_test.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "optimize"))
import snapshot  # noqa: E402

STOCK = "com.google.android.apps.tv.launcherx/com.google.android.apps.tv.launcherx.home.HomeActivity"


def state(packages, disabled=(), home=STOCK, **settings):
    s = {k: "" for k in snapshot.QUERIES}
    s.update(packages="\n".join(f"package:{p}" for p in packages), disabled="\n".join(f"package:{p}" for p in disabled),
             home=home, vending_bucket="10", vending_bg="RUN_IN_BACKGROUND: allow",
             vending_any_bg="RUN_ANY_IN_BACKGROUND: allow", cached_limit="null")
    s.update({f"global/{k}": "1.0" for k in ("window_animation_scale", "transition_animation_scale", "animator_duration_scale")})
    s.update(settings)
    return s


BASE = ["com.tcl.bi", "com.google.android.apps.mediashell", "com.netflix.ninja", "com.google.android.apps.tv.launcherx",
        "com.tcl.hearaid"]
failures = []


def case(name, before, now, want, never=()):
    cmds, _ = snapshot.plan(before, now)
    ok = all(w in cmds for w in want) and not any(n in c for c in cmds for n in never)
    print(f"snapshot: {name}: " + ("ok" if ok else f"WRONG {cmds}"))
    if not ok:
        failures.append(name)


case("debloat step: turn back on what it turned off", state(BASE), state(BASE, disabled=["com.tcl.bi"]),
     ["pm enable com.tcl.bi"])
case("launcher step: stock Home back before our app goes, own apps untouched",
     state(BASE), state(BASE + ["sa.urtv.home"], disabled=["com.google.android.apps.tv.launcherx"],
                        home="sa.urtv.home/.MainActivity"),
     ["pm enable com.google.android.apps.tv.launcherx", f"cmd package set-home-activity --user 0 {STOCK}",
      "pm uninstall sa.urtv.home"], never=["netflix"])
cmds, _ = snapshot.plan(state(BASE), state(BASE + ["sa.urtv.home"], disabled=["com.google.android.apps.tv.launcherx"],
                                           home="sa.urtv.home/.MainActivity"))
order_ok = cmds.index("input keyevent KEYCODE_HOME") < cmds.index("pm uninstall sa.urtv.home")
print("snapshot: Home is switched before the home app is removed: " + ("ok" if order_ok else f"WRONG {cmds}"))
if not order_ok:
    failures.append("order")
case("tweaks step: animation and Play Store limits back",
     state(BASE), state(BASE, vending_bucket="45", vending_bg="RUN_IN_BACKGROUND: ignore",
                        **{"global/window_animation_scale": "0.5"}),
     ["settings put global window_animation_scale 1.0", "am set-standby-bucket com.android.vending 10",
      "cmd appops set com.android.vending RUN_IN_BACKGROUND allow"])
case("an app installed by the owner meanwhile is never removed", state(BASE), state(BASE + ["com.example.mine"]),
     [], never=["uninstall"])
case("a protected app that was off before is not turned off again",
     state(BASE, disabled=["com.google.android.apps.mediashell"]), state(BASE), [], never=["disable-user"])
case("a setting that was unset before is deleted, not set to 'null'",
     state(BASE, **{"secure/screensaver_components": "null"}),
     state(BASE, **{"secure/screensaver_components": "sa.urtv.screensaver/.ScreenDream"}),
     ["settings delete secure screensaver_components"])
sys.exit(1 if failures else 0)
