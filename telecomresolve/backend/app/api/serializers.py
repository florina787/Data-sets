"""Response shaping with field minimisation by role."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.permissions import Perm
from ..auth.session import Principal
from ..models.orm import (
    Account, ActionExecution, Approval, AuditEvent, Case, Customer, Equipment, Recommendation,
    RecoveryObservation, Service, ServiceAssetMapping, SupportInteraction,
)


def iso(dt):
    return dt.isoformat() if dt else None


def case_summary(c: Case) -> dict:
    return {"id": c.id, "title": c.title, "status": c.status, "status_reason": c.status_reason,
            "account_id": c.account_id, "service_id": c.service_id, "created_at": iso(c.created_at),
            "updated_at": iso(c.updated_at), "version": c.version, "linked_incident_id": c.linked_incident_id,
            "investigation_running": c.active_job is not None}


def recommendation(r: Recommendation | None) -> dict | None:
    if r is None:
        return None
    return {"id": r.id, "status": r.status, "action_type": r.action_type, "payload": r.payload,
            "payload_hash": r.payload_hash, "purpose": r.purpose, "prerequisites": r.prerequisites,
            "evidence_refs": r.evidence_refs, "uncertainty": r.uncertainty, "risk": r.risk,
            "approval_requirement": r.approval_requirement, "policy_version": r.policy_version,
            "policy_decision": r.policy_decision, "prior_interventions": r.prior_interventions,
            "refused_requests": r.refused_requests, "alternatives": r.alternatives,
            "proposed_by": r.proposed_by, "generation_mode": r.generation_mode,
            "snapshot_id": r.snapshot_id, "created_at": iso(r.created_at)}


def approval(a: Approval | None) -> dict | None:
    if a is None:
        return None
    return {"id": a.id, "case_id": a.case_id, "recommendation_id": a.recommendation_id,
            "action_type": a.action_type, "payload_hash": a.payload_hash, "policy_version": a.policy_version,
            "evidence_snapshot_id": a.evidence_snapshot_id, "requested_by": a.requested_by,
            "requested_at": iso(a.requested_at), "required_roles": a.required_roles,
            "separation_of_duties": a.separation_of_duties, "status": a.status, "decided_by": a.decided_by,
            "decided_at": iso(a.decided_at), "decision_reason": a.decision_reason,
            "expires_at": iso(a.expires_at), "consumed_by_execution_id": a.consumed_by_execution_id}


def execution(e: ActionExecution | None) -> dict | None:
    if e is None:
        return None
    return {"id": e.id, "approval_id": e.approval_id, "action_type": e.action_type, "status": e.status,
            "connector": e.connector, "connector_mode": e.connector_mode, "external_ref": e.external_ref,
            "result": e.result, "attempts": e.attempts, "executed_by": e.executed_by,
            "idempotency_key": e.idempotency_key, "started_at": iso(e.started_at),
            "completed_at": iso(e.completed_at)}


def recovery(o: RecoveryObservation | None) -> dict | None:
    if o is None:
        return None
    return {"id": o.id, "execution_id": o.execution_id, "outcome": o.outcome, "reasons": o.reasons,
            "healthy_samples": o.healthy_samples, "unhealthy_samples": o.unhealthy_samples,
            "required_samples": o.required_samples, "sample_ids": o.sample_ids,
            "window_start": iso(o.window_start), "window_end": iso(o.window_end),
            "customer_report_conflict": o.customer_report_conflict, "simulation_time": o.simulation_time,
            "checked_by": o.checked_by, "checked_at": iso(o.checked_at)}


def audit_event(e: AuditEvent) -> dict:
    return {"seq": e.id, "event_id": e.event_id, "case_id": e.case_id, "trace_id": e.trace_id,
            "request_id": e.request_id, "occurred_at": iso(e.occurred_at), "actor_id": e.actor_id,
            "actor_role": e.actor_role, "event_type": e.event_type, "node": e.node,
            "from_status": e.from_status, "to_status": e.to_status, "generation_mode": e.generation_mode,
            "connector_mode": e.connector_mode, "policy_version": e.policy_version,
            "latency_ms": e.latency_ms, "usage": e.usage, "detail": e.detail,
            "prev_hash": e.prev_hash, "event_hash": e.event_hash}


def case_detail(db: Session, principal: Principal, c: Case) -> dict:
    account = db.get(Account, c.account_id)
    customer = db.get(Customer, account.customer_id)
    service = db.get(Service, c.service_id)
    mapping = db.scalar(select(ServiceAssetMapping).where(ServiceAssetMapping.service_id == c.service_id))
    equipment = db.scalar(select(Equipment).where(Equipment.service_id == c.service_id))
    history = db.scalars(select(SupportInteraction).where(SupportInteraction.account_id == c.account_id)
                         .order_by(SupportInteraction.occurred_at)).all()
    rec = db.get(Recommendation, c.current_recommendation_id) if c.current_recommendation_id else None
    appr = db.scalar(select(Approval).where(Approval.case_id == c.id).order_by(Approval.requested_at.desc()).limit(1))
    exe = db.scalar(select(ActionExecution).where(ActionExecution.case_id == c.id)
                    .order_by(ActionExecution.started_at.desc()).limit(1))
    obs = db.scalar(select(RecoveryObservation).where(RecoveryObservation.case_id == c.id)
                    .order_by(RecoveryObservation.checked_at.desc()).limit(1))
    show_contact = principal.can(Perm.CUSTOMER_CONTACT_READ)
    from ..agents.evidence import detect_injection, quarantine

    return {
        **case_summary(c),
        "complaint_text": c.complaint_text,
        "reported_symptoms": c.reported_symptoms,
        "customer": {"id": customer.id, "display_name": customer.display_name,
                     "contact_phone": customer.contact_phone if show_contact else "[restricted]",
                     "contact_email": customer.contact_email if show_contact else "[restricted]"},
        "account": {"id": account.id, "segment": account.segment, "status": account.status,
                    "service_address": account.service_address, "postal_area": account.postal_area},
        "service": {"id": service.id, "product": service.product, "plan": service.plan,
                    "access_technology": service.access_technology, "status": service.status},
        "mapping": {"id": mapping.id, "asset_id": mapping.asset_id, "port": mapping.port} if mapping else None,
        "equipment": {"id": equipment.id, "model": equipment.model, "firmware": equipment.firmware}
        if equipment else None,
        "support_history": [{"id": h.id, "channel": h.channel, "occurred_at": iso(h.occurred_at),
                             "summary": h.summary, "notes": quarantine(h.notes),
                             "untrusted_content_flag": bool(detect_injection(h.notes)),
                             "actions_taken": h.actions_taken, "outcome": h.outcome,
                             "author_type": h.author_type} for h in history],
        "recommendation": recommendation(rec),
        "approval": approval(appr),
        "execution": execution(exe),
        "recovery": recovery(obs),
    }
