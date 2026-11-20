"""Execution engine: retries, permanent failure, durable resume, timeouts, concurrency, validation."""

from __future__ import annotations

import asyncio

from florome.models import ActionExecution, RemediationPlan
from tests.conftest import H, approve, rca_and_plan, sandbox


def _approved(c):
    _, plan = rca_and_plan(c)
    assert approve(c, plan).status_code == 201
    return plan


def _exec(c, plan):
    return c.post("/api/v1/executions", json={"plan_id": plan["id"]}, headers=H("operator"))


def test_transient_failure_is_retried(client, db):
    plan = _approved(client)
    sandbox(client).world.s.fail_next["rerun_job"] = [True, True]  # two transient failures, third attempt succeeds
    out = _exec(client, plan).json()
    assert out["status"] == "succeeded"
    row = db.query(ActionExecution).filter_by(plan_id=plan["id"], action_id="rerun_job").one()
    assert row.attempts == 3


def test_permanent_failure_stops_and_resume_skips_completed_steps(client, db):
    c = client
    plan = _approved(c)
    sb = sandbox(c)
    sb.world.s.fail_next["rerun_job"] = [False]
    out = _exec(c, plan).json()
    assert out["status"] == "failed" and out["current_step"] == 2
    assert [s["status"] for s in out["steps"]][:3] == ["succeeded", "succeeded", "failed"]
    assert c.get(f"/api/v1/incidents/{plan['incident_id']}", headers=H("viewer")).json()["status"] == "remediating"
    calls_before = list(sb.world.s.calls)
    out = _exec(c, plan).json()  # resume: approval still valid and bound to the same hash
    assert out["status"] == "succeeded"
    new_calls = sb.world.s.calls[len(calls_before):]
    assert ("rollback_deployment", sb.world.s.calls[0][1]) not in new_calls  # completed steps were not re-run
    assert [a for a, _ in new_calls] == ["rerun_job", "refresh_cache", "create_ticket"]
    assert db.query(ActionExecution).filter_by(plan_id=plan["id"]).count() == 5  # one row per step, retried in place


def test_timeout_marks_step_timed_out(client, db):
    plan = _approved(client)
    sb = sandbox(client)
    sb.world.s.delay["rollback_deployment"] = 5.0  # action timeout in tests is 2s
    client.ctx.settings.action_max_attempts = 1
    out = _exec(client, plan).json()
    assert out["status"] == "failed" and "Timed out" in out["last_error"]
    assert db.query(ActionExecution).filter_by(plan_id=plan["id"]).one().status == "timed_out"


def test_concurrent_execution_is_refused(client, db):
    plan = _approved(client)
    p = db.get(RemediationPlan, plan["id"])
    p.status = "executing"
    db.commit()
    assert _exec(client, plan).status_code == 409


def test_connector_idempotency_replays_previous_result():
    from florome.connectors.sandbox import LAMBDA, SandboxConnector

    conn = SandboxConnector()
    first = asyncio.run(conn.execute_action("rollback_deployment", LAMBDA, {"to_version": "v2.13.4"}, "k1"))
    second = asyncio.run(conn.execute_action("rollback_deployment", LAMBDA, {"to_version": "v2.13.4"}, "k1"))
    assert first.success and second.success and second.idempotent_replay and not first.idempotent_replay
    assert len(conn.world.s.calls) == 1


def test_out_of_order_recovery_fails_honestly():
    from florome.connectors.sandbox import JOB, SandboxConnector

    conn = SandboxConnector()
    r = asyncio.run(conn.execute_action("rerun_job", JOB, {}, "k"))
    assert not r.success and "data quality" in r.message
    assert not asyncio.run(conn.verify(JOB)).healthy


def test_validation_fails_when_system_not_recovered(client, db):
    from florome.actions.service import validate

    _, plan = rca_and_plan(client)
    p = db.get(RemediationPlan, plan["id"])
    v = asyncio.run(validate(db, client.ctx, p))
    assert v.passed is False and any(not ch["passed"] for ch in v.checks)
