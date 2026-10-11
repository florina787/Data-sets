"""Change lifecycle services. Every state change goes through `transition`, which checks the
permitted-transition table; prerequisites are checked here, server-side, before transitioning."""
from __future__ import annotations

import json
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import Conflict, Forbidden, NotFound, PolicyViolation, ValidationFailed
from app.lifecycle.state_machine import S, assert_transition
from app.models.orm import (AcceptanceCriterion, Approval, ChangeRequest, Clarification, CodeRevision, CopilotMessage,
                            DatasetVersion, EvaluationRun, EvidenceReference, ImpactAssessment, ModelVersion,
                            RequirementVersion, Review, User, new_id, utcnow)
from app.security.rbac import require
from app.services import audit, binding, fixtures
from app.services.repo import get_change
from app.workflows import graph

EVAL_CONFIG_ID = "EVC-SHADE-2026.2"


def transition(db: Session, ch: ChangeRequest, to: S | str, actor: str, reason: str, refs: dict | None = None) -> None:
    to = S(to)
    prereq = assert_transition(ch.status, to.value)
    src = ch.status
    ch.status = to.value
    audit.record(db, tenant_id=ch.tenant_id, change_id=ch.id, actor_id=actor, action="state.transition", status="OK",
                 reason=f"{src} -> {to.value}: {reason} [prerequisite: {prereq}]", input_refs=refs or {}, trace_id=ch.trace_id)


def message(db: Session, ch: ChangeRequest, role: str, author: str, text: str, refs: list | None = None) -> None:
    db.add(CopilotMessage(change_id=ch.id, role=role, author=author, text=text, refs=refs or []))


# ---------------------------------------------------------------------------
# Tool factory: facts and DB-backed read tools for agents
# ---------------------------------------------------------------------------

def tool_factory(db: Session, ch: ChangeRequest, extra_facts: dict | None = None):
    from app.services import gates  # local import avoids a cycle

    def factory(agent: str):
        rv = db.get(RequirementVersion, ch.current_requirement_version_id) if ch.current_requirement_version_id else None
        latest_rv = latest_requirement(db, ch.id)
        clar = db.execute(select(Clarification).where(Clarification.change_id == ch.id)).scalars().all()
        answered = {c.key: {"answer": c.answer, "structured": c.structured_answer} for c in clar if c.answer}
        facts = {"statement": (latest_rv or rv).statement if (latest_rv or rv) else ch.description,
                 "scope": (rv.scope if rv else (latest_rv.scope if latest_rv else {})) or {},
                 "answered": answered, "demo_clarifications": fixtures.demo_clarifications() if get_settings().demo else {},
                 "evaluation_config_id": ch.evaluation_config_id, **(extra_facts or {})}
        ds = fixtures.dataset_file()
        tools = {
            "system_map.read": lambda: fixtures.load_json(fixtures.synthetic_dir() / "system_map.json"),
            "dataset.describe": lambda: {"dataset_snapshot_id": ds["dataset_snapshot_id"], "devices_covered": ds["devices_covered"],
                                         "records": len(ds["records"]), "synthetic": True},
            "revision.read": lambda: _revision_dict(db, ch),
            "evaluation.read": lambda: _run_summary(db, ch),
            "reviews.read": lambda: gates.review_status(db, ch),
            "gates.read": lambda: {"gates": [g.dict() for g in gates.release_gates(db, ch)]},
            "monitoring.read": lambda: (extra_facts or {})["monitoring"],
            "model_registry.read": lambda: (extra_facts or {})["registry"],
        }
        return facts, tools
    return factory


def _revision_dict(db: Session, ch: ChangeRequest) -> dict:
    rev = db.get(CodeRevision, ch.code_revision_id)
    if rev is None:
        raise NotFound("revision_not_found", "No code revision registered")
    return {"revision_id": rev.id, "diff": rev.diff, "requirement_refs": rev.requirement_refs, "test_refs": rev.test_refs,
            "author": rev.author_user_id}


def _run_summary(db: Session, ch: ChangeRequest) -> dict:
    run = db.get(EvaluationRun, ch.latest_evaluation_run_id) if ch.latest_evaluation_run_id else None
    if run is None or not run.summary:
        raise NotFound("evaluation_not_found", "No completed evaluation")
    return {**run.summary, "run_id": run.id, "outcome": run.outcome}


def run_agents(db: Session, ch: ChangeRequest, user: User, agents: list[str], interrupt: dict | None = None,
               extra_facts: dict | None = None) -> dict:
    return graph.run(db, ch, agents, user.roles, tool_factory(db, ch, extra_facts), user.id, interrupt=interrupt)


# ---------------------------------------------------------------------------
# Requirements
# ---------------------------------------------------------------------------

def latest_requirement(db: Session, change_id: str) -> RequirementVersion | None:
    return db.execute(select(RequirementVersion).where(RequirementVersion.change_id == change_id)
                      .order_by(RequirementVersion.version.desc()).limit(1)).scalar_one_or_none()


def create_change(db: Session, user: User, title: str, description: str, scenario: str = "foundation_shade",
                  change_id: str | None = None) -> ChangeRequest:
    require(user, "change.create")
    if not description.strip():
        raise ValidationFailed("empty_description", "Change description is required")
    ch = ChangeRequest(id=change_id or f"BR-{uuid.uuid4().hex[:6].upper()}", tenant_id=user.tenant_id, title=title,
                       description=description, scenario=scenario, status=S.DRAFT.value, created_by=user.id,
                       baseline_model_id="shade-matcher-v2.3.0", trace_id=uuid.uuid4().hex)
    db.add(ch)
    db.flush()
    rv = RequirementVersion(id=new_id("RV"), change_id=ch.id, version=1, statement=description, scope={}, status="DRAFT")
    db.add(rv)
    audit.record(db, tenant_id=ch.tenant_id, change_id=ch.id, actor_id=user.id, action="change.create", status="OK",
                 reason=title, version_refs={"requirement_version": rv.id}, trace_id=ch.trace_id)
    message(db, ch, "user", user.id, description)
    final = run_agents(db, ch, user, ["requirements"])
    out = final["outputs"]["requirements"]["data"]
    for a in out["ambiguities"]:
        db.add(Clarification(id=new_id("CL"), change_id=ch.id, key=a["key"], question=a["question"], required=a["required"],
                             owner_role=a["owner_role"], suggested_answer=a["suggested_answer"],
                             structured_answer=None, evidence_refs=a["related_guidance"]))
    if out["ambiguities"]:
        transition(db, ch, S.NEEDS_CLARIFICATION, "agent:requirements", f"{len(out['ambiguities'])} ambiguities flagged")
    db.flush()
    _interrupt(db, ch, "clarification_answers", "Answer required clarifications")
    return ch


def _interrupt(db: Session, ch: ChangeRequest, awaiting: str, detail: str) -> None:
    from app.models.orm import WorkflowCheckpoint
    db.add(WorkflowCheckpoint(change_id=ch.id, thread_id=f"H-{ch.id}", step=0,
                              node="human", status="INTERRUPTED", state={"status": ch.status}, pending_nodes=[],
                              interrupt={"awaiting": awaiting, "detail": detail}))


def answer_clarification(db: Session, user: User, change_id: str, key: str, answer: str | None,
                         structured: dict | None, use_suggested: bool = False) -> Clarification:
    require(user, "clarification.answer")
    ch = get_change(db, user.tenant_id, change_id)
    if ch.status not in (S.NEEDS_CLARIFICATION.value, S.DRAFT.value):
        raise PolicyViolation("clarification_closed", f"Clarifications cannot be changed in state {ch.status}")
    cl = db.execute(select(Clarification).where(Clarification.change_id == ch.id, Clarification.key == key)).scalar_one_or_none()
    if cl is None:
        raise NotFound("clarification_not_found", f"No clarification '{key}'")
    if use_suggested:
        if not get_settings().demo:
            raise Forbidden("demo_only", "Configured demo clarifications are only available in demo mode")
        demo = fixtures.demo_clarifications().get(key)
        if not demo:
            raise ValidationFailed("no_suggestion", f"No configured demo answer for '{key}'")
        answer, structured = demo["answer"], demo["structured"]
    if not answer or not answer.strip():
        raise ValidationFailed("empty_answer", "Answer text is required")
    if structured is not None and not isinstance(structured, dict):
        raise ValidationFailed("invalid_structured", "Structured answer must be an object")
    if cl.answer:
        cl.cycle += 1
    cl.answer, cl.structured_answer, cl.answered_by, cl.answered_at = answer.strip(), structured or {}, user.id, utcnow()
    audit.record(db, tenant_id=ch.tenant_id, change_id=ch.id, actor_id=user.id, action="clarification.answer", status="OK",
                 reason=f"{key}: {answer[:200]}", input_refs={"clarification_id": cl.id, "cycle": cl.cycle}, trace_id=ch.trace_id)
    db.flush()
    remaining = db.execute(select(Clarification).where(Clarification.change_id == ch.id, Clarification.required.is_(True),
                                                       Clarification.answer.is_(None))).scalars().all()
    if not remaining:
        _new_requirement_version(db, ch, user)
    return cl


def _new_requirement_version(db: Session, ch: ChangeRequest, user: User) -> RequirementVersion:
    final = run_agents(db, ch, user, ["requirements"])
    out = final["outputs"]["requirements"]["data"]
    prev = latest_requirement(db, ch.id)
    if prev and prev.status == "DRAFT" and prev.version > 1:
        prev.status = "SUPERSEDED"
    rv = RequirementVersion(id=new_id("RV"), change_id=ch.id, version=(prev.version + 1 if prev else 1), statement=ch.description,
                            scope=out["scope"], status="DRAFT")
    db.add(rv)
    db.flush()
    for c in out["acceptance_criteria"]:
        db.add(AcceptanceCriterion(id=new_id("AC"), requirement_version_id=rv.id, code=c["code"], text=c["text"],
                                   metric=c["metric"], gate_id=c["gate_id"]))
    audit.record(db, tenant_id=ch.tenant_id, change_id=ch.id, actor_id="agent:requirements", action="requirement.version",
                 status="DRAFT", reason=f"v{rv.version} with {len(out['acceptance_criteria'])} acceptance criteria",
                 version_refs={"requirement_version": rv.id}, trace_id=ch.trace_id)
    _interrupt(db, ch, "requirement_approval", f"Product owner approval of requirement v{rv.version}")
    return rv


def approve_requirements(db: Session, user: User, change_id: str) -> RequirementVersion:
    require(user, "requirements.approve")
    ch = get_change(db, user.tenant_id, change_id)
    open_req = db.execute(select(Clarification).where(Clarification.change_id == ch.id, Clarification.required.is_(True),
                                                      Clarification.answer.is_(None))).scalars().all()
    if open_req:
        raise PolicyViolation("unresolved_ambiguity", f"{len(open_req)} required clarifications unanswered",
                              {"keys": [c.key for c in open_req]})
    rv = latest_requirement(db, ch.id)
    if rv is None or rv.status != "DRAFT":
        raise PolicyViolation("no_draft_requirement", "No draft requirement version to approve")
    if not db.execute(select(AcceptanceCriterion).where(AcceptanceCriterion.requirement_version_id == rv.id)).first() and rv.version > 1:
        raise PolicyViolation("no_acceptance_criteria", "Requirement version has no acceptance criteria")
    for old in db.execute(select(RequirementVersion).where(RequirementVersion.change_id == ch.id,
                                                           RequirementVersion.status == "APPROVED")).scalars():
        old.status = "SUPERSEDED"
    rv.status, rv.approved_by, rv.approved_at = "APPROVED", user.id, utcnow()
    ch.current_requirement_version_id = rv.id
    db.add(Approval(id=new_id("AP"), change_id=ch.id, kind="requirements", decision="APPROVED", approver_id=user.id,
                    binding={"requirement_version_id": rv.id}, binding_digest=binding.digest({"requirement_version_id": rv.id}),
                    nonce=uuid.uuid4().hex, expires_at=utcnow() + timedelta(days=365)))
    transition(db, ch, S.REQUIREMENTS_APPROVED, user.id, f"requirement v{rv.version} approved", {"requirement_version": rv.id})
    message(db, ch, "system", "lifecycle", f"Requirement v{rv.version} approved by {user.display_name}. Next: run evidence and impact investigation.")
    return rv


# ---------------------------------------------------------------------------
# Evidence and impact
# ---------------------------------------------------------------------------

def investigate(db: Session, user: User, change_id: str) -> dict:
    require(user, "investigate.run")
    ch = get_change(db, user.tenant_id, change_id)
    if ch.status not in (S.REQUIREMENTS_APPROVED.value, S.IMPACT_REVIEW.value):
        raise PolicyViolation("illegal_state", f"Investigation requires REQUIREMENTS_APPROVED (current {ch.status})")
    final = run_agents(db, ch, user, ["evidence", "impact"], interrupt={"awaiting": "impact_acceptance"})
    ev, im = final["outputs"]["evidence"]["data"], final["outputs"]["impact"]["data"]
    for old in db.execute(select(EvidenceReference).where(EvidenceReference.change_id == ch.id)).scalars():
        db.delete(old)
    for c in ev["citations"]:
        db.add(EvidenceReference(id=new_id("EV"), change_id=ch.id, source_id=c["source_id"], source_version=c["source_version"],
                                 section=c["section"], excerpt=c["excerpt"], retrieved_by=user.id, purpose=c["purpose"],
                                 validation_status=c["validation_status"] if c["usable_as_authority"] else
                                 ("INJECTION_IGNORED" if any("instruction" in f for f in c["flags"]) else c["validation_status"]),
                                 flags=c["flags"]))
    db.add(ImpactAssessment(id=new_id("IA"), change_id=ch.id, requirement_version_id=ch.current_requirement_version_id, content=im))
    if ch.status == S.REQUIREMENTS_APPROVED.value:
        transition(db, ch, S.IMPACT_REVIEW, user.id, "evidence and impact agents completed")
    return {"evidence": ev, "impact": im, "thread_id": final["thread_id"]}


def accept_impact(db: Session, user: User, change_id: str) -> ImpactAssessment:
    require(user, "impact.accept")
    ch = get_change(db, user.tenant_id, change_id)
    ia = db.execute(select(ImpactAssessment).where(ImpactAssessment.change_id == ch.id)
                    .order_by(ImpactAssessment.created_at.desc()).limit(1)).scalar_one_or_none()
    if ia is None:
        raise PolicyViolation("no_impact", "Run the investigation first")
    if ia.requirement_version_id != ch.current_requirement_version_id:
        raise PolicyViolation("stale_impact", "Impact assessment is for an older requirement version")
    ia.accepted_by, ia.accepted_at = user.id, utcnow()
    ch.impact_accepted = True
    transition(db, ch, S.DEVELOPMENT, user.id, "impact assessment accepted", {"impact_id": ia.id})
    message(db, ch, "system", "lifecycle", "Impact accepted. Next: register a candidate revision for evaluation.")
    return ia


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------

def invalidate_bindings(db: Session, ch: ChangeRequest, reason: str, actor: str) -> int:
    n = 0
    for a in db.execute(select(Approval).where(Approval.change_id == ch.id, Approval.kind == "release",
                                               Approval.invalidated_at.is_(None), Approval.consumed_at.is_(None))).scalars():
        a.invalidated_at, a.invalidated_reason = utcnow(), reason
        n += 1
    for r in db.execute(select(Review).where(Review.change_id == ch.id, Review.invalidated_at.is_(None))).scalars():
        if r.kind == "code" and r.binding.get("code_revision_id") == ch.code_revision_id:
            continue  # code review stays bound to the unchanged revision
        r.invalidated_at, r.invalidated_reason = utcnow(), reason
        n += 1
    if n:
        audit.record(db, tenant_id=ch.tenant_id, change_id=ch.id, actor_id=actor, action="approvals.invalidated", status="OK",
                     reason=f"{n} reviews/approvals invalidated: {reason}", trace_id=ch.trace_id)
    return n


def register_candidate(db: Session, user: User, change_id: str, model_id: str) -> ChangeRequest:
    require(user, "candidate.register")
    ch = get_change(db, user.tenant_id, change_id)
    allowed = {S.DEVELOPMENT.value, S.EVALUATION_FAILED.value, S.EVALUATION_INCONCLUSIVE.value, S.REVIEW_REQUIRED.value}
    if ch.status not in allowed:
        raise PolicyViolation("illegal_state", f"Candidates can be registered in {sorted(allowed)} (current {ch.status})")
    mv = db.get(ModelVersion, model_id)
    if mv is None or mv.role == "baseline":
        raise ValidationFailed("invalid_candidate", f"{model_id} is not a registered candidate model")
    if fixtures.compute_artifact_digest(model_id) != mv.artifact_digest:
        raise PolicyViolation("artifact_digest_mismatch", f"Artifact for {model_id} does not match its registered digest")
    if ch.status != S.DEVELOPMENT.value:
        transition(db, ch, S.DEVELOPMENT, user.id, f"new candidate {model_id} registered")
    ch.candidate_model_id, ch.code_revision_id = model_id, mv.code_revision_id
    ch.dataset_snapshot_id = db.execute(select(DatasetVersion.id)).scalars().first()
    ch.evaluation_config_id = EVAL_CONFIG_ID
    ch.latest_evaluation_run_id = None
    invalidate_bindings(db, ch, f"candidate changed to {model_id}", user.id)
    audit.record(db, tenant_id=ch.tenant_id, change_id=ch.id, actor_id=user.id, action="candidate.register", status="OK",
                 reason=model_id, version_refs={"artifact_digest": mv.artifact_digest, "code_revision": mv.code_revision_id},
                 trace_id=ch.trace_id)
    run_agents(db, ch, user, ["development"], interrupt={"awaiting": "code_review_and_evaluation"})
    return ch


def cancel(db: Session, user: User, change_id: str, reason: str) -> ChangeRequest:
    require(user, "change.cancel")
    ch = get_change(db, user.tenant_id, change_id)
    transition(db, ch, S.CANCELLED, user.id, reason or "cancelled")
    invalidate_bindings(db, ch, "change cancelled", user.id)
    return ch
