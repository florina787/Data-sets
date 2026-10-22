"""FastAPI endpoints use the shared service layer."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.scenarios import scenario_request


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# 12
def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["demo_mode"] is True
    assert body["live_ai_available"] is False
    assert "key" not in " ".join(k for k in body if k != "live_ai_available").lower()


def test_assessment_endpoint(client):
    payload = scenario_request("banking-transaction-rules").model_dump(mode="json")
    r = client.post("/assessment", json=payload)
    assert r.status_code == 200
    d = r.json()["decision"]
    assert d["agentic_verdict"] == "not_recommended"
    assert d["primary_architecture"] == "keep_existing"
    assert r.json()["trace"]["paid_model_calls"] == 0


def test_architecture_recommend(client):
    payload = scenario_request("finops-incident-investigation").model_dump(mode="json")
    r = client.post("/architecture/recommend", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["decision"]["agentic_verdict"] == "constrained"
    assert any(m["component"] == "LangGraph AI Orchestrator" and m["decision"] == "ADD" for m in body["matrix"])


def test_cost_simulate(client):
    r = client.post("/cost/simulate", json={"architecture": "rag_genai", "cost_inputs": {"requests_per_month": 10000}})
    assert r.status_code == 200
    assert r.json()["model_cost_month"] > 0
    again = client.post("/cost/simulate", json={"architecture": "rag_genai", "cost_inputs": {"requests_per_month": 10000}})
    assert again.json() == r.json()


def test_cost_simulate_unknown_model_is_422(client):
    r = client.post("/cost/simulate", json={"architecture": "rag_genai", "cost_inputs": {"primary_model": "nope"}})
    assert r.status_code == 422


def test_roi_calculate(client):
    r = client.post("/roi/calculate", json={"roi_inputs": {"tasks_per_month": 50, "minutes_per_task": 5}, "ai_operating_cost_annual": 50000})
    assert r.status_code == 200
    assert r.json()["verdict"] == "ROI DOES NOT JUSTIFY AI"


def test_scenarios_and_scenario_assessment(client):
    items = client.get("/scenarios").json()
    assert len(items) >= 5
    r = client.post(f"/scenarios/{items[0]['id']}/assessment")
    assert r.status_code == 200
    assert client.get("/scenarios/does-not-exist").status_code == 404
    assert client.post("/scenarios/does-not-exist/assessment").status_code == 404


def test_metrics_and_decision_options(client):
    client.post("/scenarios/legal-research/assessment")
    m = client.get("/metrics").json()
    assert m["counters"]["assessments_total"] >= 1
    assert m["counters"].get("paid_llm_calls_total", 0) == 0
    opts = client.get("/decision-options").json()
    assert {o["id"] for o in opts["architecture_options"]} >= {"keep_existing", "agentic_ai", "hybrid"}
    assert "DO NOT USE AI" in opts["negative_recommendations_supported"]


def test_adr_markdown_export(client):
    payload = scenario_request("legal-research").model_dump(mode="json")
    r = client.post("/assessment/adr", json=payload)
    assert r.status_code == 200
    assert r.text.startswith("# ADR:")
    for section in ("## Business problem", "## Rejected alternatives", "## Security implications", "## Conditions requiring reassessment"):
        assert section in r.text


def test_invalid_payload_rejected(client):
    r = client.post("/assessment", json={"use_case": {"deterministic_requirement": 9}})
    assert r.status_code == 422


def test_workflow_mermaid(client):
    r = client.get("/workflow/mermaid")
    assert r.status_code == 200
    assert "decision_engine" in r.text and "challenger" in r.text
