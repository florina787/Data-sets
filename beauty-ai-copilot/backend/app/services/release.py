"""Simulated release, monitoring and rollback. Deployment mode is simulated: no real traffic and no
external writes. Release and rollback are idempotent and revalidate approvals immediately before
acting, with optimistic version guards against concurrent changes."""
from __future__ import annotations

import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import Conflict, IntegrationUnavailable, PolicyViolation, ValidationFailed
from app.lifecycle.state_machine import S
from app.models.orm import (Alert, Approval, ChangeRequest, EvaluationRun, IdempotencyRecord, ModelVersion, MonitoringWindow,
                            Release, RollbackRecord, User, new_id, utcnow)
from app.monitoring import simulator
from app.policies.engine import PASS, overall
from app.security.rbac import require
from app.services import audit, fixtures
from app.services.gates import approval_problems, release_gates
from app.services.lifecycle import message, run_agents, transition
from app.services.repo import get_change, get_release


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

def _idem(db: Session, tenant_id: str, op: str, key: str | None, request: dict) -> dict | None:
    if not key:
        raise ValidationFailed("idempotency_key_required", "Idempotency-Key header is required for this operation")
    rec = db.get(IdempotencyRecord, f"{tenant_id}:{op}:{key}")
    if rec is None:
        return None
    if rec.request_digest != fixtures.canonical_digest(request):
        raise Conflict("idempotency_key_reused", "Idempotency key was used with a different request")
    return {**rec.response, "idempotent_replay": True}


def _idem_store(db: Session, tenant_id: str, op: str, key: str, request: dict, response: dict) -> None:
    db.add(IdempotencyRecord(key=f"{tenant_id}:{op}:{key}", tenant_id=tenant_id, operation=op,
                             request_digest=fixtures.canonical_digest(request), response=response))


def _deployment_guard() -> None:
    if get_settings().deployment_mode != "simulated":
        raise IntegrationUnavailable("deployment_unconfigured", "Real deployment adapter is not configured; external writes are disabled.")


# ---------------------------------------------------------------------------
# Release
# ---------------------------------------------------------------------------

def release_dict(r: Release) -> dict:
    return {"id": r.id, "change_id": r.change_id, "model_id": r.model_id, "artifact_digest": r.artifact_digest,
            "previous_model_id": r.previous_model_id, "deployment_target": r.deployment_target, "approval_id": r.approval_id,
            "status": r.status, "stage_index": r.stage_index, "stages": r.stages, "allocation_pct": r.stages[r.stage_index],
            "history": r.history, "mode": r.mode, "created_at": r.created_at.isoformat()}


def execute_release(db: Session, user: User, change_id: str, idempotency_key: str | None, approval_id: str | None = None) -> dict:
    require(user, "release.execute")
    _deployment_guard()
    req = {"change_id": change_id, "approval_id": approval_id}
    prior = _idem(db, user.tenant_id, "release", idempotency_key, req)
    if prior:
        return prior
    ch = get_change(db, user.tenant_id, change_id)
    if ch.status != S.RELEASE_APPROVED.value:
        raise PolicyViolation("illegal_state", f"Release requires RELEASE_APPROVED (current {ch.status})")
    q = select(Approval).where(Approval.change_id == ch.id, Approval.kind == "release", Approval.decision == "APPROVED")
    if approval_id:
        q = q.where(Approval.id == approval_id)
    a = db.execute(q.order_by(Approval.created_at.desc()).limit(1)).scalar_one_or_none()
    if a is None:
        raise PolicyViolation("no_approval", "No release approval found")
    # Revalidation immediately before deployment.
    gates = release_gates(db, ch, approval=a)
    if overall(gates) != PASS:
        blockers = [f"{g.gate_id}: {g.observed}" for g in gates if g.status != PASS]
        audit.record(db, tenant_id=ch.tenant_id, change_id=ch.id, actor_id=user.id, action="release.execute", status="BLOCKED",
                     reason="; ".join(blockers)[:900], input_refs={"approval_id": a.id}, trace_id=ch.trace_id)
        if any(x in " ".join(blockers) for x in ("binding mismatch", "expired", "invalidated", "STALE")) and not a.consumed_at:
            a.invalidated_at, a.invalidated_reason = utcnow(), "revalidation failed: " + "; ".join(blockers)[:300]
            transition(db, ch, S.REVIEW_REQUIRED, "system:release-guard", "approval no longer valid at deployment time")
        db.commit()
        raise PolicyViolation("revalidation_failed", "Release blocked at revalidation", {"blockers": blockers})
    a.consumed_at, a.consumed_by = utcnow(), "pending"
    pol, _ = fixtures.policy()
    base = db.get(ModelVersion, ch.baseline_model_id)
    rel = Release(id=new_id("REL"), change_id=ch.id, tenant_id=ch.tenant_id, model_id=ch.candidate_model_id,
                  artifact_digest=fixtures.compute_artifact_digest(ch.candidate_model_id), previous_model_id=base.id,
                  previous_artifact_digest=base.artifact_digest, deployment_target=ch.deployment_target, approval_id=a.id,
                  status="CANARY", stage_index=0, stages=pol["rollout_stages_pct"], mode="simulated", created_by=user.id,
                  history=[{"event": "deploy", "stage_pct": pol["rollout_stages_pct"][0], "at": utcnow().isoformat(), "by": user.id,
                            "note": "simulated deployment event (not customer traffic)"}])
    db.add(rel)
    a.consumed_by = rel.id
    transition(db, ch, S.CANARY, user.id, f"simulated canary at {rel.stages[0]}%", {"release_id": rel.id, "approval_id": a.id})
    audit.record(db, tenant_id=ch.tenant_id, change_id=ch.id, actor_id=user.id, action="release.execute", status="OK",
                 reason=f"simulated rollout {rel.stages} to {rel.deployment_target}",
                 version_refs={"artifact_digest": rel.artifact_digest, "approval": a.id}, trace_id=ch.trace_id)
    message(db, ch, "system", "release", f"Simulated canary started at {rel.stages[0]}% (prototype stages {rel.stages}). Last approved version {base.id} preserved for rollback.")
    resp = {"release": release_dict(rel), "idempotent_replay": False}
    _idem_store(db, user.tenant_id, "release", idempotency_key, req, resp)
    db.flush()
    run_agents(db, ch, user, ["release"])
    return resp


def _reference_by_lighting(db: Session, ch: ChangeRequest) -> dict:
    run = db.get(EvaluationRun, ch.latest_evaluation_run_id)
    out = {}
    for light in ("daylight_neutral", "warm_indoor", "cool_fluorescent"):
        cells = [v for k, v in run.summary["cells"].items() if k.endswith("|" + light)]
        k = sum(c["candidate"]["top1_correct"] for c in cells)
        n = sum(c["candidate"]["n_eligible"] for c in cells)
        out[light] = round(100 * k / n, 2)
    return out


def advance_window(db: Session, user: User, release_id: str) -> dict:
    require(user, "monitoring.advance")
    rel = get_release(db, user.tenant_id, release_id)
    if rel.status not in ("CANARY", "MONITORING", "RELEASED"):
        raise PolicyViolation("release_inactive", f"Release is {rel.status}")
    ch = db.get(ChangeRequest, rel.change_id)
    idx = len(db.execute(select(MonitoringWindow).where(MonitoringWindow.release_id == rel.id)).scalars().all())
    mv = db.get(ModelVersion, rel.model_id)
    alloc = rel.stages[rel.stage_index]
    w = simulator.simulate_window(rel.id, rel.model_id, mv.lighting_profile_map_id, idx, alloc)
    mw = MonitoringWindow(id=new_id("MW"), release_id=rel.id, index=idx, allocation_pct=alloc,
                          simulated_sessions=w["simulated_sessions"], exposures=w["exposures"], labelled=w["labelled"], cohorts=w["cells"])
    db.add(mw)
    db.flush()
    pol, _ = fixtures.policy()
    windows = db.execute(select(MonitoringWindow).where(MonitoringWindow.release_id == rel.id)
                         .order_by(MonitoringWindow.index)).scalars().all()
    agg = simulator.cumulative([{"cells": x.cohorts} for x in windows])
    found = simulator.detect(agg, _reference_by_lighting(db, ch), pol["monitoring"]["min_labels_per_cohort_cell"],
                             pol["monitoring"]["alert_drop_pp"])
    new_alerts = []
    for f in found:
        if db.execute(select(Alert).where(Alert.release_id == rel.id, Alert.scope == f["scope"])).first():
            continue
        al = Alert(id=new_id("ALT"), release_id=rel.id, change_id=ch.id, scope=f["scope"], observed=f["observed"],
                   rule=f"labelled ≥ {pol['monitoring']['min_labels_per_cohort_cell']}, accuracy < reference − {pol['monitoring']['alert_drop_pp']} pp, Wilson 95% upper < reference")
        db.add(al)
        new_alerts.append(al)
        audit.record(db, tenant_id=ch.tenant_id, change_id=ch.id, actor_id="system:monitoring", action="alert.open", status="OPEN",
                     reason=f"{f['scope']}: {f['observed']}", input_refs={"release_id": rel.id, "window": idx}, trace_id=ch.trace_id)
        message(db, ch, "system", "monitoring", f"ALERT {al.id}: {f['scope']} observed {f['observed']['accuracy_pct']}% on {f['observed']['labelled']} simulated labelled sessions vs reference {f['observed']['reference_pct']}%. Statistical signal only — investigate before concluding a cause.")
    audit.record(db, tenant_id=ch.tenant_id, change_id=ch.id, actor_id=user.id, action="monitoring.window", status="OK",
                 reason=f"window {idx} at {alloc}%: {w['simulated_sessions']} simulated sessions, {w['labelled']} labelled",
                 input_refs={"release_id": rel.id}, trace_id=ch.trace_id)
    return {"window": window_dict(mw), "new_alerts": [alert_dict(a) for a in new_alerts]}


def window_dict(w: MonitoringWindow) -> dict:
    return {"id": w.id, "index": w.index, "allocation_pct": w.allocation_pct, "simulated_sessions": w.simulated_sessions,
            "exposures": w.exposures, "labelled": w.labelled, "cohorts": w.cohorts, "simulated": True}


def alert_dict(a: Alert) -> dict:
    return {"id": a.id, "release_id": a.release_id, "scope": a.scope, "rule": a.rule, "observed": a.observed, "status": a.status,
            "investigation": a.investigation, "created_at": a.created_at.isoformat()}


def monitoring_view(db: Session, user: User, release_id: str) -> dict:
    require(user, "monitoring.read")
    rel = get_release(db, user.tenant_id, release_id)
    ch = db.get(ChangeRequest, rel.change_id)
    windows = db.execute(select(MonitoringWindow).where(MonitoringWindow.release_id == rel.id).order_by(MonitoringWindow.index)).scalars().all()
    alerts = db.execute(select(Alert).where(Alert.release_id == rel.id).order_by(Alert.created_at)).scalars().all()
    rbs = db.execute(select(RollbackRecord).where(RollbackRecord.release_id == rel.id).order_by(RollbackRecord.created_at)).scalars().all()
    pol, _ = fixtures.policy()
    return {"release": release_dict(rel), "windows": [window_dict(w) for w in windows],
            "cumulative": simulator.cumulative([{"cells": w.cohorts} for w in windows]),
            "reference_by_lighting": _reference_by_lighting(db, ch), "alerts": [alert_dict(a) for a in alerts],
            "rollbacks": [rollback_dict(r) for r in rbs], "rule": pol["monitoring"],
            "simulator": {"sessions_per_window_at_100pct": simulator.SESSIONS_PER_WINDOW_AT_100, "label_rate": simulator.LABEL_RATE,
                          "device_share": simulator.DEVICE_SHARE, "note": "Simulated observations — not customer traffic."}}


def promote(db: Session, user: User, release_id: str) -> dict:
    require(user, "release.execute")
    rel = get_release(db, user.tenant_id, release_id)
    ch = db.get(ChangeRequest, rel.change_id)
    if rel.status not in ("CANARY", "MONITORING"):
        raise PolicyViolation("illegal_state", f"Cannot promote a release in {rel.status}")
    if db.execute(select(Alert).where(Alert.release_id == rel.id, Alert.status != "RESOLVED")).first():
        raise PolicyViolation("open_alert", "Promotion blocked: an alert is open")
    pol, _ = fixtures.policy()
    at_stage = db.execute(select(MonitoringWindow).where(MonitoringWindow.release_id == rel.id,
                                                         MonitoringWindow.allocation_pct == rel.stages[rel.stage_index])).scalars().all()
    if len(at_stage) < pol["min_windows_per_stage"]:
        raise PolicyViolation("insufficient_monitoring", f"Need ≥ {pol['min_windows_per_stage']} monitoring window(s) at {rel.stages[rel.stage_index]}%")
    rel.stage_index += 1
    pct = rel.stages[rel.stage_index]
    rel.history = rel.history + [{"event": "promote", "stage_pct": pct, "at": utcnow().isoformat(), "by": user.id}]
    if rel.stage_index == len(rel.stages) - 1:
        rel.status = "RELEASED"
        if ch.status == S.CANARY.value:
            transition(db, ch, S.MONITORING, user.id, "canary observed without alerts")
        transition(db, ch, S.RELEASED, user.id, f"promoted to {pct}% (simulated)")
    else:
        rel.status = "MONITORING"
        if ch.status == S.CANARY.value:
            transition(db, ch, S.MONITORING, user.id, f"promoted to {pct}% (simulated)")
    audit.record(db, tenant_id=ch.tenant_id, change_id=ch.id, actor_id=user.id, action="release.promote", status="OK",
                 reason=f"stage {pct}%", input_refs={"release_id": rel.id}, trace_id=ch.trace_id)
    message(db, ch, "system", "release", f"Simulated rollout promoted to {pct}%.")
    return release_dict(rel)


def investigate_alert(db: Session, user: User, alert_id: str) -> dict:
    require(user, "alert.investigate")
    al = db.get(Alert, alert_id)
    rel = get_release(db, user.tenant_id, al.release_id) if al else None
    if al is None or rel is None:
        from app.errors import NotFound
        raise NotFound("alert_not_found", f"Alert {alert_id} not found")
    ch = db.get(ChangeRequest, rel.change_id)
    mv, prev = db.get(ModelVersion, rel.model_id), db.get(ModelVersion, rel.previous_model_id)
    maps = fixtures.models_file()["lighting_profile_maps"]
    windows = db.execute(select(MonitoringWindow).where(MonitoringWindow.release_id == rel.id)).scalars().all()
    facts = {"monitoring": {"alert": alert_dict(al), "cohort_cells": simulator.cumulative([{"cells": w.cohorts} for w in windows])},
             "registry": {"released_lpm_id": mv.lighting_profile_map_id, "released_lpm": maps[mv.lighting_profile_map_id],
                          "previous_lpm_id": prev.lighting_profile_map_id, "previous_lpm": maps[prev.lighting_profile_map_id],
                          "previous_model_id": prev.id}}
    final = run_agents(db, ch, user, ["monitoring"], extra_facts=facts,
                       interrupt={"awaiting": "rollback_decision"})
    out = final["outputs"]["monitoring"]["data"]
    al.investigation = out
    al.status = "INVESTIGATED"
    if out["proposed_response"]["action"] == "rollback" and ch.status in (S.CANARY.value, S.MONITORING.value, S.RELEASED.value):
        transition(db, ch, S.ROLLBACK_RECOMMENDED, "agent:monitoring", f"alert {al.id} investigation proposed rollback", {"alert_id": al.id})
    return {"alert": alert_dict(al), "investigation": out}


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------

def rollback_dict(r: RollbackRecord) -> dict:
    return {"id": r.id, "release_id": r.release_id, "requested_by": r.requested_by, "reason": r.reason, "alert_id": r.alert_id,
            "status": r.status, "approved_by": r.approved_by, "target_model_id": r.target_model_id, "compatibility": r.compatibility,
            "error": r.error, "created_at": r.created_at.isoformat(), "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "duration_ms": r.duration_ms}


def request_rollback(db: Session, user: User, release_id: str, reason: str, alert_id: str | None, idempotency_key: str | None) -> dict:
    require(user, "rollback.request")
    req = {"release_id": release_id, "reason": reason, "alert_id": alert_id}
    prior = _idem(db, user.tenant_id, "rollback_request", idempotency_key, req)
    if prior:
        return prior
    rel = get_release(db, user.tenant_id, release_id)
    ch = db.get(ChangeRequest, rel.change_id)
    if rel.status not in ("CANARY", "MONITORING", "RELEASED"):
        raise PolicyViolation("illegal_state", f"Rollback not possible for release in {rel.status}")
    if db.execute(select(RollbackRecord).where(RollbackRecord.release_id == rel.id, RollbackRecord.status == "REQUESTED")).first():
        raise Conflict("rollback_pending", "A rollback request is already pending")
    if not reason.strip():
        raise ValidationFailed("reason_required", "Rollback reason is required")
    rb = RollbackRecord(id=new_id("RB"), release_id=rel.id, change_id=ch.id, requested_by=user.id, reason=reason, alert_id=alert_id,
                        status="REQUESTED", target_model_id=rel.previous_model_id, idempotency_key=idempotency_key)
    db.add(rb)
    if ch.status in (S.CANARY.value, S.MONITORING.value, S.RELEASED.value):
        transition(db, ch, S.ROLLBACK_RECOMMENDED, user.id, f"rollback requested: {reason[:120]}")
    audit.record(db, tenant_id=ch.tenant_id, change_id=ch.id, actor_id=user.id, action="rollback.request", status="REQUESTED",
                 reason=reason[:500], input_refs={"release_id": rel.id, "alert_id": alert_id}, trace_id=ch.trace_id)
    message(db, ch, "system", "release", f"Rollback to {rel.previous_model_id} requested by {user.display_name}; awaiting authorized release-manager review.")
    db.flush()
    resp = {"rollback": rollback_dict(rb), "idempotent_replay": False}
    _idem_store(db, user.tenant_id, "rollback_request", idempotency_key, req, resp)
    return resp


def compatibility(db: Session, rel: Release) -> dict:
    target = db.get(ModelVersion, rel.previous_model_id)
    active_cat = fixtures.load_json(fixtures.synthetic_dir() / "catalogue.json")["catalogue_version"]
    checks = {
        "catalogue_compatible": target.catalogue_version == active_cat,
        "artifact_digest_matches_registry": fixtures.compute_artifact_digest(target.id) == target.artifact_digest,
        "previous_digest_matches_release_record": target.artifact_digest == rel.previous_artifact_digest,
    }
    return {"target_model_id": target.id, "checks": checks, "compatible": all(checks.values()), "active_catalogue": active_cat}


def decide_rollback(db: Session, user: User, rollback_id: str, decision: str, comment: str = "") -> dict:
    require(user, "rollback.approve")
    rb = db.get(RollbackRecord, rollback_id)
    rel = get_release(db, user.tenant_id, rb.release_id) if rb else None
    if rb is None or rel is None:
        from app.errors import NotFound
        raise NotFound("rollback_not_found", f"Rollback {rollback_id} not found")
    ch = db.get(ChangeRequest, rel.change_id)
    if rb.status != "REQUESTED":
        raise Conflict("rollback_already_decided", f"Rollback is {rb.status}")
    if rb.requested_by == user.id:
        raise PolicyViolation("separation_of_duties", "Rollback approver must differ from the requester")
    if decision not in ("APPROVE", "REJECT"):
        raise ValidationFailed("invalid_decision", "decision must be APPROVE or REJECT")
    t0 = time.perf_counter()
    if decision == "REJECT":
        rb.status, rb.approved_by, rb.completed_at = "REJECTED", user.id, utcnow()
        transition(db, ch, S.MONITORING, user.id, f"rollback rejected: {comment[:120]}")
        audit.record(db, tenant_id=ch.tenant_id, change_id=ch.id, actor_id=user.id, action="rollback.decide", status="REJECTED",
                     reason=comment[:500], input_refs={"rollback_id": rb.id}, trace_id=ch.trace_id)
        return rollback_dict(rb)
    _deployment_guard()
    rb.approved_by = user.id
    comp = compatibility(db, rel)
    rb.compatibility = comp
    if not comp["compatible"]:
        rb.status, rb.error, rb.completed_at = "FAILED", "compatibility check failed: " + ", ".join(k for k, v in comp["checks"].items() if not v), utcnow()
        rb.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        audit.record(db, tenant_id=ch.tenant_id, change_id=ch.id, actor_id=user.id, action="rollback.execute", status="FAILED",
                     reason=rb.error, input_refs={"rollback_id": rb.id}, trace_id=ch.trace_id)
        message(db, ch, "system", "release", f"Rollback FAILED: {rb.error}. Release unchanged; state remains {ch.status}.")
        return rollback_dict(rb)
    rel.status = "ROLLED_BACK"
    rel.history = rel.history + [{"event": "rollback", "stage_pct": 0, "at": utcnow().isoformat(), "by": user.id,
                                  "restored": rel.previous_model_id, "note": "simulated"}]
    rb.status, rb.completed_at = "EXECUTED", utcnow()
    for al in db.execute(select(Alert).where(Alert.release_id == rel.id)).scalars():
        al.status = "RESOLVED"
    rb.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
    transition(db, ch, S.ROLLED_BACK, user.id, f"rollback to {rel.previous_model_id} executed (simulated)", {"rollback_id": rb.id})
    audit.record(db, tenant_id=ch.tenant_id, change_id=ch.id, actor_id=user.id, action="rollback.execute", status="EXECUTED",
                 reason=f"restored {rel.previous_model_id}", version_refs={"restored_digest": rel.previous_artifact_digest},
                 input_refs={"rollback_id": rb.id, "release_id": rel.id}, trace_id=ch.trace_id)
    message(db, ch, "system", "release", f"Rollback executed (simulated): {rel.previous_model_id} restored on {rel.deployment_target}.")
    return rollback_dict(rb)
