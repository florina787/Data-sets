"""Evaluation job: paired baseline-vs-candidate comparison on eligible held-out samples, metric
persistence, deterministic gate evaluation and lifecycle transition."""
from __future__ import annotations

import time
from collections import defaultdict

from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.adapters.prediction import get_prediction_adapter
from app.db import SessionLocal
from app.errors import DomainError
from app.evaluation import metrics as M
from app.lifecycle.state_machine import S
from app.models.orm import (ChangeRequest, Clarification, DatasetVersion, EvaluationRun,
                            EvidenceReference, GateDecision, MetricResult, ModelVersion, Prediction, RequirementVersion,
                            User, new_id, utcnow)
from app.policies import controls as C
from app.policies import engine as E
from app.retrieval.knowledge import get_kb
from app.security.rbac import require
from app.services import audit, fixtures
from app.services.lifecycle import invalidate_bindings, message, run_agents, transition
from app.services.repo import get_change

MAX_ATTEMPTS = 3
REQUIRED_EVIDENCE = ["POL-REL-005", "PROT-EVAL-008", "DS-CARD-010", "SPEC-SHADE-001"]


class Cancelled(Exception):
    pass


def request_evaluation(db: Session, user: User, change_id: str) -> EvaluationRun:
    require(user, "evaluation.run")
    ch = get_change(db, user.tenant_id, change_id)
    if ch.status not in (S.DEVELOPMENT.value, S.EVALUATION_FAILED.value, S.EVALUATION_INCONCLUSIVE.value, S.REVIEW_REQUIRED.value):
        from app.errors import PolicyViolation
        raise PolicyViolation("illegal_state", f"Evaluation cannot be requested in state {ch.status}")
    return _create_run(db, user, ch)


def _create_run(db: Session, user: User, ch: ChangeRequest) -> EvaluationRun:
    from app.errors import PolicyViolation
    if not ch.candidate_model_id or not ch.evaluation_config_id:
        raise PolicyViolation("no_candidate", "Register a candidate before requesting evaluation")
    prior = db.execute(select(EvaluationRun).where(EvaluationRun.change_id == ch.id)).scalars().all()
    if any(r.status in ("QUEUED", "RUNNING") for r in prior):
        raise PolicyViolation("evaluation_in_progress", "An evaluation is already queued or running for this change")
    pol, _ = fixtures.policy()
    run = EvaluationRun(id=new_id("EVR"), change_id=ch.id, tenant_id=ch.tenant_id, status="QUEUED",
                        baseline_model_id=ch.baseline_model_id, candidate_model_id=ch.candidate_model_id,
                        code_revision_id=ch.code_revision_id, dataset_snapshot_id=ch.dataset_snapshot_id,
                        evaluation_config_id=ch.evaluation_config_id, policy_version=pol["policy_version"],
                        requirement_version_id=ch.current_requirement_version_id, requested_by=user.id,
                        test_set_evaluation_index=len([r for r in prior if r.status == "SUCCEEDED"]) + 1)
    db.add(run)
    if ch.status == S.REVIEW_REQUIRED.value:
        invalidate_bindings(db, ch, "re-evaluation requested", user.id)
    transition(db, ch, S.EVALUATING, user.id, f"evaluation {run.id} queued", {"run_id": run.id})
    ch.latest_evaluation_run_id = run.id
    audit.record(db, tenant_id=ch.tenant_id, change_id=ch.id, actor_id=user.id, action="evaluation.request", status="QUEUED",
                 reason=f"{ch.candidate_model_id} vs {ch.baseline_model_id}",
                 version_refs={"config": ch.evaluation_config_id, "dataset": ch.dataset_snapshot_id}, trace_id=ch.trace_id)
    message(db, ch, "system", "evaluation", f"Evaluation {run.id} queued (background job). Test-split evaluation #{run.test_set_evaluation_index} for this change.")
    return run


def cancel(db: Session, user: User, run_id: str) -> EvaluationRun:
    from app.services.repo import get_run
    require(user, "evaluation.cancel")
    run = get_run(db, user.tenant_id, run_id)
    if run.status not in ("QUEUED", "RUNNING"):
        from app.errors import PolicyViolation
        raise PolicyViolation("not_cancellable", f"Run is {run.status}")
    run.cancel_requested = True
    audit.record(db, tenant_id=run.tenant_id, change_id=run.change_id, actor_id=user.id, action="evaluation.cancel_requested",
                 status="OK", input_refs={"run_id": run.id})
    return run


def _check_cancel(db: Session, run: EvaluationRun) -> None:
    db.refresh(run, ["cancel_requested"])
    if run.cancel_requested:
        raise Cancelled()


def execute(run_id: str) -> None:
    """Entry point for the job worker. Owns its session; bounded retries for transient DB errors."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        db = SessionLocal()
        try:
            _execute(db, run_id)
            return
        except OperationalError as exc:  # transient (e.g. database locked): retry with backoff
            db.rollback()
            if attempt == MAX_ATTEMPTS:
                _fail(run_id, {"category": "computation", "code": "db_operational_error", "message": str(exc)[:300]})
                return
            time.sleep(0.2 * 2 ** attempt)
        except Cancelled:
            db.rollback()
            _finish_cancelled(run_id)
            return
        except Exception as exc:  # computation failure: not retried (deterministic)
            db.rollback()
            _fail(run_id, {"category": "computation", "code": type(exc).__name__, "message": str(exc)[:500]})
            return
        finally:
            db.close()


def _fail(run_id: str, err: dict) -> None:
    db = SessionLocal()
    try:
        run = db.get(EvaluationRun, run_id)
        run.status, run.error, run.finished_at = "FAILED", err, utcnow()
        ch = db.get(ChangeRequest, run.change_id)
        if ch.status == S.EVALUATING.value:
            transition(db, ch, S.DEVELOPMENT, "system:evaluation", f"evaluation computation failed: {err['message'][:200]}")
        audit.record(db, tenant_id=run.tenant_id, change_id=run.change_id, actor_id="system:evaluation", action="evaluation.run",
                     status="FAILED", reason=f"[{err['category']}] {err['message'][:400]}", input_refs={"run_id": run.id})
        message(db, ch, "system", "evaluation", f"Evaluation {run.id} FAILED (computation error, not a policy decision): {err['message'][:200]}")
        db.commit()
    finally:
        db.close()


def _finish_cancelled(run_id: str) -> None:
    db = SessionLocal()
    try:
        run = db.get(EvaluationRun, run_id)
        run.status, run.finished_at = "CANCELLED", utcnow()
        db.execute(delete(Prediction).where(Prediction.run_id == run_id))
        ch = db.get(ChangeRequest, run.change_id)
        if ch.status == S.EVALUATING.value:
            transition(db, ch, S.DEVELOPMENT, "system:evaluation", f"evaluation {run_id} cancelled")
        audit.record(db, tenant_id=run.tenant_id, change_id=run.change_id, actor_id="system:evaluation", action="evaluation.run",
                     status="CANCELLED", input_refs={"run_id": run.id})
        db.commit()
    finally:
        db.close()


def _execute(db: Session, run_id: str) -> None:
    run = db.get(EvaluationRun, run_id)
    if run is None or run.status not in ("QUEUED", "RUNNING"):
        return
    run.status, run.attempts, run.started_at = "RUNNING", run.attempts + 1, utcnow()
    db.commit()
    t0 = time.perf_counter()
    _check_cancel(db, run)
    ch = db.get(ChangeRequest, run.change_id)
    config, cfg_digest = fixtures.eval_config(run.evaluation_config_id)
    policy, pol_digest = fixtures.policy()
    run.evaluation_config_digest = cfg_digest

    # --- artifact and dataset digests (registered vs recomputed from files) ---
    artifact_check = {}
    for role, mid in (("baseline", run.baseline_model_id), ("candidate", run.candidate_model_id)):
        mv = db.get(ModelVersion, mid)
        artifact_check[f"{role}:{mid}"] = {"registered": mv.artifact_digest, "computed": fixtures.compute_artifact_digest(mid)}
    dsv = db.get(DatasetVersion, run.dataset_snapshot_id)
    artifact_check[f"dataset:{dsv.id}"] = {"registered": dsv.digest, "computed": fixtures.dataset_digest()}
    run.baseline_artifact_digest = artifact_check[f"baseline:{run.baseline_model_id}"]["computed"]
    run.candidate_artifact_digest = artifact_check[f"candidate:{run.candidate_model_id}"]["computed"]
    run.dataset_digest = artifact_check[f"dataset:{dsv.id}"]["computed"]

    # --- eligibility (dataset permission service) ---
    from app.services.datasets import eligible_samples
    el = eligible_samples(db, run.dataset_snapshot_id, split=config["split"], purpose="evaluation")
    recs = el["eligible"]
    ids = [r.sample_id for r in recs]
    adapter = get_prediction_adapter()
    preds = {"baseline": adapter.predict_batch(run.baseline_model_id, ids),
             "candidate": adapter.predict_batch(run.candidate_model_id, ids)}
    _check_cancel(db, run)
    db.execute(delete(Prediction).where(Prediction.run_id == run.id))
    db.bulk_save_objects([Prediction(run_id=run.id, model_id=mid, sample_id=sid, top3=preds[role][sid]["top3"],
                                     abstained=preds[role][sid]["abstained"])
                          for role, mid in (("baseline", run.baseline_model_id), ("candidate", run.candidate_model_id)) for sid in ids])

    # --- metrics per cell ---
    by_cell: dict[str, list] = defaultdict(list)
    for r in recs:
        by_cell[f"{r.tone_stratum}|{r.lighting_category}"].append(r)
    required = [f"{s}|{l}" for s in config["strata"] for l in config["lighting"]]
    boot = config["bootstrap"]
    cells, integrity_issues = {}, []

    def block(rs: list, seed_offset: int) -> dict:
        exp = [r.expected_shade_id for r in rs]
        out = {}
        ind = {}
        for role in ("baseline", "candidate"):
            pl = [preds[role][r.sample_id] for r in rs]
            ind[role] = M.indicators(exp, pl)
            out[role] = M.summarize(ind[role])
            out[f"{role}_confusion"] = M.family_confusion(exp, pl)
        out["delta"] = M.delta(out["baseline"], out["candidate"])
        out["delta_ci95_pp"] = M.paired_bootstrap_delta(ind["baseline"]["top1"], ind["candidate"]["top1"],
                                                        boot["resamples"], boot["seed"] + seed_offset, boot["confidence"])
        if out["baseline"]["n_eligible"] != len(rs) or out["candidate"]["n_eligible"] != len(rs):
            integrity_issues.append("prediction count mismatch")
        return out

    for i, c in enumerate(required):
        if by_cell.get(c):
            cells[c] = block(by_cell[c], i)
    overall_block = block(recs, 99)
    pred_count = len(ids) * 2
    integrity = {"ok": not integrity_issues and all(len(preds[k]) == len(ids) for k in preds),
                 "observed": f"{len(ids)} eligible samples × 2 models = {pred_count} prediction records; abstentions in denominator: "
                             f"baseline {overall_block['baseline']['abstained']}, candidate {overall_block['candidate']['abstained']}"}
    _check_cancel(db, run)

    # --- requirement, evidence, controls ---
    rv = db.get(RequirementVersion, run.requirement_version_id) if run.requirement_version_id else None
    unresolved = len(db.execute(select(Clarification).where(Clarification.change_id == ch.id, Clarification.required.is_(True),
                                                            Clarification.answer.is_(None))).scalars().all())
    thresholds = E.effective_thresholds(policy, (rv.scope if rv else {}) or {})
    kb = get_kb()
    evrefs = db.execute(select(EvidenceReference).where(EvidenceReference.change_id == ch.id)).scalars().all()
    usable = {}
    invalid = []
    for e in evrefs:
        v = kb.validate_citation({"source_id": e.source_id, "source_version": e.source_version, "section": e.section, "excerpt": e.excerpt})
        if e.validation_status == "VALID":
            if v["status"] != "VALID":
                invalid.append(f"{e.source_id} v{e.source_version} {e.section} ({v['status']})")
            else:
                usable.setdefault(e.source_id, []).append({"source_id": e.source_id, "source_version": e.source_version, "section": e.section})
    evidence_check = {"missing": [d for d in REQUIRED_EVIDENCE if d not in usable], "invalid": invalid,
                      "valid": sum(len(v) for v in usable.values()), "refs": [v[0] for v in usable.values()]}
    state_probe = {"change_id": ch.id, "evidence_refs": [e.source_id for e in evrefs]}
    ctrl = C.run_controls(db, tenant_id=ch.tenant_id, evaluated=recs, workflow_state=state_probe)

    gates = E.evaluation_gates(policy=policy, thresholds=thresholds, cells=cells, required_cells=required,
                               target_cell=config["target_cell"], controls=ctrl, unresolved_required=unresolved,
                               requirement_approved=bool(rv and rv.status == "APPROVED"), evidence_check=evidence_check,
                               artifact_check=artifact_check, config_present=True, integrity=integrity)
    outcome = E.overall(gates)

    for scope, blk in [("overall", overall_block), *cells.items()]:
        for role in ("baseline", "candidate"):
            db.add(MetricResult(run_id=run.id, scope=scope, model_role=role,
                                metrics={**blk[role], "confusion_family": blk[f"{role}_confusion"]}))
        db.add(MetricResult(run_id=run.id, scope=scope, model_role="delta", metrics={**blk["delta"], "ci95_pp": blk["delta_ci95_pp"]}))
    for g in gates:
        db.add(GateDecision(change_id=ch.id, run_id=run.id, context="evaluation", gate_id=g.gate_id, rule=g.rule, observed=g.observed,
                            status=g.status, owner_role=g.owner_role, evidence=g.evidence, policy_version=policy["policy_version"]))
    run.summary = {
        "overall": overall_block, "cells": cells, "required_cells": required, "target_cell": config["target_cell"],
        "gates": [g.dict() for g in gates], "controls": ctrl, "thresholds": thresholds,
        "exclusions": el["excluded_by_reason"], "declared_eligible_overridden": el["declared_eligible_overridden"],
        "split_total": el["split_total"], "eligible_total": len(ids), "prediction_mode": adapter.mode,
        "config": config, "policy_version": policy["policy_version"], "policy_digest": pol_digest,
        "artifact_check": artifact_check, "test_set_evaluation_index": run.test_set_evaluation_index,
        "uncertainty_method": f"Wilson 95% for proportions; paired percentile bootstrap ({boot['resamples']} resamples, seed {boot['seed']}) for cell deltas",
    }
    run.outcome = outcome
    run.status, run.finished_at = "SUCCEEDED", utcnow()
    run.duration_ms = round((time.perf_counter() - t0) * 1000, 1)
    target = {E.FAIL: S.EVALUATION_FAILED, E.INCONCLUSIVE: S.EVALUATION_INCONCLUSIVE, E.PASS: S.REVIEW_REQUIRED}[outcome]
    transition(db, ch, target, "system:policy-engine", f"evaluation {run.id} outcome {outcome}", {"run_id": run.id})
    audit.record(db, tenant_id=ch.tenant_id, change_id=ch.id, actor_id="system:policy-engine", action="evaluation.gates",
                 status=outcome, reason="; ".join(f"{g.gate_id}={g.status}" for g in gates),
                 version_refs={"policy": policy["policy_version"], "config": run.evaluation_config_id,
                               "candidate_digest": run.candidate_artifact_digest, "dataset_digest": run.dataset_digest},
                 input_refs={"run_id": run.id}, trace_id=ch.trace_id)
    db.commit()
    requester = db.get(User, run.requested_by)
    try:
        run_agents(db, ch, requester, ["evaluation", "governance"],
                   interrupt={"awaiting": "reviews" if outcome == E.PASS else "new_candidate"})
    except DomainError:
        pass  # agent failure is checkpointed and resumable; the computed outcome stands


def recover_jobs() -> list[str]:
    """On restart, re-queue runs left QUEUED/RUNNING (bounded by MAX_ATTEMPTS)."""
    db = SessionLocal()
    out = []
    try:
        for run in db.execute(select(EvaluationRun).where(EvaluationRun.status.in_(["QUEUED", "RUNNING"]))).scalars():
            if run.attempts >= MAX_ATTEMPTS:
                run.status, run.error = "FAILED", {"category": "computation", "code": "max_attempts", "message": "exceeded retry limit after restarts"}
            else:
                run.status = "QUEUED"
                out.append(run.id)
        db.commit()
    finally:
        db.close()
    return out
