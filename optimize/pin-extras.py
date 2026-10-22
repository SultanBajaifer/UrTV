#!/usr/bin/env python3
"""Pin TV Bro and SmartTube to one release each: writes optimize/lists/extras.lock (optimize/pin-extras.sh).

Each line: package, processor type (abi, or "universal"), version, download URL, SHA-256 of the file as downloaded
now. optimize/install.sh extras installs only those exact files. Run it once, read what it prints, commit the lock;
run it again only when you decide to move to a newer version.

    TVBRO_TAG=v2.0.1 SMARTTUBE_TAG=29.25 optimize/pin-extras.sh     (default: each project's latest release)
"""
import hashlib
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

LOCK = Path(__file__).resolve().parent / "lists" / "extras.lock"
APPS = [   # package, GitHub repo, tag variable, asset pattern ({abi}: the processor type in the file name)
    ("com.phlox.tvwebbrowser", "truefedex/tv-bro", "TVBRO_TAG", r"tvbro-[0-9.]+-generic-geckoExcluded\.apk"),
    ("org.smarttube.stable", "yuliskov/SmartTube", "SMARTTUBE_TAG", r"SmartTube_stable_[0-9.]+_{abi}\.apk"),
]
ABIS = ["arm64-v8a", "armeabi-v7a", "x86", "universal"]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "UrTV pin-extras", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main():
    lines = ["# Pinned by optimize/pin-extras.sh: package  abi  version  url  sha256",
             "# optimize/install.sh extras installs only these files, after checking each SHA-256."]
    for pkg, repo, var, pattern in APPS:
        tag = os.environ.get(var)
        rel = json.loads(get(f"https://api.github.com/repos/{repo}/releases/" + (f"tags/{tag}" if tag else "latest")))
        assets = {a["name"]: a["browser_download_url"] for a in rel["assets"]}
        print(f"{repo} {rel['tag_name']} (published {rel.get('published_at', '?')})")
        found = 0
        for abi in ABIS if "{abi}" in pattern else ["universal"]:
            rx = re.compile(pattern.replace("{abi}", re.escape(abi)) + "$")
            hit = sorted(n for n in assets if rx.search(n))
            if not hit:
                continue
            data = get(assets[hit[0]])
            digest = hashlib.sha256(data).hexdigest()
            # GitHub lists its own SHA-256 for newer uploads: a second opinion on the download
            listed = next((a.get("digest") for a in rel["assets"] if a["name"] == hit[0]), None)
            if listed and listed != f"sha256:{digest}":
                sys.exit(f"!! {hit[0]}: GitHub lists {listed}, the download is sha256:{digest}. Not pinned.")
            lines.append(f"{pkg} {abi} {rel['tag_name']} {assets[hit[0]]} {digest}")
            print(f"   {abi:12} {hit[0]}  sha256 {digest}")
            found += 1
        if not found:
            sys.exit(f"!! no file in {repo} {rel['tag_name']} matches {pattern}")
    LOCK.write_text("\n".join(lines) + "\n")
    print(f"Wrote {LOCK}. Check the versions above, then commit it.")


if __name__ == "__main__":
    main()
