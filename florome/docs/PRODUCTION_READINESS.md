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

## Florome Shield (research preview)

* **Done and tested:** scope-authorised ingestion, tree-sitter code graph with provenance and incremental reuse; Opengrep/Bandit/Trivy adapters; hypotheses; namespace-isolated verification (2 runs); adjudication; template patches with regression; independent patch review; incidents; containment supervisor; MCP manifest pinning and revocation; OPA dual authorization; quotas, rate limits, signed plans; labelled-corpus evaluation.
* **Not done:** microVM isolation for hostile code; interprocedural/cross-language data flow; fuzzing (AFL++/libFuzzer/OSS-Fuzz); CodeQL; CyberGym benchmark; LLM-based research and the LLM-only baseline; PyRIT/garak/promptfoo/AgentDojo runs; Wazuh/Falco event intake; Alembic migrations and PostgreSQL CI; the dependency CVEs in echarts and react-router.

## Ask Florome assistant

* **Done and tested:** the Copilot home page (chat-first landing, grouped starters, source status); one dock on all 9 other pages, 4 starters per page, 44 question types; customer-conversation questions answered live by the Conversation Intelligence Copilot (Project A) over HTTP, with its session carried between turns and its status shown; visual answers, evidence links, follow-ups, memory, page context, briefs, privacy, injection handling.
* **Partial:** the Project A bridge was tested against Project A running locally with `LLM_ENABLED=false`; it has no authentication between Florome and Project A yet, so it should only point at a local or private-network instance.
* **Not done:** a language model for phrasing (none authorised); interactive drill-down inside answers; analytics on which questions go unanswered.

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
