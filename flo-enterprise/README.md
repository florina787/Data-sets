# FLO — Financial Leadership, Operations & Wealth Intelligence

An enterprise **agentic AI platform** for an investment-management firm: executive command center, investment and
wealth-advisor workspaces, a governed multi-agent copilot ("Ask Flo"), scenario simulation, decision memory,
regulatory research and AI operations — with deny-by-default governance, privacy controls and human approvals built in.

> **Independent architecture demonstration.** Not affiliated with AGF or any firm; uses no protected branding and has no
> access to proprietary systems. **All data is synthetic** (fixed seed). **All integrations are mock adapters.** The
> default model is a deterministic in-process mock — **no external LLM calls**. **Securities trading is prohibited.**

![Executive Command Center](docs/screenshots/01-executive.png)

## Quick start

**Docker (full stack: PostgreSQL + pgvector, Redis, OPA, API, worker, UI, Prometheus, Grafana)**

```bash
cd flo-enterprise
docker compose --profile observability up -d --build
# UI http://localhost:8080 · API docs http://localhost:8000/docs · Grafana http://localhost:3000 · Prometheus http://localhost:9090
```
Behind a TLS-intercepting corporate proxy, pass its CA bundle as a build secret (TLS verification stays on):
`FLO_EXTRA_CA_FILE=/path/to/corp-ca.pem docker compose build`.

**Local development (SQLite, no services required)**

```bash
make setup          # venv + npm ci
make seed           # migrations + synthetic data + document ingestion
make api            # http://localhost:8000
make ui             # http://localhost:5173 (proxies /api)
```
Sign in by picking a synthetic user (mock identity provider): CEO, CFO, CIO, analyst, two wealth advisors, an external
dealer advisor, compliance officer, privacy officer, AI administrator, and an advisor in a second tenant.

## What is implemented

| Area | Highlights |
|---|---|
| Executive Command Center | 12 KPIs + the 10 required visualizations (AUM trend, attribution waterfall, revenue/expenses, net flows, profitability treemap, margin trend, risk heatmap, geographic map, actual vs budget, initiative scorecard) with filters, drill-down, tooltips, table view, PNG/CSV export, lineage & methodology, last refresh, Explain with Flo |
| Financial engine | Decimal money, AUM reconciliation to the cent, net flows, revenue yield and exact volume/mix/fee attribution, TWR, MWR (IRR), benchmarks, Sharpe, volatility, drawdown, HHI, drift, fee impact, product contribution, scenario revenue impact; semantic metrics layer |
| Investment workspace | portfolio explorer (500 portfolios), portfolio detail (performance, relative return, drawdown, allocation donut, sector treemap, contribution waterfall, geographic map, holdings), fund research, benchmark comparison, risk-return scatter, concentration, correlation heatmap, market intelligence |
| Scenario simulator | base / bull / bear / severe stress + sliders, AUM path, revenue/profit, portfolio impacts, comparison, tornado sensitivity, assumption traceability |
| Wealth Advisor 360 | advisor home, assigned-client directory, Client 360 (masked contacts + audited reveal), portfolio health, goals, retirement projection with what-if, cash-flow forecast, service timeline, suitability screen, meeting prep, product comparison with fee impact |
| Ask Flo | LangGraph enterprise supervisor → 5 domain supervisors → 20 specialist agents, parallel fan-out, numeric grounding, citations, governance trace |
| Governance | deny-by-default RBAC+ABAC policy-as-code, OPA/Rego with parity tests (~2,000 decisions), tenant isolation, resource/tool/model-provider policies, data residency, hash-chained audit |
| Human-in-the-loop | durable approvals (LangGraph `interrupt` + SQLite checkpoints), SHA-256 payload binding, self-approval/replay/expiry/payload-change protection, re-authorization at execution |
| Privacy | PII/secret detection, masking, tokenization, encrypted vault, authorized rehydration, retention purge, subject erasure |
| Knowledge / RAG | malware/file validation, parsing (PDF/DOCX/XLSX/CSV/MD), ACL pre-filter, BM25 + pgvector hybrid, injection quarantine, citations, multilingual query expansion, policy change comparison |
| AI operations | traces, cost per (successful) workflow, latency, tokens, cache hit rates, tool failure rate, queue depth, breakers, fault injection, agent workflow graph, data quality, evaluations, load tests |
| Multilingual | EN / FR / ES / HI / TA / KO UI labels, language detection, approved communication templates in all six languages with translation validation |
| Deployment | Docker Compose, Kubernetes manifests, Helm chart, Terraform module contracts + AWS ca-central-1 example, Prometheus + Grafana, CI workflow, release gate |

## The eight end-to-end demonstrations

All are automated in `tests/e2e/test_journeys.py` (API) and `frontend/e2e/journeys.spec.ts` (browser).

1. **CEO — why AUM rose while profitability fell.** AUM, financial-performance and revenue agents run in parallel: AUM
   +3.08% (12m) on ETF/institutional inflows; margin 30.69% → 27.85% as expenses grew 9.19% vs revenue 4.89%; revenue
   attribution shows a −CAD 36.9m product-mix effect (shift to low-fee vehicles) and −CAD 3.3m fee changes.
2. **CIO — concentration + market shock.** Northgate Technologies is the largest issuer (4.5%, held in 270 portfolios);
   230 portfolios exceed the 10% single-issuer limit; a −25% equity shock is simulated with assumption traceability.
3. **Advisor — portfolio review.** Only assigned clients are visible; four wealth agents build the review and agenda.
4. **Compliance — AI communication review.** A French draft from an approved template passes translation validation,
   waits at a LangGraph interrupt, is approved against its payload hash, then sent to a mock outbox; edits after approval
   invalidate it; replays are rejected.
5. **AI admin — agent failure.** A market-data outage is injected; retries and the circuit breaker are visible; the
   operational-intelligence agent identifies the failing agent and cites the incident report; other agents keep working.
6. **Security — unauthorized client access.** Unassigned, cross-tenant, external-advisor and executive requests for a
   client record are denied with rule codes and audited; the audit chain verifies.
7. **Prompt injection.** Injection in the question is flagged; a compromised model plan requesting exports, e-mails and
   trades is blocked by the tool gateway; a malicious document is quarantined at ingestion.
8. **Decisions vs outcomes.** Decision memory reports delivered/partial/not-delivered decisions, behind-schedule
   initiatives and overdue commitments; D-0001 is measured from data with an explicit "not causal" caveat.

## Verification (run in this environment)

| Check | Result |
|---|---|
| Backend tests (`pytest`) — unit, security, adversarial, e2e journeys | **128 passed** on SQLite **and** on PostgreSQL + Redis |
| OPA policy tests (`opa test policies/opa`) + Python/OPA parity | 7/7 + parity on ~2,000 decisions |
| Frontend typecheck + production build | pass |
| Playwright browser journeys | 6/6 against the dev stack and against the Docker stack |
| Docker Compose deployment | all services healthy; OPA PDP, pgvector retrieval, Redis cache, Prometheus target up, Grafana dashboard provisioned |
| Terraform | module contracts pass `terraform validate`; the AWS example was not validated (provider registry unreachable here) and never applied |
| Load tests | see [docs/OPERATIONS.md](docs/OPERATIONS.md) — measured, not estimated |

Release gate: `make release-gate` (critical tests, OPA tests, evaluations, ruff, bandit, pip-audit, secret scan,
TypeScript) writes `var/release_gate.json` and exits non-zero on any blocking failure.

## Repository layout

```
flo-enterprise/
  frontend/ backend/ agents/ harness/ governance/ privacy/ analytics/ integrations/ retrieval/ scenarios/
  approvals/ observability/ data/ policies/ infrastructure/ tests/ docs/ scripts/
  docker-compose.yml .env.example Makefile README.md
```

## Documentation

[Architecture & current-state assessment](docs/ARCHITECTURE.md) · [Product, KPIs, UX](docs/PRODUCT.md) ·
[Data, methodology, scenarios](docs/DATA_AND_ANALYTICS.md) · [Security, approvals, privacy](docs/SECURITY.md) ·
[Agents, harness, RAG, observability](docs/AGENTS.md) · [Regulatory](docs/REGULATORY.md) ·
[Operations, NFRs, evaluation, load tests](docs/OPERATIONS.md) · [Progress & definition of done](docs/PROGRESS.md)

## Limitations (read before demoing)

* Synthetic data and mock adapters only; no connection to any production system. Figures are illustrative.
* The default model is deterministic templating, not an LLM. Narratives are fluent but formulaic; free-text answers are
  English with localized headings (approved client templates are fully localized). The Bedrock adapter is implemented
  but was not exercised (no credentials).
* Name detection relies on a CRM gazetteer and honorific patterns; Presidio is optional and not installed by default.
* The embedder is a deterministic hashing model (quality below neural embeddings); pgvector is used on PostgreSQL.
* The mock IdP issues HS256 tokens kept in `sessionStorage`; production must use the enterprise OIDC IdP.
* Approval workflow checkpoints use SQLite; a multi-node deployment should use a PostgreSQL checkpointer.
* Per-process state (circuit breakers, agent result cache, cancellation handles) is not shared across API replicas.
* Regulatory references are illustrative and not legal advice; the AI makes no regulatory determinations.
* Load-test numbers come from a single 4-vCPU container that also ran the load generator; they are not production SLAs.
* Not implemented: a dedicated Sankey chart, malware scanning with a real AV engine, DR failover drills (backup/restore
  is documented and the restore path tested locally — see OPERATIONS.md).
