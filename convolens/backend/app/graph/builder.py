"""Flo StateGraph definition with conditional routing, a bounded adaptive loop and an approval interrupt."""
from __future__ import annotations

import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from app.graph import nodes as n
from app.graph.state import FloState

NODE_ORDER = ["interpret_request", "resolve_context", "plan_analysis", "execute_tools", "inspect_results", "validate_claims",
              "compose_response", "request_action_approval", "persist_approved_action", "handle_failure"]

EDGES = [  # (source, target, label) - used both to build the graph and to render the execution map
    ("__start__", "interpret_request", ""),
    ("interpret_request", "resolve_context", "analysis / evidence / investigation"),
    ("interpret_request", "compose_response", "unsupported / limitations"),
    ("interpret_request", "handle_failure", "error"),
    ("resolve_context", "plan_analysis", ""),
    ("resolve_context", "handle_failure", "error"),
    ("plan_analysis", "execute_tools", "plan ready"),
    ("plan_analysis", "compose_response", "unsupported"),
    ("plan_analysis", "handle_failure", "model error"),
    ("execute_tools", "inspect_results", "results"),
    ("execute_tools", "handle_failure", "tool errors"),
    ("inspect_results", "execute_tools", "adaptive step (bounded)"),
    ("inspect_results", "validate_claims", "sufficient"),
    ("inspect_results", "compose_response", "insufficient evidence"),
    ("inspect_results", "handle_failure", "no results"),
    ("validate_claims", "compose_response", ""),
    ("validate_claims", "handle_failure", "error"),
    ("compose_response", "request_action_approval", "action proposed"),
    ("compose_response", "__end__", "answer"),
    ("compose_response", "handle_failure", "model error"),
    ("request_action_approval", "persist_approved_action", "approved"),
    ("request_action_approval", "__end__", "rejected"),
    ("persist_approved_action", "__end__", ""),
    ("handle_failure", "__end__", ""),
]


def build_graph(checkpointer):
    g = StateGraph(FloState)
    for name in NODE_ORDER:
        g.add_node(name, getattr(n, name))
    g.add_edge(START, "interpret_request")
    g.add_conditional_edges("interpret_request", n.route_after_interpret, ["resolve_context", "compose_response", "handle_failure"])
    g.add_conditional_edges("resolve_context", n.route_simple("plan_analysis"), ["plan_analysis", "handle_failure"])
    g.add_conditional_edges("plan_analysis", n.route_after_plan, ["execute_tools", "compose_response", "handle_failure"])
    g.add_conditional_edges("execute_tools", n.route_after_execute, ["inspect_results", "handle_failure"])
    g.add_conditional_edges("inspect_results", n.route_after_inspect, ["execute_tools", "validate_claims", "compose_response", "handle_failure"])
    g.add_conditional_edges("validate_claims", n.route_simple("compose_response"), ["compose_response", "handle_failure"])
    g.add_conditional_edges("compose_response", n.route_after_compose, ["request_action_approval", "handle_failure", END])
    g.add_conditional_edges("request_action_approval", n.route_after_approval, ["persist_approved_action", END])
    g.add_edge("persist_approved_action", END)
    g.add_edge("handle_failure", END)
    return g.compile(checkpointer=checkpointer)


def sqlite_checkpointer(path) -> SqliteSaver:
    conn = sqlite3.connect(str(path), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver
