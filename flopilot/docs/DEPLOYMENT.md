# Deployment

## Local Docker (default target)

```bash
cd flopilot
cp .env.example .env                 # optional
docker compose up --build -d
# web: http://localhost:8080   (nginx serves the app and proxies /api to the backend)
docker compose logs -f backend
docker compose down                  # keep data;  `down -v` deletes the flopilot-data volume
```

Services:

| Service | Image | Notes |
|---|---|---|
| `backend` | `backend/Dockerfile` (python:3.13-slim, non-root uid 10001) | Port 8000 on the internal network only; data in the `flopilot-data` volume at `/data`; health check `GET /api/health` |
| `frontend` | `frontend/Dockerfile` (node:22-alpine build → nginx-unprivileged) | Publishes `8080`; CSP and security headers; proxies `/api/` |

Networks: `internal` (`internal: true`, no internet) connects frontend and backend; `edge` gives the frontend its published port. The backend therefore cannot make outbound connections.

### Optional build/run settings

| Goal | How |
|---|---|
| Real formula verification | `FLOPILOT_INSTALL_LIBREOFFICE=true docker compose build backend` (adds ~600 MB). `FLOPILOT_RECALC_ENGINE=auto` uses it automatically. |
| Use Claude for free-form requests | In `.env`: `FLOPILOT_LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY=…` (server-side only). Start with `docker compose -f docker-compose.yml -f docker-compose.llm.yml up -d` to give the backend egress. Model (`FLOPILOT_LLM_MODEL`, default `claude-opus-5-5`), effort and budgets are configurable. Server-side refusal fallbacks (`fallbacks: "default"`) are enabled in the adapter. |
| Behind a TLS-inspecting proxy | `FLOPILOT_EXTRA_CA_FILE=/path/to/corp-ca.crt docker compose build` — passed as a BuildKit secret, used only during dependency installation and not stored in the image. |
| Different port | Change `ports` of `frontend` in `docker-compose.yml`, and `FLOPILOT_CORS_ORIGINS` if the API is called cross-origin. |

## Local development (no Docker)

```bash
make install
make dev-api      # uvicorn on :8000; reads ../.env (FLOPILOT_ENV_FILE overrides); data in ./data
make dev-web      # Vite on :5173 with /api proxy (FLOPILOT_API overrides the target)
```

## Configuration

All settings are environment variables; see `.env.example` for the full list with defaults (storage, limits, rate limits, auth mode, LLM provider/model/effort/prices, harness budgets, recalculation engine, retention, content logging).

## Operations

* **Backups**: back up the data directory/volume (`flopilot.db` and `blobs/`). Versions are immutable files, so incremental backups are cheap.
* **Retention**: workbooks older than `FLOPILOT_RETENTION_DAYS` are purged at startup (restart daily, or call `apply_retention()` from a scheduler).
* **Crash recovery**: on startup, temp files are removed and interrupted runs are marked failed; published versions are always complete.
* **Health**: `GET /api/health`; admin metrics at `GET /api/admin/metrics` (runs by state, token totals, model-cache hits).

## Moving beyond a single machine

The local build deliberately keeps state simple. Before running more than one backend process:

| Concern | Today | Production path |
|---|---|---|
| Metadata | SQLite (`db.py`, portable SQL, no SQLite-only functions) | PostgreSQL: set up the same tables (types map 1:1: TEXT, INTEGER, REAL), replace `db._connect` with a psycopg pool, keep the transaction helper. Add proper migrations (e.g. Alembic) at that point. |
| Blobs | Local filesystem (`storage.LocalStorage`) | Object storage implementing `storage.Storage` (`put_immutable` with if-none-match, `get`, `delete`); enable server-side encryption. |
| Publication lock | In-process `threading.Lock` per workbook | Database row lock (`SELECT … FOR UPDATE` on the workbook row) or advisory lock; the conditional `UPDATE … WHERE current_version = ?` already prevents double publication. |
| Background runs | Thread pool in the API process | A queue (e.g. Redis/RQ, Celery, or a cloud queue) once runs exceed seconds or LibreOffice verification becomes common. |
| Rate limits | In-process | Shared store (Redis) or gateway. |
| Auth | Demo tokens | OIDC / Microsoft Entra ID via `auth.IdentityProvider`; map groups to roles and tenants to workspaces. |
| Large workbooks | 500k cells in memory | openpyxl read-only streaming for profiling, sampling for type inference (already capped at 5,000 rows), background profiling jobs. |

## Excel add-in (later)

The planned task-pane add-in would call the same API: send the current selection and an uploaded snapshot, receive proposals, and apply an approved change set inside Excel via Office.js (`ExcelHostBridge` in `app/extensions.py`). It is not implemented; nothing in this build claims a live Excel connection.
