"""The investigation workflow: one LangGraph graph, four agent nodes.

    triage -> evidence -> diagnosis -+-> planning -> human_review (interrupt) -> END
                  ^                  |
                  +-- missing signal-+-> finalize (NEEDS_INFORMATION / ESCALATED / FAILED)

Nodes communicate only through the shared typed state below plus persisted
records referenced by id (evidence snapshots, recommendations). This is an
in-process graph; there is no agent-to-agent network protocol.

Every node performs its case-state transition and audit write in one
database transaction, so status events always reflect persisted state.
"""
from __future__ import annotations

import hashlib
import json
import operator
import time
import uuid
from datetime import timedelta
from typing import Annotated, Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from sqlalchemy import select, update

from ..agents import diagnosis as diagnosis_agent
from ..agents import evidence as evidence_agent
from ..agents import planning as planning_agent
from ..agents import triage as triage_agent
from ..agents.contracts import DiagnosisOutput, EvidenceBundle, TriageInput, TriageOutput
from ..agents.providers import ProviderUnavailable, get_provider
from ..config import get_settings
from ..db import session_scope, utcnow
from ..models.orm import (
    Approval, Case, EvidenceReference, EvidenceSnapshot, Hypothesis, Recommendation,
    SupportInteraction,
)
from ..observability import audit
from ..policies.catalog import load_catalog
from ..policies.engine import payload_hash
from ..policies.state_machine import CaseStatus as S
from ..policies.state_machine import transition
from .checkpoints import get_checkpointer


def _merge_usage(a: dict, b: dict) -> dict:
    out = dict(a or {})
    for k, v in (b or {}).items():
        if isinstance(v, (int, float)) and isinstance(out.get(k), (int, float)):
            out[k] = out[k] + v
        elif v is not None:
            out[k] = v
    return out


class CaseWorkflowState(TypedDict, total=False):
    case_id: str
    tenant_id: str
    actor_id: str
    actor_role: str
    status: str
    started_at: float
    symptoms: dict
    evidence_refs: list[dict]
    evidence_snapshot_id: str | None
    missing_evidence: list[str]
    requested_evidence: list[str]
    hypotheses: list[dict]
    diagnosis: dict | None
    proposed_action: dict | None
    policy_decision: dict | None
    recommendation_id: str | None
    approval_id: str | None
    execution_id: str | None
    recovery_result: dict | None
    iteration_count: int
    usage: Annotated[dict, _merge_usage]
    errors: Annotated[list[dict], operator.add]
    trace_id: str
    route: str


# Test hook: raise inside a node to simulate a process crash.
FAULT_HOOKS: dict[str, Callable[[CaseWorkflowState], None]] = {}


class NodeError(Exception):
    pass


def _usage_dict(usage) -> dict:
    if usage is None:
        return {}
    d = usage.to_dict()
    return {"input_tokens": d["input_tokens"] or 0, "output_tokens": d["output_tokens"] or 0,
            "calls": d["calls"], "estimated_cost_usd": d["estimated_cost_usd"] or 0.0,
            "usage_available": d["usage_available"], "provider": d["provider"], "model": d["model"],
            "pricing_configured_on": d["pricing_configured_on"]}


def _budget_used(state: CaseWorkflowState) -> int:
    u = state.get("usage") or {}
    return int(u.get("input_tokens", 0) or 0) + int(u.get("output_tokens", 0) or 0)


def _audit(db, state, event_type, case, *, node=None, frm=None, to=None, detail=None, latency=None,
           usage=None):
    p = get_provider()
    audit.record(db, tenant_id=state["tenant_id"], actor_id=state["actor_id"],
                 actor_role=state["actor_role"], event_type=event_type, case_id=case.id,
                 trace_id=state["trace_id"], node=node, from_status=frm, to_status=to,
                 generation_mode=p.mode, connector_mode=get_settings().connector_mode,
                 policy_version=load_catalog().version, latency_ms=latency, usage=usage or {},
                 detail=detail or {})


def _move(db, state, case, target: S, node: str, reason: str, detail: dict | None = None,
          usage: dict | None = None, latency: float | None = None) -> None:
    prev = transition(db, case, target, reason)
    _audit(db, state, "STATE_TRANSITION", case, node=node, frm=prev, to=target.value,
           detail={"reason": reason, **(detail or {})}, usage=usage, latency=latency)


def _check_limits(state: CaseWorkflowState) -> str | None:
    s = get_settings()
    if time.time() - state.get("started_at", time.time()) > s.max_investigation_seconds:
        return "investigation time budget exhausted"
    if _budget_used(state) >= s.llm_case_token_budget:
        return "token budget exhausted"
    return None


def _guard(node_name: str):
    """Wrap a node: fault hooks, timing, and conversion of unexpected errors
    into an explicit FAILED transition (never a silent success)."""

    def deco(fn):
        def wrapper(state: CaseWorkflowState) -> dict:
            hook = FAULT_HOOKS.get(node_name)
            if hook:
                hook(state)
            t0 = time.perf_counter()
            try:
                out = fn(state, t0)
            except ProviderUnavailable as exc:
                return {"route": "fail", "errors": [{"node": node_name, "code": exc.code,
                                                     "message": exc.reason}]}
            except NodeError as exc:
                return {"route": "fail", "errors": [{"node": node_name, "code": "NODE_ERROR",
                                                     "message": str(exc)}]}
            return out

        wrapper.__name__ = fn.__name__
        return wrapper

    return deco


def _load_case(db, state) -> Case:
    case = db.scalar(select(Case).where(Case.id == state["case_id"], Case.tenant_id == state["tenant_id"]))
    if case is None:
        raise NodeError("case not found in tenant scope")
    return case


# ------------------------------------------------------------------ nodes
@_guard("triage")
def triage_node(state: CaseWorkflowState, t0: float) -> dict:
    provider = get_provider()
    with session_scope() as db:
        case = _load_case(db, state)
        contacts = db.scalars(select(SupportInteraction.id).where(
            SupportInteraction.account_id == case.account_id,
            SupportInteraction.tenant_id == case.tenant_id)).all()
        clar = (case.reported_symptoms or {}).get("clarifications", [])
        text = case.complaint_text + ("".join(f"\nClarification: {c['text']}" for c in clar))
        inp = TriageInput(case_id=case.id, product="home_internet", complaint_text=text,
                          prior_contact_count=len(contacts))
        out, usage = triage_agent.run(inp, provider, _budget_used(state))
        symptoms = {**out.model_dump(), "clarifications": clar}
        case.reported_symptoms = symptoms
        u = _usage_dict(usage)
        latency = (time.perf_counter() - t0) * 1000
        if case.status in (S.NEW.value, S.NEEDS_INFORMATION.value):
            _move(db, state, case, S.TRIAGED, "triage", "triage output validated",
                  {"symptoms": {k: symptoms[k] for k in ("symptom_pattern", "onset", "special_requests",
                                                          "customer_reported_actions")}},
                  usage=u, latency=latency)
        else:
            _audit(db, state, "NODE_COMPLETED", case, node="triage", detail={"re_investigation": True},
                   usage=u, latency=latency)
        return {"symptoms": symptoms, "status": case.status, "usage": u, "route": "ok"}


@_guard("evidence")
def evidence_node(state: CaseWorkflowState, t0: float) -> dict:
    provider = get_provider()
    limit = _check_limits(state)
    if limit:
        return {"route": "escalate", "errors": [{"node": "evidence", "code": "BUDGET", "message": limit}]}
    iteration = state.get("iteration_count", 0)
    with session_scope() as db:
        case = _load_case(db, state)
        if case.status != S.COLLECTING_EVIDENCE.value:
            _move(db, state, case, S.COLLECTING_EVIDENCE, "evidence",
                  "specific missing signal identified" if iteration else "scope check passed",
                  {"requested": state.get("requested_evidence", [])})
        triage = TriageOutput(**{k: v for k, v in case.reported_symptoms.items() if k != "clarifications"})
        tool_log: list[dict] = []
        now = utcnow()
        bundle, usage = evidence_agent.collect(
            db, tenant_id=state["tenant_id"], role=state["actor_role"], case=case, triage=triage,
            iteration=iteration, requested=state.get("requested_evidence", []), now=now,
            provider=provider, budget_used=_budget_used(state), tool_log=tool_log)
        snap = _persist_snapshot(db, case, bundle)
        u = _usage_dict(usage)
        injected = [i.source_id for i in bundle.items if "prompt_injection" in i.flags]
        _audit(db, state, "EVIDENCE_COLLECTED", case, node="evidence",
               detail={"snapshot_id": snap.id, "items": len(bundle.items), "facts": bundle.facts,
                       "missing": bundle.missing_evidence, "tool_calls": tool_log, "iteration": iteration},
               usage=u, latency=(time.perf_counter() - t0) * 1000)
        if injected:
            _audit(db, state, "PROMPT_INJECTION_QUARANTINED", case, node="evidence",
                   detail={"sources": injected})
        refs = [{"ref_id": i.ref_id, "source_type": i.source_type, "source_id": i.source_id,
                 "supports": i.supports, "opposes": i.opposes} for i in bundle.items]
        return {"evidence_snapshot_id": snap.id, "evidence_refs": refs,
                "missing_evidence": bundle.missing_evidence, "status": case.status,
                "iteration_count": iteration + 1, "usage": u, "route": "ok"}


def _persist_snapshot(db, case: Case, bundle: EvidenceBundle) -> EvidenceSnapshot:
    raw = bundle.model_dump()
    h = hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()
    snap = EvidenceSnapshot(id=f"SNAP-{uuid.uuid4().hex[:12]}", case_id=case.id, tenant_id=case.tenant_id,
                            created_at=utcnow(), content_hash=h, bundle=raw)
    db.add(snap)
    db.flush()
    for i in bundle.items:
        db.add(EvidenceReference(
            id=f"{snap.id}:{i.ref_id}", snapshot_id=snap.id, case_id=case.id, source_type=i.source_type,
            source_id=i.source_id, source_version=i.source_version, authority=i.authority, kind=i.kind,
            excerpt=i.excerpt, freshness=i.freshness, supports=i.supports, opposes=i.opposes,
            flags=i.flags, retrieved_at=utcnow()))
    return snap


def load_bundle(db, snapshot_id: str) -> EvidenceBundle:
    snap = db.get(EvidenceSnapshot, snapshot_id)
    return EvidenceBundle(**snap.bundle)


@_guard("diagnosis")
def diagnosis_node(state: CaseWorkflowState, t0: float) -> dict:
    provider = get_provider()
    s = get_settings()
    with session_scope() as db:
        case = _load_case(db, state)
        _move(db, state, case, S.ASSESSING, "diagnosis", "evidence bundle persisted")
        bundle = load_bundle(db, state["evidence_snapshot_id"])
        requested = state.get("requested_evidence", [])
        can_iterate = state.get("iteration_count", 0) < s.max_evidence_iterations and \
            "fresh_line_diagnostics" not in requested
        out, usage, errors = diagnosis_agent.run(bundle, provider, can_iterate=can_iterate,
                                                 budget_used=_budget_used(state))
        for rank, h in enumerate(out.hypotheses, start=1):
            db.add(Hypothesis(id=f"HYP-{uuid.uuid4().hex[:10]}", case_id=case.id,
                              snapshot_id=state["evidence_snapshot_id"], rank=rank, category=h.category,
                              statement=h.statement, sufficiency=h.sufficiency,
                              supporting_refs=h.supporting_refs, opposing_refs=h.opposing_refs))
        u = _usage_dict(usage)
        _audit(db, state, "DIAGNOSIS_COMPLETED", case, node="diagnosis",
               detail={"conclusion": out.conclusion, "summary": out.summary,
                       "hypotheses": [{"category": h.category, "sufficiency": h.sufficiency}
                                      for h in out.hypotheses],
                       "needs_more_evidence": out.needs_more_evidence, "validation_errors": errors},
               usage=u, latency=(time.perf_counter() - t0) * 1000)
        if out.needs_more_evidence:
            route = "more_evidence"
        elif out.escalate:
            route = "escalate"
        elif out.conclusion in ("INSUFFICIENT_EVIDENCE",):
            route = "needs_info"
        else:
            route = "plan"
        return {"diagnosis": out.model_dump(), "hypotheses": [h.model_dump() for h in out.hypotheses],
                "requested_evidence": sorted(set(requested) | set(out.needs_more_evidence)),
                "status": case.status, "usage": u, "route": route,
                "errors": [{"node": "diagnosis", "code": "VALIDATION", "message": e} for e in errors]}


@_guard("planning")
def planning_node(state: CaseWorkflowState, t0: float) -> dict:
    provider = get_provider()
    s = get_settings()
    with session_scope() as db:
        case = _load_case(db, state)
        bundle = load_bundle(db, state["evidence_snapshot_id"])
        diag = DiagnosisOutput(**state["diagnosis"])
        triage = TriageOutput(**{k: v for k, v in case.reported_symptoms.items() if k != "clarifications"})
        draft, decision, facts, usage, notes, refused = planning_agent.plan(
            case.id, case.service_id, triage, bundle, diag, provider, _budget_used(state))
        u = _usage_dict(usage)
        if draft is None or decision is None:
            return {"route": "escalate", "usage": u,
                    "errors": [{"node": "planning", "code": "NO_PERMITTED_ACTION",
                                "message": "; ".join(notes) or "no permitted action"}]}
        rec = create_recommendation(db, case, state["evidence_snapshot_id"], draft, decision, facts,
                                    proposed_by=state["actor_id"], generation_mode=provider.mode)
        _move(db, state, case, S.RECOMMENDATION_READY, "planning",
              "hypotheses validated and action selected",
              {"recommendation_id": rec.id, "action_type": rec.action_type,
               "policy_allowed": decision.allowed, "notes": notes,
               "refused_requests": [r.request for r in refused]},
              usage=u, latency=(time.perf_counter() - t0) * 1000)
        approval_id = None
        if decision.requires_approval and decision.allowed:
            appr = request_approval(db, case, rec, requested_by=state["actor_id"], ttl=s.approval_ttl_minutes)
            _move(db, state, case, S.AWAITING_APPROVAL, "planning", "approval record created",
                  {"approval_id": appr.id, "required_roles": appr.required_roles,
                   "separation_of_duties": appr.separation_of_duties})
            approval_id = appr.id
        return {"recommendation_id": rec.id, "approval_id": approval_id,
                "proposed_action": {"action_type": rec.action_type, "payload_hash": rec.payload_hash},
                "policy_decision": decision.to_dict(), "status": case.status, "usage": u,
                "route": "review" if approval_id else "done"}


def create_recommendation(db, case: Case, snapshot_id: str, draft, decision, facts, *, proposed_by: str,
                          generation_mode: str) -> Recommendation:
    db.execute(update(Recommendation).where(Recommendation.case_id == case.id,
                                            Recommendation.status == "active").values(status="superseded"))
    db.execute(update(Approval).where(Approval.case_id == case.id, Approval.status == "pending")
               .values(status="superseded"))
    rec = Recommendation(
        id=f"REC-{uuid.uuid4().hex[:10]}", case_id=case.id, tenant_id=case.tenant_id, snapshot_id=snapshot_id,
        action_type=draft.action_type, payload=draft.payload, payload_hash=payload_hash(draft.payload),
        purpose=draft.purpose, prerequisites=draft.prerequisites, evidence_refs=draft.evidence_refs,
        uncertainty=draft.uncertainty, risk=decision.risk,
        approval_requirement={"requires_approval": decision.requires_approval,
                              "approver_roles": decision.approver_roles,
                              "executor_roles": decision.executor_roles,
                              "separation_of_duties": decision.separation_of_duties,
                              "mvp_behavior": decision.mvp_behavior},
        policy_version=decision.policy_version, policy_decision={**decision.to_dict(), "facts": facts},
        prior_interventions=[p.model_dump() for p in draft.prior_interventions],
        refused_requests=[r.model_dump() for r in draft.refused_requests],
        alternatives=draft.alternatives, proposed_by=proposed_by, generation_mode=generation_mode,
        status="active", created_at=utcnow())
    db.add(rec)
    case.current_recommendation_id = rec.id
    db.flush()
    return rec


def request_approval(db, case: Case, rec: Recommendation, *, requested_by: str, ttl: int) -> Approval:
    now = utcnow()
    appr = Approval(
        id=f"APR-{uuid.uuid4().hex[:10]}", case_id=case.id, tenant_id=case.tenant_id, recommendation_id=rec.id,
        action_type=rec.action_type, payload_hash=rec.payload_hash, policy_version=rec.policy_version,
        evidence_snapshot_id=rec.snapshot_id, requested_by=requested_by, requested_at=now,
        required_roles=rec.approval_requirement["approver_roles"],
        separation_of_duties=rec.approval_requirement["separation_of_duties"], status="pending",
        expires_at=now + timedelta(minutes=ttl))
    db.add(appr)
    db.flush()
    return appr


def human_review_node(state: CaseWorkflowState) -> dict:
    """Durable wait for a human decision. The approval itself is recorded by
    the approval service in its own transaction; resuming only records that
    the graph observed it."""
    decision = interrupt({"approval_id": state.get("approval_id"), "case_id": state["case_id"]})
    with session_scope() as db:
        case = _load_case(db, state)
        _audit(db, state, "HUMAN_REVIEW_RESUMED", case, node="human_review",
               detail={"approval_id": state.get("approval_id"), "decision": decision})
    return {"status": case.status, "route": "done"}


def finalize_node(state: CaseWorkflowState) -> dict:
    route = state.get("route")
    with session_scope() as db:
        case = _load_case(db, state)
        diag = state.get("diagnosis") or {}
        errors = state.get("errors") or []
        if route == "needs_info":
            symptoms = case.reported_symptoms or {}
            questions = list(symptoms.get("clarifying_questions", []))
            questions.append("Can the customer keep the modem powered on so a fresh line test can be "
                             "collected? (Current diagnostics are stale or unavailable.)")
            _move(db, state, case, S.NEEDS_INFORMATION, "finalize", "insufficient evidence",
                  {"summary": diag.get("summary"), "clarifying_questions": questions,
                   "missing": state.get("missing_evidence", [])})
        elif route == "escalate":
            if case.status in (S.ASSESSING.value, S.COLLECTING_EVIDENCE.value):
                summary = diag.get("summary") or "; ".join(e["message"] for e in errors)
                _move(db, state, case, S.ESCALATED, "finalize",
                      "contradictory evidence or budget exhausted",
                      {"summary": summary, "evidence_snapshot_id": state.get("evidence_snapshot_id"),
                       "hypotheses": state.get("hypotheses", []), "errors": errors,
                       "escalate_to": "network_analyst"})
        elif route == "fail":
            if case.status in (S.NEW.value, S.TRIAGED.value, S.COLLECTING_EVIDENCE.value, S.ASSESSING.value):
                _move(db, state, case, S.FAILED, "finalize", "workflow error", {"errors": errors})
            else:
                _audit(db, state, "WORKFLOW_ERROR", case, node="finalize", detail={"errors": errors})
        return {"status": case.status}


def _route_after(node: str):
    def router(state: CaseWorkflowState) -> str:
        r = state.get("route", "ok")
        if r in ("fail", "escalate", "needs_info"):
            return "finalize"
        if node == "diagnosis":
            return {"more_evidence": "evidence", "plan": "planning"}.get(r, "finalize")
        if node == "planning":
            return "human_review" if r == "review" else END
        return {"triage": "evidence", "evidence": "diagnosis"}[node]

    return router


def build_graph():
    g = StateGraph(CaseWorkflowState)
    g.add_node("triage", triage_node)
    g.add_node("evidence", evidence_node)
    g.add_node("diagnosis", diagnosis_node)
    g.add_node("planning", planning_node)
    g.add_node("human_review", human_review_node)
    g.add_node("finalize", finalize_node)
    g.add_edge(START, "triage")
    g.add_conditional_edges("triage", _route_after("triage"), ["evidence", "finalize"])
    g.add_conditional_edges("evidence", _route_after("evidence"), ["diagnosis", "finalize"])
    g.add_conditional_edges("diagnosis", _route_after("diagnosis"), ["evidence", "planning", "finalize"])
    g.add_conditional_edges("planning", _route_after("planning"), ["human_review", "finalize", END])
    g.add_edge("human_review", END)
    g.add_edge("finalize", END)
    return g.compile(checkpointer=get_checkpointer())


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def reset_graph() -> None:
    global _graph
    _graph = None


def initial_state(case: Case, actor_id: str, actor_role: str, trace_id: str) -> dict[str, Any]:
    return {"case_id": case.id, "tenant_id": case.tenant_id, "actor_id": actor_id,
            "actor_role": actor_role, "status": case.status, "started_at": time.time(),
            "symptoms": {}, "evidence_refs": [], "evidence_snapshot_id": None, "missing_evidence": [],
            "requested_evidence": [], "hypotheses": [], "diagnosis": None, "proposed_action": None,
            "policy_decision": None, "recommendation_id": None, "approval_id": None,
            "execution_id": None, "recovery_result": None, "iteration_count": 0, "usage": {},
            "errors": [], "trace_id": trace_id, "route": "ok"}
