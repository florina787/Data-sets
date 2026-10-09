"""LangGraph supervisor graph.

USER REQUEST -> MATTER CONTEXT -> ACCESS CONTROL -(denied)-> STOP + AUDIT
            -> ETHICAL WALL -(blocked)-> STOP + AUDIT
            -> AI POLICY (MatterGuard) -(AI prohibited)-> HUMAN / TRADITIONAL ROUTE
                                       -(provider prohibited)-> POLICY BLOCK
            -> AI SUITABILITY -> SUPERVISOR -> AI ROUTER
            -> {HUMAN LAWYER | TRADITIONAL SEARCH | INTERNAL AI | EXTERNAL LEGAL AI}
            -> EXECUTE AGENTS (bounded loop) -> CITATION CHECK -> PLAYBOOK CHECK -> CONFIDENTIALITY / PRIVILEGE
            -> ASSURANCE -> HUMAN REVIEW -> FINALIZE (VALUE + AUDIT)
"""

from __future__ import annotations

import time
import uuid
from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.agents import assurance as assurance_agents
from app.agents import core
from app.agents.legal import WORK_AGENTS
from app.config import get_settings
from app.copilot.composer import STATUS_PRIORITY, compose
from app.graph.context import IterationLimitExceeded, RequestTimeout, RunContext
from app.graph.state import LexGuardState
from app.models.db import WorkflowRunRow, session
from app.observability.logging import log_event
from app.providers import llm
from app.services.data_store import get_store
from app.valueiq import service as valueiq

TERMINAL = {"ACCESS_DENIED", "BLOCKED", "HALTED", "ERROR", "NEEDS_INPUT"}


def _node(name: str, enforce_deadline: bool = True):
    def deco(fn):
        def wrapped(state: dict, config) -> dict:
            ctx: RunContext = config["configurable"]["ctx"]
            t0 = time.perf_counter()
            try:
                if enforce_deadline:
                    ctx.check_deadline()
                out = fn(state, ctx) or {}
            except RequestTimeout as e:
                ctx.audit("REQUEST_TIMEOUT", {"node": name}, "WARNING")
                out = {"status": "HALTED", "errors": [str(e)],
                       "agent_trace": [{"label": "Time budget exceeded - workflow halted", "agent": name, "status": "error",
                                        "detail": str(e)}]}
            except PermissionError as e:
                out = {"status": "BLOCKED", "errors": [f"{name}: {e}"], "answer": f"Blocked by control: {e}",
                       "agent_trace": [{"label": "Control blocked an agent action", "agent": name, "status": "blocked",
                                        "detail": str(e)}]}
            except Exception as e:  # noqa: BLE001 - surfaced as structured error, never silently ignored
                ctx.audit("NODE_ERROR", {"node": name, "error": type(e).__name__}, "WARNING")
                out = {"status": "ERROR", "errors": [f"{name}: {type(e).__name__}: {e}"],
                       "agent_trace": [{"label": f"Error in {name}", "agent": name, "status": "error", "detail": str(e)}]}
            dt = round((time.perf_counter() - t0) * 1000, 2)
            for t in out.get("agent_trace", []):
                t.setdefault("duration_ms", dt)
                t.setdefault("node", name)
            out["graph_path"] = [name]
            return out
        wrapped.__name__ = name
        wrapped.__doc__ = fn.__doc__
        return wrapped
    return deco


# ------------------------------------------------------------------------------------------- nodes
matter_context = _node("matter_context")(core.matter_intake)
access_control = _node("access_control")(core.access_control)
ethical_wall = _node("ethical_wall")(core.ethical_wall)
ai_policy = _node("ai_policy")(core.ai_policy)
suitability = _node("ai_suitability")(core.assess_suitability)
supervisor = _node("supervisor")(core.supervisor)
ai_router = _node("ai_router")(core.route)
citation_check = _node("citation_check")(assurance_agents.citation_check)
playbook_check = _node("playbook_check")(assurance_agents.playbook_check)
privilege_check = _node("privilege_check")(assurance_agents.privilege_check)
assurance = _node("assurance")(assurance_agents.assurance)
human_review = _node("human_review")(assurance_agents.human_review)


@_node("stop_audit", enforce_deadline=False)
def stop_audit(state: dict, ctx: RunContext) -> dict:
    ctx.audit("WORKFLOW_STOPPED", {"reason": "access control", "retrieval_performed": False}, "WARNING")
    return {"agent_trace": [{"label": "Workflow stopped and audited - no retrieval performed", "agent": "supervisor",
                             "status": "blocked", "detail": ""}]}


@_node("policy_block")
def policy_block(state: dict, ctx: RunContext) -> dict:
    return {"agent_trace": [{"label": "Allowed alternative offered", "agent": "ai_policy", "status": "ok",
                             "detail": "; ".join((state.get("ai_policy") or {}).get("alternatives", []))}]}


@_node("human_traditional_route")
def human_traditional_route(state: dict, ctx: RunContext) -> dict:
    ctx.audit("ROUTING_DECISION", {"route": "HUMAN_LAWYER", "reason": "AI prohibited by client (Level 0)"})
    return {"routing_decision": {"route": "HUMAN_LAWYER", "provider_id": None, "workflow_id": None,
                                 "reasons": ["Client prohibits all AI use (Level 0)."],
                                 "ai_support_permitted": ["Traditional keyword search (non-generative)"], "options": []},
            "agent_trace": [{"label": "Routed to human lawyer / traditional workflow", "agent": "ai_routing", "status": "ok",
                             "detail": "No AI tools invoked."}]}


def _route_node(name: str, label: str):
    @_node(name)
    def _n(state: dict, ctx: RunContext) -> dict:
        rd = state.get("routing_decision") or {}
        return {"agent_trace": [{"label": label, "agent": "ai_routing", "status": "ok",
                                 "detail": f"Provider: {rd.get('provider_id') or 'none'}"}]}
    return _n


human_lawyer_route = _route_node("human_lawyer_route", "Human-lawyer route: AI limited to decision support")
traditional_search_route = _route_node("traditional_search_route", "Traditional search route (non-generative)")
internal_ai_route = _route_node("internal_ai_route", "Internal AI route (firm-hosted, permission-aware)")
external_ai_route = _route_node("external_ai_route", "External legal-AI route (approved provider, gateway-enforced)")


@_node("execute_agents")
def execute_agents(state: dict, ctx: RunContext) -> dict:
    plan = state.get("plan") or []
    idx = state.get("plan_index", 0)
    iterations = state.get("iterations", 0)
    if idx >= len(plan):
        return {}
    if iterations >= ctx.max_steps:
        ctx.audit("AGENT_ITERATION_LIMIT", {"max_steps": ctx.max_steps, "plan": plan}, "WARNING")
        raise_iteration = IterationLimitExceeded(f"Agent iteration limit ({ctx.max_steps}) reached.")
        return {"status": "HALTED", "errors": [str(raise_iteration)], "plan_index": len(plan),
                "agent_trace": [{"label": "Agent iteration limit reached - workflow halted", "agent": "supervisor",
                                 "status": "error", "detail": str(raise_iteration)}]}
    agent_name = plan[idx]
    fn = WORK_AGENTS[agent_name]
    ctx.audit("AGENT_INVOKED", {"agent": agent_name, "step": idx + 1})
    out = fn(state, ctx) or {}
    out["plan_index"] = idx + 1
    out["iterations"] = iterations + 1
    return out


@_node("finalize", enforce_deadline=False)
def finalize(state: dict, ctx: RunContext) -> dict:
    statuses = [state.get("status")] if state.get("status") else []
    if state.get("human_review"):
        statuses.append("REVIEW_REQUIRED")
    status = next((s for s in STATUS_PRIORITY if s in statuses), state.get("status") or "COMPLETED")
    if state.get("status") == "HUMAN_ROUTE":
        status = "HUMAN_ROUTE"
    wp = state.get("work_product") or {}
    review = state.get("review") or {}
    value = None
    if wp and status not in ("ACCESS_DENIED", "BLOCKED"):
        units = review.get("documents_processed") or len(wp.get("propositions", [])) or 1
        devs = sum(1 for r in state.get("playbook_results", []) if r["result"] != "ALIGNED")
        value = valueiq.estimate_run(state.get("workflow"), units, review_items=review.get("clauses", 0), deviations=devs)
    resp = compose(state, ctx, status, value)
    answer, used_llm = llm.narrate(resp["answer"], (state.get("ai_policy") or {}).get("allowed_tools", []))
    resp["answer"] = answer
    latency = round((time.perf_counter() - ctx.started) * 1000, 1)
    est_cost = round(0.0004 * (review.get("documents_processed") or 0) + 0.01 * len(state.get("agents_invoked", [])), 4)
    ctx.audit("FINAL_STATUS", {"status": resp["status"], "work_product_id": resp.get("work_product_id"),
                               "latency_ms": latency, "graph_path": state.get("graph_path", []) + ["finalize"]},
              "INFO" if resp["status"] not in ("ACCESS_DENIED", "BLOCKED") else "WARNING")
    if ctx.persist:
        with session() as s:
            s.add(WorkflowRunRow(run_id="RUN-" + uuid.uuid4().hex[:12], request_id=ctx.request_id, user_id=ctx.user_id,
                                 matter_id=ctx.matter_id, practice_id=(ctx.store.matters[ctx.matter_id].practice_id
                                                                       if ctx.matter_id in ctx.store.matters else None),
                                 intent=state.get("intent", "unknown"), route=(state.get("routing_decision") or {}).get("route"),
                                 provider_id=state.get("provider"), workflow_id=state.get("workflow"), status=resp["status"],
                                 latency_ms=latency, est_cost_usd=est_cost,
                                 metrics={"value": value or {}, "assurance_status": (resp.get("assurance") or {}).get("status", "N/A"),
                                          "citation_issues": sum(1 for c in state.get("citations", []) if c["status"] != "SUPPORTED"),
                                          "playbook_deviations": sum(1 for r in state.get("playbook_results", []) if r["result"] != "ALIGNED")}))
            s.commit()
    trace_tools = ctx.tools.calls if ctx.tools else []
    resp["metrics"] = {"latency_ms": latency, "est_cost_usd": est_cost, "paid_llm_calls": int(used_llm),
                       "agents_invoked": list(dict.fromkeys(state.get("agents_invoked", []))),
                       "tools_invoked": sorted({t["tool"] for t in trace_tools}), "tool_calls": len(trace_tools),
                       "graph_path": state.get("graph_path", []) + ["finalize"], "demo_mode": ctx.settings.demo_mode}
    log_event("copilot_request", request_id=ctx.request_id, user=ctx.user_id, client=ctx.client_id, matter=ctx.matter_id,
              intent=state.get("intent"), graph_path=resp["metrics"]["graph_path"], agents=resp["metrics"]["agents_invoked"],
              tools=resp["metrics"]["tools_invoked"],
              retrieval_source_ids=[s.get("doc_id") for s in state.get("retrieved_sources", [])][:50],
              provider=state.get("provider"), policy_decision=(state.get("ai_policy") or {}).get("decision"),
              risk=state.get("risk"), assurance=(resp.get("assurance") or {}).get("status"),
              human_review=bool(state.get("human_review")), latency_ms=latency, est_cost_usd=est_cost,
              errors=state.get("errors", []), status=resp["status"])
    return {"response": resp, "status": resp["status"], "latency": latency, "cost": est_cost}


# ------------------------------------------------------------------------------------------- edges
def _after_access(state: dict) -> str:
    return "stop_audit" if state.get("status") == "ACCESS_DENIED" else "ethical_wall"


def _after_wall(state: dict) -> str:
    return "stop_audit" if state.get("status") == "ACCESS_DENIED" else "ai_policy"


def _after_policy(state: dict) -> str:
    s = state.get("status")
    if s == "HUMAN_ROUTE":
        return "human_traditional_route"
    if s == "BLOCKED":
        return "policy_block"
    if s in TERMINAL:
        return "finalize"
    return "ai_suitability"


def _after_supervisor(state: dict) -> str:
    return "finalize" if state.get("status") in TERMINAL else "ai_router"


def _after_router(state: dict) -> str:
    route = (state.get("routing_decision") or {}).get("route")
    return {"HUMAN_LAWYER": "human_lawyer_route", "TRADITIONAL_SEARCH": "traditional_search_route",
            "EXTERNAL_LEGAL_AI": "external_ai_route", "NO_AI": "finalize"}.get(route, "internal_ai_route")


def _after_execute(state: dict) -> str:
    if state.get("status") in TERMINAL:
        return "finalize"
    if state.get("plan_index", 0) < len(state.get("plan") or []):
        return "execute_agents"
    if state.get("work_product") and (state.get("work_product") or {}).get("propositions") is not None:
        return "citation_check"
    return "finalize"


def build_graph():
    g = StateGraph(LexGuardState)
    for name, fn in [("matter_context", matter_context), ("access_control", access_control), ("ethical_wall", ethical_wall),
                     ("ai_policy", ai_policy), ("ai_suitability", suitability), ("supervisor", supervisor),
                     ("ai_router", ai_router), ("human_lawyer_route", human_lawyer_route),
                     ("traditional_search_route", traditional_search_route), ("internal_ai_route", internal_ai_route),
                     ("external_ai_route", external_ai_route), ("execute_agents", execute_agents),
                     ("citation_check", citation_check), ("playbook_check", playbook_check),
                     ("privilege_check", privilege_check), ("assurance", assurance), ("human_review", human_review),
                     ("stop_audit", stop_audit), ("policy_block", policy_block),
                     ("human_traditional_route", human_traditional_route), ("finalize", finalize)]:
        g.add_node(name, fn)
    g.add_edge(START, "matter_context")
    g.add_edge("matter_context", "access_control")
    g.add_conditional_edges("access_control", _after_access, ["stop_audit", "ethical_wall"])
    g.add_conditional_edges("ethical_wall", _after_wall, ["stop_audit", "ai_policy"])
    g.add_conditional_edges("ai_policy", _after_policy, ["human_traditional_route", "policy_block", "ai_suitability", "finalize"])
    g.add_edge("ai_suitability", "supervisor")
    g.add_conditional_edges("supervisor", _after_supervisor, ["finalize", "ai_router"])
    g.add_conditional_edges("ai_router", _after_router, ["human_lawyer_route", "traditional_search_route",
                                                          "external_ai_route", "internal_ai_route", "finalize"])
    for r in ("human_lawyer_route", "traditional_search_route", "internal_ai_route", "external_ai_route"):
        g.add_edge(r, "execute_agents")
    g.add_conditional_edges("execute_agents", _after_execute, ["execute_agents", "citation_check", "finalize"])
    g.add_edge("citation_check", "playbook_check")
    g.add_edge("playbook_check", "privilege_check")
    g.add_edge("privilege_check", "assurance")
    g.add_edge("assurance", "human_review")
    g.add_edge("human_review", "finalize")
    for n in ("stop_audit", "policy_block", "human_traditional_route"):
        g.add_edge(n, "finalize")
    g.add_edge("finalize", END)
    return g.compile()


@lru_cache
def get_graph():
    return build_graph()


def run_copilot(*, user_id: str, matter_id: str | None, message: str, selected_finding_id: str | None = None,
                destination: str | None = None, cfg: dict | None = None, persist: bool = True) -> dict:
    settings = get_settings()
    ctx = RunContext(store=get_store(), settings=settings, request_id="REQ-" + uuid.uuid4().hex[:16], user_id=user_id,
                     matter_id=matter_id, message=message, selected_finding_id=selected_finding_id,
                     destination_override=destination, cfg=cfg or {}, persist=persist)
    final = get_graph().invoke({"request_id": ctx.request_id, "audit_events": [], "agent_trace": [], "graph_path": [],
                                "errors": [], "agents_invoked": []},
                               config={"configurable": {"ctx": ctx}, "recursion_limit": 80})
    resp = final["response"]
    trace = final.get("agent_trace", [])
    resp.update(request_id=ctx.request_id, user_id=user_id, matter_id=matter_id,
                agent_trace=[dict(t, step=i + 1) for i, t in enumerate(trace)],
                audit_event_ids=list(ctx.audit_ids), errors=final.get("errors", []))
    return resp
