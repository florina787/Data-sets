"""MCP Server G — Governance. Note: these tools *assist* agents; enforcement lives in the gateway."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..careers.context import as_uuid
from ..db import SessionLocal
from ..governance.approvals import CONSEQUENTIAL_ACTIONS, request_approval
from ..governance.audit import audit
from ..security.sanitize import detect_injection, redact

VERSION = "1.0.0"
mcp = FastMCP("careerflo-governance")


@mcp.tool(description="Check whether an agent may call a tool (static allowlist).")
def validate_tool_request(agent: str, tool: str) -> dict:
    from ..mcp_gateway import AGENT_ALLOWLIST

    allowed = tool in AGENT_ALLOWLIST.get(agent, set())
    return {"agent": agent, "tool": tool, "allowed": allowed}


@mcp.tool(description="Whether an action needs human approval.")
def check_permissions(action: str) -> dict:
    return {"action": action, "requires_approval": action in CONSEQUENTIAL_ACTIONS,
            "description": CONSEQUENTIAL_ACTIONS.get(action)}


@mcp.tool(description="Redact emails, phone numbers, ID numbers, card numbers and secrets; flag injection attempts.")
def redact_sensitive_data(text: str) -> dict:
    return {"text": redact(text[:50000]), "injection_flags": detect_injection(text[:50000])}


@mcp.tool(description="Create a pending approval request for a consequential action (never executes it).")
def request_human_approval(user_id: str, action: str, summary: str, payload: dict, requested_by: str = "agent") -> dict:
    with SessionLocal() as db:
        req = request_approval(db, as_uuid(user_id), action, summary, payload, requested_by)
        return {"approval_id": str(req.id), "status": req.status}


@mcp.tool(description="Write an audit event.")
def record_audit_event(user_id: str, action: str, detail: dict | None = None, actor: str = "agent") -> dict:
    with SessionLocal() as db:
        audit(db, as_uuid(user_id), actor, action, None, detail or {})
    return {"recorded": True}
