# FLO Bank — Sherin AI 3.0

A money-first enterprise AI platform for banking executives. The first screen answers eight questions:
**How much did we earn? How much did we spend? How much did Sherin cost? What verified value did Sherin create?
How much work did the agents complete? How many tokens and how much compute did they use? Which agents are financially
efficient? Which decisions need a human?**

![Financial Command Center](docs/screenshots/route-home.png)

> **Demonstration data.** In demo mode every financial figure is synthetic and badged as such. Synthetic and measured
> records are kept in separate views and never mixed. Nothing here is FLO Bank's actual performance.

## What's inside

| | |
|---|---|
| **Financial Command Center** | 8 drill-down KPI cards (MoM and budget). Eight large interactive Plotly charts take about 55% of the screen, with the chat at 25% and investment graph + agent harness + alerts at 20%. Panels are resizable |
| **Money engine** | Deterministic `Decimal` engine with written accounting rules ([docs/FINANCIAL_ACCOUNTING.md](docs/FINANCIAL_ACCOUNTING.md)). No double counting; ROI denominator stated; reconciliation checks visible in the UI |
| **Sherin Copilot** | ChatGPT-style chat: streaming, persistent and searchable history, file uploads, inline charts, code diffs, approval cards, reports. Answers come from the engine and link to their chart |
| **Agent harness** | LangGraph orchestration of 15 agents with planning, routing, tool permissions, checkpointing, retries, verification, human approval, cost and token accounting, and a live React Flow graph |
| **Azure & Python engineering** | Pipeline YAML lint and fix, ADF / Functions / AKS / App Insights log diagnosis, infra review, secrets scan, Python AST debugging with patch diffs and test scaffolds. Each workflow shows its cost against a human baseline |
| **Sherin Guardian** | Deterministic pre-trade controls (mandate, restricted list, exclusions, concentration, liquidity, rating, ESG, volatility and VaR, evidence, materiality). A PASS is not authorization; a BLOCK cannot be overridden |
| **Manager Approval Center** | Roles, segregation of duties, escalation, risk evidence, agent history and audit trail. Approval cards also appear in chat |
| **Observability** | OpenTelemetry spans, JSON logs, live P50/P95/P99, CPU, memory, GPU if present, task outcomes, retries, budget alerts, and "why did Sherin spend more today?" |
| **Currencies** | USD, INR and CAD with a rate history (source, timestamp, base) |

## Run it

**Docker** (PostgreSQL, API, web; seeds demo data on first start):

```bash
docker compose up --build
```

Open http://localhost:8080. Add `--profile qwen` to also run Ollama, then pull the model:

```bash
docker compose exec ollama ollama pull qwen2.5:7b-instruct
```

**Local development:**

```bash
cd backend && uv sync && DATABASE_URL=postgresql+psycopg://sherin:sherin@localhost/flobank uv run uvicorn app.main:app --reload
```

```bash
cd frontend && npm ci && npm run dev
```

Without `DATABASE_URL` the API uses a local SQLite file. The Vite dev server proxies `/api` to port 8000.

## Sherin's portrait

Every screen uses one asset through `SherinAvatar`: **`frontend/public/sherin/sherin-ghibli.png`**. Place the approved
Ghibli-style portrait there. Until it is present, a neutral leaf monogram is shown. No substitute face is generated.

## Tests

```bash
cd backend && uv run pytest
```

```bash
cd backend && TEST_DATABASE_URL=postgresql+psycopg://sherin:sherin@localhost/flobank_test uv run pytest
```

```bash
cd frontend && npm run typecheck && npm test && npm run build
```

```bash
cd frontend && npm run e2e
```

The first command runs 107 backend tests on SQLite; the second runs them on PostgreSQL. The third covers types, 25 unit tests and the build. The last runs 27 browser acceptance checks and needs the API on :8000 and `vite preview` on :4173.

See [docs/TEST_RESULTS.md](docs/TEST_RESULTS.md), [docs/STATUS.md](docs/STATUS.md) (functional, simulated, measured or pending) and
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Screens

| | |
|---|---|
| ![KPI drill-down](docs/screenshots/kpi-drilldown.png) | ![Copilot](docs/screenshots/chat-answer.png) |
| ![Python run awaiting approval](docs/screenshots/python-run-awaiting-approval.png) | ![Agent harness](docs/screenshots/harness-completed.png) |
| ![Guardian block](docs/screenshots/guardian-block.png) | ![Approvals](docs/screenshots/route-approvals.png) |
| ![Token analytics](docs/screenshots/route-tokens.png) | ![System metrics](docs/screenshots/route-metrics.png) |
