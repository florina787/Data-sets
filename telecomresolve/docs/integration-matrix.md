# Integration matrix

Every operational connector has a typed contract (`app/connectors/synthetic.py: TOOL_SPECS`, served at
`GET /api/connectors`) with permission, input schema, read/write classification, timeout, idempotency
requirement, error types and audit fields. Today all of them are **SIMULATED**. Enterprise adapters exist as stubs
(`app/connectors/enterprise.py`) that raise `CONNECTOR_UNAVAILABLE` until configured.

| Capability | Prototype adapter | Class | Approval | Idempotency | Enterprise target (unconfigured) | Needed before enabling |
|---|---|---|---|---|---|---|
| Account, service, equipment, mapping | `account_context` (synthetic DB) | read | no | n/a | CRM / inventory | Data-access agreement, field list, freshness SLA, tenant mapping |
| Support history | `support_history` | read | no | n/a | CRM interactions | Retention rules, PII minimisation, note authorship flags |
| Incident search | `incident_search` (mapped path + proximity, kept separate) | read | no | n/a | ITSM incident module (e.g. ServiceNow) | Asset/CI identifiers aligned with service mapping; status history access |
| Diagnostics / peer health | `diagnostics`, `peer_health` | read | no | n/a | Telemetry platform | Signal definitions, units, sampling interval, freshness, rate limits |
| On-demand line test | `on_demand_line_test` | read (triggers test) | no | n/a | Line-test API | Customer impact rules for running tests |
| Knowledge | `knowledge_search` | read | no | n/a | Knowledge base | Document versions, effective dates, role scopes |
| Incident link | `incident_link` (simulated record + case link) | write | specialist confirmation | required | ITSM case–incident relation | Write scope, duplicate detection |
| Customer troubleshooting / update drafts | `customer_message_preview` | write (record only, never sends) | specialist | required | SMS / email | Consent, templates, opt-out, sending authority. **No sending in demo mode** |
| Dispatch preview / create | `dispatch_create` (simulated appointment) | write | supervisor, separation of duties | required (reconcile on lost response) | Field-service scheduling | Eligibility rules, appointment availability source, cancellation API, status reconciliation |
| Equipment reset / service change | proposal only | write | supervisor | required | Provisioning | Action authorization, rollback, customer-impact rules |
| Bill credit | disabled | write | n/a | n/a | Billing | Deterministic eligibility and financial authority; never model-derived |
| Model generation | `AnthropicProvider` (LIVE/HYBRID) | n/a | n/a | n/a | Approved model endpoint | Contract, region, budget, evaluation baseline |
| Embeddings / semantic retrieval | not implemented | — | — | — | pgvector + embedding provider | Region, model choice, re-index process |

## MCP / A2A

Not used. If a future system exposes MCP tools, they must be wrapped with the same `ToolSpec`, the same scope
check before any call, the same input validation and the same audit fields as the REST tools; model text still
cannot authorize writes.
