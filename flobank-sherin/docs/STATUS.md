# What is functional, simulated, measured or pending

Status as of this build. **Functional** = implemented and tested end to end. **Simulated** = works against demo inputs,
with no live external system behind it. **Measured** = recorded by the running system. **Pending** = not built.

| Area | Status | Notes |
|---|---|---|
| Deterministic money engine (KPIs, waterfall, ROI, budgets, drill-downs) | Functional | Reconciliation identities tested on PostgreSQL and SQLite |
| 8 KPI cards with MoM, budget comparison and drill-down | Functional | Drill-down lists breakdown rows and the attribution method |
| Graphs A–H (Plotly, interactive) | Functional | Same engine endpoints; click-through on Graph D to cost records |
| USD / INR / CAD with rate history | Functional | Demo rates are labelled synthetic; managers can set new rates |
| Synthetic FLO Bank environment (14 months) | Simulated | Every row has `data_class = "synthetic"` and is badged in the UI |
| Measured view | Measured | Harness runs, their costs and tokens, live API latency, CPU and memory |
| Copilot: streaming (SSE), persistent and searchable history, uploads, charts, approval cards, diffs, reports | Functional | Intents answer from the engine; tests compare answers to DB records |
| Open questions through local Qwen | Functional, optional | Used only when Ollama is reachable; output is labelled model-generated; never supplies figures |
| LangGraph harness: plan, route, tool permissions, retries, verification, interrupt for approval, checkpointing, cost accounting, audit | Functional | SqliteSaver checkpoints; one measured AgentTask per run |
| 15 agents | Functional (deterministic tools) | Python AST debug and patch, test generation, pipeline YAML lint and fix, infra review, secrets scan, Azure log diagnosis, reconciliation, VaR, ESG, compliance, FinOps, reporting |
| Azure DevOps / Azure Monitor / AKS / ADF / Functions connections | Simulated | Diagnoses run on uploaded artefacts (YAML, logs, Bicep). No live tenant connection |
| Opening PRs and deploying after approval | Simulated | The outcome reads "applied (simulated)". A connector to Azure DevOps REST is pending |
| Sherin Guardian (PASS / REVIEW / BLOCK / INSUFFICIENT_DATA) | Functional | Mandatory blocks cannot be overridden by a model or by approval (tested) |
| Manager Approval Center: roles, segregation of duties, escalation, audit | Functional | Demo identity from headers; see "Identity" below |
| OpenTelemetry tracing and structured JSON logs | Functional | In-process span exporter feeds the Metrics page. Export to an OTLP collector is pending |
| P50/P95/P99, request volume, CPU, memory | Measured | Live, from this process |
| GPU utilisation | Measured if available | Reads `nvidia-smi`; otherwise says so. GPU history is synthetic |
| 12-month system metric history | Simulated | Synthetic daily history, labelled |
| Budget alerts and "why did spend increase" | Functional | Built from cost records: category, agent, volume, paid-token share, retries |
| Executive report (Markdown, CSV) | Functional | Includes reconciliation results and definitions |
| Walking full-body Sherin (persistent layer, 11 animation states, 7-scene journey, controls, reduced motion) | Functional | Code-rigged SVG with framer-motion movement. Follows real harness events through SSE `/api/harness/runs/{id}/stream`. Demo mode uses clearly labelled synthetic events |
| Full-body character art | **Draft, pending approval** | Drawn to the brief (long black hair, orange-red outfit). It must be matched to the approved portrait, or replaced by a Rive or Spine export using the same pose names, before release |
| Sherin's approved Ghibli portrait | **Pending asset** | Place the approved image at `frontend/public/sherin/sherin-ghibli.png`. All screens use it automatically. No substitute face is generated |
| Identity / SSO | Pending | Roles come from `X-Role` / `X-User` headers (demo). Production should use Entra ID OIDC group claims |
| Docker Compose | Written, not verified here | No Docker daemon was available in the build environment |
| Alembic migrations | Pending | Tables are created with `create_all` |

## Known limitations

* Chat intent detection uses rules. Questions outside the known intents need the local Qwen model, or return an
  honest "not recognised" answer with the current position.
* The portfolio risk figure is an undiversified weighted volatility (a conservative upper bound) with parametric VaR.
  It is not a full covariance model.
* Generated tests are scaffolds that skip until a reviewer supplies expected values. They compile, but they do not
  assert behaviour on their own.
