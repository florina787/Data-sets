"""Audit role (Astra ✨): writes the run's events to the session's hash-chained audit log."""
from __future__ import annotations

from agents.base import AgentResult, agent_node
from services.tool_registry import ToolRecorder
from workflows.context import MuseContext
from workflows.state import MuseState


@agent_node("audit", "audit")
def audit(state: MuseState, ctx: MuseContext, tools: ToolRecorder) -> AgentResult:
    run_id = state.get("run_id", "")
    written = 0
    for event in state.get("trace", []):
        if event.get("kind") != "agent":
            continue
        ctx.audit.record(run_id, f"{event['node']}.{event['status']}", {
            "agent": event["agent"], "message": event.get("message", ""),
            "tools": [c["tool"] for c in event.get("tool_calls", [])],
        })
        written += 1
    approval = state.get("approval")
    if approval:
        ctx.audit.record(run_id, f"human.{approval['decision']}", {"tool": (state.get("action") or {}).get("tool"), "note": approval.get("note", "")})
        written += 1
    summary = ctx.audit.record(run_id, "run.summary", {"scenario": state.get("scenario_id"), "status": state.get("status"), "errors": state.get("errors", [])})
    written += 1
    return AgentResult(
        output={"kind": "audit", "entries_written": written, "chain_head": summary["hash"], "chain_verified": ctx.audit.verify()},
        message=f"Recorded {written} hash-chained audit entries (head {summary['hash'][:10]}…).",
    )
