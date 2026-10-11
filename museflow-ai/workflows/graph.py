"""The MuseFlow LangGraph ``StateGraph``.

Topology (hub-and-spoke supervisor):

    START → intent_router → supervisor ⇄ {specialists, governance, approval, simulate_action, audit}
                               supervisor → respond → END

The supervisor's conditional edge picks the head of ``state["queue"]``. Agents may extend the
queue (e.g. governance inserts ``approval``; approval inserts ``simulate_action`` only when a
human approves), and the supervisor enforces safety invariants on every hop.
"""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from agents.analytics import analytics
from agents.approval import approval, simulate_action
from agents.audit import audit
from agents.browser import browser
from agents.calendar import calendar
from agents.document import document
from agents.email import email
from agents.governance import governance
from agents.memory import memory
from agents.planning import planning
from agents.research import research
from agents.supervisor import intent_router, respond, supervisor
from workflows.context import MuseContext
from workflows.routing import AGENT_NODES, route_from_supervisor
from workflows.state import MuseState

NODE_FUNCTIONS = {
    "planning": planning, "research": research, "memory": memory, "email": email, "calendar": calendar,
    "document": document, "browser": browser, "analytics": analytics, "governance": governance,
    "approval": approval, "simulate_action": simulate_action, "audit": audit,
}
NODE_AGENT = {name: fn.agent_key for name, fn in NODE_FUNCTIONS.items()} | {
    "intent_router": "supervisor", "supervisor": "supervisor", "respond": "supervisor",
}


def build_graph(checkpointer: Any = None):
    """Compile a fresh graph. Each visitor session compiles its own with its own checkpointer."""
    builder = StateGraph(MuseState, context_schema=MuseContext)
    builder.add_node("intent_router", intent_router)
    builder.add_node("supervisor", supervisor)
    builder.add_node("respond", respond)
    for name in AGENT_NODES:
        builder.add_node(name, NODE_FUNCTIONS[name])
        builder.add_edge(name, "supervisor")
    builder.add_edge(START, "intent_router")
    builder.add_edge("intent_router", "supervisor")
    builder.add_conditional_edges("supervisor", route_from_supervisor, {**{n: n for n in AGENT_NODES}, "respond": "respond"})
    builder.add_edge("respond", END)
    return builder.compile(checkpointer=checkpointer)


def graph_topology() -> dict[str, list]:
    """Nodes and edges of the compiled graph (used by Workflow Galaxy)."""
    drawable = build_graph().get_graph()
    nodes = [n for n in drawable.nodes]
    edges = [(e.source, e.target, bool(e.conditional)) for e in drawable.edges]
    return {"nodes": nodes, "edges": edges}
