"""Workflow services: investigation jobs, approvals, execution, recovery
verification, clarifications and cancellation.

All consequential steps re-check authorization and policy at the moment
they happen, and every state change is a compare-and-set transition
committed together with its audit event.
"""
from __future__ import annotations

import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from langgraph.types import Command
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..agents.providers import get_provider
from ..auth.session import Principal
from ..config import get_settings
from ..connectors import synthetic as conn
from ..connectors.base import OutcomeUnknown
from ..db import session_scope, utcnow
from ..models.orm import (
    ActionExecution, Approval, Case, CaseMessage, DiagnosticSample, Incident, Recommendation,
    RecoveryObservation,
)
from ..observability import audit
from ..policies import engine
from ..policies.catalog import load_catalog
from ..policies.state_machine import CaseStatus as S
from ..policies.state_machine import ConcurrentModification, IllegalTransition, transition
from . import graph as wf

log = logging.getLogger("telecomresolve.workflow")
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="investigation")
_exec_lock = threading.Lock()

INVESTIGABLE = {S.NEW, S.FAILED, S.REJECTED, S.ESCALATED, S.RECOMMENDATION_READY, S.MONITORING, S.RESOLVED}


class WorkflowError(Exception):
    def __init__(self, status: int, code: str, message: str, extra: dict | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra or {}


def _ev(db: Session, principal: Principal, event_type: str, case: Case | None, **kw):
    p = get_provider()
    return audit.record(db, tenant_id=principal.tenant_id, actor_id=principal.user_id,
                        actor_role=principal.role, event_type=event_type,
                        case_id=case.id if case else None, generation_mode=p.mode,
                        connector_mode=get_settings().connector_mode,
                        policy_version=load_catalog().version, **kw)


def _move(db, principal, case, target: S, reason: str, detail: dict | None = None, trace_id=None):
    try:
        prev = transition(db, case, target, reason)
    except IllegalTransition as exc:
        raise WorkflowError(409, "ILLEGAL_TRANSITION", str(exc)) from exc
    except ConcurrentModification as exc:
        raise WorkflowError(409, "CONCURRENT_MODIFICATION",
                            "The case changed while you were acting on it; reload and retry.") from exc
    _ev(db, principal, "STATE_TRANSITION", case, from_status=prev, to_status=target.value,
        trace_id=trace_id, detail={"reason": reason, **(detail or {})})


# ------------------------------------------------------------ investigation
def start_investigation(db: Session, principal: Principal, case: Case, *, wait: bool,
                        after_clarification: bool = False) -> dict:
    allowed = INVESTIGABLE | ({S.TRIAGED} if after_clarification else set())
    if S(case.status) not in allowed:
        raise WorkflowError(409, "INVALID_STATE",
                            f"Cannot start an investigation while the case is {case.status}")
    job_id = f"JOB-{uuid.uuid4().hex[:10]}"
    # Claim the case atomically so two investigators cannot run concurrently.
    claimed = db.execute(update(Case).where(Case.id == case.id, Case.active_job.is_(None),
                                            Case.version == case.version)
                         .values(active_job=job_id, workflow_thread_id=f"{case.id}:{job_id}")
                         .execution_options(synchronize_session=False))
    if claimed.rowcount != 1:
        db.rollback()
        raise WorkflowError(409, "INVESTIGATION_IN_PROGRESS",
                            "Another investigation or update is in progress for this case")
    trace_id = f"trace-{uuid.uuid4().hex[:12]}"
    _ev(db, principal, "INVESTIGATION_STARTED", case, trace_id=trace_id,
        detail={"job_id": job_id, "provider": get_provider().describe()})
    db.commit()
    state = wf.initial_state(case, principal.user_id, principal.role, trace_id)
    thread_id = f"{case.id}:{job_id}"
    if wait:
        _run_job(case.id, thread_id, state)
    else:
        _executor.submit(_run_job, case.id, thread_id, state)
    return {"job_id": job_id, "trace_id": trace_id, "thread_id": thread_id, "mode": "sync" if wait else "async"}


def _run_job(case_id: str, thread_id: str, state: dict | None) -> None:
    cfg = {"configurable": {"thread_id": thread_id}}
    try:
        wf.get_graph().invoke(state, cfg)
    except Exception:  # noqa: BLE001 - recorded below; job remains claimable for recovery
        log.exception("investigation %s crashed", thread_id)
        with session_scope() as db:
            case = db.get(Case, case_id)
            audit.record(db, tenant_id=case.tenant_id, actor_id="system", actor_role="system",
                         event_type="WORKFLOW_INTERRUPTED", case_id=case_id,
                         detail={"thread_id": thread_id,
                                 "message": "Worker stopped unexpectedly; resumable from last checkpoint"})
        return
    with session_scope() as db:
        db.execute(update(Case).where(Case.id == case_id).values(active_job=None))


def recover_incomplete_jobs() -> list[str]:
    """Resume investigations whose worker stopped (e.g. process restart).
    Waits for human review are not jobs: they resume only on a decision."""
    resumed = []
    with session_scope() as db:
        rows = db.scalars(select(Case).where(Case.active_job.is_not(None))).all()
        pending = [(c.id, c.workflow_thread_id) for c in rows]
    graph = wf.get_graph()
    for case_id, thread_id in pending:
        cfg = {"configurable": {"thread_id": thread_id}}
        snapshot = graph.get_state(cfg)
        if snapshot.next == ("human_review",) or (snapshot.tasks and snapshot.tasks[0].interrupts):
            with session_scope() as db:
                db.execute(update(Case).where(Case.id == case_id).values(active_job=None))
            continue
        if not snapshot.next:
            with session_scope() as db:
                db.execute(update(Case).where(Case.id == case_id).values(active_job=None))
            continue
        _run_job(case_id, thread_id, None)  # None = resume from checkpoint
        resumed.append(case_id)
    return resumed


def _resume_review(case: Case, decision: dict) -> None:
    if not case.workflow_thread_id:
        return
    cfg = {"configurable": {"thread_id": case.workflow_thread_id}}
    graph = wf.get_graph()
    snap = graph.get_state(cfg)
    if snap.next == ("human_review",):
        graph.invoke(Command(resume=decision), cfg)


# ------------------------------------------------------------ approvals
def _current_recommendation(db, case: Case) -> Recommendation:
    rec = db.get(Recommendation, case.current_recommendation_id) if case.current_recommendation_id else None
    if rec is None or rec.status != "active":
        raise WorkflowError(409, "NO_ACTIVE_RECOMMENDATION", "The case has no active recommendation")
    return rec


def request_new_approval(db, principal: Principal, case: Case, recommendation_id: str) -> Approval:
    rec = _current_recommendation(db, case)
    if rec.id != recommendation_id:
        raise WorkflowError(409, "STALE_RECOMMENDATION", "Recommendation is no longer current")
    if case.status != S.RECOMMENDATION_READY.value:
        raise WorkflowError(409, "INVALID_STATE", f"Approval can be requested only from RECOMMENDATION_READY "
                                                  f"(case is {case.status})")
    decision = engine.evaluate(rec.action_type, set(rec.policy_decision.get("facts", [])))
    if not decision.allowed:
        raise WorkflowError(409, "POLICY_BLOCKED", "; ".join(decision.reasons))
    db.execute(update(Approval).where(Approval.case_id == case.id, Approval.status == "pending")
               .values(status="superseded"))
    appr = wf.request_approval(db, case, rec, requested_by=principal.user_id,
                               ttl=get_settings().approval_ttl_minutes)
    _move(db, principal, case, S.AWAITING_APPROVAL, "approval record created", {"approval_id": appr.id})
    return appr


def decide_approval(db: Session, principal: Principal, case: Case, *, approval_id: str, decision: str,
                    payload_hash: str, reason: str) -> Approval:
    appr = db.scalar(select(Approval).where(Approval.id == approval_id, Approval.case_id == case.id,
                                            Approval.tenant_id == principal.tenant_id))
    if appr is None:
        raise WorkflowError(404, "APPROVAL_NOT_FOUND", "Approval not found for this case")
    if appr.status != "pending":
        _ev(db, principal, "APPROVAL_REPLAY_REJECTED", case, detail={"approval_id": appr.id, "status": appr.status})
        db.commit()
        raise WorkflowError(409, "APPROVAL_NOT_PENDING",
                            f"Approval is {appr.status}; duplicate or replayed decisions are rejected")
    now = utcnow()
    if appr.expires_at and now > appr.expires_at:
        appr.status = "expired"
        _ev(db, principal, "APPROVAL_EXPIRED", case, detail={"approval_id": appr.id})
        if case.status == S.AWAITING_APPROVAL.value:
            _move(db, principal, case, S.RECOMMENDATION_READY, "approval expired or superseded")
        db.commit()
        raise WorkflowError(409, "APPROVAL_EXPIRED", "Approval expired; request a new review")
    rec = _current_recommendation(db, case)
    if rec.id != appr.recommendation_id or rec.payload_hash != appr.payload_hash:
        raise WorkflowError(409, "PAYLOAD_CHANGED", "The recommendation changed; a new review is required")
    if payload_hash != appr.payload_hash:
        raise WorkflowError(409, "PAYLOAD_MISMATCH",
                            "The payload you reviewed differs from the bound payload; reload and review again")
    if appr.policy_version != load_catalog().version or appr.evidence_snapshot_id != rec.snapshot_id:
        raise WorkflowError(409, "STALE_APPROVAL", "Policy version or evidence snapshot changed")
    policy = engine.PolicyDecision(**{k: v for k, v in rec.policy_decision.items() if k != "facts"})
    ok, why = engine.can_approve(principal.role, principal.user_id, rec.proposed_by, policy)
    if not ok:
        _ev(db, principal, "APPROVAL_DENIED", case, detail={"approval_id": appr.id, "reason": why})
        db.commit()
        raise WorkflowError(403, "APPROVER_NOT_AUTHORIZED", why)
    if decision not in ("approve", "reject"):
        raise WorkflowError(422, "INVALID_DECISION", "decision must be approve or reject")
    if decision == "reject" and not reason.strip():
        raise WorkflowError(422, "REASON_REQUIRED", "A reason is required to reject")
    # Compare-and-set on the approval row prevents double decisions.
    res = db.execute(update(Approval).where(Approval.id == appr.id, Approval.status == "pending")
                     .values(status="approved" if decision == "approve" else "rejected",
                             decided_by=principal.user_id, decided_at=now, decision_reason=reason)
                     .execution_options(synchronize_session=False))
    if res.rowcount != 1:
        raise WorkflowError(409, "APPROVAL_NOT_PENDING", "Approval was decided concurrently")
    db.refresh(appr)
    _ev(db, principal, "APPROVAL_DECIDED", case,
        detail={"approval_id": appr.id, "decision": decision, "reason": reason,
                "payload_hash": appr.payload_hash, "evidence_snapshot_id": appr.evidence_snapshot_id})
    _move(db, principal, case, S.APPROVED if decision == "approve" else S.REJECTED,
          "authorised approval recorded" if decision == "approve" else "approver rejected",
          {"approval_id": appr.id})
    db.commit()
    _resume_review(case, {"approval_id": appr.id, "decision": decision, "by": principal.user_id})
    return appr


# ------------------------------------------------------------ execution
_WRITERS = {
    "create_technician_dispatch": conn.dispatch_system,
    "suggest_customer_troubleshooting": conn.message_preview,
    "draft_customer_update": conn.message_preview,
    "associate_case_with_incident": conn.incident_link_system,
}


def execute(db: Session, principal: Principal, case: Case, *, approval_id: str,
            idempotency_key: str) -> tuple[ActionExecution, bool]:
    """Returns (execution, replayed)."""
    if not idempotency_key or len(idempotency_key) > 128:
        raise WorkflowError(422, "IDEMPOTENCY_KEY_REQUIRED", "Idempotency-Key header is required")
    existing = db.scalar(select(ActionExecution).where(ActionExecution.case_id == case.id,
                                                       ActionExecution.idempotency_key == idempotency_key))
    if existing is not None:
        if existing.approval_id != approval_id:
            raise WorkflowError(409, "IDEMPOTENCY_KEY_REUSED", "Key already used for a different approval")
        if existing.status == "unknown":
            return _reconcile_and_finish(db, principal, case, existing), False
        _ev(db, principal, "EXECUTION_REPLAYED", case, detail={"execution_id": existing.id,
                                                              "idempotency_key": idempotency_key})
        db.commit()
        return existing, True

    with _exec_lock:  # serialises the claim step within this process; DB CAS covers others
        appr = db.scalar(select(Approval).where(Approval.id == approval_id, Approval.case_id == case.id,
                                                Approval.tenant_id == principal.tenant_id))
        if appr is None:
            raise WorkflowError(404, "APPROVAL_NOT_FOUND", "Approval not found for this case")
        if appr.status == "consumed":
            _ev(db, principal, "EXECUTION_DUPLICATE_REJECTED", case,
                detail={"approval_id": appr.id, "idempotency_key": idempotency_key})
            db.commit()
            raise WorkflowError(409, "APPROVAL_ALREADY_USED",
                                "This approval was already used; duplicate execution prevented")
        if appr.status != "approved":
            raise WorkflowError(409, "NOT_APPROVED", f"Approval is {appr.status}")
        if appr.expires_at and utcnow() > appr.expires_at:
            appr.status = "expired"
            _move(db, principal, case, S.RECOMMENDATION_READY, "approval expired or invalidated")
            db.commit()
            raise WorkflowError(409, "APPROVAL_EXPIRED", "Approval expired before execution; review again")
        rec = _current_recommendation(db, case)
        if rec.id != appr.recommendation_id or rec.payload_hash != appr.payload_hash:
            raise WorkflowError(409, "PAYLOAD_CHANGED", "Payload changed since approval")
        if engine.payload_hash(rec.payload) != appr.payload_hash:
            raise WorkflowError(409, "PAYLOAD_TAMPERED", "Stored payload no longer matches its approved hash")
        # Re-validate policy and the executor's authorization now.
        decision = engine.evaluate(rec.action_type, set(rec.policy_decision.get("facts", [])))
        if decision.policy_version != appr.policy_version:
            raise WorkflowError(409, "STALE_APPROVAL", "Policy version changed since approval")
        ok, why = engine.can_execute(principal.role, decision)
        if not ok:
            _ev(db, principal, "EXECUTION_DENIED", case, detail={"approval_id": appr.id, "reason": why})
            db.commit()
            raise WorkflowError(403, "EXECUTOR_NOT_AUTHORIZED", why)
        if case.status != S.APPROVED.value:
            raise WorkflowError(409, "INVALID_STATE", f"Case is {case.status}, not APPROVED")
        execution = ActionExecution(
            id=f"EXE-{uuid.uuid4().hex[:10]}", case_id=case.id, tenant_id=case.tenant_id,
            approval_id=appr.id, action_type=rec.action_type, payload_hash=rec.payload_hash,
            idempotency_key=idempotency_key, executed_by=principal.user_id,
            connector=_WRITERS[rec.action_type].system, connector_mode=get_settings().connector_mode,
            status="pending", attempts=0, started_at=utcnow())
        db.add(execution)
        appr.status = "consumed"
        appr.consumed_by_execution_id = execution.id
        try:
            _move(db, principal, case, S.EXECUTING, "approval and policy revalidated",
                  {"execution_id": execution.id, "idempotency_key": idempotency_key})
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise WorkflowError(409, "DUPLICATE_EXECUTION", "Execution already recorded for this approval") from exc
        except WorkflowError:
            db.rollback()
            raise
    return _attempt(db, principal, case, execution, rec), False


def _attempt(db, principal, case, execution: ActionExecution, rec: Recommendation) -> ActionExecution:
    writer = _WRITERS[rec.action_type]
    execution.attempts += 1
    try:
        record = writer.create(db, case, rec.payload, execution.idempotency_key,
                               fault_consumed=execution.attempts > 1)
    except OutcomeUnknown as exc:
        execution.status = "unknown"
        execution.result = {"error": exc.code, "message": str(exc)}
        _ev(db, principal, "EXECUTION_OUTCOME_UNKNOWN", case,
            detail={"execution_id": execution.id, "message": str(exc),
                    "next_step": "retry with the same Idempotency-Key to reconcile"})
        db.commit()
        return execution
    return _finish(db, principal, case, execution, rec, record)


def _finish(db, principal, case, execution, rec, record) -> ActionExecution:
    execution.status = "succeeded"
    execution.external_ref = record.id
    execution.completed_at = utcnow()
    execution.result = {"external_ref": record.id, "system": record.system, "simulated": True,
                        "note": "Simulated connector. Success means the record was created, "
                                "not that service is restored."}
    if rec.action_type == "associate_case_with_incident":
        case.linked_incident_id = rec.payload["incident_id"]
    _ev(db, principal, "ACTION_EXECUTED", case,
        detail={"execution_id": execution.id, "action_type": rec.action_type, "external_ref": record.id,
                "payload_hash": rec.payload_hash, "approval_id": execution.approval_id,
                "idempotency_key": execution.idempotency_key, "attempts": execution.attempts})
    _move(db, principal, case, S.VERIFYING, "execution succeeded or reconciled",
          {"execution_id": execution.id})
    db.commit()
    return execution


def _reconcile_and_finish(db, principal, case, execution: ActionExecution) -> ActionExecution:
    """After a lost response, check the external system before retrying."""
    rec = db.get(Recommendation, db.get(Approval, execution.approval_id).recommendation_id)
    writer = _WRITERS[rec.action_type]
    found = writer.find(db, execution.idempotency_key)
    _ev(db, principal, "EXECUTION_RECONCILED", case,
        detail={"execution_id": execution.id, "found_existing": found is not None})
    if found is not None:
        return _finish(db, principal, case, execution, rec, found)
    return _attempt(db, principal, case, execution, rec)


# ------------------------------------------------------------ verification
def verify(db: Session, principal: Principal, case: Case, *, customer_report: str | None) -> RecoveryObservation:
    s = get_settings()
    if case.status == S.MONITORING.value:
        _move(db, principal, case, S.VERIFYING, "re-verification")
    if case.status != S.VERIFYING.value:
        raise WorkflowError(409, "INVALID_STATE", f"Case is {case.status}; nothing to verify")
    execution = db.scalar(select(ActionExecution).where(ActionExecution.case_id == case.id,
                                                        ActionExecution.status == "succeeded")
                          .order_by(ActionExecution.completed_at.desc()).limit(1))
    if execution is None:
        raise WorkflowError(409, "NO_EXECUTION", "No successful execution to verify")
    start = execution.completed_at
    end = start + timedelta(minutes=s.recovery_window_minutes)
    # SIMULATION: fast-forwards telemetry for the observation window.
    conn.diagnostics.simulate_post_action(db, case, execution.id, start, s.recovery_window_minutes)
    samples = list(db.scalars(select(DiagnosticSample).where(
        DiagnosticSample.service_id == case.service_id, DiagnosticSample.tenant_id == case.tenant_id,
        DiagnosticSample.collected_at > start, DiagnosticSample.collected_at <= end)
        .order_by(DiagnosticSample.collected_at)))
    from ..agents.evidence import is_healthy

    healthy = [x for x in samples if is_healthy(x)]
    unhealthy = [x for x in samples if not is_healthy(x)]
    reasons: list[str] = []
    conflict = bool(customer_report and customer_report.strip())
    linked_active = False
    if case.linked_incident_id:
        inc = db.get(Incident, case.linked_incident_id)
        linked_active = inc is not None and inc.status == "active"
    span_ok = bool(samples) and (samples[-1].collected_at - samples[0].collected_at) >= \
        timedelta(minutes=s.recovery_window_minutes * 0.6)
    if linked_active:
        outcome = S.MONITORING
        reasons.append(f"Linked incident {case.linked_incident_id} is still active; recovery depends on "
                       "incident restoration.")
    elif len(unhealthy) >= 2:
        outcome = S.ESCALATED
        reasons.append(f"{len(unhealthy)} of {len(samples)} post-action samples are unhealthy: recovery failed.")
    elif conflict:
        outcome = S.MONITORING
        reasons.append("Customer follow-up report conflicts with telemetry; case kept open for investigation.")
    elif len(healthy) >= s.recovery_min_samples and not unhealthy and span_ok:
        outcome = S.RESOLVED
        reasons.append(f"{len(healthy)} healthy samples across the {s.recovery_window_minutes}-minute window "
                       f"(minimum {s.recovery_min_samples}).")
    else:
        outcome = S.MONITORING
        reasons.append(f"Recovery not yet verified: {len(healthy)} healthy of {s.recovery_min_samples} required "
                       f"samples in the window; missing samples are not treated as healthy.")
    obs = RecoveryObservation(
        id=f"REC-OBS-{uuid.uuid4().hex[:8]}", case_id=case.id, execution_id=execution.id,
        checked_by=principal.user_id, checked_at=utcnow(), window_start=start, window_end=end,
        sample_ids=[x.id for x in samples], healthy_samples=len(healthy), unhealthy_samples=len(unhealthy),
        required_samples=s.recovery_min_samples, customer_report_conflict=conflict, outcome=outcome.value,
        reasons=reasons, simulation_time=True)
    db.add(obs)
    _ev(db, principal, "RECOVERY_CHECKED", case,
        detail={"observation_id": obs.id, "outcome": outcome.value, "reasons": reasons,
                "sample_ids": obs.sample_ids, "simulation_time_fast_forwarded": True,
                "customer_report": customer_report})
    _move(db, principal, case, outcome, {S.RESOLVED: "fresh healthy samples across window",
                                          S.MONITORING: "recovery not yet verified",
                                          S.ESCALATED: "recovery failed"}[outcome],
          {"observation_id": obs.id})
    db.commit()
    return obs


# ------------------------------------------------------------ other actions
def add_clarification(db, principal, case: Case, text: str) -> CaseMessage:
    if case.status != S.NEEDS_INFORMATION.value:
        raise WorkflowError(409, "INVALID_STATE", "Clarifications are accepted only in NEEDS_INFORMATION")
    msg = CaseMessage(id=f"MSG-{uuid.uuid4().hex[:10]}", case_id=case.id, tenant_id=case.tenant_id,
                      author_id=principal.user_id, role="user", kind="clarification", text=text[:2000],
                      citations=[], generation_mode="n/a", created_at=utcnow())
    db.add(msg)
    symptoms = dict(case.reported_symptoms or {})
    symptoms["clarifications"] = [*symptoms.get("clarifications", []),
                                  {"text": text[:2000], "by": principal.user_id, "at": utcnow().isoformat(),
                                   "kind": "customer_statement"}]
    case.reported_symptoms = symptoms
    _ev(db, principal, "CLARIFICATION_ADDED", case, detail={"message_id": msg.id})
    _move(db, principal, case, S.TRIAGED, "clarification received")
    db.commit()
    return msg


def cancel(db, principal, case: Case, reason: str) -> None:
    if case.active_job:
        raise WorkflowError(409, "INVESTIGATION_IN_PROGRESS", "Wait for the running investigation to finish")
    db.execute(update(Approval).where(Approval.case_id == case.id, Approval.status.in_(["pending", "approved"]))
               .values(status="superseded"))
    _move(db, principal, case, S.CANCELLED, "cancel request", {"reason": reason})
    db.commit()


def select_alternative(db, principal, case: Case, action_type: str) -> Recommendation:
    from ..agents import planning as planning_agent
    from ..agents.contracts import DiagnosisOutput, TriageOutput

    if case.status != S.RECOMMENDATION_READY.value and case.status != S.AWAITING_APPROVAL.value:
        raise WorkflowError(409, "INVALID_STATE", "Alternatives can be selected only before approval")
    rec = _current_recommendation(db, case)
    bundle = wf.load_bundle(db, rec.snapshot_id)
    diag_event = db.scalar(select(audit.AuditEvent).where(audit.AuditEvent.case_id == case.id,
                                                          audit.AuditEvent.event_type == "DIAGNOSIS_COMPLETED")
                           .order_by(audit.AuditEvent.id.desc()).limit(1))
    from ..models.orm import Hypothesis

    hyps = db.scalars(select(Hypothesis).where(Hypothesis.snapshot_id == rec.snapshot_id)
                      .order_by(Hypothesis.rank)).all()
    diag = DiagnosisOutput(
        hypotheses=[{"category": h.category, "statement": h.statement, "supporting_refs": h.supporting_refs,
                     "opposing_refs": h.opposing_refs, "sufficiency": h.sufficiency} for h in hyps],
        conclusion=diag_event.detail["conclusion"], observations=[], needs_more_evidence=[], escalate=False,
        summary=diag_event.detail.get("summary", ""))
    triage = TriageOutput(**{k: v for k, v in case.reported_symptoms.items() if k != "clarifications"})
    draft, decision, facts = planning_agent.build_for_action(action_type, case.id, case.service_id, triage,
                                                             bundle, diag)
    if draft is None:
        reasons = decision.reasons if decision else ["not a candidate for this diagnosis"]
        raise WorkflowError(409, "POLICY_BLOCKED", "; ".join(reasons))
    if case.status == S.AWAITING_APPROVAL.value:
        _move(db, principal, case, S.RECOMMENDATION_READY, "approval expired or superseded",
              {"superseded_by_alternative": action_type})
    new = wf.create_recommendation(db, case, rec.snapshot_id, draft, decision, facts,
                                   proposed_by=principal.user_id, generation_mode="DEMO")
    _ev(db, principal, "RECOMMENDATION_ALTERNATIVE_SELECTED", case,
        detail={"from": rec.id, "to": new.id, "action_type": action_type})
    request_new_approval(db, principal, case, new.id)
    db.commit()
    return new
