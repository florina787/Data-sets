# API & MCP guide

## Conventions

* Base URL `http://127.0.0.1:8000`; OpenAPI at `/openapi.json`, docs at `/docs`.
* Auth: `POST /api/auth/login {"user_id": "planner.marco"}` (DEMO_MODE only) → `Authorization: Bearer <token>`.
  Tokens carry audience `flying-florina-ui` and an 8 h expiry. Missing/invalid/wrong-audience tokens → 401 with a typed error.
* Success envelope: `{request_id, data, warnings, provenance, demo, timestamp}`.
* Error: `{code, message, details, request_id}`; policy denials are `403 policy_denied` with the decision (policy id, ordered checks) in `details`.
* Pagination: `limit`/`offset` on list endpoints (`/api/maintenance/work-orders`, `/api/audit/events`); generated adapters cap `limit` at 50.
* Versioning: API version in `/api/config`; policy set version in `/api/policy/catalog`; simulation results carry `version`.
* Access control: every data endpoint calls the policy engine; agents call tools only through the gateway.

## Endpoint map (implemented)

| Area | Endpoints |
|---|---|
| Platform | `GET /health`, `GET /api/config`, `GET /api/demo/status`, `POST /api/demo/reset`, `GET /api/personas`, `POST /api/auth/login`, `GET /api/auth/me` |
| Sessions & workflows | `GET/POST /api/sessions`, `POST /api/chat/query` (`wait`, `options`), `GET /api/workflows`, `GET /api/workflows/{id}`, `GET /api/workflows/{id}/events?after=`, `GET /api/workflows/{id}/stream` (SSE), `POST /api/workflows/{id}/cancel`, `POST /api/workflows/{id}/replay` |
| Operations | `GET /api/fleet/overview`, `GET /api/fleet/trends`, `GET /api/aircraft/{id}`, `GET /api/maintenance/work-orders`, `GET /api/parts/availability`, `GET /api/incidents`, `GET /api/documents`, `GET /api/documents/search`, `GET /api/documents/{id}` |
| Legacy X-Ray | `POST /api/legacy/import` (multipart), `GET /api/legacy/fixtures`, `POST /api/legacy/import-fixture`, `GET /api/legacy/systems`, `GET /api/legacy/graph`, `POST /api/legacy/recommend` |
| Bridge Studio | `GET /api/bridge/sources`, `POST /api/bridge/generate`, `POST /api/bridge/test`, `GET /api/bridge/tools`, `GET /api/bridge/mcp-discover`, `POST /api/bridge/register-tool`, `GET /api/bridge/{id}`, `GET /api/bridge/{id}/download` |
| Governance | `POST /api/policy/evaluate`, `GET /api/policy/decisions`, `GET /api/policy/catalog`, `POST /api/policy/tests/run`, `GET /api/compliance/matrix`, `GET /api/governance/state`, `GET /api/governance/classification`, `POST /api/governance/kill-switch` |
| Audit | `GET /api/audit/events`, `POST /api/audit/verify`, `GET /api/audit/export` |
| Approvals | `GET /api/approvals`, `POST /api/approvals/{id}/approve`, `.../reject`, `.../execute` |
| Simulation & reports | `POST /api/simulations/compare`, `POST /api/simulations/roi`, `GET /api/simulations`, `POST /api/reports/generate`, `GET /api/reports`, `GET /api/reports/{id}/download` |
| Integrations | `GET /api/agents/catalog`, `GET /api/integrations` |

## Responsibilities along the chain

`intent (rules; optional local LLM never decides)` → `workflow engine` → `tool registry (pinned)` →
`policy gateway (deny-by-default, per invocation)` → `MCP server (agent interface)` → `typed API adapter` →
`authorized system endpoint (synthetic here)`.

* Never pass a user's bearer token upstream: the generated adapter verifies the caller and would use its own service credential.
* Validate audience and scope on every hop; reject missing/mismatched identity.
* Retry only idempotent reads; writes need an approval-bound idempotency key.
* No user-supplied URLs are fetched (SSRF); the only outbound target allowed is a loopback LLM endpoint, and only when enabled.

## Generated adapter

`generated_adapters/example_part_availability/` is a committed bundle. Run it:
```bash
cd generated_adapters/example_part_availability
ADAPTER_DEMO_SECRET=change-me PYTHONPATH=. ../../backend/.venv/bin/python -m pytest -q     # 14 tests
ADAPTER_DEMO_SECRET=change-me PYTHONPATH=. ../../backend/.venv/bin/uvicorn adapter.app:app --port 8100
```
`tests/test_mcp.py` launches `mcp_server/server.py` over stdio with the official SDK client and calls `get_part_availability`.

## Demo MCP server

```bash
backend/.venv/bin/python -m mcp_servers.demo_maintenance.server   # needs FF_MCP_TOKEN (audience ff-mcp-demo)
```
The backend launches it for you from Bridge Studio (*Discover & call tools*), checks each tool's schema hash against
`fixtures/policies/mcp_allowlist.yaml`, and calls only pinned tools.

## Pinning tools

Pins live in `fixtures/policies/tool_allowlist.yaml` and `mcp_allowlist.yaml`. After a reviewed change run
`backend/.venv/bin/python scripts/pin_tools.py`, review the diff and commit. Pins are never updated automatically.

## Direct API vs MCP vs events vs batch vs RAG

Served at `/api/integrations` (`matrix`) and shown in Settings and Legacy X-Ray. Summary: use documented APIs for
system-to-system integration; expose narrow, read-only MCP tools to agents over those APIs; use events/CDC only when
permitted and keys are stable; validate/quarantine/reconcile batch files; filter documents by classification before ranking.
MCP is an agent interface, **not** a replacement for enterprise API governance.
