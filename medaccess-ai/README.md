<div align="center">

# 🏥 MedAccess AI — Dr. Christina Copilot

### Smarter Healthcare Access. Shorter Waits. Better Choices.

![Python](https://img.shields.io/badge/Python-3.11%2B-1565C0?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-00897B?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-multi--agent-1565C0)
![React](https://img.shields.io/badge/React-TypeScript-00897B?logo=react&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-1565C0?logo=postgresql&logoColor=white)
![Tests](https://img.shields.io/badge/backend%20tests-129%20passing-2E7D32)
![E2E](https://img.shields.io/badge/e2e-7%20passing-2E7D32)
![Data](https://img.shields.io/badge/data-synthetic%20only-ED6C02)

*A multi-agent AI copilot that helps patients find potentially earlier medical appointments,<br/>and an AI-driven software lifecycle that keeps it honest.*

</div>

> **⚠️ DEMONSTRATION DATA — NOT LIVE APPOINTMENT AVAILABILITY.**
> Every facility, appointment and user is fictional. No real provider is connected, no appointment is ever booked,
> and deployments in the SDLC demo are simulated. **Christina is a virtual AI assistant, not a licensed physician.**

---

## 📑 Contents

1. [Why this exists](#-why-this-exists)
2. [At a glance](#-at-a-glance)
3. [System architecture](#-system-architecture)
4. [The patient journey](#-the-patient-journey)
5. [The agent workflow (LangGraph)](#-the-agent-workflow-langgraph)
6. [How availability is verified](#-how-availability-is-verified)
7. [Booking: handoff, not fabrication](#-booking-handoff-not-fabrication)
8. [Safety, privacy and the agent harness](#-safety-privacy-and-the-agent-harness)
9. [Knowledge with citations (RAG)](#-knowledge-with-citations-rag)
10. [The AI-SDLC Command Center](#-the-ai-sdlc-command-center)
11. [Data model](#-data-model)
12. [Deployment and CI/CD](#-deployment-and-cicd)
13. [Screenshots](#-screenshots)
14. [Quick start](#-quick-start)
15. [Testing](#-testing)
16. [Repository layout](#-repository-layout)
17. [Status and limitations](#-status-and-limitations)

---

## 💡 Why this exists

My best friend had to wait three months for an MRI. The appointment existed, but nobody could answer one question:
**is there an earlier, eligible appointment somewhere else?** That information is scattered across phone lines,
booking pages and referral rules. MedAccess AI brings it together, and it is designed above all **never to overstate
what it knows**.

📖 Full story: [*My best friend had to wait three months for an MRI*](https://medium.com/@florinaregius/my-best-friend-had-to-wait-three-months-for-an-mri-142bbc859bdc)

---

## 🔭 At a glance

| | Healthcare Access Intelligence | Enterprise AI-SDLC |
|---|---|---|
| **Who** | Patients, through Dr. Christina | Engineers, product owners, release approvers |
| **What** | Find, verify, compare and hand off earlier appointments | Requirement → architecture → code → test → release → monitoring |
| **Engine** | LangGraph patient graph: 22 nodes, 20 agents | LangGraph SDLC graph: 15 stages, 8 agents |
| **Human gates** | Radius expansion, booking handoff | Requirement clarification, production release |
| **Proof** | 129 backend tests, 29 QA scenarios, 7 e2e browser tests | Injected defect detected, root cause confirmed, fix released |

```mermaid
mindmap
  root((MedAccess AI))
    Patient app
      Dr. Christina chat
      Search and compare
      Map and wait times
      Booking handoff
      Requisition checklist
    Agents
      20 patient agents
      8 SDLC agents
      Agent harness
      9 MCP servers
    Trust
      Verified vs unverified
      Human approvals
      Redaction
      Hash-chained audit
    Engineering
      Requirements to release
      Defect injection
      Root cause analysis
      Monitoring
```

---

## 🏗️ System architecture

```mermaid
flowchart LR
    subgraph Client["🖥️ Browser"]
        UI["React + TypeScript + Tailwind<br/>Dr. Christina · map · dashboards"]
    end

    subgraph API["⚙️ FastAPI backend"]
        MW["Middleware<br/>JWT · RBAC · rate limit · request IDs"]
        PG["🧭 Patient LangGraph<br/>22 nodes · 20 agents"]
        SG["🛠️ AI-SDLC LangGraph<br/>15 stages · 8 agents"]
        H["🛡️ Agent harness<br/>allowlists · budgets · retries · circuit breakers"]
        T["🔧 Typed tools<br/>9 MCP servers · LangChain tools"]
        RAG["📚 RAG index<br/>BM25 + vectors · verified citations"]
    end

    subgraph Data["💾 Data and observability"]
        DB[("PostgreSQL / SQLite<br/>31 tables")]
        CP[("LangGraph checkpoints")]
        OBS["📈 OpenTelemetry · Prometheus · Grafana<br/>LangSmith (opt-in, redacted)"]
    end

    SRC["📡 Availability sources<br/>synthetic now · FHIR / partner later"]

    UI -->|HTTPS + JWT| MW
    MW --> PG & SG
    PG --> H
    SG --> H
    H --> T & RAG
    T -->|untrusted, sanitised| SRC
    PG --> CP
    MW --> DB
    MW --> OBS

    classDef blue fill:#E8F1FB,stroke:#1565C0,color:#17324D
    classDef teal fill:#E0F2F0,stroke:#00897B,color:#17324D
    classDef warn fill:#FFF4E5,stroke:#ED6C02,color:#17324D
    class UI,MW,PG,SG blue
    class H,T,RAG,DB,CP,OBS teal
    class SRC warn
```

**Design rule:** LLMs are optional and never make safety-relevant decisions. Distance, dates, verification,
eligibility, ranking and booking transitions are deterministic Python with Pydantic-typed inputs and outputs.

---

## 🧑‍⚕️ The patient journey

```mermaid
sequenceDiagram
    autonumber
    actor P as 🧑 Patient
    participant C as 🩺 Dr. Christina
    participant G as 🧭 LangGraph
    participant S as 📡 Sources
    participant A as ✋ Human approval

    P->>C: I need an MRI. My appointment is three months away.
    C-->>P: Do you have a requisition, and where should I search?
    P->>C: Yes. Toronto, within 25 km.
    C->>G: start workflow (service, coarse location, radius)
    G->>G: safety screen · classify · discover · filter by distance
    G->>S: fetch slots (authorized sources only)
    S-->>G: raw slots (treated as untrusted)
    G->>G: verify · check eligibility · compare waits · rank
    G-->>C: 5 verified alternatives + 5 unverified possibilities
    C-->>P: 🟢 Verified: 5 days away, 14 km, 85 days sooner<br/>🟡 Unverified: 3-day slot, NOT confirmed
    P->>C: Prepare a booking handoff
    C->>G: booking request (idempotency key + consent)
    G->>A: ⏸ interrupt: approval required
    P->>A: Approve
    A-->>G: resume
    G-->>P: Official booking instructions, marked NOT CONFIRMED
```

---

## 🧭 The agent workflow (LangGraph)

An explicit `StateGraph` with conditional branches, durable checkpoints and two human interrupts.

```mermaid
flowchart TD
    START([▶ START]) --> intake[Patient Intake]
    intake -->|missing input| audit
    intake --> safety{Clinical Safety Check}
    safety -->|urgent language| sint[🚨 Safety Interruption<br/>911 · Health811 · 988]
    sint --> audit
    safety -->|routine| classify[Service Classification]
    classify --> discover[Facility Discovery]
    discover --> geo[Geospatial Filtering]
    geo --> avail[Availability Search]
    avail -->|source failed| recovery[🔁 Recovery Agent<br/>retry · circuit breaker · mark unavailable]
    avail --> dq[Data Quality]
    recovery --> dq
    dq --> verify[Availability Verification]
    verify --> elig[Eligibility Validation]
    elig --> wait[Wait-Time Comparison]
    wait --> rec{Recommendation}
    rec -->|no verified result| expand[Expand Search Options]
    expand --> expappr[/✋ Patient approval: wider radius?/]
    expappr -->|approved, max 2| discover
    expappr -->|declined| review
    rec --> review[Patient Review]
    review -->|booking requested| prep[Booking Preparation]
    review --> audit
    prep --> happr[/✋ Human Approval/]
    happr -->|approved| handoff[Booking Handoff]
    happr -->|rejected| audit
    handoff --> confirm[Confirmation Verification]
    confirm --> notify[Notification]
    notify --> audit[🧾 Audit]
    audit --> END([⏹ END])

    classDef gate fill:#FFF4E5,stroke:#ED6C02,color:#17324D
    classDef danger fill:#FDECEC,stroke:#D32F2F,color:#17324D
    classDef ok fill:#E8F5E9,stroke:#2E7D32,color:#17324D
    class expappr,happr gate
    class sint danger
    class audit,END,START ok
```

### The 20 patient agents

| Group | Agents | Responsibility |
|---|---|---|
| 🎛️ **Control** | Supervisor · Human Approval · Recovery | Run the graph, enforce budgets and checkpoints, pause for people, recover from failures |
| 🗣️ **Understand** | Patient Intake · Clinical Safety · Service Classification | Collect the minimum needed, screen for emergencies, map requests to services |
| 🔎 **Find** | Facility Discovery · Geospatial Intelligence · Availability Search | Find facilities, filter by distance (2–100 km), query authorized sources |
| ⚖️ **Judge** | Availability Verification · Requisition Eligibility · Wait-Time Intelligence · Recommendation | Verify, check eligibility, compute waits, rank in separate tiers |
| 🤝 **Act** | Booking Assistance · Notification · RAG Knowledge | Prepare handoffs, send consent-gated reminders, answer with citations |
| 🛡️ **Guard** | Data Quality · Privacy and Security · Audit · Monitoring | Catch bad data, minimise and redact, record everything, watch health |

--- a17[Human Approval] --- a20[Recovery]
    end
    subgraph Understand["🗣️ Understand"]
        a2[Patient Intake] --- a3[Clinical Safety] --- a4[Service Classification]
    end
    subgraph Find["🔎 Find"]
        a5[Facility Discovery] --- a6[Geospatial Intelligence] --- a7[Availability Search]
    end
    subgraph Judge["⚖️ Judge"]
        a8[Availability Verification] --- a9[Requisition Eligibility] --- a10[Wait-Time Intelligence] --- a11[Recommendation]
    end
    subgraph Act["🤝 Act"]
        a12[Booking Assistance] --- a13[Notification] --- a14[RAG Knowledge]
    end
    subgraph Guard["🛡️ Guard"]
        a15[Data Quality] --- a16[Privacy and Security] --- a18[Audit] --- a19[Monitoring]
    end
```

---

## ✅ How availability is verified

Every slot is classified by deterministic rules (`backend/app/services/verification.py`).

```mermaid
flowchart TD
    S[Raw slot from a source] --> F{Facility known?}
    F -->|no| UNK1[❔ UNKNOWN]
    F -->|yes| SV{Offers this service?}
    SV -->|no| UN1[⛔ UNAVAILABLE]
    SV -->|yes| TS{Valid timestamp?}
    TS -->|no| UNK2[❔ UNKNOWN]
    TS -->|yes| PAST{In the past?}
    PAST -->|yes| UN2[⛔ UNAVAILABLE]
    PAST -->|no| AUTH{Authorized source?}
    AUTH -->|no| UNK3[❔ UNKNOWN]
    AUTH -->|yes| ST{Source status}
    ST -->|booked / cancelled| UN3[⛔ UNAVAILABLE]
    ST -->|call to confirm| CR[📞 CONTACT_REQUIRED]
    ST -->|advertised| AU1[🟡 ADVERTISED_UNVERIFIED]
    ST -->|confirmed by feed| FR{Verified within 6 h?}
    FR -->|no| AU2[🟡 ADVERTISED_UNVERIFIED<br/>stale]
    FR -->|yes| REL{Source reliability ≥ 0.80?}
    REL -->|no| AU3[🟡 ADVERTISED_UNVERIFIED<br/>low reliability]
    REL -->|yes| OK[🟢 VERIFIED_AVAILABLE]

    classDef ok fill:#E8F5E9,stroke:#2E7D32,color:#17324D
    classDef warn fill:#FFF4E5,stroke:#ED6C02,color:#17324D
    classDef bad fill:#FDECEC,stroke:#D32F2F,color:#17324D
    classDef grey fill:#F1F5F9,stroke:#90A4AE,color:#17324D
    class OK ok
    class AU1,AU2,AU3,CR warn
    class UNK1,UNK2,UNK3 bad
    class UN1,UN2,UN3 grey
```

Synthetic records additionally display **`DEMO_SIMULATED`**. Results are then split into two tiers that never mix:

```mermaid
flowchart LR
    V[Verified slots] --> T1["🟢 CONFIRMED ALTERNATIVES<br/>ranked by days, then distance, then travel time"]
    U[Advertised / contact-required slots] --> T2["🟡 UNVERIFIED POSSIBILITIES<br/>always listed below, marked NOT CONFIRMED"]
    T1 --> D["Potential days saved<br/>(verified alternatives only)"]
    E[Ineligible facility<br/>e.g. requisition not accepted] -.->|excluded| X[✖]

    classDef ok fill:#E8F5E9,stroke:#2E7D32,color:#17324D
    classDef warn fill:#FFF4E5,stroke:#ED6C02,color:#17324D
    class T1,D ok
    class T2 warn
```

---

## 🤝 Booking: handoff, not fabrication

MedAccess AI never books on a patient's behalf. A booking reaches `PROVIDER_CONFIRMED` only through a verifiable
confirmation from an authorized live integration, which synthetic data can never produce (enforced by tests).

```mermaid
stateDiagram-v2
    [*] --> NOT_REQUESTED
    NOT_REQUESTED --> PENDING_APPROVAL: patient selects slot + consents
    PENDING_APPROVAL --> REJECTED: patient rejects
    PENDING_APPROVAL --> FAILED: slot no longer eligible
    PENDING_APPROVAL --> HANDOFF_PREPARED: patient approves
    HANDOFF_PREPARED --> PATIENT_REPORTED_BOOKED: "I booked this" (unverified)
    HANDOFF_PREPARED --> PROVIDER_CONFIRMED: authorized live integration only
    PATIENT_REPORTED_BOOKED --> PROVIDER_CONFIRMED: authorized live integration only
    HANDOFF_PREPARED --> CANCELLED
    PROVIDER_CONFIRMED --> CANCELLED
    REJECTED --> [*]
    FAILED --> [*]
    CANCELLED --> [*]
```

Booking requests are **idempotent**: the same idempotency key always returns the same request, never a duplicate.

---

## 🛡️ Safety, privacy and the agent harness

Every tool call made by any agent passes through the harness (`backend/app/harness/core.py`):

```mermaid
flowchart LR
    A[Agent requests tool] --> B{Tool on agent's<br/>allowlist?}
    B -->|no| X1[⛔ TOOL_NOT_ALLOWED]
    B -->|yes| C{Role has<br/>permission?}
    C -->|no| X2[⛔ PERMISSION_DENIED]
    C -->|yes| D{Side effect?}
    D -->|yes, no approved approval id| X3[⛔ APPROVAL_REQUIRED]
    D -->|no / approved| E{Budget left?<br/>steps · time · calls · tokens}
    E -->|no| X4[⛔ BUDGET_EXCEEDED]
    E -->|yes| F[Validate input<br/>Pydantic]
    F --> G{Circuit<br/>closed?}
    G -->|open| X5[⛔ CIRCUIT_OPEN]
    G -->|yes| H[Run tool]
    H -->|transient error| R[🔁 Backoff + bounded retry]
    R --> G
    H --> I[Validate output]
    I --> J[Sanitise untrusted output<br/>strip prompt injection]
    J --> K[✅ Result + telemetry + audit]

    classDef bad fill:#FDECEC,stroke:#D32F2F,color:#17324D
    classDef ok fill:#E8F5E9,stroke:#2E7D32,color:#17324D
    class X1,X2,X3,X4,X5 bad
    class K ok
```

Privacy-by-design, from input to export:

```mermaid
flowchart TB
    IN["🧑 Patient message"] --> SAFE{"🚨 Safety screen<br/>(before anything else)"}
    SAFE -->|urgent| EMG["Emergency guidance<br/>search paused"]
    SAFE --> INJ["Prompt-injection check<br/>message = data, never instructions"]
    INJ --> MIN["Data minimisation<br/>service · postal area (3 chars) · radius"]
    MIN --> STATE[("Workflow state<br/>no free text, no names")]
    STATE --> RED["Redaction<br/>emails · phones · health cards · postal codes · DOB · names"]
    RED --> AUD[("🧾 Hash-chained audit log")]
    RED --> TEL["📈 Telemetry / LangSmith<br/>redacted only, opt-in"]

    classDef danger fill:#FDECEC,stroke:#D32F2F,color:#17324D
    classDef teal fill:#E0F2F0,stroke:#00897B,color:#17324D
    class SAFE,EMG danger
    class MIN,RED,STATE,AUD,TEL teal
```

| Control | Where | Tested by |
|---|---|---|
| JWT auth + RBAC + object-level ownership | `security/auth.py`, routes | `tests/security/` |
| Human approval and separation of duties | `governance/approvals.py` | `tests/agents/`, `tests/security/` |
| Redaction before audit and tracing | `security/guards.py`, `telemetry/tracing.py` | `test_redaction`, `test_langsmith_redaction_hook` |
| Tamper-evident audit | `governance/audit.py` | `test_audit_log_is_redacted_and_tamper_evident` |
| No secrets in the frontend | build scan + Security Agent | e2e `no API keys or secrets in the served frontend` |
| Field encryption, startup secret checks | `security/crypto.py`, `config/settings.py` | `test_production_config_requires_secrets` |

---

## 📚 Knowledge with citations (RAG)

```mermaid
flowchart LR
    subgraph Ingest
        D1[Approved docs<br/>data/knowledge] --> D2[Validate metadata] --> D3[Clean + chunk] --> D4[Embed + index]
    end
    subgraph Answer
        Q[Question] --> R1[Hybrid retrieval<br/>BM25 + vectors] --> R2[Metadata rerank] --> R3{Confidence<br/>enough?}
        R3 -->|no| NO["🙅 Refuse:<br/>won't guess"]
        R3 -->|yes| R4[Extractive answer] --> R5{Every cited sentence<br/>found in its chunk?}
        R5 -->|no| NO
        R5 -->|yes| OUT["✅ Answer + citations<br/>+ stale-document warnings"]
    end
    D4 --> R1
```

The knowledge base contains platform documentation, a summary of public Ontario help lines (verify at source) and
clearly labelled fictional facility documents. **No invented medical policies.**

---

## 🛠️ The AI-SDLC Command Center

**The 90-Day MRI Wait-Time Challenge** runs on a separate LangGraph: 15 stages, 8 engineering agents and 2 human checkpoints.

```mermaid
flowchart LR
    S1[1 · Business<br/>requirement] --> S2[2 · Ambiguity<br/>detection]
    S2 --> S3[/3 · ✋ Human<br/>clarification/]
    S3 --> S4[4 · Architecture] --> S5[5 · Development<br/>build 1.4.0]
    S5 --> S6[6 · QA<br/>29 scenarios] --> S7[7 · Simulation<br/>ground truth]
    S7 --> S8[8 · 💣 Injected defect<br/>build 1.5.0]
    S8 --> S9[9 · 📈 Monitoring<br/>anomaly detected]
    S9 --> S10[10 · 🔍 Root cause<br/>with evidence]
    S10 --> S11[11 · Fix<br/>build 1.5.1]
    S11 --> S12[12 · Regression<br/>+ security]
    S12 --> S13[/13 · ✋ Release<br/>approval/]
    S13 --> S14[14 · Deployment<br/>simulated]
    S14 --> S15[15 · Post-release<br/>monitoring]

    classDef gate fill:#FFF4E5,stroke:#ED6C02,color:#17324D
    classDef bad fill:#FDECEC,stroke:#D32F2F,color:#17324D
    classDef ok fill:#E8F5E9,stroke:#2E7D32,color:#17324D
    class S3,S13 gate
    class S8,S9 bad
    class S11,S12,S15 ok
```

### The injected defect, end to end

```mermaid
sequenceDiagram
    autonumber
    participant Dev as 🛠️ Development
    participant Prod as 🏭 demo-production
    participant Mon as 📈 Monitoring
    participant RCA as 🔍 Root Cause
    participant QA as 🧪 QA
    actor App as ✋ Release Approver

    Dev->>Prod: deploy 1.5.0 (advertised → VERIFIED, deliberate defect)
    Prod-->>Mon: synthetic traffic: unverified slots shown as confirmed
    Mon->>Mon: VERIFICATION_MISCLASSIFICATION · UNVERIFIED_AS_CONFIRMED
    Mon->>RCA: anomaly + traces
    RCA->>QA: run suite on 1.5.0 and 1.4.0
    QA-->>RCA: 3 regression scenarios fail only on 1.5.0
    RCA->>RCA: code diff + timing ⇒ H1 CONFIRMED, H2–H4 rejected
    RCA->>Dev: propose 1.5.1 (one-line mapping fix)
    Dev->>QA: regression on 1.5.1
    QA-->>Dev: all pass
    Dev->>App: request production approval
    Note over Dev,App: requester ≠ approver (separation of duties)
    App-->>Prod: approve → deploy 1.5.1
    Prod-->>Mon: post-release traffic: 0 unverified shown as confirmed ✅
```

### Root-cause hypotheses are evidence-gated

```mermaid
flowchart TD
    H[Hypothesis] --> E1{Code or config<br/>difference exists?}
    E1 -->|no| REJ[❌ REJECTED]
    E1 -->|yes| E2{Tests fail on<br/>suspect build?}
    E2 -->|no| INC[❔ INCONCLUSIVE]
    E2 -->|yes| E3{Same tests pass when only<br/>that difference is reverted?}
    E3 -->|no| INC
    E3 -->|yes| CON[✅ CONFIRMED]

    classDef ok fill:#E8F5E9,stroke:#2E7D32,color:#17324D
    classDef bad fill:#FDECEC,stroke:#D32F2F,color:#17324D
    classDef warn fill:#FFF4E5,stroke:#ED6C02,color:#17324D
    class CON ok
    class REJ bad
    class INC warn
```

### Traceability chain

```mermaid
flowchart LR
    REQ["📋 REQ<br/>requirement + stories"] --> ARCH["🏗️ ARCH<br/>diagrams"] --> CODE["💻 CODE<br/>build + diff"] --> TEST["🧪 TEST<br/>suite results"] --> REL["🚀 REL<br/>approval + deploy"] --> MON["📈 MON<br/>anomalies + RCA"]
    MON -.->|continuous improvement| REQ
```

---

## 🗄️ Data model

31 tables in PostgreSQL (Alembic migration verified on PostgreSQL 16). Core relationships:

```mermaid
erDiagram
    USERS ||--o{ SEARCH_REQUESTS : runs
    USERS ||--o{ BOOKING_REQUESTS : owns
    USERS ||--o{ PATIENT_CONSENTS : grants
    USERS ||--o{ NOTIFICATIONS : receives
    ROLES ||--o{ USERS : assigns
    ROLES ||--o{ PERMISSIONS : grants
    PROVIDER_INTEGRATIONS ||--o{ FACILITIES : feeds
    FACILITIES ||--|| FACILITY_LOCATIONS : located_at
    FACILITIES ||--o{ FACILITY_SERVICES : offers
    FACILITIES ||--o{ APPOINTMENT_SLOTS : has
    FACILITIES ||--o{ REQUISITION_REQUIREMENTS : requires
    HEALTHCARE_SERVICES ||--o{ FACILITY_SERVICES : classifies
    SEARCH_REQUESTS ||--o{ SEARCH_RESULTS : produces
    SEARCH_REQUESTS ||--o{ RECOMMENDATIONS : ranks
    BOOKING_REQUESTS ||--o{ BOOKING_CONFIRMATIONS : "verified only"
    KNOWLEDGE_DOCUMENTS ||--o{ DOCUMENT_CHUNKS : splits
    WORKFLOW_EXECUTIONS ||--o{ AGENT_EXECUTIONS : runs
    WORKFLOW_EXECUTIONS ||--o{ TOOL_EXECUTIONS : calls
    WORKFLOW_EXECUTIONS ||--o{ APPROVAL_REQUESTS : pauses_for
    WORKFLOW_EXECUTIONS ||--o{ AUDIT_EVENTS : records
```

Also: `slot_verifications`, `model_usage`, `integration_errors`, `system_metrics`, `release_versions`,
`user_preferences`, `sdlc_artifacts`. All timestamps are UTC and shown in the facility's local time zone.

### Three separated data modes

```mermaid
flowchart LR
    A["🅰️ Synthetic demonstration<br/><b>implemented</b><br/>fictional, labelled DEMO"]
    B["🅱️ Public provider discovery<br/><b>planned</b><br/>real facilities, no inferred vacancies"]
    C["🅲 Authorized live integration<br/><b>interface + FHIR mapping tested</b><br/>partner APIs only"]
    A -.->|never mixed without labels| B -.->|never mixed without labels| C

    classDef done fill:#E8F5E9,stroke:#2E7D32,color:#17324D
    classDef plan fill:#F1F5F9,stroke:#90A4AE,color:#17324D
    classDef part fill:#FFF4E5,stroke:#ED6C02,color:#17324D
    class A done
    class B plan
    class C part
```

---

## 🚢 Deployment and CI/CD

```mermaid
flowchart LR
    U["🌐 Browser"] -->|:8080| FE["frontend<br/>nginx + static React"]
    FE -->|/api| BE["backend<br/>uvicorn + FastAPI"]
    BE --> PG[("postgres:16")]
    BE --> RD[("redis:7")]
    BE --> VOL[("runtime volume<br/>checkpoints")]
    subgraph Monitoring["profile: monitoring"]
        PR["Prometheus :9090"] -->|scrape /api/v1/metrics| BE
        GF["Grafana :3001"] --> PR
    end
```

```mermaid
flowchart LR
    C[Commit] --> L[Lint · ruff] --> TC[Type check<br/>mypy · tsc]
    TC --> UT[Tests<br/>SQLite + PostgreSQL]
    UT --> SEC[Security<br/>pip-audit · npm audit · suites]
    SEC --> BLD[Build containers]
    BLD --> STG[Ephemeral staging<br/>docker compose]
    STG --> E2E[Playwright e2e]
    E2E --> GATE[/✋ GitHub environment<br/>approval/]
    GATE --> PROD[Production deploy<br/>no target configured]
    PROD --> POST[Post-deploy checks]

    classDef gate fill:#FFF4E5,stroke:#ED6C02,color:#17324D
    class GATE gate
```

---

## 📸 Screenshots

| Search results | Dr. Christina on mobile |
|---|---|
| ![Search results](docs/user-guide/screenshots/results-desktop.png) | ![Christina on mobile](docs/user-guide/screenshots/christina-mobile.png) |
| **Booking handoff approval** | **AI-SDLC root cause** |
| ![Booking handoff](docs/user-guide/screenshots/booking-handoff.png) | ![SDLC root cause](docs/user-guide/screenshots/sdlc-complete.png) |

*Captured automatically by the Playwright end-to-end suite.*

---

## 🚀 Quick start

### Docker (recommended)

```bash
cd medaccess-ai
docker compose up --build                       # UI → http://localhost:8080 · API docs → http://localhost:8000/docs
docker compose --profile monitoring up --build  # + Prometheus :9090 · Grafana :3001
```

No API keys, cloud services or real patient data are needed. Sign in with a demo account on the start screen:

| Account | Can do |
|---|---|
| 🧑 Demo Patient | Chat with Christina, search, approve booking handoffs |
| 🛠️ Demo Engineer | Run the AI-SDLC challenge, QA, architecture, monitoring |
| ✅ Demo Release Approver | Approve production releases (separation of duties) |
| 🔑 Demo Administrator | Governance, administration, everything above |

> Behind a TLS-intercepting proxy, pass its CA as a BuildKit secret. See
> [deployment docs](docs/deployment/deployment-and-capacity.md).

### Local development

Requirements: Python 3.11+ (tested on 3.13) and Node 20+ (tested on 22).

```bash
cd medaccess-ai
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements-dev.txt
(cd frontend && npm ci)
make backend    # API on :8000 (SQLite + synthetic data)
make frontend   # UI on http://localhost:5173
```

Optional settings live in `.env` (copy `.env.example`; it is git-ignored):

| Setting | Effect |
|---|---|
| `LLM_ENABLED=true` + `ANTHROPIC_API_KEY` | Christina rephrases replies with Claude; all decisions stay deterministic |
| `LANGSMITH_TRACING=true` + `LANGSMITH_API_KEY` | Exports **redacted** traces |
| `DATABASE_URL` | Use PostgreSQL instead of SQLite |

Keys stay on the backend. The frontend never sees them.

---

## 🧪 Testing

```mermaid
pie showData
    title Automated tests by layer
    "Backend unit" : 65
    "Backend agents (LangGraph)" : 26
    "Backend integration (API)" : 19
    "Backend security" : 17
    "Backend performance" : 2
    "Frontend unit" : 7
    "End-to-end browser" : 7
```

```bash
make test          # pytest (129) + JUnit report at sdlc/qa/pytest-report.xml + vitest (7)
make lint typecheck
TEST_DATABASE_URL=postgresql+psycopg://user:pw@localhost/medaccess .venv/bin/python -m pytest   # same suite on PostgreSQL
cd frontend && npm run build && npm run preview & npx playwright test   # e2e, desktop + mobile
```

| Evidence | Result |
|---|---|
| Backend tests | **129 passed** on SQLite and PostgreSQL 16 |
| QA Agent scenarios | **29/29** pass on 1.4.0 and 1.5.1; 3 fail on defective 1.5.0 (as designed) |
| End-to-end (Chromium, desktop + Pixel 7) | **7 passed** on dev servers and on the full Docker stack |
| Load test (one worker) | ~6.5 searches/s, p95 ≈ 204 ms at concurrency 1 |

---

## 🗂️ Repository layout

```text
medaccess-ai/
├── backend/app/
│   ├── api/            FastAPI routes + middleware
│   ├── agents/         agent catalogue (20 patient + 8 SDLC) and node logic
│   ├── graphs/         LangGraph StateGraphs: patient_graph.py, sdlc_graph.py
│   ├── harness/        allowlists, permissions, budgets, retries, circuit breakers
│   ├── tools/ mcp/     typed tools, 9 MCP servers, LangChain StructuredTools
│   ├── services/       geo, verification, eligibility, ranking, booking, synthetic data
│   ├── integrations/   availability adapters (synthetic, FHIR, partner interface)
│   ├── rag/            retrieval with citation verification
│   ├── copilot/        Dr. Christina conversation engine, optional LLM layer
│   ├── sdlc_engine/    requirements, architecture, QA, simulation, monitoring, RCA, security, release
│   └── governance/ security/ telemetry/ models/ database/ config/
├── backend/migrations/ Alembic (31 tables)
├── frontend/src/       React + TypeScript + Tailwind
├── tests/              unit · integration · agents · security · performance
├── data/knowledge/     approved knowledge base
├── sdlc/               artifacts generated by the SDLC agents
├── infrastructure/     nginx · Prometheus/Grafana · Kubernetes starter · load test
├── docs/               architecture · api · security · deployment · user-guide
└── docker-compose.yml
```

📘 More docs: [Architecture](docs/architecture/overview.md) · [API](docs/api/README.md) ·
[Security & privacy](docs/security/security-privacy.md) · [Deployment & capacity](docs/deployment/deployment-and-capacity.md) ·
[Demo walkthrough](docs/user-guide/demo-walkthrough.md) · [Implementation status](IMPLEMENTATION_STATUS.md)

---

## 📊 Status and limitations

| Area | Status |
|---|---|
| Patient workflow, verification, ranking, approvals, booking handoff | 🟢 Implemented and tested |
| AI-SDLC lifecycle with injected defect | 🟢 Implemented (deployments simulated) |
| Docker, PostgreSQL, Prometheus, Grafana | 🟢 Verified locally |
| Real provider data (FHIR / partner APIs) | 🟡 Interface + FHIR mapping tested on synthetic data only |
| LLM rephrasing and LangSmith tracing | 🟡 Wired up, not exercised without credentials |
| OAuth 2.0 / OIDC login | ⚪ Planned (demo JWT login today) |
| CI on GitHub, Kubernetes | ⚪ Defined, not yet run |
| PHIPA privacy impact assessment, legal review, formal accessibility audit | ⚪ Required before any real patient data |

Full evidence for every claim: [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).

---

<div align="center">

**In an emergency, call 911. For health advice in Ontario, call Health811 (811).**

*MedAccess AI is a prototype built with synthetic data. Christina is a virtual AI assistant, not a licensed physician.*

</div>
