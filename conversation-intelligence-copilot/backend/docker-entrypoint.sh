#!/bin/sh
# Prepare the dataset and retrieval index on first start (idempotent), then serve the API.
set -e
if [ ! -f /app/data/processed/analytics.duckdb ]; then
  echo "Preparing dataset…"; python -m scripts.prepare_dataset
fi
if [ ! -f /app/data/indexes/conversations.faiss ]; then
  echo "Building retrieval index…"; python -m scripts.build_embeddings
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
