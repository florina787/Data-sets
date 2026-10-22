"""FastAPI endpoints: health, validation, and the main flow."""

from fastapi.testclient import TestClient

from app.api.main import app
from app.requirements.analyzer import DEMO_CLARIFICATIONS, DEMO_REQUIREMENT

client = TestClient(app)
CLAIM = {"claim_id": "CLM-SYN-API", "member_id": "MBR-SYN-API", "provider_id": "PRV-SYN-API", "plan_id": "NSH-GOLD",
         "benefit_type": "PHYSIOTHERAPY", "service_date": "2026-08-03",
         "lines": [{"procedure_code": "PT-97110", "billed_amount": 100}]}


def test_30_health_endpoint():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["settings"]["demo_mode"] is True and body["paid_llm_calls"] == 0
    assert "SYNTHETIC" in body["notice"] and "sk-" not in r.text
    assert r.headers["X-Content-Type-Options"] == "nosniff"


def test_31_api_input_validation():
    assert client.post("/requirements/analyze", json={"text": "short"}).status_code == 422
    assert client.post("/requirements/analyze", json={"text": DEMO_REQUIREMENT, "persona": "Hacker"}).status_code == 422
    assert client.post("/requirements/analyze", json={"text": DEMO_REQUIREMENT, "extra": 1}).status_code == 422
    assert client.post("/claims/adjudicate", json={"claim": {"claim_id": "x"}}).status_code == 422
    bad = {**CLAIM, "lines": [{"procedure_code": "PT-97110", "billed_amount": -5}]}
    assert client.post("/claims/adjudicate", json={"claim": bad}).status_code == 422
    assert client.post("/claims/generate", json={"n_claims": 7}).status_code == 422
    assert client.post("/claims/adjudicate", json={"claim": CLAIM, "ruleset_id": "NOPE"}).status_code == 400
    assert client.post("/policy/upload", json={"filename": "evil.exe", "content": "x"}).status_code == 400
    assert client.get("/traceability/UNKNOWN-NODE").status_code == 404
    assert client.post("/tests/generate", json={"text": DEMO_REQUIREMENT}).status_code == 409  # needs clarification


def test_api_adjudicate_and_simulation():
    r = client.post("/claims/adjudicate", json={"claim": CLAIM, "context": {"prior_completed_visits": 10}})
    assert r.status_code == 200 and r.json()["reason_code"] == "AUTH_REQUIRED" and "no LLM" in r.json()["engine"]
    sim = client.post("/simulation/run", json={"n_claims": 1000}).json()
    assert sim["claims_simulated"] == 1000 and sim["unexpected_changes"] == 0


def test_api_release_flow_and_claimiq():
    body = {"text": DEMO_REQUIREMENT, "clarifications": DEMO_CLARIFICATIONS}
    a = client.post("/release/assess", json=body).json()
    assert a["status"] == "AWAITING_APPROVAL" and a["release_risk"]["decision"] in ("READY WITH APPROVAL", "READY")
    d = client.post("/release/deploy-simulated", json={**body, "approval": {"approver": "API RM", "decision": "APPROVED"}}).json()
    assert d["release"]["status"].startswith("DEPLOYED")
    assert client.get("/claimiq/metrics").json()["kpis"]["current_release"] == "2.4"
    assert client.post("/claimiq/detect-anomaly", json={}).json()["primary"]["detected"] is True
    inv = client.post("/claimiq/investigate", json={}).json()
    assert inv["status"] == "CLOSED_LOOP_COMPLETE" and inv["root_cause"]["changed_rule"] == "AUTH_RULE_184"
    assert client.post("/defects/generate").json()["defects"][0]["source_requirement"] == "BR-391"
    assert client.get("/use-cases").json()["counts"]["IMPLEMENTED"] >= 25
    assert client.get("/metrics").json()["paid_llm_calls"] == 0
