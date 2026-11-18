"""Flo & Jerry 3.0: enterprise pulse, continuity records, lenses vs permissions, Jerry intents."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import auth, pulse
from app.copilot import engine, router
from app.enterprise import data
from app.vision import service as vision

from conftest import user

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def client(platform):
    data.seed()
    from app.main import app

    return TestClient(app)


def headers(username: str) -> dict:
    return {"Authorization": f"Bearer {auth.login(username, auth.DEMO_PASSWORD)[0]}"}


def test_pulse_is_evidence_backed_and_bounded(client):
    body = client.get("/api/pulse", headers=headers("val.viewer")).json()
    assert len(body["health"]) == 5
    for h in body["health"]:
        assert h["provenance"] in pulse.PROVENANCE and h["explanation"] and h["status"] in (
            "good", "watch", "attention", "unknown")
    prios = body["priorities"]
    assert prios and [p["score"] for p in prios] == sorted((p["score"] for p in prios), reverse=True)
    for p in prios:
        assert p["title"] and p["why"] and p["next_step"] and p["evidence"] and p["owner"]
        assert p["provenance"] in pulse.PROVENANCE
        assert all(e["provenance"] in pulse.PROVENANCE for e in p["evidence"])
    ids = [p["id"] for p in prios]
    assert "PRI-STOCK-FS-APPLE-355" in ids and any(i.startswith("PRI-COMP-") for i in ids)
    assert any(p["provenance"] == "modeled" for p in prios)  # the globe's simulation is labelled as modelled
    assert "No verified enterprise data source" in body["data_status"]
    assert body["since"]["first_visit"] is True and body["briefing"]


def test_since_last_visit_reports_real_changes_or_says_nothing_changed(client):
    h = headers("val.viewer")
    client.get("/api/pulse", headers=h)  # first visit sets the baseline
    second = client.get("/api/pulse", headers=h).json()["since"]
    assert second["first_visit"] is False and second["changes"] == []
    assert second["message"] == "Nothing meaningful has changed since your last visit."
    batch = vision.create_batch("val.viewer", "New batch", supplier="Farm A")
    vision.add_image(batch["id"], "val.viewer", (ROOT / "e2e" / "fixtures" / "synthetic-potatoes.jpg").read_bytes())
    third = client.get("/api/pulse", headers=h).json()["since"]
    kinds = {c["kind"] for c in third["changes"]}
    assert "inspection" in kinds and third["message"] is None


def test_lens_changes_layout_never_permissions(client):
    h = headers("val.viewer")
    assert client.get("/api/me/lens", headers=h).json()["lens"] == "executive"  # default for the viewer role
    assert client.put("/api/me/lens", json={"lens": "admin"}, headers=h).json()["lens"] == "admin"
    assert client.put("/api/me/lens", json={"lens": "superuser"}, headers=h).status_code == 400
    # Administrator lens, still the viewer role: release approval stays forbidden.
    assert client.post("/api/releases/rollback", json={"reason": "lens test"}, headers=h).status_code == 403
    assert client.get("/api/pulse", headers={}).status_code == 401


def test_decision_journal_and_investigations_are_private_and_compare_against_baseline(client):
    h, other = headers("val.viewer"), headers("maya.marketing")
    d = client.post("/api/decisions", headers=h, json={
        "title": "Expedite apple stock", "decision": "Expedite PO-55102", "priority_id": "PRI-STOCK-FS-APPLE-355",
        "follow_up_on": "2026-01-01"}).json()
    assert d["evidence"] and d["recommendation"] and d["baseline"]["high_campaign_risk"] == 1
    assert "No action was executed" in d["note"]
    assert client.get("/api/decisions", headers=other).json()["decisions"] == []
    assert client.patch(f"/api/decisions/{d['id']}", headers=other, json={"status": "done"}).status_code == 404
    done = client.patch(f"/api/decisions/{d['id']}", headers=h,
                        json={"status": "done", "outcome": "PO arrived early"}).json()
    assert done["status"] == "done" and done["outcome_recorded_at"]
    inv = client.post("/api/investigations", headers=h, json={"title": "Apple stock", "priority_id":
                      "PRI-STOCK-FS-APPLE-355", "geo": {"country": "124"}}).json()
    assert inv["still_open"] is True and inv["changes"] == [] and inv["geo"] == {"country": "124"}
    assert client.get("/api/investigations", headers=other).json()["investigations"] == []
    # the follow-up date has passed, so it shows up as a change since the last visit
    client.get("/api/pulse", headers=h)
    client.patch(f"/api/decisions/{d['id']}", headers=h, json={"status": "open"})
    assert any(c["kind"] == "decision" for c in client.get("/api/pulse", headers=h).json()["since"]["changes"])


def test_feedback_technology_and_reports(client):
    h = headers("val.viewer")
    assert client.post("/api/copilot/feedback", headers=h, json={"helpful": False, "comment": "wrong region"}).json()
    tech = client.get("/api/technology", headers=h).json()["questions"]
    assert [t["key"] for t in tech] == ["reliable", "jerry", "integrations", "trust", "cost"]
    assert "1 answer rating(s), 0 helpful" in tech[3]["answer"]
    assert "no per-token charge" in tech[4]["answer"]
    weekly = client.get("/api/reports/weekly", headers=h).json()
    assert set(weekly["this_week"]) == set(weekly["last_week"]) and weekly["business"]["provenance"] == "synthetic"
    hist = client.get("/api/reports/history", headers=h).json()
    assert len(hist["sales"]["series"]) == 16 and hist["quality"]["provenance"] == "operational_record"


def test_jerry_answers_cto_questions_from_records(client):
    assert router.parse("Jerry, what changed since yesterday?").intents == ["pulse"]
    assert router.parse("Are our AI systems healthy?").intents == ["tech_health"]
    assert router.parse("What should I focus on before my board meeting?").intents == ["overview", "pulse"]
    assert router.parse("How did our sales do in the last 4 weeks?").intents == ["sales"]  # unchanged
    a = engine.ask("Jerry, what changed since yesterday?", user("val.viewer"))
    assert "first visit" in a["answer"] and "Top priorities" in a["answer"] and a["sources"]
    a = engine.ask("Are our AI systems healthy?", user("val.viewer"))
    assert "Is Jerry available?" in a["answer"] and "[S1]" in a["answer"]
    a = engine.ask("What happened to the quality issue we discussed last week?", user("val.viewer"))
    assert "no saved investigations" in a["answer"]
