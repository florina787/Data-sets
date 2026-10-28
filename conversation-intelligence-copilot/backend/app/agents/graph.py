"""LangGraph workflow definition and runner.

START → input_validation → session_context → router → intent → supervisor
      → {specialist | retrieval | both in parallel}      (conditional)
      → [retrieval after analysis, when the query depends on the result]
      → evidence → explanation → visualization → qa → governance → response → memory_telemetry → END

Checkpointing: each request runs on its own LangGraph thread (thread_id = request_id). By default the
checkpointer is in memory and the thread is dropped once the request is recorded: the audit trail (every
node's status, timing, inputs/outputs summary and the final response) is kept in telemetry, so writing the
full state to disk after every node added ~130 ms per request for nothing that is read back. Set
CHECKPOINT_BACKEND=sqlite to persist every intermediate state for debugging. Cross-turn memory lives in the
session store (memory/store.py).
"""

from __future__ import annotations

import sqlite3
import time
import uuid
from collections.abc import Iterator
from functools import lru_cache

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from app.agents import fast_path, nodes
from app.agents.state import AnalysisState
from app.agents.tracing import NODE_INFO
from app.config import get_settings
from app.observability.store import get_telemetry

SPECIALISTS = ["topic_agent", "sentiment_agent", "coaching_agent", "leadership_agent", "analytics_agent"]


def route_after_supervisor(state: dict) -> list[str]:
    plan = state["analytical_plan"]
    mode = plan["retrieval"]["mode"]
    targets: list[str] = []
    if plan.get("specialist"):
        targets.append(plan["specialist"])
    if mode in ("parallel", "only"):
        targets.append("retrieval")
    return targets or ["evidence"]


def route_after_specialist(state: dict) -> str:
    return "retrieval" if state["analytical_plan"]["retrieval"]["mode"] == "after_analysis" else "evidence"


def build_graph(checkpointer=None):
    g = StateGraph(AnalysisState)
    for name in ["input_validation", "session_context", "router", "intent", "supervisor", *SPECIALISTS, "retrieval", "evidence", "explanation",
                 "visualization", "qa", "governance", "response", "memory_telemetry"]:
        g.add_node(name, getattr(nodes, name))
    g.add_edge(START, "input_validation")
    g.add_edge("input_validation", "session_context")
    g.add_edge("session_context", "router")
    g.add_edge("router", "intent")
    g.add_edge("intent", "supervisor")
    g.add_conditional_edges("supervisor", route_after_supervisor, [*SPECIALISTS, "retrieval", "evidence"])
    for s in SPECIALISTS:
        g.add_conditional_edges(s, route_after_specialist, ["retrieval", "evidence"])
    g.add_edge("retrieval", "evidence")
    for a, b in [("evidence", "explanation"), ("explanation", "visualization"), ("visualization", "qa"), ("qa", "governance"),
                 ("governance", "response"), ("response", "memory_telemetry"), ("memory_telemetry", END)]:
        g.add_edge(a, b)
    return g.compile(checkpointer=checkpointer)


@lru_cache
def get_graph():
    s = get_settings()
    if s.checkpoint_backend == "memory":
        return build_graph(InMemorySaver())
    s.checkpoint_database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(s.checkpoint_database_path, check_same_thread=False)
    return build_graph(SqliteSaver(conn))


def _release(graph, request_id: str) -> None:
    """Drop an in-memory request thread once its state has been recorded, so memory does not grow per request."""
    if isinstance(graph.checkpointer, InMemorySaver):
        graph.checkpointer.delete_thread(request_id)


def graph_definition() -> dict:
    """Static topology for the Agent Harness view."""
    edges = [("START", "input_validation"), ("input_validation", "session_context"), ("session_context", "router"), ("router", "intent"), ("intent", "supervisor")]
    edges += [("supervisor", s) for s in SPECIALISTS] + [("supervisor", "retrieval"), ("supervisor", "evidence")]
    edges += [(s, "retrieval") for s in SPECIALISTS] + [(s, "evidence") for s in SPECIALISTS] + [("retrieval", "evidence")]
    edges += [("evidence", "explanation"), ("explanation", "visualization"), ("visualization", "qa"), ("qa", "governance"),
              ("governance", "response"), ("response", "memory_telemetry"), ("memory_telemetry", "END")]
    conditional = {("supervisor", s) for s in SPECIALISTS} | {("supervisor", "retrieval"), ("supervisor", "evidence")} | \
                  {(s, "retrieval") for s in SPECIALISTS} | {(s, "evidence") for s in SPECIALISTS}
    return {
        "nodes": [{"id": "START", "label": "Start", "role": "Analyst question"}] + [{"id": k, **v} for k, v in NODE_INFO.items()]
                 + [{"id": "END", "label": "End", "role": "Response delivered"}],
        "edges": [{"source": a, "target": b, "conditional": (a, b) in conditional} for a, b in edges],
    }


def _initial_state(question: str, session_id: str, request_id: str, dataset_mode: str, selected: str | None, analysis_mode: str = "auto") -> dict:
    return {"request_id": request_id, "session_id": session_id, "user_question": question, "dataset_mode": dataset_mode, "analysis_mode": analysis_mode,
            "selected_conversation_id": selected, "started_at": time.time(), "execution_trace": [], "errors": [],
            "tool_results": {}, "retrieved_evidence": [], "retrieval_meta": {}, "governance_findings": []}


def _finish(state: dict, request_id: str, session_id: str, question: str, started: float, error: str | None = None) -> dict:
    tel = get_telemetry()
    fr = state.get("final_response")
    latency = round((time.perf_counter() - started) * 1000, 1)
    for ev in state.get("execution_trace", []):
        tel.record_node(request_id, ev)
    executed = {ev["node"] for ev in state.get("execution_trace", [])}
    for name in NODE_INFO:
        if name not in executed:
            tel.record_node(request_id, {"node": name, "status": "skipped" if not error else "cancelled", "duration_ms": 0})
    intent = state.get("resolved_intent") or {}
    tel.record_request(request_id=request_id, session_id=session_id, question=question, intent=intent,
                       operations=[s["op"] for s in state.get("analytical_plan", {}).get("steps", [])],
                       status=(fr or {}).get("status", "failed") if not error else ("cancelled" if error == "cancelled" else "failed"), latency_ms=latency,
                       error_category=error, llm_mode=(fr or {}).get("model_metadata", {}).get("mode"),
                       quality_status=(fr or {}).get("quality_status", {}).get("status"), response=fr)
    if fr:
        fr["latency_ms"] = latency
    return fr or {}


def _finish_fast(fr: dict, events: list[dict], request_id: str, session_id: str, question: str, started: float) -> Iterator[dict]:
    """Record a fast-path reply like any other request: node events, request row, memory turn, audit entry."""
    from app.memory.store import get_memory

    for ev in events:
        yield {"type": "node_start", "node": ev["node"], "label": ev["label"], "at": ev["started_at"]}
        yield {"type": "node_end", **{k: ev[k] for k in ("node", "label", "status", "duration_ms", "error", "output_summary", "meta")}}
    state = {"execution_trace": events, "resolved_intent": fr["resolved_intent"], "analytical_plan": {"steps": []}, "final_response": fr}
    fr = _finish(state, request_id, session_id, question, started)
    # status "small_talk" keeps the turn out of follow-up context (only completed analyses are resolved against)
    get_memory().add_turn(session_id, request_id, question, fr["resolved_intent"], fr["dataset_scope"], fr["plan"], {}, fr["headline"], "small_talk")
    get_telemetry().audit("request", "answered", {"category": "general_chat", "status": fr["status"], "qa": "pass", "route": "fast_path"},
                          request_id, session_id)
    yield {"type": "final", "response": fr}


def run_chat(question: str, session_id: str | None = None, dataset_mode: str = "original", selected_conversation_id: str | None = None,
             analysis_mode: str = "auto") -> dict:
    """Synchronous run; returns the final response."""
    events = list(stream_chat(question, session_id, dataset_mode, selected_conversation_id, analysis_mode))
    final = [e for e in events if e["type"] in ("final", "error")]
    return final[-1]["response"] if final and final[-1]["type"] == "final" else {"status": "failed", "error": final[-1] if final else None}


def stream_chat(question: str, session_id: str | None = None, dataset_mode: str = "original",
                selected_conversation_id: str | None = None, analysis_mode: str = "auto") -> Iterator[dict]:
    """Yield real execution events: node_start / node_end (from the nodes themselves), then final."""
    from app.memory.store import get_memory

    request_id = f"R-{uuid.uuid4().hex[:12]}"
    sid = get_memory().ensure_session(session_id, dataset_mode, question)
    started = time.perf_counter()
    graph = get_graph()
    config = {"configurable": {"thread_id": request_id}}
    yield {"type": "accepted", "request_id": request_id, "session_id": sid}
    fast = fast_path.respond(question, request_id, sid, dataset_mode)
    if fast is not None:
        fr, events = fast
        yield from _finish_fast(fr, events, request_id, sid, question, started)
        return
    error = None
    try:
        for mode, chunk in graph.stream(_initial_state(question, sid, request_id, dataset_mode, selected_conversation_id, analysis_mode), config,
                                        stream_mode=["custom", "updates"]):
            if mode == "custom":
                yield chunk
    except GeneratorExit:
        _finish(graph.get_state(config).values, request_id, sid, question, started, error="cancelled")
        _release(graph, request_id)
        get_telemetry().audit("request", "cancelled", {"question": question[:200]}, request_id, sid)
        raise
    except Exception as e:  # noqa: BLE001
        error = f"{type(e).__name__}: {str(e)[:300]}"
    state = graph.get_state(config).values
    _release(graph, request_id)
    fr = _finish(state, request_id, sid, question, started, error=error.split(":")[0] if error else None)
    get_telemetry().audit("request", "answered" if not error else "failed",
                          {"category": (state.get("resolved_intent") or {}).get("category"), "status": fr.get("status"),
                           "qa": fr.get("quality_status", {}).get("status"), "error": error}, request_id, sid)
    if error:
        yield {"type": "error", "request_id": request_id, "session_id": sid, "message": error,
               "retryable": "InvalidInput" not in error}
    else:
        yield {"type": "final", "response": fr}
