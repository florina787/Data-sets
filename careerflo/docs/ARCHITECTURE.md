# Architecture

```
 Browser (React + TS, Vite)                     Supabase
 ┌──────────────────────────┐   access token   ┌──────────────┐
 │ 22 sections + pricing    │◀────────────────▶│ Auth (email  │
 │ TanStack Query, SSE chat │                  │ verify/reset)│
 └────────────┬─────────────┘                  │ PostgreSQL   │◀──── RLS policies (0002)
              │ HTTPS /api                     └──────▲───────┘
 ┌────────────▼──────────────────────────────────────┼──────────────────────────┐
 │ FastAPI (single VM)                                │ SQLAlchemy               │
 │  routers ─▶ metering (reserve → run → commit)      │                          │
 │     │                                               │                          │
 │     ├─▶ LangGraph supervisor ─▶ 14 agents ─▶ governance node                  │
 │     │                              │                                          │
 │     └──────────────▶ MCP gateway (allowlists, injected user_id, rate limit,   │
 │                       timeouts, audit) ─▶ 7 FastMCP servers (in-memory MCP)   │
 │                                              │                                │
 │  Qwen client (one queue) ──▶ Ollama / llama-server (Qwen3, quantized)         │
 └───────────────────────────────┬──────────────────────────────────────────────┘
                                 │ outbound HTTPS
   JSearch · Adzuna · Greenhouse · Lever · Ashby · Wikipedia · GitHub · Stripe ◀── webhooks
```

## Request lifecycle (metered feature)
1. `get_current_user` verifies the Supabase JWT (JWKS or HS256) or a local dev token. The first request provisions the `users` row with `id = auth.uid()`.
2. `metered(user, feature, Idempotency-Key)` runs an atomic conditional `UPDATE … WHERE used + reserved < limit` and inserts a reservation row with a unique idempotency key.
3. The feature runs. Tool calls go through `mcp_gateway.call_tool`, which strips any client-supplied `user_id`, injects the authenticated one, checks the allowlist and writes an `mcp_tool_calls` row.
4. On success, `commit()` moves the use from `reserved` to `used` and caches the result for replays. On any exception, `release()` frees it. Stale reservations are released at start-up.
5. A nested feature inside an outer metered block is *included*, not charged. Example: resume tailoring calls job matching internally, and only one use is counted.

## LangGraph supervisor (`app/agents/graph.py`)
`START → supervisor → (agent)* → governance → END`. The supervisor classifies intent deterministically (`agents/intents.py`), extracts parameters (city, salary, currency, title, topics, company, GitHub user, offer) and builds a plan of at most 6 agents. A conditional edge (`dispatch`) walks the plan. Each agent is wrapped for error recovery: a failing agent records a note and the workflow continues. Bounds are a 24 tool-call budget, recursion limit 30 and per-tool timeouts. Each run is persisted to `agent_runs` with its step trace. Progress is streamed to the UI as Server-Sent Events.

The 15 agents are Job Discovery, Job Matching, Resume, ATS, Cover Letter, Interview, Coding Coach, Company Research, Recruiter CRM, Application Tracker, GitHub Portfolio, Salary, Career Analytics, Autonomous Workflow and Governance. The Governance node flags unsupported claims, neutralised injection attempts and synthetic data. **Enforcement does not depend on it**: allowlists, identity injection, approvals and metering are deterministic code.

## Where Qwen is used, and where it is not
| Task | Engine |
|---|---|
| Routing, parameter extraction, matching, ATS, salary statistics, dedupe, metering | Deterministic code |
| Assistant narrative (streamed) | Qwen |
| Resume summary rewrite | Qwen, then **rejected** if the fact checker finds unsupported claims |
| Cover-letter polish | Qwen, fact-checked the same way |
| Interview answer feedback | Rubric score (deterministic) + Qwen comment |

If the inference server is down, every feature still returns its deterministic result. The UI labels the source (for example, "deterministic (Qwen unavailable)"), and a degraded chat reply is not charged.

## Data model
41 tables (`app/models.py`, migration `0001`): the 38 required tables plus `invoices` (payment history), `provider_usage` (provider quotas) and `search_cache`. UUID keys, foreign keys with `ON DELETE CASCADE` for user data, check constraints (`ck_trial_max_two`: `used + reserved <= 2`), unique constraints for idempotency (`uq_reservation_idem`), saved jobs, sources and Stripe events.
