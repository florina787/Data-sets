PY := .venv/bin/python
.PHONY: setup seed api ui dev test critical evals release-gate e2e load-test up down opa-export lint

setup:            ## create venv + install backend and frontend deps
	python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt -c requirements.lock
	cd frontend && npm ci
seed:             ## run migrations and load synthetic data (idempotent)
	$(PY) -m backend.db.seed
api:              ## run the API (dev, SQLite, in-process worker)
	.venv/bin/uvicorn backend.main:app --reload --port 8000
ui:               ## run the UI dev server (proxies /api to :8000)
	cd frontend && npm run dev
test:
	$(PY) -m pytest -q
critical:         ## release-blocking security + financial correctness tests
	$(PY) -m pytest -m critical -q
evals:
	$(PY) tests/evals/run_evals.py
release-gate:
	$(PY) scripts/release_gate.py
e2e:              ## Playwright journeys against a running stack (FLO_UI_URL, default http://localhost:8080)
	cd frontend && npx playwright test
load-test:        ## measured load test: make load-test USERS=50
	$(PY) tests/load/loadtest.py --users $${USERS:-50} --duration $${DURATION:-60}
up:               ## full stack: Postgres+pgvector, Redis, OPA, API, worker, UI, Prometheus, Grafana
	docker compose --profile observability up -d --build
down:
	docker compose --profile observability down
opa-export:       ## regenerate OPA data from the YAML policy bundle (+ Helm copy)
	$(PY) -m governance.opa export && cp policies/opa/data.json infrastructure/helm/flo/files/opa-data.json
lint:
	$(PY) -m ruff check backend agents harness governance privacy analytics integrations retrieval scenarios approvals observability data
