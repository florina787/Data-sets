"""Supervisor role (Lumi 🦄): intent routing, policy-enforcing routing, final response."""
from __future__ import annotations

from agents.base import AgentResult, agent_node
from services import scenario_loader as fixtures
from services.tool_registry import ToolRecorder
from services.validation import MAX_REQUEST_CHARS, ValidationError, clean_text
from workflows.context import MuseContext
from workflows.params import validate_params
from workflows.routing import build_queue, classify_intent
from workflows.state import MuseState

HELP_TEXT = (
    "I can run these simulated workflows: interview prep, email drafting, weekly planning, research briefs, "
    "document analysis, travel planning, simulated bookings, memories, project plans and the AI dream team."
)


@agent_node("intent_router", "supervisor")
def intent_router(state: MuseState, ctx: MuseContext, tools: ToolRecorder) -> AgentResult:
    """Resolve the scenario (explicit or via keyword intent rules), validate params, build the queue."""
    scenario_id = state.get("scenario_id") or ""
    params = dict(state.get("params") or {})
    request = state.get("request") or ""
    matched: list[str] = []
    if request:
        request = clean_text(request, max_chars=MAX_REQUEST_CHARS, field="Request")
    if not scenario_id:
        match = classify_intent(request)
        matched = match.matched
        if not match.scenario_id:
            return AgentResult(
                output={"intent": match.intent, "scenario_id": None, "matched": matched},
                message=f"No workflow for intent '{match.intent}'.",
                updates={"status": "unsupported", "final_response": HELP_TEXT},
                queue_replace=[],
            )
        scenario_id = match.scenario_id
        params = {**match.params, **params}
    if scenario_id not in fixtures.scenario_ids():
        raise ValidationError(f"Unsupported scenario {scenario_id!r}")
    clean_params = validate_params(scenario_id, params)
    queue = build_queue(scenario_id, clean_params)
    spec = fixtures.get_scenario(scenario_id)
    return AgentResult(
        output={"scenario_id": scenario_id, "title": spec.title, "matched_keywords": matched, "initial_queue": queue},
        message=f"Routed to '{spec.title}' with plan: {' → '.join(queue)}.",
        updates={"scenario_id": scenario_id, "params": clean_params},
        queue_replace=queue,
    )


@agent_node("supervisor", "supervisor", kind="route")
def supervisor(state: MuseState, ctx: MuseContext, tools: ToolRecorder) -> AgentResult:
    """Enforce routing invariants, then hand control to the head of the queue."""
    queue = list(state.get("queue") or [])
    notes: list[str] = []
    governance = state.get("governance") or {}
    approval = state.get("approval") or {}

    if governance.get("decision") == "deny" and any(n != "audit" for n in queue):
        queue = ["audit"] if "audit" in queue else []
        notes.append("governance denied the action: only audit may run")
    if queue and queue[0] == "simulate_action" and approval.get("decision") != "approved":
        queue.pop(0)
        notes.append("blocked simulate_action without an approval")
    if state.get("action") and not governance.get("checked") and "governance" not in queue:
        position = queue.index("audit") if "audit" in queue else len(queue)
        queue.insert(position, "governance")
        notes.append("inserted governance: an action was proposed")
    if governance.get("requires_approval") and not approval and "approval" not in queue:
        position = queue.index("audit") if "audit" in queue else len(queue)
        queue.insert(position, "approval")
        notes.append("inserted approval: governance requires it")

    next_hop = queue[0] if queue else "respond"
    return AgentResult(
        output={},
        message=f"→ {next_hop}" + (f" ({'; '.join(notes)})" if notes else ""),
        queue_replace=queue,
    )


def compose_response(state: MuseState) -> str:
    """Template-based final message — every line comes from a node's actual output."""
    status = state.get("status", "")
    scenario_id = state.get("scenario_id", "")
    if status == "unsupported":
        return state.get("final_response") or HELP_TEXT
    title = fixtures.get_scenario(scenario_id).title if scenario_id else "Workflow"
    agents = []
    for event in state.get("trace", []):
        if event.get("kind") == "agent" and event.get("status") == "completed" and event["agent"] not in agents:
            agents.append(event["agent"])
    names = ", ".join(fixtures.get_agent(a).name for a in agents if a != "supervisor")
    if status == "error":
        return f"Something went wrong in '{title}': {'; '.join(state.get('errors', []))}. The audit log recorded it."
    if status == "denied":
        return f"Pearl 🛡️ blocked the proposed action in '{title}' — it is not on the allowlist. Nothing was executed."
    if status in {"rejected", "cancelled"}:
        return f"Understood — the action in '{title}' was {status}. Nothing was executed, even in simulation. ✨"

    lines = [f"✨ '{title}' is complete. Team: {names}."]
    outputs = state.get("outputs") or {}
    if (plan := outputs.get("planning")) and plan.get("headline"):
        lines.append(f"🦋 {plan['headline']}")
    if (research := outputs.get("research")) and research.get("headline"):
        lines.append(f"🧚 {research['headline']}")
    if (doc := outputs.get("document")) and doc.get("headline"):
        lines.append(f"📚 {doc['headline']}")
    if (cal := outputs.get("calendar")) and cal.get("headline"):
        lines.append(f"🌙 {cal['headline']}")
    if (mem := outputs.get("memory")) and mem.get("headline"):
        lines.append(f"🌸 {mem['headline']}")
    if (mail := outputs.get("email")) and mail.get("headline"):
        lines.append(f"💌 {mail['headline']}")
    if (web := outputs.get("browser")) and web.get("headline"):
        lines.append(f"🧭 {web['headline']}")
    if (stats := outputs.get("analytics")) and stats.get("headline"):
        lines.append(f"🔮 {stats['headline']}")
    if result := state.get("action_result"):
        lines.append(f"💖 Approved action completed **in simulation** (confirmation {result.get('confirmation', 'n/a')}).")
    return "\n\n".join(lines)


@agent_node("respond", "supervisor")
def respond(state: MuseState, ctx: MuseContext, tools: ToolRecorder) -> AgentResult:
    status = state.get("status") or "running"
    final_status = status if status in {"rejected", "cancelled", "error", "denied", "unsupported"} else "completed"
    text = compose_response({**state, "status": final_status})
    return AgentResult(
        output={"status": final_status},
        message=f"Final response composed ({final_status}).",
        updates={"status": final_status, "final_response": text},
        queue_replace=[],
    )
