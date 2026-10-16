"""API integration tests via HTTPX TestClient."""

import pytest

pytestmark = pytest.mark.integration


def test_health_and_public_config(client):
    h = client.get("/api/v1/health").json()
    assert h["status"] == "ok" and h["data_mode"] == "SYNTHETIC"
    cfg = client.get("/api/v1/config/public").json()
    assert cfg["demo_banner"] == "DEMONSTRATION DATA - NOT LIVE APPOINTMENT AVAILABILITY"
    assert "not a licensed physician" in cfg["christina_disclaimer"]
    assert 25 in cfg["radii_km"]


def test_request_id_and_security_headers(client):
    r = client.get("/api/v1/health", headers={"X-Request-ID": "abc123"})
    assert r.headers["X-Request-ID"] == "abc123" and r.headers["X-Frame-Options"] == "DENY"


def test_openapi_documents_required_routes(client):
    paths = client.get("/openapi.json").json()["paths"]
    for p in ["/api/v1/copilot/chat", "/api/v1/search/facilities", "/api/v1/search/appointments",
              "/api/v1/facilities", "/api/v1/facilities/{facility_id}", "/api/v1/appointments/{slot_id}",
              "/api/v1/bookings/request", "/api/v1/bookings/{booking_id}", "/api/v1/workflows/start",
              "/api/v1/workflows/{workflow_id}", "/api/v1/workflows/{workflow_id}/events",
              "/api/v1/approvals/{approval_id}/decision", "/api/v1/agents", "/api/v1/agents/metrics",
              "/api/v1/sdlc/requirements", "/api/v1/sdlc/requirements/analyze", "/api/v1/sdlc/architecture",
              "/api/v1/sdlc/tests/run", "/api/v1/sdlc/releases", "/api/v1/telemetry", "/api/v1/health"]:
        assert p in paths, p


def test_chat_patient_journey(client, patient):
    r = client.post("/api/v1/copilot/greet", json={}, headers=patient).json()
    assert "I'm Christina" in r["reply"] and r["avatar_state"] == "greeting"
    sid = r["session_id"]
    r = client.post("/api/v1/copilot/chat", json={"message": "I need an MRI. My appointment is three months away.",
                                                  "session_id": sid}, headers=patient).json()
    assert "requisition" in r["reply"].lower()
    r = client.post("/api/v1/copilot/chat", json={"message": "Yes, I have a requisition", "session_id": sid},
                    headers=patient).json()
    assert "city or postal code" in r["reply"]
    r = client.post("/api/v1/copilot/chat", json={"message": "Toronto. Search within 25 kilometres.",
                                                  "session_id": sid}, headers=patient).json()
    wf = r["workflow"]
    assert wf["workflow_status"] == "COMPLETED" and wf["radius_km"] == 25
    assert wf["wait_summary"]["existing_wait_days"] == 90 and r["avatar_state"] == "celebrating"
    assert any("DEMONSTRATION DATA" in w for w in r["warnings"])


def test_chat_emergency_and_rag(client, patient):
    r = client.post("/api/v1/copilot/chat", json={"message": "I have chest pain, need a CT"}, headers=patient).json()
    assert r["avatar_state"] == "warning" and "911" in r["reply"] and r["workflow"] is None
    r = client.post("/api/v1/copilot/chat", json={"message": "What does advertised unverified mean?"},
                    headers=patient).json()
    assert r["citations"] and r["citations"][0]["document_id"] == "KB-PLATFORM-001"


def test_search_endpoints(client, patient):
    r = client.post("/api/v1/search/facilities", json={"service": "MRI", "location": "M5V", "radius_km": 10},
                    headers=patient)
    assert r.status_code == 200 and all(x["geo"]["straight_km"] <= 10 for x in r.json()["results"])
    assert client.post("/api/v1/search/facilities", json={"service": "MRI", "location": "Atlantis", "radius_km": 10},
                       headers=patient).status_code == 422
    assert client.post("/api/v1/search/facilities", json={"service": "MRI", "location": "Toronto", "radius_km": 7},
                       headers=patient).status_code == 422
    r = client.post("/api/v1/search/appointments", json={"service": "CT", "location": "North York", "radius_km": 10,
                                                         "requisition_status": "HAS_REQUISITION"}, headers=patient)
    body = r.json()
    assert r.status_code == 200 and body["workflow_status"] in {"COMPLETED", "AWAITING_PATIENT_DECISION"}
    ev = client.get(f"/api/v1/workflows/{body['workflow_id']}/events", headers=patient).json()
    assert ev["agent_trace"] and ev["audit_events"]


def test_facilities_pagination_and_detail(client, patient):
    r = client.get("/api/v1/facilities?limit=5&offset=0", headers=patient).json()
    assert len(r["items"]) == 5 and r["total"] > 5
    d = client.get("/api/v1/facilities/FAC-001", headers=patient).json()
    assert d["facility"]["is_synthetic"] and d["integration"]["id"] == "INT-SYN-A"
    assert client.get("/api/v1/facilities/NOPE", headers=patient).status_code == 404
    s = client.get("/api/v1/appointments/SLOT-004-007", headers=patient).json()
    assert s["slot"]["verification_status"] == "ADVERTISED_UNVERIFIED"


def test_booking_api_flow(client, patient):
    client.post("/api/v1/consents", json={"consent_type": "notifications", "granted": True}, headers=patient)
    s = client.post("/api/v1/search/appointments", json={"service": "MRI", "location": "Toronto", "radius_km": 25,
                                                         "requisition_status": "HAS_REQUISITION"},
                    headers=patient).json()
    slot = s["recommendations"][0]["slot_id"]
    req = {"search_workflow_id": s["workflow_id"], "slot_id": slot, "idempotency_key": "api-test-key-0001",
           "consent": True}
    b = client.post("/api/v1/bookings/request", json=req, headers=patient).json()
    assert b["workflow_status"] == "AWAITING_APPROVAL" and b["approval_id"]
    again = client.post("/api/v1/bookings/request", json=req, headers=patient).json()
    assert again["idempotent_replay"] and again["booking"]["id"] == b["booking"]["id"]
    pend = client.get("/api/v1/approvals", headers=patient).json()["items"]
    a = next(x for x in pend if x["id"] == b["approval_id"])
    assert a["evidence"] and a["consequences"] and a["requesting_agent"] == "booking_assistance"
    d = client.post(f"/api/v1/approvals/{b['approval_id']}/decision", json={"decision": "APPROVED"},
                    headers=patient).json()
    assert d["workflow"]["booking_status"] == "HANDOFF_PREPARED"
    bk = client.get(f"/api/v1/bookings/{b['booking']['id']}", headers=patient).json()
    assert bk["status"] == "HANDOFF_PREPARED" and bk["is_confirmed_booking"] is False
    assert client.post(f"/api/v1/approvals/{b['approval_id']}/decision", json={"decision": "APPROVED"},
                       headers=patient).status_code == 409  # cannot decide twice
    n = client.get("/api/v1/notifications", headers=patient).json()["items"]
    assert n and "MRI" not in n[0]["body"]  # no health details in notifications
    r = client.post(f"/api/v1/bookings/{bk['id']}/patient-reported", headers=patient).json()
    assert r["status"] == "PATIENT_REPORTED_BOOKED" and r["is_confirmed_booking"] is False


def test_booking_requires_consent(client, patient):
    s = client.post("/api/v1/search/appointments", json={"service": "MRI", "location": "Toronto"},
                    headers=patient).json()
    r = client.post("/api/v1/bookings/request", json={"search_workflow_id": s["workflow_id"], "slot_id": "x",
                                                      "idempotency_key": "nocons-0001", "consent": False},
                    headers=patient)
    assert r.status_code == 400


def test_preferences_history_and_deletion(client, patient):
    p = client.put("/api/v1/preferences", json={"default_radius_km": 50, "prefer_transit": True}, headers=patient)
    assert p.status_code == 200 and client.get("/api/v1/preferences", headers=patient).json()["default_radius_km"] == 50
    assert client.put("/api/v1/preferences", json={"default_radius_km": 7}, headers=patient).status_code == 422
    h = client.get("/api/v1/searches/history", headers=patient).json()["items"]
    assert h and client.post(f"/api/v1/searches/{h[0]['id']}/save", headers=patient).json()["saved"]
    assert client.get("/api/v1/searches/history?saved=true", headers=patient).json()["items"]


def test_engineering_endpoints(client, engineer):
    names = {a["name"] for a in client.get("/api/v1/agents", headers=engineer).json()["agents"]}
    from app.agents.registry import PATIENT_AGENTS, SDLC_AGENTS

    assert len(PATIENT_AGENTS) == 20 and len(SDLC_AGENTS) == 8
    assert {a.name for a in PATIENT_AGENTS + SDLC_AGENTS} <= names
    m = client.get("/api/v1/agents/metrics", headers=engineer).json()
    assert m["measured"] and m["agents"]
    a = client.post("/api/v1/sdlc/requirements/analyze",
                    json={"requirement": "Patients should be able to find MRI appointments within 25 km."},
                    headers=engineer).json()
    assert a["status"] == "NEEDS_CLARIFICATION"
    arch = client.get("/api/v1/sdlc/architecture", headers=engineer).json()
    assert arch["patient_workflow"]["mermaid"].startswith("---") or "graph" in arch["patient_workflow"]["mermaid"]
    t = client.post("/api/v1/sdlc/tests/run", json={"build_version": "1.5.0"}, headers=engineer).json()
    assert t["failed"] == 3
    sim = client.post("/api/v1/sdlc/simulations", json={"volume": 30}, headers=engineer).json()
    assert sim["synthetic"] and sim["searches"] == 30
    tel = client.get("/api/v1/telemetry", headers=engineer).json()
    assert tel["tracing"]["langsmith"]["redaction"] == "enabled" and "infrastructure" in tel
    tb = client.get("/api/v1/telemetry/token-benchmark", headers=engineer).json()
    assert tb["optimized_chars"] < tb["baseline_chars"]
    assert "medaccess_http_requests_total" in client.get("/api/v1/metrics").text


def test_sdlc_demo_over_api(client, engineer, approver):
    r = client.post("/api/v1/sdlc/demo/start", json={"simulation_volume": 20}, headers=engineer).json()
    run = r["run_id"]
    r = client.post(f"/api/v1/approvals/{r['approval_id']}/decision",
                    json={"decision": "APPROVED", "answer": "Only verified appointments."}, headers=engineer).json()
    wf = r["workflow"]
    assert wf["status"] == "AWAITING_RELEASE_APPROVAL"
    assert client.post(f"/api/v1/approvals/{wf['approval_id']}/decision", json={"decision": "APPROVED"},
                       headers=engineer).status_code == 403
    r = client.post(f"/api/v1/approvals/{wf['approval_id']}/decision", json={"decision": "APPROVED"},
                    headers=approver).json()
    assert r["workflow"]["status"] == "COMPLETED"
    tr = client.get(f"/api/v1/sdlc/demo/{run}/traceability", headers=engineer).json()["chain"]
    assert len(tr) >= 14
    art = client.get(f"/api/v1/sdlc/demo/{run}/artifacts/root_cause", headers=engineer).json()
    assert art["content"]["confirmed"]


def test_governance_and_audit(client, admin):
    g = client.get("/api/v1/governance/overview", headers=admin).json()
    assert g["audit_chain"]["valid"] and g["mcp_servers"] and g["agent_permissions"]
    assert client.get("/api/v1/governance/audit/verify", headers=admin).json()["valid"]
    assert client.post("/api/v1/admin/demo/reset", headers=admin).json()["reset"]


def test_validation_error_envelope(client, patient):
    r = client.post("/api/v1/search/appointments", json={"radius_km": 500}, headers=patient)
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"
