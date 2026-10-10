#!/bin/bash
# Double-click this file.  Nothing to install, nothing to configure by hand.
#
# It starts the sibling's helper -- the only thing that talks to the local model, and the
# only thing that writes the archive -- and opens it in your browser.  The first time, the
# page asks which local model should speak and what the sibling is called; after that it
# just opens the session.
#
# Closing this window stops the sibling.  Nothing in the archive depends on it running.

cd "$(dirname "$0")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
  echo
  echo "This computer has no Python 3, and the sibling is made of it."
  echo "Open Terminal once (Spotlight: 'Terminal') and run:   xcode-select --install"
  echo "Then double-click this file again."
  echo
  read -r -p "Press return to close. " _
  exit 1
fi

# the port is remembered in settings.json, if there are settings yet
PORT=$(python3 - <<'PY' 2>/dev/null || echo 8799
import json, pathlib
p = pathlib.Path("settings.json")
print(json.loads(p.read_text()).get("port", 8799) if p.exists() else 8799)
PY
)

echo "starting the sibling on port ${PORT}..."
python3 sib.py &
HELPER=$!
trap 'kill $HELPER 2>/dev/null' EXIT INT TERM

# wait until it answers, then open the page.  A real check, not a fixed sleep.
for _ in $(seq 1 60); do
  if curl -s -m 1 -o /dev/null "http://127.0.0.1:${PORT}/health" 2>/dev/null; then
    open "http://127.0.0.1:${PORT}/"
    cat <<'NOTE'

The sibling is running, and the page is open in your browser.
This window is its log: what it is doing, and nothing about what is being said.
Closing this window stops it.  The archive keeps everything either way.

NOTE
    wait $HELPER
    exit 0
  fi
  if ! kill -0 $HELPER 2>/dev/null; then
    echo
    echo "The helper stopped before it could answer -- the messages above say why."
    echo
    read -r -p "Press return to close. " _
    exit 1
  fi
  sleep 0.5
done

echo "It did not answer within thirty seconds.  The messages above may say why."
read -r -p "Press return to close. " _
