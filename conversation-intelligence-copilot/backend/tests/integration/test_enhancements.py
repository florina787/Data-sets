"""The six enhancements against the hand-checked fixture (see tests/fixtures/build_fixture.py)."""

import pytest
from fastapi.testclient import TestClient

from app.agents.graph import run_chat

Q1 = "What were the top 5 topics most associated with negative customer sentiment in the last month represented in the dataset?"


def op(name, scope=None, **params):
    from app.analytics.db import get_db
    from app.analytics.query_registry import run_operation
    from app.schemas.analysis import Scope

    return run_operation(get_db(), name, scope or Scope(), params)


# --- Conversation X-Ray -----------------------------------------------------------------------

def test_xray_findings_match_hand_count(env):
    # C0000001: opening (neg) / hold / escalate / hold / urgent / refund. Each negative turn gets a non-empathic reply.
    r = op("conversation_xray", conversation_id="C0000001")
    m = {x.id: x.value for x in r.metrics}
    assert (m["escalation_signals"], m["repeated_concerns"], m["communication_gaps"], m["high_severity"]) == (2, 0, 3, 3)
    kinds = {s["kind"]: s for s in r.series["signals"].rows}
    assert kinds["unacknowledged_negative"]["turns"] == [0, 1, 2, 3, 4, 5]
    assert kinds["repeated_hold_notice"]["turns"] == [1, 3] and kinds["ends_unresolved"]["turns"] == [4]
    ids = {row["message_id"] for row in r.table.rows}
    assert all(set(s["message_ids"]) <= ids for s in r.series["signals"].rows)  # every finding cites real messages
    flagged = {row["message_id"]: row["signals"] for row in r.table.rows}
    assert "escalation_request" in flagged[kinds["escalation_request"]["message_ids"][0]]  # timeline <-> finding link


def test_xray_resolution_mismatch_and_missing_conversation(env):
    r = op("conversation_xray", conversation_id="C0000002")  # duplicate charge closed with a coupon
    assert any(s["kind"] == "resolution_mismatch" for s in r.series["signals"].rows)
    assert op("conversation_xray", conversation_id="C9999999").status == "insufficient_data"


def test_xray_through_the_graph(env):
    r = run_chat("X-ray conversation C0000001")
    assert r["plan"]["category"] == "conversation_xray" and r["xray"]["params"]["conversation_id"] == "C0000001"
    assert r["routing"]["route"] == "analytics_only" and r["status"] == "completed"
    r = run_chat("How did customer sentiment change in conversation C0000002?")
    assert [s["op"] for s in r["plan"]["steps"]] == ["sentiment_trajectory", "conversation_xray"] and r["xray"]


# --- Root Cause Investigator -------------------------------------------------------------------

def test_root_cause_needs_enough_conversations(env):
    r = op("root_cause_investigation", topic="duplicate_charge")
    assert r.status == "insufficient_data" and "at least 20" in r.uncertainty_notes[0]


def test_root_cause_statistics_on_fixture(env, monkeypatch):
    from app.analytics import root_cause

    monkeypatch.setattr(root_cause, "MIN_TOPIC_CONVERSATIONS", 2)
    monkeypatch.setattr(root_cause, "MIN_SUPPORT", 1)
    # duplicate charge: C1, C6 negative with non-empathic replies; C2 empathic, coupon (mismatch), not negative.
    r = op("root_cause_investigation", topic="duplicate_charge")
    f = {h["factor"]: h for h in r.series["all_factors"].rows}
    assert (f["low_empathy"]["with_factor"], f["low_empathy"]["negative_rate_with"], f["low_empathy"]["negative_rate_without"]) == (2, 1.0, 0.0)
    assert f["resolution_mismatch"]["negative_rate_with"] == 0.0 and f["resolution_mismatch"]["risk_difference"] == -1.0
    assert "escalation" not in f and any("Customer asked to escalate" in n for n in r.method_notes)  # all 3 escalate: untestable
    assert any("not causal" in n for n in r.uncertainty_notes) and r.series["alternatives"].rows


def test_root_cause_intent_and_plan(env):
    from app.agents.intent_rules import parse_intent

    i = parse_intent("What is driving negative sentiment in duplicate charges?")
    assert i.category == "root_cause" and i.topics == ["duplicate_charge"]
    r = run_chat("What is driving negative sentiment in duplicate charges?", analysis_mode="analytics_only")
    assert r["plan"]["steps"][0]["op"] == "root_cause_investigation" and r["status"] == "insufficient_data"


# --- Dynamic dashboards --------------------------------------------------------------------------

def test_dashboard_is_built_from_the_answer(env):
    r = run_chat(Q1)
    d = r["dashboard"]
    chart_ids = {c["chart_id"] for c in r["charts"]}
    placed = [i["chart_id"] for s in d["sections"] for i in s["items"]]
    assert set(placed) <= chart_ids and "negative_topics" in placed  # nothing on the dashboard that the answer did not compute
    assert d["sections"][0]["title"] == "Answer" and all(i["why"] for s in d["sections"] for i in s["items"])
    assert {"field": "window", "value": "February 2025"} in d["filters"]
    labels = [x["label"] for x in d["refinements"]]
    assert "All dates" in labels and "Compare top two" in labels


def test_unsupported_question_has_no_dashboard(env):
    assert run_chat("What is the revenue impact of churn?")["dashboard"] is None


# --- Evidence Challenger ---------------------------------------------------------------------------

def test_challenger_runs_on_every_answer(env):
    r = run_chat(Q1 + " (challenger)")
    ev = r["evidence_review"]
    names = {c["check"] for c in ev["checks"]}
    assert {"excerpt_fidelity", "evidence_coverage", "sample_size", "counter_evidence", "causal_language"} <= names
    fid = next(c for c in ev["checks"] if c["check"] == "excerpt_fidelity")
    assert fid["status"] == "pass" and any(c["check"] == "excerpt_fidelity" for c in r["quality_status"]["checks"])
    assert any("small" in n or "fewer than" in n for n in r["uncertainty_notes"])  # n=3 groups are disclosed


def test_challenger_catches_tampered_quote_and_causal_claim(env):
    from app.agents.evidence_challenger import challenge
    from app.analytics.db import get_db

    ev = [{"conversation_id": "C0000001", "topic": "Duplicate charge", "sentiment": "negative",
           "excerpts": [{"message_id": "C0000001-T00", "text": "I was charged THREE times for my Wallet."}]}]
    expl = {"headline": "Duplicate charges cause frustration.", "answer": "Negativity is driven by slow replies.", "key_points": []}
    review, out = challenge(get_db(), {"category": "negative_topics"}, {}, ev, expl, "llm")
    checks = {c["check"]: c for c in review["checks"]}
    assert checks["excerpt_fidelity"]["status"] == "fail" and checks["excerpt_fidelity"]["items"] == ["C0000001-T00"]
    assert checks["causal_language"]["status"] == "warn" and review["verdict"] == "challenged"
    assert out["headline"] == "Duplicate charges are associated with frustration." and "associated with slow replies" in out["answer"]


def test_challenger_rejects_unsupported_root_cause_claim(env):
    from app.agents.evidence_challenger import challenge
    from app.analytics.db import get_db

    rows = [{"factor": "low_empathy", "role": "agent_behaviour", "strength": "strong association", "evidence": ["C0000001"],
             "negative_rate_with": 0.6, "negative_rate_without": 0.2},
            {"factor": "scripted_repeats", "role": "agent_behaviour", "strength": "weak — not distinguishable from noise", "evidence": [],
             "negative_rate_with": 0.3, "negative_rate_without": 0.3}]
    rc = {"status": "ok", "table": {"rows": rows}, "series": {"all_factors": {"rows": rows}}}
    expl = {"headline": "Negativity is associated with scripted repeats.", "answer": "", "key_points": []}
    review, _ = challenge(get_db(), {"category": "root_cause"}, {"root_cause_investigation": rc}, [], expl, "llm")
    assert review["replaced_explanation"] is True
    assert next(c for c in review["checks"] if c["check"] == "claim_consistency")["items"] == ["scripted_repeats"]


# --- Decision Replay + token accounting -------------------------------------------------------------

@pytest.fixture()
def client(env):
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_decision_replay_is_complete_and_sanitised(client):
    r = client.post("/api/chat", json={"question": Q1 + " (replay)"}).json()
    rp = client.get(f"/api/replay/{r['request_id']}").json()
    assert rp["routing"]["route"] == "analytics_only" and rp["counts"]["llm_calls"] == 0
    assert [o["op"] for o in rp["operations"]] == ["rank_negative_topics", "sentiment_distribution", "sentiment_trend"]
    assert all(o["engine"] == "duckdb" and o["duration_ms"] >= 0 and "rows" in o for o in rp["operations"])
    assert [s["node"] for s in rp["steps"]][:3] == ["input_validation", "session_context", "router"]
    assert {d["at"] for d in rp["decisions"]} >= {"router", "intent", "supervisor", "explanation", "qa"}
    assert client.get("/api/replay/R-doesnotexist").status_code == 404


def test_replay_sanitiser_redacts_secrets():
    from app.observability.replay import sanitize

    out = sanitize({"api_key": "x", "headers": {"a": 1}, "note": "key=AIzaSyA1234567890123456789012345 Bearer abcdefghijklmnop",
                    "nested": [{"traceback": "...", "ok": "x" * 400}], "total_tokens": 12})
    assert "api_key" not in out and "headers" not in out and "AIza" not in out["note"] and "Bearer abc" not in out["note"]
    assert "traceback" not in out["nested"][0] and len(out["nested"][0]["ok"]) == 301 and out["total_tokens"] == 12


def test_token_accounting_endpoint_separates_preprocessing(client):
    t = client.get("/api/telemetry/tokens").json()
    assert t["preprocessing"]["label_source"] == "rules" and "no LLM tokens" in t["preprocessing"]["note"]
    assert t["per_query"]["total_tokens"] is not None or t["per_query"]["unreported"] > 0
    assert any(x["route"] == "analytics_only" for x in t["routes"])


def test_chat_request_accepts_analysis_mode(client):
    r = client.post("/api/chat", json={"question": "Why is sentiment negative?", "analysis_mode": "hybrid_ai"}).json()
    assert r["routing"]["requested_mode"] == "hybrid_ai" and r["routing"]["route"] == "analytics_only"  # no LLM in tests
    assert client.post("/api/chat", json={"question": "x", "analysis_mode": "turbo"}).status_code == 422
