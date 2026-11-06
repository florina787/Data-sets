from app.db import session_scope
from app.models.orm import Case
from conftest import approve, execute, investigate


def _run_to_verify(client, login, cid, profile=None, approver="u-sup-emma", executor="u-field-dev"):
    if profile:
        with session_scope() as db:
            c = db.get(Case, cid)
            c.simulation_profile = {**c.simulation_profile, "post_action": profile}
    d = investigate(client, login, cid)
    assert approve(client, login, cid, d, persona=approver).status_code == 200
    assert execute(client, login, cid, d["approval"]["id"], persona=executor).status_code == 200


def test_missing_samples_are_not_success(client, login):
    _run_to_verify(client, login, "C-1010")
    v = client.post("/api/cases/C-1010/verify", headers=login("u-spec-ava"), json={}).json()
    assert v["case"]["status"] == "MONITORING"
    assert v["recovery"]["healthy_samples"] == 1
    assert "Recovery not yet verified" in v["recovery"]["reasons"][0]


def test_failed_recovery_escalates(client, login):
    _run_to_verify(client, login, "C-1011", profile="still_failing")
    v = client.post("/api/cases/C-1011/verify", headers=login("u-spec-ava"), json={}).json()
    assert v["case"]["status"] == "ESCALATED"


def test_customer_report_conflict_keeps_case_open(client, login):
    _run_to_verify(client, login, "C-1011")
    v = client.post("/api/cases/C-1011/verify", headers=login("u-spec-ava"),
                    json={"customer_report": "Customer says it dropped twice since the visit."}).json()
    assert v["case"]["status"] == "MONITORING" and v["recovery"]["customer_report_conflict"]
    # re-verification without a conflicting report can resolve it
    v2 = client.post("/api/cases/C-1011/verify", headers=login("u-spec-ava"), json={}).json()
    assert v2["case"]["status"] == "RESOLVED"


def test_active_incident_keeps_monitoring(client, login):
    _run_to_verify(client, login, "C-1001", approver="u-spec-ava", executor="u-spec-ava")
    v = client.post("/api/cases/C-1001/verify", headers=login("u-spec-ava"), json={}).json()
    assert v["case"]["status"] == "MONITORING"
    assert "still active" in v["recovery"]["reasons"][0]


def test_verify_requires_execution(client, login):
    investigate(client, login, "C-1003")
    r = client.post("/api/cases/C-1003/verify", headers=login("u-spec-ava"), json={})
    assert r.status_code == 409
