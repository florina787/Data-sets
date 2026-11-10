# ArchAI — single image for both the FastAPI service and the Streamlit UI.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEMO_MODE=true

WORKDIR /app

COPY requirements.txt requirements-live.txt ./
ARG INSTALL_LIVE=false
RUN pip install --upgrade pip && \
    if [ "$INSTALL_LIVE" = "true" ]; then pip install -r requirements-live.txt; else pip install -r requirements.txt; fi

COPY app ./app
COPY frontend ./frontend
COPY config ./config
COPY scenarios ./scenarios
COPY .streamlit ./.streamlit

RUN useradd --create-home --uid 10001 archai && chown -R archai:archai /app
USER archai

EXPOSE 8000 8501

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
