#!/usr/bin/env sh
# One-time setup (needs network once to fetch packages; runtime is fully offline).
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT/backend"
python3 -m venv .venv
.venv/bin/pip install -q -r requirements-dev.txt
.venv/bin/python -m app.seed.generator > /dev/null
echo "Backend ready (synthetic DB seeded)."
cd "$ROOT/frontend"
npm ci --no-audit --no-fund || npm install --no-audit --no-fund
echo "Frontend ready. Run: make demo   (or see README)"
