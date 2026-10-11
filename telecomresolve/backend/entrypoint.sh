#!/bin/sh
set -e
python -m alembic upgrade head
if [ "${APP_MODE:-demo}" = "demo" ] && [ "${SEED_ON_START:-true}" = "true" ]; then
  python -m app.seed
fi
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
