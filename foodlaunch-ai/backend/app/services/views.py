"""Read models for the control room. Every metric is computed from recorded data."""

from __future__ import annotations

import json
import statistics
from datetime import datetime

from app.config import get_settings
from app.db import kv_get, loads, row, rows
from app.graph import flows
from app.records import list_activity
from app.services import delivery, incidents
from app.tools import deploy as deployer
from app.tools import inventory_sim, telemetry

STAGES = [
    ("brief_analysis", "Brief analysis", "Brief Analyst", []),
    ("clarification", "Clarification decisions", "Brief Analyst + Marketing", ["brief_analysis"]),
    ("requirements", "Requirements and approval", "Requirements Agent + Product owner", ["clarification"]),
    ("design", "Design", "Design Agent", ["requirements"]),
    ("implementation", "Implementation (isolated workspace)", "Implementation Agent", ["design"]),
    ("testing", "Acceptance tests", "QA Agent", ["implementation"]),
    ("repair", "Repair of failing regression", "Repair Agent", ["testing"]),
    ("review", "Static checks and review", "Review Agent", ["testing"]),
    ("release", "Release gates and approval", "Release Coordinator + Approver", ["review"]),
    ("recovery", "Incident recovery verification", "Incident Analyst", ["release"]),
]


def _gate_head(run_id: str) -> dict | None:
    head = delivery.head_revision(run_id)
    return delivery.evaluate_gates(run_id, head) if head else None


def test_run_summary(test_run: dict) -> dict:
    return {k: test_run[k] for k in ("id", "revision", "suite_version", "tests_hash", "purpose", "exit_code",
                                     "status", "duration_s", "started_at", "finished_at")}


def run_detail(run_id: str) -> dict:
    run = delivery.get_run(run_id)
    sets = [delivery.requirement_set(run_id, r["version"])
            for r in rows("SELECT version FROM requirement_sets WHERE run_id = ? ORDER BY version", (run_id,))]
    design = row("SELECT * FROM designs WHERE run_id = ?", (run_id,))
    if design:
        design["content"] = json.loads(design.pop("content_json"))
    change_sets = delivery.change_sets(run_id)
    for cs in change_sets:
        cs["diff_stats"] = {"added": sum(1 for line in cs["diff_text"].splitlines()
                                         if line.startswith("+") and not line.startswith("+++")),
                            "removed": sum(1 for line in cs["diff_text"].splitlines()
                                           if line.startswith("-") and not line.startswith("---"))}
        cs.pop("diff_text")
    releases = rows("SELECT id, revision, kind, status, manifest_hash, created_at, deployed_at, incident_id"
                    " FROM releases WHERE run_id = ? ORDER BY created_at", (run_id,))
    run_incidents = rows("SELECT id, status, title, release_id, opened_at, resolved_at FROM incidents"
                         " WHERE run_id = ? ORDER BY opened_at", (run_id,))
    snaps = {"delivery": flows.snapshot(run_id, "delivery")}
    for inc in run_incidents:
        snaps[f"incident:{inc['id']}"] = flows.snapshot(run_id, "incident", inc["id"])
    for snap in snaps.values():
        snap.pop("values", None)
    return {
        "run": run,
        "brief": delivery.current_brief(run_id),
        "clarifications": delivery.list_clarifications(run_id),
        "requirement_sets": sets,
        "design": design,
        "change_sets": change_sets,
        "test_runs": [test_run_summary(t) for t in
                      rows("SELECT * FROM test_runs WHERE run_id = ? ORDER BY started_at", (run_id,))],
        "static_checks": rows("SELECT id, revision, tool, exit_code, status, created_at, findings_json FROM"
                              " static_checks WHERE run_id = ? ORDER BY created_at", (run_id,)),
        "findings": rows("SELECT * FROM findings WHERE run_id = ?", (run_id,)),
        "releases": releases,
        "incidents": run_incidents,
        "gates": _gate_head(run_id),
        "history": rows("SELECT * FROM status_history WHERE run_id = ? ORDER BY seq", (run_id,)),
        "flows": snaps,
        "board": board(run_id),
    }


def board(run_id: str) -> list[dict]:
    run = delivery.get_run(run_id)
    acts = list_activity(run_id)
    agent_names = {a["agent"] for a in acts}
    order = [s[0] for s in STAGES]
    current = run["stage"]
    current_idx = order.index(current) if current in order else -1
    flow = run["active_flow"] or "delivery"
    incident_id = flow.split(":", 1)[1] if flow.startswith("incident:") else None
    finished = flows.snapshot(run_id, "incident" if incident_id else "delivery", incident_id)["done"]
    blockers = []
    if run["status"] == "blocked":
        blockers.append(run["error"] or "Run blocked; see activity log")
    if run["waiting_for"]:
        blockers.append(f"Waiting for human: {run['waiting_for'].replace('_', ' ')}")
    items = []
    for idx, (key, title, owner, deps) in enumerate(STAGES):
        if key == current:
            if run["status"] == "blocked":
                status = "blocked"
            elif run["waiting_for"]:
                status = "waiting"
            elif finished:
                status = "done"
            else:
                status = "active"
        elif idx < current_idx or (key == "repair" and "Repair Agent" in agent_names):
            status = "done"
        else:
            status = "pending"
        if key == "repair" and "Repair Agent" not in agent_names and idx < current_idx:
            status = "skipped"
        items.append({"stage": key, "title": title, "owner": owner, "depends_on": deps, "status": status,
                      "blockers": blockers if key == current else []})
    return items


def trace(run_id: str) -> dict:
    """brief -> requirement -> acceptance criterion -> change set -> test result -> release -> incident -> repair."""
    brief = delivery.current_brief(run_id)
    req_set = delivery.requirement_set(run_id)
    css = delivery.change_sets(run_id)
    for cs in css:
        cs.pop("diff_text")
    results = rows("SELECT r.*, t.revision, t.started_at, t.purpose FROM test_results r JOIN test_runs t"
                   " ON t.id = r.test_run_id WHERE t.run_id = ? ORDER BY t.started_at", (run_id,))
    for r in results:
        r["ac_ids"] = json.loads(r.pop("ac_ids_json"))
        r["regression_ids"] = json.loads(r.pop("regression_ids_json"))
    releases = rows("SELECT id, revision, kind, status, manifest_hash, incident_id FROM releases WHERE run_id = ?"
                    " ORDER BY created_at", (run_id,))
    run_incidents = rows("SELECT id, status, release_id, revision FROM incidents WHERE run_id = ?", (run_id,))
    head = delivery.head_revision(run_id)
    requirements = []
    for req in (req_set["requirements"] if req_set else []):
        criteria = []
        for ac in req["criteria"]:
            tests = [{"nodeid": r["nodeid"], "outcome": r["outcome"], "test_run_id": r["test_run_id"],
                      "revision": r["revision"], "regression_ids": r["regression_ids"]}
                     for r in results if ac["ac_id"] in r["ac_ids"]]
            head_runs = [t["test_run_id"] for t in tests if t["revision"] == head]
            on_head = [t for t in tests if head_runs and t["test_run_id"] == head_runs[-1]]
            criteria.append({
                "ac_id": ac["ac_id"], "text": ac["text"], "critical": bool(ac["critical"]),
                "tests": tests,
                "status_on_head": ("gap: no test evidence" if not on_head else
                                   "passing" if all(t["outcome"] == "passed" for t in on_head) else "failing"),
            })
        requirements.append({
            "req_id": req["req_id"], "title": req["title"], "decisions": req["decisions"],
            "change_sets": [c["id"] for c in css if req["req_id"] in c["addresses"]],
            "criteria": criteria,
        })
    return {"brief": {"id": brief["id"], "version": brief["version"]},
            "requirement_set_version": req_set["version"] if req_set else None,
            "head_revision": head, "requirements": requirements, "change_sets": css, "releases": releases,
            "incidents": run_incidents}


def _duration_s(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    return round((datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds(), 1)


def overview() -> dict:
    test_runs = rows("SELECT status, duration_s FROM test_runs WHERE status != 'running'")
    deployments = rows("SELECT action, status, started_at, finished_at FROM deployments")
    durations = [t["duration_s"] for t in test_runs if t["duration_s"] is not None]
    deploy_durations = [d for d in (_duration_s(x["started_at"], x["finished_at"]) for x in deployments) if d]
    runs = rows("SELECT id, title, mode, status, stage, waiting_for, error, created_at, updated_at FROM runs"
                " ORDER BY created_at DESC")
    first_deploy = []
    for run in runs:
        dep = row("SELECT MIN(r.deployed_at) AS t FROM releases r WHERE r.run_id = ? AND r.deployed_at IS NOT NULL",
                  (run["id"],))
        if dep and dep["t"]:
            first_deploy.append(_duration_s(run["created_at"], dep["t"]))
    current = delivery.current_release()
    lkg = kv_get(delivery.LKG_KEY)
    tel = telemetry.summary()
    return {
        "runs": runs,
        "blocked_releases": rows("SELECT id, run_id, revision, status, kind FROM releases WHERE status IN"
                                 " ('blocked', 'awaiting-approval', 'failed')"),
        "incidents": incidents.open_incidents(),
        "current_release": {k: current[k] for k in ("id", "revision", "kind", "status", "deployed_at")}
        if current else None,
        "last_known_good": lkg,
        "metrics": {
            "label": "Measured from this local installation's records (not business outcomes)",
            "test_runs": len(test_runs),
            "test_runs_passed": sum(1 for t in test_runs if t["status"] == "passed"),
            "test_runs_failed": sum(1 for t in test_runs if t["status"] == "failed"),
            "median_test_run_s": round(statistics.median(durations), 2) if durations else None,
            "deployments": len(deployments),
            "deployments_healthy": sum(1 for d in deployments if d["status"] in ("healthy", "stopped")),
            "rollbacks": sum(1 for d in deployments if d["action"] == "rollback"),
            "median_deploy_s": round(statistics.median(deploy_durations), 2) if deploy_durations else None,
            "brief_to_first_deploy_s": first_deploy[0] if first_deploy else None,
            "gate_rejections": row("SELECT COUNT(*) AS n FROM audit_events WHERE outcome = 'rejected'")["n"],
            "telemetry_requests": tel["requests"],
            "checkout_p95_ms": tel["checkout_p95_ms"],
        },
    }


def system_status() -> dict:
    settings = get_settings()
    process = deployer.current_process()
    return {
        "demo": True,
        "default_mode": settings.default_mode,
        "live_mode": {"available": settings.live_available,
                      "reason": None if settings.live_available else
                      "ANTHROPIC_API_KEY and ANTHROPIC_MODEL are not both set on the backend"},
        "sandbox": {"container": False,
                    "note": "No container runtime is used. Only trusted seeded fixture patches are executed, in a "
                            "restricted subprocess (scrubbed env, timeouts, output caps, var/ working dirs)."},
        "storefront": {"url": settings.storefront_url, "process": process, "health": deployer.health(1.0)},
        "fault": inventory_sim.fault_state(),
        "demo_clock": settings.demo_clock,
        "current_release": kv_get(delivery.CURRENT_KEY),
        "last_known_good": kv_get(delivery.LKG_KEY),
    }


def change_set(cs_id: str) -> dict:
    found = row("SELECT * FROM change_sets WHERE id = ?", (cs_id,))
    if found:
        found["files"] = loads(found.pop("files_json"), [])
        found["addresses"] = loads(found.pop("addresses_json"), [])
    return found
