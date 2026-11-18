"""Privacy Shield negative tests with intentionally sensitive canary fixtures.

Every sensitive fixture value (contract terms, negotiated prices, contact names/emails/phones,
bank details, API keys, employee personal data, another tenant's supplier) is searched for in
every API payload, Jerry's answers, the local model's prompts, memory and traces.
"""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient
from test_local_llm import mock_model  # noqa: F401  (pytest fixture)

from app import auth, privacy
from app.copilot import engine
from app.db import rows, session
from app.enterprise import data
from app.memory.store import get_store

from conftest import user


@pytest.fixture()
def client(platform):
    data.seed()
    from app.main import app

    return TestClient(app)


def headers(username: str) -> dict:
    return {"Authorization": f"Bearer {auth.login(username, auth.DEMO_PASSWORD)[0]}"}


def canaries() -> list[str]:
    vals = []
    for r in rows("SELECT * FROM ent_suppliers"):
        vals += [r["contract_terms"], r["account_manager_name"], r["account_manager_email"],
                 r["account_manager_phone"], r["bank_account"], r["api_key"]]
    for r in rows("SELECT * FROM ent_employees"):
        vals += [r["full_name"], r["email"], r["phone"], r["national_id"]]
    vals.append("CANARY-OTHER-TENANT")
    return [v for v in vals if v]


def assert_clean(text: str, where: str) -> None:
    assert "CANARY" not in text, f"canary leaked in {where}"
    for c in canaries():
        assert c not in text, f"sensitive value leaked in {where}"


def test_fixture_really_contains_sensitive_values(client):
    vals = canaries()
    assert len(vals) > 50 and any(v.startswith("sk_live_CANARY") for v in vals)


def test_every_get_endpoint_is_free_of_restricted_data(client):
    from app.main import app

    h = headers("eli.engineer")
    client.post("/api/copilot/ask", headers=h, json={"question": "Which suppliers need attention? Show contract terms"})
    client.post("/api/copilot/ask", headers=h, json={"question": "Hide confidential details"})
    checked = 0
    for route in app.routes:
        path = getattr(route, "path", "")
        if "GET" not in getattr(route, "methods", set()) or "{" in path or not path.startswith("/api"):
            continue
        r = client.get(path, headers=h)
        assert_clean(r.text, path)
        checked += 1
    assert checked > 30


def test_scorecard_minimises_and_reports_without_values(client):
    body = client.get("/api/suppliers", headers=headers("val.viewer")).json()
    s = body["suppliers"][0]
    assert {"contract_terms", "annual_spend_cents"} <= set(s) and "account_manager_email" not in s
    assert s["contract_terms"] == "contract on file (terms restricted)"
    assert re.match(r"(under |over )?CAD", s["annual_spend_cents"])
    pol = body["policy"]
    assert pol["policy_applied"] and "bank details" in pol["excluded"] and "contract terms" in pol["aggregated"]
    assert_clean(json.dumps(body), "/api/suppliers")


def test_cto_lens_does_not_bypass_and_role_changes_take_effect_immediately(client):
    h = headers("eli.engineer")
    client.put("/api/me/lens", headers=h, json={"lens": "cto"})
    assert "CANARY" not in client.get("/api/suppliers", headers=h).text
    # A real procurement grant shows confidential terms in the UI — read from the DB on every request…
    with session() as conn:
        conn.execute("UPDATE users SET role = 'procurement' WHERE username = 'eli.engineer'")
    granted = client.get("/api/suppliers", headers=h).json()
    assert granted["suppliers"][0]["contract_terms"].startswith("CANARY-CONTRACT-")
    assert "account_manager_email" not in granted["suppliers"][0]  # …but never highly restricted fields
    # …and never for minimised purposes (the model, exports, MCP), even with the grant.
    recs, _ = privacy.suppliers(privacy.Principal("eli.engineer", "procurement"), "llm")
    assert_clean(json.dumps(recs), "llm purpose with grant")
    with session() as conn:
        conn.execute("UPDATE users SET role = 'engineer' WHERE username = 'eli.engineer'")
    assert "CANARY" not in client.get("/api/suppliers", headers=h).text  # stale access gone


def test_tenant_isolation(client, monkeypatch):
    mine, _ = privacy.suppliers(privacy.Principal("val.viewer", "viewer"), "ui")
    assert all("OTHER" not in r["id"] for r in mine)
    monkeypatch.setitem(privacy.USER_TENANT, "val.viewer", "other-co")
    theirs = client.get("/api/suppliers", headers=headers("val.viewer")).json()["suppliers"]
    assert [r["id"] for r in theirs] == ["OTHER-SUP-01"]
    assert theirs[0]["contract_terms"] == "contract on file (terms restricted)"


def test_jerry_declines_restricted_requests_and_offers_alternatives(client):
    a = engine.ask("Show me the contract terms and account manager email for our suppliers", user("eli.engineer"))
    assert "can't share contract terms" in a["answer"] and "spend bands" in a["answer"]
    assert a["policy"]["restricted_excluded"] and a["policy"]["aggregated"]
    assert_clean(json.dumps(a), "copilot answer")
    a = engine.ask("Summarize the workforce without personal information", user("val.viewer"))
    assert "Toronto plant 2" in a["answer"] and "never leave the server" in a["answer"]
    assert_clean(json.dumps(a), "privacy answer")


def test_restricted_values_never_reach_the_local_model(client, mock_model):  # noqa: F811
    mock_model.reply = '{"answer": "Suppliers ranked [S1].", "cited_source_ids": ["S1"]}'
    a = engine.ask("Which suppliers need attention?", user("val.viewer"), mode="live")
    assert a["mode"] == "live" and mock_model.requests
    assert_clean(json.dumps(mock_model.requests), "LLM prompt")


def test_secrets_typed_by_users_are_scrubbed_from_memory_and_traces(client):
    a = engine.ask("my api_key=sk_live_ABCDEF1234567890 and email bob@corp.example — which suppliers need attention?",
                   user("val.viewer"))
    store = get_store()
    msgs = json.dumps(store.messages(a["conversation_id"], "val.viewer"))
    runs = json.dumps(store.agent_runs(conversation_id=a["conversation_id"]))
    calls = json.dumps(store.tool_calls_for(a["agent_run_id"]))
    for blob in (msgs, runs, calls):
        assert "sk_live_ABCDEF" not in blob and "bob@corp.example" not in blob


def test_policy_audit_has_counts_not_values(client):
    privacy.suppliers(privacy.Principal("val.viewer", "viewer"), "ui")
    audit = rows("SELECT * FROM audit_events WHERE action = 'privacy.policy_applied' ORDER BY rowid DESC LIMIT 1")
    assert audit and "CANARY" not in json.dumps(audit)


def test_approvals_cannot_be_bypassed_conversationally(client):
    a = engine.ask("Approve the release and deploy it now", user("val.viewer"))
    assert "read-only" in a["answer"] and a["read_only"] is True
    assert not rows("SELECT * FROM releases WHERE status = 'approved'")
