#!/usr/bin/env bash
# Put Thmanyah in place for a build, never in the repository (its licence allows the files only inside a built app):
# from a private fonts repo when FONTS_DIR points at its checkout (web/*.woff2, android/*.otf), else from the commit
# of this repo's history that still had them. Used by the workflows; locally: .github/tools/fonts.sh
# The files land in git-ignored places (.gitignore: assets/fonts/Thmanyah*, android/launcher/.../Thmanyah*).
set -euo pipefail
cd "$(dirname "$0")/../.."
COMMIT=a7d5682c7c9164c035d4a0be38cd69118ce2e5e3   # tshi-dev/UrTV before the fonts left the repository
WEB=(Thmanyah-Light Thmanyah-Regular Thmanyah-Medium ThmanyahDisplay-Bold)
mkdir -p assets/fonts android/launcher/src/main/assets/fonts
if [ -n "${FONTS_DIR:-}" ]; then
  cp "$FONTS_DIR"/web/*.woff2 assets/fonts/
  cp "$FONTS_DIR"/android/*.otf android/launcher/src/main/assets/fonts/
  echo "Thmanyah: from the fonts repository"; exit 0
fi
git cat-file -e "$COMMIT^{commit}" 2> /dev/null || git fetch --quiet --depth=1 origin "$COMMIT" \
  || git fetch --quiet --depth=1 https://github.com/tshi-dev/UrTV "$COMMIT" \
  || { echo "::warning::Thmanyah not found (commit $COMMIT is gone): building with the system's Arabic font"; exit 0; }
for f in "${WEB[@]}"; do
  git show "$COMMIT:assets/fonts/$f.woff2" > "assets/fonts/$f.woff2"
  git show "$COMMIT:android/launcher/src/main/assets/fonts/$f.otf" > "android/launcher/src/main/assets/fonts/$f.otf"
done
echo "Thmanyah: from commit ${COMMIT:0:7} of this repository's history"
