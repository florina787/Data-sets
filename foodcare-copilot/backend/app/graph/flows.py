"""LangGraph definitions and the resumable runner.

Two graphs share agent nodes: the delivery flow (brief -> deploy) and the
incident flow (analysis -> repair release -> verified recovery). State is
checkpointed in SQLite after every node, so a paused, crashed or restarted run
resumes from its last completed step. Human decisions are LangGraph
interrupts; the gate node re-checks the database when resumed.
"""

from __future__ import annotations

import sqlite3
import threading

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from app.agents import nodes
from app.agents.nodes import FlowState
from app.config import get_settings
from app.db import now_iso, session
from app.errors import PlatformError
from app.graph import jobs
from app.records import activity

_graphs: dict[str, object] = {}
_graph_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _gated(builder: StateGraph, gate: str, target: str) -> None:
    """A human gate loops back to itself until satisfied (one interrupt per execution)."""
    builder.add_conditional_edges(gate, nodes.route_gate(target, gate), [target, gate])


def _delivery(builder: StateGraph) -> StateGraph:
    for name in ("brief_analyst", "clarification_gate", "requirements_agent", "requirements_gate", "design_agent",
                 "implementation_agent", "qa_agent", "repair_agent", "blocked", "review_agent",
                 "release_coordinator", "approval_gate", "post_deploy_check"):
        builder.add_node(name, getattr(nodes, name))
    builder.add_edge(START, "brief_analyst")
    builder.add_edge("brief_analyst", "clarification_gate")
    _gated(builder, "clarification_gate", "requirements_agent")
    builder.add_edge("requirements_agent", "requirements_gate")
    _gated(builder, "requirements_gate", "design_agent")
    builder.add_edge("design_agent", "implementation_agent")
    builder.add_conditional_edges(
        "implementation_agent", lambda s: END if s.get("outcome") == "blocked_live_execution_disabled" else "qa_agent",
        {END: END, "qa_agent": "qa_agent"})
    builder.add_conditional_edges("qa_agent", nodes.route_after_qa, ["review_agent", "repair_agent", "blocked"])
    builder.add_edge("repair_agent", "qa_agent")
    builder.add_edge("blocked", END)
    builder.add_edge("review_agent", "release_coordinator")
    builder.add_conditional_edges("release_coordinator", nodes.route_after_release, ["approval_gate", "blocked"])
    _gated(builder, "approval_gate", "post_deploy_check")
    builder.add_edge("post_deploy_check", END)
    return builder


def _incident(builder: StateGraph) -> StateGraph:
    for name in ("incident_analyst", "requirements_update", "requirements_gate", "reproduce", "repair_agent",
                 "qa_agent", "blocked", "review_agent", "release_coordinator", "approval_gate", "verify_under_fault",
                 "fault_gate", "verify_after_clear"):
        builder.add_node(name, getattr(nodes, name))
    builder.add_edge(START, "incident_analyst")
    builder.add_edge("incident_analyst", "requirements_update")
    builder.add_edge("requirements_update", "requirements_gate")
    _gated(builder, "requirements_gate", "reproduce")
    builder.add_conditional_edges("reproduce", nodes.route_after_reproduce, ["repair_agent", "blocked"])
    builder.add_edge("repair_agent", "qa_agent")
    builder.add_conditional_edges("qa_agent", nodes.route_after_qa, ["review_agent", "repair_agent", "blocked"])
    builder.add_edge("blocked", END)
    builder.add_edge("review_agent", "release_coordinator")
    builder.add_conditional_edges("release_coordinator", nodes.route_after_release, ["approval_gate", "blocked"])
    _gated(builder, "approval_gate", "verify_under_fault")
    builder.add_edge("verify_under_fault", "fault_gate")
    _gated(builder, "fault_gate", "verify_after_clear")
    builder.add_edge("verify_after_clear", END)
    return builder


def reset_graphs() -> None:
    global _conn
    with _graph_lock:
        _graphs.clear()
        if _conn is not None:
            _conn.close()
            _conn = None


def graph(flow: str):
    global _conn
    with _graph_lock:
        if flow not in _graphs:
            if _conn is None:
                path = get_settings().checkpoint_path
                path.parent.mkdir(parents=True, exist_ok=True)
                _conn = sqlite3.connect(path, check_same_thread=False)
            saver = SqliteSaver(_conn)
            builder = StateGraph(FlowState)
            built = _delivery(builder) if flow == "delivery" else _incident(builder)
            _graphs[flow] = built.compile(checkpointer=saver)
        return _graphs[flow]


def thread_id(run_id: str, flow: str, incident_id: str | None = None) -> str:
    return run_id if flow == "delivery" else f"{run_id}:{incident_id}"


def snapshot(run_id: str, flow: str, incident_id: str | None = None) -> dict:
    config = {"configurable": {"thread_id": thread_id(run_id, flow, incident_id)}}
    snap = graph(flow).get_state(config)
    interrupts = [i.value for t in snap.tasks for i in (t.interrupts or ())]
    return {"next": list(snap.next), "interrupts": interrupts, "started": bool(snap.values),
            "done": bool(snap.values) and not snap.next and not interrupts, "values": dict(snap.values or {})}


def advance(run_id: str, flow: str, incident_id: str | None = None, mode: str = "demo") -> dict:
    """Run the graph until it waits for a human, finishes, is paused or fails."""
    g = graph(flow)
    config = {"configurable": {"thread_id": thread_id(run_id, flow, incident_id)}, "recursion_limit": 60}
    snap = g.get_state(config)
    if not snap.values:
        payload = {"run_id": run_id, "flow": flow, "mode": mode, "incident_id": incident_id, "repair_attempts": 0}
    elif any(t.interrupts for t in snap.tasks):
        payload = Command(resume="recheck")
    elif snap.next:
        payload = None
    else:
        return {"state": "done"}
    with session() as conn:
        conn.execute("UPDATE runs SET active_flow = ?, error = NULL WHERE id = ?",
                     (flow if flow == "delivery" else f"incident:{incident_id}", run_id))
    steps = []
    try:
        for update in g.stream(payload, config, stream_mode="updates"):
            names = [k for k in update if k != "__interrupt__"]
            steps.extend(names)
            with session() as conn:
                run = conn.execute("SELECT step_mode, pause_requested FROM runs WHERE id = ?", (run_id,)).fetchone()
                if names and (run["pause_requested"] or run["step_mode"]):
                    conn.execute("UPDATE runs SET pause_requested = 0 WHERE id = ?", (run_id,))
                    activity(run_id, "Orchestrator", "paused", f"Paused after {names[-1]} (checkpoint saved)",
                             "deterministic")
                    break
    except Exception as exc:
        message = exc.message if isinstance(exc, PlatformError) else f"{type(exc).__name__}: {exc}"
        with session() as conn:
            conn.execute("UPDATE runs SET error = ?, updated_at = ? WHERE id = ?", (message, now_iso(), run_id))
        activity(run_id, "Orchestrator", "error", f"Step failed: {message}. The run can resume from its last "
                 "checkpoint.", "deterministic")
        raise
    after = snapshot(run_id, flow, incident_id)
    state = "waiting" if after["interrupts"] else ("done" if after["done"] else "paused")
    if state == "done":
        with session() as conn:
            conn.execute("UPDATE runs SET waiting_for = NULL WHERE id = ?", (run_id,))
    return {"state": state, "steps": steps, "next": after["next"], "interrupts": after["interrupts"]}


def start(run_id: str, flow: str, incident_id: str | None = None, mode: str = "demo") -> str:
    def work() -> dict:
        return advance(run_id, flow, incident_id, mode)

    job_id = jobs.submit(f"advance:{flow}", run_id, work, lock_key=f"run:{run_id}")
    with session() as conn:
        conn.execute("UPDATE runs SET active_job = ? WHERE id = ?", (job_id, run_id))
    return job_id
