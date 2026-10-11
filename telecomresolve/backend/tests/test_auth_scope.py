from conftest import investigate


def test_requires_authentication(client):
    assert client.get("/api/cases").status_code == 401
    assert client.get("/api/cases", headers={"Authorization": "Bearer forged.token"}).status_code == 401


def test_identity_cannot_be_asserted_by_body(client, login):
    # Extra identity fields in a body are ignored; actor comes from the session.
    r = client.post("/api/cases", headers=login("u-spec-ava"),
                    json={"account_id": "ACCT-1003", "title": "x test", "complaint_text": "drops again",
                          "actor_id": "u-sup-emma", "tenant_id": "tenant-south"})
    assert r.status_code == 201
    audit = client.get(f"/api/cases/{r.json()['id']}/audit", headers=login("u-sup-emma")).json()
    assert audit[0]["actor_id"] == "u-spec-ava"


def test_cross_tenant_case_denied_before_retrieval(client, login):
    r = client.post("/api/cases/C-1012/investigate?wait=true", headers=login("u-spec-ava"))
    assert r.status_code == 404
    assert client.get("/api/cases/C-1012/evidence", headers=login("u-spec-ava")).status_code == 404
    assert client.get("/api/cases/C-1012", headers=login("u-spec-ava")).status_code == 404
    # south tenant specialist can see it, and the north listing does not include it
    assert client.get("/api/cases/C-1012", headers=login("u-spec-gil")).status_code == 200
    ids = [c["id"] for c in client.get("/api/cases", headers=login("u-spec-ava")).json()]
    assert "C-1012" not in ids
    denied = client.get("/api/audit?event_type=ACCESS_DENIED", headers=login("u-sup-emma")).json()
    assert any(e["detail"]["requested_case_id"] == "C-1012" for e in denied)


def test_account_segment_scope(client, login):
    assert client.get("/api/cases/C-1013", headers=login("u-spec-ava")).status_code == 404
    assert client.get("/api/cases/C-1013", headers=login("u-sup-emma")).status_code == 200


def test_auditor_is_read_only(client, login):
    aud = login("u-aud-farah")
    assert client.post("/api/cases/C-1003/investigate", headers=aud).status_code == 403
    assert client.post("/api/cases/C-1003/verify", headers=aud, json={}).status_code == 403
    assert client.post("/api/cases/C-1003/execute", headers=aud, json={"approval_id": "x"}).status_code == 403
    r = client.post("/api/cases/C-1003/approvals", headers=aud,
                    json={"action": "approve", "approval_id": "x", "payload_hash": "y"})
    assert r.status_code == 403
    assert client.get("/api/audit", headers=aud).status_code == 200
    detail = client.get("/api/cases/C-1003", headers=aud).json()
    assert detail["customer"]["contact_phone"] == "[restricted]"


def test_specialist_cannot_read_tenant_audit(client, login):
    assert client.get("/api/audit", headers=login("u-spec-ava")).status_code == 403


def test_field_coordinator_cannot_approve_dispatch(client, login):
    d = investigate(client, login, "C-1003")
    r = client.post("/api/cases/C-1003/approvals", headers=login("u-field-dev"),
                    json={"action": "approve", "approval_id": d["approval"]["id"],
                          "payload_hash": d["recommendation"]["payload_hash"]})
    assert r.status_code == 403


def test_knowledge_scoped_by_tenant_and_role(client, login):
    r = client.get("/api/knowledge/search?q=planned maintenance end time", headers=login("u-spec-ava")).json()
    assert not any(x["document_id"] == "KB-S-101" for x in r["results"])
    r = client.get("/api/knowledge/search?q=planned maintenance end time", headers=login("u-spec-gil")).json()
    assert any(x["document_id"] == "KB-S-101" for x in r["results"])
    q = "contradictory evidence telemetry healthy escalate"
    spec = client.get(f"/api/knowledge/search?q={q}", headers=login("u-spec-ava")).json()
    net = client.get(f"/api/knowledge/search?q={q}", headers=login("u-net-chloe")).json()
    assert not any(x["document_id"] == "KB-NET-009" for x in spec["results"])
    assert any(x["document_id"] == "KB-NET-009" for x in net["results"])


def test_production_mode_disables_personas(client, monkeypatch):
    from app.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s.__class__, "is_demo", property(lambda self: False))
    assert client.post("/api/auth/demo-login", json={"persona_id": "u-spec-ava"}).status_code == 403
    r = client.get("/api/cases", headers={"Authorization": "Bearer anything"})
    assert r.status_code == 503 and r.json()["detail"]["code"] == "IDP_NOT_CONFIGURED"
    assert client.post("/api/demo/reset").status_code in (401, 503)
