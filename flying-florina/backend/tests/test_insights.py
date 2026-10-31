from tests.conftest import login


def test_command_center_kpis_and_filters_are_consistent(client):
    h = login(client, "planner.marco")
    all_ = client.get("/api/command/overview", headers=h).json()["data"]
    k = all_["kpis"]
    assert k["total_aircraft"] == 150 and k["aog"] == sum(v for s, v in all_["status"].items() if s == "aog")
    parts = [client.get(f"/api/command/overview?base={b}", headers=h).json()["data"]["kpis"]["total_aircraft"] for b in ("MAIN-HUB", "NORTH-FIELD", "EAST-DEPOT")]
    assert sum(parts) == 150  # drill-down by base adds up to the fleet total
    assert k["predicted_maintenance_events"] is None  # no trained model: not invented
    assert "SIMULATION" in k["simulated_downtime_exposure_usd"]["label"]
    guest = client.get("/api/command/overview", headers=login(client, "guest"))
    assert guest.status_code == 403


def test_predictive_scores_are_labelled_and_rank_ac204_first(client):
    d = client.get("/api/predictive/overview", headers=login(client, "rel.nadia")).json()["data"]
    assert "no trained model" in d["method"]["type"] and "No accuracy" in d["method"]["accuracy"]
    assert d["scores"][0]["aircraft"] == "AC-204" and d["scores"][0]["priority"] == "high"
    assert sum(x["aircraft"] for x in d["distribution"]) == len(d["scores"])


def test_predictive_explain_reports_qwen_absence_instead_of_inventing(client):
    r = client.post("/api/predictive/explain", headers=login(client, "rel.nadia"), json={"aircraft_id": "AC-204"}).json()["data"]
    assert r["available"] is False and "explanation" not in r


def test_observability_endpoints_report_measured_values(client):
    h = login(client, "sec.ines")
    client.post("/api/chat/query", headers=h, json={"query": "Show me fleet health overview"})
    w = client.get("/api/observability/workflows", headers=h).json()["data"]
    assert w["runs"] >= 1 and w["by_agent"] and w["success_rate"] is not None
    ev = client.get("/api/observability/eval", headers=h).json()["data"]
    assert any(e["split"] == "test_v2" for e in ev)
    m = client.get("/api/llm/metrics", headers=h).json()["data"]
    assert m["status"]["external_fallback"] is False and "system" in m


def test_llm_test_endpoint_refuses_honestly_without_qwen(client):
    r = client.post("/api/llm/test", headers=login(client, "planner.marco"), json={})
    assert r.status_code == 503 and r.json()["code"] == "qwen_unavailable"


def test_modernization_blueprint_export(client):
    h = login(client, "arch.olu")
    rep = client.post("/api/reports/generate", headers=h, json={"kind": "modernization_blueprint", "fmt": "md"}).json()["data"]
    text = client.get(rep["download"], headers=h).text
    for section in ("Current-state architecture", "Proposed target architecture", "Candidate API contracts", "Security considerations",
                    "Data migration assumptions", "Test strategy", "Rollback considerations", "Human review requirements", "PROPOSAL"):
        assert section in text
