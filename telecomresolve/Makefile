PY ?= python3
.PHONY: setup seed reset dev-backend dev-frontend test test-backend test-frontend e2e eval openapi up

setup:            ## install backend + frontend dependencies
	cd backend && $(PY) -m pip install -r requirements-dev.txt
	cd frontend && npm ci

seed:             ## create schema and seed synthetic data (demo mode only)
	cd backend && $(PY) -m alembic upgrade head && $(PY) -m app.seed

reset:            ## restore the known demo state (demo mode only)
	cd backend && $(PY) -m app.seed --reset

dev-backend:
	cd backend && $(PY) -m uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

test: test-backend test-frontend

test-backend:
	cd backend && $(PY) -m pytest -q

test-frontend:
	cd frontend && npm run typecheck && npm test && npm run build

e2e:              ## browser journey against a fresh demo backend
	cd frontend && PYTHON=$(PY) npx playwright test

eval:             ## labelled evaluation on an isolated database
	cd backend && $(PY) -m app.evaluation.run

openapi:
	cd backend && $(PY) -c "import json;from app.main import create_app;print(json.dumps(create_app(run_recovery=False).openapi(),indent=2))" > ../docs/openapi.json

up:
	docker compose up --build
