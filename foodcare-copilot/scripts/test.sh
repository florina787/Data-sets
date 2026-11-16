#!/usr/bin/env bash
# Fast verification: lint, fixture-patch sync, backend tests, UI typecheck and build.
# Browser end-to-end: npm run e2e (starts its own isolated server on other ports).
set -euo pipefail
. "$(dirname "$0")/_venv.sh"
cd "$(dirname "$0")/.."
"$VENV_BIN/ruff" check backend scripts
"$PY" scripts/regen_fixture_patches.py --check
"$PY" -m pytest
npm run typecheck
npm run build
