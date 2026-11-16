#!/usr/bin/env bash
# Deterministic reset: wipes var/, reseeds data and accounts, recreates the storefront
# repository and redeploys the v1.0 baseline. Uses the running server if there is one.
set -euo pipefail
. "$(dirname "$0")/_venv.sh"
cd "$(dirname "$0")/../backend"
exec "$PY" -m app.cli reset
