#!/bin/bash
cd "$(dirname "$0")"
PORT=8080
python3 update-media.py --watch &
WATCH_PID=$!
trap 'kill "$WATCH_PID" 2>/dev/null' EXIT
echo "Starting The Studio at http://localhost:$PORT"
echo "Drop photos/videos into assets/work/Photos or assets/work/Videos — albums update automatically."
echo "Press Ctrl+C to stop."
if command -v open >/dev/null 2>&1; then
  (sleep 1 && open "http://localhost:$PORT") &
fi
python3 -m http.server "$PORT"
