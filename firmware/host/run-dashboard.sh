#!/usr/bin/env bash
# Launch the bench dashboard as a standalone app window.
#
# Chrome/Edge --app= gives a real window with no tabs, no URL bar and its own
# Dock entry. Falls back to the default browser when neither is installed.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-8420}"
PY="$HOME/.platformio/penv/bin/python"
URL="http://127.0.0.1:${PORT}"

[[ -x "$PY" ]] || PY=python3

pkill -f "bridge.py" 2>/dev/null || true
sleep 0.5

# --source fake runs with no hardware attached and is labelled DEMO in the UI.
"$PY" "$HERE/bridge.py" --http-port "$PORT" "$@" &
BRIDGE=$!
trap 'kill $BRIDGE 2>/dev/null || true' EXIT

for _ in $(seq 1 40); do
  curl -sf -o /dev/null "$URL" && break
  sleep 0.25
done

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
EDGE="/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"

if [[ -x "$CHROME" ]]; then
  "$CHROME" --app="$URL" --window-size=1280,980 \
            --user-data-dir="${TMPDIR:-/tmp}/bench-dashboard-profile" >/dev/null 2>&1 &
elif [[ -x "$EDGE" ]]; then
  "$EDGE" --app="$URL" --window-size=1280,980 \
          --user-data-dir="${TMPDIR:-/tmp}/bench-dashboard-profile" >/dev/null 2>&1 &
else
  echo "Chrome/Edge not found - opening in the default browser instead."
  open "$URL"
fi

echo "Dashboard running at $URL   (Ctrl-C to stop)"
wait $BRIDGE
