"""Approval role (Cora 💖): LangGraph interrupt for human decisions + simulated execution."""
from __future__ import annotations

from datetime import datetime, timezone

from langgraph.types import interrupt

from agents.base import AgentResult, agent_node
from services.tool_registry import ToolNotAllowedError, ToolRecorder
from services.validation import ValidationError, clean_text
from workflows.context import MuseContext
from workflows.state import MuseState

DECISIONS = ("approved", "rejected", "cancelled")


@agent_node("approval", "approval")
def approval(state: MuseState, ctx: MuseContext, tools: ToolRecorder) -> AgentResult:
    action = state.get("action")
    if not action:
        raise ValueError("Approval requested without a proposed action")
    # Pauses the graph here; the checkpoint is saved and the run resumes from this node.
    response = interrupt({
        "run_id": state.get("run_id"),
        "scenario_id": state.get("scenario_id"),
        "tool": action["tool"],
        "agent": action["agent"],
        "summary": action["summary"],
        "args": {k: (v if len(str(v)) < 400 else str(v)[:399] + "…") for k, v in action["args"].items()},
    })
    if not isinstance(response, dict) or response.get("decision") not in DECISIONS:
        raise ValidationError(f"Invalid approval decision: {response!r}")
    decision = response["decision"]
    note = clean_text(response.get("note", ""), max_chars=200, field="Note", allow_empty=True)
    record = {"decision": decision, "note": note, "decided_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if decision == "approved":
        return AgentResult(output={"kind": "decision", **record}, message="Human approved — handing to simulated execution.",
                           updates={"approval": record}, queue_insert=["simulate_action"])
    return AgentResult(output={"kind": "decision", **record}, message=f"Human {decision} the action — nothing executed.",
                       updates={"approval": record, "status": decision}, queue_replace=["audit"])


@agent_node("simulate_action", "approval")
def simulate_action(state: MuseState, ctx: MuseContext, tools: ToolRecorder) -> AgentResult:
    action = state.get("action") or {}
    if (state.get("approval") or {}).get("decision") != "approved" or not (state.get("governance") or {}).get("checked"):
        raise ToolNotAllowedError("Refusing to simulate an action without governance + human approval.")
    result = tools.call(action["tool"], action["args"], approved=True)
    return AgentResult(
        output={"kind": "simulated_action", "tool": action["tool"], "result": result},
        message=f"{action['tool']} completed in simulation.",
        updates={"action_result": result if isinstance(result, dict) else {"result": result}},
    )
