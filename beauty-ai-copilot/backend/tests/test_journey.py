"""Seeded BR-101 journey through the HTTP API, computed from fixtures (no hard-coded results)."""
from tests.conftest import H


def test_seeded_change_needs_clarification(journey):
    d = journey.get()
    assert d["change"]["status"] == "NEEDS_CLARIFICATION"
    keys = {c["key"] for c in d["clarifications"]}
    assert keys == {"correct_match", "group_definitions", "lighting_protocol", "reference_labels", "acceptable_regression",
                    "supported_devices", "recapture", "release_evidence"}
    assert d["interrupt"]["interrupt"]["awaiting"] == "clarification_answers"


def test_requirement_approval_creates_versioned_criteria(journey):
    journey.approve_requirements()
    d = journey.get()
    assert d["change"]["status"] == "REQUIREMENTS_APPROVED"
    approved = [r for r in d["requirement_versions"] if r["status"] == "APPROVED"]
    assert len(approved) == 1 and approved[0]["version"] == 2
    codes = {c["code"]: c["gate_id"] for c in approved[0]["acceptance_criteria"]}
    assert codes["AC-1"] == "G-TARGET" and codes["AC-2"] == "G-NO-REGRESSION" and codes["AC-3"] == "G-SAMPLES"


def test_evidence_citations_resolve_and_flags(journey):
    journey.approve_requirements()
    out = journey.ok(journey.c.post("/api/changes/BR-101/investigate", headers=H("u-ml-eng")))
    ev = out["evidence"]
    assert ev["missing_required"] == []
    for c in ev["citations"]:
        r = journey.c.get(f"/api/evidence/{c['source_id']}/{c['source_version']}/{c['section']}", headers=H("u-ml-eng"))
        assert r.status_code == 200 and r.json()["excerpt"] == c["excerpt"]
    assert any("outdated" in " ".join(c["flags"]) for c in ev["citations"]) or ev["conflicts"]
    assert ev["injection_flags"], "vendor note instruction text must be flagged"
    assert all(u["status"] == "UNKNOWN" for u in ev["unsupported_claims"])
    assert journey.get()["change"]["status"] == "IMPACT_REVIEW"
    assert any("DEV-T3" in r["risk"] for r in out["impact"]["risks"])


def test_failing_candidate_hides_subgroup_regression_and_blocks(journey):
    journey.to_development()
    journey.candidate("shade-matcher-v2.4.0-rc1")
    run = journey.evaluate()
    s = run["summary"]
    assert run["status"] == "SUCCEEDED" and run["outcome"] == "FAIL"
    assert s["overall"]["delta"]["top1_delta_pp"] > 0  # aggregate improves
    worst = min(s["cells"].items(), key=lambda kv: kv[1]["delta"]["top1_delta_pp"])
    assert worst[0] == "TS-3|cool_fluorescent" and worst[1]["delta"]["top1_delta_pp"] < -2.0
    g = {x["gate_id"]: x for x in s["gates"]}
    assert g["G-NO-REGRESSION"]["status"] == "FAIL" and g["G-TARGET"]["status"] == "PASS"
    # paired: both models scored on the same eligible samples
    assert all(v["baseline"]["n_eligible"] == v["candidate"]["n_eligible"] >= 100 for v in s["cells"].values())
    assert journey.get()["change"]["status"] == "EVALUATION_FAILED"
    # release approval impossible from this state
    r = journey.c.post("/api/changes/BR-101/release-approvals", headers=H("u-release"), json={"decision": "APPROVED"})
    assert r.status_code == 409


def test_corrected_candidate_passes_and_full_release_rollback_flow(journey):
    journey.to_development()
    journey.candidate("shade-matcher-v2.4.0-rc1")
    assert journey.evaluate()["outcome"] == "FAIL"
    journey.candidate("shade-matcher-v2.4.0-rc2")
    journey.ok(journey.c.post("/api/changes/BR-101/reviews", headers=H("u-qa"), json={"kind": "code", "decision": "APPROVE"}))
    run = journey.evaluate()
    assert run["outcome"] == "PASS", [g for g in run["summary"]["gates"] if g["status"] != "PASS"]
    assert journey.get()["change"]["status"] == "REVIEW_REQUIRED"
    journey.reviews()
    journey.ok(journey.c.post("/api/changes/BR-101/release-approvals", headers=H("u-release"), json={"decision": "APPROVED"}), 201)
    rel = journey.ok(journey.release(), 201)["release"]
    assert rel["status"] == "CANARY" and rel["allocation_pct"] == 5 and rel["mode"] == "simulated"
    c = journey.c
    alert = None
    for i in range(8):
        w = journey.ok(c.post(f"/api/releases/{rel['id']}/monitoring/advance", headers=H("u-ops")))
        if w["new_alerts"]:
            alert = w["new_alerts"][0]
            break
        journey.ok(c.post(f"/api/releases/{rel['id']}/promote", headers=H("u-release")))
    assert alert and alert["scope"] == "DEV-T3|warm_indoor"
    inv = journey.ok(c.post(f"/api/alerts/{alert['id']}/investigate", headers=H("u-ops")))["investigation"]
    assert "lpm-v2" in inv["suspected_cause"]["hypothesis"] and "cool_fluorescent" in inv["suspected_cause"]["hypothesis"]
    assert any("does not prove root cause" in x for x in inv["caveats"])
    assert journey.get()["change"]["status"] == "ROLLBACK_RECOMMENDED"
    rb = journey.ok(c.post(f"/api/releases/{rel['id']}/rollback-requests", headers=H("u-ops", **{"Idempotency-Key": "rb-1"}),
                           json={"reason": "DEV-T3 warm regression", "alert_id": alert["id"]}), 201)["rollback"]
    # requester cannot approve; ops lacks the permission anyway
    assert c.post(f"/api/rollbacks/{rb['id']}/decision", headers=H("u-ops"), json={"decision": "APPROVE"}).status_code == 403
    done = journey.ok(c.post(f"/api/rollbacks/{rb['id']}/decision", headers=H("u-release"), json={"decision": "APPROVE"}))
    assert done["status"] == "EXECUTED" and done["target_model_id"] == "shade-matcher-v2.3.0"
    assert journey.get()["change"]["status"] == "ROLLED_BACK"
    audit = journey.ok(c.get("/api/changes/BR-101/audit", headers=H("u-po")))
    assert audit["chain"]["valid"]
    trace = journey.ok(c.get("/api/changes/BR-101/traceability", headers=H("u-po")))["chain"]
    types = {x["type"] for x in trace}
    assert {"requirement", "clarification", "revision", "dataset", "evaluation", "policy_decision", "review", "approval",
            "release", "monitoring", "rollback", "alert"} <= types
    md = c.get("/api/changes/BR-101/report", headers=H("u-po")).text
    assert "TS-3|cool_fluorescent" in md and "G-NO-REGRESSION" in md and "synthetic" in md


def test_agent_invocations_recorded_with_real_latency(journey):
    journey.approve_requirements()
    d = journey.get()
    inv = d["agent_invocations"]
    assert inv and all(i["latency_ms"] >= 0 and i["language_mode"] == "deterministic" for i in inv)
    assert all(i["input_tokens"] == 0 and (i["cost_usd"] in (None, 0)) for i in inv)
    t = journey.ok(journey.c.get("/api/changes/BR-101/telemetry", headers=H("u-po")))
    assert t["by_agent"]["requirements"]["invocations"] >= 2


def test_copilot_answers_from_state(journey):
    journey.to_development()
    journey.candidate("shade-matcher-v2.4.0-rc1")
    journey.evaluate()
    a = journey.ok(journey.c.post("/api/changes/BR-101/copilot", headers=H("u-po"), json={"message": "why is release blocked?"}))
    assert "G-NO-REGRESSION" in a["answer"]


def test_process_metrics_have_definitions(journey):
    journey.to_development()
    journey.candidate("shade-matcher-v2.4.0-rc1")
    journey.evaluate()
    m = journey.ok(journey.c.get("/api/metrics/process", headers=H("u-po")))["metrics"]
    assert m["regressions_caught_before_release"]["value"] == 1
    for v in m.values():
        assert {"numerator", "denominator", "window", "exclusions", "source"} <= set(v)
