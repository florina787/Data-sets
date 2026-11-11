"""Cross-tenant access: another tenant's objects are indistinguishable from missing ones."""

from __future__ import annotations

from tests.conftest import H, approve, rca_and_plan


def test_cross_tenant_reads_and_writes_are_404(client):
    c = client
    inc, plan = rca_and_plan(c)  # meridian
    ev_id = c.get(f"/api/v1/rca/{inc}", headers=H("viewer")).json()["timeline"][0]["evidence_id"]
    other = H("admin", "halcyon")
    for url in (f"/api/v1/incidents/{inc}", f"/api/v1/rca/{inc}", f"/api/v1/remediations/{plan['id']}", f"/api/v1/evidence/{ev_id}"):
        assert c.get(url, headers=other).status_code == 404, url
    assert c.post(f"/api/v1/rca/{inc}", headers=H("operator", "halcyon")).status_code == 404
    assert c.post("/api/v1/remediations", json={"incident_id": inc}, headers=H("operator", "halcyon")).status_code == 404
    assert c.post("/api/v1/executions", json={"plan_id": plan["id"]}, headers=other).status_code == 404
    body = {"plan_id": plan["id"], "decision": "approve", "plan_hash": plan["plan_hash"], "nonce": "x" * 20}
    assert c.post("/api/v1/approvals", json=body, headers=other).status_code == 404


def test_lists_are_tenant_scoped(client):
    c = client
    rca_and_plan(c)
    mine = c.get("/api/v1/incidents", headers=H("viewer")).json()["items"]
    theirs = c.get("/api/v1/incidents", headers=H("operator", "halcyon")).json()["items"]
    assert {i["id"] for i in mine}.isdisjoint({i["id"] for i in theirs})
    assert c.get("/api/v1/remediations", headers=H("operator", "halcyon")).json() == []
    res_m = {r["id"] for r in c.get("/api/v1/resources", headers=H("viewer")).json()}
    res_h = {r["id"] for r in c.get("/api/v1/resources", headers=H("admin", "halcyon")).json()}
    assert res_m.isdisjoint(res_h)


def test_audit_chains_are_per_tenant(client):
    c = client
    _, plan = rca_and_plan(c)
    approve(c, plan)
    m = c.get("/api/v1/governance/audit?limit=500", headers=H("viewer")).json()
    h = c.get("/api/v1/governance/audit?limit=500", headers=H("admin", "halcyon")).json()
    assert {e["id"] for e in m["items"]}.isdisjoint({e["id"] for e in h["items"]})
    assert c.get("/api/v1/governance/audit/verify", headers=H("admin", "halcyon")).json()["valid"]
