# syntax=docker/dockerfile:1.7
# Career_flo AI — single-container Hugging Face Docker Space:
#   FastAPI (API + built React app on one origin, port 7860) + llama.cpp server running Qwen3 (GGUF, CPU) on 127.0.0.1:8081.
# Build context: the staging folder produced by `python scripts/hf_deploy.py --stage-only` (backend/, frontend/, start.sh).
# Persistent data lives in Supabase (DATABASE_URL); the container disk is ephemeral.

########## 1. Frontend build ##########
FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# Public, non-secret values (Space *Variables* are passed as build args).
ARG VITE_SUPABASE_URL=""
ARG VITE_SUPABASE_ANON_KEY=""
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY
RUN npm run build

########## 2. Runtime: official llama.cpp server image (Ubuntu 24.04, Python 3.12 from apt) ##########
FROM ghcr.io/ggml-org/llama.cpp:server-b12199@sha256:ca40726778c25a7fadce42c09bada8484eab22e28bc283bdbf212e87b1555390
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    # Spaces run as uid 1000; Ubuntu 24.04 ships a default "ubuntu" user with that uid.
    && (userdel -r ubuntu 2>/dev/null || true) && useradd -m -u 1000 user
COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv

USER user
ENV HOME=/home/user
WORKDIR /home/user/app

COPY --chown=user backend/pyproject.toml backend/uv.lock backend/
RUN cd backend && uv sync --frozen --no-dev --no-install-project --python /usr/bin/python3
COPY --chown=user backend/ backend/
COPY --chown=user --from=web /web/dist frontend-dist/

# Qwen3 GGUF weights, pinned by revision and verified by SHA-256 (Apache-2.0). Override via Space Variables (build args).
ARG MODEL_REPO=unsloth/Qwen3-1.7B-GGUF
ARG MODEL_REVISION=d7f544eead698dbd1f15126ef60b45a1e1933222
ARG MODEL_FILE=Qwen3-1.7B-Q4_K_M.gguf
ARG MODEL_SHA256=b139949c5bd74937ad8ed8c8cf3d9ffb1e99c866c823204dc42c0d91fa181897
ARG MODEL_ALIAS=qwen3-1.7b
RUN mkdir -p models && curl -fL --retry 5 --retry-delay 3 -o models/model.gguf \
      "https://huggingface.co/${MODEL_REPO}/resolve/${MODEL_REVISION}/${MODEL_FILE}" \
    && echo "${MODEL_SHA256}  models/model.gguf" | sha256sum -c -

COPY --chown=user start.sh deploy-manifest.json ./
ENV APP_DIR=/home/user/app \
    FRONTEND_DIST=/home/user/app/frontend-dist \
    LLAMA_BIN=/app/llama-server \
    LLAMA_MODEL_PATH=/home/user/app/models/model.gguf \
    LLM_PROVIDER=llamacpp LLM_BASE_URL=http://127.0.0.1:8081 LLM_MODEL=${MODEL_ALIAS} \
    LLM_MAX_CONCURRENCY=2 LLAMA_PARALLEL=2 LLAMA_CTX=8192 \
    PORT=7860 ENVIRONMENT=production
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s CMD curl -fsS http://127.0.0.1:7860/api/health || exit 1
ENTRYPOINT ["/home/user/app/start.sh"]
