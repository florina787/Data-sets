# MCP server and connector architecture

## Connector states (`GET /api/connectors`)

`planned · adapter_available · configured · connection_tested · connected · read_only ·
write_with_approval · simulated · failed`

A state is only set from evidence:

* `configured` — the server environment variables exist. A settings screen alone never counts.
* `connection_tested` / `failed` — after a real read-only test request (`POST /api/connectors/{id}/test`,
  permission `connector.test`).
* `simulated` — security, billing and delivery adapters whose demo records are labelled synthetic.
* `planned` — no adapter yet (SAP/ERP, Oracle, SQL Server, PostgreSQL, REST/SOAP, lake, events,
  threat intel, containment writes, Confluence/SharePoint, notifications).

Credentials live only in server environment variables. Nothing is stored in browser storage.

## Governance for every external call (`connectors.governed_call`)

| Control | Implementation |
|---|---|
| Allowlisted operation | Fixed query names / API paths per connector |
| Timeout | 10–20 s per request |
| Rate limit | 30 calls / minute / user / connector |
| Circuit breaker | Opens after 3 failures, 60 s cool-down |
| Retry | One retry for idempotent reads only |
| Audit | `audit_events` with connector, operation, outcome — counts only, never values |
| Untrusted output | `neutralise()` strips prompt-injection-like text, scrubs secrets, caps sizes |

## MCP server (`POST /mcp`, JSON-RPC 2.0, protocol `2025-06-18`)

Methods: `initialize`, `tools/list`, `tools/call`. Tools (all read-only):

| Tool | Returns |
|---|---|
| `supplier_scorecard` | Suppliers by incidents and quality, confidential fields banded |
| `enterprise_priorities` | The ranked priorities shown on the Pulse |
| `technology_health` | App, storefront and model status |
| `sales_summary` | Sales by region and period (validated arguments) |
| `origin_trace` | Supply-network exposure for a region |

Every call needs the same signed-in identity as the web app (Bearer token), validates arguments
against the tool's input schema (extra arguments rejected), runs through the governor, and is
minimised with purpose `mcp` (no confidential values, even for granted roles). There are no
write tools.

Code: `backend/app/connectors.py`, `backend/app/mcp_server.py`. Tests: `backend/tests/test_command.py`
(mock HTTP servers, injection neutralising, breaker, MCP schema validation, no canaries).
