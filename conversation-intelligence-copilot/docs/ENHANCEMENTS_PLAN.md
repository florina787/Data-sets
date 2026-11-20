# Six enhancements: audit and implementation plan

These extend the existing graph rather than rebuilding it. The four assignment questions, the registered-operation
contract (no LLM-written SQL), FAISS hybrid retrieval and the provider-neutral LLM client stay as they are.

## Audit: what already exists and where each feature hooks in

| Existing piece | File | Reused by |
|---|---|---|
| Typed graph state, conditional routing, traced nodes (`execution_trace`) | `agents/state.py`, `agents/graph.py`, `agents/tracing.py` | Router, Decision Replay |
| Rules intent parser + `rules_first` strategy | `agents/intent_rules.py`, `agents/intent_agent.py` | Router (rules are the zero-LLM path) |
| Registered DuckDB operations (13) | `analytics/query_registry.py` | X-Ray, Root Cause (new operations) |
| Wilson CI, two-proportion test | `analytics/stats.py` | Root Cause |
| Turn-by-turn trajectory | `analytics/trajectories.py` | X-Ray |
| Deterministic chart planner | `visualization/planner.py` | Dynamic dashboards |
| QA agent (11 checks), numeric grounding | `agents/qa_agent.py`, `agents/grounding.py` | Evidence Challenger |
| Telemetry SQLite (`node_events`, `llm_calls`) | `observability/store.py` | Decision Replay, token accounting |
| Usage counting (cumulative stream max) | `llm/usage.py` | Honest token reporting |

Gap found during the audit: missing usage metadata becomes `Usage(0, 0, 0)`, so it can't be told apart from a call
that really used zero tokens. This is fixed as part of the Router work.

## Plan (P0 first)

1. **Zero-LLM Intelligence Router (P0).** `agents/router.py`.
   - Modes: `auto | analytics_only | hybrid_ai`, set on each request (`analysis_mode`).
   - AUTO sends questions the rules recognise and that have a deterministic narrative to analytics only. It uses the LLM
     when the question asks for interpretation (why / explain / recommend / summarise / root cause) or the rules can't
     parse it.
   - Each response carries the route, the reason, LLM calls made and tokens.
   - Tokens are `null` when the provider did not report them, and `0` only when no call was made.
   - Dataset-preprocessing tokens are reported separately from per-query tokens.
2. **Query-driven dynamic dashboards (P0).** `visualization/dashboard.py`.
   - Builds a dashboard spec from the verified results of each question: title, KPI strip, sections with a "why this
     chart" rationale, active filters, and drill-down refinements.
   - The UI renders it as a dashboard view of the answer, with refinement chips that re-ask with a changed window or
     filter.
3. **Conversation X-Ray (P0).** New registered operation `conversation_xray`.
   - Message-level timeline with phases, repeated concerns, escalation signals and communication gaps (unacknowledged
     negative turns, repeated holds or verification, a closing action that doesn't fit the issue).
   - Every finding cites message IDs.
   - The UI syncs the timeline and transcript both ways on `message_id`.
4. **Root Cause Investigator (P1).** New operation `root_cause_investigation` and intent `root_cause`.
   - For a topic (or the top negative topic in scope), compares negative and non-negative conversations on observable
     factors.
   - Reports lift, Wilson CI, two-proportion p-value, support, and a temporal-precedence check (does the factor appear
     before the first negative customer turn?).
   - Lists alternative explanations (product or agent concentration) and states uncertainty.
   - Language is associational only.
5. **AI Decision Replay (P1).** `GET /api/replay/{request_id}`.
   - A sanitised, ordered replay of the routing decision, nodes, registered operations with params, row counts and
     timings, FAISS searches, LLM calls (prompt id@version, tokens or null, latency, cache), and QA.
   - The UI shows it inline per response, expandable, with step-through.
6. **Analytical Evidence Challenger (P1).** `agents/evidence_challenger.py`, run in the QA node. It checks that:
   - each quoted excerpt matches its source message;
   - small samples are disclosed;
   - each ranked claim has evidence coverage;
   - counter-evidence (non-negative share) is shown;
   - causal wording is qualified.
   - Results appear in a new "Evidence review" section.

Folded in from earlier requests:
- Per-method retrieval ranks (MiniLM, LSA, RRF) on evidence cards.
- A retrieval-mode toggle in Explorer.
- A retrieval backends panel in Metrics.

Each feature gets unit/integration tests; the UI gets Playwright coverage. README, ARCHITECTURE, EVALUATION, the demo
walkthrough and known limitations are updated last, using measured numbers only.
