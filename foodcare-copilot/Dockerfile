# Flo & Jerry — Food Copilot: container image for Kubernetes (GKE, AKS, EKS or on-prem).
# Build:   docker build -t foodcare-copilot:0.1.0 .
# Lean:    docker build --build-arg WITH_TORCH=0 -t foodcare-copilot:0.1.0-lean .
#          (no PyTorch: classical inspection only; the trained classifier is reported as unavailable)
# Behind a TLS-inspecting corporate proxy, pass its CA without baking it into the image:
#          docker build --secret id=corp_ca,src=/path/to/corp-ca.pem .
# The image contains NO language model. It calls the plant's existing OpenAI-compatible
# Qwen server through FOODCARE_LLM_BASE_URL.

# ---- 1. build the two web UIs ---------------------------------------------------------
FROM node:20-bookworm-slim AS ui
WORKDIR /src
COPY package.json package-lock.json ./
COPY apps/control-room/package.json apps/control-room/
COPY apps/storefront/package.json apps/storefront/
COPY e2e/package.json e2e/
RUN --mount=type=secret,id=corp_ca,required=false \
    if [ -f /run/secrets/corp_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/corp_ca; fi; \
    npm ci --ignore-scripts
COPY apps ./apps
RUN npm run build

# ---- 2. Python runtime ----------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime
ARG WITH_TORCH=1
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/app/.venv UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    FOODCARE_BIND_HOST=0.0.0.0 FOODCARE_VAR_DIR=/var/lib/foodcare
# git: the demo keeps the storefront code in a local git repository.
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home --shell /usr/sbin/nologin foodcare
COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=secret,id=corp_ca,required=false \
    if [ -f /run/secrets/corp_ca ]; then export SSL_CERT_FILE=/run/secrets/corp_ca; fi; \
    if [ "$WITH_TORCH" = "1" ]; then uv sync --frozen --no-dev; \
    else uv sync --frozen --no-dev --no-install-package torch --no-install-package torchvision; fi
COPY backend ./backend
COPY fixtures ./fixtures
COPY --from=ui /src/apps/control-room/dist ./apps/control-room/dist
COPY --from=ui /src/apps/storefront/dist ./apps/storefront/dist
RUN mkdir -p /var/lib/foodcare && chown -R foodcare:foodcare /var/lib/foodcare
USER 10001
WORKDIR /app/backend
EXPOSE 8700
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
  CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8700/api/health', timeout=4)" || exit 1
CMD ["/app/.venv/bin/python", "-m", "app"]
