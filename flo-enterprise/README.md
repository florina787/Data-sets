<p align="center">
  <img src="docs/images/banner.svg" alt="FLO Enterprise — Financial Leadership, Operations & Wealth Intelligence" width="100%">
</p>

<p align="center">
  <img alt="tests" src="https://img.shields.io/badge/pytest-128%20passed-10B981?style=flat-square">
  <img alt="browser" src="https://img.shields.io/badge/Playwright-6%2F6-10B981?style=flat-square">
  <img alt="evals" src="https://img.shields.io/badge/evals-10%2F10-10B981?style=flat-square">
  <img alt="release gate" src="https://img.shields.io/badge/release%20gate-PASS-10B981?style=flat-square">
  <img alt="opa" src="https://img.shields.io/badge/OPA%20parity-~2000%20decisions-3B82F6?style=flat-square">
  <img alt="stack" src="https://img.shields.io/badge/LangGraph%20·%20FastAPI%20·%20React-0B1220?style=flat-square">
  <img alt="data" src="https://img.shields.io/badge/data-100%25%20synthetic-D4AF37?style=flat-square">
</p>

<p align="center">
  An enterprise <b>agentic AI platform</b> for an investment-management firm — executive command center, investment and
  wealth-advisor workspaces, a governed multi-agent copilot (<b>Ask Flo</b>), scenario simulation, decision memory,
  regulatory research and AI operations — with deny-by-default governance, privacy controls and human approvals built in.
</p>

> [!IMPORTANT]
> **Independent architecture demonstration.** Not affiliated with AGF or any firm; uses no protected branding and has no
> access to proprietary systems. **All data is synthetic** (fixed seed) · **all integrations are mock adapters** · the
> default model is a **deterministic in-process mock** (no external LLM calls) · **securities trading is prohibited.**

<p align="center">
  <img src="docs/screenshots/01-executive.png" alt="Executive Command Center" width="100%">
</p>

---

## Contents

[At a glance](#at-a-glance) · [The data story](#the-data-story) · [Product tour](#product-tour) ·
[Architecture](#architecture) · [Agents](#multi-agent-orchestration) · [Governance & security](#governance-zero-trust--human-in-the-loop) ·
[Knowledge / RAG](#permission-aware-knowledge-retrieval) · [Analytics & scenarios](#financial-engine--scenario-simulator) ·
[The 8 demonstrations](#the-eight-end-to-end-demonstrations) · [Verification](#verification--measured-performance) ·
[Quick start](#quick-start) · [Repository](#repository-layout) · [Docs](#documentation) · [Limitations](#limitations)

## At a glance

<table>
<tr>
<td align="center"><h3>20</h3>specialist agents<br><sub>+ 6 LangGraph supervisors</sub></td>
<td align="center"><h3>13</h3>workspaces<br><sub>role-aware navigation</sub></td>
<td align="center"><h3>~2,000</h3>policy decisions<br><sub>Python ⇄ OPA parity-tested</sub></td>
<td align="center"><h3>128</h3>backend tests<br><sub>SQLite & PostgreSQL</sub></td>
</tr>
<tr>
<td align="center"><h3>2,000</h3>synthetic clients<br><sub>500 portfolios · 100 funds</sub></td>
<td align="center"><h3>10,000</h3>transactions<br><sub>24 months of history</sub></td>
<td align="center"><h3>6</h3>languages<br><sub>EN · FR · ES · HI · TA · KO</sub></td>
<td align="center"><h3>0</h3>external LLM calls<br><sub>numeric-grounded narratives</sub></td>
</tr>
</table>

## The data story

The synthetic dataset is generated (seed `20261020`) so the headline executive question is **answerable from data, not
scripted**: markets rise with a spring-2025 drawdown, client money rotates from high-fee mutual funds into low-fee ETFs and
an institutional pool, a 15 bp fee cut lands in Nov 2025, and technology spend steps up in Aug 2025.

<p align="center"><img src="docs/images/story-aum-yield-margin.png" alt="AUM up while revenue yield and operating margin fall" width="100%"></p>

<table>
<tr>
<td width="50%"><img src="docs/images/revenue-attribution.png" alt="Revenue attribution waterfall"><br>
<sub><b>Exact revenue attribution</b> — change = volume + rate; rate = product mix + fee changes. Mix shift to low-fee
vehicles costs CAD 36.9m; fee changes CAD 3.3m.</sub></td>
<td width="50%"><img src="docs/images/net-flows-rotation.png" alt="Cumulative net flows by vehicle"><br>
<sub><b>Flow rotation</b> — cumulative net flows by vehicle: ETFs and pooled mandates gain while mutual funds bleed.</sub></td>
</tr>
</table>

## Product tour

### Executive Command Center
KPIs plus the ten required visualizations. Every chart supports hover, drill-down/filtering, a **table view**,
**PNG/CSV export**, a **lineage & methodology** panel (semantic metric ids, adapters, dataset version), last refresh
time and **Explain with Flo**.

<table>
<tr>
<td width="50%"><img src="docs/screenshots/01b-executive-revenue-flows.png" alt="Revenue and expenses, net flows"><br><sub>Revenue vs expenses (one CAD axis) · net flow analysis with drill-down</sub></td>
<td width="50%"><img src="docs/screenshots/01c-executive-profitability-margin.png" alt="Profitability treemap and margin trend"><br><sub>Product profitability treemap (diverging margin) · operating margin & revenue yield</sub></td>
</tr>
<tr>
<td><img src="docs/screenshots/01d-executive-risk-geo.png" alt="Risk heatmap and geographic exposure"><br><sub>Enterprise risk heatmap · look-through geographic exposure (MapLibre, bundled shapes)</sub></td>
<td><img src="docs/screenshots/01e-executive-budget-initiatives.png" alt="Actual vs budget and initiatives"><br><sub>Actual vs budget variance · strategic initiative scorecard (progress vs plan)</sub></td>
</tr>
<tr>
<td><img src="docs/screenshots/01f-lineage-panel.png" alt="Lineage panel"><br><sub>Source lineage & methodology on every chart — AUM reconciled to the cent</sub></td>
<td><img src="docs/screenshots/02-ask-flo.png" alt="Ask Flo answer"><br><sub><b>Ask Flo</b>: three agents in parallel answer the CEO question, with a governance trace of every tool call</sub></td>
</tr>
</table>

### Investment intelligence & scenario simulator

<table>
<tr>
<td width="50%"><img src="docs/screenshots/03a-portfolio-explorer.png" alt="Portfolio explorer"><br><sub>Portfolio explorer — 500 portfolios, client identity withheld (data minimization)</sub></td>
<td width="50%"><img src="docs/screenshots/03-portfolio-detail.png" alt="Portfolio detail"><br><sub>TWR, MWR, Sharpe, drawdown, effective N; performance vs benchmark; relative return</sub></td>
</tr>
<tr>
<td><img src="docs/screenshots/03b-portfolio-allocation.png" alt="Allocation"><br><sub>Drawdown · allocation donut · sector treemap · contribution waterfall</sub></td>
<td><img src="docs/screenshots/03c-risk-intelligence.png" alt="Risk intelligence"><br><sub>Enterprise issuer concentration · sector exposure</sub></td>
</tr>
<tr>
<td><img src="docs/screenshots/03d-correlation.png" alt="Correlation heatmap"><br><sub>Sector correlation heatmap (diverging scale centred on zero)</sub></td>
<td><img src="docs/screenshots/03e-performance-benchmarks.png" alt="Benchmarks"><br><sub>Relative return by fund · risk-return bubble chart</sub></td>
</tr>
<tr>
<td><img src="docs/screenshots/03f-market-intelligence.png" alt="Market intelligence"><br><sub>Market intelligence from the (mock) market-data provider</sub></td>
<td><img src="docs/screenshots/03g-geographic-exposure.png" alt="Geographic exposure"><br><sub>Geographic exposure — enterprise, funds or managed portfolios</sub></td>
</tr>
<tr>
<td><img src="docs/screenshots/04-scenarios.png" alt="Scenario simulator"><br><sub>Scenario simulator — severe stress with sliders and portfolio impacts</sub></td>
<td><img src="docs/screenshots/04b-scenario-comparison-tornado.png" alt="Scenario comparison and tornado"><br><sub>Assumption traceability · scenario comparison · tornado sensitivity</sub></td>
</tr>
</table>

### Wealth Advisor 360

<table>
<tr>
<td width="50%"><img src="docs/screenshots/05a-advisor-home.png" alt="Advisor home"><br><sub>Advisor home — only <i>assigned</i> clients are visible (resource-level authorization)</sub></td>
<td width="50%"><img src="docs/screenshots/05-client-360.png" alt="Client 360"><br><sub>Client 360 — masked contacts with audited, policy-checked reveal; suitability screen; timeline</sub></td>
</tr>
<tr>
<td><img src="docs/screenshots/05b-retirement.png" alt="Retirement"><br><sub>Goal progress · retirement projection with what-if inputs · cash-flow forecast</sub></td>
<td><img src="docs/screenshots/05c-meeting-prep.png" alt="Meeting prep"><br><sub>Meeting preparation — four wealth agents build the review and agenda</sub></td>
</tr>
<tr>
<td><img src="docs/screenshots/06-comms-draft.png" alt="Communication draft"><br><sub>Hindi client letter from an approved template — numbers & terms validated, awaiting compliance</sub></td>
<td><img src="docs/screenshots/16-external-advisor-products.png" alt="External advisor products"><br><sub>External dealer advisor — public product research and fee comparison only</sub></td>
</tr>
</table>

### Compliance, governance, privacy & AI operations

<table>
<tr>
<td width="50%"><img src="docs/screenshots/07-approvals.png" alt="Approvals"><br><sub>Approval queue — exact payload, SHA-256 hash, evidence, risk, approver role, expiry</sub></td>
<td width="50%"><img src="docs/screenshots/09-regulatory-change.png" alt="Regulatory change"><br><sub>Regulatory change comparison (section-level diff between policy versions)</sub></td>
</tr>
<tr>
<td><img src="docs/screenshots/09b-exceptions-evidence.png" alt="Exceptions"><br><sub>Exception management with evidence collection and audit trail</sub></td>
<td><img src="docs/screenshots/13-knowledge-search.png" alt="Knowledge search"><br><sub>Permission-aware search — a French query retrieves the French policy; 8 docs excluded by ACL</sub></td>
</tr>
<tr>
<td><img src="docs/screenshots/14-prompt-injection.png" alt="Prompt injection"><br><sub>Prompt injection flagged (high) — no export, no tool bypass; answer stays grounded in policy</sub></td>
<td><img src="docs/screenshots/12-privacy.png" alt="Privacy console"><br><sub>Privacy console — detection, tokenization (<code>[CLIENT_001]</code>), policy-checked rehydration</sub></td>
</tr>
<tr>
<td><img src="docs/screenshots/11-audit-log.png" alt="Audit log"><br><sub>Hash-chained audit log with one-click chain verification</sub></td>
<td><img src="docs/screenshots/11b-rbac-matrix.png" alt="RBAC matrix"><br><sub>Policy-as-code: RBAC matrix, ABAC rules, approval rules</sub></td>
</tr>
<tr>
<td><img src="docs/screenshots/08-aiops.png" alt="AI operations"><br><sub>AI operations — cost per (successful) workflow, latency, cache hits, breakers, capacity</sub></td>
<td><img src="docs/screenshots/08b-agent-workflow-graph.png" alt="Agent workflow graph"><br><sub>Per-workflow agent graph: supervisors → agents → tool calls</sub></td>
</tr>
<tr>
<td><img src="docs/screenshots/08c-agent-registry.png" alt="Agent registry"><br><sub>Agent registry — every agent's contract (roles, tools, budgets, approvals, evals)</sub></td>
<td><img src="docs/screenshots/10-decision-memory.png" alt="Decision memory"><br><sub>Executive decision memory — outcomes vs targets, with a "not causal" caveat</sub></td>
</tr>
<tr>
<td><img src="docs/screenshots/08d-data-quality.png" alt="Data quality"><br><sub>Measured data-quality checks (one real failure: overdue KYC)</sub></td>
<td><img src="docs/screenshots/15-data-products.png" alt="Data products"><br><sub>Governed data products: owner, classification, lineage, SLA, access policy, schema</sub></td>
</tr>
</table>

## Architecture

```mermaid
flowchart TB
  subgraph EXP["Experience — React · TypeScript · Vite · Tailwind · ECharts · Recharts · MapLibre · TanStack"]
    UI["13 role-aware workspaces"]:::ui
    ASK["Ask Flo side panel"]:::ui
  end
  subgraph API["FastAPI — authN · deny-by-default authZ · load shedding · security headers"]
    R["Domain routers"]
    J["Async jobs → worker"]
  end
  subgraph ORCH["LangGraph orchestration"]
    SUP["Enterprise supervisor → 5 domain supervisors"]
    AG["20 specialist agents"]
    HITL["Durable approval workflow<br/>interrupt() + checkpoints"]
  end
  subgraph CTRL["Control plane"]
    H["Agent harness<br/>budgets · retries · breakers · grounding"]
    TG{{"Tool gateway"}}
    PDP["Policy engine<br/>RBAC + ABAC · OPA sidecar"]
    PRIV["Privacy service<br/>tokenize · vault · rehydrate"]
    AUD[("Hash-chained<br/>audit log")]
  end
  subgraph DATA["Data & knowledge"]
    SEM["Semantic metrics layer"]
    FIN["Deterministic analytics<br/>Decimal · scenarios"]
    RAG["Hybrid RAG<br/>BM25 + pgvector"]
    ADP["Mock enterprise adapters<br/>PMS · accounting · CRM · ERP · market data · DMS · DWH"]
    PG[("PostgreSQL 16<br/>+ pgvector")]
    RD[("Redis")]
  end
  OBS["Observability<br/>traces · Prometheus · Grafana · LangSmith (redacted)"]
  UI & ASK --> R
  R --> SUP --> AG --> H --> TG
  R --> HITL
  TG --> PDP
  TG --> FIN & RAG
  FIN --> SEM --> ADP --> PG
  RAG --> PG
  R -.-> RD
  TG -.-> AUD
  PDP -.-> AUD
  AG -.-> PRIV
  H -.-> OBS
  classDef ui fill:#162338,stroke:#D4AF37,color:#ECF0F6
```

<details>
<summary><b>Deployment topology</b> (Docker Compose · Kubernetes · Helm · Terraform)</summary>

```mermaid
flowchart LR
  U((Browser)) --> NG["UI · nginx<br/>CSP · re-resolving upstream"]
  NG --> A1["API pod"] & A2["API pod"] & A3["API pod …HPA"]
  subgraph pod["each API pod"]
    A1 --- O1["OPA sidecar<br/>fail-closed"]
  end
  W["Worker pods<br/>queue-depth scaling"] --> PG
  A1 & A2 & A3 --> PG[("PostgreSQL + pgvector<br/>PITR · multi-AZ")]
  A1 & A2 & A3 --> RD[("Redis<br/>TLS · AUTH")]
  A1 -. "/metrics" .-> PR["Prometheus"] --> GF["Grafana"]
  M["Migration Job<br/>Alembic + seed"] --> PG
```

Compose runs all of this locally (`docker compose --profile observability up -d`). Kubernetes manifests and a Helm chart
add HPA, PDB, default-deny NetworkPolicies, restricted pod security and read-only root filesystems. Terraform provides
provider-neutral module contracts plus an illustrative AWS `ca-central-1` example (Canadian residency).
</details>

<details>
<summary><b>Current-state reference model</b> (13 enterprise system categories → FLO)</summary>

```mermaid
flowchart LR
  MKT[Market data] --> PMS[Portfolio mgmt] --> OMS[Trading / OMS]
  OMS --> ACCT[Portfolio accounting] --> PERF[Performance]
  ACCT --> DWH[(Data warehouse)]
  PERF --> DWH
  ERP[ERP / GL] --> DWH
  CRM[CRM] --> DWH
  DMS[Document mgmt] -.-> GRC[Compliance & risk]
  DWH --> BI[BI & reporting]
  DWH --> PORTAL[Advisor portal]
  IAM[IAM / SSO] -. authN .-> PMS & CRM & ERP & BI & PORTAL & GRC
  DWH ==> FLO{{FLO data products<br/>+ semantic layer}}
  DMS ==> FLO
```

The full integration discovery matrix (owner, purpose, classification, APIs, batch/event interfaces, auth, freshness,
SLA, rate limits, residency, licensing, risk) and the assumptions to validate are in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
</details>

## Multi-agent orchestration

```mermaid
flowchart LR
  Q[/"Question + chart context"/] --> G["guard<br/>size · injection scan · language"]
  G --> ES{"enterprise<br/>supervisor"}
  ES --> EX["executive"] & IN["investment"] & WE["wealth"] & RC["risk & compliance"] & AO["AI operations"]
  EX -- "Send() fan-out<br/>(independent tasks only)" --> S1["aum"] & S2["financial performance"] & S3["revenue"]
  S1 & S2 & S3 --> SY["synthesize<br/>narrative · citations · approvals · governance trace"]
  IN & WE & RC & AO -.-> SP["… 17 more specialists"] -.-> SY
  SY --> E((answer))
```

The graph is a DAG (no agent-to-agent loops, bounded recursion). Every specialist runs through the **harness** and can
only reach data through the **tool gateway**:

```mermaid
sequenceDiagram
  autonumber
  participant A as Agent
  participant H as Harness
  participant G as Tool gateway
  participant P as Policy engine (OPA)
  participant T as Analytics tool
  participant L as Audit log
  A->>H: run(input) — role admission, schema, budget, deadline
  A->>G: ctx.tool("client.profile", client_id)
  G->>G: known? not prohibited? allowlisted for this agent? strict args?
  G->>P: authorize(human principal, client:read, client resource)
  P-->>G: allow / deny + rule ids + policy version
  alt denied or approval-gated
    G->>L: deny event
    G-->>A: PolicyDenied / ApprovalRequired
  else allowed
    G->>T: call (circuit breaker + timeout)
    T-->>G: facts
    G->>L: allow event
    G-->>A: facts
  end
  A->>H: narrative from facts
  H->>H: reject any number not present in facts
```

| Domain | Agents |
|---|---|
| Executive | AUM · Financial Performance · Revenue · Board Reporting · Decision Memory |
| Investment | Portfolio · Benchmark · Investment Research · Market Intelligence · Scenario |
| Wealth | Client Intelligence · Wealth Advisor · Retirement Planning · Product Research · Client Meeting |
| Risk & compliance | Risk · Compliance Research |
| AI operations | Operational Intelligence · Data Quality · Evaluation |

Each agent registers a full contract — name, version, owner, roles, tools, input/output schema, budget, data
classification, approval and evaluation requirements ([docs/AGENTS.md](docs/AGENTS.md)).

## Governance, zero-trust & human-in-the-loop

```mermaid
flowchart LR
  REQ["request(principal, action, resource, context)"] --> A{authenticated?}
  A -- no --> D1["DENY · AUTHN-REQUIRED"]
  A -- yes --> B{prohibited action?<br/>trade · shell · raw DB}
  B -- yes --> D2["DENY · PROHIBITED-ACTION"]
  B -- no --> C{RBAC grant?}
  C -- no --> D3["DENY · RBAC-DENY-DEFAULT"]
  C -- yes --> T{same tenant?}
  T -- no --> D4["DENY · TENANT-ISOLATION"]
  T -- yes --> X{ABAC rules<br/>assignment · clearance · segregation · residency}
  X -- fail --> D5["DENY · rule id"]
  X -- pass --> OB{approval-gated?}
  OB -- yes --> AP["ALLOW with obligation<br/>approval_required"]
  OB -- no --> OK["ALLOW"]
```

Approvals are durable and bound to the exact payload:

```mermaid
stateDiagram-v2
  [*] --> pending: request (requester authorized)
  pending --> approved: approver confirms payload hash (not self, right role, same tenant)
  pending --> rejected
  pending --> expired: TTL
  approved --> executed: re-authorize · hash matches · single use
  approved --> invalidated: payload changed after approval
  approved --> expired
  executed --> [*]: replay rejected
```

| Control | Implementation |
|---|---|
| Identity | `Principal` propagated API → harness → tools → telemetry; roles from the directory, never from client claims |
| Policy-as-code | versioned YAML bundle, content hash in every decision; Rego mirror with parity tests; OPA sidecar fails closed |
| Resource-level | clients, portfolios, documents, approvals, exports, jobs; unknown ids denied like cross-tenant ids |
| Model providers | scoped service identity; region/classification policy enforces Canadian residency |
| Audit | append-only SHA-256 hash chain in a separate store; PII redacted; tamper detection tested |
| Privacy | detection (SIN with Luhn, accounts, e-mail, phone, DOB, addresses, names, secrets) · masking · tokenization · encrypted vault · audited rehydration · retention purge · subject erasure |
| HITL | comms, recommendations, sensitive exports, board distribution, record changes, portfolio modifications |

Details: [docs/SECURITY.md](docs/SECURITY.md).

## Permission-aware knowledge retrieval

```mermaid
flowchart LR
  F["file"] --> V["validate<br/>allowlist · size · magic bytes<br/>EICAR · macros · zip bombs"] --> P["parse<br/>PDF · DOCX · XLSX · CSV · MD"]
  P --> C["classify<br/>PII ⇒ upgrade"] --> M["metadata + ACL"] --> K["chunk"] --> I{"injection<br/>screen"}
  I -- high --> Q["quarantine"]
  I -- ok --> E["embed → pgvector<br/>+ BM25"]
  QY[/"query"/] --> AF["authorization pre-filter<br/>tenant · groups · clearance · dates"] --> HY["hybrid RRF"] --> PC["policy post-check"] --> RR["rerank"] --> EV["evidence validation"] --> CI["citations"]
  E -.-> HY
```

Retrieved text is rendered as neutralized evidence and never executed as instructions; multilingual queries are expanded
with an approved glossary.

## Financial engine & scenario simulator

<table>
<tr>
<td width="50%"><img src="docs/images/concentration.png" alt="Issuer concentration"></td>
<td width="50%"><img src="docs/images/scenarios.png" alt="Scenario comparison"></td>
</tr>
</table>

* **Money** in integer cents → `Decimal`, quantized once (ROUND_HALF_EVEN); statistics as floats.
* **AUM roll-forward** reconciled to the cent for every product-month; ledger revenue reconciled to product accruals.
* **Returns & risk**: TWR, MWR (IRR), benchmark-relative, Sharpe, volatility, max drawdown, tracking error, beta, HHI, drift.
* **Revenue**: yield, exact volume / mix / fee attribution, fee impact, product contribution (illustrative allocation).
* **Scenarios**: deterministic base / bull / bear / severe stress, sliders, portfolio impacts, tornado sensitivity and full
  assumption traceability — **no probabilities or confidence intervals**.
* **The LLM never computes figures.** Formulas and hand-verified tests: [docs/DATA_AND_ANALYTICS.md](docs/DATA_AND_ANALYTICS.md).

<p align="center"><img src="docs/images/synthetic-data.png" alt="Synthetic dataset volumes" width="80%"></p>

## The eight end-to-end demonstrations

Automated in [`tests/e2e/test_journeys.py`](tests/e2e/test_journeys.py) (API) and
[`frontend/e2e/journeys.spec.ts`](frontend/e2e/journeys.spec.ts) (browser).

| # | Persona | What happens | Proof |
|---|---|---|---|
| 1 | CEO | AUM +3.08% (12m) while margin falls 30.69% → 27.85%; expenses +9.19% vs revenue +4.89%; mix effect −CAD 36.9m | [Ask Flo](docs/screenshots/02-ask-flo.png) |
| 2 | CIO | Northgate Technologies is 4.5% of portfolio assets across 270 portfolios; 230 breach the 10% limit; −25% equity shock simulated | [Risk](docs/screenshots/03c-risk-intelligence.png) · [Scenarios](docs/screenshots/04-scenarios.png) |
| 3 | Wealth advisor | Only assigned clients; four agents build the review and agenda | [Meeting prep](docs/screenshots/05c-meeting-prep.png) |
| 4 | Compliance officer | Approves the exact hash of an AI-drafted letter; edits after approval invalidate it; replays rejected | [Approvals](docs/screenshots/07-approvals.png) |
| 5 | AI administrator | Injected market-data outage → retries, circuit breaker, failing agent identified with the incident cited | [AI Ops](docs/screenshots/08-aiops.png) |
| 6 | Security test | Unassigned, cross-tenant, external and executive access to a client record denied with rule codes, audited | [Audit](docs/screenshots/11-audit-log.png) |
| 7 | Prompt injection | Flagged; a compromised model plan requesting export/e-mail/trade is blocked at the gateway; malicious doc quarantined | [Injection](docs/screenshots/14-prompt-injection.png) |
| 8 | Executive | Delivered / partial / not-delivered decisions, behind-schedule initiatives, overdue commitments, "not causal" caveat | [Decisions](docs/screenshots/10-decision-memory.png) |

## Verification & measured performance

<p align="center"><img src="docs/images/verification.png" alt="Verification summary" width="85%"></p>

| Check | Result |
|---|---|
| Backend tests — unit, financial, security, adversarial, e2e journeys | **128 passed** on SQLite **and** PostgreSQL + Redis |
| OPA policy tests + Python ⇄ OPA parity | 7/7 · parity on ~2,000 decisions |
| Evaluation suite (grounding, citations, retrieval, tool selection, authorization, privacy, injection, multilingual) | 10/10 |
| Release gate (critical tests, OPA, evals, ruff, bandit, pip-audit, secret scan, TypeScript) | **PASS** |
| Playwright browser journeys | 6/6 on the dev stack and on the Docker stack |
| Docker Compose | all services healthy; OPA PDP, pgvector, Redis, Prometheus & Grafana verified |
| Backup / restore drill | identical row counts; audit hash chain valid on the restored copy |
| Helm / Kubernetes / Terraform | `helm lint` + `template` pass; manifests parse; module contracts `terraform validate` — **not applied to a real cluster/account** |

<p align="center"><img src="docs/images/load-tests.png" alt="Measured load tests" width="100%"></p>

Load tests ran on **one 4-vCPU container that also ran the load generator**. At 50 users: 100% success, dashboard p95
50 ms, Ask Flo p95 195 ms. The host saturates at ~55–60 req/s; at 500+ users latency targets are **not met** on one host,
but overload is shed as `503 Retry-After` — no 500s, no crashes. Horizontal scaling was not measured.
Raw data and methodology: [docs/OPERATIONS.md](docs/OPERATIONS.md).

## Quick start

<details open>
<summary><b>Docker — full stack</b></summary>

```bash
cd flo-enterprise
docker compose --profile observability up -d --build
# UI http://localhost:8080 · API docs http://localhost:8000/docs · Grafana http://localhost:3000 · Prometheus http://localhost:9090
```
Behind a TLS-intercepting corporate proxy, pass its CA as a build secret (TLS verification stays on):
`FLO_EXTRA_CA_FILE=/path/to/corp-ca.pem docker compose build`
</details>

<details>
<summary><b>Local development — SQLite, no services</b></summary>

```bash
make setup     # venv + npm ci
make seed      # migrations + synthetic data + document ingestion
make api       # http://localhost:8000
make ui        # http://localhost:5173 (proxies /api)
```
</details>

<details>
<summary><b>Quality commands</b></summary>

```bash
make test           # pytest
make critical       # release-blocking security + financial tests
make evals          # evaluation suite → var/eval_report.json
make release-gate   # everything; exits non-zero on any blocking failure
make e2e            # Playwright against a running stack
make load-test USERS=50
python scripts/make_readme_charts.py                   # regenerate README charts
cd frontend && FLO_GALLERY=1 npx playwright test gallery  # regenerate README screenshots
```
</details>

<p align="center"><img src="docs/screenshots/00-login.png" alt="Sign in as a synthetic user" width="80%"><br>
<sub>Sign in as any synthetic user (mock identity provider): CEO, CFO, CIO, analyst, wealth advisors, external advisor,
compliance, privacy, AI administrator, and an advisor in a second tenant.</sub></p>

## Repository layout

```text
flo-enterprise/
├── frontend/        React + TypeScript UI, Playwright journeys & screenshot gallery
├── backend/         FastAPI app, routers, DB models, Alembic migrations, seed, worker
├── agents/          LangGraph graphs, 20 specialist agents, tool catalog, approved comms templates
├── harness/         agent runtime, tool gateway, budgets, resilience, model adapters, grounding
├── governance/      identity, policy engine, OPA adapter, resources, hash-chained audit
├── privacy/         detection, masking, tokenization, encrypted vault
├── analytics/       Decimal financial engine, semantic layer, wealth, decisions, data quality
├── scenarios/       strategy-twin scenario engine
├── retrieval/       ingestion, validation, parsing, embeddings, pgvector, hybrid search
├── approvals/       durable approval service
├── integrations/    provider-neutral interfaces + mock synthetic adapters
├── observability/   telemetry (local / LangSmith) and Prometheus metrics
├── data/            synthetic generator, documents, glossary, data-product catalog
├── policies/        RBAC, ABAC, approvals, providers, suitability, retention + OPA/Rego
├── infrastructure/  k8s, Helm, Terraform, Prometheus & Grafana provisioning
├── tests/           unit · security · e2e · evals · load
├── scripts/         release gate, backup/restore drill, README chart generator
├── docs/            architecture, product, security, agents, operations, screenshots, charts, evidence
└── docker-compose.yml · Makefile · .env.example
```

## Documentation

| Document | Covers |
|---|---|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | current-state assessment, integration discovery matrix, C4/dependency/data-flow diagrams, target architecture, deployment, integrations |
| [PRODUCT.md](docs/PRODUCT.md) | business domains & KPIs, UX & visual analytics, multilingual, decision memory |
| [DATA_AND_ANALYTICS.md](docs/DATA_AND_ANALYTICS.md) | synthetic data, data products, semantic layer, financial methodology, scenarios |
| [SECURITY.md](docs/SECURITY.md) | governance plane, OPA, approvals, privacy |
| [AGENTS.md](docs/AGENTS.md) | orchestration, agent table, harness, RAG, LLM observability |
| [REGULATORY.md](docs/REGULATORY.md) | regulatory research workspace (illustrative, not legal advice) |
| [OPERATIONS.md](docs/OPERATIONS.md) | NFRs, measured load tests, cost & capacity, DR, evaluation |
| [PROGRESS.md](docs/PROGRESS.md) | phases and definition-of-done evidence |

## Limitations

* Synthetic data and mock adapters only; nothing connects to a production system. Figures are illustrative.
* The default model is deterministic templating, not an LLM: narratives are accurate but formulaic; free-text answers are
  English with localized headings (approved client templates are fully localized). The Bedrock adapter is implemented
  but untested (no credentials). LangSmith runs in **local-fallback** mode without an API key.
* Name detection uses a CRM gazetteer and honorific patterns; Presidio is optional. The embedder is a deterministic
  hashing model (below neural quality).
* Mock IdP (HS256 tokens in `sessionStorage`); production must use the enterprise OIDC IdP.
* Approval checkpoints use SQLite; breakers, agent cache and cancellation handles are per process — multi-replica
  deployments need shared equivalents.
* Load results come from a single shared host and are not production SLAs; horizontal scaling is untested.
* Regulatory references are illustrative; the AI makes no legal or regulatory determinations.
* Not implemented: dedicated Sankey chart, real AV engine, regional DR failover drill.
