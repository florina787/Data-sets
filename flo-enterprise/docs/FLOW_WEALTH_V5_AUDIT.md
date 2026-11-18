# FLOW WEALTH v5 — architecture audit (Phase 0–1)

Date: 2026-11-18. Every statement below was checked against the code or a command run in this session.

## 1. Correct repository and branch

| Item | Finding |
|---|---|
| Repository | `florina787/Data-sets` (the only repository this session's GitHub access reaches; GitHub code search across it found no other FLO/OPA project) |
| Branch holding the product | `claude/zen-goldberg-t5e2x7`, head `3ed4ee8` "FLO 2.0 design refresh and detailed README" |
| How it was identified | All 28 remote branches were scanned. Only `flo-enterprise/` on this branch has OPA Rego policies (3 `.rego` files), Gemini provider, gold-to-lime chart styling, LumaTrade/Goovest design references, personas, evidence drawers, approvals, client-scoped cache, axe and Playwright tests. Nearest other candidate, `flying-florina/` (`claude/new-session-yijwxb`), has no Rego, no evidence drawer and no LumaTrade styling. Others (`flobank-sherin`, `flopilot`, `florome`, `careerflo`, `wealth-ai-platform`) match none of the governance markers. |
| Working branch for v5 | `claude/inspiring-wozniak-kj43ao`. FLO was merged into it unchanged (merge `d883d0c`); the FLO branch only adds `flo-enterprise/` and `.github/workflows/flo-enterprise.yml`, so nothing else moved. |

## 2. Application directory

`flo-enterprise/` (334 files, 10 build commits: phases 1–10, then FLO 2.0).

## 3. Frontend

React 18 + TypeScript + Vite + Tailwind, ECharts (charts), MapLibre (maps), TanStack Query. FLO conversation workspace in
`frontend/src/flo/` (composer, SSE client, agent timeline, evidence drawer, dynamic dashboard renderer, persona selector) and
15 enterprise pages in `frontend/src/pages/`. Chart theme: near-black tiles, glowing gold-to-lime hero line (`lib/chartTheme.ts`).
Tests: vitest (8), Playwright journeys (20) with axe-core accessibility checks.

## 4. Backend

FastAPI (`backend/main.py`, routers in `backend/api/`), SQLAlchemy 2 + Alembic (4 migrations, SQLite default, PostgreSQL 16 + pgvector
in Compose/CI), Redis optional, background worker, Prometheus metrics. Conversation API streams Server-Sent Events with idempotency keys.

## 5. Agent orchestration

LangGraph enterprise supervisor → 5 domain supervisors → 25 specialist agents + visualization agent (`agents/graph.py`,
`agents/specialists.py`). Each agent has an `AgentSpec` contract (roles, tool allowlist, schemas, budget, classification). The harness
(`harness/runtime.py`) enforces admission, budgets, deadlines, retries, circuit breakers, cancellation and **numeric grounding** (narrative
numbers must appear in tool facts). A deterministic intent planner (`conversation/intent.py`, `flo-intent-rules/1.0`) maps messages to
intents, agents and charts. The model adapter is a deterministic in-process mock by default; Bedrock and Gemini adapters exist.

## 6. Authentication and authorization

Mock IdP issuing HS256 JWTs (synthetic users). Deny-by-default **RBAC + ABAC** from a versioned YAML policy bundle (`policies/`, hash in
every decision) with an **OPA/Rego mirror** and a parity test. Every agent tool call passes the **tool gateway** (`harness/tools.py`):
unknown/prohibited tool → agent allowlist → strict argument schema → policy decision for the *human* principal → approval obligations →
rate limit → breaker/timeout → output size; every allow/deny is written to a SHA-256 hash-chained audit log. Personas are UX only and never
grant access. Model providers are policy-gated by data classification (Gemini: **public data only**). Record-scoped outputs are never
cached, and the policy version is part of the cache key (fix for the stale-after-reassignment bug, covered by tests).

## 7. Data sources and storage

All enterprise data is **synthetic** (fixed seed) behind mock adapters (`integrations/mock`). The existing `market.intelligence` tool
returns synthetic monthly benchmark and sector returns. Storage: relational tables for tenants, users, clients, portfolios, holdings,
benchmarks, products, finance, risk, approvals, audit, documents (pgvector), conversations.

## 8. Existing analytics

Deterministic `Decimal` engine: AUM roll-forward, revenue bridge, profitability, TWR/MWR, Sharpe, drawdown, concentration (HHI, effective
N), correlation, sector contribution, scenarios and sector shocks, wealth/retirement projections, data quality. Semantic metric layer.

## 9. Existing model training

**None.** FLO computes analytics deterministically; it has no forecasting models, training pipeline or backtester.

## 10. Reusable components from the synthetic `flowwealth/` prototype

Algorithms only (no data): point-in-time lake pattern (`available_at`, versioned manifests), quality checks, leakage-safe features with
**availability-cohort ranks** (the cross-timezone look-ahead fix), purged/embargoed chronological and walk-forward splits, cost model and
gross-vs-net backtest, metrics, hash-chained append-only prediction ledger, promotion criteria with human approval and rollback, profile
model separating trading speed from risk appetite. These are ported into `flo-enterprise/markets/`. The `flowwealth/` app itself is **not**
the target and is marked deprecated.

## 11. Missing market-intelligence capabilities

Real market data and provenance; dataset licensing records; point-in-time research lake; forecasting models and evaluation; transaction-cost
backtests; model promotion; prediction memory; market/quant/news/bull/bear/skeptic agents; market intents and charts; market UI views;
current-data adapter and scheduler; a chart provenance value for real historical data (today every chart defaults to `platform_synthetic`).

## 12. Integration plan (preserves existing functionality)

| Concern | Plan |
|---|---|
| Code location | New package `flo-enterprise/markets/` beside `analytics/` and `scenarios/`; no existing module is replaced. |
| Data | Kaggle datasets downloaded with KaggleHub (anonymous public access) into a local cache; Parquet + DuckDB research lake under `var/markets/` (gitignored). Dataset manifests (licence, checksums, counts) committed. Enterprise synthetic client data untouched. |
| Classification | New resource type `market_dataset`, classification **public**. Market agents only allowlist market tools, so they cannot reach client data even if a plan asks. |
| Policy | Extend existing `market:read`; add `quant:read` for model research outputs. YAML bundle version bump, OPA data regenerated, parity test run. |
| Agents | New specialists through the existing harness and gateway: market data, quant research, news research, bull, bear, skeptic, evidence aggregator. No orchestration framework replaced. |
| Conversation | New intents in the existing planner; new chart builders in the existing visualization agent; new provenance value `historical_market_data`. |
| Prediction memory | New tables via Alembic migration `0005`, append-only (DB triggers) and hash-chained, in FLO's existing database. |
| UI | New pages inside the existing shell and design system (ChartCard/ECharts gold-to-lime theme), plus market prompts on FLO Home. |
| Tests | All 181 existing backend tests, 8 vitest tests and Playwright journeys must keep passing; new tests for each item in the brief's §16. |

## Baseline before any change (this session)

| Suite | Result |
|---|---|
| Backend `pytest` (SQLite) | **181 passed, 1 skipped** (OPA parity needs the `opa` binary) |
| Frontend `vitest` | **8/8** |
| Frontend `tsc -b` | clean |
