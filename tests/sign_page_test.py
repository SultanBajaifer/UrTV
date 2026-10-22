"""optimize/sign-page.py in a scratch tree: keygen, sign, verify, and a changed page or another key refused.

    python3 tests/sign_page_test.py          (needs: pip install cryptography)
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
t = Path(tempfile.mkdtemp())
(t / "optimize").mkdir()
(t / "dist").mkdir()
(t / "android/app").mkdir(parents=True)
shutil.copy(ROOT / "optimize/sign-page.py", t / "optimize")
(t / "dist/tv.html").write_text("<html>" + "x" * 40000 + "</html>")
failures = []


def run(cmd, key):
    r = subprocess.run([sys.executable, str(t / "optimize/sign-page.py"), cmd], capture_output=True, text=True,
                       env=dict(os.environ, URTV_PAGE_KEY=str(t / key)))
    return r.returncode, r.stdout + r.stderr


def case(name, ok):
    print(f"sign-page: {name}: " + ("ok" if ok else "WRONG"))
    if not ok:
        failures.append(name)


case("keygen", run("keygen", "k1.pem")[0] == 0 and (t / "android/app/page-key.pub").is_file())
case("the private key is only readable by its owner", (t / "k1.pem").stat().st_mode & 0o077 == 0 or os.name == "nt")
case("keygen never replaces a key", run("keygen", "k1.pem")[0] != 0)
case("sign + verify", run("sign", "k1.pem")[0] == 0 and run("verify", "k1.pem")[0] == 0)
(t / "dist/tv.html").write_text("<html>" + "y" * 40000 + "</html>")
case("a changed page fails verify", run("verify", "k1.pem")[0] != 0)
pub = (t / "android/app/page-key.pub").read_bytes()
(t / "android/app/page-key.pub").unlink()
run("keygen", "k2.pem")
(t / "android/app/page-key.pub").write_bytes(pub)   # the app still carries key 1
case("another private key refuses to sign", run("sign", "k2.pem")[0] != 0)
shutil.rmtree(t)
sys.exit(1 if failures else 0)
