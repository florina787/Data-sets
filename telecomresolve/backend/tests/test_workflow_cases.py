from conftest import approve, execute, investigate


def evidence(client, login, cid, persona="u-spec-ava"):
    return client.get(f"/api/cases/{cid}/evidence", headers=login(persona)).json()


def test_primary_journey_end_to_end(client, login):
    d = investigate(client, login, "C-1003")
    assert d["status"] == "AWAITING_APPROVAL"
    rec = d["recommendation"]
    assert rec["action_type"] == "create_technician_dispatch"
    restart = next(p for p in rec["prior_interventions"] if p["action"] == "modem_restart")
    assert restart["repeated_in_recommendation"] is False and "not repeated" in restart["justification"]
    ev = evidence(client, login, "C-1003")
    top = ev["hypotheses"][0]
    assert top["category"] == "LINE_IMPAIRMENT" and top["sufficiency"] == "strong"
    assert top["statement"].startswith("Suspected cause")
    # observations (measured) are separate from statements
    kinds = {i["ref_id"]: i["kind"] for i in ev["items"]}
    assert kinds["DIAG-SNR"] == "observation" and kinds["STATEMENT"] == "statement"
    # specialist (proposer) cannot approve; supervisor can
    assert approve(client, login, "C-1003", d, persona="u-spec-ava").status_code == 403
    assert approve(client, login, "C-1003", d).status_code == 200
    r = execute(client, login, "C-1003", d["approval"]["id"])
    assert r.status_code == 200 and r.json()["case"]["status"] == "VERIFYING"
    assert "not that service is restored" in r.json()["execution"]["result"]["note"]
    v = client.post("/api/cases/C-1003/verify", headers=login("u-spec-ava"), json={}).json()
    assert v["case"]["status"] == "RESOLVED" and v["recovery"]["simulation_time"] is True
    replay = client.get("/api/cases/C-1003/audit/replay", headers=login("u-sup-emma")).json()
    assert replay["hash_chain_valid"] and replay["status_matches"] and not replay["illegal_transitions"]
    assert replay["recommendations"][0]["evidence"]


def test_citation_record_opens_exact_source(client, login):
    investigate(client, login, "C-1003")
    r = client.get("/api/cases/C-1003/evidence/DIAG-SNR", headers=login("u-spec-ava")).json()
    assert r["resolves"] and len(r["record"]["samples"]) == len(r["item"]["data"]["sample_ids"]) >= 20
    ev = evidence(client, login, "C-1003")
    kb = next(i for i in ev["items"] if i["source_type"] == "knowledge")
    from urllib.parse import quote

    r = client.get(f"/api/cases/C-1003/evidence/{quote(kb['ref_id'], safe='')}",
                   headers=login("u-spec-ava")).json()
    assert r["resolves"] and r["item"]["excerpt"] in r["record"]["text"]


def test_stale_diagnostics_produce_request_not_diagnosis(client, login):
    d = investigate(client, login, "C-1004")
    assert d["status"] == "NEEDS_INFORMATION"
    assert d["recommendation"] is None
    ev = evidence(client, login, "C-1004")
    assert ev["diagnosis"]["conclusion"] == "INSUFFICIENT_EVIDENCE"
    assert "fresh_line_diagnostics" in ev["snapshot"]["missing_evidence"]
    audit = client.get("/api/cases/C-1004/audit", headers=login("u-spec-ava")).json()
    collected = [e for e in audit if e["event_type"] == "EVIDENCE_COLLECTED"]
    assert len(collected) == 2  # evidence loop ran again for the specific missing signal
    tools = [t["tool"] for t in collected[1]["detail"]["tool_calls"]]
    assert "on_demand_line_test" in tools
    needs = next(e for e in audit if e["to_status"] == "NEEDS_INFORMATION")
    assert needs["detail"]["clarifying_questions"]
    # a clarification is a statement, not a measurement: still insufficient
    r = client.post("/api/cases/C-1004/clarifications", headers=login("u-spec-ava"),
                    json={"text": "Drops happen every evening, wired devices too.", "wait": True})
    assert r.status_code == 200
    assert client.get("/api/cases/C-1004", headers=login("u-spec-ava")).json()["status"] == "NEEDS_INFORMATION"


def test_contradictory_evidence_escalates_and_proximity_is_not_cause(client, login):
    d = investigate(client, login, "C-1005")
    assert d["status"] == "ESCALATED" and d["recommendation"] is None
    ev = evidence(client, login, "C-1005")
    near = next(i for i in ev["items"] if i["source_id"] == "INC-7003")
    assert "proximity_only" in near["flags"] and not near["supports"]
    assert all(h["category"] != "AREA_INCIDENT" for h in ev["hypotheses"])
    assert ev["diagnosis"]["conclusion"] == "CONTRADICTORY_EVIDENCE"


def test_area_incident_requires_mapping_and_time_overlap(client, login):
    d = investigate(client, login, "C-1001")
    assert d["recommendation"]["action_type"] == "associate_case_with_incident"
    assert d["recommendation"]["payload"]["incident_id"] == "INC-7001"
    ev = evidence(client, login, "C-1001")
    inc = next(i for i in ev["items"] if i["source_id"] == "INC-7001")
    assert {"mapped_path", "time_overlap"} <= set(inc["flags"])
    assert "MAPPING" in d["recommendation"]["evidence_refs"]
    dispatch = next(a for a in d["recommendation"]["alternatives"] if a["action_type"] == "create_technician_dispatch")
    assert not dispatch["allowed"] and any("active_mapped_incident" in r for r in dispatch["reasons"])
    # same incident appears for C-1003 only as proximity, never as cause
    investigate(client, login, "C-1003")
    ev3 = evidence(client, login, "C-1003")
    near = next(i for i in ev3["items"] if i["source_id"] == "INC-7001")
    assert "proximity_only" in near["flags"]


def test_closed_incident_not_inherited(client, login):
    d = investigate(client, login, "C-1006")
    ev = evidence(client, login, "C-1006")
    inc = next(i for i in ev["items"] if i["source_id"] == "INC-7002")
    assert "not_applicable" in inc["flags"] and not inc["supports"]
    assert ev["diagnosis"]["conclusion"] == "LINE_IMPAIRMENT"
    assert d["recommendation"]["action_type"] != "associate_case_with_incident"


def test_restoration_guarantee_and_credit_refused(client, login):
    d = investigate(client, login, "C-1007")
    refused = {r["request"]: r for r in d["recommendation"]["refused_requests"]}
    g = refused["Guaranteed restoration time"]
    assert "No restoration estimate is published" in g["reason"] and g["citations"]
    assert "Bill credit / compensation" in refused
    msg = client.post("/api/cases/C-1007/messages", headers=login("u-spec-ava"),
                      json={"text": "When will the internet be restored? Can you guarantee 5pm?"}).json()
    assert msg["generation_mode"] == "POLICY" and "No restoration time can be promised" in msg["text"]


def test_prompt_injection_quarantined(client, login):
    d = investigate(client, login, "C-1008")
    ev = evidence(client, login, "C-1008")
    note = next(i for i in ev["items"] if i["source_id"] == "INT-1008-1")
    assert "prompt_injection" in note["flags"]
    assert "ignore all previous instructions" not in note["excerpt"].lower()
    assert "quarantined" in note["excerpt"]
    assert d["recommendation"]["action_type"] == "suggest_customer_troubleshooting"
    assert any("Instructions embedded" in r["request"] for r in d["recommendation"]["refused_requests"])
    hist = next(h for h in d["support_history"] if h["id"] == "INT-1008-1")
    assert hist["untrusted_content_flag"] and "bill credit" not in hist["notes"]
    audit = client.get("/api/cases/C-1008/audit", headers=login("u-spec-ava")).json()
    assert any(e["event_type"] == "PROMPT_INJECTION_QUARANTINED" for e in audit)


def test_supervisor_rejection(client, login):
    d = investigate(client, login, "C-1009")
    r = approve(client, login, "C-1009", d, decision="reject", reason="")
    assert r.status_code == 422  # reason required
    r = approve(client, login, "C-1009", d, decision="reject", reason="Run a repeat line test first")
    assert r.status_code == 200
    assert client.get("/api/cases/C-1009", headers=login("u-spec-ava")).json()["status"] == "REJECTED"
    assert execute(client, login, "C-1009", d["approval"]["id"]).status_code == 409


def test_alternative_action_requires_new_approval(client, login):
    d = investigate(client, login, "C-1001")
    r = client.post("/api/cases/C-1001/recommendations", headers=login("u-spec-ava"),
                    json={"action_type": "draft_customer_update"})
    assert r.status_code == 200, r.text
    new = client.get("/api/cases/C-1001", headers=login("u-spec-ava")).json()
    assert new["recommendation"]["action_type"] == "draft_customer_update"
    assert new["approval"]["id"] != d["approval"]["id"] and new["approval"]["status"] == "pending"
    # old approval can no longer be used
    old = client.post("/api/cases/C-1001/approvals", headers=login("u-spec-ava"),
                      json={"action": "approve", "approval_id": d["approval"]["id"],
                            "payload_hash": d["recommendation"]["payload_hash"]})
    assert old.status_code == 409
    blocked = client.post("/api/cases/C-1001/recommendations", headers=login("u-spec-ava"),
                          json={"action_type": "create_technician_dispatch"})
    assert blocked.status_code == 409


def test_concurrent_investigation_rejected(client, login):
    from app.db import session_scope
    from app.models.orm import Case

    with session_scope() as db:
        db.get(Case, "C-1002").active_job = "JOB-other"
    r = client.post("/api/cases/C-1002/investigate?wait=true", headers=login("u-spec-ben"))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "INVESTIGATION_IN_PROGRESS"
