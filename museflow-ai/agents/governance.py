"""Governance role (Pearl 🛡️): allowlist, input and approval policies."""
from __future__ import annotations

from typing import Any

from agents.base import AgentResult, agent_node
from services.tool_registry import ToolRecorder
from services.validation import find_sensitive
from workflows.context import MuseContext
from workflows.state import MuseState

SYNTHETIC_DOMAIN = "@example.com"
MAX_ARG_CHARS = 20_000


def evaluate(action: dict[str, Any] | None, ctx: MuseContext) -> list[dict[str, str]]:
    """Return policy decisions; each result is 'pass', 'require_approval' or 'deny'."""
    decisions = [
        {"policy": "DEMO-001 Simulation-only mode", "result": "pass", "detail": "No LLM clients or production connectors are configured."},
        {"policy": "DATA-001 Session-scoped data", "result": "pass", "detail": f"State is held in session {ctx.session_id[:8]}… only."},
    ]
    if not action:
        decisions.append({"policy": "ACT-000 No consequential action", "result": "pass", "detail": "Read-only workflow."})
        return decisions

    tool = action.get("tool", "")
    if not ctx.tools.is_allowed(tool):
        decisions.append({"policy": "TOOL-001 Allowlist", "result": "deny", "detail": f"'{tool}' is not an allowlisted tool."})
        return decisions
    decisions.append({"policy": "TOOL-001 Allowlist", "result": "pass", "detail": f"'{tool}' is allowlisted."})

    args = action.get("args") or {}
    if len(repr(args)) > MAX_ARG_CHARS:
        decisions.append({"policy": "INPUT-001 Argument size", "result": "deny", "detail": "Arguments exceed the size limit."})
        return decisions
    if tool == "email.simulate_send":
        if not str(args.get("to", "")).endswith(SYNTHETIC_DOMAIN):
            decisions.append({"policy": "MAIL-001 Synthetic recipients only", "result": "deny", "detail": "Recipient is not on example.com."})
            return decisions
        decisions.append({"policy": "MAIL-001 Synthetic recipients only", "result": "pass", "detail": f"{args['to']} is synthetic."})
        sensitive = find_sensitive(str(args.get("body", "")))
        sensitive = [s for s in sensitive if s != "email address"]
        if sensitive:
            decisions.append({"policy": "INPUT-002 No sensitive data", "result": "deny", "detail": f"Body contains: {', '.join(sensitive)}."})
            return decisions
    if ctx.tools.is_consequential(tool):
        decisions.append({"policy": "HITL-001 Human approval", "result": "require_approval",
                          "detail": "Consequential (simulated) action — a human must approve before it is marked complete."})
    return decisions


@agent_node("governance", "governance")
def governance(state: MuseState, ctx: MuseContext, tools: ToolRecorder) -> AgentResult:
    action = state.get("action")
    decisions = evaluate(action, ctx)
    results = {d["result"] for d in decisions}
    if "deny" in results:
        decision = "deny"
    elif "require_approval" in results:
        decision = "require_approval"
    else:
        decision = "allow"
    governance_state = {"checked": True, "decision": decision, "requires_approval": decision == "require_approval",
                        "tool": (action or {}).get("tool")}
    output = {"kind": "policy", "decisions": decisions, "decision": decision}
    if decision == "deny":
        return AgentResult(output=output, message="Denied: action violates policy.",
                           updates={"governance": governance_state, "status": "denied"}, queue_replace=["audit"])
    queue_insert = ["approval"] if decision == "require_approval" else []
    return AgentResult(
        output=output,
        message={"allow": "All policies passed.", "require_approval": "Policies passed; human approval required."}[decision],
        updates={"governance": governance_state},
        queue_insert=queue_insert,
    )
