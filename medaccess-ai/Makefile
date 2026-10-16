PY := .venv/bin/python
.PHONY: setup backend frontend test test-pg lint typecheck e2e load dataset up down

setup:            ## create venv + install backend and frontend deps
	python3 -m venv .venv && .venv/bin/pip install -r backend/requirements-dev.txt
	cd frontend && npm ci

backend:          ## run the API on :8000 (SQLite + synthetic data)
	cd backend && ../.venv/bin/uvicorn app.main:app --reload --port 8000

frontend:         ## run the UI on :5173 (proxies /api to :8000)
	cd frontend && npm run dev

test:             ## backend tests + machine-readable report
	$(PY) -m pytest --junitxml=sdlc/qa/pytest-report.xml
	cd frontend && npm test

lint:
	.venv/bin/ruff check backend/app tests --config backend/pyproject.toml

typecheck:
	cd backend && ../.venv/bin/mypy app --config-file pyproject.toml
	cd frontend && npm run typecheck

e2e:              ## needs backend on :8000 and `npm run build && npm run preview` on :4173
	cd frontend && npx playwright test

load:             ## simple load test against a running backend
	$(PY) infrastructure/ci-cd/load_test.py --base http://localhost:8000 --concurrency 8 --requests 200

dataset:          ## export the synthetic dataset snapshot
	cd backend && ../.venv/bin/python -m app.services.synthetic

up:
	docker compose up --build

down:
	docker compose down
