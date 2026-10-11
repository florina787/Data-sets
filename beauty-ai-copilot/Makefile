.PHONY: up down reset test test-backend test-frontend e2e dev-api dev-web data reports backup
up: ; docker compose up --build
down: ; docker compose down
reset: ; cd backend && python -m app.seed --reset                     # demo mode only
data: ; cd backend && python -m app.datagen.synthetic                    # regenerate fixed-seed fixtures
dev-api: ; cd backend && alembic upgrade head && python -m app.seed && uvicorn app.main:app --reload --port 8000
dev-web: ; cd frontend && npm install && npm run dev
test: test-backend test-frontend e2e
test-backend: ; cd backend && python -m pytest -q
test-frontend: ; cd frontend && npm run typecheck && npm test && npm run build
e2e: ; cd frontend && npx playwright test
reports: ; cd backend && python -m scripts.generate_reports
backup: ; cd backend && python -m app.backup dump ../var/backup.json
