#!/usr/bin/env sh
# One-time setup (needs network once to fetch Python/npm packages; runtime is fully offline).
# Your existing local Qwen model is REUSED: nothing here downloads a model.
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT/backend"
python3 -m venv .venv
.venv/bin/pip install -q -r requirements-dev.txt

# llama.cpp runtime for an existing Qwen .gguf file (skipped if Ollama already serves a Qwen model).
if curl -sf http://127.0.0.1:11434/api/tags 2>/dev/null | grep -qi qwen; then
  echo "Ollama with a Qwen model detected: using it (no extra runtime needed)."
else
  INDEX=https://abetlen.github.io/llama-cpp-python/whl/cpu
  [ "$(uname -s)" = "Darwin" ] && INDEX=https://abetlen.github.io/llama-cpp-python/whl/metal
  .venv/bin/pip install -q -r requirements-llm.txt --extra-index-url "$INDEX" || \
    echo "WARNING: llama-cpp-python did not install; serve Qwen with Ollama or set FF_QWEN_BASE_URL to a local llama.cpp server."
fi
.venv/bin/python -m app.seed.generator > /dev/null
echo "Backend ready (synthetic DB seeded)."
.venv/bin/python ../scripts/check_qwen.py || echo "See the reason above; set FF_QWEN_MODEL_PATH to your .gguf file if it lives elsewhere."
cd "$ROOT/frontend"
npm ci --no-audit --no-fund || npm install --no-audit --no-fund
echo "Frontend ready. Run: make demo   (or see README)"
