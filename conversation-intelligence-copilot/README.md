# Conversation Intelligence Copilot

**An agentic decision-intelligence workspace for contact-centre analysts and leadership.** Ask a question in plain language; a LangGraph supervisor routes it to specialist agents that run deterministic analytics over the customer-support conversations, retrieve source evidence, explain the result (with Gemini when available), choose charts, verify the answer and record how it was produced.

> *Ask a question. Understand the evidence. Explore the visualisations. Make a decision.*

![Home](docs/screenshots/01-home.png)

| Q1 · negative topics | Q4 · leadership priorities |
|---|---|
| ![Q1](docs/screenshots/02-q1-negative-topics.png) | ![Q4](docs/screenshots/05-q4-leadership.png) |
| **Agent Harness (real execution trace)** | **Q3 · sentiment trajectory** |
| ![Harness](docs/screenshots/12-agent-harness.png) | ![Q3](docs/screenshots/04-q3-trajectory.png) |

More screenshots: [`docs/screenshots/`](docs/screenshots) (coaching, memory follow-ups, retrieval, explorer, dashboards, prompt library, metrics, governance, drilldown, mobile).

## What it does

* **The four assignment questions**, end to end: top-5 negative topics in the last month *represented in the data*; agents who may benefit from empathy/communication coaching (with a sample-size gate and evidence); a selected conversation's sentiment trajectory; the recurring concerns leadership should review first (transparent priority score, sensitivity analysis, owners).
* **General analytical Q&A** over 13 registered operations (distribution, trend, frequency, comparisons, resolution fit, conversation lists and detail, agent profile, coverage), plus follow-ups ("compare the top two", "previous month", "the first one", "why was this ranked first?", "which findings are uncertain?", "summarise for leadership") — and honest refusals for what the data cannot answer.
* **All three bonus extensions**: knowledge retrieval (FAISS), a specialised LLM classification agent (resumable Gemini labelling), and session memory.
* **Enterprise layer**: nine-page UI, validated dynamic charts with drilldown/export, Agent Harness, prompt library, system metrics, governance with blind human review, audit trail, dataset modes.

## How it works

```
Analyst question
  → input validation → session memory → intent (Gemini structured | rules)
  → supervisor/planner (resolve references, date window, registered operations)
  → specialist agent (topic | sentiment | coaching | leadership | analytics)  ‖  retrieval (FAISS)
  → evidence assembly → explanation (Gemini, numeric-grounding check | deterministic)
  → visualisation planner → QA agent → governance agent → response → memory + telemetry
```

Numbers are **computed, never generated**: counts, rates, ranks and chart data come from registered DuckDB operations; the QA agent rejects answers whose numbers are not in the verified results. Full design: [ARCHITECTURE.md](ARCHITECTURE.md).

## Quick start

Prerequisites: Python 3.12+ with [uv](https://docs.astral.sh/uv/), Node 22+.

```bash
cd conversation-intelligence-copilot
cp .env.example .env          # optional: add GEMINI_API_KEY
make install                  # uv sync + npm ci
make prepare                  # raw zip → data/processed/analytics.duckdb (≈30 s)
make index                    # FAISS index (≈15 s)
make dev                      # API :8000 + UI :5173
```

Open http://localhost:5173. API docs: http://localhost:8000/docs.

Docker: `docker compose up --build` → UI on http://localhost:8080 (the backend prepares data and the index on first start). *The images were written but could not be built in the development sandbox (Docker Hub / ECR anonymous-pull rate limits), so they are not verified end to end.*

### Commands

| Command | What it does |
|---|---|
| `make prepare` | Ingest, validate, label, build DuckDB + manifests |
| `make index` | Build the retrieval index |
| `make label` | Optional: label unique messages with Gemini (resumable); then `LABEL_SOURCE=gemini make prepare` |
| `make synthetic` | Optional: generate 120 tagged synthetic demo conversations (then `make prepare index`, `ENABLE_SYNTHETIC_DEMO=true`) |
| `make test` | Backend pytest (97) + frontend typecheck and Vitest (8) |
| `make e2e` | Playwright end-to-end (10) — starts the servers if needed |
| `make evaluate` | Evaluation on the real data → `docs/evaluation/EVALUATION_RESULTS.md` |
| `make screenshots` | Re-capture `docs/screenshots` from a running app |
| `make report` | Generate the submission DOCX and the engineering PDF |

## Configuration

All settings are environment variables (see [`.env.example`](.env.example)); nothing secret is hardcoded.

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | — | Enables Gemini. Without it the app runs in deterministic mode and says so. |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Any Flash / Flash-Lite model your key can use |
| `GEMINI_REQUESTS_PER_MINUTE`, `GEMINI_MAX_CONCURRENCY` | 10, 2 | Client-side rate limiting |
| `GEMINI_MAX_RETRIES`, `GEMINI_TIMEOUT_SECONDS` | 3, 45 | Retry and timeout budget |
| `GEMINI_INPUT_COST_PER_MTOK`, `GEMINI_OUTPUT_COST_PER_MTOK` | 0.30, 2.50 | Cost *estimates* (USD per 1M tokens) — set to your tier |
| `LLM_ENABLED` | true | Kill switch for all model calls |
| `LABEL_SOURCE` | rules | `gemini` uses Gemini labels where present |
| `EMBEDDING_BACKEND`, `EMBEDDING_MODEL` | auto, all-MiniLM-L6-v2 | auto falls back to local LSA if the model can't load |
| `DATASET_MODE`, `ENABLE_SYNTHETIC_DEMO` | original, false | Dataset modes |
| `MIN_AGENT_CONVERSATIONS` | 3 | Coaching sample-size gate |
| `SESSION_RETENTION_DAYS` | 30 | Memory retention |
| `ENABLE_LANGSMITH` | false | Turns on LangSmith tracing (needs `LANGSMITH_API_KEY`) |
| `DATABASE_PATH`, `MEMORY_DATABASE_PATH`, `FAISS_INDEX_PATH`, … | `data/…` | Storage locations |

## Models, dependencies and cost

| Component | Choice | Notes |
|---|---|---|
| LLM | Google Gemini (Flash) via `google-genai` | Intent, grounded explanation, batch classification. **API key required for model features.** |
| Orchestration | LangGraph (+ SQLite checkpointer) | |
| Analytics | DuckDB, pandas, SciPy | Exact, deterministic |
| Retrieval | FAISS; Sentence-Transformers MiniLM (optional extra) or local LSA (scikit-learn) | Local, free |
| Memory / telemetry | SQLite | |
| API | FastAPI, Pydantic v2 | |
| UI | React 18, TypeScript, Vite, Tailwind, Radix (shadcn-style), Recharts, React Flow, Framer Motion, Lucide | |
| Reports | python-docx, ReportLab, matplotlib | |

**Cost assumptions.** Without a key: $0. With Gemini Flash, a chat turn makes at most two small calls (intent ≈ 600 input tokens; explanation ≈ 3–6k input / ≤ 1.2k output), i.e. roughly **$0.003–0.005 per question** at the default rates; cached repeats are free. Labelling the 426 unique texts takes ~18 batched calls (≈ 50k tokens) — well under $0.10, and within free-tier quotas. Costs are estimated per call from actual usage metadata and shown on System Metrics.

## The dataset

Syncora.ai Customer Support Conversation sample (Kaggle), 3,000 synthetic conversations / 41,965 messages, Aug–Dec 2025 — details, preparation steps and data dictionary in [docs/dataset/DATASET.md](docs/dataset/DATASET.md); every interpretation is in [ASSUMPTIONS.md](ASSUMPTIONS.md). Key properties the app surfaces rather than hides: messages end in random filler tokens (removed); timestamps are not in turn order (turn index used); ~1 agent per conversation (no fair per-agent ranking); most topic differences in negative rate are not statistically significant.

## Evaluation (summary)

| | |
|---|---|
| Q1 vs an independent oracle | exact match (682 conversations, 239 negative, top-5 counts) |
| End-to-end QA pass rate | 100% of 51 requests (11 checks each) |
| Unsupported questions refused | 6/6 |
| Intent (rules fallback) | 100% tuning set · **50% held-out paraphrases** (7/10 misses refused safely) |
| Retrieval (LSA) topic P@5 | 36.7% vs 12.5% random |
| Latency (deterministic, local) | p50 159 ms · p95 602 ms |

Details and limitations: [EVALUATION.md](EVALUATION.md).

## Sample requests and outputs

[`examples/requests/`](examples/requests) and [`examples/outputs/`](examples/outputs) — generated from real runs (`uv run python -m scripts.generate_examples`), as JSON and readable Markdown: Q1 with follow-ups, Q2, Q3, Q4 with "why" and "uncertain" follow-ups, retrieval, an unsupported question.

```bash
curl -s localhost:8000/api/chat -H 'Content-Type: application/json' \
  -d '{"question":"Which recurring customer concerns should contact-centre leadership review first?"}' | jq '.headline, .recommendations[0]'
```

## Status and limitations

* **Gemini was not reachable during development** (the provided credential returned `401 API_KEY_SERVICE_BLOCKED`). The adapter, prompts, labelling pipeline and grounding checks are implemented and tested against a scripted SDK, but live behaviour is unverified. Everything shown in the screenshots ran in deterministic mode.
* Sentence-Transformers weights could not be downloaded (Hugging Face blocked by network policy); retrieval used the LSA fallback.
* Sentiment/empathy mappings are developer judgements; human-agreement metrics need labels from the in-app review panel.
* No authentication/RBAC (see [SECURITY.md](SECURITY.md)); single-node storage.

Implementation status per feature: [docs/IMPLEMENTATION_MATRIX.md](docs/IMPLEMENTATION_MATRIX.md) · requirements traceability: [docs/requirements/REQUIREMENTS_MATRIX.md](docs/requirements/REQUIREMENTS_MATRIX.md) · reports: [docs/reports/](docs/reports) · demo script: [docs/interview/DEMO_SCRIPT.md](docs/interview/DEMO_SCRIPT.md).

## Repository layout

```
backend/   FastAPI app (app/), scripts/, tests/ (unit, integration, evaluation datasets, fixtures)
frontend/  React app (src/), Playwright e2e/
data/      raw/ (supplied zip), synthetic/, manifests/ (profile, quality, evaluation); processed/ and indexes/ are generated
docs/      architecture-adjacent docs, dataset, evaluation, interview, reports, screenshots, requirements
examples/  sample requests and outputs
```

## Production roadmap

Managed warehouse + vector store, job queue for labelling, SSO/RBAC/tenant isolation, secret manager, OpenTelemetry/LangSmith tracing, CI/CD with evaluation gates, prompt/model A/B with human-labelled sets, retention policies, horizontal API scaling. None of these are implemented here.

## License

MIT — see [LICENSE](LICENSE). The dataset remains subject to its original Kaggle/Syncora terms.
