"""sandbox-ops: a bundled MCP server (stdio) used to verify Florome's MCP gateway end to end.

It serves synthetic operational data from its own in-process simulation; it touches no external system.
Run directly with:  python -m florome.mcp_servers.sandbox_ops_server
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

SERVICES = {
    "ingest-orders": {"platform": "aws", "health": "failed", "errors": ["OrderSchemaV3 validation failed: required field 'currency' missing"]},
    "orders-etl": {"platform": "databricks", "health": "failed", "errors": ["Data quality check failed: orders-raw row count below minimum"]},
    "revenue-api": {"platform": "azure", "health": "failed", "errors": ["RevenueSummaryService: gold.revenue_daily returned 0 rows"]},
    "customer-portal": {"platform": "azure", "health": "healthy", "errors": []},
}

server = MCPServer("sandbox-ops", instructions="Synthetic operations data for Florome tests. All data is simulated.")


@server.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
def get_service_status(service: str) -> dict:
    """Return the simulated health state of a service."""
    svc = SERVICES.get(service)
    if svc is None:
        raise ValueError(f"Unknown service '{service}'. Known: {', '.join(sorted(SERVICES))}")
    return {"service": service, "platform": svc["platform"], "health": svc["health"], "simulated": True}


@server.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
def list_recent_errors(service: str, limit: int = 10) -> dict:
    """Return up to `limit` recent simulated error messages for a service."""
    if not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")
    svc = SERVICES.get(service)
    if svc is None:
        raise ValueError(f"Unknown service '{service}'")
    return {"service": service, "errors": svc["errors"][:limit], "simulated": True}


@server.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True))
def restart_service(service: str) -> dict:
    """Restart a simulated service (write operation)."""
    if service not in SERVICES:
        raise ValueError(f"Unknown service '{service}'")
    return {"service": service, "restarted": True, "simulated": True}


if __name__ == "__main__":
    server.run()
