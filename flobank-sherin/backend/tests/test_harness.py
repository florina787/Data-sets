"""Agent harness end to end: plan, permissions, retry, verification, approval interrupt, resume, accounting."""
from sqlalchemy import func, select

from app import models as M
from app.agents import harness as H
from app.finance import engine as E
from tests.conftest import hdr

BUGGY = """import os
def load(path, cache={}):
    try:
        data = open(path).read()
    except:
        return None
    if data == None:
        return None
    return data
"""

PIPE = """trigger: [main]
pool:
  vmImage: ubuntu-latest
steps:
- task: Cache@2
  inputs:
    key: 'python | "$(Agent.OS)"'
    path: $(PIP_CACHE_DIR)
- script: pytest
"""


def _run(client, request, attachments=(), role="ENGINEER", user="eng.ravi"):
    r = client.post("/api/harness/runs", json={"request": request, "attachments": list(attachments)}, headers=hdr(role, user))
    assert r.status_code == 200, r.text
    return client.get(f"/api/harness/runs/{r.json()['run_id']}").json()


def test_python_debug_run_pauses_for_approval_then_completes(client, db):
    run = _run(client, "Debug this Python loader", [{"name": "loader.py", "content": BUGGY}])
    assert [s["agent"] for s in run["plan"]] == ["python_coding", "qa", "python_coding"]
    assert run["status"] == "awaiting_approval"
    steps = run["result"]["steps"]
    dbg = steps[0]["output"]
    assert {f["rule"] for f in dbg["findings"]} >= {"bare-except", "none-comparison", "mutable-default"}
    assert "except Exception:" in dbg["diff"]
    assert all(v["verified"] for v in run["result"]["verification"])
    aid = run["result"]["approval_id"]
    # Requester (the agent) cannot approve; the manager can.
    r = client.post(f"/api/approvals/{aid}/decision", json={"decision": "approve", "comment": "LGTM"}, headers=hdr("SHERIN_MANAGER", "mgr.sherin"))
    assert r.status_code == 200 and r.json()["status"] == "approved"
    run = client.get(f"/api/harness/runs/{run['id']}").json()
    assert run["status"] == "completed", run["trace"][-3:]
    res = run["result"]
    assert res["verified"] and res["human_review_basis"] == "measured" and res["allocated_cost_usd"] > 0
    assert "minutes of agent execution" in res["sentence"]
    task = db.get(M.AgentTask, res["task_id"])
    assert task.data_class == "measured" and task.run_id == run["id"]
    linked = db.scalar(select(func.sum(M.AiCostRecord.amount_usd)).where(M.AiCostRecord.task_id == task.id))
    assert E.q(linked) == E.q(task.cost_model + task.cost_compute + task.cost_infra + task.cost_tooling + task.cost_human_review + task.cost_rework)


def test_rejected_run_gets_no_savings_credit(client, db):
    run = _run(client, "Fix the pipeline yaml build failure", [{"name": "azure-pipelines.yml", "content": PIPE}])
    assert run["plan"][0]["tool"] == "pipeline.yaml_lint" and run["status"] == "awaiting_approval"
    aid = run["result"]["approval_id"]
    client.post(f"/api/approvals/{aid}/decision", json={"decision": "reject", "comment": "wrong image"}, headers=hdr("SHERIN_MANAGER", "mgr.sherin"))
    run = client.get(f"/api/harness/runs/{run['id']}").json()
    assert run["status"] == "completed_rejected" and run["result"]["estimated_saving_usd"] == 0.0
    assert db.get(M.AgentTask, run["result"]["task_id"]).verified is False


def test_guardian_run_with_block_is_not_approvable(client):
    run = _run(client, "Evaluate trade TP-1002", role="PORTFOLIO_MANAGER", user="pm.liam")
    assert run["plan"][0]["tool"] == "guardian.evaluate"
    assert run["status"] == "completed_blocked"
    ap = client.get(f"/api/approvals/{run['result']['approval_id']}").json()
    assert ap["policy_blocked"] and not ap["can_be_approved"]


def test_tool_permission_denied(client, monkeypatch):
    monkeypatch.setattr(H, "make_plan", lambda *a, **k: [{"step": 1, "agent": "reporting", "tool": "deploy.request_approval", "objective": "sneaky deploy"}])
    run = _run(client, "report something")
    step = run["result"]["steps"][0]
    assert step.get("denied") and not step["ok"]
    assert run["status"] == "completed" and not run["result"]["verified"]
    audit = client.get("/api/audit").json()
    assert any(a["action"] == "tool.denied" for a in audit)


def test_retry_and_recovery(client, monkeypatch):
    calls = {"n": 0}
    real = H.run_tool

    def flaky(tool, state, db, prior):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("transient")
        return real(tool, state, db, prior)
    monkeypatch.setattr(H, "run_tool", flaky)
    run = _run(client, "What is the cost and token position?", role="SHERIN_MANAGER", user="mgr.sherin")
    assert run["result"]["steps"][0]["retries"] == 1 and run["result"]["steps"][0]["ok"]
    assert any(e.get("status") == "retry" for e in run["trace"])


def test_viewer_cannot_start_runs_and_uploads_validated(client):
    assert client.post("/api/harness/runs", json={"request": "do things"}, headers=hdr("VIEWER", "v")).status_code == 403
    r = client.post("/api/harness/runs", json={"request": "x run", "attachments": [{"name": "evil.exe", "content": "MZ"}]}, headers=hdr("ENGINEER", "e"))
    assert r.status_code == 415


def test_agent_cards_expose_required_fields(client):
    agents = client.get("/api/harness/agents").json()["agents"]
    assert len(agents) == 15
    for a in agents:
        assert {"current_task", "status", "time_hours", "tokens", "compute_cost", "quality_pass_rate", "verified_tasks", "economic_contribution"} <= set(a)


def test_measured_runs_never_enter_synthetic_view(client, db):
    n = db.scalar(select(func.count()).select_from(M.AgentTask).where(M.AgentTask.data_class == "measured"))
    assert n >= 1
    k = client.get("/api/finance/kpis", params={"dc": "measured", "period": "custom", "start": "2026-01-01", "end": "2030-12-31"}).json()
    assert {c["key"]: c for c in k["cards"]}["verified_work"]["value"] >= 1


def _events(client, run_id):
    return [e["event"] for e in client.get(f"/api/harness/runs/{run_id}/events").json()["events"]]


def test_typed_events_follow_real_execution_and_pause_for_approval(client):
    run = _run(client, "Evaluate trade TP-1003 and check the portfolio risk", role="PORTFOLIO_MANAGER", user="pm.ananya")
    ev = _events(client, run["id"])
    assert ev[0] == "RUN_PLANNED"
    # every step starts, runs its tool and completes, in order
    for i in range(len(run["plan"])):
        seg = ev[1 + 3 * i: 4 + 3 * i]
        assert seg == ["AGENT_STARTED", "TOOL_RUNNING", "TOOL_COMPLETED"], seg
    assert ev[-3:] == ["VALIDATION_STARTED", "VALIDATION_PASSED", "APPROVAL_REQUIRED"]
    assert "TASK_COMPLETED" not in ev  # nothing claims success while the workflow waits for a human
    aid = run["result"]["approval_id"]
    client.post(f"/api/approvals/{aid}/decision", json={"decision": "approve"}, headers=hdr("SHERIN_MANAGER", "mgr.sherin"))
    ev = _events(client, run["id"])
    assert ev[-2:] == ["APPROVAL_DECIDED", "TASK_COMPLETED"]
    body = client.get(f"/api/harness/runs/{run['id']}/stream").text
    assert body.count("event: harness") == len(ev) and body.rstrip().endswith('{"status": "completed"}')


def test_failed_tool_emits_tool_failed(client, monkeypatch):
    monkeypatch.setattr(H, "make_plan", lambda *a, **k: [{"step": 1, "agent": "reporting", "tool": "deploy.request_approval", "objective": "x"}])
    run = _run(client, "anything")
    ev = _events(client, run["id"])
    assert "TOOL_DENIED" in ev and "VALIDATION_FAILED" in ev and ev[-1] == "TASK_COMPLETED"
    last = client.get(f"/api/harness/runs/{run['id']}/events").json()["events"][-1]
    assert last["verified"] is False
