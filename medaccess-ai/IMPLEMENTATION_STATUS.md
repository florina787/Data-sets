# Implementation Status

Last verified: 2026-10-16. Status legend: **Implemented** (working and tested), **Simulated** (works, but
on synthetic data or in-process stand-ins, labelled as such), **Partial**, **Planned** (not built).

## Verification evidence (executed in this repository)

| Check | Command | Result |
|---|---|---|
| Backend tests (SQLite) | `.venv/bin/python -m pytest` | **129 passed** |
| Backend tests (PostgreSQL 16) | `TEST_DATABASE_URL=postgresql+psycopg://… pytest` | **129 passed** |
| Alembic migration | `alembic upgrade head` on PostgreSQL 16 | 31 tables + `alembic_version` |
| Lint / types | `ruff check`, `mypy app`, `tsc -b` | clean |
| Frontend unit tests | `npx vitest run` | **7 passed** |
| End-to-end (Playwright, Chromium) | vite preview + uvicorn **and** full `docker compose` stack via nginx :8080 | **7 passed** each (desktop + mobile/Pixel 7) |
| Docker | `docker compose up` (postgres, redis, backend, frontend) + `--profile monitoring` | all healthy; Prometheus target `up`; Grafana dashboard provisioned |
| Load test | `infrastructure/ci-cd/load_test.py` | 6.5 req/s, p95 204 ms at concurrency 1; see capacity doc |
| AI-SDLC demo | API test + Playwright | 15/15 stages, defect detected, RCA confirmed, 1.5.1 released, defect absent post-release |

Bugs found and fixed through this verification: the e2e bundle check and the Security Agent caught an env-var name
in UI text, and the release gate correctly blocked until it was fixed. Running in Docker exposed a startup crash
when `CORS_ORIGINS` was comma-separated; it now has a regression test.

## Acceptance criteria (Part 34)

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Frontend loads | ✅ | e2e (all) |
| 2 | Christina appears and responds | ✅ | e2e patient journey; `test_chat_patient_journey` |
| 3 | Select a healthcare service | ✅ | SearchForm; e2e booking test |
| 4 | Search by location | ✅ | `test_search_endpoints` (city, FSA) |
| 5 | Radius filtering | ✅ | `test_radius_filter_respects_every_supported_radius`, boundary tests |
| 6 | Synthetic appointments displayed accurately | ✅ | `test_happy_path_executes_full_graph` (exact facility/days) |
| 7 | Verification statuses correct | ✅ | parametrised `test_verification_status_mapping`, QA-003/011/013/016/017/021/022 |
| 8 | Wait-time calculations correct | ✅ | `test_days_until_and_saved`, QA-010 (DST), QA-015 |
| 9 | LangGraph workflow executes | ✅ | `tests/agents/test_patient_workflow.py` |
| 10 | Agent activity visible | ✅ | LangGraphVisualizer / Agent Activity page; e2e |
| 11 | LangSmith tracing works when configured | ⚠️ **Not verified** | Client + `LangChainTracer` wiring with redaction hooks exists; no LangSmith key available here |
| 12 | Sensitive data redacted from telemetry | ✅ | `test_langsmith_redaction_hook`, audit redaction test |
| 13 | Human approval checkpoints | ✅ | booking, expansion, clarification, release tests |
| 14 | Booking handoff never fabricates confirmation | ✅ | `test_booking_requires_approval_and_never_fabricates_confirmation`, `test_provider_confirmation_only_from_live_integration` |
| 15 | AI-SDLC workflow accessible | ✅ | Command Center e2e |
| 16 | Requirements analysis works | ✅ | `test_requirements_agent_detects_ambiguities` |
| 17 | Architecture diagrams generated | ✅ | `test_graph_mermaid_generated_from_code`; Architecture Explorer |
| 18 | Automated tests execute | ✅ | this table |
| 19 | Controlled defect demonstrable | ✅ | `test_qa_detects_defective_build`, `test_defective_build_affects_workflow` |
| 20 | Monitoring detects the defect | ✅ | `test_full_lifecycle_with_human_checkpoints` |
| 21 | Root-cause evidence displayed | ✅ | `test_rca_requires_evidence`; RootCauseExplorer e2e |
| 22 | Regression tests verify correction | ✅ | regression stage + `REGRESSION_IDS` |
| 23 | Release approval works | ✅ | separation-of-duties tests, e2e |
| 24 | Docker starts the application | ✅ | compose stack verified (needs `--secret extra_ca` only behind TLS-intercepting proxies) |
| 25 | No API keys in frontend assets | ✅ | e2e + Security Agent bundle scan |
| 26 | Role-based restrictions enforced | ✅ | security tests, frontend nav tests |
| 27 | Usable on mobile | ✅ | Playwright Pixel 7 project; responsive layout (manual WCAG audit not performed) |
| 28 | README has working setup instructions | ✅ | commands above were executed |

## Capability status

### Patient healthcare access
| Capability | Status | Notes |
|---|---|---|
| Synthetic dataset (Mode A) | Implemented / Simulated | 41 fictional facilities, 284 slots, deterministic seed, data-quality fixtures |
| Public provider discovery (Mode B) | Planned | data-mode flag only |
| Authorized live integration (Mode C) | Partial | FHIR R4 `Slot` mapping implemented and tested; no live endpoint; partner API adapter raises `IntegrationNotConfigured` |
| Facility discovery, geo filtering, radii 2–100 km | Implemented | driving/transit times are labelled estimates, not routing |
| Verification (6 states), freshness, reliability, dedupe | Implemented | |
| Requisition / referral / private-pay / accessibility rules | Implemented | rules describe fictional facilities; no OHIP guarantee |
| Ranking with separate confirmed / unverified tiers | Implemented | |
| Radius-expansion loop with patient approval | Implemented | max 2 expansions |
| Booking handoff + idempotency + approval | Implemented | never books; self-report is labelled unverified |
| Notifications | Partial | in-app implemented, consent-gated; email/SMS planned |
| Christina chat (deterministic NLU) | Implemented | multi-turn slot filling, RAG Q&A, injection warnings |
| Christina LLM rephrasing | Partial | code path with caching/budgets/usage tracking; **not exercised** without an API key |
| Avatar (SVG, 8 states, reduced motion) | Implemented | Three.js not used |
| Voice (Web Speech API) | Partial | opt-in with disclosure; not automatically tested (browser APIs); French UI planned |
| Interactive map | Implemented | dependency-free schematic SVG (no tile server, so no location leakage) |
| Clinical safety screen | Implemented | keyword-based and conservative; not a clinical triage tool |

### Orchestration, harness, knowledge
| Capability | Status | Notes |
|---|---|---|
| LangGraph patient StateGraph (22 nodes, conditional branches) | Implemented | |
| Durable checkpoints / resume without repeating actions | Implemented | SQLite saver; PostgresSaver planned for multi-replica |
| 20 patient agents + 8 SDLC agents | Implemented | several patient agents are deterministic nodes; the supervisor role is the graph + router |
| Harness (allowlists, permissions, budgets, retries, breakers, contracts, sanitisation) | Implemented | sync tools; timeouts are measured post-hoc rather than pre-empted |
| MCP: 9 logical servers, typed contracts, stdio server via MCP SDK | Partial | catalogue + FastMCP build tested; Analytics MCP planned; booking/notification exposed only via approval-gated workflow |
| LangChain StructuredTools | Implemented | tested through harness |
| RAG (hybrid retrieval, rerank, staleness, refusal, citation verification, KB versioning) | Implemented | deterministic hashed embeddings; external embedding model planned |
| Knowledge base | Implemented | 6 docs: platform docs, one public-help summary (verify at source), fictional facility docs. No invented medical policy |

### AI-SDLC Command Center
| Capability | Status | Notes |
|---|---|---|
| 15-stage LangGraph with 2 human checkpoints | Implemented | |
| Requirements Agent | Implemented | rule-based ambiguity detection |
| Architecture Agent | Implemented | Mermaid, patient/SDLC graphs rendered from code |
| Development Agent | Simulated | proposes a real diff of the mapping; does not edit the repository |
| QA Agent (29 scenarios) + pytest report import | Implemented | |
| Simulation with ground truth | Simulated | synthetic traffic, labelled |
| Monitoring & anomaly detection (8 threshold rules) | Implemented | statistical detection planned |
| RCA (evidence-gated hypotheses) | Implemented | |
| Security Agent | Partial | secret scan, bundle scan, injection/leakage/authz suites; pip-audit only in CI |
| Release Agent + deployment | Simulated | in-process build switch for `demo-staging` / `demo-production` |
| Traceability REQ→ARCH→CODE→TEST→REL→MON | Implemented | |

### Platform
| Capability | Status | Notes |
|---|---|---|
| FastAPI API (Part 21 routes + extras), OpenAPI | Implemented | |
| Auth | Partial | demo JWT; OAuth2/OIDC planned |
| RBAC, rate limiting, validation, error envelope, pagination | Implemented | in-process limiter |
| PostgreSQL schema (30 + 1 tables), Alembic, retention, deletion | Implemented | backups documented, not automated |
| Field encryption | Implemented | Fernet; DB/disk encryption is a platform concern |
| OpenTelemetry | Partial | spans + IDs; no exporter configured by default (console export optional) |
| Prometheus / Grafana | Implemented | dashboard + alert rules |
| Token optimisation | Partial | caching/compression/budgets coded; benchmark measures prompt characters, not provider tokens |
| CI/CD (GitHub Actions) | Implemented, **not yet run on GitHub** | production job is approval-gated and intentionally has no target |
| Kubernetes manifests | Planned / starter | not applied to a cluster |
| WCAG 2.2 AA | Partial | semantic roles, labels, focus styles, reduced motion; no formal audit |

## Known limitations
1. All availability is synthetic. No real provider, FHIR server or booking system is connected.
2. While the SDLC demo has build 1.5.0 active, patient searches use the defective mapping (by design). Reset via Administration.
3. Single-worker throughput is ~6 searches/s (CPU-bound plus SQLite checkpoint/audit writes).
4. LangSmith and LLM paths are untested without credentials.
5. Not legally assessed for PHIPA/PIPEDA. Do not use with real patient data.

## Resuming work (next phases)
1. OIDC login (authorization code + PKCE) and Redis-backed rate limiting.
2. `PostgresSaver` checkpoints; async workers for throughput.
3. Mode B public-discovery adapter with source attribution; Mode C partner sandbox integration.
4. Run CI on GitHub; add pip-audit/npm audit results to the Security dashboard.
5. Formal accessibility audit, French UI, LangSmith verification with a non-production project.
