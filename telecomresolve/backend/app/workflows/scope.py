"""Case access scope: tenant isolation and account-segment checks happen
before any evidence retrieval. Out-of-scope cases are reported as not found
so their existence is not disclosed."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.session import Principal
from ..models.orm import Account, Case
from ..observability import audit


def scoped_case(db: Session, principal: Principal, case_id: str, *, for_update: bool = False) -> Case:
    q = select(Case).where(Case.id == case_id, Case.tenant_id == principal.tenant_id)
    if for_update:
        q = q.with_for_update()
    case = db.scalar(q)
    allowed = False
    if case is not None:
        segment = db.scalar(select(Account.segment).where(Account.id == case.account_id,
                                                          Account.tenant_id == principal.tenant_id))
        allowed = segment in principal.account_segments
    if not allowed:
        audit.record(db, tenant_id=principal.tenant_id, actor_id=principal.user_id,
                     actor_role=principal.role, event_type="ACCESS_DENIED", case_id=None,
                     detail={"requested_case_id": case_id,
                             "reason": "case not in caller's tenant or account scope"})
        db.commit()
        raise HTTPException(status_code=404, detail={"code": "CASE_NOT_FOUND",
                                                     "message": "Case not found in your scope"})
    return case


def visible_case_filter(db: Session, principal: Principal):
    segs = list(principal.account_segments)
    return (select(Case).join(Account, Account.id == Case.account_id)
            .where(Case.tenant_id == principal.tenant_id, Account.segment.in_(segs)))
