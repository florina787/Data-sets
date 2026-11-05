# Career_flo AI — Your Intelligent AI Career Partner

A multi-tenant career-intelligence SaaS with these parts:
- a **FastAPI** backend;
- a **LangGraph** supervisor with 15 specialised agents;
- **7 MCP servers** built with the official Python SDK;
- **Qwen3 open-weight models** served by Ollama or llama.cpp (no hosted LLM APIs at runtime);
- **Supabase** (PostgreSQL + Auth + RLS) for data and accounts;
- **Stripe** Checkout and Billing for payments;
- a **React + TypeScript** frontend.

**Trial model:** every new account gets **two free successful uses of every premium feature**, with no card required. Counters live on the server and are independent per feature. The reservation logic is concurrency-safe and idempotent. Failures never consume a use, and a trial never turns into a charge.

## Run it locally (no external accounts needed)
```bash
# backend (Python 3.11+, uv)
cd backend && uv sync
uv run python -c "from app.main import init_db; init_db(); from app.db import SessionLocal; from app.seed import seed_demo; seed_demo(SessionLocal())"
LLM_PROVIDER=ollama LLM_MODEL=qwen3:1.7b uv run uvicorn app.main:app --port 8000   # or LLM_PROVIDER=disabled
# Qwen: install Ollama, then `ollama pull qwen3:1.7b`

# frontend (Node 22)
cd frontend && npm install && npm run dev        # http://localhost:5173  (proxies /api to :8000)
```
Demo login: `demo@careerflo.example` / `DemoPassword123`. All demo records are synthetic and labelled; they are excluded from admin revenue analytics. Without Supabase, `AUTH_MODE=local` issues dev tokens. Production uses `AUTH_MODE=supabase`.

## Tests
```bash
cd backend && uv run pytest                                   # SQLite
TEST_DATABASE_URL=postgresql://... uv run pytest              # PostgreSQL (after `alembic upgrade head`)
cd frontend && npm run typecheck && npm test && npm run build
```
The tests cover acceptance scenarios A–F, MCP discovery, allowlists and identity injection, LangGraph workflows, the streaming chat, Stripe webhooks (signature, replay, out-of-order), cross-user access, counter manipulation, concurrent trial use, malicious uploads, prompt injection and the coding sandbox.

## Where things are
| Requirement | Location |
|---|---|
| Feature registry, plans, trial limit | `backend/app/features.py` |
| Metering (reserve/commit/release, idempotency, nesting) | `backend/app/billing/metering.py` |
| Stripe Checkout, Portal, webhooks | `backend/app/billing/stripe_service.py`, `routers/billing.py` |
| LangGraph supervisor + agents | `backend/app/agents/` |
| MCP servers A–G + gateway | `backend/app/mcp_servers/`, `backend/app/mcp_gateway.py` |
| Qwen client + benchmark | `backend/app/llm/qwen.py`, `backend/scripts/benchmark_qwen.py` |
| Job providers, normalisation, dedupe | `backend/app/jobs/` |
| Resume / ATS / interview / coding / salary / company / portfolio | `backend/app/careers/` |
| Migrations (schema + RLS) | `backend/migrations/versions/` |
| Frontend (22 sections + Skills & Learning, pricing, billing, admin) | `frontend/src/` |

Docs: [Architecture](docs/ARCHITECTURE.md) · [MCP](docs/MCP.md) · [API](docs/API.md) · [Security](docs/SECURITY.md) · [Deployment](docs/DEPLOYMENT.md) · [Qwen benchmark](docs/BENCHMARK.md) · [Limitations & costs](docs/LIMITATIONS_AND_COSTS.md) · [Design](docs/DESIGN.md) · [Dossier assessment](docs/DOSSIER_ASSESSMENT.md)

## Status
Built and tested locally. **Not deployed.** Stripe is wired for **test mode**: live keys are refused unless `STRIPE_ALLOW_LIVE=true`. Live job providers need API keys; until they are added, clearly labelled synthetic jobs are used.
