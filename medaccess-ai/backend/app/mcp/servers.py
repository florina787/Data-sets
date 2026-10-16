"""MCP tool architecture.

Nine logical MCP servers group the harness tools. Each server declares its tools
with typed (JSON-schema) inputs/outputs, authentication + authorization
requirements, error contract, timeout policy and audit events.

``build_fastmcp_server(name)`` exposes a server over stdio using the official MCP
Python SDK (``python -m app.mcp.servers facility_directory``). Calls are executed
through the harness under a fixed least-privilege service principal, so MCP
clients get exactly the same validation, allowlisting and audit as internal agents.
Tool output returned to MCP clients is untrusted from the client's perspective and
inbound arguments are validated like any other untrusted input.
"""

from __future__ import annotations

import sys

from app.harness.core import TOOLS, AgentSpec, RunContext, call_tool, new_id, register_agent

SERVERS: dict[str, dict] = {
    "facility_directory": {"title": "Healthcare Facility Directory MCP", "status": "implemented"},
    "geolocation": {"title": "Geolocation MCP", "status": "implemented"},
    "appointment_availability": {"title": "Appointment Availability MCP", "status": "implemented (synthetic adapter)"},
    "booking_handoff": {"title": "Booking Handoff MCP", "status": "implemented via workflow (approval-gated)"},
    "requisition_rules": {"title": "Requisition Rules MCP", "status": "implemented"},
    "administrative_knowledge": {"title": "Administrative Knowledge MCP", "status": "implemented (RAG)"},
    "notification": {"title": "Notification MCP", "status": "in-app only; email/SMS planned"},
    "audit": {"title": "Audit MCP", "status": "implemented (read-only)"},
    "analytics": {"title": "Analytics MCP", "status": "planned"},
}

ERROR_CONTRACT = {
    "TOOL_NOT_ALLOWED": "caller lacks allowlist entry or permission",
    "APPROVAL_REQUIRED": "side-effecting tool invoked without an approved approval id",
    "TOOL_CONTRACT_VIOLATION": "input or output failed schema validation",
    "CIRCUIT_OPEN": "upstream source temporarily disabled after repeated failures",
    "BUDGET_EXCEEDED": "workflow tool-call or time budget exhausted",
}


def mcp_catalog() -> list[dict]:
    out = []
    for sid, meta in SERVERS.items():
        tools = [t for t in TOOLS.values() if t.mcp_server == sid]
        out.append({
            "id": sid, **meta,
            "authentication": "service principal JWT (stdio: local process trust)",
            "authorization": sorted({t.permission for t in tools if t.permission}) or ["n/a"],
            "tools": [{"name": t.name, "description": t.description, "side_effect": t.side_effect,
                       "timeout_s": t.timeout_s, "input_schema": t.input_model.model_json_schema(),
                       "output_schema": t.output_model.model_json_schema()} for t in tools],
            "error_contract": ERROR_CONTRACT, "audit_events": ["TOOL_CALLED", "TOOL_FAILED"],
        })
    return out


def _service_ctx(server: str) -> tuple[RunContext, str]:
    agent = f"mcp_{server}"
    register_agent(AgentSpec(agent, f"MCP {server}", "MCP service principal", "mcp",
                             {t.name for t in TOOLS.values() if t.mcp_server == server and not t.side_effect}))
    return RunContext(workflow_id=new_id("MCP"), role="patient", permissions={"patient:search"}, persist=False), agent


def build_fastmcp_server(server: str):
    from mcp.server.fastmcp import FastMCP

    from app.agents.registry import register_all
    from app.tools.patient_tools import register

    register_all()
    register()
    if server not in SERVERS:
        raise SystemExit(f"unknown server {server}")
    app = FastMCP(SERVERS[server]["title"])
    for t in [t for t in TOOLS.values() if t.mcp_server == server and not t.side_effect]:
        def make(tool_name: str, model):
            def handler(arguments: dict) -> dict:
                ctx, agent = _service_ctx(server)
                return call_tool(ctx, agent, tool_name, model.model_validate(arguments)).model_dump(mode="json")
            handler.__name__ = tool_name.replace(".", "_")
            handler.__doc__ = TOOLS[tool_name].description
            return handler
        app.add_tool(make(t.name, t.input_model), name=t.name.replace(".", "_"), description=t.description)
    return app


def langchain_tools(server: str | None = None) -> list:
    """Expose harness tools as LangChain StructuredTools (harness controls still apply)."""
    from langchain_core.tools import StructuredTool

    out = []
    for t in TOOLS.values():
        if (server and t.mcp_server != server) or t.side_effect or t.mcp_server is None:
            continue

        def make(spec):
            def fn(**kwargs):
                ctx, agent = _service_ctx(spec.mcp_server)
                return call_tool(ctx, agent, spec.name, kwargs).model_dump(mode="json")
            return fn
        out.append(StructuredTool.from_function(func=make(t), name=t.name.replace(".", "_"),
                                                description=t.description, args_schema=t.input_model))
    return out


if __name__ == "__main__":  # pragma: no cover - manual stdio entry point
    build_fastmcp_server(sys.argv[1] if len(sys.argv) > 1 else "facility_directory").run()
