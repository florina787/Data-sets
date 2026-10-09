#!/usr/bin/env bash
# Deterministic reset: wipes var/, reseeds data and accounts, recreates the storefront
# repository and redeploys the v1.0 baseline. Uses the running server if there is one.
set -euo pipefail
cd "$(dirname "$0")/../backend"
exec ../.venv/bin/python -m app.cli reset
