#!/usr/bin/env bash
# Sign the screensaver page so the TV accepts it as an update (see optimize/sign-page.py).
#   optimize/sign-page.sh keygen   once: the key pair (private key in ~/.urtv, public key in android/app/page-key.pub)
#   optimize/sign-page.sh sign     after python3 src/build.py and reviewing the change: writes dist/tv.html.sig
#   optimize/sign-page.sh verify   is the committed page signed?
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-optimize/venv/bin/python}"
"$PY" -I optimize/sign-page.py "$@"
