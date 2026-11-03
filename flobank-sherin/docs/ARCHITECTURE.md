# Architecture

```
React 19 + TypeScript + Tailwind + Plotly + React Flow   (frontend/)
   │  /api (JSON, server-sent events)
FastAPI ── OpenTelemetry middleware ── JSON logs           (backend/app/main.py)
   ├── finance/engine.py      deterministic money engine (single source of truth)
   ├── copilot/service.py     intent → engine call → answer + chart + dashboard link
   ├── agents/harness.py      LangGraph StateGraph + SqliteSaver checkpoints
   │     └── agents/tools.py  deterministic tools (AST, YAML, logs, risk, ESG …)
   │     └── agents/llm.py    optional local Qwen (Ollama), measured tokens
   ├── guardian/engine.py     pre-trade controls, PASS / REVIEW / BLOCK / INSUFFICIENT_DATA
   ├── approvals/service.py   roles, segregation of duties, policy blocks, audit
   └── observability/telemetry.py  spans, latency percentiles, host metrics, alerts
PostgreSQL (SQLite for zero-setup runs)
```

## Data model

Money is `NUMERIC(18,2)` in USD. Every business table carries `data_class` (`synthetic` | `measured`). Cost tables
also carry `basis` (`actual` | `estimated` | `forecast`). Each API call takes a `dc` parameter and never mixes the two classes.

| Table | Purpose |
|---|---|
| `ledger_lines` | Daily bank revenue and opex by category (incl. "Technology – Sherin AI") |
| `budgets` | Monthly budgets for bank revenue, bank opex and AI cost |
| `agent_tasks` | One unit of agent work with its six workflow cost components and a baseline snapshot |
| `ai_cost_records` | Every AI cost; workflow categories are generated 1:1 from task costs, so they reconcile |
| `token_usage` | Per model call: provider (local_qwen / paid_api), tokens, API cost, local compute and electricity cost |
| `human_baselines` | Configured human-only hours and rate per workflow type |
| `revenue_attribution`, `realized_savings` | AI-attributed fee revenue (with method) and booked savings |
| `portfolios`, `positions`, `portfolio_transactions`, `trade_proposals` | Investment data for Guardian |
| `approvals`, `audit_log` | Human-in-the-loop decisions and an append-only audit trail |
| `harness_runs` | Plan, trace and result of each agent run (LangGraph state is checkpointed separately) |
| `conversations`, `messages` | Persistent, searchable copilot history with structured payloads |
| `fx_rates` | Rate history with source, timestamp and data class |

## Agent harness

```
plan_task ─▶ execute_step ─┬─▶ execute_step (next step)
                           └─▶ verify ─┬─▶ approval_gate (interrupt) ─▶ finalize
                                       └─▶ finalize
```

* **Planning and routing:** the request text and attachments map to steps of `(agent, tool, objective)`, which are
  validated against the agent registry (`catalog.AGENTS`).
* **Tool permissions:** a step may only call tools on its agent's allow-list. Violations are denied and audited.
* **Retry and recovery:** up to 2 retries with exponential backoff. Failures are recorded, never hidden.
* **Validation:** the Independent Verification Agent recompiles patched code, re-parses patched YAML, recomputes Guardian
  decisions and reconciles break counts.
* **Human approval:** state-changing actions (apply a patch, open a PR, deploy, trade) create an Approval and pause the
  graph with `interrupt()`. Deciding the approval resumes the run with `Command(resume=…)`. The human review minutes
  are *measured* from request to decision.
* **Persistent state:** `SqliteSaver` checkpoints by run id, so a paused run survives an API restart.
* **Resource and cost accounting:** each run writes one `measured` AgentTask with measured wall time, measured Ollama
  tokens and latency when the model is used, allocated compute, and human review cost.

## Roles

`SHERIN_MANAGER`, `RISK_OFFICER`, `COMPLIANCE_OFFICER`, `PORTFOLIO_MANAGER`, `ENGINEER`, `VIEWER`.

* Investment actions need `SHERIN_MANAGER`, and also `RISK_OFFICER` when material. ESG findings add `COMPLIANCE_OFFICER`.
* Production deployments and code changes need `SHERIN_MANAGER`. Sensitive data changes add `COMPLIANCE_OFFICER`.
* Requesters cannot decide their own requests. One person cannot approve twice under different roles.
* `policy_blocked` approvals (Guardian BLOCK) reject every approve attempt with HTTP 409, and the attempt is audited.
