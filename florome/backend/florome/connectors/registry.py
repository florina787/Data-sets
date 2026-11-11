"""Runtime connector registry and the platform catalog.

The catalog states, for every integration target named in the product scope, what is actually implemented.
Nothing here is reported as "connected": a Connection becomes ``verified`` only after its live health check
passes (see api/connections.py).
"""

from __future__ import annotations

from florome.connectors.base import Connector

IMPLEMENTED = "implemented"  # code + automated tests exist; still needs per-tenant credentials and verification
SIMULATED = "simulated"  # safe synthetic target
NOT_IMPLEMENTED = "not_implemented"

# platform -> (group, implementation status, connector type, note)
PLATFORM_CATALOG: list[dict[str, str]] = [
    {"platform": "sandbox", "group": "Test", "status": SIMULATED, "connector_type": "sandbox",
     "note": "Stateful multi-cloud simulation used for demo mode and end-to-end tests. Never calls external systems."},
    {"platform": "github", "group": "Enterprise software", "status": IMPLEMENTED, "connector_type": "github_rest",
     "note": "REST: repository + workflow discovery, workflow-run history, re-run failed jobs, create issue. "
             "Contract-tested with a mocked HTTP transport; not yet verified against the live API."},
    {"platform": "mcp", "group": "Agentic integration", "status": IMPLEMENTED, "connector_type": "mcp_gateway",
     "note": "MCP stdio client, allow-listed servers, tool discovery, schema pinning, argument validation, output sanitisation. "
             "Verified against the bundled sandbox-ops MCP test server."},
]
for _group, _names in {
    "Microsoft": ["azure_monitor", "application_insights", "azure_devops", "azure_ai_foundry", "microsoft_fabric", "entra_id",
                  "microsoft_graph", "teams", "sharepoint", "power_bi", "azure_functions", "aks"],
    "AWS": ["cloudwatch", "lambda", "ecs", "eks", "step_functions", "bedrock", "sagemaker", "s3", "cloudtrail", "cost_explorer", "iam"],
    "Databricks": ["databricks_jobs", "databricks_workflows", "mlflow", "mosaic_ai", "unity_catalog", "databricks_sql", "delta_lake"],
    "Enterprise software": ["github_actions_deployments", "jenkins", "kubernetes", "jira", "confluence", "servicenow", "salesforce", "workday"],
}.items():
    for _n in _names:
        PLATFORM_CATALOG.append({"platform": _n, "group": _group, "status": NOT_IMPLEMENTED, "connector_type": "",
                                 "note": "Planned. No connector code yet; never shown as connected."})


class ConnectorRegistry:
    """Holds live connector instances keyed by connection id. Instances hold credentials; they never leave the process."""

    def __init__(self) -> None:
        self._by_conn: dict[str, Connector] = {}

    def register(self, connection_id: str, connector: Connector) -> None:
        self._by_conn[connection_id] = connector

    def get(self, connection_id: str) -> Connector:
        try:
            return self._by_conn[connection_id]
        except KeyError as exc:
            raise LookupError(f"No connector instance for connection {connection_id}") from exc

    def has(self, connection_id: str) -> bool:
        return connection_id in self._by_conn

    def remove(self, connection_id: str) -> None:
        self._by_conn.pop(connection_id, None)
