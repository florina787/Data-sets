#!/usr/bin/env bash
# Developer setup for macOS and Linux: Python backend + desktop app.
# Free tools only. Needs Python 3.11+, Node 22+, and internet for the first download.
set -euo pipefail
cd "$(dirname "$0")/.."

PY=${PYTHON:-python3}
"$PY" -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ required"'
"$PY" -m venv .venv
# CPU build of torch (about 200 MB instead of several GB of CUDA libraries).
.venv/bin/pip install --upgrade pip
.venv/bin/pip install --extra-index-url https://download.pytorch.org/whl/cpu -e ".[dev]"

(cd apps/desktop && npm ci && node scripts/make-icons.mjs)

if ! command -v ollama >/dev/null; then
  echo "Ollama is not installed. Get it free from https://ollama.com/download"
fi
if ! command -v tesseract >/dev/null; then
  echo "Optional: install Tesseract OCR for better screen text (apt install tesseract-ocr / brew install tesseract)."
fi
echo
echo "Done. Next:"
echo "  ollama pull qwen2.5:3b && ollama pull qwen2.5vl:3b   # or let the Setup wizard do it"
echo "  cd apps/desktop && npm run dev"
