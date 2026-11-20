ARG PYTHON_IMAGE=python:3.13-slim
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir uv==0.11.32 && apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/app ./app
COPY backend/scripts ./scripts
COPY backend/docker-entrypoint.sh ./
# The raw dataset is baked in; processed data and indexes live on a volume (/app/data).
COPY data/raw /app/data/raw
COPY data/manifests /app/data/manifests

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=120s CMD curl -fs http://127.0.0.1:8000/health || exit 1
ENTRYPOINT ["sh", "./docker-entrypoint.sh"]
