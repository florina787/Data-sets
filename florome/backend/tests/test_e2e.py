"""End to end: detect -> evidence -> hypotheses -> RCA -> plan -> approve -> execute (safe target) -> validate -> audit -> dashboard."""

from __future__ import annotations

from tests.conftest import H, approve, incident_id, sandbox


def test_full_incident_lifecycle(client):
    c = client
    # 1. Detect: the seeded incident is open and visible on the topology overlay.
    inc = incident_id(c)
    assert c.get(f"/api/v1/incidents/{inc}", headers=H("viewer")).json()["status"] == "open"

    # 2-4. Gather evidence, generate and test hypotheses, conclude.
    rep = c.post(f"/api/v1/rca/{inc}", headers=H("operator")).json()
    assert rep["evidence_collection"]["collected"] >= 15
    status = {h["title"].split(":")[0]: h["status"] for h in rep["hypotheses"] if h["role"] == "root_cause"}
    assert status["Deployment on ingest-orders"] == "confirmed"
    assert status["Config Change on revenue-api"] == "disproven"
    assert status["Deployment on revenue-api"] == "disproven"
    assert rep["conclusion"]["final_status"] == "confirmed"
    names = {a["name"]: a["role"] for a in rep["affected_systems"]}
    assert names["ingest-orders"] == "root" and "Daily revenue reporting" in names
    assert rep["business_impact"][0]["name"] == "Daily revenue reporting"
    topo = c.get("/api/v1/topology", headers=H("viewer")).json()
    roles = {n["name"]: (n["incident"] or {}).get("role") for n in topo["nodes"]}
    assert roles["ingest-orders"] == "root" and roles["revenue-api"] == "symptom" and roles["customer-portal"] is None

    # 5. Propose action.
    plan = c.post("/api/v1/remediations", json={"incident_id": inc}, headers=H("operator")).json()
    assert plan["status"] == "pending_approval"
    assert [s["action_id"] for s in plan["steps"]] == ["rollback_deployment", "replay_ingestion", "rerun_job", "refresh_cache", "create_ticket"]
    for s in plan["steps"]:
        for field in ("target_name", "params", "expected_outcome", "risk", "rollback", "required_permission"):
            assert s[field] is not None

    # Execution before approval is refused.
    r = c.post("/api/v1/executions", json={"plan_id": plan["id"]}, headers=H("operator"))
    assert r.status_code == 409 and "pending_approval" in r.json()["detail"]

    # 6. Approval by a different user.
    assert approve(c, plan).status_code == 201

    # 7-8. Execute against the sandbox and validate.
    out = c.post("/api/v1/executions", json={"plan_id": plan["id"]}, headers=H("operator")).json()
    assert out["status"] == "succeeded", out
    assert out["validations"][-1]["passed"] is True
    checks = {(ch["resource"], ch["check"]) for ch in out["validations"][-1]["checks"]}
    assert ("Daily revenue reporting", "business_outcome") in checks
    assert all(s["status"] == "succeeded" for s in out["steps"])
    assert sandbox(c).world.s.health  # sandbox really changed state
    assert set(sandbox(c).world.s.health.values()) == {"healthy"}

    # 9. Audit evidence persisted and the chain verifies.
    actions = [e["action"] for e in c.get("/api/v1/governance/audit?limit=200", headers=H("viewer")).json()["items"]]
    for a in ("rca.run", "plan.create", "plan.approve", "action.execute", "plan.execute"):
        assert a in actions
    assert c.get("/api/v1/governance/audit/verify", headers=H("viewer")).json()["valid"] is True
    execs = c.get(f"/api/v1/executions?plan_id={plan['id']}", headers=H("viewer")).json()
    assert len(execs) == 5 and all(x["status"] == "succeeded" and x["verification"] for x in execs)

    # 10. Dashboard reflects the outcome.
    assert c.get(f"/api/v1/incidents/{inc}", headers=H("viewer")).json()["status"] == "resolved"
    summary = c.get("/api/v1/analytics/summary", headers=H("viewer")).json()
    assert summary["incidents"]["resolved"] == 1 and summary["executions"]["succeeded"] == 5
    assert summary["rca"]["by_conclusion"] == {"confirmed": 1}
    topo = c.get("/api/v1/topology", headers=H("viewer")).json()
    assert all(n["incident"] is None for n in topo["nodes"]) and all(n["health"] == "healthy" for n in topo["nodes"])


def test_learning_similar_incident_lookup(client, db):
    from florome.models import Incident

    c = client
    inc = incident_id(c)
    c.post(f"/api/v1/rca/{inc}", headers=H("operator"))
    original = db.get(Incident, inc)
    twin = Incident(tenant_id=original.tenant_id, title="Earlier revenue outage", severity="sev3", status="resolved",
                    primary_resource_id=original.primary_resource_id, detected_at=original.detected_at,
                    fingerprint={**original.fingerprint, "outcome": {"resolved": True}}, is_demo=True)
    db.add(twin)
    db.commit()
    sim = c.get(f"/api/v1/incidents/{inc}/similar", headers=H("viewer")).json()
    assert sim[0]["incident_id"] == twin.id and sim[0]["similarity"] == 1.0 and sim[0]["outcome"] == {"resolved": True}


def test_step_progress_is_persisted_not_just_in_memory(client, db):
    """Regression: step statuses must survive a fresh read (JSON column change detection)."""
    from florome.models import RemediationPlan
    from tests.conftest import rca_and_plan

    _, plan = rca_and_plan(client)
    approve(client, plan)
    client.post("/api/v1/executions", json={"plan_id": plan["id"]}, headers=H("operator"))
    fresh = db.get(RemediationPlan, plan["id"])
    assert [s["status"] for s in fresh.steps] == ["succeeded"] * 5
    assert [s["status"] for s in client.get(f"/api/v1/remediations/{plan['id']}", headers=H("viewer")).json()["steps"]] == ["succeeded"] * 5
