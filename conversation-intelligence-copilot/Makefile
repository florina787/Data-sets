.PHONY: install prepare label synthetic index dev backend frontend test test-backend test-frontend e2e evaluate screenshots report docker-up clean

install:            ## Install backend (uv) and frontend (npm) dependencies
	cd backend && uv sync
	cd frontend && npm ci

prepare:            ## Ingest, validate, label and build data/processed/analytics.duckdb
	cd backend && uv run python -m scripts.prepare_dataset

label:              ## Optional: label unique messages with Gemini (resumable), then rebuild with LABEL_SOURCE=gemini
	cd backend && uv run python -m scripts.label_dataset

synthetic:          ## Optional: generate the tagged synthetic demo set (then `make prepare index`)
	cd backend && uv run python -m scripts.generate_synthetic

index:              ## Build the FAISS retrieval index
	cd backend && uv run python -m scripts.build_embeddings

backend:            ## Run the API on :8000
	cd backend && uv run uvicorn app.main:app --reload --port 8000

frontend:           ## Run the UI on :5173 (proxies /api to :8000)
	cd frontend && npx vite

dev:                ## Run API and UI together
	$(MAKE) -j2 backend frontend

test: test-backend test-frontend

test-backend:
	cd backend && uv run pytest

test-frontend:
	cd frontend && npx tsc -b --noEmit && npx vitest run

e2e:                ## Playwright end-to-end tests (starts servers if needed)
	cd frontend && npx playwright test

evaluate:           ## Evaluation on the real dataset -> data/manifests/evaluation_results.json, docs/evaluation/
	cd backend && uv run python -m scripts.evaluate

screenshots:        ## Capture docs/screenshots from a running app
	cd frontend && node e2e/capture-screenshots.mjs ../docs/screenshots

report:             ## Generate the submission DOCX and the detailed engineering PDF
	cd backend && uv run python -m scripts.generate_report

docker-up:
	docker compose up --build

clean:
	rm -rf data/processed/* data/indexes/*
