"""Promotion is blocked by insufficient evidence, stale/replayed approvals, mismatched artifacts,
duplicate deployment, rejection and failed rollback."""
import json
from datetime import timedelta

from sqlalchemy import select

from tests.conftest import H


def _db():
    from app.db import SessionLocal
    return SessionLocal()


def test_insufficient_samples_inconclusive_via_stricter_criteria(journey):
    c = journey.c
    for cl in journey.get()["clarifications"]:
        body = {"key": cl["key"], "use_suggested": True}
        if cl["key"] == "release_evidence":
            body = {"key": cl["key"], "answer": "Need at least 150 eligible samples per cell.",
                    "structured": {"min_samples_per_cell": 150, "privacy_tests": "all_pass", "authorization_tests": "all_pass"}}
        journey.ok(c.post("/api/changes/BR-101/clarifications", headers=H("u-po"), json=body))
    journey.ok(c.post("/api/changes/BR-101/requirements/approve", headers=H("u-po")))
    journey.ok(c.post("/api/changes/BR-101/investigate", headers=H("u-ml-eng")))
    journey.ok(c.post("/api/changes/BR-101/impact/accept", headers=H("u-po")))
    journey.candidate("shade-matcher-v2.4.0-rc2")
    run = journey.evaluate()
    g = {x["gate_id"]: x["status"] for x in run["summary"]["gates"]}
    assert g["G-SAMPLES"] == "INCONCLUSIVE" and run["outcome"] == "INCONCLUSIVE"
    assert journey.get()["change"]["status"] == "EVALUATION_INCONCLUSIVE"


def test_artifact_tampering_fails_evaluation(journey, env):
    journey.to_development()
    journey.candidate("shade-matcher-v2.4.0-rc2")
    p = env["data"] / "synthetic" / "predictions" / "shade-matcher-v2.4.0-rc2.json"
    d = json.loads(p.read_text())
    first = next(iter(d["predictions"]))
    d["predictions"][first]["abstained"] = not d["predictions"][first]["abstained"]
    d["predictions"][first]["top3"] = d["predictions"][first]["top3"] or ["SH-01", "SH-02", "SH-03"]
    p.write_text(json.dumps(d))
    from app.services import fixtures
    fixtures.clear_caches()
    run = journey.evaluate()
    g = {x["gate_id"]: x for x in run["summary"]["gates"]}
    assert g["G-ARTIFACT"]["status"] == "FAIL" and run["outcome"] == "FAIL"


def test_artifact_mismatch_after_approval_blocks_deploy(journey, env):
    journey.to_release_approved()
    p = env["data"] / "synthetic" / "predictions" / "shade-matcher-v2.4.0-rc2.json"
    p.write_text(p.read_text().replace('"SH-01"', '"SH-02"', 1))
    from app.services import fixtures
    fixtures.clear_caches()
    r = journey.release()
    assert r.status_code == 409 and r.json()["error"]["code"] == "revalidation_failed"
    assert any("binding mismatch" in b or "STALE" in b for b in r.json()["error"]["details"]["blockers"])
    assert journey.get()["change"]["status"] == "REVIEW_REQUIRED"


def test_expired_approval_blocks_deploy(journey):
    journey.to_release_approved()
    from app.models.orm import Approval, utcnow
    db = _db()
    a = db.execute(select(Approval).where(Approval.kind == "release")).scalar_one()
    a.expires_at = utcnow() - timedelta(minutes=1)
    db.commit(); db.close()
    r = journey.release()
    assert r.status_code == 409 and any("expired" in b for b in r.json()["error"]["details"]["blockers"])


def test_policy_change_invalidates_approval(journey, env):
    journey.to_release_approved()
    p = env["data"].parent / "policy_override"
    p.mkdir()
    from app.config import ROOT
    src = json.loads((ROOT / "policies" / "release-policy-v2.1.json").read_text())
    src["policy_version"] = "2.2-demo"
    (p / "release-policy-v2.1.json").write_text(json.dumps(src))
    env["monkeypatch"].setenv("POLICY_DIR", str(p))
    from app.config import reset_settings
    reset_settings()
    r = journey.release()
    assert r.status_code == 409
    assert any("policy" in b for b in r.json()["error"]["details"]["blockers"])


def test_new_candidate_invalidates_reviews_and_approval(journey):
    journey.to_release_approved()
    # state is RELEASE_APPROVED; registering is not allowed there
    r = journey.c.post("/api/changes/BR-101/candidates", headers=H("u-cv-eng"), json={"model_id": "shade-matcher-v2.4.0-rc1"})
    assert r.status_code == 409


def test_replay_and_duplicate_deployment(journey):
    journey.to_release_approved()
    first = journey.ok(journey.release("same-key"), 201)
    again = journey.ok(journey.release("same-key"), 201)
    assert again["idempotent_replay"] and again["release"]["id"] == first["release"]["id"]
    dup = journey.release("other-key")
    assert dup.status_code == 409  # change is already CANARY; approval consumed
    from app.models.orm import Approval, Release
    db = _db()
    assert len(db.execute(select(Release)).scalars().all()) == 1
    a = db.execute(select(Approval).where(Approval.kind == "release")).scalar_one()
    assert a.consumed_at is not None
    db.close()


def test_idempotency_key_required_and_reuse_with_different_body(journey):
    journey.to_release_approved()
    r = journey.c.post("/api/changes/BR-101/releases", headers=H("u-release"), json={})
    assert r.status_code == 422 and r.json()["error"]["code"] == "idempotency_key_required"
    journey.ok(journey.release("k"), 201)
    r = journey.c.post("/api/changes/BR-101/releases", headers=H("u-release", **{"Idempotency-Key": "k"}), json={"approval_id": "AP-x"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "idempotency_key_reused"


def test_rejected_release_cannot_deploy(journey):
    journey.to_review_required()
    journey.reviews()
    rej = journey.ok(journey.c.post("/api/changes/BR-101/release-approvals", headers=H("u-release"),
                                    json={"decision": "REJECTED", "comment": "need more DEV-T3 data"}), 201)
    assert rej["decision"] == "REJECTED"
    assert journey.get()["change"]["status"] == "REVIEW_REQUIRED"
    assert journey.release().status_code == 409


def test_release_approval_requires_reviews(journey):
    journey.to_review_required()
    r = journey.c.post("/api/changes/BR-101/release-approvals", headers=H("u-release"), json={"decision": "APPROVED"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "release_gates_blocking"
    assert any("G-REVIEWS" in b for b in r.json()["error"]["details"]["blockers"])


def test_code_review_by_author_rejected(journey):
    journey.to_development()
    journey.candidate("shade-matcher-v2.4.0-rc2")
    # u-cv-eng authored the revision and holds review.code permission; separation of duties still applies
    r = journey.c.post("/api/changes/BR-101/reviews", headers=H("u-cv-eng"), json={"kind": "code", "decision": "APPROVE"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "separation_of_duties"


def test_reevaluation_invalidates_prior_reviews(journey):
    journey.to_review_required()
    journey.reviews()
    journey.evaluate()  # re-evaluation from REVIEW_REQUIRED
    rs = journey.get()["review_status"]["status"]
    assert rs["domain"] in ("PENDING", "STALE") and rs["privacy"] in ("PENDING", "STALE")


def test_failed_rollback_keeps_state(journey):
    journey.to_release_approved()
    rel = journey.ok(journey.release(), 201)["release"]
    from app.models.orm import ModelVersion
    db = _db()
    db.get(ModelVersion, "shade-matcher-v2.3.0").catalogue_version = "CAT-2025.4"
    db.commit(); db.close()
    rb = journey.ok(journey.c.post(f"/api/releases/{rel['id']}/rollback-requests", headers=H("u-ops", **{"Idempotency-Key": "r"}),
                                   json={"reason": "test"}), 201)["rollback"]
    out = journey.ok(journey.c.post(f"/api/rollbacks/{rb['id']}/decision", headers=H("u-release"), json={"decision": "APPROVE"}))
    assert out["status"] == "FAILED" and "catalogue_compatible" in out["error"]
    assert journey.get()["change"]["status"] == "ROLLBACK_RECOMMENDED"
    assert journey.get()["releases"][0]["status"] == "CANARY"


def test_rollback_rejection_returns_to_monitoring(journey):
    journey.to_release_approved()
    rel = journey.ok(journey.release(), 201)["release"]
    rb = journey.ok(journey.c.post(f"/api/releases/{rel['id']}/rollback-requests", headers=H("u-ops", **{"Idempotency-Key": "r"}),
                                   json={"reason": "check"}), 201)["rollback"]
    journey.ok(journey.c.post(f"/api/rollbacks/{rb['id']}/decision", headers=H("u-release"), json={"decision": "REJECT"}))
    assert journey.get()["change"]["status"] == "MONITORING"


def test_promotion_blocked_without_window_and_with_open_alert(journey):
    journey.to_release_approved()
    rel = journey.ok(journey.release(), 201)["release"]
    r = journey.c.post(f"/api/releases/{rel['id']}/promote", headers=H("u-release"))
    assert r.status_code == 409 and r.json()["error"]["code"] == "insufficient_monitoring"


def test_checkpoint_resume_after_node_failure(journey):
    journey.approve_requirements()
    from app.workflows import graph
    graph.FAULTS.add("impact")
    r = journey.c.post("/api/changes/BR-101/investigate", headers=H("u-ml-eng"))
    assert r.status_code == 500 and r.json()["error"]["category"] == "computation"
    thread = r.json()["error"]["details"]["thread_id"]
    assert journey.get()["change"]["status"] == "REQUIREMENTS_APPROVED"
    graph.FAULTS.clear()
    out = journey.ok(journey.c.post("/api/changes/BR-101/workflow/resume", headers=H("u-ml-eng"), json={"thread_id": thread}))
    assert out["completed"] == ["evidence", "impact"]
    from app.models.orm import AgentInvocation
    db = _db()
    inv = db.execute(select(AgentInvocation).where(AgentInvocation.thread_id == thread)).scalars().all()
    assert [i.agent for i in inv if i.status != "ERROR"].count("evidence") == 1  # evidence not re-run
    db.close()


def test_background_job_and_cancel_and_recovery(journey, env):
    journey.to_development()
    journey.candidate("shade-matcher-v2.4.0-rc2")
    env["monkeypatch"].setenv("EVAL_EXECUTION", "background")
    from app.config import reset_settings
    reset_settings()
    from app.evaluation import jobs, runner
    from app.models.orm import EvaluationRun
    # queue without executing, then simulate a restart recovering it
    monkey = env["monkeypatch"]
    monkey.setattr(jobs, "submit", lambda rid: None)
    run = journey.ok(journey.c.post("/api/changes/BR-101/evaluations", headers=H("u-ml-eng")), 202)
    assert run["status"] == "QUEUED"
    assert runner.recover_jobs() == [run["id"]]
    runner.execute(run["id"])
    got = journey.ok(journey.c.get(f"/api/evaluations/{run['id']}", headers=H("u-qa")))
    assert got["status"] == "SUCCEEDED" and got["outcome"] == "PASS"
    # cancellation path
    journey.candidate("shade-matcher-v2.4.0-rc1")
    run2 = journey.ok(journey.c.post("/api/changes/BR-101/evaluations", headers=H("u-ml-eng")), 202)
    journey.ok(journey.c.post(f"/api/evaluations/{run2['id']}/cancel", headers=H("u-qa")))
    runner.execute(run2["id"])
    got2 = journey.ok(journey.c.get(f"/api/evaluations/{run2['id']}", headers=H("u-qa")))
    assert got2["status"] == "CANCELLED"
    assert journey.get()["change"]["status"] == "DEVELOPMENT"


def test_real_thread_pool_job_completes(journey, env):
    journey.to_development()
    journey.candidate("shade-matcher-v2.4.0-rc2")
    env["monkeypatch"].setenv("EVAL_EXECUTION", "background")
    from app.config import reset_settings
    reset_settings()
    from app.evaluation import jobs
    run = journey.ok(journey.c.post("/api/changes/BR-101/evaluations", headers=H("u-ml-eng")), 202)
    jobs.wait(run["id"], timeout=120)
    got = journey.ok(journey.c.get(f"/api/evaluations/{run['id']}", headers=H("u-qa")))
    assert got["status"] == "SUCCEEDED"
