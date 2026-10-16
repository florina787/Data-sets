# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv/backend
COPY backend/requirements.txt .
# Optional corporate/proxy CA: docker build --secret id=extra_ca,src=/path/ca.crt (never baked into the image)
RUN --mount=type=secret,id=extra_ca,required=false \
    sh -c 'if [ -s /run/secrets/extra_ca ]; then export PIP_CERT=/run/secrets/extra_ca; fi; pip install -r requirements.txt'
COPY backend/ /srv/backend/
COPY data/knowledge /srv/data/knowledge
RUN useradd --create-home --uid 10001 medaccess && mkdir -p /srv/data/runtime && chown -R medaccess /srv/data
USER medaccess
ENV CHECKPOINT_DB_PATH=/srv/data/runtime/checkpoints.sqlite
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=5 CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health').status==200 else 1)"
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
