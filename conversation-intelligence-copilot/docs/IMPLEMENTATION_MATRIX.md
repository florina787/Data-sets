# Implementation matrix (Definition of Done)

Status vocabulary: **Implemented and verified** (code integrated, reachable, tested, documented) · **Implemented but not fully verified** · **Partial** · **Not implemented**.

| Feature | Status | Evidence | Tests | Limitations |
|---|---|---|---|---|
| Dataset ingestion, schema mapping, quality report, profile | Implemented and verified | `data/*`, manifests | `test_data.py` | Regex PII only |
| Deterministic labelling (topic, product, domain, sentiment, empathy, resolution) | Implemented and verified | `labeling/rules.py` | `test_labeling.py` | Mapping is a developer judgement |
| Q1 negative topics (last month in data) | Implemented and verified | chat, Sentiment page | fixture, oracle, graph, E2E | Rate differences not significant (reported) |
| Q2 coaching (sample-size gated) | Implemented and verified | chat, Coaching page | fixture, graph, E2E | ≤ 2 conversations per agent in data |
| Q3 conversation trajectory | Implemented and verified | chat, Explorer | fixture, graph, E2E | Ordinal template scores |
| Q4 leadership priorities with sensitivity and owners | Implemented and verified | chat, Leadership page | fixture, graph, E2E | No cost/churn data |
| General Q&A (13 operations), unsupported refusal | Implemented and verified | registry | intent + eval | Rules parser brittle on paraphrases (50% held-out) |
| LangGraph orchestration, conditional + parallel routing, checkpointing | Implemented and verified | `agents/graph.py` | stream/graph tests | — |
| Gemini adapter (structured output, repair, rate limit, retries, circuit, cache, tokens/cost) | Implemented but not fully verified | `llm/*` | scripted-SDK tests | Live API never reached (key blocked) |
| Gemini intent and grounded explanation | Implemented but not fully verified | `intent_agent.py`, `nodes.explanation` | scripted tests incl. grounding rejection | Not run live |
| Resumable Gemini batch labelling + coverage | Implemented but not fully verified | `gemini_labeler.py`, `make label` | partial-coverage pipeline test | Not run live |
| Knowledge retrieval (FAISS, filters, evidence) | Implemented and verified | `retrieval/*`, Explorer semantic search | API + eval | LSA fallback; MiniLM not downloadable here |
| Session memory and follow-ups | Implemented and verified | `memory/store.py` | memory/graph/E2E | No cross-session memory |
| QA agent and numeric grounding | Implemented and verified | `qa_agent.py`, `grounding.py` | graph + eval | Grounding checks numbers, not wording |
| Governance (PII, injection flags, safeguards, audit) | Implemented and verified | Governance page | security tests | No auth/RBAC |
| Blind human review + agreement metrics | Implemented and verified (mechanics) | Governance page | API test | No real human labels collected yet |
| Premium UI: 9 pages, charts, drilldowns, export, harness | Implemented and verified | `frontend/` | Vitest 8, Playwright 10, screenshots | PNG export depends on browser support |
| Telemetry and adoption analytics | Implemented and verified | Metrics page | API tests | Single-node SQLite |
| Prompt library (versions, schemas, tests, usage) | Implemented and verified | Prompts page | registry tests | Lifecycle via PR, no approval UI |
| Synthetic / combined dataset modes | Implemented and verified | header selector (when enabled) | supervisor/API tests | Demo data only |
| Docker Compose packaging | Implemented but not fully verified | Dockerfiles, compose | — | Image build blocked by registry rate limits in sandbox |
| CI (pytest, typecheck, Vitest, build) | Implemented but not fully verified | `.github/workflows/cic-ci.yml` | — | Runs on the next PR |
| Sentence-Transformers embeddings | Partial | adapter + optional extra | — | Weights could not be downloaded here |
| LangSmith tracing | Partial | `ENABLE_LANGSMITH` sets env for LangGraph | — | Requires a LangSmith key; not exercised |
| Authentication / RBAC / multi-tenancy | Not implemented | — | — | See SECURITY.md |
| Image generation for answers | Not implemented (deliberate) | — | — | Charts and real screenshots only; no decorative images |
