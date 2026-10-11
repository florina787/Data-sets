"""LangGraph supervisor with bounded agent nodes and durable checkpoints.

The graph is: supervisor -> <next pending agent> -> supervisor -> ... -> END. Only the agents a
lifecycle step needs are scheduled ("invoke only relevant nodes"). After every node the workflow
writes a WorkflowCheckpoint row (state + remaining nodes) and commits, so a crash mid-run can be
resumed from the last completed node (`resume`). Human review points are recorded as INTERRUPTED
checkpoints naming the awaited decision; the corresponding API call resumes the thread.
"""
from __future__ import annotations

import operator
import time
import uuid
from typing import Annotated, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.agents import AGENTS, CONTRACTS, ToolGateway, summary_contradicts
from app.agents.llm import get_provider
from app.errors import ComputationFailed, NotFound
from app.models.orm import AgentInvocation, ChangeRequest, CopilotMessage, WorkflowCheckpoint, new_id
from app.security.redaction import contains_image_payload
from app.services import audit

# Test hook: node names listed here raise inside the node (simulated crash).
FAULTS: set[str] = set()


def _merge_usage(a: dict, b: dict) -> dict:
    out = dict(a or {})
    for k, v in (b or {}).items():
        out[k] = (out.get(k) or 0) + (v or 0)
    return out


class ChangeState(TypedDict, total=False):
    change_id: str
    tenant_id: str
    status: str
    requirement_version: str | None
    unresolved_questions: list[dict]
    evidence_refs: list[dict]
    impact: dict | None
    baseline_model_id: str
    candidate_model_id: str | None
    code_revision: str | None
    dataset_snapshot_id: str | None
    evaluation_config_id: str | None
    evaluation_run_id: str | None
    gate_results: list[dict]
    approval_ids: list[str]
    release_id: str | None
    alert_ids: list[str]
    trace_id: str
    usage: Annotated[dict, _merge_usage]
    errors: Annotated[list[dict], operator.add]
    pending: list[str]
    completed: Annotated[list[str], operator.add]
    outputs: Annotated[dict, lambda a, b: {**(a or {}), **(b or {})}]


def initial_state(ch: ChangeState | ChangeRequest) -> ChangeState:
    return ChangeState(
        change_id=ch.id, tenant_id=ch.tenant_id, status=ch.status, requirement_version=ch.current_requirement_version_id,
        unresolved_questions=[], evidence_refs=[], impact=None, baseline_model_id=ch.baseline_model_id,
        candidate_model_id=ch.candidate_model_id, code_revision=ch.code_revision_id, dataset_snapshot_id=ch.dataset_snapshot_id,
        evaluation_config_id=ch.evaluation_config_id, evaluation_run_id=ch.latest_evaluation_run_id, gate_results=[],
        approval_ids=[], release_id=None, alert_ids=[], trace_id=ch.trace_id, usage={}, errors=[], pending=[], completed=[], outputs={})


ToolFactory = Callable[[str], tuple[dict, dict]]  # agent -> (facts, extra tools)


def _state_update(agent: str, data: dict) -> dict:
    """Map an agent's output into typed state fields (references only, never image payloads)."""
    if agent == "requirements":
        return {"unresolved_questions": [{"key": a["key"], "question": a["question"]} for a in data["ambiguities"]]}
    if agent == "evidence":
        return {"evidence_refs": [{k: c[k] for k in ("source_id", "source_version", "section", "validation_status")}
                                  for c in data["citations"]]}
    if agent == "impact":
        return {"impact": {"components": [c["id"] for c in data["components"]], "owners": data["owners"]}}
    if agent == "development":
        return {"code_revision": data["revision_id"]}
    if agent == "evaluation":
        return {"gate_results": [{"outcome": data["outcome"]}]}
    return {}


def _checkpoint(db: Session, thread_id: str, change_id: str, node: str, status: str, state: dict, pending: list[str],
                interrupt: dict | None = None) -> None:
    step = (db.execute(select(WorkflowCheckpoint.step).where(WorkflowCheckpoint.thread_id == thread_id)
                       .order_by(WorkflowCheckpoint.step.desc()).limit(1)).scalar_one_or_none() or 0) + 1
    clean = {k: v for k, v in state.items() if k != "outputs"}
    if contains_image_payload(clean):
        raise ComputationFailed("image_in_state", "Workflow state must hold references, not image payloads")
    db.add(WorkflowCheckpoint(change_id=change_id, thread_id=thread_id, step=step, node=node, status=status,
                              state=clean, pending_nodes=pending, interrupt=interrupt))


def _budget_remaining(db: Session, change_id: str) -> int:
    from app.config import get_settings
    used = sum((i.input_tokens or 0) + (i.output_tokens or 0) for i in
               db.execute(select(AgentInvocation).where(AgentInvocation.change_id == change_id)).scalars())
    return get_settings().llm_token_budget_per_change - used


def _make_node(db: Session, agent: str, roles: list[str], thread_id: str, tool_factory: ToolFactory, actor_id: str):
    def node(state: ChangeState) -> dict:
        pending = list(state.get("pending", []))
        remaining = pending[1:]
        t0 = time.perf_counter()
        try:
            if agent in FAULTS:
                raise RuntimeError(f"injected fault in {agent}")
            facts, extra = tool_factory(agent)
            from app.agents.agents import default_tools
            gw = ToolGateway(agent, roles, default_tools(roles, extra))
            res = AGENTS[agent](gw, facts)
        except Exception as exc:  # recorded, checkpointed, re-raised by run()
            db.rollback()
            err = {"agent": agent, "error": type(exc).__name__, "message": str(exc)[:500]}
            _checkpoint(db, thread_id, state["change_id"], agent, "FAILED", {**state, "errors": state.get("errors", []) + [err]}, pending)
            db.add(AgentInvocation(id=new_id("AI"), change_id=state["change_id"], thread_id=thread_id, agent=agent, status="ERROR",
                                   language_mode=get_provider().mode, latency_ms=round((time.perf_counter() - t0) * 1000, 2),
                                   output={}, error=err))
            db.commit()
            raise
        latency = round((time.perf_counter() - t0) * 1000, 2)
        provider = get_provider()
        llm = provider.summarize(f"summary_{agent}", {"summary": res.summary, "data": res.data}, _budget_remaining(db, state["change_id"]))
        llm_summary, llm_err = None, llm.error
        if llm.output is not None:
            computed = res.data.get("outcome") or res.data.get("recommendation")
            if summary_contradicts(agent, computed, llm.output.summary):
                llm_err = {"code": "summary_contradicts_computed_result",
                           "message": "Generated summary claimed a favourable result the policy engine did not produce; rejected."}
            else:
                llm_summary = llm.output.model_dump()
        out = {**res.model_dump(), "language_mode": llm.mode, "llm_summary": llm_summary, "llm_error": llm_err}
        db.add(AgentInvocation(id=new_id("AI"), change_id=state["change_id"], thread_id=thread_id, agent=agent,
                               status="OK" if not llm_err else "OK_WITH_LLM_ERROR", language_mode=llm.mode,
                               provider=llm.provider, model=llm.model, prompt_id=llm.prompt_id,
                               latency_ms=latency + llm.latency_ms, tool_calls=gw.calls, input_tokens=llm.input_tokens,
                               output_tokens=llm.output_tokens, cost_usd=llm.cost_usd, price_config=llm.price_config,
                               output=out, error=llm_err))
        text = llm_summary["summary"] if llm_summary else res.summary
        db.add(CopilotMessage(change_id=state["change_id"], role="agent", author=f"{agent} agent",
                              text=text + ("" if llm_summary else "  [deterministic summary]"), refs=res.refs[:8]))
        audit.record(db, tenant_id=state["tenant_id"], change_id=state["change_id"], actor_id=f"agent:{agent}",
                     action=f"agent.{agent}", status="OK", reason=res.summary[:500], trace_id=state["trace_id"],
                     input_refs={"thread_id": thread_id, "tools": [c["tool"] for c in gw.calls]},
                     version_refs={"language_mode": llm.mode, "model": llm.model})
        upd = {**_state_update(agent, res.data), "pending": remaining, "completed": [agent], "outputs": {agent: out},
               "usage": {"agent_calls": 1, "input_tokens": llm.input_tokens or 0, "output_tokens": llm.output_tokens or 0}}
        if llm_err:
            upd["errors"] = [{"agent": agent, **llm_err}]
        merged = {**state, **{k: v for k, v in upd.items() if k not in ("completed", "errors", "usage", "outputs")}}
        merged["completed"] = state.get("completed", []) + [agent]
        merged["errors"] = state.get("errors", []) + upd.get("errors", [])
        merged["usage"] = _merge_usage(state.get("usage", {}), upd["usage"])
        _checkpoint(db, thread_id, state["change_id"], agent, "COMPLETED", merged, remaining)
        db.commit()
        return upd
    return node


def _route(state: ChangeState) -> str:
    return state["pending"][0] if state.get("pending") else END


def build_graph(db: Session, agents: list[str], roles: list[str], thread_id: str, tool_factory: ToolFactory, actor_id: str):
    g = StateGraph(ChangeState)
    g.add_node("supervisor", lambda s: {})
    for a in dict.fromkeys(agents):
        g.add_node(a, _make_node(db, a, roles, thread_id, tool_factory, actor_id))
        g.add_edge(a, "supervisor")
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", _route, {**{a: a for a in agents}, END: END})
    return g.compile()


def run(db: Session, ch: ChangeRequest, agents: list[str], roles: list[str], tool_factory: ToolFactory, actor_id: str,
        interrupt: dict | None = None, thread_id: str | None = None, state: ChangeState | None = None) -> ChangeState:
    unknown = [a for a in agents if a not in CONTRACTS]
    if unknown:
        raise NotFound("unknown_agent", f"Unknown agents {unknown}")
    thread_id = thread_id or f"T-{uuid.uuid4().hex[:10]}"
    st = state or initial_state(ch)
    st["pending"] = list(agents)
    db.commit()  # preconditions are durable before agents run
    graph = build_graph(db, agents, roles, thread_id, tool_factory, actor_id)
    try:
        final = graph.invoke(st, {"recursion_limit": 4 * len(agents) + 4})
    except Exception as exc:
        raise ComputationFailed("agent_node_failed", f"Workflow thread {thread_id} failed: {exc}",
                                {"thread_id": thread_id, "resumable": True}) from exc
    if interrupt:
        _checkpoint(db, thread_id, ch.id, "supervisor", "INTERRUPTED", final, [], interrupt)
        db.commit()
    final["thread_id"] = thread_id  # type: ignore[typeddict-unknown-key]
    return final


def resume(db: Session, ch: ChangeRequest, thread_id: str, roles: list[str], tool_factory: ToolFactory, actor_id: str) -> ChangeState:
    cp = db.execute(select(WorkflowCheckpoint).where(WorkflowCheckpoint.thread_id == thread_id)
                    .order_by(WorkflowCheckpoint.step.desc()).limit(1)).scalar_one_or_none()
    if cp is None:
        raise NotFound("checkpoint_not_found", f"No checkpoint for thread {thread_id}")
    if cp.status != "FAILED":
        raise ComputationFailed("not_resumable", f"Thread {thread_id} last status {cp.status}; nothing to resume")
    state = ChangeState(**{**cp.state, "outputs": {}})
    return run(db, ch, list(cp.pending_nodes), roles, tool_factory, actor_id, thread_id=thread_id, state=state)


def latest_interrupt(db: Session, change_id: str) -> dict | None:
    cp = db.execute(select(WorkflowCheckpoint).where(WorkflowCheckpoint.change_id == change_id)
                    .order_by(WorkflowCheckpoint.id.desc()).limit(1)).scalar_one_or_none()
    return {"thread_id": cp.thread_id, "status": cp.status, "node": cp.node, "interrupt": cp.interrupt,
            "pending": cp.pending_nodes} if cp else None
