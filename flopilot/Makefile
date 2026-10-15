# FloPilot developer commands. Run from the flopilot/ directory.
.PHONY: install dev-api dev-web test test-api test-web e2e lint typecheck scan demo-workbook docker-up docker-down

install:            ## install backend (incl. dev + optional LLM SDK) and frontend dependencies
	cd backend && python -m pip install -r requirements-dev.txt
	cd frontend && npm ci

dev-api:            ## FastAPI on :8000 (reads ../.env if present)
	cd backend && python -m uvicorn app.main:app --reload --port 8000

dev-web:            ## Vite dev server on :5173 (proxies /api to :8000)
	cd frontend && npm run dev

test: test-api test-web

test-api:
	cd backend && python -m pytest

test-web:
	cd frontend && npm test && npm run typecheck

e2e:                ## browser journey; needs a fresh backend data dir and `npx playwright install chromium` (or CHROMIUM_PATH)
	FLOPILOT_URL=$${FLOPILOT_URL:-http://localhost:5173} node e2e/ui_journey.mjs

lint:
	cd backend && ruff check app tests scripts --select E,F,W,B --ignore E501,B008,B905

typecheck:
	cd frontend && npm run typecheck

scan:               ## dependency + container vulnerability scans (pip-audit, npm audit, trivy if installed)
	cd backend && pip-audit -r requirements.txt -r requirements-llm.txt
	cd frontend && npm audit
	@command -v trivy >/dev/null && trivy image --severity HIGH,CRITICAL flopilot-backend flopilot-frontend || echo "trivy not installed: skipped container scan"

demo-workbook:      ## regenerate the synthetic demo workbook
	cd backend && python scripts/generate_demo_workbook.py

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down
