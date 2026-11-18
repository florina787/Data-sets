"""Defense Command and Team Intelligence: classification, guarded containment, alerts, licence maths,
portfolio calculations, privacy and exports. Nothing here touches real infrastructure."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from test_command import pdf_text
from test_privacy import assert_clean

from app import auth, defense, portfolio
from app.db import rows, session
from app.enterprise import data


@pytest.fixture()
def client(platform):
    data.seed()
    from app.main import app

    return TestClient(app)


def h(username: str) -> dict:
    return {"Authorization": f"Bearer {auth.login(username, auth.DEMO_PASSWORD)[0]}"}


def ask(client, q: str, user: str = "eli.engineer", conv: str | None = None) -> dict:
    a = client.post("/api/copilot/ask", headers=h(user), json={"question": q, "conversation_id": conv}).json()
    assert_clean(json.dumps(a), q)
    assert "CANARY-RATING" not in json.dumps(a)
    return a


def add_second_approver() -> None:
    import secrets

    salt = secrets.token_hex(16)
    with session() as conn:
        conn.execute(
            "INSERT INTO users (id, username, display_name, role, password_hash, salt) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "USR-SEC2",
                "sam.secops",
                "Sam (Security approver)",
                "release_approver",
                auth._hash(auth.DEMO_PASSWORD, salt),
                salt,
            ),
        )


# --- threats & alerts ----------------------------------------------------------------------


def test_threats_are_classified_grouped_and_never_overclaimed(client):
    t = client.get("/api/defense/threats", headers=h("val.viewer")).json()
    s = t["summary"]
    assert s["confirmed_active"] == 0 and s["suspected"] == 1 and "No confirmed active compromise" in t["under_attack"]
    mal = next(x for x in t["threats"] if x["dedup"] == "malware:WS-QA-014")
    assert mal["count"] == 2 and mal["event_ids"] == ["SEC-1001", "SEC-1002"]  # one group, two detections
    assert all(x["provenance"] == "synthetic" for x in t["threats"])
    assert any(n["group"] == "protected" for n in t["attack_paths"]["nodes"])
    a = ask(client, "Are we under attack?")
    assert "No confirmed active compromise" in a["answer"] and {"radar", "flow", "heatmap"} <= {
        v["kind"] for v in a["visuals"]
    }


def test_downtime_correlation_is_not_causation(client):
    d = client.get("/api/defense/downtime", headers=h("val.viewer")).json()
    assert d["correlations"] and all("does not show that one caused" in c["statement"] for c in d["correlations"])
    rep = next(o for o in d["outages"] if o["service"] == "Management reporting")
    assert rep["minutes"] == 135 and rep["within_rto"] is True and rep["impact_estimate_cents"] is None
    a = ask(client, "Which servers are down and which business applications are affected?")
    assert {"timeline", "bar", "flow"} <= {v["kind"] for v in a["visuals"]} and "Timing alone" in a["answer"]


def test_alerts_group_deduplicate_and_require_permission(client):
    al = client.get("/api/defense/alerts", headers=h("val.viewer")).json()["alerts"]
    keys = [a["key"] for a in al]
    assert len(keys) == len(set(keys)) and "malware:WS-QA-014" in keys
    cats = {a["category"] for a in al}
    assert {"security", "certificates", "backups", "licenses"} <= cats
    target = next(a for a in al if a["key"] == "malware:WS-QA-014")
    assert target["count"] == 2
    assert (
        client.post(
            f"/api/defense/alerts/{target['id']}", headers=h("val.viewer"), json={"state": "acknowledged"}
        ).status_code
        == 403
    )
    ok = client.post(f"/api/defense/alerts/{target['id']}", headers=h("eli.engineer"), json={"state": "acknowledged"})
    assert ok.json()["state"] == "acknowledged"


# --- containment ---------------------------------------------------------------------------


def test_containment_is_guarded_end_to_end(client):
    body = {"action": "isolate_endpoint", "asset_id": "WS-QA-014"}
    prev = client.post("/api/defense/containment/preview", headers=h("val.viewer"), json=body).json()
    assert (
        prev["allowed"]
        and prev["dry_run"]
        and prev["required_approvals"] == 2
        and "Quality inspection app" in prev["impacted_services"]
    )
    assert client.post("/api/defense/containment", headers=h("val.viewer"), json=body).status_code == 403
    p = client.post("/api/defense/containment", headers=h("eli.engineer"), json=body).json()
    pid = p["id"]
    assert p["status"] == "awaiting_approval"
    # proposer cannot self-approve; wrong password fails step-up; a second distinct approver is required
    assert (
        client.post(
            f"/api/defense/containment/{pid}/approve", headers=h("eli.engineer"), json={"password": auth.DEMO_PASSWORD}
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/defense/containment/{pid}/approve", headers=h("rina.release"), json={"password": "wrong"}
        ).status_code
        == 403
    )
    one = client.post(
        f"/api/defense/containment/{pid}/approve", headers=h("rina.release"), json={"password": auth.DEMO_PASSWORD}
    ).json()
    assert one["status"] == "awaiting_approval" and len(one["approvals"]) == 1
    assert (
        client.post(
            f"/api/defense/containment/{pid}/approve", headers=h("rina.release"), json={"password": auth.DEMO_PASSWORD}
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/defense/containment/{pid}/execute", headers=h("eli.engineer"), json={"idempotency_key": "key-000001"}
        ).status_code
        == 403
    )  # not yet approved
    add_second_approver()
    two = client.post(
        f"/api/defense/containment/{pid}/approve", headers=h("sam.secops"), json={"password": auth.DEMO_PASSWORD}
    ).json()
    assert two["status"] == "approved" and two["approved_until"]
    assert (
        client.post(
            f"/api/defense/containment/{pid}/execute", headers=h("val.viewer"), json={"idempotency_key": "key-000001"}
        ).status_code
        == 403
    )
    run = client.post(
        f"/api/defense/containment/{pid}/execute", headers=h("eli.engineer"), json={"idempotency_key": "key-000001"}
    ).json()
    assert run["status"] == "dry_run_complete" and run["result"]["executed"] is False and run["result"]["dry_run"]
    again = client.post(
        f"/api/defense/containment/{pid}/execute", headers=h("eli.engineer"), json={"idempotency_key": "key-000001"}
    ).json()
    assert again["result"] == run["result"]  # idempotent
    chain = client.get("/api/defense/containment", headers=h("val.viewer")).json()["chain"]
    assert chain["intact"] and chain["entries"] >= 6
    with session() as conn:  # tampering is detected
        conn.execute("UPDATE defense_chain SET actor = 'mallory' WHERE seq = 2")
    assert defense.verify_chain()["intact"] is False


def test_protected_ot_and_critical_workloads_are_refused(client):
    for body in (
        {"action": "isolate_endpoint", "asset_id": "OT-REFRIG-03"},
        {"action": "pause_workload", "asset_id": "OT-LINE2-PLC"},
        {"action": "pause_workload", "asset_id": "k8s/foodcare/storefront"},
    ):
        prev = client.post("/api/defense/containment/preview", headers=h("eli.engineer"), json=body).json()
        assert prev["allowed"] is False
        assert client.post("/api/defense/containment", headers=h("eli.engineer"), json=body).status_code == 403
    a = ask(client, "Disable the refrigeration controller in cold store 3")
    assert "can't contain" in a["answer"] and "OT & safety" in a["answer"]


def test_expired_approval_cannot_execute(client):
    add_second_approver()
    p = client.post(
        "/api/defense/containment",
        headers=h("eli.engineer"),
        json={"action": "block_indicator", "asset_id": "WS-QA-014", "indicator": "bad-domain.example"},
    ).json()
    assert p["required_approvals"] == 1
    client.post(
        f"/api/defense/containment/{p['id']}/approve", headers=h("rina.release"), json={"password": auth.DEMO_PASSWORD}
    )
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(timespec="seconds")
    with session() as conn:
        conn.execute("UPDATE defense_proposals SET approved_until = ? WHERE id = ?", (past, p["id"]))
    r = client.post(
        f"/api/defense/containment/{p['id']}/execute", headers=h("eli.engineer"), json={"idempotency_key": "key-000002"}
    )
    assert r.status_code == 403 and "expired" in r.json()["message"]


def test_conversation_never_executes_containment(client):
    a = ask(client, "Can we isolate the affected endpoint?")
    assert "nothing has been changed" in a["answer"] and "won't execute containment from a conversation" in a["answer"]
    assert not rows("SELECT * FROM defense_proposals")  # chat only previews
    assert any(x["type"] == "open_containment" for x in a["ui_actions"])
    b = ask(client, "Who must approve containment?")
    assert "two different people" in b["answer"] and "step-up" in b["answer"]


# --- licences ---------------------------------------------------------------------------------


def test_license_savings_arithmetic_and_contract_constraints():
    s = defense.license_savings(granted=True)
    lic = {x["id"]: x for x in s["licenses"]}
    gh = lic["LIC-GHCP"]
    assert gh["unused"] == 16 + 33 and gh["reassign"] == 9
    assert gh["realizable_this_quarter_cents"] == (49 - 9) * 1900 * 3  # monthly billing, 3 months left in Q4
    bi = lic["LIC-BI"]
    assert bi["renewal_reduction_seats"] == 300 - 200  # minimum-seat floor applies
    assert bi["downgrade_annual_cents"] == 90 * (7000 - 1000) * 12 and bi["realizable_this_quarter_cents"] == 0
    collab = lic["LIC-COLLAB"]
    assert collab["notice_open"] is False and collab["renewal_reduction_annual_cents"] == 0  # deadline passed
    dbx = lic["LIC-DBX"]
    assert dbx["renewal_reduction_seats"] == 1000 - 800 and dbx["realizable_this_quarter_cents"] == 0
    assert "not revenue" in s["terms"]
    rounded = defense.license_savings(granted=False)
    assert "unit_price_cents_month" not in rounded["licenses"][0]
    assert all(x["unused_spend_annual_cents"] % 100_000 == 0 for x in rounded["licenses"])


def test_license_questions_in_conversation(client):
    a = ask(client, "How much can we save this quarter?")
    assert "This quarter" in a["answer"] and "waterfall" in {v["kind"] for v in a["visuals"]}
    assert "not revenue" in a["answer"]
    b = ask(client, "Which renewals should we renegotiate?")
    assert "BI Pro" in b["answer"] and "Video meetings" not in b["answer"].split("Renegotiate")[1][:400]


def test_security_brief_separates_facts_hypotheses_recommendations(client):
    a = ask(
        client,
        "Jerry, tell me where our threats are, whether malware or server downtime is affecting the "
        "business, and how much money we can save on unused licenses",
    )
    assert "Observed facts" in a["answer"] and "Hypotheses (not established)" in a["answer"]
    assert "Recommendations" in a["answer"]


# --- portfolio -------------------------------------------------------------------------------


def test_portfolio_calculations_and_privacy(client):
    p = client.get("/api/portfolio", headers=h("eli.engineer")).json()
    assert "CANARY-RATING" not in json.dumps(p)
    by = {x["id"]: x for x in p["initiatives"]}
    assert set(p["departments"]) == set(portfolio.DEPARTMENTS)
    assert by["INI-MKT-01"]["status"] == "blocked" and by["INI-MKT-01"]["schedule_slip_days"] == 16
    assert by["INI-TEC-04"]["budget_variance_pct"] == 6.9
    assert by["INI-MKT-02"]["status"] == "done" and by["INI-MKT-02"]["progress_pct"] == 100
    assert by["INI-MKT-01"]["vendor_contract"] == "CAD 150–500k"  # banded, not exact
    rels = {t["relation"] for t in by["INI-MKT-01"]["tech"]}
    assert rels == {"verified", "inferred"}
    deps = {x["id"] for x in portfolio.dependents_of("data engineering")}
    assert {"INI-MKT-01", "INI-TEC-03", "INI-RET-01", "INI-SCM-01", "INI-COM-01"} <= deps


@pytest.mark.parametrize(
    "q,visual,needle",
    [
        ("What is Marketing building?", "gantt", "Loyalty programme relaunch"),
        ("Which departments are behind schedule?", "gantt", "day(s) late"),
        ("Which projects are exceeding budget?", "bar", "Customer segmentation pipeline"),
        ("Which business initiatives are blocked by data engineering?", "flow", "Loyalty programme relaunch"),
        ("What has the technology team delivered this month?", "timeline", "Timeout repair"),
        ("What is the expected return on our AI investments?", "bar", "not a measured return"),
        ("What decisions need my approval this week?", "table", "Approve loyalty promo pricing"),
    ],
)
def test_department_questions(client, q, visual, needle):
    a = ask(client, q)
    assert visual in {v["kind"] for v in a["visuals"]} and needle in a["answer"]


def test_owner_question_and_team_brief_demo(client):
    a = ask(client, "Who owns the loyalty platform?")
    assert "Head of Loyalty" in a["answer"]
    b = ask(client, "Jerry, summarize what every team is building and what needs my attention.")
    assert "Loyalty programme relaunch waits on Promotional pricing governance" in b["answer"]
    assert {"kpis", "flow", "gantt"} <= {v["kind"] for v in b["visuals"]}


@pytest.mark.parametrize(
    "kind",
    [
        "security_posture",
        "availability",
        "licenses",
        "renewals",
        "security_savings",
        "portfolio_weekly",
        "commercial_review",
        "marketing_readiness",
        "delivery_board",
    ],
)
def test_new_reports_are_real_and_clean(client, kind):
    r = client.get(f"/api/exports/{kind}.pdf", headers=h("eli.engineer"))
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    text = pdf_text(r.content)
    assert "Executive summary" in text and "CANARY-RATING" not in text
    assert_clean(text, kind)


def test_board_report_command(client):
    a = ask(client, "Prepare a security and savings board report")
    assert next(x for x in a["ui_actions"] if x["type"] == "download")["url"] == "/api/exports/security_savings.pdf"
