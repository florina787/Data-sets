"""Memory role (Iris 🌸): session-scoped memory add/search and personalisation signals."""
from __future__ import annotations

from typing import Any

from agents.base import AgentResult, agent_node
from services.tool_registry import ToolRecorder
from workflows.context import MuseContext
from workflows.state import MuseState


def derive_signals(memories: list[dict[str, Any]]) -> dict[str, Any]:
    """Turn stored preferences into simple planning hints (keyword rules, no inference)."""
    text = " ".join(m["text"].lower() for m in memories)
    signals: dict[str, Any] = {}
    if "morning" in text:
        signals["time_of_day"] = "morning"
    elif "afternoon" in text or "evening" in text:
        signals["time_of_day"] = "afternoon"
    if any(w in text for w in ("workout", "yoga", "pilates", "walk", "gym")):
        signals["wellness"] = True
    signals["goals"] = [m["text"] for m in memories if m["category"] == "Goals"][:3]
    return signals


@agent_node("memory", "memory")
def memory(state: MuseState, ctx: MuseContext, tools: ToolRecorder) -> AgentResult:
    params = state.get("params") or {}
    scenario = state.get("scenario_id")

    if scenario == "personal_memory":
        item = tools.call("memory.add", {"category": params["category"], "text": params["text"], "source": "user"})
        return AgentResult(
            output={"operation": "add", "memory": item, "headline": f"Planted a new {item['category'].lower()} memory: “{item['text']}”"},
            message=f"Stored memory {item['id']} in this session only.",
        )
    if scenario == "memory_recall":
        found = tools.call("memory.search", {"query": params.get("query", "")})
        head = f"Found {len(found)} memor{'y' if len(found) == 1 else 'ies'}" + (f" about “{params['query']}”." if params.get("query") else ".")
        return AgentResult(output={"operation": "search", "memories": found, "headline": head}, message=head)

    prefs = tools.call("memory.search", {"category": "Preferences"})
    goals = tools.call("memory.search", {"category": "Goals"})
    signals = derive_signals(prefs + goals)
    head = (f"Used {len(prefs) + len(goals)} memories to personalise the plan." if prefs or goals
            else "No preferences stored yet — tip: tell me “remember that I prefer morning focus”.")
    return AgentResult(
        output={"operation": "personalise", "memories": prefs + goals, "signals": signals, "headline": head},
        message=f"Derived signals {sorted(k for k in signals if signals[k])} from {len(prefs) + len(goals)} memories.",
    )
