"""LangGraph StateGraph for patient appointment discovery.

START -> intake -> clinical_safety -(urgent)-> safety_interruption -> audit -> END
                                   -> service_classification -> facility_discovery -> geospatial
      -> availability_search -(source failure)-> recovery -> data_quality
                              -> data_quality -> availability_verification -> eligibility -> wait_time
      -> recommendation -(no verified result)-> expand_search_options -> expansion_approval
                                                    -(approved)-> facility_discovery (repeat search)
                                                    -(declined)-> patient_review
                        -> patient_review -(booking requested)-> booking_preparation -> human_approval
                                                  -(approved)-> booking_handoff -> confirmation_verification
                                                  -> notification -> audit -> END
                                          -> audit -> END

Human approval and radius expansion use ``interrupt()`` with a durable SQLite
checkpointer, so a paused workflow survives restarts and resumes without
re-running completed external actions.
"""

from __future__ import annotations

import sqlite3
import time
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.errors import GraphBubbleUp
from langgraph.graph import END, START, StateGraph

from app.agents import patient_nodes as n
from app.config.settings import get_settings
from app.database.session import session_scope
from app.governance import audit as audit_log
from app.graphs.state import PatientWorkflowState
from app.harness.core import AGENTS, BudgetExceeded, HarnessError, RunContext
from app.models import db as m
from app.security.guards import redact_text
from app.telemetry import metrics as tm
from app.telemetry.tracing import tracer

NODE_AGENT = {
    "intake": "intake", "clinical_safety": "clinical_safety", "safety_interruption": "clinical_safety",
    "service_classification": "service_classification", "facility_discovery": "facility_discovery",
    "geospatial": "geospatial", "availability_search": "availability_search", "recovery": "recovery",
    "data_quality": "data_quality", "availability_verification": "availability_verification",
    "eligibility": "eligibility", "wait_time": "wait_time", "recommendation": "recommendation",
    "expand_search_options": "supervisor", "expansion_approval": "human_approval", "patient_review": "supervisor",
    "booking_preparation": "booking_assistance", "human_approval": "human_approval",
    "booking_handoff": "booking_assistance", "confirmation_verification": "booking_assistance",
    "notification": "notification", "audit": "audit",
}


def _ctx(config) -> RunContext:
    return config["configurable"]["ctx"]


def wrap(node_name: str, fn):
    agent = NODE_AGENT[node_name]

    def run(state: PatientWorkflowState, config) -> dict:
        ctx = _ctx(config)
        t0 = time.perf_counter()
        status = "completed"
        with tracer().start_as_current_span(f"agent.{node_name}") as span:
            span.set_attribute("medaccess.workflow_id", ctx.workflow_id)
            span.set_attribute("medaccess.agent", agent)
            try:
                ctx.step(node_name)
                out = fn(state, ctx) or {}
            except GraphBubbleUp:
                raise  # interrupts must propagate to LangGraph
            except BudgetExceeded as e:
                status, out = "failed", {"workflow_status": "HALTED", "errors": [f"{node_name}: {e}"],
                                         "_explanation": str(e)}
            except HarnessError as e:
                status, out = "failed", {"workflow_status": "FAILED", "errors": [f"{node_name}: {e.code}: {e}"],
                                         "_explanation": e.code}
            except Exception as e:  # noqa: BLE001 - surfaced as a structured failure
                status, out = "failed", {"workflow_status": "FAILED",
                                         "errors": [f"{node_name}: {type(e).__name__}: {e}"],
                                         "_explanation": f"{type(e).__name__}"}
        dur = round((time.perf_counter() - t0) * 1000, 2)
        expl = redact_text(str(out.pop("_explanation", "")))
        out.setdefault("agent_trace", [])
        out["agent_trace"] = list(out["agent_trace"]) + [{
            "node": node_name, "agent": agent, "title": AGENTS[agent].title if agent in AGENTS else agent,
            "status": status, "action": expl, "duration_ms": dur, "at": datetime.now(UTC).isoformat()}]
        if node_name == "audit":
            out["security_events"] = ctx.security_events[:]
        tm.AGENT_RUNS.labels(agent=agent, status=status).inc()
        tm.AGENT_LATENCY.labels(agent=agent).observe(dur / 1000)
        tm.STORE.add("agent_latency_ms", dur, {"agent": agent})
        tm.STORE.add("agent_success", 1 if status == "completed" else 0, {"agent": agent})
        if ctx.persist:
            with session_scope() as s:
                s.add(m.AgentExecution(workflow_id=ctx.workflow_id, agent=agent, status=status, duration_ms=dur,
                                       detail=expl[:500]))
            audit_log.record("AGENT_EXECUTED", agent, {"node": node_name, "status": status, "duration_ms": dur},
                             ctx.workflow_id)
        return out

    run.__name__ = node_name
    return run


def _halted(state: PatientWorkflowState) -> bool:
    return state.workflow_status in {"FAILED", "HALTED", "NEEDS_INPUT"}


def route_after_intake(state):
    return "audit" if _halted(state) else "clinical_safety"


def route_after_safety(state):
    if _halted(state):
        return "audit"
    return "safety_interruption" if state.safety.get("interrupt") else "service_classification"


def route_after_classification(state):
    return "audit" if _halted(state) else "facility_discovery"


def route_linear(next_node: str):
    def r(state):
        return "audit" if _halted(state) else next_node
    r.__name__ = f"to_{next_node}"
    return r


def route_after_availability(state):
    if _halted(state):
        return "audit"
    return "recovery" if state.failed_sources else "data_quality"


def route_after_recommendation(state):
    if _halted(state):
        return "audit"
    has_confirmed = any(r["tier"] == "CONFIRMED_ALTERNATIVE" for r in state.recommendations)
    if not has_confirmed and not state.request_booking and state.expansions < n.MAX_EXPANSIONS:
        return "expand_search_options"
    return "patient_review"


def route_after_expand(state):
    return "expansion_approval" if state.pending_question else "patient_review"


def route_after_expansion_approval(state):
    return "facility_discovery" if state.approval_status == "APPROVED" else "patient_review"


def route_after_review(state):
    return "booking_preparation" if state.request_booking and state.selected_slot_id else "audit"


def route_after_booking_prep(state):
    return "human_approval" if state.workflow_status == "AWAITING_APPROVAL" else "audit"


def route_after_human_approval(state):
    return "booking_handoff" if state.approval_status == "APPROVED" else "audit"


def build_graph() -> StateGraph:
    g = StateGraph(PatientWorkflowState)
    nodes = {
        "intake": n.intake, "clinical_safety": n.clinical_safety, "safety_interruption": n.safety_interruption,
        "service_classification": n.service_classification, "facility_discovery": n.facility_discovery,
        "geospatial": n.geospatial, "availability_search": n.availability_search, "recovery": n.recovery,
        "data_quality": n.data_quality, "availability_verification": n.availability_verification,
        "eligibility": n.eligibility, "wait_time": n.wait_time, "recommendation": n.recommendation,
        "expand_search_options": n.expand_search_options, "expansion_approval": n.expansion_approval,
        "patient_review": n.patient_review, "booking_preparation": n.booking_preparation,
        "human_approval": n.human_approval, "booking_handoff": n.booking_handoff,
        "confirmation_verification": n.confirmation_verification, "notification": n.notification,
        "audit": n.audit_node,
    }
    for name, fn in nodes.items():
        g.add_node(name, wrap(name, fn))
    g.add_edge(START, "intake")
    g.add_conditional_edges("intake", route_after_intake, ["clinical_safety", "audit"])
    g.add_conditional_edges("clinical_safety", route_after_safety,
                            ["safety_interruption", "service_classification", "audit"])
    g.add_edge("safety_interruption", "audit")
    g.add_conditional_edges("service_classification", route_after_classification, ["facility_discovery", "audit"])
    g.add_conditional_edges("facility_discovery", route_linear("geospatial"), ["geospatial", "audit"])
    g.add_conditional_edges("geospatial", route_linear("availability_search"), ["availability_search", "audit"])
    g.add_conditional_edges("availability_search", route_after_availability, ["recovery", "data_quality", "audit"])
    g.add_conditional_edges("recovery", route_linear("data_quality"), ["data_quality", "audit"])
    g.add_conditional_edges("data_quality", route_linear("availability_verification"),
                            ["availability_verification", "audit"])
    g.add_conditional_edges("availability_verification", route_linear("eligibility"), ["eligibility", "audit"])
    g.add_conditional_edges("eligibility", route_linear("wait_time"), ["wait_time", "audit"])
    g.add_conditional_edges("wait_time", route_linear("recommendation"), ["recommendation", "audit"])
    g.add_conditional_edges("recommendation", route_after_recommendation,
                            ["expand_search_options", "patient_review", "audit"])
    g.add_conditional_edges("expand_search_options", route_after_expand, ["expansion_approval", "patient_review"])
    g.add_conditional_edges("expansion_approval", route_after_expansion_approval,
                            ["facility_discovery", "patient_review"])
    g.add_conditional_edges("patient_review", route_after_review, ["booking_preparation", "audit"])
    g.add_conditional_edges("booking_preparation", route_after_booking_prep, ["human_approval", "audit"])
    g.add_conditional_edges("human_approval", route_after_human_approval, ["booking_handoff", "audit"])
    g.add_edge("booking_handoff", "confirmation_verification")
    g.add_edge("confirmation_verification", "notification")
    g.add_edge("notification", "audit")
    g.add_edge("audit", END)
    return g


@lru_cache
def checkpointer() -> SqliteSaver:
    path = get_settings().checkpoint_db_path
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver


@lru_cache
def compiled_graph():
    return build_graph().compile(checkpointer=checkpointer())


def mermaid() -> str:
    return build_graph().compile().get_graph().draw_mermaid()


def reset_cache() -> None:
    compiled_graph.cache_clear()
    checkpointer.cache_clear()
