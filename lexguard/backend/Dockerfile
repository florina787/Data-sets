FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DEMO_MODE=true LEXGUARD_DATA_DIR=/app/synthetic_data
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ /app/backend/
COPY synthetic_data/ /app/synthetic_data/
RUN useradd -m lexguard && mkdir -p /data && chown lexguard /data
USER lexguard
ENV DATABASE_URL=sqlite:////data/lexguard.db
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=10 CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
