"""Human-in-the-loop review: work products, approvals, rejections and delivery gates."""

from __future__ import annotations

from sqlalchemy import select

from app.access.matter_access import check_ethical_wall, check_matter_access
from app.access.rbac import has_permission
from app.audit import service as audit
from app.models.db import ReviewRow, WorkProductRow, session
from app.services.data_store import DataStore


class ReviewError(Exception):
    def __init__(self, code: str, message: str, http_status: int = 403):
        super().__init__(message)
        self.code, self.message, self.http_status = code, message, http_status


def save_work_product(*, work_product_id: str, request_id: str, matter_id: str, kind: str, title: str, content: dict,
                      assurance: dict, destination: str, required_roles: list[str], created_by: str) -> None:
    with session() as s:
        existing = s.get(WorkProductRow, work_product_id)
        if existing is None:
            s.add(WorkProductRow(work_product_id=work_product_id, request_id=request_id, matter_id=matter_id, kind=kind,
                                 title=title, content=content, assurance=assurance, destination=destination,
                                 required_approver_roles=required_roles, created_by=created_by, status="PENDING_REVIEW"))
        s.commit()


def get_work_product(work_product_id: str) -> dict | None:
    with session() as s:
        r = s.get(WorkProductRow, work_product_id)
        if r is None:
            return None
        reviews = s.execute(select(ReviewRow).where(ReviewRow.work_product_id == work_product_id)).scalars().all()
        return {"work_product_id": r.work_product_id, "request_id": r.request_id, "matter_id": r.matter_id, "kind": r.kind,
                "title": r.title, "status": r.status, "destination": r.destination, "assurance": r.assurance,
                "required_approver_roles": r.required_approver_roles, "created_by": r.created_by,
                "created_at": r.created_at.isoformat() if r.created_at else None, "content": r.content,
                "reviews": [{"reviewer_id": v.reviewer_id, "decision": v.decision, "destination": v.destination,
                             "comment": v.comment, "ts": v.ts.isoformat()} for v in reviews]}


def list_work_products(matter_id: str | None = None) -> list[dict]:
    with session() as s:
        q = select(WorkProductRow).order_by(WorkProductRow.created_at.desc())
        if matter_id:
            q = q.where(WorkProductRow.matter_id == matter_id)
        rows = s.execute(q.limit(100)).scalars().all()
        return [{"work_product_id": r.work_product_id, "matter_id": r.matter_id, "title": r.title, "status": r.status,
                 "destination": r.destination, "kind": r.kind, "assurance_status": (r.assurance or {}).get("status"),
                 "assurance_pct": (r.assurance or {}).get("score_pct"), "created_at": r.created_at.isoformat()} for r in rows]


def decide(store: DataStore, *, work_product_id: str, reviewer_id: str, decision: str, destination: str | None,
           comment: str) -> dict:
    reviewer = store.users.get(reviewer_id)
    with session() as s:
        wp = s.get(WorkProductRow, work_product_id)
        if wp is None:
            raise ReviewError("NOT_FOUND", "Work product not found.", 404)
        matter = store.matters.get(wp.matter_id)
        acc = check_matter_access(store, reviewer, matter)
        wall = check_ethical_wall(store, reviewer, wp.matter_id)
        ctx = dict(request_id=wp.request_id, user_id=reviewer_id, client_id=matter.client_id if matter else None,
                   matter_id=wp.matter_id)
        if not acc.allowed or wall.blocked:
            audit.record("REVIEW_DENIED", **ctx, payload={"work_product_id": work_product_id, "reason": "no matter access"},
                         severity="WARNING")
            raise ReviewError("ACCESS_DENIED", "Reviewer does not have access to this matter.")
        if wp.status in ("APPROVED", "REJECTED"):
            raise ReviewError("ALREADY_DECIDED", f"Work product already {wp.status.lower()}.", 409)
        dest = destination or wp.destination
        if decision == "APPROVE":
            needed = "approve_external" if dest.startswith("external") else "approve_internal"
            if not has_permission(reviewer, needed):
                audit.record("REVIEW_DENIED", **ctx, payload={"work_product_id": work_product_id, "reason": f"role lacks {needed}"},
                             severity="WARNING")
                raise ReviewError("ROLE_NOT_PERMITTED", f"Role {reviewer.role.value} cannot approve for destination '{dest}'.")
            if wp.required_approver_roles and reviewer.role.value not in wp.required_approver_roles:
                audit.record("REVIEW_DENIED", **ctx, payload={"work_product_id": work_product_id, "reason": "escalation requires partner"},
                             severity="WARNING")
                raise ReviewError("ESCALATION_REQUIRES_PARTNER",
                                  "This work product contains playbook escalations and requires Partner approval.")
            assurance_status = (wp.assurance or {}).get("status")
            if dest.startswith("external") and assurance_status != "PASS":
                audit.record("DELIVERY_BLOCKED", **ctx, payload={"work_product_id": work_product_id, "destination": dest,
                                                                "assurance_status": assurance_status,
                                                                "rule": "POL-DEST-001"}, severity="WARNING")
                raise ReviewError("ASSURANCE_GATE",
                                  f"External delivery blocked: assurance status is {assurance_status}. Resolve evidence issues "
                                  "and re-run assurance, or approve for internal use only.", 409)
            wp.status = "APPROVED"
            event = "HUMAN_REVIEW_APPROVED"
        elif decision == "REJECT":
            if not has_permission(reviewer, "approve_internal"):
                raise ReviewError("ROLE_NOT_PERMITTED", f"Role {reviewer.role.value} cannot review work product.")
            wp.status = "REJECTED"
            event = "HUMAN_REVIEW_REJECTED"
        else:
            raise ReviewError("BAD_DECISION", "Decision must be APPROVE or REJECT.", 400)
        s.add(ReviewRow(work_product_id=work_product_id, reviewer_id=reviewer_id, decision=decision, destination=dest,
                        comment=comment[:2000]))
        wp.destination = dest
        s.commit()
    audit.record(event, **ctx, payload={"work_product_id": work_product_id, "destination": dest, "comment": comment[:500]})
    audit.record("FINAL_STATUS", **ctx, payload={"work_product_id": work_product_id, "status": "APPROVED" if decision == "APPROVE" else "REJECTED"})
    return get_work_product(work_product_id)
