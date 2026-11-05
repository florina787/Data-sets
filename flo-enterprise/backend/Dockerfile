FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt requirements.lock ./
# Optional corporate/proxy CA (BuildKit secret "extra_ca", empty by default). TLS verification is never disabled.
RUN --mount=type=secret,id=extra_ca,required=false \
    if [ -s /run/secrets/extra_ca ]; then cat /etc/ssl/certs/ca-certificates.crt /run/secrets/extra_ca > /tmp/ca.pem; export PIP_CERT=/tmp/ca.pem; fi; \
    pip install -r requirements.txt -c requirements.lock && rm -f /tmp/ca.pem
COPY alembic.ini pyproject.toml ./
COPY backend backend
COPY agents agents
COPY analytics analytics
COPY approvals approvals
COPY conversation conversation
COPY data data
COPY governance governance
COPY harness harness
COPY integrations integrations
COPY observability observability
COPY policies policies
COPY privacy privacy
COPY retrieval retrieval
COPY scenarios scenarios
RUN useradd --uid 10001 --create-home flo && mkdir -p /app/var && chown -R flo /app/var
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=5 CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz').status==200 else 1)"
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers"]
