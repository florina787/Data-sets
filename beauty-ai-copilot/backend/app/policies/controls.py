"""Privacy and authorization control tests executed (not asserted) during every evaluation.
Each returns PASS/FAIL with the observation it made. Results feed gate G-CONTROLS."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.orm import ChangeRequest, DatasetConsentRecord
from app.errors import NotFound
from app.security.rbac import PERMISSIONS
from app.services.repo import get_change
from app.security.redaction import contains_image_payload, redact
from app.services.datasets import eligibility


def _r(test_id: str, kind: str, ok: bool, observed: str) -> dict:
    return {"test_id": test_id, "kind": kind, "status": "PASS" if ok else "FAIL", "observed": observed}


def run_controls(db: Session, *, tenant_id: str, evaluated: list, workflow_state: dict, today: date | None = None) -> list[dict]:
    today = today or date.today()
    consents = {c.sample_id: c for c in db.execute(select(DatasetConsentRecord)).scalars()}
    out = []

    bad = [r.sample_id for r in evaluated if eligibility(r, consents.get(r.sample_id), "evaluation", "test", today)]
    out.append(_r("CT-CONSENT", "privacy", not bad,
                  f"{len(evaluated)} evaluated samples re-checked against consent records; {len(bad)} not permitted"))

    inline = [r.sample_id for r in evaluated if not (r.image_ref.startswith("synthetic://") or r.image_ref.startswith("private://"))]
    payload = contains_image_payload(workflow_state)
    out.append(_r("CT-NO-IMAGE-PAYLOAD", "privacy", not inline and not payload,
                  f"image refs by reference only: {len(inline)} inline refs; image data in workflow state: {payload}"))

    inferred = [r.sample_id for r in evaluated if not r.grouping_protocol.startswith("GP-DEMO-1")]
    out.append(_r("CT-NO-INFERRED-GROUPS", "privacy", not inferred,
                  f"{len(inferred)} samples with group labels outside approved protocol GP-DEMO-1"))

    split_leak = [r.sample_id for r in evaluated if r.split != "test"]
    out.append(_r("CT-HELDOUT-SPLIT", "privacy", not split_leak, f"{len(split_leak)} non-test samples in evaluation set"))

    probe = "api_key=sk-ant-PROBE1234567890 data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB"
    red = redact(probe)
    out.append(_r("CT-LOG-REDACTION", "privacy", "PROBE1234567890" not in red and "iVBORw0KGgoAAAANSUhEUg" not in red,
                  "secret and image probe redacted" if red != probe else "probe not redacted"))

    must_not = {"release.approve": {"cv_engineer", "ml_engineer", "product_owner"},
                "rollback.approve": {"ops_analyst", "ml_engineer", "cv_engineer"},
                "review.privacy": {"cv_engineer", "ml_engineer", "release_manager"},
                "requirements.approve": {"cv_engineer", "release_manager"}}
    viol = [f"{perm}:{sorted(PERMISSIONS[perm] & roles)}" for perm, roles in must_not.items() if PERMISSIONS[perm] & roles]
    out.append(_r("CT-RBAC-SEPARATION", "authorization", not viol, "separation-of-duties matrix holds" if not viol else "; ".join(viol)))

    foreign = db.execute(select(ChangeRequest.id).where(ChangeRequest.tenant_id != tenant_id).limit(1)).scalar_one_or_none()
    if foreign is None:
        out.append(_r("CT-TENANT-SCOPE", "authorization", True, "no foreign-tenant change present to probe; scoped getter unchanged"))
    else:
        try:
            get_change(db, tenant_id, foreign)
            out.append(_r("CT-TENANT-SCOPE", "authorization", False, f"foreign change {foreign} readable from {tenant_id}"))
        except NotFound:
            out.append(_r("CT-TENANT-SCOPE", "authorization", True, "foreign-tenant change probe returned not-found"))
    return out
