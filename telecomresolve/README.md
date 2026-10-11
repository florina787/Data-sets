# TelecomResolve Copilot

> **Independent telecom prototype — synthetic data.** Not affiliated with, sponsored by, or endorsed by any
> operator. It has no access to any operator's systems, data, policies, topology or models. Every customer,
> account, network asset, incident, measurement and policy value in this repository is fictional.

TelecomResolve Copilot is an enterprise prototype for investigating recurring home-internet disconnections.
It takes a case from **intake → evidence collection → diagnosis → recommended action → human approval →
simulated execution → recovery verification**, with every step recorded in an audit trail that can be replayed.

The chat box is one way in; the product is the workflow. Every conclusion cites its evidence, separates what was
**measured** from what was **reported**, and abstains when the evidence is missing, stale or contradictory.

## Hypothesis being explored

Investigators *could* benefit from one evidence-backed workflow that links recurring complaints with network
conditions, earlier interventions and outcomes. This is a hypothesis to validate with stakeholders
([discovery worksheet](docs/discovery-worksheet.md)), not a claim that any operator lacks such a capability.
Public context that motivated the domain choice: an operator's published contact-centre AI services page and a
2024 press release about a telco–ServiceNow partnership (links in [docs/discovery-worksheet.md](docs/discovery-worksheet.md)).

## What is implemented (Phase 1 MVP + parts of Phase 2/3)

| Area | Status |
|---|---|
| Four-node LangGraph workflow (triage, evidence, diagnosis, action planning) with typed shared state, persistent checkpoints, bounded evidence loop, time/token budgets | Implemented |
| Human review via LangGraph `interrupt()` backed by a persistent approval record bound to case, action, payload hash, policy version, evidence snapshot and expiry | Implemented |
| Backend state machine (16 states) with compare-and-set transitions | Implemented |
| Versioned action catalog + deterministic policy engine, separation of duties | Implemented |
| Idempotent simulated execution, lost-response reconciliation, duplicate prevention | Implemented |
| Recovery verification from post-action samples (simulated, fast-forwarded time) | Implemented |
| Tenant isolation, role permissions, account-segment scope, field minimisation, log redaction | Implemented |
| Append-only, hash-chained audit trail with replay | Implemented (tamper-evident, not tamper-proof) |
| Citations that open the exact record/excerpt and are re-validated against the source | Implemented |
| Prompt-injection quarantine for retrieved records | Implemented (pattern-based) |
| 13 seeded scenarios with separately stored labels; evaluation runner with release gates and a heuristic baseline | Implemented |
| React + TypeScript UI: Overview, Cases, Copilot Workspace, Evidence, Approvals, Audit, Evaluation | Implemented |
| LIVE / HYBRID generation through the Anthropic API with validation, timeouts, retries, circuit breaker, budget | Implemented, **not exercised against the real API in this build** (no key was available); covered by tests with a scripted fake provider |
| Semantic (pgvector) retrieval | **Not implemented** — lexical BM25 only; documented as a gap |
| Enterprise connectors (ITSM/ServiceNow, CRM, telemetry, provisioning, dispatch, comms, billing) | Stubs that fail clearly as `UNCONFIGURED` |
| SSO / production authentication | **Not implemented** — production mode refuses requests rather than falling back |

## Quick start

### Option A — local development (no Docker)

Requirements: Python 3.13, Node 22.

```bash
cd telecomresolve
make setup                       # pip install -r backend/requirements-dev.txt; npm ci
make seed                        # alembic upgrade head + synthetic seed (SQLite by default)
make dev-backend                 # http://127.0.0.1:8000  (OpenAPI UI at /docs)
make dev-frontend                # http://127.0.0.1:5173  (proxies /api to the backend)
```

Restore the known demo state at any time with `make reset` (refused unless `APP_MODE=demo`).

### Option B — Docker Compose (PostgreSQL)

```bash
cd telecomresolve
cp .env.example .env             # optional; defaults work for a local demo
docker compose up --build        # UI: http://localhost:8080, API: http://localhost:8000
```

> The Compose images were **not built in this environment** (Docker Hub rate-limited the base-image pulls).
> The same startup sequence (`alembic upgrade head` → seed → uvicorn) was verified against a local PostgreSQL 16.

### Tests and evaluation

```bash
make test-backend     # 60 pytest tests (SQLite); CI also runs them on PostgreSQL
make test-frontend    # tsc + vitest + production build
make e2e              # Playwright: full journey in Chromium against a fresh demo backend
make eval             # labelled evaluation on an isolated DB -> evaluation/results/
```

## Operating modes (always shown in the UI header)

| Setting | Values | Meaning |
|---|---|---|
| `APP_MODE` | `demo` (default) / `production` | Demo enables persona login, seeding and reset. Production disables all three and requires an SSO provider (not implemented → requests are refused with `IDP_NOT_CONFIGURED`). |
| `GENERATION_MODE` | `DEMO` (default) / `LIVE` / `HYBRID` | DEMO = deterministic rules and templates; no model is called, and output is labelled DEMO. LIVE/HYBRID = real server-side model calls; output is validated and cannot override policy. There is no silent fallback: an outage produces an explicit `FAILED` state with the provider error code. |
| Connector mode | `SIMULATED` | All operational reads/writes use synthetic data and a simulated system of record. Nothing is sent externally. |

## Demo personas (demo mode only)

| Persona | Role | Tenant | Can |
|---|---|---|---|
| Ava Moreau, Ben Okafor | specialist | north | investigate, confirm low-risk actions, verify |
| Chloe Tremblay | network_analyst | north | read evidence incl. restricted runbook, confirm incident links |
| Dev Singh | field_coordinator | north | execute approved dispatches |
| Emma Laurent | supervisor | north | approve dispatches (not her own), read tenant audit, run evaluation |
| Farah Haddad | auditor | north | read-only, contact details hidden |
| Gil Romero | specialist | south | sees only south-tenant data |

The persona selector chooses *which server-side user record* the session is issued for; role, tenant and
scope are always read from the database on each request.

## Five-minute walkthrough

See [docs/demo-script.md](docs/demo-script.md). Short version: sign in as Ava → open **C-1003** → *Run
investigation* → open the `DIAG-SNR` citation → note the earlier modem restarts are not repeated → switch to
Emma and approve → switch to Dev and execute → *Verify recovery* → open **Audit**. Then open **C-1004** to see
abstention.

## Repository layout

```
backend/app/agents/       triage, evidence, diagnosis, planning nodes; provider abstraction; grounded Q&A
backend/app/workflows/    LangGraph graph, checkpoints, approval/execution/verification services, scope checks
backend/app/policies/     state machine, action catalog loader, policy engine
backend/app/connectors/   typed tool specs, synthetic adapters, enterprise stubs
backend/app/retrieval/    knowledge chunking + scoped BM25, citation resolution/validation
backend/app/auth/         roles, permissions, demo sessions
backend/app/observability audit chain, redaction
backend/app/evaluation/   labelled evaluation runner
backend/tests/            pytest suite
data/synthetic/           dataset, action catalog, diagnostic rules (versioned)
data/knowledge/           fictional troubleshooting guides, runbooks, policies
evaluation/               labels (kept away from agents) and results
frontend/                 React + TypeScript UI, Vitest, Playwright e2e
docs/                     architecture, data dictionary, API, security, integrations, discovery, demo, readiness
```

## Documentation

- [Architecture and production reference design](docs/architecture.md)
- [Data dictionary](docs/data-dictionary.md)
- [API contract](docs/api.md) ([openapi.json](docs/openapi.json))
- [Security and privacy notes](docs/security.md)
- [Integration matrix](docs/integration-matrix.md)
- [Discovery worksheet and gap-validation matrix](docs/discovery-worksheet.md)
- [Demo script](docs/demo-script.md)
- [Business measures](docs/business-measures.md)
- [Known limitations, production-readiness checklist and roadmap](docs/limitations-and-readiness.md)
- [Latest evaluation report](evaluation/results/latest.md)

## Dependencies

Backend versions are pinned in `backend/requirements.txt` and were installed and tested together on
Python 3.13 (2026-10-11). Frontend versions are pinned in `frontend/package.json` with a lockfile
(React 19.3, Vite 7.3, TypeScript 5.9, Vitest 3.2, Playwright 1.56).
