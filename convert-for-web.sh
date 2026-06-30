#!/bin/bash
# Convert videos to browser-friendly H.264 MP4 (requires ffmpeg).
# Usage: ./convert-for-web.sh
# Creates web-{original-name}.mp4 alongside each .mov file, then run update-media.py

set -e
cd "$(dirname "$0")"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg is required. Install with: brew install ffmpeg"
  exit 1
fi

find assets/work/Videos -type f \( -iname "*.mov" -o -iname "*.mkv" \) ! -name "web-*" | while read -r src; do
  dir="$(dirname "$src")"
  base="$(basename "$src")"
  stem="${base%.*}"
  out="$dir/web-${stem}.mp4"
  if [ -f "$out" ]; then
    echo "Skip (exists): $out"
    continue
  fi
  echo "Converting: $src"
  ffmpeg -y -i "$src" \
    -c:v libx264 -preset medium -crf 23 -vf "scale='min(1920,iw)':-2" \
    -c:a aac -b:a 128k \
    -movflags +faststart \
    "$out"
done

python3 update-media.py
echo "Done. Refresh the site to use web-compatible versions."
