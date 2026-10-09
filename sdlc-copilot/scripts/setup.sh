#!/usr/bin/env bash
# Install pinned dependencies and build both UIs. Safe to re-run.
set -euo pipefail
cd "$(dirname "$0")/.."
command -v uv >/dev/null || { echo "uv is required: https://docs.astral.sh/uv/"; exit 1; }
command -v npm >/dev/null || { echo "Node.js 20+ and npm are required"; exit 1; }
uv sync --frozen
npm ci --no-audit --no-fund
npm run build
echo "Setup complete. Start with: scripts/start.sh"
