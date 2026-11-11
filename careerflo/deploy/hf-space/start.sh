#!/usr/bin/env bash
# Supervises the two processes of the Career_flo container. If either exits, the container exits so the
# platform restarts it (no half-alive state). Works locally too: override APP_DIR / LLAMA_BIN / paths.
set -euo pipefail

APP_DIR="${APP_DIR:-/home/user/app}"
PORT="${PORT:-7860}"
LLAMA_PORT="${LLAMA_PORT:-8081}"
PIDS=()

shutdown() { kill -TERM "${PIDS[@]}" 2>/dev/null || true; wait || true; }
trap shutdown TERM INT

if [[ "${LLM_PROVIDER:-llamacpp}" == "llamacpp" && -n "${LLAMA_MODEL_PATH:-}" ]]; then
  THREADS="${LLAMA_THREADS:-${CPU_CORES:-2}}"
  echo "[start] llama-server: model=${LLAMA_MODEL_PATH} threads=${THREADS} parallel=${LLAMA_PARALLEL:-2} ctx=${LLAMA_CTX:-8192}"
  "${LLAMA_BIN:-/app/llama-server}" -m "${LLAMA_MODEL_PATH}" --host 127.0.0.1 --port "${LLAMA_PORT}" \
      -t "${THREADS}" -c "${LLAMA_CTX:-8192}" --parallel "${LLAMA_PARALLEL:-2}" --jinja --alias "${LLM_MODEL:-qwen3}" \
      >"${LLAMA_LOG:-/dev/stdout}" 2>&1 &
  PIDS+=("$!")
  # The API starts immediately and reports "degraded" readiness until the model is loaded; deterministic
  # features work meanwhile. We only wait briefly so the first chat after boot usually has a model.
  for _ in $(seq 1 "${LLAMA_WAIT_SECONDS:-90}"); do
    curl -fsS "http://127.0.0.1:${LLAMA_PORT}/health" >/dev/null 2>&1 && { echo "[start] model ready"; break; }
    kill -0 "${PIDS[0]}" 2>/dev/null || { echo "[start] llama-server exited during load"; exit 1; }
    sleep 1
  done
fi

cd "${APP_DIR}/backend"
if [[ "${DATABASE_URL:-}" == postgres* ]]; then
  echo "[start] applying database migrations"
  .venv/bin/alembic upgrade head
fi

echo "[start] api on :${PORT}"
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --workers 1 \
    --proxy-headers --forwarded-allow-ips='*' --timeout-graceful-shutdown 20 &
PIDS+=("$!")

set +e
wait -n "${PIDS[@]}"
CODE=$?
echo "[start] a process exited (code ${CODE}); stopping the container so the platform restarts it"
shutdown
exit "${CODE}"
