from app.db import session_scope
from app.models.orm import Case
from app.workflows import checkpoints, graph, service


class Crash(RuntimeError):
    pass


def test_crash_mid_workflow_resumes_from_checkpoint(client, login):
    calls = {"n": 0}

    def crash(_state):
        calls["n"] += 1
        raise Crash("simulated worker crash")

    graph.FAULT_HOOKS["diagnosis"] = crash
    r = client.post("/api/cases/C-1003/investigate?wait=true", headers=login("u-spec-ava"))
    assert r.status_code == 202
    with session_scope() as db:
        c = db.get(Case, "C-1003")
        assert c.status == "COLLECTING_EVIDENCE" and c.active_job is not None
    audit = client.get("/api/cases/C-1003/audit", headers=login("u-spec-ava")).json()
    assert audit[-1]["event_type"] == "WORKFLOW_INTERRUPTED"
    # "restart": drop in-memory graph and checkpointer connection, keep the files
    graph.FAULT_HOOKS.clear()
    graph.reset_graph()
    checkpoints._saver = None  # noqa: SLF001 - simulate a fresh process
    checkpoints._conn = None  # noqa: SLF001
    resumed = service.recover_incomplete_jobs()
    assert resumed == ["C-1003"]
    d = client.get("/api/cases/C-1003", headers=login("u-spec-ava")).json()
    assert d["status"] == "AWAITING_APPROVAL" and not d["investigation_running"]
    # triage and evidence were not re-run: only one EVIDENCE_COLLECTED event
    audit = client.get("/api/cases/C-1003/audit", headers=login("u-spec-ava")).json()
    assert sum(1 for e in audit if e["event_type"] == "EVIDENCE_COLLECTED") == 1


def test_approval_wait_is_durable_across_restart(client, login):
    r = client.post("/api/cases/C-1003/investigate?wait=true", headers=login("u-spec-ava"))
    assert r.status_code == 202
    graph.reset_graph()
    checkpoints._saver = None  # noqa: SLF001
    checkpoints._conn = None  # noqa: SLF001
    assert service.recover_incomplete_jobs() == []  # waiting on a human is not a stalled job
    d = client.get("/api/cases/C-1003", headers=login("u-spec-ava")).json()
    r = client.post("/api/cases/C-1003/approvals", headers=login("u-sup-emma"),
                    json={"action": "approve", "approval_id": d["approval"]["id"],
                          "payload_hash": d["recommendation"]["payload_hash"]})
    assert r.status_code == 200
    audit = client.get("/api/cases/C-1003/audit", headers=login("u-spec-ava")).json()
    assert any(e["event_type"] == "HUMAN_REVIEW_RESUMED" for e in audit)
    thread = client.get("/api/cases/C-1003", headers=login("u-spec-ava")).json()
    assert thread["status"] == "APPROVED"
