<div align="center">

<img src="frontend/public/brand/ff-mark.svg" width="96" alt="Flying_Florina mark" />

# Flying_Florina

### From legacy systems to trusted industrial intelligence.
**Ask. Analyze. Modernize. Govern. Act — with approval.**

An aerospace & defense **Industrial AI Transformation Command Center** that runs fully offline:
natural-language questions → deterministic routing → multi-agent workflows → cited evidence and live dashboards →
**policy-gated, human-approved actions**.

![Synthetic data](https://img.shields.io/badge/data-100%25%20synthetic-D7B46A)
![Offline](https://img.shields.io/badge/runtime-offline-0B1230)
![Paid APIs](https://img.shields.io/badge/paid%20APIs-%240-0F8B8D)
![Backend tests](https://img.shields.io/badge/pytest-102%20passed-0F8B8D)
![E2E](https://img.shields.io/badge/playwright-13%20passed-0F8B8D)
![Security lab](https://img.shields.io/badge/security%20lab-12%2F12-5C35B7)
![License](https://img.shields.io/badge/license-GPL--3.0-A78BFA)

> **Independent concept demo | Not affiliated with or endorsed by IFS.**
> All data is synthetic and fictional. There is no live IFS (or any other) connection. Nothing here is a
> certification, an airworthiness determination, or a promise of savings.

<img src="docs/screenshots/01_mission_control.png" width="900" alt="Mission Control: centered chat with sample questions" />

</div>

---

## Contents

1. [At a glance](#at-a-glance)
2. [System architecture](#system-architecture)
3. [Trust chain and security boundaries](#trust-chain-and-security-boundaries)
4. [Agent workflows](#agent-workflows)
5. [Governance flows](#governance-flows)
6. [Legacy X-Ray and Bridge pipeline](#legacy-x-ray-and-bridge-pipeline)
7. [Data model](#data-model)
8. [Screenshot tour](#screenshot-tour)
9. [Quick start](#quick-start)
10. [Interview demo](#interview-demo)
11. [Tests and quality gates](#tests-and-quality-gates)
12. [Repository layout](#repository-layout)
13. [Honest limits](#honest-limits)
14. [Documentation index](#documentation-index)

---

## At a glance

| Area | What you can do | Proof |
|---|---|---|
| 🧭 **Mission Control** | Ask any of the 10 sample questions (or your own), watch the real execution log, keep the conversation going, replay sessions | `e2e/core.spec.ts` |
| ✈️ **AC-204 investigation** | Telemetry stats, access-filtered retrieval, maintenance history, hypotheses, verified parts, qualified technicians, compliance checklist, dry-run draft, approval gate | `tests/test_workflows.py` |
| 🔬 **Legacy X-Ray** | Parse SQL DDL, OpenAPI, CSV feeds, OData XML, event schemas and ZIP bundles **without executing anything**; dependency map, findings, unknowns, 8 recommendations, 30/60/90 roadmap | `tests/test_api.py` |
| 🔌 **API & MCP Bridge Studio** | Generate a **runnable** read-only FastAPI adapter + MCP server (official SDK) + tests, run them in a sandbox (14/14 pass), download the bundle | `generated_adapters/example_part_availability` |
| 🛡️ **Defense Trust Center** | 13 deterministic policies, decision traces, kill switch, approval queue, hash-chained audit log, 12-scenario Security Test Lab | `tests/test_policy.py` |
| 🚫 **Exfiltration demo** | "Export restricted maintenance records to my personal email" → **DENY (POL-004) before the tool runs**, 0 executions | `test_export_request_denied_before_tool_and_zero_invocations` |
| 📈 **Simulation & ROI** | Deterministic delay scenarios, seeded Monte Carlo, sensitivity, editable ROI ranges | `tests/test_approvals_sim.py` |
| 📄 **Reports** | PDF, HTML, Markdown, CSV, JSON; workspace exports; audit packet; SHA-256 recorded | `test_reports_generate_and_download` |
| 📴 **Offline** | No internet, no LLM, no accounts; a process-level egress guard blocks non-loopback traffic | `scripts/offline_check.py` |

---

## System architecture

```mermaid
flowchart LR
  subgraph Browser["Browser (React + TypeScript + Vite)"]
    UI["Mission Control<br/>+ 15 domain pages"]
  end

  subgraph API["FastAPI backend (local)"]
    MW["Middleware<br/>request id · security headers · CORS"]
    AUTH["Demo identity<br/>HMAC token · audience · expiry"]
    IR["Intake & Intent Agent<br/>deterministic router"]
    WE["Workflow engine<br/>DAG · parallel waves · retries<br/>timeouts · cancel · checkpoints"]
    AG["Specialist agents"]
    GW["Tool gateway"]
    PE{{"Policy engine<br/>deny-by-default"}}
    RET["Retrieval<br/>label filter → FTS5/BM25 → TF-IDF"]
    APR["Approvals<br/>SoD · expiry · idempotency"]
    LX["Legacy X-Ray parsers"]
    BR["Bridge generator"]
    SIM["Simulation & ROI"]
    REP["Reports<br/>PDF · HTML · MD · CSV · JSON"]
  end

  subgraph Local["Local resources"]
    DB[("SQLite<br/>synthetic data · seed 20261024")]
    AUD[("Hash-chained<br/>audit log")]
    MCPS["Demo MCP server<br/>(stdio)"]
    BUNDLE["Generated adapter<br/>+ MCP tool + tests"]
  end

  UI -->|"JSON envelope"| MW --> AUTH --> IR --> WE --> AG
  AG --> GW --> PE
  PE -->|ALLOW| DB
  PE -->|DENY| AUD
  AG --> RET --> DB
  WE --> SIM
  WE --> REP
  API --> APR --> PE
  API --> LX
  API --> BR --> BUNDLE
  API -->|"stdio client"| MCPS --> PE
  PE --> AUD
```

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript (strict), Vite 6, Tailwind 4, TanStack Query, Zustand, Apache ECharts, React Flow, Lucide |
| Backend | Python 3.11+, FastAPI, Pydantic v2, SQLite (+ FTS5), ReportLab, official MCP Python SDK |
| Agents | Explicit typed state machine (LangGraph-compatible semantics); no hosted LLM |
| Tests | pytest, ruff (incl. security rules), Vitest, Testing Library, Playwright |

---

## Trust chain and security boundaries

```mermaid
flowchart LR
  A["Intent<br/>(rules; optional local LLM<br/>never decides)"] --> B["Workflow<br/>engine"]
  B --> C["Tool registry<br/>name+version+schema SHA-256 pinned"]
  C --> D{"Policy gateway<br/>per invocation"}
  D -->|ALLOW| E["MCP server<br/>(agent interface)"]
  D -->|DENY| X["Not executed<br/>decision + audit"]
  E --> F["Typed read-only<br/>API adapter"]
  F --> G["Authorized system endpoint<br/>(synthetic)"]
  style D fill:#5C35B7,color:#fff
  style X fill:#C53030,color:#fff
```

Policy evaluation order (first failure decides; every check is recorded):

```mermaid
flowchart TB
  S([Request]) --> P12{"POL-012<br/>identity?"}
  P12 -->|no| DENY([DENY])
  P12 --> P09{"POL-009<br/>kill switch off?"}
  P09 -->|no| DENY
  P09 --> P11{"POL-011<br/>from user, not<br/>retrieved text?"}
  P11 -->|no| DENY
  P11 --> P07{"POL-007<br/>no self-escalation?"}
  P07 -->|no| DENY
  P07 --> P06{"POL-006<br/>tool pinned?"}
  P06 -->|no| DENY
  P06 --> P08{"POL-008<br/>model is local?"}
  P08 -->|no| DENY
  P08 --> P04{"POL-004<br/>destination internal?"}
  P04 -->|no| DENY
  P04 --> P02{"POL-001/002<br/>role grants action?"}
  P02 -->|no| DENY
  P02 --> P03{"POL-003<br/>label & attributes?"}
  P03 -->|no| DENY
  P03 --> P10{"POL-010<br/>authoritative evidence?"}
  P10 -->|no| DENY
  P10 --> P13{"POL-013<br/>separation of duties?"}
  P13 -->|no| DENY
  P13 --> P05{"POL-005<br/>approved, unexpired,<br/>not replayed write?"}
  P05 -->|no| DENY
  P05 --> ALLOW([ALLOW])
  style DENY fill:#C53030,color:#fff
  style ALLOW fill:#0F8B8D,color:#fff
```

| Boundary | Control |
|---|---|
| Browser → API | Signed token in the `Authorization` header (no cookies, so no CSRF), strict CORS, security headers, validation, upload limits |
| Agent → tool | Agent rights = its own grants ∩ the requesting human's; schema validation, rate limit, circuit breaker, timeout, redacted logs |
| Retrieved text → agent | Classification filter **in SQL before ranking**; instruction-like text quarantined; actions it requests are denied (POL-011) |
| Uploads | Extension allowlist, size limit, binary rejection, ZIP traversal/symlink/bomb checks, XML DTD rejection, parse-only |
| Generated code | Vetted templates, static checks, tests only on explicit request in a subprocess with a minimal environment and a timeout |
| Process → network | `OFFLINE_MODE` egress guard blocks non-loopback sockets and DNS |

---

## Agent workflows

### Graph 1: maintenance investigation (AC-204)

```mermaid
flowchart LR
  I["intake<br/>Intake & Intent"] --> P["policy_precheck<br/>Security & Governance"]
  P --> T["telemetry<br/>Asset Telemetry"]
  P --> R["retrieval<br/>Knowledge Retrieval"]
  P --> H["history<br/>Diagnostic Evidence"]
  T --> D["diagnostics<br/>hypotheses only"]
  R --> D
  H --> D
  D --> PA["parts<br/>verified stock · approved alternates"]
  D --> SC["scheduling<br/>qualified techs · hangar slots"]
  PA --> C["compliance<br/>evidence checklist"]
  SC --> C
  C --> DR["draft_plan<br/>dry-run work order"]
  DR --> AP{{"approval_gate<br/>human, different persona"}}
  AP -.->|approve + execute| W["simulated write<br/>idempotent, audited"]
  style AP fill:#D7B46A,color:#0B1230
```

### Graph 2: legacy modernization · Graph 3: governance

```mermaid
flowchart LR
  subgraph G2["Graph 2 — Legacy"]
    a1[precheck] --> a2[metadata import] --> a3[dependency graph] --> a4[risk classification]
    a4 --> a5[integration options] --> a6[target architecture] --> a7[adapter generation]
    a7 --> a8[static contract tests] --> a9[security review]
  end
  subgraph G3["Graph 3 — Governance"]
    b1[identity + policy evaluation] -->|DENY| b2[no tool execution] --> b3[audit] --> b4[response]
    b1 -->|ALLOW| b5[permitted tool only] --> b3
  end
```

| Agent | Responsibility | Tools (pinned) |
|---|---|---|
| Intake & Intent | Deterministic routing, entity extraction, clarification | — |
| Supervisor | DAG waves, retries, cancellation, checkpoints | — |
| Asset Telemetry | Baselines, z-scores, outliers, data-quality gaps | `telemetry.get_series` |
| Knowledge Retrieval | Access-filtered hybrid search, injection quarantine | `docs.search` |
| Diagnostic Evidence | Hypotheses with supporting/contradicting evidence | `maintenance.get_history` |
| Parts | Reconciled inventory, authority-backed alternates | `parts.check_availability` |
| Maintenance Planner | Unexpired qualifications, slots, dry-run drafts | `roster.find_qualified`, `hangar.find_slots`, `workorder.create_draft` |
| Compliance | Evidence sufficiency (never certification) | `docs.search` |
| Legacy Discovery / Integration Architect | Metadata parsing, options, adapter generation | — |
| Scenario Simulator | Deterministic scenarios, seeded Monte Carlo, ROI | — |
| Security & Governance | Explains decisions; never overrides them | — |
| Reporting | Workspace blocks, citations, exports | — |

The agent graph and timeline in the UI are drawn from persisted execution events with real timestamps; nothing is animated or invented.

---

## Governance flows

### Exfiltration attempt: denied before execution

```mermaid
sequenceDiagram
  autonumber
  actor U as Planner
  participant UI as Mission Control
  participant IR as Intent router
  participant SG as Security & Governance agent
  participant PE as Policy engine
  participant T as records.export_email
  participant A as Audit chain
  U->>UI: "Export restricted maintenance records to my personal email."
  UI->>IR: POST /api/chat/query
  IR->>SG: route = data_export (matched first, cannot be outscored)
  SG->>PE: evaluate(export, RESTRICTED, personal_email)
  PE-->>SG: DENY · POL-004
  PE->>A: decision + hash-linked event
  Note over T: never invoked (execution count stays 0)
  SG-->>UI: DENIED · policy trace · identity · classification · 0 executions
```

### Approval lifecycle

```mermaid
stateDiagram-v2
  [*] --> pending: draft created by planner<br/>payload SHA-256 stored
  pending --> pending: requester tries to approve<br/>DENY POL-013
  pending --> approved: different approver role<br/>evidence hash recorded
  pending --> rejected: approver rejects
  pending --> expired: TTL elapsed
  approved --> executed: execute with idempotency key<br/>policy re-checked (POL-005)
  executed --> executed: replay attempt<br/>DENY POL-005
  rejected --> [*]
  expired --> [*]
  executed --> [*]
```

### Hash-chained audit log

```mermaid
flowchart LR
  G["genesis<br/>000…0"] --> E1["event 1<br/>hash = SHA-256(fields + prev)"]
  E1 --> E2["event 2<br/>prev = hash(1)"]
  E2 --> E3["event 3<br/>prev = hash(2)"]
  E3 --> V{"verify"}
  V -->|"any edit or deletion"| BROKEN(["broken_at = event id"])
  V -->|"intact"| OK(["valid · head hash"])
  style BROKEN fill:#C53030,color:#fff
  style OK fill:#0F8B8D,color:#fff
```

Tamper-evident, not tamper-proof: a host administrator could rewrite the file and recompute the chain.

---

## Legacy X-Ray and Bridge pipeline

```mermaid
flowchart LR
  subgraph In["Inputs (parsed, never executed)"]
    s1[SQL DDL]
    s2[OpenAPI JSON/YAML]
    s3[Nightly CSV]
    s4[OData XML]
    s5[Event schema]
    s6[ZIP: .py AST / .java metadata]
  end
  In --> SAFE["Safety gate<br/>size · extension · binary · ZIP traversal/bomb · XXE"]
  SAFE --> X["Landscape<br/>systems · tables · APIs · edges"]
  X --> F["Findings<br/>/admin/sql · SSRF · missing PKs · stale counts"]
  X --> U["Unknowns U1–U5<br/>(asked, not assumed)"]
  F --> REC["8 recommendations<br/>strangler · ACL · read-only view · CDC<br/>batch bridge · RAG · documented ERP APIs · MCP facade"]
  REC --> RM["30/60/90 roadmap"]
  REC --> GEN["Bridge generator"]
  GEN --> B1["FastAPI adapter + Pydantic models"]
  GEN --> B2["MCP server (official SDK)"]
  GEN --> B3["contract · security · MCP tests"]
  GEN --> B4["OpenAPI · threat model · README"]
  B3 --> RUN{{"sandboxed pytest<br/>14/14 pass"}}
  style RUN fill:#0F8B8D,color:#fff
```

Canonical mapping used by the generated `get_part_availability(part_number)` adapter:

| Legacy column (`V_PART_AVAILABILITY`) | Canonical field | Rule |
|---|---|---|
| `PART_NO` | `part_number` | validated `^P-[0-9A-Z]{3,8}$` |
| `PART_DESC` | `description` | — |
| `BASE_CODE` | `location` | — |
| `QTY_OH` | `quantity_on_hand` | non-negative |
| `LOT_NO` | `lot` | `UNKNOWN` ⇒ not traceable |
| `LAST_CNT_DT` | `last_counted` | critical part counted > 30 days ago ⇒ unverified |

---

## Data model

```mermaid
erDiagram
  AIRCRAFT ||--o{ SENSOR_READINGS : "548 days"
  AIRCRAFT ||--o{ MAINTENANCE_EVENTS : has
  AIRCRAFT ||--o{ WORK_ORDERS : has
  PARTS ||--o{ INVENTORY : "per system of record"
  PARTS }o--|| SUPPLIERS : "sourced from"
  SUPPLIERS ||--o{ SUPPLIER_DELIVERIES : "reliability computed"
  WORK_ORDERS }o--o| TECHNICIANS : assigned
  DOCUMENTS ||--|| DOCUMENTS_FTS : indexed
  WORKFLOW_RUNS ||--o{ WORKFLOW_EVENTS : logs
  WORKFLOW_RUNS ||--o{ POLICY_DECISIONS : produces
  POLICY_DECISIONS ||--o{ TOOL_INVOCATIONS : "allow only"
  APPROVALS ||--o| WRITE_LOG : "idempotency key"
  AUDIT_EVENTS ||--|| AUDIT_EVENTS : "prev_hash"
```

| Synthetic dataset (seed `20261024`) | Rows |
|---|---|
| Aircraft (fictional IDs, e.g. AC-204) | 150 |
| Daily sensor readings (18 months) | 82,200 |
| Maintenance events / work orders | ~2,400 each |
| Parts / inventory records / supplier deliveries | 60 / ~130 / 720 |
| Technicians / hangar slots | 40 / 60 |
| Technical documents (fictional, versioned, classified) | 28 |
| Enterprise applications / incidents | 12 / 8 |

Seeded incidents include the AC-204 vibration anomaly, a supplier lead-time slip, an ERP-vs-CSV inventory mismatch, a superseded revision, a missing approval, an unauthorized export, a duplicate work order, and an integration timeout.

---

## Screenshot tour

All screenshots come from the running app on the build machine, using synthetic data.

### 1 · Mission Control and the operational AI workflow

| Ask Flying_Florina | Export request denied (POL-004, 0 tool executions) |
|---|---|
| <img src="docs/screenshots/01_mission_control.png" alt="Mission Control" /> | <img src="docs/screenshots/03_export_denied.png" alt="Export denied" /> |

<details>
<summary><b>AC-204 investigation, full workspace</b> (timeline, vibration chart, hypotheses, parts reconciliation, recovery options, technicians, compliance checklist, citations, decision trace, approval gate). Click to expand.</summary>

<img src="docs/screenshots/02_ac204_investigation.png" alt="AC-204 investigation workspace" />
</details>

### 2 · Operations

| Fleet & Asset Health | AOG Recovery |
|---|---|
| <img src="docs/screenshots/04_fleet.png" alt="Fleet" /> | <img src="docs/screenshots/05_aog.png" alt="AOG" /> |

| Maintenance & MRO | Parts & Supply Chain |
|---|---|
| <img src="docs/screenshots/06_maintenance.png" alt="Maintenance" /> | <img src="docs/screenshots/07_parts.png" alt="Parts" /> |

| Engineering Quality | Scenario Simulator |
|---|---|
| <img src="docs/screenshots/08_quality.png" alt="Quality" /> | <img src="docs/screenshots/14_simulator.png" alt="Simulator" /> |

### 3 · Modernization

| Legacy X-Ray: dependency map | API & MCP Bridge Studio |
|---|---|
| <img src="docs/screenshots/09_legacy.png" alt="Legacy X-Ray" /> | <img src="docs/screenshots/10_bridge.png" alt="Bridge Studio" /> |

<details>
<summary><b>Generated adapter preview and sandboxed test results</b>. Click to expand.</summary>

<img src="docs/screenshots/18_legacy_bridge_tests.png" alt="Generated adapter tests passing" />
</details>

### 4 · Trust and governance

| Defense Trust Center | Security Test Lab: 12/12 |
|---|---|
| <img src="docs/screenshots/12_trust.png" alt="Trust Center" /> | <img src="docs/screenshots/12_trust_security_lab.png" alt="Security Test Lab" /> |

| Agent Mission Control | Compliance Evidence |
|---|---|
| <img src="docs/screenshots/11_agents.png" alt="Agents" /> | <img src="docs/screenshots/13_compliance.png" alt="Compliance" /> |

### 5 · Value, reports and settings

<details>
<summary><b>Executive Value Studio: 90-day pitch with roadmap, risks and editable ROI</b>. Click to expand.</summary>

<img src="docs/screenshots/15_executive.png" alt="Executive Value Studio" />
</details>

| Reports & Exports | Integrations & Settings |
|---|---|
| <img src="docs/screenshots/16_reports.png" alt="Reports" /> | <img src="docs/screenshots/17_settings.png" alt="Settings" /> |

---

## Quick start

Requires Python 3.11+ and Node 20+. Setup needs network **once** to fetch packages; after that everything runs offline.

```mermaid
flowchart LR
  A["scripts/setup.sh<br/>venv · deps · seed DB · npm install"] --> B["make demo<br/>API :8000 + UI :5173"]
  B --> C["open http://127.0.0.1:5173<br/>no credentials · no API keys"]
  C --> D["make test · make test-e2e · make offline"]
```

**macOS / Linux**
```bash
cd flying-florina
sh scripts/setup.sh
make demo            # backend :8000 + UI :5173
```
Without Make:
```bash
cd flying-florina/backend  && .venv/bin/uvicorn app.main:app --reload --port 8000
cd flying-florina/frontend && npm run dev
```

**Windows PowerShell**
```powershell
cd flying-florina
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
cd backend;  .\.venv\Scripts\uvicorn app.main:app --reload --port 8000
# second terminal
cd frontend; npm run dev
```

The UI signs you in as a synthetic persona automatically. You can switch personas in the top bar: Executive, Maintenance Planner, Technician, Reliability Engineer, Enterprise Architect, Security Officer, Auditor, Forward Deployed Engineer, Guest, and an external supplier. The backend enforces permissions; the UI only adapts.

---

## Interview demo

```mermaid
timeline
  title Six-minute offline demo
  Act 1 (2 min) : Legacy X-Ray : import MRO schema + nightly CSV : dependency map, hotspots, unknowns : generate read-only bridge, run 14 tests
  Act 2 (2 min) : AC-204 question : agent graph, citations, charts : pending approval : change lead time and recompute scenarios
  Act 3 (1 min) : export request : DENY POL-004, 0 executions : approve as another persona : replay denied POL-005
  Act 4 (1 min) : 90-day pitch : roadmap, risks, ROI ranges : download PDF brief
```

Full 3-minute and 8-minute scripts are in [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md).

---

## Tests and quality gates

| Command | What it covers | Result |
|---|---|---|
| `make test-backend` | routing, policies, export blocking, retrieval filtering, citations, approvals, replay, audit chain, workflows, failure injection, cancel, simulation determinism, upload safety, bridge generation **and execution**, MCP stdio | **102 passed** |
| `npm test` (Vitest) | XSS-safe markdown, chart mapping, table sorting, workspace rendering | **9 passed** |
| `make test-e2e` (Playwright) | fresh start, personas, all 10 prompts, charts, agent graph, legacy upload, adapter tests, denial, approvals, PDF download, guest denials, offline interception, mobile | **13 passed** |
| `make offline` | every workflow + reports with the egress guard on, no LLM | **0 egress attempts** |
| Generated bundle `pytest` | contract 6 · security 6 · MCP stdio 2 | **14 passed** |
| `make lint` / `npm run typecheck` / `npm run build` | ruff (incl. bandit rules), strict TS, production build | clean |

Measured latency on a 4-CPU container, rules only, no LLM: **58 ms** (export denial) to **~970 ms** (downtime analysis with bootstrap CIs); the AC-204 investigation takes about **250 ms**. See [`docs/latency_measured.json`](docs/latency_measured.json) and [`docs/TEST_REPORT.md`](docs/TEST_REPORT.md).

---

## Repository layout

```
flying-florina/
├── backend/app/
│   ├── core/            config · security · policy · audit · egress · db
│   ├── agents/          maintenance + analytics agents
│   ├── workflows/       intent router · DAG engine · graphs · workspace composer
│   ├── retrieval/       access-aware FTS5/TF-IDF search
│   ├── integrations/    legacy/ (parsers, X-Ray) · mcp/ (registry, bridge, client)
│   ├── simulation/      delay scenarios · ROI
│   ├── reports/         PDF/HTML/MD/CSV/JSON
│   ├── seed/            deterministic synthetic data
│   └── api/             REST endpoints with envelope + typed errors
├── backend/tests/       pytest suite
├── frontend/src/        components/ · features/<15 pages> · lib/
├── frontend/e2e/        Playwright suite
├── mcp_servers/demo_maintenance/          local stdio MCP server
├── generated_adapters/example_part_availability/   runnable generated bundle
├── fixtures/            documents · legacy schemas · OpenAPI · OData · CSV · policies · tool pins
├── docs/                architecture · threat model · guides · scripts · screenshots
└── scripts/             setup · seed · smoke · offline check · latency · pin tools
```

---

## Honest limits

| ✅ Real | 🟡 Simulated / demo-grade | ⛔ Not built |
|---|---|---|
| Policy engine, approvals, audit chain, retrieval filtering, workflows, parsers, generated adapter + MCP, reports, offline guard | Persona login (no IdP/MFA), approved writes (demo DB only), ERP data (fictional "IFS-like" fixtures), prompt-injection patterns, process-level egress guard, subprocess test sandbox | Live IFS connection, PostgreSQL/Alembic, OPA, embeddings, local-LLM rephrasing (detection only), 3D views, connector gallery |

**Cost:** no paid APIs, hosted inference, cloud services or accounts are used, so incremental software spend is **$0**. You provide the hardware and electricity. Claude Code, which was used to build this, may need its own subscription.

**Brand assets:** the authorized portrait and logo files named in the spec were not available, so the UI uses a neutral placeholder mark rather than an invented likeness. To use your own assets, see [`frontend/public/brand/README.md`](frontend/public/brand/README.md).

Read [`docs/SECURITY_LIMITATIONS.md`](docs/SECURITY_LIMITATIONS.md) before presenting to a security team, and [`docs/GAP_MATRIX.md`](docs/GAP_MATRIX.md) for the full status list.

---

## Documentation index

| Topic | Document |
|---|---|
| Architecture and trust boundaries | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Plan, environment inventory, task board | [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) |
| What is real / simulated / missing | [docs/GAP_MATRIX.md](docs/GAP_MATRIX.md) |
| Threat model | [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) |
| Security limitations | [docs/SECURITY_LIMITATIONS.md](docs/SECURITY_LIMITATIONS.md) |
| Compliance mapping (informational) | [docs/COMPLIANCE_MAPPING.md](docs/COMPLIANCE_MAPPING.md) |
| API and MCP guide | [docs/API_MCP_GUIDE.md](docs/API_MCP_GUIDE.md) |
| ROI method | [docs/ROI_METHOD.md](docs/ROI_METHOD.md) |
| Deployment and offline install | [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) |
| Demo scripts (3 and 8 min) | [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md) |
| One-page pilot brief | [docs/ONE_PAGE_BRIEF.md](docs/ONE_PAGE_BRIEF.md) |
| Test report | [docs/TEST_REPORT.md](docs/TEST_REPORT.md) |
| Third-party notices | [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) |

<div align="center">
<sub>License: GNU GPL v3 (same as the repository root) · Independent concept demo | Not affiliated with or endorsed by IFS</sub>
</div>
