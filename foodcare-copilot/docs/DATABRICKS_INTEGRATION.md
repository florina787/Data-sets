# Databricks integration (governed, read-only)

**Status in this repository: adapter built and contract-tested against a mock server. No
Databricks workspace is connected.** The Connect page shows `adapter_available` until the
variables below exist, `configured` once they do, and `connection_tested`/`failed` only after a
real test request.

## How it works

* API: Databricks SQL Statement Execution API (`POST {host}/api/2.0/sql/statements`) on a SQL warehouse.
* Queries: a fixed allowlist of parameterised `SELECT` statements (`connectors.DATABRICKS_QUERIES`):

| Name | Purpose | Parameters |
|---|---|---|
| `factory_performance` | Weekly throughput, downtime, OEE per site | `since: DATE` |
| `supplier_quality` | Lots received / rejected per supplier | `since: DATE` |
| `table_freshness` | Last-altered time of tables (connection test) | `schema_name: STRING` |

* Parameters are sent as typed statement parameters, never concatenated. A call with different
  parameter names is refused. The schema name from configuration must match `catalog.schema`.
* **No LLM-generated SQL.** Jerry can only choose a query name; it cannot write SQL.
* Every call goes through the governor (rate limit, circuit breaker, single retry, audit, output
  neutralising) — see `MCP_CONNECTOR_ARCHITECTURE.md`.

## Configure (server environment only)

```bash
export DATABRICKS_HOST=https://<workspace>.cloud.databricks.com
export DATABRICKS_TOKEN=<service principal token>     # never in the browser or the repo
export DATABRICKS_WAREHOUSE_ID=<warehouse id>
export DATABRICKS_SCHEMA=<catalog>.<schema>
```

Identity: a service principal with `USE CATALOG`, `USE SCHEMA` and `SELECT` on the approved
schema only (Unity Catalog). No `MODIFY`, no workspace-admin, no cluster creation.

Then, as an engineer or release approver: **Technology → Connect your enterprise → Databricks →
Run read-only test**.

## Cost note

Running statements uses your SQL warehouse and is billed by Databricks. Nothing in this
repository creates or starts a warehouse.

Tests: `test_databricks_runs_only_allowlisted_parameterised_queries`,
`test_circuit_breaker_opens_after_repeated_failures`, `test_registry_is_honest_when_nothing_is_configured`
in `backend/tests/test_command.py`.
