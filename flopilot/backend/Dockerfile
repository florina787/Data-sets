# FloPilot API
# syntax=docker/dockerfile:1
FROM python:3.13-slim

# LibreOffice is optional (~600 MB). It is used only to VERIFY formula results, never to write files.
ARG INSTALL_LIBREOFFICE=false
ARG INSTALL_LLM=true
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 FLOPILOT_DATA_DIR=/data

# Optional build secret "extra_ca": a CA bundle for TLS-inspecting corporate proxies (unused when absent).
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -s /run/secrets/extra_ca ]; then cp /run/secrets/extra_ca /usr/local/share/ca-certificates/extra_ca.crt && update-ca-certificates >/dev/null 2>&1 || true; fi; \
    if [ "$INSTALL_LIBREOFFICE" = "true" ]; then \
      apt-get update && apt-get install -y --no-install-recommends libreoffice-calc-nogui && rm -rf /var/lib/apt/lists/*; \
    fi \
 && rm -f /usr/local/share/ca-certificates/extra_ca.crt && update-ca-certificates --fresh >/dev/null 2>&1 || true
RUN useradd --create-home --uid 10001 flopilot && mkdir -p /data && chown flopilot:flopilot /data

WORKDIR /app
COPY requirements.txt requirements-llm.txt ./
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -s /run/secrets/extra_ca ]; then export PIP_CERT=/run/secrets/extra_ca; fi; \
    pip install -r requirements.txt && if [ "$INSTALL_LLM" = "true" ]; then pip install -r requirements-llm.txt; fi
COPY app ./app
COPY sample_data ./sample_data

USER flopilot
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
# One worker: version publication uses an in-process lock (see docs/DEPLOYMENT.md before scaling out).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]
