import re

from app.core import db
from app.core.security import load_actor
from app.integrations.mcp.registry import invocation_count
from app.workflows import orchestrator
from app.workflows.engine import events

AC204 = "Investigate abnormal vibration on AC-204, retrieve maintenance evidence, check parts and draft a maintenance plan."


def test_maintenance_graph_executes_real_steps_with_evidence():
    s = orchestrator.start(load_actor("planner.marco"), AC204)
    assert s.status == "awaiting_approval"
    ev = events(s.run_id)
    done = {e["step"] for e in ev if e["status"] == "completed"}
    for step in ["intake", "policy_precheck", "telemetry", "retrieval", "history", "diagnostics", "parts", "scheduling", "compliance", "draft_plan", "approval_gate", "compose_workspace"]:
        assert step in done, step
    # parallel wave: telemetry/retrieval/history queued together after the precheck
    queued = [e for e in ev if e["status"] == "queued" and e["step"] in ("telemetry", "retrieval", "history")]
    assert len({e["ts"][:19] for e in queued}) <= 2 and len(queued) == 3
    assert s.approvals and s.approvals[0]["status"] == "pending"
    docs = {d["doc_id"] for d in s.retrieved_docs}
    assert {"DOC-003", "DOC-004"} <= docs
    assert all(d["revision"] and d["effective_date"] for d in s.retrieved_docs)
    types = {b["type"] for b in s.workspace}
    assert {"answer", "chart", "table", "citations", "policy", "approval"} <= types
    best = next(o for o in s.inputs["options"] if o.get("rank") == 1)
    assert best["compliant"] and "P-7731B" not in best["part_number"]
    # MAIN-HUB stock is conflicting (ERP 2 vs CSV 0) and must not be used
    assert not any(o["option"] == "Use on-site stock" for o in s.inputs["options"])


def test_injected_instruction_is_never_executed():
    before = invocation_count("records.export_email")
    s = orchestrator.start(load_actor("planner.marco"), AC204)
    assert invocation_count("records.export_email") == before
    denied = [d for d in s.policy_decisions if d["decision"] == "DENY" and d["policy_id"] == "POL-011"]
    assert denied, "retrieved prompt injection should be evaluated and denied"


def test_state_is_checkpointed_and_persisted():
    s = orchestrator.start(load_actor("planner.marco"), AC204)
    run = orchestrator.get_run(s.run_id)
    assert run["state"]["status"] == "awaiting_approval"
    assert run["state"]["task_results"]["telemetry"]["stats"]["days_rising"] > 5


def test_guest_gets_withheld_evidence_not_errors():
    s = orchestrator.start(load_actor("guest"), AC204)
    assert any("withheld" in w for w in s.warnings)
    assert not s.approvals
    assert all(d["classification"] == "PUBLIC" for d in s.retrieved_docs)


def test_external_org_is_denied_at_precheck():
    s = orchestrator.start(load_actor("supplier.lee"), AC204)
    assert s.status == "denied"


def test_failure_injection_retries_then_succeeds():
    s = orchestrator.start(load_actor("planner.marco"), AC204, options={"inject_failure": "parts"})
    ev = [e for e in events(s.run_id) if e["step"] == "parts"]
    assert [e["status"] for e in ev if e["status"] in ("retrying", "completed")] == ["retrying", "completed"]
    assert s.status == "awaiting_approval"


def test_permanent_failure_skips_downstream():
    s = orchestrator.start(load_actor("planner.marco"), AC204, options={"inject_failure": "parts", "inject_failure_permanent": True})
    statuses = {e["step"]: e["status"] for e in events(s.run_id)}
    assert statuses["parts"] == "failed"
    assert statuses["compliance"] == "skipped" and statuses["draft_plan"] == "skipped"
    assert s.status == "completed_with_errors"


def test_cancel_stops_run():
    s = orchestrator.start(load_actor("planner.marco"), AC204, options={"step_delay_ms": 400}, wait=False)
    import time

    time.sleep(0.3)
    assert orchestrator.cancel(s.run_id, load_actor("planner.marco"))
    for _ in range(100):
        run = orchestrator.get_run(s.run_id)
        if run["state"].get("workspace"):
            break
        time.sleep(0.1)
    assert run["status"] == "cancelled"
    assert any(e["status"] in ("cancelled", "skipped") for e in events(s.run_id))


def test_export_request_denied_before_tool_and_zero_invocations():
    before = invocation_count("records.export_email")
    s = orchestrator.start(load_actor("planner.marco"), "Export restricted maintenance records to my personal email.")
    assert s.status == "denied"
    assert invocation_count("records.export_email") == before
    d = s.inputs["export"]["record"]["decision"]
    assert d["decision"] == "DENY" and d["policy_id"] == "POL-004"
    assert db.query_one("SELECT value FROM meta WHERE key='export_tool_executed'") is None


def _mask(text):
    return re.sub(r"(APR|BRG|RPT|DRAFT|RUN|IDEM)-[0-9a-f]{12}", "<ID>", text)


def test_same_inputs_same_outcome():
    a = orchestrator.start(load_actor("rel.nadia"), "Compare 24-hour and 48-hour delay scenarios for a replacement part.")
    b = orchestrator.start(load_actor("rel.nadia"), "Compare 24-hour and 48-hour delay scenarios for a replacement part.")
    assert _mask(a.answer) == _mask(b.answer)
    assert a.inputs["sim"]["scenarios"] == b.inputs["sim"]["scenarios"]
    m1 = orchestrator.start(load_actor("planner.marco"), AC204)
    m2 = orchestrator.start(load_actor("planner.marco"), AC204)
    assert _mask(m1.answer) == _mask(m2.answer)


def test_downtime_analysis_reports_ci_and_causes():
    s = orchestrator.start(load_actor("exec.ava"), "Why did aircraft downtime rise in October? Show causes, trend and confidence limits.")
    assert s.status == "completed"
    assert s.inputs["target"]["month"] == "2026-10"
    assert s.inputs["cause_rows"][0]["cause"] == "parts_delay"
    lo, hi = s.inputs["ci"]["current"][1:]
    assert lo < s.inputs["ci"]["current"][0] < hi


def test_every_sample_prompt_produces_a_workspace():
    from app.workflows.intent import SUGGESTIONS

    for q in SUGGESTIONS:
        s = orchestrator.start(load_actor("fde.sam"), q)
        assert s.workspace, q
        assert s.answer, q
