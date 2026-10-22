#!/usr/bin/env python3
"""Sign the screensaver page, so the TV accepts it as an update (optimize/sign-page.sh).

The private key stays on this computer, outside the repo (~/.urtv/page-signing.pem, or $URTV_PAGE_KEY); only the
public key is committed (android/app/page-key.pub) and built into the app. Keep a copy of the private key somewhere
safe: without it, page updates can only reach the TV by reinstalling the app.

    keygen    make the key pair (once; refuses to replace an existing key)
    sign      python3 src/build.py first; writes dist/tv.html.sig
    verify    does dist/tv.html.sig match dist/tv.html and the committed public key?
"""
import base64
import os
import sys
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = Path(os.environ.get("URTV_PAGE_KEY") or Path.home() / ".urtv" / "page-signing.pem")
PUBLIC = ROOT / "android/app/page-key.pub"
PAGE = ROOT / "dist/tv.html"
SIG = ROOT / "dist/tv.html.sig"


def keygen():
    if PRIVATE.exists():
        sys.exit(f"!! {PRIVATE} already exists: not replaced (a new key would make the TV refuse every update "
                 "until the app is rebuilt and reinstalled)")
    key = ec.generate_private_key(ec.SECP256R1())
    PRIVATE.parent.mkdir(parents=True, exist_ok=True)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption())
    fd = os.open(PRIVATE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(pem)
    PUBLIC.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM,
                                                     serialization.PublicFormat.SubjectPublicKeyInfo))
    print(f"Private key: {PRIVATE} (keep a backup; never commit it)")
    print(f"Public key:  {PUBLIC.relative_to(ROOT)} (commit it; the next APK build carries it)")


def sign():
    key = serialization.load_pem_private_key(PRIVATE.read_bytes(), password=None)
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    if not PUBLIC.is_file() or PUBLIC.read_bytes().strip() != public.strip():
        sys.exit(f"!! {PRIVATE} does not match {PUBLIC.relative_to(ROOT)}: the TV would refuse this signature")
    SIG.write_text(base64.b64encode(key.sign(PAGE.read_bytes(), ec.ECDSA(hashes.SHA256()))).decode() + "\n")
    print(f"Signed {PAGE.relative_to(ROOT)} -> {SIG.relative_to(ROOT)}: commit both")


def verify():
    if not PUBLIC.is_file():
        sys.exit(f"!! no {PUBLIC.relative_to(ROOT)}: run optimize/sign-page.sh keygen")
    if not SIG.is_file():
        sys.exit(f"!! no {SIG.relative_to(ROOT)}: run optimize/sign-page.sh sign")
    key = serialization.load_pem_public_key(PUBLIC.read_bytes())
    try:
        key.verify(base64.b64decode(SIG.read_text().strip()), PAGE.read_bytes(), ec.ECDSA(hashes.SHA256()))
    except InvalidSignature:
        sys.exit(f"!! {SIG.relative_to(ROOT)} does not match {PAGE.relative_to(ROOT)}: the TV will keep its "
                 "current page. Run optimize/sign-page.sh sign after reviewing the change")
    print("dist/tv.html is signed with the key in android/app/page-key.pub")


if __name__ == "__main__":
    cmds = {"keygen": keygen, "sign": sign, "verify": verify}
    if len(sys.argv) != 2 or sys.argv[1] not in cmds:
        sys.exit("usage: optimize/sign-page.sh keygen|sign|verify")
    cmds[sys.argv[1]]()
