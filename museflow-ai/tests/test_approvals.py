"""Human-in-the-loop: interrupts, decisions, checkpoint restoration and execution guards."""
from __future__ import annotations

import pytest

from services.tool_registry import ToolEnv, ToolNotAllowedError
from services.validation import ValidationError
from tests.conftest import nodes


def test_approve_executes_simulated_action_once(engine):
    run = engine.start("email_followup")
    assert engine.stores.outbox == []  # nothing happens before approval
    run = engine.resume(run.run_id, "approved", "looks lovely")
    assert run.status == "completed"
    assert len(engine.stores.outbox) == 1 and engine.stores.outbox[0]["simulated"] is True
    assert run.values["approval"]["note"] == "looks lovely"


@pytest.mark.parametrize("decision", ["rejected", "cancelled"])
def test_reject_or_cancel_executes_nothing(engine, decision):
    run = engine.resume(engine.start("browser", {"task": "booking"}).run_id, decision)
    assert run.status == decision
    assert engine.stores.bookings == []
    assert "simulate_action" not in nodes(run)
    assert nodes(run)[-3:] == ["approval", "audit", "respond"]
    assert any(e["kind"] == f"human.{decision}" for e in engine.audit.entries(run.run_id))


def test_resume_validations(engine):
    run = engine.start("email_followup")
    with pytest.raises(ValidationError):
        engine.resume(run.run_id, "maybe")
    engine.resume(run.run_id, "approved")
    with pytest.raises(ValidationError, match="not awaiting"):
        engine.resume(run.run_id, "approved")
    with pytest.raises(KeyError):
        engine.resume("R999-nope", "approved")


def test_resume_comes_from_checkpoint_not_restart(engine):
    run = engine.start("document_edit")
    assert engine.checkpoints.checkpoint_count(run.run_id) > 0
    engine.rebuild_graph()  # brand-new compiled graph object, same session checkpointer
    run = engine.resume(run.run_id, "approved")
    assert run.status == "completed"
    assert sum(1 for e in run.trace if e["node"] == "intent_router") == 1  # not re-run
    assert sum(1 for e in run.trace if e["node"] == "document" and e["status"] == "completed") == 1
    assert "meeting_notes" in engine.stores.document_edits


def test_multiple_pending_runs_resume_independently(engine):
    first = engine.start("email_followup")
    second = engine.start("schedule_meeting")
    assert {r.run_id for r in engine.pending()} == {first.run_id, second.run_id}
    engine.resume(second.run_id, "approved")
    assert engine.runs[first.run_id].status == "awaiting_approval"
    assert len(engine.stores.calendar_events) == 1 and engine.stores.outbox == []


def test_consequential_tools_refuse_without_approval(engine):
    env = ToolEnv(engine.stores, engine.today)
    with pytest.raises(ToolNotAllowedError):
        engine.tools.execute("email.simulate_send", {"to": "a@example.com", "subject": "s", "body": "b"}, env)
    with pytest.raises(ToolNotAllowedError):
        engine.tools.execute("shell.exec", {"cmd": "ls"}, env, approved=True)
    assert engine.stores.outbox == []


def test_every_consequential_tool_requires_approval_in_governance(engine):
    from agents.governance import evaluate

    for name, spec in engine.tools.specs.items():
        args = {"to": "x@example.com", "body": "hi"} if name == "email.simulate_send" else {}
        results = {d["result"] for d in evaluate({"tool": name, "args": args}, engine.context())}
        assert ("require_approval" in results) == spec.consequential, name


def test_governance_denies_non_synthetic_recipient(engine):
    run = engine.start("email_followup", {"custom_body": "Hello there, friend."})
    assert run.status == "awaiting_approval"
    from agents.governance import evaluate

    decisions = evaluate({"tool": "email.simulate_send", "args": {"to": "someone@gmail.com", "body": "hi"}}, engine.context())
    assert decisions[-1]["result"] == "deny"


def test_approval_states_cover_spec(engine):
    states = set()
    for decision in ("approved", "rejected", "cancelled"):
        run = engine.start("schedule_meeting")
        states.add(run.status)
        states.add(engine.resume(run.run_id, decision).status)
    assert states == {"awaiting_approval", "completed", "rejected", "cancelled"}
