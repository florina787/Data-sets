# Requirements traceability

Scope key: **A** = assignment-required · **B** = optional bonus in the brief · **E** = our enterprise enhancement.

## Business objective and personas

Help contact-centre **analysts** (investigate patterns, find evidence), **QA / team leads** (review communication quality fairly) and **operations / leadership** (decide what to review first) turn customer-support conversations into evidence-backed decisions.

## Functional requirements

| ID | Scope | Requirement | Implementation | Tests / evidence |
|---|---|---|---|---|
| FR-001 | A | Ingest and document the supplied Syncora sample | `data/ingestion.py`, `data/pipeline.py`, `docs/dataset/DATASET.md` | `test_data.py`, manifests |
| FR-002 | A | Q1 top-5 negative topics in the last month represented | `analytics/topics.py`, `time_windows.py` | `test_rank_negative_topics_*`, `test_q1_end_to_end`, oracle match, E2E Q1 |
| FR-003 | A | Q2 agents who may need empathy/communication coaching, with evidence | `analytics/coaching.py` | `test_coaching_*`, `test_q2_*`, E2E Q2 |
| FR-004 | A | Q3 sentiment change over a selected conversation | `analytics/trajectories.py` | `test_sentiment_trajectory_*`, `test_q3_*`, E2E Q3 |
| FR-005 | A | Q4 recurring concerns leadership should review first | `analytics/prioritization.py` | `test_leadership_*`, `test_q4_*`, E2E Q4 |
| FR-006 | A | Coordinated analysis, not a single prompt | `agents/graph.py`, `supervisor.py` | `test_stream_emits_real_node_events_in_order` |
| FR-007 | A | Clear, evidence-based, quantitative, explainable answers with uncertainty | `agents/narrative.py`, `retrieval/evidence.py`, QA | `qa_agent` checks, evaluation §4 |
| FR-008 | A | Support other analytical questions; refuse unsupported ones | 13 registered operations, `intent_rules.py` | intent tests, evaluation (6/6 refused) |
| FR-009 | A | Document models, dependencies, keys, costs, orchestration | README, ARCHITECTURE | — |
| FR-010 | B | Knowledge retrieval with source references | `retrieval/*` | `test_conversations_and_retrieval`, retrieval evaluation |
| FR-011 | B | Specialised ML/LLM analytical agent | `labeling/gemini_labeler.py` (resumable Gemini labelling), specialist agents | scripted-SDK tests; live run not possible (key blocked) |
| FR-012 | B | Memory across turns | `memory/store.py`, `supervisor.py` | `test_follow_up_chain_uses_memory`, E2E follow-up |
| FR-013 | E | Premium chat-first UI with nine pages | `frontend/src/pages/*` | Playwright `all pages render`, screenshots |
| FR-014 | E | Dynamic, validated visualisations with drilldown and export | `visualization/*`, `ChartRenderer.tsx`, `ChartCard.tsx` | chart consistency QA check, E2E drilldown, Vitest |
| FR-015 | E | Agent Harness inspector with real execution traces | `tracing.py`, telemetry store, `Harness.tsx` | E2E harness test |
| FR-016 | E | Prompt library with versions, schemas, test cases, usage | `prompts/*`, `Prompts.tsx` | `test_prompt_registry_*` |
| FR-017 | E | System metrics and adoption analytics from real telemetry | `observability/store.py`, `Metrics.tsx` | API tests |
| FR-018 | E | Governance page, audit log, blind human review | `governance/*`, `Governance.tsx` | `test_human_review_metrics` |
| FR-019 | E | Dataset modes (original / synthetic / combined) | `generate_synthetic.py`, `db.where`, header selector | supervisor and API tests |

## Non-functional requirements

| ID | Requirement | Implementation | Evidence |
|---|---|---|---|
| NFR-001 | Numbers computed deterministically | Registered DuckDB operations | oracle match; QA grounding |
| NFR-002 | Responsive interaction | Real progress streaming (SSE), skeletons | p50 159 ms / p95 602 ms (deterministic) |
| NFR-003 | Bounded model use | Rate limiter, timeouts, retries, circuit breaker, budgets | adapter tests |
| NFR-004 | Graceful degradation | Deterministic intent/explanation; retrieval failure tolerated | outage + corrupt-index tests |
| NFR-005 | Reproducible | Locked deps (uv.lock, package-lock), idempotent pipeline, Makefile, Compose | CI workflow |
| NFR-006 | Accessible, responsive | Keyboard focus rings, labels, chart summaries, reduced motion, mobile layout | E2E mobile overflow test |
| NFR-007 | Observable | Node events, LLM calls, audit, UI events | Harness / Metrics pages |

## Governance requirements

| ID | Requirement | Evidence |
|---|---|---|
| GOV-001 … GOV-010 | See [SECURITY.md](../../SECURITY.md) (secrets, PII, pseudonymisation, injection, tool safety, grounding, coaching safeguards, synthetic isolation, retention; RBAC not implemented) | tests listed there |

## Evaluation requirements

| ID | Requirement | Evidence |
|---|---|---|
| EVAL-001 | Exact analytical correctness on fixtures | `test_analytics.py` |
| EVAL-002 | Independent check on real data | Q1 oracle |
| EVAL-003 | Intent evaluation incl. held-out | 100% tuning / 50% held-out |
| EVAL-004 | Retrieval evaluation | P@5, hit-rate, MRR, latency |
| EVAL-005 | Grounding / citation / chart consistency | QA pass rates |
| EVAL-006 | Classification metrics vs human labels | Implemented (Governance → Human review); **no labels submitted yet** |
| EVAL-007 | Failure testing | §1 of EVALUATION.md |

## Acceptance criteria (brief §32) — status

| Criterion | Status |
|---|---|
| Dataset ingested and profiled | Met |
| Four questions work end to end | Met (API, graph, UI, E2E) |
| Gemini integrated through a configurable adapter | Implemented and tested with a scripted SDK; **live calls blocked** (401 API_KEY_SERVICE_BLOCKED) |
| LangGraph coordinates real operations | Met |
| Deterministic numbers | Met |
| Evidence supports claims; retrieval returns valid evidence | Met |
| Memory supports follow-ups | Met |
| Charts from actual data; chat central; professional, responsive UI | Met |
| Harness shows actual traces | Met |
| Sensitive data handled; model failures handled | Met (regex PII; see gaps) |
| Automated tests pass; evaluation documented | Met |
| Startable with documented commands | Met locally; Docker images not built in the sandbox (registry rate limit) |
| Short submission report generated | Met (`docs/reports/`) |
| No keys committed; no fabricated metrics | Met |
