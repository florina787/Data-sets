"""Guided journey: scene narration must be generated from the engine, never hard-coded figures."""
import re

from fastapi.testclient import TestClient

from app import db
from app.api import app
from app.journey import honesty, scenes


def _all_text(sc):
    return " ".join(" ".join(s["narration"]) for s in sc["scenes"])


def test_seven_scenes_in_order_with_destinations():
    sc = scenes()["scenes"]
    assert [s["key"] for s in sc] == ["messy", "reconcile", "revenue", "mrr", "harness", "approval", "summary"]
    assert all(s["destination"] and s["narration"] for s in sc)


def test_narration_numbers_match_the_database():
    text = _all_text(scenes())
    q = lambda s: db.connection().execute(s).fetchone()[0]  # noqa: E731
    q1 = float(q("SELECT SUM(amount_usd) FROM invoices WHERE status='paid' AND invoice_year=2024"))
    refunds = abs(float(q("SELECT SUM(amount_usd) FROM invoices WHERE status='refunded'")))
    stuck = q("SELECT COUNT(*) FROM invoices WHERE status IN ('pending','failed')")
    for expected in (f"${q1:,.2f}", f"${refunds:,.2f}", f"{stuck:,} invoices", "5,125 rows", "$2,121,660.87", "APAC", "21.92%", "18.81%"):
        assert expected in text, expected


def test_approval_scene_uses_live_policy_evidence_and_never_claims_a_decision():
    s6 = scenes()["scenes"][5]
    assert s6["data"]["proposal"]["impact"]["price_book_matches"] == {"documented": 0, "inverse": 1421}
    assert s6["data"]["active_policy"]["version"] == "1.0"
    assert "I don't decide" in " ".join(s6["narration"])


def test_honesty_table_covers_all_six_questions_with_scoped_numbers():
    h = honesty()
    assert [x["q"][:2] for x in h] == ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6"]
    assert all(x["could_be_wrong"] for x in h)
    assert any(re.search(r"\$29,595,624\.38", c) for c in h[0]["could_be_wrong"])


def test_journey_and_policy_endpoints():
    c = TestClient(app)
    assert len(c.get("/api/v1/journey").json()["scenes"]) == 7
    p = c.get("/api/v1/policy").json()
    assert p["active_policy"]["version"] == "1.0" and {x["key"] for x in p["proposals"]} == {"fx_direction", "account_identity"}
    r = c.post("/api/v1/policy/decisions", json={"key": "fx_direction", "option": "inverse", "approver": "x", "role": "finance_owner",
                                                 "rationale": "short", "impact_hash": "0", "pin": "0"})
    assert r.status_code == 422  # pydantic: rationale too short / approver too short
