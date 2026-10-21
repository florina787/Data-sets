FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv
RUN pip install --no-cache-dir uv==0.11.32
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
ARG INSTALL_EMBEDDINGS=false
RUN if [ "$INSTALL_EMBEDDINGS" = "true" ]; then uv sync --frozen --no-dev --extra embeddings; else uv sync --frozen --no-dev; fi
COPY backend/app ./app
COPY data/demo /app/data/demo
ENV PATH="/opt/venv/bin:$PATH" DATA_DIR=/app/backend/var IMPORT_ROOT=/app/data/imports DEMO_DATA_DIR=/app/data/demo
RUN useradd --create-home --uid 10001 convolens && mkdir -p /app/backend/var /app/data/imports && chown -R convolens /app/backend/var /app/data/imports
USER convolens
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
