#!/usr/bin/env bash
# Pin TV Bro and SmartTube to exact files and SHA-256s in optimize/lists/extras.lock (see optimize/pin-extras.py).
#   optimize/pin-extras.sh                                   each project's latest release, pinned
#   TVBRO_TAG=<tag> SMARTTUBE_TAG=<tag> optimize/pin-extras.sh   a release you chose
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-optimize/venv/bin/python}"
"$PY" -I optimize/pin-extras.py
