"""Durable human-in-the-loop approvals.

Lifecycle: pending -> approved | rejected | expired | invalidated ; approved -> executed (exactly once).
Controls (policies/approvals.yaml):
* the requester must be authorized for the action at request time AND again at execution time (fresh attributes);
* the approver must hold `approvals:decide`, an approver role for the action type, be in the same tenant and must not
  be the requester;
* the approver confirms the payload hash they reviewed; execution recomputes the hash of the payload presented —
  any difference invalidates the approval;
* approvals expire; executed approvals cannot be replayed.
Executors only write to mock outboxes: nothing is sent externally and no securities are traded.
"""
from __future__ import annotations

import csv
import hashlib
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db import models as m
from governance import audit
from governance.identity import Principal
from governance.policy import PolicyEngine, Resource, canonical_json


class ApprovalError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def payload_hash(payload: dict) -> str:
    return hashlib.sha256(canonical_json(payload).encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_dict(a: m.Approval) -> dict:
    return {"id": a.id, "action_type": a.action_type, "requested_by": a.requested_by, "payload": a.payload, "payload_hash": a.payload_hash,
            "evidence": a.evidence, "risk_class": a.risk_class, "approver_role": a.approver_role, "resource_ref": a.resource_ref,
            "created_at": a.created_at.isoformat(), "expires_at": a.expires_at.isoformat(), "status": effective_status(a),
            "decided_by": a.decided_by, "decided_at": a.decided_at.isoformat() if a.decided_at else None, "decision_note": a.decision_note,
            "executed_at": a.executed_at.isoformat() if a.executed_at else None, "execution_result": a.execution_result,
            "policy_version": a.policy_version, "tenant_id": a.tenant_id}


def effective_status(a: m.Approval) -> str:
    if a.status in ("pending", "approved") and a.expires_at < _now():
        return "expired"
    return a.status


class ApprovalService:
    def __init__(self, engine: PolicyEngine, resolve_resource: Callable[[str, str], Resource | None]):
        self.engine = engine
        self.resolve = resolve_resource  # (tenant_id, resource_ref) -> fresh Resource
        self.executors: dict[str, Callable[[Session, m.Approval, Principal], dict]] = {
            "comms:send": _exec_outbox("email (mock CRM outbox - not delivered)"),
            "recommendation:deliver": _exec_outbox("client recommendation (mock CRM outbox - not delivered)"),
            "board:distribute": _exec_outbox("board portal (mock - not distributed)"),
            "records:change": _exec_outbox("ERP adjustment request (mock ERP - not posted)"),
            "portfolio:modify": _exec_outbox("rebalance instruction (simulated; trading is prohibited, nothing transmitted)"),
            "export:sensitive": _exec_export,
        }

    # ------------------------------------------------------------------ request
    def request(self, s: Session, principal: Principal, action: str, resource_ref: str, payload: dict, evidence: list,
                thread_id: str | None = None, context: dict | None = None) -> m.Approval:
        spec = self.engine.approval_spec(action)
        if spec is None:
            raise ApprovalError("NOT_APPROVABLE", f"{action} is not an approval-gated action")
        res = self.resolve(principal.tenant_id, resource_ref)
        d = self.engine.authorize(principal, action, res, context)
        if not d.allowed:
            audit.record(tenant_id=principal.tenant_id, actor=principal.user_id, action=f"approval.request:{action}", resource_type="approval",
                         resource_id=resource_ref, decision="deny", reasons=d.reasons, policy_version=d.policy_version)
            raise ApprovalError("REQUEST_NOT_AUTHORIZED", f"requester not authorized: {d.denial_codes}")
        a = m.Approval(id=f"APR-{uuid.uuid4().hex[:12]}", tenant_id=principal.tenant_id, action_type=action, requested_by=principal.user_id,
                       payload=payload, payload_hash=payload_hash(payload), evidence=evidence, risk_class=spec["risk"],
                       approver_role=",".join(spec["approver_roles"]), resource_ref=resource_ref, created_at=_now(),
                       expires_at=_now() + timedelta(minutes=spec["expires_minutes"]), status="pending",
                       workflow_thread_id=thread_id, policy_version=self.engine.version)
        s.add(a)
        s.flush()
        audit.record(tenant_id=principal.tenant_id, actor=principal.user_id, action="approval.requested", resource_type="approval",
                     resource_id=a.id, decision="pending", policy_version=self.engine.version,
                     details={"action": action, "payload_hash": a.payload_hash, "resource": resource_ref, "risk": a.risk_class})
        return a

    def get(self, s: Session, principal: Principal, approval_id: str) -> m.Approval:
        a = s.get(m.Approval, approval_id)
        if a is None or a.tenant_id != principal.tenant_id:
            raise ApprovalError("NOT_FOUND", "approval not found")
        return a

    # ------------------------------------------------------------------ decide
    def decide(self, s: Session, approver: Principal, approval_id: str, approve: bool, reviewed_payload_hash: str,
               note: str = "") -> m.Approval:
        a = self.get(s, approver, approval_id)
        fail = None
        if effective_status(a) != "pending":
            fail = ("NOT_PENDING", f"approval is {effective_status(a)}")
        elif not self.engine.authorize(approver, "approvals:decide").allowed:
            fail = ("APPROVER_NOT_AUTHORIZED", "approver lacks approvals:decide")
        elif not set(approver.roles) & set(a.approver_role.split(",")):
            fail = ("APPROVER_ROLE_MISMATCH", f"requires one of {a.approver_role}")
        elif approver.user_id == a.requested_by:
            fail = ("SELF_APPROVAL", "requesters cannot approve their own actions")
        elif reviewed_payload_hash != a.payload_hash:
            fail = ("PAYLOAD_HASH_MISMATCH", "reviewed payload differs from the stored proposal")
        if fail:
            audit.record(tenant_id=approver.tenant_id, actor=approver.user_id, action="approval.decide", resource_type="approval",
                         resource_id=a.id, decision="deny", reasons=[{"rule": fail[0], "effect": "deny", "message": fail[1]}],
                         policy_version=self.engine.version)
            raise ApprovalError(*fail)
        a.status = "approved" if approve else "rejected"
        a.decided_by, a.decided_at, a.decision_note = approver.user_id, _now(), note
        audit.record(tenant_id=approver.tenant_id, actor=approver.user_id, action=f"approval.{a.status}", resource_type="approval",
                     resource_id=a.id, decision=a.status, policy_version=self.engine.version, details={"note": note, "payload_hash": a.payload_hash})
        return a

    # ------------------------------------------------------------------ execute
    def execute(self, s: Session, principal: Principal, approval_id: str, payload: dict) -> m.Approval:
        a = self.get(s, principal, approval_id)
        fail = None
        status = effective_status(a)
        if a.executed_at is not None or status == "executed":
            fail = ("REPLAY", "approval already executed (single use)")
        elif status == "expired":
            a.status = "expired"
            fail = ("EXPIRED", "approval expired")
        elif status != "approved":
            fail = ("NOT_APPROVED", f"approval is {status}")
        elif payload_hash(payload) != a.payload_hash:
            a.status = "invalidated"
            fail = ("PAYLOAD_CHANGED", "payload differs from the approved payload; approval invalidated")
        elif principal.user_id != a.requested_by:
            fail = ("NOT_REQUESTER", "only the requesting identity may execute the approved action")
        if fail is None:
            res = self.resolve(principal.tenant_id, a.resource_ref)
            d = self.engine.authorize(principal, a.action_type, res)
            if not d.allowed:
                fail = ("REVALIDATION_FAILED", f"authorization revoked since request: {d.denial_codes}")
        if fail:
            audit.record(tenant_id=principal.tenant_id, actor=principal.user_id, action="approval.execute", resource_type="approval",
                         resource_id=a.id, decision="deny", reasons=[{"rule": fail[0], "effect": "deny", "message": fail[1]}],
                         policy_version=self.engine.version)
            s.flush()
            raise ApprovalError(*fail)
        result = self.executors[a.action_type](s, a, principal)
        a.status, a.executed_at, a.execution_result = "executed", _now(), result
        audit.record(tenant_id=principal.tenant_id, actor=principal.user_id, action=f"approval.executed:{a.action_type}", resource_type="approval",
                     resource_id=a.id, decision="allow", policy_version=self.engine.version, details={"result": result})
        return a

    def pending_for(self, s: Session, principal: Principal) -> list[m.Approval]:
        q = select(m.Approval).where(m.Approval.tenant_id == principal.tenant_id).order_by(m.Approval.created_at.desc()).limit(200)
        rows = list(s.scalars(q))
        return [a for a in rows if set(principal.roles) & set(a.approver_role.split(",")) or a.requested_by == principal.user_id]


def _exec_outbox(channel: str):
    def run(s: Session, a: m.Approval, p: Principal) -> dict:
        ob = m.Outbox(id=f"OB-{uuid.uuid4().hex[:10]}", tenant_id=a.tenant_id, channel=channel, recipient_ref=a.resource_ref,
                      subject=str(a.payload.get("subject", a.action_type))[:200], body=str(a.payload.get("body", canonical_json(a.payload))),
                      approval_id=a.id, created_at=_now(), status="queued_mock")
        s.add(ob)
        return {"outbox_id": ob.id, "channel": channel, "delivered_externally": False}
    return run


def _exec_export(s: Session, a: m.Approval, p: Principal) -> dict:
    d = Path(get_settings().export_dir)
    d.mkdir(parents=True, exist_ok=True)
    rows = a.payload.get("rows", [])
    path = d / f"{a.id}.csv"
    with path.open("w", newline="") as fh:
        if rows:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    return {"file": path.name, "rows": len(rows), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "ttl_hours": 24, "watermark": f"SYNTHETIC export approved under {a.id}"}


def list_by_status(s: Session, tenant_id: str, status: str | None = None) -> list[m.Approval]:
    q = select(m.Approval).where(m.Approval.tenant_id == tenant_id)
    rows = list(s.scalars(q.order_by(m.Approval.created_at.desc())))
    return [a for a in rows if status is None or effective_status(a) == status]
