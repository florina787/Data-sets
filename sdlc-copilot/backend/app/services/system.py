"""Startup, deterministic reset and cross-cutting actions shared by API and demo."""

from __future__ import annotations

import shutil

from app import auth
from app.auth import User
from app.config import get_settings
from app.db import init_db, kv_set, row
from app.errors import Conflict
from app.graph import flows, jobs
from app.records import activity, audit
from app.services import delivery, incidents
from app.tools import deploy as deployer
from app.tools import inventory_sim, workspace


def reset_demo(actor: str = "system") -> dict:
    """Wipe all local state and rebuild the seeded demo. Deterministic."""
    settings = get_settings()
    deployer.stop_current()
    flows.reset_graphs()
    if settings.var_dir.exists():
        for child in settings.var_dir.iterdir():
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    settings.var_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    auth.seed_accounts()
    inventory_sim.seed()
    base = workspace.init_repository()
    release_id = delivery.seed_baseline_release(base)
    deployment = deployer.deploy(release_id, base, actor, "baseline")
    kv_set("demo.reset_at", deployment["started_at"])
    audit(actor, "demo.reset", entity_type="system", baseline_revision=base, deployment=deployment["status"])
    return {"baseline_revision": base, "deployment": deployment}


def startup() -> None:
    init_db()
    jobs.mark_interrupted()
    if row("SELECT 1 FROM users LIMIT 1") is None:
        reset_demo("startup")
        return
    current = delivery.current_release()
    if current and deployer.current_process() is None:
        deployer.deploy(current["id"], current["revision"], "startup", "restore")


def resume_active_flow(run_id: str, actor: User) -> str:
    run = delivery.get_run(run_id)
    flow = run["active_flow"] or "delivery"
    incident_id = flow.split(":", 1)[1] if flow.startswith("incident:") else None
    audit(actor.username, "run.continue", entity_type="run", entity_id=run_id, flow=flow)
    return flows.start(run_id, "incident" if incident_id else "delivery", incident_id, run["mode"])


def deploy_and_resume(release_id: str, user: User) -> dict:
    deployment = delivery.deploy_release(release_id, user)
    release = delivery.get_release(release_id)
    result = {"deployment": deployment}
    run = delivery.get_run(release["run_id"])
    flow = run["active_flow"] or "delivery"
    incident_id = flow.split(":", 1)[1] if flow.startswith("incident:") else None
    result["flow"] = flows.advance(release["run_id"], "incident" if incident_id else "delivery", incident_id,
                                   run["mode"])
    return result


def open_incident_and_start(user: User) -> dict:
    auth.require(user, "incident.manage", "incident")
    result = incidents.analyse(user.username)
    incident = result["incident"]
    if incident and incident["run_id"]:
        snap = flows.snapshot(incident["run_id"], "incident", incident["id"])
        if not snap["started"]:
            activity(incident["run_id"], "Incident Analyst", "incident",
                     f"{incident['id']} opened from telemetry for {incident['release_id']}", "deterministic")
            result["flow"] = flows.advance(incident["run_id"], "incident", incident["id"])
    return result


def request_implementation(run_id: str, user: User) -> None:
    """Explicit attempt to start implementation; demonstrates the clarification gate (episode A)."""
    auth.require(user, "run.control", "run", run_id)
    pending = delivery.open_required_clarifications(run_id)
    if pending:
        audit(user.username, "run.request_implementation", outcome="rejected", entity_type="run", entity_id=run_id,
              open=[p["id"] for p in pending])
        raise Conflict("Implementation cannot start until every required clarification has a recorded decision",
                       open=[p["id"] for p in pending])
    raise Conflict("Implementation is started by the orchestrator after requirements approval; use Continue")
