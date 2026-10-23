.PHONY: install install-local-llm prepare llm-download label synthetic index dev backend frontend test test-backend test-frontend e2e evaluate screenshots report docker-up package clean

install:            ## Install backend (uv) and frontend (npm) dependencies
	cd backend && uv sync --extra transformers
	cd frontend && npm ci

install-local-llm:  ## Optional: also install llama.cpp bindings for the free local LLM (then `make llm-download`)
	cd backend && uv sync --extra transformers --extra local-llm

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

report:             ## Generate the submission DOCX, the engineering PDF and the personalised submission PDF
	cd backend && uv run python -m scripts.generate_report
	cd backend && uv run python -m scripts.generate_submission_pdf

docker-up:
	docker compose up --build

clean:
	rm -rf data/processed/* data/indexes/*

llm-download:       ## Download the free local LLM (Qwen2.5-1.5B-Instruct GGUF, ~1.1 GB) into data/models/
	cd backend && uv run python -c "from app.config import get_settings; from app.llm.local_client import download_model; print(download_model(get_settings()))"

package:            ## Build the submission ZIP from the committed tree (dist/conversation-intelligence-copilot.zip)
	mkdir -p dist
	git -C "$$(git rev-parse --show-toplevel)" archive --format=zip --prefix=conversation-intelligence-copilot/ -o "$(CURDIR)/dist/conversation-intelligence-copilot.zip" HEAD:conversation-intelligence-copilot
	@ls -lh dist/conversation-intelligence-copilot.zip
