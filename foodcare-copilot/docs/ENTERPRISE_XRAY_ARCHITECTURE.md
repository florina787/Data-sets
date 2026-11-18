# Enterprise X-Ray — "Show how Jerry knows"

Enterprise X-Ray shows two different things, and labels which is which:

1. **The recorded path of one answer** (`GET /api/xray/{agent_run_id}`): built from the real
   `agent_runs` and `tool_calls` records of that answer. `real_trace: true`.
2. **The architecture overview** ("Show me the architecture" / "X-ray the enterprise"): a
   `flow` visual of how systems connect, with each connector's verified state. It describes
   structure, not a live trace.

## Answer trace

Steps returned: your question (scrubbed) → Jerry orchestrator (intents, mode) → policy engine →
each read-only tool (name, status, duration, data source and that source's connector state) →
evidence (source labels) → visual answer (scrubbed summary).

What is **withheld**: tool arguments, prompts, model payloads, raw rows, credentials, tokens and
internal hostnames. Only names, timings, statuses and source states are shown.

Access: only the user who asked the question can open its trace; anyone else gets 404
(not 403, so run ids cannot be probed).

## In the UI

* Every answer with a run id has **Show how Jerry knows**; it opens the X-Ray side panel
  (`components/visuals/Actions.tsx`, `XrayPanel`).
* Asking "Where did that information come from?" uses the conversation's `last_agent_run_id`.
* External systems (Databricks, Kubernetes, MCP) are listed with their real state; an
  unconfigured system is shown as unconfigured, never as a live hop.

Tests: `test_privacy.py` (canaries absent from traces), `test_command.py` (owner-only access),
`e2e/command.spec.ts` (panel opens; no password/secret/token text).
