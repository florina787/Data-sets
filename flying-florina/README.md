<div align="center">

<img src="docs/assets/banner.svg" width="100%" alt="Flying_Florina — From legacy systems to trusted industrial intelligence" />

<br/>

![Synthetic data](https://img.shields.io/badge/data-100%25%20synthetic-D7B46A?style=for-the-badge)
![Offline](https://img.shields.io/badge/runtime-offline-0B1230?style=for-the-badge)
![Paid APIs](https://img.shields.io/badge/paid%20APIs-%240-0F8B8D?style=for-the-badge)
![Policy](https://img.shields.io/badge/policy-deny%20by%20default-5C35B7?style=for-the-badge)

![pytest](https://img.shields.io/badge/pytest-102%20passed-0F8B8D)
![playwright](https://img.shields.io/badge/playwright-13%20passed-0F8B8D)
![vitest](https://img.shields.io/badge/vitest-9%20passed-0F8B8D)
![generated adapter](https://img.shields.io/badge/generated%20adapter-14%2F14-0F8B8D)
![security lab](https://img.shields.io/badge/security%20lab-12%2F12-5C35B7)
![egress](https://img.shields.io/badge/offline%20egress%20attempts-0-0B1230)
![license](https://img.shields.io/badge/license-GPL--3.0-A78BFA)

### Ask. Analyze. Modernize. Govern. Act — with approval.

An aerospace & defense **Industrial AI Transformation Command Center**. You ask a question in plain language;
Flying_Florina routes it to a workflow, runs local agents, retrieves cited evidence, renders live dashboards,
and **gates every consequential action behind deterministic policy and human approval**. All of it runs offline, on one machine.

<sub><b>Independent concept demo | Not affiliated with or endorsed by IFS.</b> All data is synthetic and fictional. No live IFS connection,
no certification, no airworthiness determinations, no promised savings.</sub>

<br/><br/>

<img src="docs/screenshots/01_mission_control.png" width="49%" alt="Mission Control, light theme" />
<img src="docs/screenshots/highlights/dark_mission_control.png" width="49%" alt="Mission Control, dark theme" />

<sub>Mission Control in light and dark themes: one prompt, ten working sample questions, live session history.</sub>

</div>

---

<div align="center">

**[Architecture](#-architecture)** ·
**[See it in action](#-see-it-in-action)** ·
**[Every screen](#-every-screen)** ·
**[Diagrams](#-how-it-works)** ·
**[Quick start](#-quick-start)** ·
**[Demo script](#-interview-demo)** ·
**[Tests](#-tests-and-quality-gates)** ·
**[Limits](#-honest-limits)** ·
**[Docs](#-documentation)**

</div>

---

## ✨ Highlights

<table>
<tr>
<td width="33%" valign="top">

### 🧭 Ask anything
Ten sample questions, all functional. Each answer is a **workspace**: answer, KPIs, charts, tables, citations, warnings, assumptions, decision trace, approvals and exports. Follow-ups keep building the conversation.

</td>
<td width="33%" valign="top">

### 🤖 Real agents, real log
Thirteen typed agents run as a DAG with parallel waves, retries, timeouts, cancellation and checkpoints. The timeline and agent graph show **persisted events with real timestamps**; nothing is animated or invented.

</td>
<td width="33%" valign="top">

### 🛡️ Trust you can test
Thirteen deterministic policies, deny-by-default. The export of restricted records is **denied before the tool runs**: 0 executions. Separation of duties, a replay-proof write path, a kill switch, a hash-chained audit log, and a 12-scenario Security Lab.

</td>
</tr>
<tr>
<td valign="top">

### 🔬 Legacy X-Ray
Import SQL DDL, OpenAPI, CSV, OData XML, event schemas and ZIP source bundles. They are **parsed, never executed**. You get a dependency map, hotspots, findings, explicit unknowns, eight evidence-backed patterns and a 30/60/90 roadmap.

</td>
<td valign="top">

### 🔌 Bridges that run
Generate a read-only FastAPI adapter, an MCP server (official SDK) and their tests from legacy metadata. Run the tests in a sandbox (**14/14 pass**) and download the bundle.

</td>
<td valign="top">

### 📈 Value with receipts
Deterministic scenarios, seeded Monte Carlo, sensitivity, and an editable ROI range. Every number comes with its formula and assumptions. Export to PDF, HTML, Markdown, CSV and JSON.

</td>
</tr>
</table>

---

## 🏛 Architecture

<div align="center">
<img src="docs/assets/architecture.svg" width="100%" alt="Flying_Florina layered architecture" />
</div>

| Layer | What lives there | Key technology |
|---|---|---|
| **1 · Experience** | Mission Control chat, agent graph, 15 domain pages, light/dark, responsive | React 18 · TypeScript · Vite · Tailwind · ECharts · React Flow · TanStack Query |
| **2 · API** | Identity, validation, response envelope, typed errors, security headers, 61 OpenAPI paths | FastAPI · Pydantic v2 |
| **3 · Orchestration** | Deterministic intent router, DAG workflow engine, 13 specialist agents | Explicit typed state machine (LangGraph-compatible semantics) |
| **4 · Trust** | Tool gateway, policy engine, approvals, audit chain, kill switch, injection guard | Policy-as-code in Python, SHA-256 hash chain |
| **5 · Capabilities** | Access-aware retrieval, simulation & ROI, Legacy X-Ray, bridge generator, reports | SQLite FTS5/BM25 + TF-IDF · ReportLab |
| **6 · Data & integration** | Synthetic SQLite, fixtures, demo MCP server, generated adapters; IFS/ERP **not connected** | SQLite · official MCP Python SDK (stdio) |

---

## 🎬 See it in action

### Act 1: Operational AI on the AC-204 vibration anomaly

> *"Investigate AC-204 vibration anomaly, check maintenance evidence, parts and available technicians, and draft recovery options."*

<div align="center">
<img src="docs/screenshots/highlights/agent_graph_timeline.png" width="90%" alt="Agent graph and real execution timeline" />
<br/><sub><b>Agent graph + execution log.</b> Telemetry, retrieval and history run in parallel; every row is a persisted event with its own timestamp, duration and tools.</sub>
</div>

<br/>

<img src="docs/screenshots/highlights/ac204_answer.png" width="49%" alt="Investigation summary" />
<img src="docs/screenshots/highlights/ac204_vibration_chart.png" width="49%" alt="Vibration chart vs fleet mean" />

<sub><b>Left:</b> the summary: 7-day vibration mean vs its own baseline, hypotheses (not a diagnosis), the fastest compliant recovery, and the pending approval. <b>Right:</b> AC-204 vs the fleet mean, with the fictional demo threshold and a data-quality gap visible.</sub>

<img src="docs/screenshots/highlights/ac204_hypotheses.png" width="49%" alt="Diagnostic hypotheses" />
<img src="docs/screenshots/highlights/ac204_parts_reconciled.png" width="49%" alt="Parts reconciled across systems" />

<sub><b>Left:</b> hypotheses with supporting and contradicting evidence and the authoritative reference each one needs. <b>Right:</b> inventory reconciled across systems. MAIN-HUB is rejected because ERP says 2 and the physical count says 0.</sub>

<div align="center">
<img src="docs/screenshots/highlights/ac204_recovery_options.png" width="90%" alt="Recovery options ranked" />
<br/><sub><b>Recovery options.</b> Only verified stock and authority-backed alternates qualify; the gray-market substitute is rejected for lack of evidence.</sub>
</div>

<br/>

<div align="center">
<img src="docs/screenshots/highlights/ac204_citations.png" width="90%" alt="Citations with revision and provenance" />
<br/><sub><b>Citations.</b> Each one carries its revision, effective date, classification and provenance hash. The supplier bulletin's hidden instruction is <b>quarantined</b>, and the export it asked for is denied (POL-011).</sub>
</div>

<br/>

<img src="docs/screenshots/highlights/ac204_decision_trace.png" width="49%" alt="Decision trace" />
<img src="docs/screenshots/highlights/ac204_approval_gate.png" width="49%" alt="Human approval gate" />

<sub><b>Left:</b> every policy decision for the run, with expandable ordered checks. <b>Right:</b> the human approval gate. Nothing is written until a different authorized person approves.</sub>

### Act 2: What-if analysis and root cause

<img src="docs/screenshots/highlights/scenario_chart.png" width="49%" alt="Delay scenario comparison" />
<img src="docs/screenshots/highlights/downtime_analysis.png" width="49%" alt="Downtime analysis" />

<sub><b>Left:</b> 24/48/72 h part delays. Downtime jumps non-linearly because of hangar-slot availability; the P90 comes from a seeded Monte Carlo over the supplier's history. <b>Right:</b> "Why did downtime rise in October?" answered with a normalized trend, cause decomposition and bootstrap confidence intervals.</sub>

### Act 3: Defense trust

<div align="center">
<img src="docs/screenshots/highlights/export_denied.png" width="90%" alt="Export denied before execution" />
<br/><sub><b>"Export restricted maintenance records to my personal email."</b> DENY by POL-004 before execution. The tool ran <b>0</b> times; identity, classification and destination are all on record.</sub>
</div>

<br/>

<div align="center">
<img src="docs/screenshots/highlights/security_lab.png" width="90%" alt="Security Test Lab 12 of 12" />
<br/><sub><b>Security Test Lab.</b> Twelve scenarios run against the live controls: public read, restricted read, external export, expired approval, stale document, privilege escalation, prompt injection, untrusted tool, missing token, wrong audience, replayed write, tool timeout.</sub>
</div>

<br/>

<img src="docs/screenshots/highlights/audit_ledger.png" width="49%" alt="Hash-chained audit ledger" />
<img src="docs/screenshots/highlights/agents_failure_retry.png" width="49%" alt="Failure injection and retry" />

<sub><b>Left:</b> the evidence ledger, a hash-chained audit log verified in one click. <b>Right:</b> failure injection in Agent Mission Control. The parts step fails, retries with backoff, and the workflow still completes.</sub>

### Act 4: Legacy modernization, from schema to running bridge

<div align="center">
<img src="docs/screenshots/highlights/legacy_dependency_map.png" width="90%" alt="Legacy dependency map" />
<br/><sub><b>Dependency map</b> of a fictional 20-year-old MRO landscape: 12 systems, APIs, batch files and dashed <i>unknowns</i>. The unknowns are open questions; nothing is assumed.</sub>
</div>

<br/>

<img src="docs/screenshots/highlights/legacy_findings.png" width="49%" alt="Legacy findings" />
<img src="docs/screenshots/highlights/legacy_recommendations.png" width="49%" alt="Modernization recommendations" />

<sub><b>Left:</b> findings: an arbitrary-SQL endpoint, an SSRF-prone webhook, missing primary keys, stale counts, static API keys. <b>Right:</b> evidence-backed patterns (strangler fig, anti-corruption layer, read-only view, batch bridge, CDC, RAG, documented ERP APIs, MCP facade) with rollback, test plan and confidence.</sub>

<img src="docs/screenshots/highlights/bridge_tests_passed.png" width="49%" alt="Generated tests passing" />
<img src="docs/screenshots/highlights/mcp_discovery.png" width="49%" alt="MCP discovery" />

<sub><b>Left:</b> the generated adapter's contract, security and MCP stdio tests, run in a sandbox: 14 passed, 0 failed. <b>Right:</b> the demo MCP server, with tools discovered, schema hashes checked against pins, and each call authorized by the policy engine.</sub>

### Act 5: Executive value

<img src="docs/screenshots/highlights/executive_roi.png" width="49%" alt="ROI benefit components" />
<img src="docs/screenshots/highlights/executive_roadmap.png" width="49%" alt="90-day roadmap" />

<sub>An assumption-driven ROI range with editable inputs, next to the 30/60/90-day pilot roadmap with owners, dependencies and exit criteria.</sub>

### Anywhere: dark mode and mobile

<img src="docs/screenshots/highlights/dark_fleet.png" width="58%" alt="Fleet dashboard, dark theme" />
<img src="docs/screenshots/highlights/mobile_home.png" width="19%" alt="Mobile home" />
<img src="docs/screenshots/highlights/mobile_parts.png" width="19%" alt="Mobile parts" />

---

## 🖥 Every screen

Each page below was captured from the running app with synthetic data.

<table>
<tr>
<td width="50%"><b>Fleet & Asset Health</b><br/><img src="docs/screenshots/04_fleet.png" alt="Fleet & Asset Health" /></td>
<td width="50%"><b>Fleet dashboard (full)</b><br/><img src="docs/screenshots/highlights/fleet_dashboard.png" alt="Fleet dashboard" /></td>
</tr>
<tr>
<td><b>AOG Recovery</b><br/><img src="docs/screenshots/05_aog.png" alt="AOG Recovery" /></td>
<td><b>Maintenance & MRO</b><br/><img src="docs/screenshots/06_maintenance.png" alt="Maintenance & MRO" /></td>
</tr>
<tr>
<td><b>Parts & Supply Chain</b><br/><img src="docs/screenshots/07_parts.png" alt="Parts & Supply Chain" /></td>
<td><b>Engineering Quality</b><br/><img src="docs/screenshots/08_quality.png" alt="Engineering Quality" /></td>
</tr>
<tr>
<td><b>Legacy X-Ray</b><br/><img src="docs/screenshots/09_legacy.png" alt="Legacy X-Ray" /></td>
<td><b>API & MCP Bridge Studio</b><br/><img src="docs/screenshots/10_bridge.png" alt="Bridge Studio" /></td>
</tr>
<tr>
<td><b>Agent Mission Control</b><br/><img src="docs/screenshots/highlights/agents_mission_control.png" alt="Agent Mission Control" /></td>
<td><b>Agent Mission Control (catalog)</b><br/><img src="docs/screenshots/11_agents.png" alt="Agents catalog" /></td>
</tr>
<tr>
<td><b>Defense Trust Center</b><br/><img src="docs/screenshots/12_trust.png" alt="Defense Trust Center" /></td>
<td><b>Security Test Lab</b><br/><img src="docs/screenshots/12_trust_security_lab.png" alt="Security Test Lab" /></td>
</tr>
<tr>
<td><b>Compliance Evidence</b><br/><img src="docs/screenshots/13_compliance.png" alt="Compliance Evidence" /></td>
<td><b>Scenario Simulator</b><br/><img src="docs/screenshots/14_simulator.png" alt="Scenario Simulator" /></td>
</tr>
<tr>
<td><b>Reports & Exports</b><br/><img src="docs/screenshots/16_reports.png" alt="Reports & Exports" /></td>
<td><b>Integrations & Settings</b><br/><img src="docs/screenshots/17_settings.png" alt="Integrations & Settings" /></td>
</tr>
<tr>
<td valign="top"><b>Export request: denied</b><br/><img src="docs/screenshots/03_export_denied.png" alt="Export denied" /></td>
<td valign="top"><b>Legacy X-Ray: generated bridge and tests (full page)</b><br/><img src="docs/screenshots/18_legacy_bridge_tests.png" alt="Bridge tests full page" /></td>
</tr>
<tr>
<td valign="top"><b>AC-204 investigation: the complete workspace</b><br/><img src="docs/screenshots/02_ac204_investigation.png" alt="Full AC-204 workspace" /></td>
<td valign="top"><b>Executive Value Studio: the complete 90-day pitch</b><br/><img src="docs/screenshots/15_executive.png" alt="Executive Value Studio full page" /></td>
</tr>
</table>

---

## 🧠 How it works

### Trust chain

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

### Policy evaluation order (the first failure decides; every check is recorded)

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

### Graph 1: maintenance investigation

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

<sub>Tamper-evident, not tamper-proof: a host administrator could rewrite the file and recompute the chain.</sub>

### Legacy X-Ray → Bridge pipeline

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

| Legacy column (`V_PART_AVAILABILITY`) | Canonical field | Rule |
|---|---|---|
| `PART_NO` | `part_number` | validated `^P-[0-9A-Z]{3,8}$` |
| `PART_DESC` | `description` | — |
| `BASE_CODE` | `location` | — |
| `QTY_OH` | `quantity_on_hand` | non-negative |
| `LOT_NO` | `lot` | `UNKNOWN` ⇒ not traceable |
| `LAST_CNT_DT` | `last_counted` | critical part counted > 30 days ago ⇒ unverified |

### Data model

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
| Enterprise applications / seeded incidents | 12 / 8 |

### The agent roster

| Agent | Responsibility | Tools (pinned) |
|---|---|---|
| Intake & Intent | Deterministic routing, entity extraction, clarification | — |
| Supervisor | DAG waves, retries, cancellation, checkpoints | — |
| Asset Telemetry | Baselines, z-scores, outliers, data-quality gaps | `telemetry.get_series` |
| Knowledge Retrieval | Access-filtered hybrid search, injection quarantine | `docs.search` |
| Diagnostic Evidence | Hypotheses with supporting/contradicting evidence | `maintenance.get_history` |
| Parts | Reconciled inventory, authority-backed alternates | `parts.check_availability` |
| Maintenance Planner | Unexpired qualifications, slots, dry-run drafts | `roster.find_qualified` · `hangar.find_slots` · `workorder.create_draft` |
| Compliance | Evidence sufficiency (never certification) | `docs.search` |
| Legacy Discovery · Integration Architect | Metadata parsing, options, adapter generation | — |
| Scenario Simulator | Deterministic scenarios, seeded Monte Carlo, ROI | — |
| Security & Governance | Explains decisions; never overrides them | — |
| Reporting | Workspace blocks, citations, exports | — |

---

## 🚀 Quick start

Requires **Python 3.11+** and **Node 20+**. Setup needs network once; after that everything runs offline.

```mermaid
flowchart LR
  A["scripts/setup.sh<br/>venv · deps · seed DB · npm install"] --> B["make demo<br/>API :8000 + UI :5173"]
  B --> C["open http://127.0.0.1:5173<br/>no credentials · no API keys"]
  C --> D["make test · make test-e2e · make offline"]
```

<table>
<tr><th>macOS / Linux</th><th>Windows PowerShell</th></tr>
<tr>
<td>

```bash
cd flying-florina
sh scripts/setup.sh
make demo
# open http://127.0.0.1:5173
```

</td>
<td>

```powershell
cd flying-florina
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
cd backend; .\.venv\Scripts\uvicorn app.main:app --port 8000
# 2nd terminal
cd frontend; npm run dev
```

</td>
</tr>
</table>

Without Make: `cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000`, then `cd frontend && npm run dev`.

The UI signs you in as a synthetic persona. Switch personas in the top bar: Executive, Maintenance Planner, Technician, Reliability Engineer, Enterprise Architect, Security Officer, Auditor, Forward Deployed Engineer, Guest, and an external supplier. **The backend enforces rights; the UI only adapts.**

---

## 🎤 Interview demo

```mermaid
timeline
  title Six-minute offline demo
  Act 1 (2 min) : Legacy X-Ray : import MRO schema + nightly CSV : dependency map, hotspots, unknowns : generate read-only bridge, run 14 tests
  Act 2 (2 min) : AC-204 question : agent graph, citations, charts : pending approval : change lead time and recompute scenarios
  Act 3 (1 min) : export request : DENY POL-004, 0 executions : approve as another persona : replay denied POL-005
  Act 4 (1 min) : 90-day pitch : roadmap, risks, ROI ranges : download PDF brief
```

Full 3-minute and 8-minute scripts, plus the questions to expect, are in **[docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md)**.

---

## ✅ Tests and quality gates

| Command | What it covers | Result |
|---|---|---|
| `make test-backend` | routing, policies, export blocking, retrieval filtering, citations, approvals, replay, audit chain, workflows, failure injection, cancel, simulation determinism, upload safety, bridge generation **and execution**, MCP stdio | **102 passed** |
| `npm test` (Vitest) | XSS-safe markdown, chart mapping, table sorting, workspace rendering | **9 passed** |
| `make test-e2e` (Playwright) | fresh start, personas, all 10 prompts, charts, agent graph, legacy upload, adapter tests, denial, approvals, PDF download, guest denials, offline interception, mobile | **13 passed** |
| `make offline` | every workflow + reports with the egress guard on, no LLM | **0 egress attempts** |
| Generated bundle `pytest` | contract 6 · security 6 · MCP stdio 2 | **14 passed** |
| `make lint` · `npm run typecheck` · `npm run build` | ruff (incl. bandit rules) · strict TypeScript · production build | **clean** |

Measured on a 4-CPU container with rules only, no LLM: **58 ms** (export denial) to **~970 ms** (downtime analysis with bootstrap CIs); the AC-204 investigation takes about **250 ms**. See [latency_measured.json](docs/latency_measured.json) and [TEST_REPORT.md](docs/TEST_REPORT.md).

---

## 🗂 Repository layout

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
├── mcp_servers/demo_maintenance/                   local stdio MCP server
├── generated_adapters/example_part_availability/   runnable generated bundle
├── fixtures/            documents · legacy schemas · OpenAPI · OData · CSV · policies · tool pins
├── docs/                architecture · threat model · guides · scripts · assets · screenshots
└── scripts/             setup · seed · smoke · offline check · latency · pin tools
```

---

## ⚖️ Honest limits

| ✅ Real | 🟡 Simulated / demo-grade | ⛔ Not built |
|---|---|---|
| Policy engine, approvals, audit chain, retrieval filtering, workflows, parsers, generated adapter + MCP, reports, offline guard | Persona login (no IdP/MFA), approved writes (demo DB only), ERP data (fictional "IFS-like" fixtures), prompt-injection patterns, process-level egress guard, subprocess test sandbox | Live IFS connection, PostgreSQL/Alembic, OPA, embeddings, local-LLM rephrasing (detection only), 3D views, connector gallery |

**Cost:** no paid APIs, hosted inference, cloud services or accounts, so incremental software spend is **$0**. You provide the hardware and electricity. Claude Code, which was used to build this, may need its own subscription.

<img src="docs/assets/logo.png" width="64" align="right" alt="Flying_Florina logo" />

**Brand:** the round mark shown here is an original placeholder. The authorized portrait and logo files named in the spec weren't available, so no likeness was invented. To use your own assets locally, see [frontend/public/brand/README.md](frontend/public/brand/README.md).

Read [SECURITY_LIMITATIONS.md](docs/SECURITY_LIMITATIONS.md) before presenting to a security team, and [GAP_MATRIX.md](docs/GAP_MATRIX.md) for the full status list.

---

## 📚 Documentation

| | | |
|---|---|---|
| 🏛 [Architecture](docs/ARCHITECTURE.md) | 🗺 [Implementation plan](docs/IMPLEMENTATION_PLAN.md) | 📊 [Gap matrix](docs/GAP_MATRIX.md) |
| 🎯 [Threat model](docs/THREAT_MODEL.md) | 🔒 [Security limitations](docs/SECURITY_LIMITATIONS.md) | 📋 [Compliance mapping](docs/COMPLIANCE_MAPPING.md) |
| 🔌 [API & MCP guide](docs/API_MCP_GUIDE.md) | 💰 [ROI method](docs/ROI_METHOD.md) | 🚚 [Deployment & offline install](docs/DEPLOYMENT.md) |
| 🎤 [Demo scripts](docs/DEMO_SCRIPT.md) | 📄 [One-page pilot brief](docs/ONE_PAGE_BRIEF.md) | ✅ [Test report](docs/TEST_REPORT.md) |
| 📜 [Third-party notices](THIRD_PARTY_NOTICES.md) | ⚖️ [License (GPL-3.0)](LICENSE) | 🎨 [Brand assets](frontend/public/brand/README.md) |

<div align="center">
<br/>
<img src="docs/assets/logo.png" width="72" alt="Flying_Florina" />
<br/>
<b>Flying_Florina</b><br/>
<sub>From legacy systems to trusted industrial intelligence.<br/>Independent concept demo · Not affiliated with or endorsed by IFS</sub>
</div>
