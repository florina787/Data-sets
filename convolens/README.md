# ConvoLens AI — Customer Conversation Intelligence

ConvoLens AI helps support and operations leaders answer five questions:

- What problems deserve attention?
- What evidence supports those findings?
- Which improvements should come first?
- Who should own each action?
- How will we know if things improved?

It links each step to the next:

**Conversation data → calculated metrics → evidence-backed investigation → proposed decision → human review → assigned action → impact measurement**

**Flo** is the built-in assistant: *your customer intelligence and decision-support assistant.*

It uses the Kaggle dataset [Customer Support on Twitter](https://www.kaggle.com/datasets/thoughtvector/customer-support-on-twitter) (`twcs.csv`).

| | |
|---|---|
| Backend | Python 3.11+, FastAPI, LangGraph (StateGraph + SQLite checkpoints), LangChain, LangSmith, Pydantic, SQLAlchemy + SQLite |
| Frontend | React 19 + TypeScript, Vite, Tailwind CSS v4, Radix primitives, Recharts, React Flow |
| Retrieval | BM25 keyword search + sentence-transformers/FAISS semantic search, hybrid ranking (RRF) with SQL metadata filters |
| Models | Claude via the Anthropic API or Amazon Bedrock; keys stay on the backend |
| Lockfiles | `backend/uv.lock`, `frontend/package-lock.json` |

## Two explicit modes

| | Demonstration | Connected analysis |
|---|---|---|
| Data | Synthetic fixtures (`data/demo`), clearly labelled | Imported Kaggle CSV |
| Labels | Rules-based analysis (`rules-v1`), labelled as rules | Rules on import; Claude structured extraction when you run a model analysis job |
| Flo | Rules planning and templated answers, no model call | Claude plans and writes; SQL tools produce every number |
| On error | — | Explicit failure; **never** falls back to demonstration |

You switch modes in the top bar. Each mode only shows datasets of its own kind. Counts are always the actual selected counts: an import shows 3,000 conversations only when 3,000 eligible threads were actually selected.

## Quick start (no API keys)

```bash
# Backend
cd convolens/backend
uv sync                                   # add --extra embeddings for semantic search (installs PyTorch)
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

# Frontend (second terminal)
cd convolens/frontend
npm ci
npm run dev                               # http://127.0.0.1:5173, proxies /api to :8000
```

The demonstration datasets load through the real ingestion pipeline at startup.

### Docker Compose

```bash
cd convolens
cp .env.example .env                      # optional: add model / LangSmith settings
docker compose up --build                 # UI at http://127.0.0.1:8080, API at http://127.0.0.1:8000
```

Both ports bind to `127.0.0.1` because there is no user authentication. See [docs/SECURITY.md](docs/SECURITY.md).

## Importing Kaggle data

Pick one of these. Each runs the same pipeline:

- schema validation,
- reply-graph reconstruction,
- seeded selection of up to 3,000 eligible threads,
- redaction,
- language detection,
- rules analysis,
- a manifest of the import.

```bash
cd convolens/backend
uv run python -m app.ingestion.cli kaggle                       # download with kagglehub and import
uv run python -m app.ingestion.cli file /path/to/twcs.csv       # import a downloaded CSV
uv run python -m app.ingestion.cli list                         # datasets with actual counts
```

Or use **Data quality and imports** in the UI:

- **Upload** the CSV (size-limited and schema-checked).
- Import from a **local path** inside `data/imports/`.
- **Download from Kaggle.**

Imports run as background jobs with progress, cancel and resume.

If the full file is too large to move around, `tools/make_upload_csv.py`, `tools/sample_threads.py` and `tools/shrink_archive.py` reduce it. They keep only **complete conversation threads**, so no conversation is split.

## Connected analysis (model)

Set these in `.env`:

- **Anthropic:** `MODEL_PROVIDER=anthropic` and `ANTHROPIC_API_KEY`.
- **Bedrock:** `MODEL_PROVIDER=bedrock` with `BEDROCK_MODEL_ID` and `AWS_REGION`. AWS credentials come from the standard chain.

Then, on an imported dataset:

- **Data quality and imports → Run model analysis:** structured extraction, cached by content hash, model and prompt version. Evidence spans are validated against stored text.
- **Ask Flo** in Connected analysis mode.

LangSmith tracing turns on with `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY`. Payloads are redacted before they are sent.

## Tests and evaluations

```bash
cd convolens/backend && uv run pytest                 # 65 tests
cd convolens/frontend && npm test && npm run typecheck # 7 tests
cd convolens/backend && uv run python -m app.evaluation.run --system rules
uv run python -m app.evaluation.run --system llm --dataset <id> --langsmith   # needs a model
```

Results, including what has **not** been verified, are in [docs/TEST_RESULTS.md](docs/TEST_RESULTS.md).

## Documentation

- [Architecture](docs/ARCHITECTURE.md): graph, state, tools, retrieval, data flow
- [Data dictionary](docs/DATA_DICTIONARY.md): tables, fields, labels, manifest
- [Evaluation](docs/EVALUATION.md): suites, judgment types, per-language reporting
- [Security](docs/SECURITY.md): secrets, redaction, XSS, CSV injection, sessions, access limits
- [Known limitations](docs/KNOWN_LIMITATIONS.md)
- [Test results and acceptance walkthrough](docs/TEST_RESULTS.md)
- [Five-minute leadership demo script](docs/DEMO_SCRIPT.md)

## Repository layout

```
convolens/
  backend/app/        api, ingestion, analytics, retrieval, graph, tools, evaluation, observability, security, models, llm, multilingual
  backend/tests/      pytest suite + fixtures
  frontend/src/       pages, components, charts, maps, assistant, lib
  data/demo/          synthetic fixtures + generator + multilingual reference labels
  data/imports/       your imported CSVs (git-ignored)
  tools/              thread-preserving archive/sample utilities
  docs/
  docker-compose.yml, .env.example
```

The Kaggle data is licensed CC BY-NC-SA 4.0. It is not committed to this repository.
