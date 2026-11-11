# Production readiness

**Verdict: not production-ready.** It is a working, tested vertical slice in demo mode.

## Completed (verified)

* Phase 0: audit and integration plan; both projects preserved.
* Phase 1: FastAPI foundation, persistence (SQLite tested), demo/live separation, domain model, React shell and design system.
* Phase 2: Nervous System, Causality Constellation, Time-Travel, Action Command Center.
* Phase 3: MCP gateway, tool registry, connector contract, connector health, permissions, audit.
* Phase 4: end-to-end RCA with an auditable report.
* Phase 5: planning, approval, execution, validation, history against the safe sandbox.
* Partial Phase 7: FinOps Sankey and the governance console; Project B served via the adapter.

## Partial

* GitHub connector: code and mocked-transport tests only, never run against the live API.
* MCP: read tools only; write tools through approved plans are not wired.
* Governance visualization: policy, audit and metrics are shown, but not the full trust-orbit graph.
* PostgreSQL: supported through SQLAlchemy but not yet tested.
* Project A is imported but not integrated into the API.

## Missing

* Live authentication (OIDC/SSO). This is the main blocker for any non-demo use.
* Real Azure, AWS, Databricks, Jira, ServiceNow and other connectors (see INTEGRATION_MATRIX.md).
* Secrets-manager integration, HTTP rate limiting, data-retention policies.
* Alembic migrations, a background worker queue (execution is currently in-request), and OpenTelemetry export (only structured JSON logs and request IDs exist today).
* LLM narrative layer (pluggable Qwen). This was intentionally deferred: every conclusion is deterministic today.
* Remaining signature visualizations and the DevOps, MLOps and risk modules.

## Next steps

1. OIDC login plus a secrets manager.
2. Azure DevOps connector against a non-production project (needs credentials from you).
3. An MCP write path via an `MCPConnector` inside approved plans.
4. A worker queue with Alembic, then PostgreSQL CI.
