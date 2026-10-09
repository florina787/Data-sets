#!/usr/bin/env bash
# One command to run the whole demo:
#   control room + API + inventory simulator  -> http://127.0.0.1:8700
#   deployed FreshSip storefront (managed)    -> http://127.0.0.1:8801
set -euo pipefail
cd "$(dirname "$0")/.."
if ! git --version >/dev/null 2>&1; then
  echo "git is required: the demo keeps the storefront code in a local git repository."
  echo "On macOS run: xcode-select --install   (then rerun scripts/start.sh)"
  exit 1
fi
if [ ! -d .venv ] || [ ! -d apps/control-room/dist ] || [ ! -d apps/storefront/dist ]; then
  scripts/setup.sh
fi
if [ -f .env ]; then set -a; . ./.env; set +a; fi
cd backend
exec ../.venv/bin/python -m app
