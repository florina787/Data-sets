# Architecture

Prototype architecture: a **modular monolith**. No requirement justified distributed services, so modules are
separated by package and interface rather than by network boundary.

```mermaid
flowchart LR
  subgraph UI["React + TypeScript (Vite)"]
    WS[Change Workspace] --- TABS[Requirements · Evidence · Impact · Development · Evaluation · Approvals · Release · Monitoring · Audit]
    CP[Copilot conversation]
  end
  UI -->|JSON + X-Demo-User (demo only)| API[FastAPI API<br/>trusted session · trace IDs · structured errors]
  API --> LC[Lifecycle services<br/>17-state machine]
  LC --> WF[LangGraph supervisor<br/>durable checkpoints]
  WF --> AG[8 bounded agents<br/>tool gateway allow-lists]
  AG --> KB[(Knowledge base<br/>BM25, authz-filtered)]
  AG -. optional .-> LLM[Language provider<br/>deterministic | Anthropic live]
  LC --> EV[Evaluation runner<br/>background jobs]
  EV --> PA[Prediction adapter<br/>fixture | real=unconfigured]
  EV --> PE[Policy engine<br/>PASS/FAIL/INCONCLUSIVE]
  EV --> CT[Control tests<br/>privacy + authorization]
  LC --> GA[Reviews · approvals · binding]
  LC --> RS[Release simulator · monitoring · rollback]
  API & LC & EV & RS --> DB[(PostgreSQL / SQLite<br/>SQLAlchemy + Alembic)]
  LC & EV & RS --> AU[Audit<br/>hash-chained, append-only]
  RS -. unconfigured .-> CONN[Connectors: git · CI · registry · catalogue · storage · identity · deployment · incidents]
```

## Separation of concerns

| Concern | Module | Deterministic? | Notes |
|---|---|---|---|
| Frontend | `frontend/` | — | The persona selector only chooses a seeded user; buttons are shown by permission, and the server enforces them anyway |
| API | `app/api/routes.py`, `app/main.py` | yes | Actor and tenant come from session context, never from the request body. Every response carries `X-Trace-Id` |
| Orchestration | `app/workflows/graph.py` | yes (routing) | LangGraph `StateGraph(ChangeState)`: supervisor → only the scheduled agents → END |
| Agents | `app/agents/agents.py` | logic yes; summaries optional LLM | Can call only allow-listed read tools; outputs are recommendations |
| Policy engine | `app/policies/engine.py` | yes | Thresholds are the stricter of policy and acceptance criteria |
| Control tests | `app/policies/controls.py` | yes | Executed on every evaluation (consent, image refs, grouping protocol, split, redaction, RBAC separation, tenant scope) |
| Evaluation | `app/evaluation/` | yes | NumPy metrics, Wilson intervals, paired bootstrap, family-level confusion |
| Dataset permissions | `app/services/datasets.py` | yes | Eligibility is recomputed from consent records; a record's declared flag is never trusted |
| Approvals | `app/services/gates.py`, `binding.py` | yes | Binding is recomputed from files at check time |
| Release / monitoring / rollback | `app/services/release.py`, `app/monitoring/` | yes | Simulated; idempotent; version guards |
| Audit | `app/services/audit.py` | yes | Hash chain per tenant; `verify_chain` detects edits |

## Workflow, checkpoints and human interrupts

* `ChangeState` (TypedDict) holds the fields in the brief, with reducers for `errors` (append), `usage` (sum),
  `completed` (append) and `outputs` (merge). It holds **references only**: a checkpoint containing image data is
  refused (`image_in_state`).
* After each node, the workflow writes a `WorkflowCheckpoint` row (state, remaining nodes) and commits.
* If a node raises, a `FAILED` checkpoint keeps the remaining nodes. `POST /api/changes/{id}/workflow/resume`
  re-runs only those nodes; completed nodes are not repeated (tested).
* Human review points are recorded as `INTERRUPTED` checkpoints naming the awaited decision (`clarification_answers`,
  `requirement_approval`, `impact_acceptance`, `code_review_and_evaluation`, `reviews`, `rollback_decision`). The
  corresponding API call is the resume.

| Lifecycle step | Agents invoked |
|---|---|
| Create change; all clarifications answered | requirements |
| Investigate | evidence, impact |
| Register candidate | development |
| Evaluation finished | evaluation, governance |
| Release executed | release |
| Alert investigated | monitoring |

## Persistence and recovery

* SQLAlchemy 2 models (`app/models/orm.py`) cover every entity in the brief, plus checkpoints, agent invocations,
  copilot messages, idempotency records and image uploads. Alembic migrations live in `backend/migrations/`; CI runs
  `alembic check`.
* `ChangeRequest` and `Release` use optimistic version columns. A concurrent edit raises `StaleDataError`, which the
  API returns as HTTP 409 `concurrent_modification`.
* Evaluations run as background jobs (thread pool) with persisted status. On startup, `QUEUED`/`RUNNING` runs are
  re-queued, up to 3 attempts. Cancellation is cooperative. Transient database errors are retried with backoff;
  deterministic computation errors are not retried.
* Release and rollback requests require an `Idempotency-Key`. Replays return the original response; a reused key with
  a different body returns 409.
* `/health` (liveness) and `/ready` (database reachable, seeded, knowledge base loaded).
* Backup and restore: `python -m app.backup dump|restore` (JSON, FK-ordered; restore is demo-only). The round trip is
  tested, including audit-chain validity after restore.

## Error categories

| Category | HTTP | Meaning |
|---|---|---|
| `policy` | 409 | A deterministic rule blocked the action (illegal transition, gates, separation of duties) |
| `authorization` / `authentication` | 403 / 401 | Role lacks permission; no or unknown session |
| `computation` | 500 | Failed computation or agent node (resumable where stated) |
| `integration_unavailable` | 503 | Real adapter not configured |
| `validation` / `conflict` / `not_found` | 422 / 409 / 404 | Input, idempotency or concurrency conflicts, and missing (or other-tenant) records |
