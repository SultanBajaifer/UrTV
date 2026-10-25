#!/usr/bin/env python3
"""«تسريع» (Boost): which apps the home screen's pill may stop (BoostText.java, on tests/boost_cases.tsv), that it never
stops what optimize/lists/keep.txt protects, its wiring (pill, permission, a thread), and optimize/boost.sh with a stub
TV. Needs javac for the Java cases; without it they are skipped with a note.   Run: python3 tests/boost_test.py"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / "android/launcher/src/main/java/sa/urtv/home"
failed = 0


def check(name, ok, detail=""):
    global failed
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  -> {detail}"))
    failed += not ok


boost = (HOME / "Boost.java").read_text(encoding="utf-8")
main = (HOME / "MainActivity.java").read_text(encoding="utf-8")
manifest = (ROOT / "android/launcher/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
check("manifest: KILL_BACKGROUND_PROCESSES (a normal permission, no prompt)", "android.permission.KILL_BACKGROUND_PROCESSES" in manifest)
check("the pill runs Boost", 'pill("تسريع", R.drawable.ic_boost)' in main and "Boost.run(this)" in main)
check("Boost works off the main thread and posts its toast back to it", "new Thread(" in boost and "Looper.getMainLooper()" in boost)
check("Boost only stops background processes: no force-stop, no data cleared, nothing disabled",
      "killBackgroundProcesses" in boost and not re.search(r"forceStop|clearApplicationUserData|setApplicationEnabledSetting|pm clear", boost))
check("Boost asks BoostText for every app", "BoostText.mayStop(" in boost)
check("the icon exists", (ROOT / "android/launcher/src/main/res/drawable/ic_boost.xml").is_file())

# optimize/boost.sh with a stub tv.py: memory read before and after, am kill-all in between
t = Path(tempfile.mkdtemp())
(t / "optimize").mkdir()
shutil.copy(ROOT / "optimize/boost.sh", t / "optimize")
stub = t / "py"
stub.write_text('#!/usr/bin/env bash\nshift 2\necho "$*" >> "$T/log"\ncase "$1" in\n'
                '  *MemAvailable*) n=$(cat "$T/n" 2>/dev/null || echo 0); echo $((n+1)) > "$T/n";'
                ' [ "$n" = 0 ] && echo "MemAvailable:  512000 kB" || echo "MemAvailable:  716800 kB" ;;\nesac\n')
stub.chmod(0o755)
fake = t / "bin"
fake.mkdir()
(fake / "sleep").write_text("#!/bin/sh\nexit 0\n")
(fake / "sleep").chmod(0o755)
r = subprocess.run(["bash", str(t / "optimize/boost.sh")], capture_output=True, text=True,
                   env=dict(os.environ, PY=str(stub), T=str(t), PATH=f"{fake}:{os.environ['PATH']}"))
log = (t / "log").read_text().splitlines()
check("boost.sh: before, am kill-all, after", r.returncode == 0 and log == ["grep MemAvailable /proc/meminfo", "am kill-all",
      "grep MemAvailable /proc/meminfo"], (r.returncode, log, r.stderr))
check("boost.sh: says what it freed", "500 MB -> 700 MB (freed 200 MB)" in r.stdout, r.stdout)
code = "\n".join(l for l in (ROOT / "optimize/boost.sh").read_text().splitlines() if not l.lstrip().startswith("#"))
check("boost.sh: never force-stops, clears or disables", not re.search(r"force-stop|pm clear|disable", code))
shutil.rmtree(t)

if not shutil.which("javac"):
    print("SKIP boost text: no javac here")
    sys.exit(1 if failed else 0)
cases = [l.split("\t") for l in (ROOT / "tests/boost_cases.tsv").read_text(encoding="utf-8").split("\n") if l and not l.startswith("#")]
with tempfile.TemporaryDirectory() as tmp:
    subprocess.run(["javac", "-encoding", "UTF-8", "-d", tmp, str(HOME / "BoostText.java"), str(ROOT / "tests/BoostRun.java")],
                   check=True, capture_output=True)
    out = subprocess.run(["java", "-Dfile.encoding=UTF-8", "-cp", tmp, "sa.urtv.home.BoostRun", str(ROOT / "tests/boost_cases.tsv")],
                         check=True, capture_output=True).stdout
got = out.decode("utf-8").split("\n")
keep_txt = {l.split()[0] for l in (ROOT / "optimize/lists/keep.txt").read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.lstrip().startswith("#")}
for c, g in zip(cases, got):
    if c[0] == "keep":
        kept = set(g.split())
        check("every package in optimize/lists/keep.txt is kept by «تسريع» too", keep_txt <= kept, sorted(keep_txt - kept))
        check("«تسريع» keeps this app and the screensaver", {"sa.urtv.home", "sa.urtv.screensaver"} <= kept)
    else:
        check(f"boost {c[0]}: {c[5]}", g == c[4], f"{g!r}, wanted {c[4]!r}")
check("every case answered", len(got) > len(cases), (len(got), len(cases)))
sys.exit(1 if failed else 0)
