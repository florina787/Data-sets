"""Manager Approval Center: role checks, segregation of duties and non-bypassable policy blocks."""
from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models as M
from app.audit import audit

ROLES = {
    "SHERIN_MANAGER": "Sherin's manager (fictional). Approves agent actions, deployments and investment requests.",
    "RISK_OFFICER": "Independent risk sign-off for material investment actions.",
    "COMPLIANCE_OFFICER": "Compliance sign-off for sensitive data changes and ESG exceptions.",
    "PORTFOLIO_MANAGER": "Proposes trades. Cannot approve their own proposals.",
    "ENGINEER": "Requests deployments and code changes.",
    "VIEWER": "Read-only.",
}
DECISIONS = ("approve", "reject", "request_changes", "escalate")


class ApprovalError(Exception):
    status_code = 400


class Forbidden(ApprovalError):
    status_code = 403


class PolicyBlocked(ApprovalError):
    status_code = 409


class Conflict(ApprovalError):
    status_code = 409


def new_id(prefix: str = "AP") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def required_roles_for(kind: str, *, material: bool = False, sensitive: bool = False, esg_flag: bool = False) -> list[str]:
    roles = ["SHERIN_MANAGER"]
    if kind == "investment" and material:
        roles.append("RISK_OFFICER")
    if (kind == "data_change" and sensitive) or esg_flag:
        roles.append("COMPLIANCE_OFFICER")
    return roles


def create(db: Session, *, kind: str, title: str, summary: str, requested_by: str, required_roles: list[str], financial_impact_usd=0,
           risk_evidence: list | None = None, policy_blocked: bool = False, status: str | None = None, data_class: str = "measured", **related) -> M.Approval:
    a = M.Approval(id=new_id(), kind=kind, title=title, summary=summary, requested_by=requested_by, required_roles=required_roles,
                   financial_impact_usd=Decimal(str(financial_impact_usd)), risk_evidence=risk_evidence or [], policy_blocked=policy_blocked,
                   status=status or ("blocked" if policy_blocked else "pending"), decisions=[], data_class=data_class, **related)
    db.add(a)
    audit(db, requested_by, "AGENT" if requested_by.startswith("agent.") else "USER", "approval.requested", "approval", a.id, kind=kind,
          required_roles=required_roles, policy_blocked=policy_blocked)
    return a


def for_guardian(db: Session, proposal: M.TradeProposal, result: dict, requested_by: str) -> M.Approval:
    decision = result["decision"]
    esg_flag = any(c["id"] in ("esg_score", "sector_exclusion") and c["status"] != "PASS" for c in result["checks"])
    roles = required_roles_for("investment", material=result["material"], esg_flag=esg_flag)
    status = {"BLOCK": "blocked", "INSUFFICIENT_DATA": "insufficient_data"}.get(decision, "pending")
    evidence = [f"{c['name']}: {c['status']} - {c['detail']}" for c in result["checks"] if c["status"] != "PASS"] or ["All automated controls passed."]
    return create(db, kind="investment", title=f"{proposal.side} {proposal.issuer} ({proposal.portfolio_id}) - Guardian {decision}",
                  summary=f"{proposal.rationale} Guardian decision: {decision}. {result['meaning']}", requested_by=requested_by,
                  required_roles=roles, financial_impact_usd=proposal.notional_usd, risk_evidence=evidence,
                  policy_blocked=decision == "BLOCK", status=status, related_proposal_id=proposal.id, data_class=proposal.data_class)


def decide(db: Session, approval_id: str, *, actor: str, role: str, decision: str, comment: str = "") -> M.Approval:
    if decision not in DECISIONS:
        raise ApprovalError(f"decision must be one of {DECISIONS}")
    if role not in ROLES:
        raise Forbidden(f"unknown role {role}")
    a = db.get(M.Approval, approval_id, with_for_update=True)
    if a is None:
        raise KeyError(approval_id)
    if a.status in ("approved", "rejected"):
        raise Conflict(f"approval {a.id} is already {a.status}")
    if a.policy_blocked and decision == "approve":
        audit(db, actor, role, "approval.bypass_attempt", "approval", a.id, decision=decision)
        raise PolicyBlocked("A mandatory policy block cannot be overridden by any approval.")
    if a.status == "insufficient_data" and decision == "approve":
        raise PolicyBlocked("Required data is missing; the request must be re-evaluated before it can be approved.")
    if role not in a.required_roles and not (role == "SHERIN_MANAGER" and decision in ("reject", "request_changes", "escalate")):
        raise Forbidden(f"role {role} is not an approver for this request (requires {', '.join(a.required_roles)})")
    if actor == a.requested_by:
        raise Forbidden("Segregation of duties: requesters cannot decide on their own requests.")
    if decision == "approve" and any(d["actor"] == actor and d["decision"] == "approve" for d in a.decisions):
        raise Forbidden("Segregation of duties: one person cannot provide more than one approval on the same request.")
    if decision == "approve" and any(d["role"] == role and d["decision"] == "approve" for d in a.decisions):
        raise Conflict(f"{role} has already approved this request")

    entry = {"actor": actor, "role": role, "decision": decision, "comment": comment, "at": dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")}
    a.decisions = [*a.decisions, entry]
    if decision == "reject":
        a.status = "rejected"
    elif decision == "request_changes":
        a.status = "changes_requested"
    elif decision == "escalate":
        extra = "RISK_OFFICER" if a.kind == "investment" else "COMPLIANCE_OFFICER"
        if extra not in a.required_roles:
            a.required_roles = [*a.required_roles, extra]
        a.status = "escalated"
    else:
        approved_roles = {d["role"] for d in a.decisions if d["decision"] == "approve"}
        a.status = "approved" if set(a.required_roles) <= approved_roles else "partially_approved"
    audit(db, actor, role, f"approval.{decision}", "approval", a.id, status=a.status, comment=comment)
    return a


def to_dict(a: M.Approval) -> dict:
    approved_roles = {d["role"] for d in a.decisions if d["decision"] == "approve"}
    return {"id": a.id, "kind": a.kind, "title": a.title, "summary": a.summary, "requested_by": a.requested_by,
            "requested_at": a.requested_at.isoformat(timespec="seconds") if a.requested_at else None, "status": a.status,
            "required_roles": a.required_roles, "outstanding_roles": [r for r in a.required_roles if r not in approved_roles],
            "decisions": a.decisions, "financial_impact_usd": float(a.financial_impact_usd or 0), "risk_evidence": a.risk_evidence,
            "policy_blocked": a.policy_blocked, "related_task_id": a.related_task_id, "related_proposal_id": a.related_proposal_id,
            "related_run_id": a.related_run_id, "data_class": a.data_class,
            "can_be_approved": not a.policy_blocked and a.status not in ("approved", "rejected", "insufficient_data", "blocked")}


def inbox(db: Session, status: str | None = None) -> list[dict]:
    stmt = select(M.Approval).order_by(M.Approval.requested_at.desc())
    if status == "open":
        stmt = stmt.where(M.Approval.status.in_(["pending", "partially_approved", "escalated", "changes_requested"]))
    elif status:
        stmt = stmt.where(M.Approval.status == status)
    return [to_dict(a) for a in db.scalars(stmt)]
