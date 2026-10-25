# Flying_Florina convenience targets (macOS/Linux). Windows: see README (PowerShell commands).
PY := backend/.venv/bin/python
.PHONY: setup seed backend frontend demo test test-backend test-frontend test-e2e offline smoke lint perf bundle clean

setup:
	sh scripts/setup.sh

seed:
	$(PY) scripts/seed.py

backend:
	cd backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000

frontend:
	cd frontend && npm run dev

demo:
	@echo "Starting backend on :8000 and UI on :5173 (Ctrl+C stops both)"
	@trap 'kill 0' INT TERM; (cd backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000) & (cd frontend && npm run dev) & wait

test: lint test-backend test-frontend offline

test-backend:
	cd backend && .venv/bin/python -m pytest

test-frontend:
	cd frontend && npm run typecheck && npm test

test-e2e:
	cd frontend && npm run test:e2e

offline:
	$(PY) scripts/offline_check.py

smoke:
	$(PY) scripts/smoke_test.py

lint:
	cd backend && .venv/bin/ruff check app tests ../mcp_servers ../scripts

perf:
	$(PY) scripts/measure_latency.py

bundle:
	git archive --format=zip --prefix=flying-florina/ -o flying-florina-src.zip HEAD:flying-florina 2>/dev/null || \
	  (cd .. && zip -qr flying-florina/flying-florina-src.zip flying-florina -x '*/node_modules/*' '*/.venv/*' '*/data/*' '*/dist/*' '*/__pycache__/*' '*/generated_adapters/BRG-*' '*.zip')
	@echo "Wrote flying-florina-src.zip (excludes secrets, caches, venvs, data, model weights)."

clean:
	rm -rf backend/data frontend/dist frontend/test-results frontend/playwright-report generated_adapters/BRG-*
