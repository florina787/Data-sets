"""Workflow, gates, approvals, authorization, transitions, resume, deployment and rollback."""

from __future__ import annotations

import pytest

from app.db import kv_get, rows
from app.errors import Conflict, Forbidden, InvalidTransition, LiveModeUnavailable, Unauthorized
from app.graph import flows
from app.services import delivery, system
from app.states import transition_run
from app.tools import deploy, workspace

from conftest import user

BRIEF = delivery.scenario()["brief"]["text"]


def start_run(mode: str = "demo") -> str:
    run_id = delivery.create_run(user("maya.marketing"), "Ontario campaign", BRIEF, mode)
    flows.advance(run_id, "delivery", mode=mode)
    return run_id


def to_release(run_id: str) -> dict:
    delivery.apply_seeded_decisions(run_id, user("maya.marketing"))
    flows.advance(run_id, "delivery")
    delivery.approve_requirement_set(run_id, 1, user("omar.product"))
    result = flows.advance(run_id, "delivery")
    assert result["state"] == "waiting", result
    release_id = flows.snapshot(run_id, "delivery")["values"]["release_id"]
    return delivery.get_release(release_id)


def test_brief_requires_recorded_decisions_before_implementation(platform):
    run_id = start_run()
    assert delivery.get_run(run_id)["status"] == "clarification-needed"
    open_ids = [c["id"] for c in delivery.open_required_clarifications(run_id)]
    assert "Q-ONCE" in open_ids
    once = next(c for c in delivery.list_clarifications(run_id) if c["id"] == "Q-ONCE")
    assert once["evidence"]["policy_gap"] is True
    with pytest.raises(Conflict):
        system.request_implementation(run_id, user("eli.engineer"))
    with pytest.raises(InvalidTransition):
        transition_run(run_id, "implementing", "eli.engineer")
    # Continuing without decisions keeps the run waiting at the gate.
    assert flows.advance(run_id, "delivery")["state"] == "waiting"
    assert not rows("SELECT 1 FROM change_sets WHERE run_id = ?", (run_id,))


def test_brief_that_states_the_scope_does_not_raise_that_ambiguity():
    detected = {a["id"] for a in delivery.detect_ambiguities(
        "Launch a weekend Ontario campaign: buy two eligible FreshSip beverages and receive one free, "
        "once per customer per campaign, while stock lasts.")}
    assert "Q-ONCE" not in detected and "Q-SKU" in detected


def test_full_delivery_flow_produces_failing_then_passing_evidence(platform):
    run_id = start_run()
    release = to_release(run_id)
    test_runs = rows("SELECT revision, status FROM test_runs WHERE run_id = ? ORDER BY started_at", (run_id,))
    assert [t["status"] for t in test_runs] == ["failed", "passed"]
    assert test_runs[1]["revision"] == release["revision"] != test_runs[0]["revision"]
    gates = delivery.evaluate_gates(run_id, release["revision"])
    assert gates["evidence_ready"], gates
    assert release["status"] == "awaiting-approval"
    assert [c["patch_name"] for c in delivery.change_sets(run_id)] == [
        "01-campaign-implementation.patch", "02-free-unit-recompute-fix.patch"]
    # Evidence for an older revision does not qualify the new one.
    old = delivery.evaluate_gates(run_id, test_runs[0]["revision"])
    assert not next(g for g in old["gates"] if g["id"] == "G3")["passed"]


def test_release_approval_permissions_binding_and_duplicates(platform):
    run_id = start_run()
    release = to_release(run_id)
    with pytest.raises(Forbidden):
        delivery.approve_release(release["id"], user("eli.engineer"), release["manifest_hash"])
    with pytest.raises(Conflict):
        delivery.approve_release(release["id"], user("rina.release"), "0" * 64)
    approved = delivery.approve_release(release["id"], user("rina.release"), release["manifest_hash"])
    assert approved["status"] == "approved" and approved["approval"]["revision"] == release["revision"]
    with pytest.raises(Conflict):
        delivery.approve_release(release["id"], user("rina.release"), release["manifest_hash"])
    with pytest.raises(Forbidden):
        delivery.deploy_release(release["id"], user("eli.engineer"))
    rejected = rows("SELECT action FROM audit_events WHERE outcome = 'rejected'")
    assert {"release.approve", "release.deploy"} <= {r["action"] for r in rejected}


def test_new_commit_invalidates_pending_approval(platform):
    run_id = start_run()
    release = to_release(run_id)
    workspace.apply_patch(run_id, workspace.load_fixture_patch("03-inventory-timeout-repair.patch"), "late change")
    head = workspace.head(workspace.workspace_path(run_id))
    from app.services.delivery import record_change_set

    applied = type("A", (), {"revision": head, "base_revision": release["revision"], "patch_hash": "x",
                             "files": [], "diff": ""})()
    record_change_set(run_id, "implementation", "99-late.patch", applied,
                      {"label": "test", "agent": "test", "title": "late", "addresses": []})
    with pytest.raises(Conflict):
        delivery.approve_release(release["id"], user("rina.release"), release["manifest_hash"])
    assert delivery.get_release(release["id"])["status"] == "invalidated"


def test_role_permissions_are_enforced_server_side(platform):
    with pytest.raises(Forbidden):
        delivery.create_run(user("val.viewer"), "x", BRIEF, "demo")
    run_id = start_run()
    with pytest.raises(Forbidden):
        delivery.apply_seeded_decisions(run_id, user("eli.engineer"))
    delivery.apply_seeded_decisions(run_id, user("maya.marketing"))
    with pytest.raises(Forbidden):
        delivery.approve_requirement_set(run_id, 1, user("maya.marketing"))
    from app import auth

    with pytest.raises(Unauthorized):
        auth.user_for_token("not-a-token")
    with pytest.raises(Unauthorized):
        auth.login("rina.release", "wrong")


def test_invalid_transitions_are_rejected_and_recorded(platform):
    run_id = start_run()
    with pytest.raises(InvalidTransition):
        transition_run(run_id, "deployed", "eli.engineer")
    assert rows("SELECT 1 FROM audit_events WHERE action = 'run.transition' AND outcome = 'rejected'")


def test_interrupted_run_resumes_from_checkpoint_without_duplicate_work(platform, monkeypatch):
    run_id = start_run()
    delivery.apply_seeded_decisions(run_id, user("maya.marketing"))
    flows.advance(run_id, "delivery")
    delivery.approve_requirement_set(run_id, 1, user("omar.product"))
    monkeypatch.setenv("FOODCARE_CRASH_ONCE_AT", "implementation_agent")
    with pytest.raises(RuntimeError):
        flows.advance(run_id, "delivery")
    assert delivery.get_run(run_id)["error"]
    flows.reset_graphs()  # simulate a process restart: graphs rebuilt from the SQLite checkpoint
    result = flows.advance(run_id, "delivery")
    assert result["state"] == "waiting"
    patches = [c["patch_name"] for c in delivery.change_sets(run_id)]
    assert patches.count("01-campaign-implementation.patch") == 1


def test_pause_stops_after_current_node_and_continue_resumes(platform):
    run_id = start_run()
    delivery.apply_seeded_decisions(run_id, user("maya.marketing"))
    from app.db import execute

    execute("UPDATE runs SET step_mode = 1 WHERE id = ?", (run_id,))
    first = flows.advance(run_id, "delivery")
    assert first["state"] == "paused" and len(first["steps"]) == 1
    execute("UPDATE runs SET step_mode = 0 WHERE id = ?", (run_id,))
    assert flows.advance(run_id, "delivery")["state"] == "waiting"


def test_live_mode_without_credentials_fails_visibly(platform):
    run_id = delivery.create_run(user("maya.marketing"), "live", BRIEF, "live")
    with pytest.raises(LiveModeUnavailable):
        flows.advance(run_id, "delivery", mode="live")
    assert "ANTHROPIC_API_KEY" in delivery.get_run(run_id)["error"]
    assert not delivery.list_clarifications(run_id)


@pytest.mark.slow
def test_deploy_starts_exact_revision_and_rollback_restores_last_known_good(platform):
    baseline = deploy.deploy("REL-BASELINE", platform["base"], "test", "baseline")
    assert baseline["status"] == "healthy"
    run_id = start_run()
    release = to_release(run_id)
    delivery.approve_release(release["id"], user("rina.release"), release["manifest_hash"])
    deployment = delivery.deploy_release(release["id"], user("rina.release"))
    assert deployment["status"] == "healthy"
    assert deploy.health()["revision"] == release["revision"]
    assert deploy.current_process()["pid"] != baseline["pid"]
    assert kv_get(delivery.LKG_KEY) == "REL-BASELINE"
    with pytest.raises(Forbidden):
        delivery.rollback(user("eli.engineer"), "x")
    rolled = delivery.rollback(user("rina.release"), "test rollback")
    assert rolled["status"] == "healthy" and deploy.health()["revision"] == platform["base"]
    assert delivery.get_release(release["id"])["status"] == "rolled-back"
    assert delivery.get_run(run_id)["status"] == "rolled-back"
