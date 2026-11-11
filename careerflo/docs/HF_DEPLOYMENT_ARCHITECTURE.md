# Deployment architecture — Hugging Face options compared

Status: **deployment-ready, not deployed.** Nothing has been created on Hugging Face, Stripe live mode or any cloud.

## Phase 1 — readiness matrix (audit, 2026-11-11)

| Component | Functional? | Local-only today? | Needs production credentials | Synthetic data? | Background processing | Runs on HF? | Evidence level |
|---|---|---|---|---|---|---|---|
| React frontend (23 pages, design system) | ✅ | No | Supabase URL + anon key (public) | Labels synthetic data | No | ✅ Static Space | Built + unit tests + Playwright journeys (real browser) |
| FastAPI API (97 endpoints) | ✅ | No | DB, Supabase, Stripe | — | No (request/response + SSE) | ⚠️ Docker Space only if DB reachable | 66 pytest tests (SQLite + PostgreSQL) |
| Auth (Supabase ES256 JWKS / local dev) | ✅ | Supabase project not yet created | `SUPABASE_URL` | — | No | n/a | JWKS path tested with real ES256 tokens + local JWKS server; **never against a real Supabase project** |
| PostgreSQL schema (41 tables) + RLS (37 policies) | ✅ | Local PostgreSQL | `DATABASE_URL` | — | No | ❌ (port 5432 blocked on Spaces) | Alembic run on PostgreSQL 16; RLS checked with a simulated `auth` schema |
| Trial metering (17 features × 2) | ✅ | No | — | — | No | n/a | Concurrency test (12 threads, PostgreSQL row locks) |
| Stripe Checkout / Portal / webhooks | ✅ code | Test keys absent | `sk_test_…`, `whsec_…`, price ids | — | Webhooks | ✅ outbound 443 | Fake-client unit tests + **stripe-mock 0.206.0 in CI (Stripe API spec)**; **no real test-mode checkout yet** |
| Qwen inference (llama.cpp / Ollama / HF router) | ✅ | Model files local | none (`HF_TOKEN` only for router) | — | Long-lived model server | ✅ in container | Real Qwen3-0.6B/1.7B runs on 2 cores; HF router tested with fake router + live 401 path |
| LangGraph supervisor + 15 agents, 7 MCP servers | ✅ | No | — | — | In-request | n/a | Tests + E2E chat with real model |
| Job providers | ✅ code | Keys absent | JSearch / Adzuna keys | **Yes, until keys are set (labelled)** | No | ✅ (443) | Mapping unit tests; **no live provider call yet** |
| Career Graph, Learning, Analytics | ✅ | No | — | Demo records labelled | No | n/a | Tests + E2E |
| Ops dashboard / readiness | ✅ | In-process counters | — | Separates measured/estimated | No | n/a | Tests; counters reset on restart |
| Email (verification/reset) | Delegated to Supabase | — | Supabase SMTP | — | — | n/a | **Not executed** |
| Backups / retention | Supabase Pro daily backups | — | Supabase Pro | — | — | n/a | **Not executed** |
| Scheduled jobs (job alerts digest) | ❌ not implemented as a worker | — | — | — | Would need a scheduler | — | Gap — alerts are stored, not sent |

**Passing tests ≠ production proof.** Items marked *never/not executed* need the launch runbook's verification steps.

## Option A — Hugging Face-first (one Docker Space)

```
Browser ─▶ Docker Space (CPU Basic, PRO plan) : FastAPI + React + llama.cpp(Qwen3-1.7B)  ─✗─▶ Supabase Postgres :5432
                                                    └─▶ Stripe / HF / JSearch (443 ✓)
```
- Packaged and runnable now: `deploy/hf-space/` (Dockerfile, supervised `start.sh`, Space card).
- **Blocker:** Spaces allow outbound 80/443/8080 only → the API cannot reach Supabase Postgres unless HF grants a
  5432/6543 exception. `GET /api/health/ready` proves this within seconds of the first boot.
- Also: CPU Basic sleeps after 48 h without visitors (cold start ≈ 1–2 min incl. model load), single replica, no SLA,
  2 vCPU shared by API and model.

## Option B — Hybrid low-cost (RECOMMENDED)

```
Browser ─▶ Static Space (free)  : React build (VITE_API_URL=https://api.<domain>)
        └▶ VPS (same container image) : Caddy(HTTPS) → FastAPI + llama.cpp(Qwen3-1.7B, 127.0.0.1)
                                         ├─▶ Supabase (Postgres 5432 + Auth)   ✓
                                         ├─▶ Stripe (test mode)                ✓
                                         └─▶ optional: HF Inference Providers (Qwen3.5-9B) for heavier load
```
- Frontend: `scripts/hf_deploy.py --target static-frontend` (free for every HF account).
- API + Qwen: `deploy/vps/compose.yml` runs the **identical image** as Option A (multi-arch base: amd64 + arm64).
- Database/auth: Supabase. Payments: Stripe test mode until approved.
- Works on Oracle Cloud Always Free (if your account is eligible and capacity exists — *unverified*) or a small paid VPS.

## Option C — minimal-cost production for paying customers

Option B with: an 8 GB VPS (Qwen3-1.7B needs ≈ 3.1–3.5 GB for 2 parallel 8k contexts plus ≈ 0.5 GB for the API),
**Supabase Pro** (daily backups, never paused), a custom domain, and the React app served by the same container (no
separate Static Space needed). Scale inference by switching `LLM_PROVIDER=hf` (Qwen3.5-9B on Inference Providers) when
concurrent chat demand exceeds what 2–4 CPU cores can serve.

## Comparison

| | A: HF Docker Space | B: Static Space + VPS | C: production (VPS + Supabase Pro) |
|---|---|---|---|
| Monthly cost (beta) | $9 PRO (+ Supabase Free) | €0–6 VPS (+ Supabase Free) | ≈ US$40 (VPS 8 GB + Supabase Pro $25) |
| Cold start | Sleeps after 48 h idle; ≈ 20–50 s model load + container start | None (always on) | None |
| Chat latency (measured, 2 vCPU) | first token ≈ 0.3–0.5 s idle; ≈ 8 s with 2 concurrent chats | same per core count | same; more cores → more parallel chats |
| Concurrency (measured) | ≈ 2 simultaneous chats; 10 users on deterministic features p95 < 0.9 s | same on 2 cores | scale cores or use HF router |
| Database | **blocked (port 5432)** unless exception | ✅ | ✅ + backups |
| Security | HF secrets; Space can be private/protected | Caddy TLS, no public model port | + backups, PITR optional |
| Ops complexity | Lowest (git push) | Medium (one VPS) | Medium |
| Scaling limit | 1 replica on free hardware; paid replicas | vertical; add VPS | vertical + HF router |
| Commercial viability | ⚠️ no SLA, DB blocker | ✅ beta | ✅ paying customers |

**Recommendation:** B for a private/public beta, C before charging customers. Keep A as a packaged option, to be
activated only if a private test Space confirms the database is reachable.
