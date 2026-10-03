# One image, two entrypoints (API and UI); see docker-compose.yml.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/opt/hf-cache

WORKDIR /app

# Set to "false" for a slim image that uses lexical hashing embeddings only.
ARG INSTALL_SENTENCE_TRANSFORMERS=true
ARG EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

COPY requirements.txt requirements-embeddings.txt ./
RUN pip install -r requirements.txt \
 && if [ "$INSTALL_SENTENCE_TRANSFORMERS" = "true" ]; then \
      pip install torch --index-url https://download.pytorch.org/whl/cpu \
      && pip install -r requirements-embeddings.txt \
      && python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}')" \
      && chmod -R a+rX /opt/hf-cache; \
    fi

RUN useradd --create-home --uid 1000 copilot
COPY --chown=copilot:copilot . .
RUN mkdir -p data/chroma data/traces data/uploads && chown -R copilot:copilot data

USER copilot
ENV APP_MODE=demo \
    EMBEDDING_PROVIDER=sentence-transformers

EXPOSE 8000 8501
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
