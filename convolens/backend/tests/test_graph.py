import json

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.db import session_scope
from app.graph.runner import RunError
from app.llm.provider import set_model_override
from app.models.orm import Action, Run
from tests.fakes import ScriptedModel


def _run(runner, ds, q, filters=None, mode="demo", session="ses_a"):
    evs = list(runner.start(session_id=session, question=q, dataset_id=ds, mode=mode, page="overview", filters=filters))
    return evs[-1], evs


def test_follow_up_uses_active_filter_scope(runner, demo_ids):
    ans, evs = _run(runner, demo_ids["demo"], "Why is this happening?", {"topics": ["billing_refunds"]})
    resp = ans["response"]
    assert resp["question_type"] == "investigation"
    assert resp["scope"]["filters"]["topics"] == ["billing_refunds"]
    assert any("active scope" in n for n in resp["scope"]["notes"])
    tool_events = [e for e in evs if e["type"] == "tool" and e["status"] == "ok"]
    assert all("Billing & refunds" in (e.get("filters") or "Billing & refunds") for e in tool_events)
    assert "not verified causes" in resp["text"] or "not causes" in resp["text"]
    for section in ("**Finding**", "**Scope and denominator**", "**Supporting evidence**", "**Limitations**", "**Proposed next action**"):
        assert section in resp["text"]


def test_question_topic_does_not_override_explicit_scope(runner, demo_ids):
    ans, _ = _run(runner, demo_ids["demo"], "What about delivery?", {"topics": ["billing_refunds"]})
    assert ans["response"]["scope"]["filters"]["topics"] == ["billing_refunds"]


def test_csat_is_unsupported_without_tools(runner, demo_ids):
    ans, evs = _run(runner, demo_ids["demo"], "What is our CSAT score for refunds?")
    assert ans["response"]["kind"] == "unsupported"
    assert "CSAT" in ans["response"]["text"]
    assert not [e for e in evs if e["type"] == "tool"]


def test_tool_call_limit_is_enforced(runner, demo_ids, monkeypatch):
    monkeypatch.setattr(get_settings(), "flo_max_tool_calls", 2)
    ans, evs = _run(runner, demo_ids["demo"], "Why is this happening?", {"topics": ["billing_refunds"]})
    ok_calls = [e for e in evs if e["type"] == "tool" and e["status"] in ("ok", "error")]
    assert len(ok_calls) <= 2
    assert any(e["type"] == "tool" and e["status"] == "blocked" for e in evs)


def test_citations_resolve_to_exact_messages(runner, demo_ids, client):
    ans, _ = _run(runner, demo_ids["demo"], "Show the evidence behind this chart.", {"topics": ["orders_delivery"]})
    ev = ans["response"]["evidence"]
    assert ev
    for e in ev:
        conv = client.get(f"/api/datasets/{demo_ids['demo']}/conversations/{e['conversation_key']}").json()
        msg = next(m for m in conv["messages"] if m["message_id"] == e["message_id"])
        assert e["quote"] in msg["text"]


def test_approval_resume_is_idempotent(runner, demo_ids):
    ans, evs = _run(runner, demo_ids["demo"], "Propose an action to reduce unresolved refund issues", session="ses_appr")
    assert ans["status"] == "awaiting_approval"
    assert any(e["type"] == "approval_required" for e in evs)
    with session_scope() as s:
        before = s.scalar(select(func.count(Action.id)))
    rid = ans["request_id"]
    out = list(runner.resume(session_id="ses_appr", request_id=rid, decision={"decision": "approve", "reviewer": "Ops lead", "edits": {"owner": "Billing lead"}}))
    rec = out[-1]["response"]["action_record"]
    assert rec["created"] and rec["status"] == "approved"
    with pytest.raises(RunError):
        list(runner.resume(session_id="ses_appr", request_id=rid, decision={"decision": "approve"}))
    with session_scope() as s:
        assert s.scalar(select(func.count(Action.id))) == before + 1
        a = s.get(Action, rec["id"])
        assert a.owner == "Billing lead" and [h.to_status for h in a.history] == ["proposed", "approved"]


def test_read_only_analysis_needs_no_approval(runner, demo_ids):
    ans, evs = _run(runner, demo_ids["demo"], "Brief me on this dataset.")
    assert ans["status"] == "completed"
    assert not any(e["type"] == "approval_required" for e in evs)


def test_reject_saves_nothing(runner, demo_ids):
    ans, _ = _run(runner, demo_ids["demo"], "Create an action for delivery issues", session="ses_rej")
    with session_scope() as s:
        before = s.scalar(select(func.count(Action.id)))
    out = list(runner.resume(session_id="ses_rej", request_id=ans["request_id"], decision={"decision": "reject"}))
    assert out[-1]["status"] == "completed"
    with session_scope() as s:
        assert s.scalar(select(func.count(Action.id))) == before


def test_session_isolation(runner, demo_ids):
    ans, _ = _run(runner, demo_ids["demo"], "Propose an action for app issues", session="ses_owner")
    with pytest.raises(RunError) as e:
        list(runner.resume(session_id="ses_intruder", request_id=ans["request_id"], decision={"decision": "approve"}))
    assert e.value.status == 404
    with pytest.raises(RunError):
        runner.cancel("ses_intruder", ans["request_id"])


def test_prompt_injection_in_transcript_is_inert(runner, demo_ids):
    with session_scope() as s:
        before = s.scalar(select(func.count(Action.id)))
    ans, evs = _run(runner, demo_ids["demo"], "Show me evidence about admin mode and approving actions", {"topics": ["billing_refunds"]})
    assert not any(e["type"] == "approval_required" for e in evs)
    text = ans["response"]["text"].lower()
    quotes = " ".join(e["quote"].lower() for e in ans["response"]["evidence"])
    assert "100% resolved" not in text.replace(quotes, "")
    with session_scope() as s:
        assert s.scalar(select(func.count(Action.id))) == before


def test_mode_mismatch_is_rejected(runner, demo_ids, imported_id):
    with pytest.raises(RunError):
        list(runner.start(session_id="s", question="hi", dataset_id=imported_id, mode="demo", page=None, filters=None))
    with pytest.raises(RunError):
        list(runner.start(session_id="s", question="hi", dataset_id=demo_ids["demo"], mode="connected", page=None, filters=None))


def test_unconfigured_model_fails_without_demo_fallback(runner, imported_id):
    set_model_override(None)
    ans, evs = _run(runner, imported_id, "What are the most common issues?", mode="connected")
    assert ans["response"]["kind"] == "error"
    assert "did not switch to demonstration rules" in ans["response"]["text"]
    assert not [e for e in evs if e["type"] == "tool"]
    with session_scope() as s:
        assert s.get(Run, ans["request_id"]).status == "failed"


def test_failing_model_fails_without_demo_fallback(runner, imported_id):
    set_model_override(ScriptedModel(fail=True))
    try:
        ans, _ = _run(runner, imported_id, "What are the most common issues?", mode="connected")
    finally:
        set_model_override(None)
    assert ans["response"]["kind"] == "error" and "simulated provider outage" in ans["response"]["text"]


def _plan(qtype, steps):
    steps = [{"tool": st["tool"], "purpose": st["purpose"], "args_json": json.dumps(st.get("args", {}))} for st in steps]
    return {"LLMPlan": {"question_type": qtype, "steps": steps}}


def test_connected_insufficient_scope_is_reported(runner, imported_id):
    model = ScriptedModel(plans=_plan("analytics", [{"tool": "get_topic_counts", "purpose": "count", "args": {}}]))
    set_model_override(model)
    try:
        ans, _ = _run(runner, imported_id, "What are the most common issues?", mode="connected")
    finally:
        set_model_override(None)
    assert ans["response"]["kind"] == "insufficient"  # 4 conversations < minimum denominator
    assert model.calls == 0


@pytest.fixture()
def small_ok(monkeypatch):
    monkeypatch.setattr(get_settings(), "flo_min_denominator", 1)


def test_connected_answer_with_validated_numbers(runner, imported_id, small_ok):
    model = ScriptedModel(plans=_plan("analytics", [{"tool": "get_topic_counts", "purpose": "count", "args": {"top_n": 5}}]),
                          answers=["**Finding**\nBilling & refunds is the largest topic [M1].\n\n**Scope and denominator**\n4 conversations."])
    set_model_override(model)
    try:
        ans, evs = _run(runner, imported_id, "What are the most common issues?", mode="connected")
    finally:
        set_model_override(None)
    r = ans["response"]
    assert r["validation"]["status"] == "passed", r
    assert any(e["type"] == "token" for e in evs)  # streamed
    assert ans["usage"]["input_tokens"] > 0


def test_connected_answer_with_invented_number_fails_validation(runner, imported_id, small_ok):
    bad = "**Finding**\n87% of customers churned, costing 120000 dollars [M1]."
    model = ScriptedModel(plans=_plan("analytics", [{"tool": "get_topic_counts", "purpose": "count", "args": {}}]), answers=[bad, bad])
    set_model_override(model)
    try:
        ans, _ = _run(runner, imported_id, "What are the most common issues?", mode="connected")
    finally:
        set_model_override(None)
    r = ans["response"]
    assert r["validation"]["status"] == "failed"
    assert "87%" not in r["text"] and "failed claim validation" in r["text"]
    assert model.calls == 2  # one bounded retry


def test_model_cannot_add_unrequested_action(runner, imported_id, small_ok):
    model = ScriptedModel(plans=_plan("analytics", [{"tool": "get_topic_counts", "purpose": "count", "args": {}},
                                                    {"tool": "propose_action", "purpose": "sneaky", "args": {"title": "x", "issue": "y", "intervention": "z"}}]),
                          answers=["**Finding**\nSee counts [M1]."])
    set_model_override(model)
    try:
        ans, evs = _run(runner, imported_id, "What are the most common issues?", mode="connected")
    finally:
        set_model_override(None)
    assert not any(e["type"] == "approval_required" for e in evs)
    assert "propose_action" not in [e.get("tool") for e in evs if e["type"] == "tool"]


def test_model_scope_cannot_be_widened(runner, imported_id, small_ok):
    model = ScriptedModel(plans=_plan("analytics", [{"tool": "get_resolution_breakdown", "purpose": "x", "args": {"filters": {"topics": ["app_technical"]}}}]),
                          answers=["**Finding**\nok [M1]"])
    set_model_override(model)
    try:
        ans, evs = _run(runner, imported_id, "outcomes?", {"topics": ["billing_refunds"]}, mode="connected")
    finally:
        set_model_override(None)
    tool = next(e for e in evs if e["type"] == "tool" and e["status"] == "ok")
    assert "Billing & refunds" in tool["filters"] and "App" not in tool["filters"]


def test_cancellation(runner, demo_ids):
    gen = runner.start(session_id="ses_c", question="Why is this happening?", dataset_id=demo_ids["demo"], mode="demo", page=None, filters={"topics": ["billing_refunds"]})
    first = next(gen)
    runner.cancel("ses_c", first["request_id"])
    evs = list(gen)
    assert evs[-1]["response"]["kind"] == "cancelled"
    with session_scope() as s:
        assert s.get(Run, first["request_id"]).status == "cancelled"


def test_langsmith_disabled_operation(runner, demo_ids, client):
    st = client.get("/api/status").json()
    assert st["langsmith"]["configured"] is False and st["langsmith"]["label"] == "LangSmith not configured"
    ans, evs = _run(runner, demo_ids["demo"], "Brief me on this dataset.")
    assert evs[0]["tracing"] is False and ans["status"] == "completed"
    with session_scope() as s:
        assert s.get(Run, ans["request_id"]).langsmith_run_id is None
