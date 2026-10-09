#!/usr/bin/env bash
# Fast verification: lint, fixture-patch sync, backend tests, UI typecheck and build.
# Browser end-to-end: npm run e2e (starts its own isolated server on other ports).
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/ruff check backend scripts
.venv/bin/python scripts/regen_fixture_patches.py --check
.venv/bin/python -m pytest
npm run typecheck
npm run build
