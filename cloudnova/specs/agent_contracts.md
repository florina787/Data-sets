# Spec 4 — Agent Contracts

Status: **APPROVED v1.0**. One local model (Qwen via an OpenAI-compatible endpoint), one
supervisor, several *logical* agents implemented as tools behind a single harness (adapted from
FloPilot `harness/runtime.py`). No multi-agent framework: the routing is deterministic first,
LLM second, which keeps the financial path testable without a model.

| Agent (tool) | Permission | Input | Output | Uses LLM? |
|---|---|---|---|---|
| **Supervisor** `route` | — | question, session | intent ∈ analytics, data_quality, general, out_of_scope, clarify | keyword/semantic rules; LLM only for tie-break when available |
| **Financial analytics** `run_metric_query` | read | `QueryPlan` | result rows + SQL | no |
| **Financial analytics** `run_llm_sql` | read | question | SQL → guarded result | yes (generates SQL only) |
| **Data quality** `data_quality_report` | read | topic (duplicates, dates, fx, emails, conflicts…) | audit rows + rule text | no |
| **Visualization** `suggest_chart` | read | result shape | chart spec (type, x, y) from real rows | no |
| **General knowledge** `general_chat` | read | question + last 6 turns | text | yes; if Qwen is down → `llm_unavailable` error, no fabricated text |
| **Governance** `guard_sql`, `ground_answer` | — | SQL / narrative | allow/deny + reason | no |

Contracts:

* The supervisor never returns a number that was not produced by `run_metric_query` /
  `run_llm_sql` / `data_quality_report`.
* Out-of-scope / unanswerable-from-data questions (e.g. "*why* did account X churn?", "what will
  revenue be next year?", live FX) return intent `out_of_scope` with an explanation of what the data
  can and cannot support — this is the deliberate boundary tested by the expected-failure eval.
* Budgets per request (config): `MAX_STEPS=6`, `LLM_TIMEOUT_S=60`, `MAX_LLM_TOKENS=512`.
* Memory: per-session SQLite rows `(session_id, turn, question, intent, plan_json, answer)`.
  Follow-ups re-use the last `plan_json`. `DELETE /api/sessions/{id}` clears it.
* Trace: every tool call appends `{step, tool, ms, status, detail}`; persisted for the Agent
  Control Tower.
