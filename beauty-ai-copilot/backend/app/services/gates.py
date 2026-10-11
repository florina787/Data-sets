"""Reviews, release approval and release-time gates (deterministic)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import Forbidden, PolicyViolation, ValidationFailed
from app.lifecycle.state_machine import S
from app.models.orm import Approval, ChangeRequest, CodeRevision, EvaluationRun, ModelVersion, Review, User, new_id, utcnow
from app.policies.engine import FAIL, INCONCLUSIVE, PASS, Gate, overall
from app.security.rbac import require
from app.services import audit, binding, fixtures
from app.services.lifecycle import message, transition
from app.services.repo import get_change

REVIEW_PERMS = {"code": "review.code", "domain": "review.domain", "privacy": "review.privacy", "qa": "review.qa"}


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _active_reviews(db: Session, ch: ChangeRequest, kind: str) -> list[Review]:
    return db.execute(select(Review).where(Review.change_id == ch.id, Review.kind == kind, Review.invalidated_at.is_(None))
                      .order_by(Review.created_at.desc())).scalars().all()


def review_status(db: Session, ch: ChangeRequest) -> dict:
    pol, _ = fixtures.policy()
    cur = binding.digest(binding.current_binding(db, ch))
    code_cur = binding.digest(binding.code_review_binding(db, ch))
    status = {}
    for k in pol["required_reviews"]:
        rs = _active_reviews(db, ch, k)
        want = code_cur if k == "code" else cur
        latest = next((r for r in rs if r.binding_digest == want), None)
        status[k] = latest.decision if latest else ("STALE" if rs else "PENDING")
    return {"required": pol["required_reviews"], "status": status}


def submit_review(db: Session, user: User, change_id: str, kind: str, decision: str, comment: str = "") -> Review:
    if kind not in REVIEW_PERMS:
        raise ValidationFailed("invalid_review_kind", f"Unknown review kind {kind}")
    if decision not in ("APPROVE", "REJECT"):
        raise ValidationFailed("invalid_decision", "decision must be APPROVE or REJECT")
    require(user, REVIEW_PERMS[kind])
    ch = get_change(db, user.tenant_id, change_id)
    if kind == "code":
        if ch.status not in (S.DEVELOPMENT.value, S.EVALUATING.value, S.EVALUATION_FAILED.value,
                             S.EVALUATION_INCONCLUSIVE.value, S.REVIEW_REQUIRED.value):
            raise PolicyViolation("illegal_state", f"Code review not possible in {ch.status}")
        rev = db.get(CodeRevision, ch.code_revision_id) if ch.code_revision_id else None
        if rev is None:
            raise PolicyViolation("no_revision", "No code revision to review")
        if rev.author_user_id == user.id:
            raise PolicyViolation("separation_of_duties", "Code reviewer must differ from the revision author")
        b = binding.code_review_binding(db, ch)
    else:
        if ch.status != S.REVIEW_REQUIRED.value:
            raise PolicyViolation("illegal_state", f"{kind} review requires REVIEW_REQUIRED (current {ch.status})")
        b = binding.current_binding(db, ch)
    r = Review(id=new_id("RVW"), change_id=ch.id, kind=kind, decision=decision, reviewer_id=user.id, comment=comment,
               binding=b, binding_digest=binding.digest(b))
    db.add(r)
    audit.record(db, tenant_id=ch.tenant_id, change_id=ch.id, actor_id=user.id, action=f"review.{kind}", status=decision,
                 reason=comment[:500], version_refs=b, trace_id=ch.trace_id)
    message(db, ch, "system", "lifecycle", f"{kind.title()} review: {decision} by {user.display_name}." + (f" “{comment}”" if comment else ""))
    if decision == "REJECT" and kind != "code" and ch.status == S.REVIEW_REQUIRED.value:
        transition(db, ch, S.DEVELOPMENT, user.id, f"{kind} review rejected")
    return r


def _evaluation_gates_current(db: Session, ch: ChangeRequest) -> list[Gate]:
    pol, pol_digest = fixtures.policy()
    owners = pol["gate_owners"]
    run = db.get(EvaluationRun, ch.latest_evaluation_run_id) if ch.latest_evaluation_run_id else None
    g = []
    if run is None or run.status != "SUCCEEDED":
        g.append(Gate("G-EVALUATION", "A completed evaluation of the current candidate exists with outcome PASS",
                      "no completed evaluation", INCONCLUSIVE, owners["G-FRESHNESS"]))
        return g
    g.append(Gate("G-EVALUATION", "A completed evaluation of the current candidate exists with outcome PASS",
                  f"run {run.id}: {run.outcome}", PASS if run.outcome == PASS else (FAIL if run.outcome == FAIL else INCONCLUSIVE),
                  owners["G-FRESHNESS"], [{"record": f"evaluation:{run.id}"}]))
    mv = db.get(ModelVersion, ch.candidate_model_id)
    computed = fixtures.compute_artifact_digest(ch.candidate_model_id)
    stale = []
    if run.candidate_model_id != ch.candidate_model_id:
        stale.append("candidate model changed")
    if run.candidate_artifact_digest != computed or mv.artifact_digest != computed:
        stale.append("artifact digest mismatch")
    if run.requirement_version_id != ch.current_requirement_version_id:
        stale.append("requirement version changed")
    if run.evaluation_config_digest != fixtures.eval_config(run.evaluation_config_id)[1]:
        stale.append("evaluation config changed")
    if run.dataset_digest != fixtures.dataset_digest():
        stale.append("dataset changed")
    if run.policy_version != pol["policy_version"]:
        stale.append("policy version changed")
    age = (utcnow() - _aware(run.finished_at)).days if run.finished_at else 999
    if age > pol["evaluation_max_age_days"]:
        stale.append(f"evaluation is {age} days old (max {pol['evaluation_max_age_days']})")
    g.append(Gate("G-FRESHNESS", "Evaluation is current: same candidate digest, requirement version, config, dataset and policy; not older than max age",
                  "current" if not stale else "STALE: " + "; ".join(stale), PASS if not stale else FAIL, owners["G-FRESHNESS"],
                  [{"record": f"evaluation:{run.id}"}]))
    return g


def release_gates(db: Session, ch: ChangeRequest, approval: Approval | None = None) -> list[Gate]:
    pol, _ = fixtures.policy()
    owners = pol["gate_owners"]
    if not ch.candidate_model_id:
        return [Gate("G-CONFIG", "A candidate is registered", "no candidate", INCONCLUSIVE, owners["G-CONFIG"])]
    gates = _evaluation_gates_current(db, ch)
    rs = review_status(db, ch)
    rev = db.get(CodeRevision, ch.code_revision_id)
    code = rs["status"].get("code")
    gates.append(Gate("G-CODE-REVIEW", "Implementation diff reviewed and approved by someone other than its author",
                      f"code review: {code} (author {rev.author_user_id if rev else '?'})",
                      PASS if code == "APPROVE" else (FAIL if code == "REJECT" else INCONCLUSIVE), owners["G-CODE-REVIEW"],
                      [{"source_id": "POL-REL-005", "source_version": "2.1", "section": "§2"}]))
    other = {k: v for k, v in rs["status"].items() if k != "code"}
    gates.append(Gate("G-REVIEWS", "Domain and privacy reviews approved and bound to the current artifacts",
                      ", ".join(f"{k}: {v}" for k, v in other.items()),
                      PASS if all(v == "APPROVE" for v in other.values()) else (FAIL if "REJECT" in other.values() else INCONCLUSIVE),
                      owners["G-REVIEWS"], [{"source_id": "POL-REL-005", "source_version": "2.1", "section": "§3"}]))
    if approval is not None:
        problems = approval_problems(db, ch, approval)
        gates.append(Gate("G-APPROVAL", "Release approval valid: approved, unexpired, unused, bound to current artifacts, approver ≠ author",
                          "valid" if not problems else "; ".join(problems), PASS if not problems else FAIL, owners["G-APPROVAL"],
                          [{"record": f"approval:{approval.id}"}]))
    return gates


def approval_problems(db: Session, ch: ChangeRequest, a: Approval) -> list[str]:
    p = []
    if a.kind != "release" or a.decision != "APPROVED":
        p.append("not an approved release approval")
    if a.invalidated_at:
        p.append(f"invalidated: {a.invalidated_reason}")
    if a.consumed_at:
        p.append("already used (replay rejected)")
    if _aware(a.expires_at) < utcnow():
        p.append("expired")
    cur = binding.current_binding(db, ch)
    if binding.digest(cur) != a.binding_digest:
        p.append("binding mismatch: " + ", ".join(binding.diff_fields(a.binding, cur)))
    rev = db.get(CodeRevision, ch.code_revision_id)
    if rev and rev.author_user_id == a.approver_id:
        p.append("approver is the revision author")
    return p


def approve_release(db: Session, user: User, change_id: str, decision: str, comment: str = "") -> Approval:
    require(user, "release.approve")
    ch = get_change(db, user.tenant_id, change_id)
    if ch.status != S.REVIEW_REQUIRED.value:
        raise PolicyViolation("illegal_state", f"Release approval requires REVIEW_REQUIRED (current {ch.status})")
    if decision not in ("APPROVED", "REJECTED"):
        raise ValidationFailed("invalid_decision", "decision must be APPROVED or REJECTED")
    rev = db.get(CodeRevision, ch.code_revision_id)
    if rev and rev.author_user_id == user.id:
        raise PolicyViolation("separation_of_duties", "Release approver must differ from the developer who authored the revision")
    gates = release_gates(db, ch)
    b = binding.current_binding(db, ch)
    if decision == "APPROVED" and overall(gates) != PASS:
        blockers = [f"{g.gate_id}: {g.observed}" for g in gates if g.status != PASS]
        audit.record(db, tenant_id=ch.tenant_id, change_id=ch.id, actor_id=user.id, action="release.approve", status="BLOCKED",
                     reason="; ".join(blockers)[:900], trace_id=ch.trace_id)
        db.commit()
        raise PolicyViolation("release_gates_blocking", "Release gates do not pass; approval not recorded", {"blockers": blockers})
    a = Approval(id=new_id("AP"), change_id=ch.id, kind="release", decision=decision, approver_id=user.id, comment=comment,
                 binding=b, binding_digest=binding.digest(b), nonce=uuid.uuid4().hex,
                 expires_at=utcnow() + timedelta(hours=get_settings().approval_ttl_hours))
    db.add(a)
    audit.record(db, tenant_id=ch.tenant_id, change_id=ch.id, actor_id=user.id, action="release.approve", status=decision,
                 reason=comment[:500], version_refs=b, input_refs={"approval_id": a.id}, trace_id=ch.trace_id)
    if decision == "APPROVED":
        transition(db, ch, S.RELEASE_APPROVED, user.id, "release approved by distinct approver", {"approval_id": a.id})
        message(db, ch, "system", "lifecycle", f"Release approved by {user.display_name} (expires in {get_settings().approval_ttl_hours} h, single use). Approval is bound to model digest, revision, dataset, config, policy and target.")
    else:
        message(db, ch, "system", "lifecycle", f"Release rejected by {user.display_name}." + (f" “{comment}”" if comment else ""))
    return a
