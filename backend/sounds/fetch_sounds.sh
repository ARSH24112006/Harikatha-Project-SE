#!/usr/bin/env bash
# Re-download the git-ignored sound beds listed in manifest.json (Freesound previews).
# Usage: backend/sounds/fetch_sounds.sh [output_dir]   (default: this directory)
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
out="${1:-$here}"
mkdir -p "$out"

jq -r 'to_entries[] | select(.value | type == "object") | "\(.key)\t\(.value.preview_url)"' "$here/manifest.json" |
while IFS=$'\t' read -r file url; do
  if [[ -s "$out/$file" ]]; then
    echo "have    $file"
    continue
  fi
  echo "fetch   $file"
  curl -fsSL --max-filesize 30000000 -o "$out/$file.part" "$url"
  mv "$out/$file.part" "$out/$file"
done
