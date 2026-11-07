# Spec 3 — Query Interface & SQL Governance

Status: **APPROVED v1.0**. Implementation: `app/agent/`, `app/governance/sql_guard.py`, `app/api.py`.

## 1. Entry points (all share one `Copilot.ask()` code path)

| Interface | Command | Notes |
|---|---|---|
| CLI demo (the "single command") | `python -m app` | builds data if missing, runs the six stakeholder questions, prints answer + SQL |
| CLI ask | `python -m app ask "question"` | one question; `--session ID` keeps follow-up context |
| CLI chat | `python -m app chat` | interactive multi-turn REPL |
| HTTP API + UI | `python -m app serve` | FastAPI on `:8000`; UI at `/` |
| Evals | `python -m evals` | see `evaluation_plan.md` |

### `POST /ask`
Request: `{"question": str (1..1000 chars), "session_id": str | null}`
Response (`AskResponse`, schema_version `1.0`):
```json
{
  "session_id": "s_…", "intent": "analytics|data_quality|general|out_of_scope|clarify",
  "answer": "natural-language answer (numbers copied from result rows, never generated)",
  "sql": "SELECT … (exact SQL executed, or null)",
  "planner": "semantic|llm_sql|none",
  "metric_definitions": [{"id": "paid_revenue", "definition": "…"}],
  "filters": {"invoice_year": 2024},
  "result": {"columns": [...], "rows": [[...]], "row_count": 3, "truncated": false},
  "chart": {"type": "bar|line|doughnut|table", "x": "...", "y": ["..."]} | null,
  "caveats": ["…"], "sources": ["invoices", "accounts"],
  "trace": [{"step": "route", "ms": 1, "detail": "…"}, …],
  "llm": {"provider": "qwen|none", "model": "…", "used": true, "latency_ms": 812}
}
```
Errors: `{"schema_version":"1.0","code":"…","message":"safe text","retryable":bool}` with HTTP
400 (`invalid_question`), 422 (`sql_rejected`), 503 (`llm_unavailable` — only for *general chat*;
analytics never needs the LLM), 500 (`internal_error`, no stack trace).

Other routes: `GET /health`, `GET /api/kpis`, `GET /api/dashboard`, `GET /api/data-quality`,
`GET /api/traces`, `GET /api/sessions/{id}`.

## 2. Two planners, one executor

1. **Semantic planner (deterministic, default for data questions).** Parses the question into a
   `QueryPlan(metric, group_by, filters, order, limit, grain)` using the metric/dimension catalog
   (synonym lists: "revenue/sales/billings", "by region/per plan", "in 2024", "Enterprise",
   "EMEA", "top 5", "pending or failed"…). The plan is compiled to SQL from the approved metric
   definitions. It composes — any catalog metric × any dimension × any filter — so it is **not** a
   question→answer lookup table. Follow-ups ("only Enterprise", "now by plan", "as a chart")
   *patch* the previous plan stored in the session.
2. **LLM SQL planner (local Qwen, optional).** Used when the semantic planner cannot build a
   confident plan (`confidence < 0.6`) and the LLM is reachable. Qwen gets: the schema, the metric
   definitions (as SQL snippets), 6 worked examples, and the question in a delimited block. It must
   return one SQL statement. That SQL goes through the same guard + executor.
3. If neither works → `clarify` intent with suggestions; never a guessed number.

Numbers in `answer` are rendered from result rows by a template; the LLM may *phrase* an
explanation, but the response validator rejects an LLM narrative containing a number that is not
present in the result rows (grounding check).

## 3. SQL governance (defence in depth — not a keyword blacklist)

1. **Structural validation** with `sqlglot` (DuckDB dialect): exactly one statement; root must be
   `SELECT` / `UNION` / `WITH … SELECT`; every table reference ∈ {`invoices`, `accounts`,
   `monthly_revenue`, `dq_issues`, `dedup_conflicts`} or a CTE name; every column must exist in the
   referenced schema (unknown column → `sql_rejected: unknown column`); no table functions
   (`read_csv`, `read_parquet`, `glob`, …); no `COPY/ATTACH/INSTALL/LOAD/PRAGMA/SET/CALL/EXPORT`.
2. **Database-level read-only**: queries run on a connection opened with `read_only=True` to the
   built DuckDB file, and `enable_external_access=false`, `lock_configuration=true` so a statement
   cannot re-enable file/network access or load extensions.
3. **Resource limits**: result rows capped (`MAX_RESULT_ROWS`, default 200, `truncated` flag);
   query timeout (`QUERY_TIMEOUT_S`, default 10 s) enforced via `conn.interrupt()`; DuckDB
   `memory_limit` and `threads` set from config.
4. **Prompt-injection handling**: the question is passed to the LLM inside a delimited
   `<question>` block; instruction-like text (regex reused from FloPilot `security.py`) is flagged
   in the trace; the LLM cannot call anything except the read-only SQL tool; data never becomes
   instructions (only schema + aggregated results are shown to the model).
5. Every executed or rejected query is logged to the trace store (SQLite `data/runtime/traces.db`)
   with latency and outcome. PII (`contact_email`) is masked in result rows unless
   `ALLOW_PII=true`.
