# Baseline audit and hardening log

Audit of `origin/master` at `71dd252` on 21–22 October 2026, before the hardening changes on branch
`claude/awesome-bohr-jqq4uz`. Everything below was executed; nothing is assumed.

## Environment and structure

| Item | Value |
|---|---|
| Python | 3.13 (requires ≥ 3.11), managed with `uv` (`uv.lock`) |
| Node | 22, managed with `npm` (`package-lock.json`) |
| Backend entry | `backend/app/main.py` (FastAPI): 51 routes in `app/api/routes_data.py`, `routes_flo.py`, `routes_review.py` |
| Frontend entry | `frontend/src/main.tsx` (React 19, Vite) |
| Database | SQLite (`backend/var/convolens.db`), schema from SQLAlchemy models, additive migration in `app/db.py:_add_missing_columns` |
| Agent graph | `backend/app/graph/builder.py` (`StateGraph(FloState)`, 10 nodes, conditional edges, SQLite checkpointer) |
| Model adapter | `backend/app/llm/provider.py` (`get_chat_model`: Gemini, Anthropic, Bedrock) |
| Tools | `backend/app/tools/catalog.py`: 11 typed LangChain `StructuredTool`s, read-only |
| Retrieval | `backend/app/retrieval/index.py` (BM25 + FAISS, reciprocal-rank fusion), `gemini_embed.py` |
| Evaluation | `backend/app/evaluation/run.py`, reference sets in `app/evaluation/datasets/` |
| Docker | `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile` (nginx + CSP) |

## Baseline checks (before changes)

| Check | Result |
|---|---|
| `uv run pytest` | 76 passed |
| `npm test` (vitest) | 8 passed |
| `tsc` | passed |
| Fresh export of `origin/master`: `uv sync --frozen`, pytest, `npm ci`, `npm test`, `npm run build`, server health | all passed; only demonstration datasets present (the Kaggle data is not in the repository) |

## Data baseline (direct SQL)

| Measure | Value |
|---|---|
| Conversations (dataset `ds_d5b54d698d7f`) | 3,000 (3,000 distinct keys) |
| Messages | 11,359: 6,341 customer, 5,018 support |
| Conversations starting with a customer message / with a support reply | 3,000 / 3,000 |
| Gemini labels (`extract-batch-v1`, ok) | 440 conversations; 71 with only failed attempts |
| Active labels on the 3,000 | rules (`rules-v1`) |
| Human reviews | 0 |
| Gemini embeddings cached | 665 texts (the 300-conversation sample) |

## Defects found and status

| # | Severity | Defect | Status |
|---|---|---|---|
| H1 | High | Streamed usage summed per chunk; Gemini reports cumulative usage, so tokens were over-counted 13–35× and a live action proposal would trip the 24k budget at `request_action_approval` | **Fixed** (`app/llm/usage.py`; verified live and by a test that fails without the fix) |
| H1b | High | Live: `gemini-3.5-flash-lite` planned no action step for "Propose an action…" | **Fixed**: standard action plan used when the user explicitly asks; verified live to reach approval |
| H2 | High | Only 440 of 3,000 have Gemini labels | **Open**: needs ≈171 model requests (authorization requested) |
| H3 | High | No human-labelled accuracy on real data | **Open**: metrics implemented; needs ≥100 human reviews |
| M1 | Medium | Semantic search unavailable on the 3,000 | **Open**: needs 5,641 embeddings (authorization requested) |
| M2 | Medium | No live-LLM integration test | Open |
| M3 | Medium | No cost tracking; LangSmith not configured | Open |
| L1 | Low | Model-missing error did not mention Gemini | **Fixed** |
| L2 | Low | Tool events carried no arguments | **Fixed**: arguments shown in Flo's tool activity |
| — | — | No CI | **Added** `.github/workflows/convolens-ci.yml` |
