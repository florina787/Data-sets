"""SDLC Copilot control-room API. Start with ``python -m app`` (see scripts/start.sh)."""

from __future__ import annotations

import json
import os
import warnings
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import auth
from app.auth import User
from app.config import FIXTURES, get_settings
from app.db import execute, rows
from app.errors import NotFound, PlatformError
from app.graph import flows, jobs
from app.records import PROVENANCE, audit, list_activity
from app.services import delivery, demo, incidents, system, views
from app.tools import inventory_sim, telemetry, traffic, workspace
from app.tools.retrieval import get_index

warnings.filterwarnings("ignore", message=".*allowed_objects.*")


@asynccontextmanager
async def lifespan(_: FastAPI):
    system.startup()
    yield
    # By default the deployed storefront keeps running across control-room restarts and
    # is re-adopted from its PID file. Test harnesses opt in to stopping it on exit.
    if os.environ.get("SDLC_COPILOT_STOP_STOREFRONT_ON_EXIT") == "1":
        from app.tools import deploy

        deploy.stop_current()


app = FastAPI(title="SDLC Copilot control room (demo)", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(inventory_sim.router)


@app.exception_handler(PlatformError)
async def platform_error(_: Request, exc: PlatformError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code,
                        content={"error": exc.code, "message": exc.message, "details": exc.details})


def current_user(authorization: str | None = Header(default=None)) -> User:
    token = authorization.removeprefix("Bearer ").strip() if authorization else None
    return auth.user_for_token(token)


# --- request bodies --------------------------------------------------------------------

class LoginBody(BaseModel):
    username: str = Field(max_length=60)
    password: str = Field(max_length=200)


class RunBody(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    brief: str = Field(min_length=1, max_length=4000)
    mode: str = "demo"


class DecisionBody(BaseModel):
    decision: str = Field(min_length=1, max_length=400)
    rationale: str = Field(default="", max_length=800)


class ApproveBody(BaseModel):
    manifest_hash: str = Field(min_length=64, max_length=64)


class ReasonBody(BaseModel):
    reason: str = Field(default="Mitigation", max_length=300)


class FaultBody(BaseModel):
    active: bool


class TrafficBody(BaseModel):
    journeys: int = Field(default=3, ge=1, le=10)


class StepModeBody(BaseModel):
    enabled: bool


# --- auth ------------------------------------------------------------------------------

@app.post("/api/auth/login")
def login(body: LoginBody) -> dict:
    token, user = auth.login(body.username, body.password)
    return {"token": token, "user": user.__dict__}


@app.post("/api/auth/logout")
def logout(authorization: str | None = Header(default=None)) -> dict:
    if authorization:
        auth.logout(authorization.removeprefix("Bearer ").strip())
    return {"ok": True}


@app.get("/api/auth/me")
def me(user: User = Depends(current_user)) -> dict:
    return {"user": user.__dict__, "permissions": sorted(a for a, r in auth.PERMISSIONS.items() if user.role in r)}


@app.get("/api/auth/demo-accounts")
def demo_accounts() -> dict:
    return {
        "accounts": [{"username": u, "display_name": d, "role": r} for _, u, d, r in auth.DEMO_ACCOUNTS],
        "password": auth.DEMO_PASSWORD,
        "note": "Local demo accounts only. This is not enterprise SSO.",
    }


# --- overview / system -----------------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/system")
def system_status() -> dict:
    return views.system_status()


@app.get("/api/overview")
def overview() -> dict:
    return views.overview()


@app.get("/api/provenance")
def provenance() -> dict:
    return PROVENANCE


# --- runs ------------------------------------------------------------------------------

@app.get("/api/runs")
def list_runs() -> dict:
    return {"runs": rows("SELECT * FROM runs ORDER BY created_at DESC")}


@app.post("/api/runs", status_code=201)
def create_run(body: RunBody, user: User = Depends(current_user)) -> dict:
    run_id = delivery.create_run(user, body.title, body.brief, body.mode)
    job_id = flows.start(run_id, "delivery", mode=body.mode)
    return {"run_id": run_id, "job_id": job_id}


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str) -> dict:
    return views.run_detail(run_id)


@app.get("/api/runs/{run_id}/activity")
def run_activity(run_id: str, after: int = 0) -> dict:
    delivery.get_run(run_id)
    return {"activity": list_activity(run_id, after)}


@app.get("/api/runs/{run_id}/trace")
def run_trace(run_id: str) -> dict:
    return views.trace(run_id)


@app.get("/api/runs/{run_id}/gates")
def run_gates(run_id: str, revision: str | None = None) -> dict:
    return delivery.evaluate_gates(run_id, revision or delivery.head_revision(run_id))


@app.post("/api/runs/{run_id}/continue")
def continue_run(run_id: str, user: User = Depends(current_user)) -> dict:
    auth.require(user, "run.advance", "run", run_id)
    return {"job_id": system.resume_active_flow(run_id, user)}


@app.post("/api/runs/{run_id}/pause")
def pause_run(run_id: str, user: User = Depends(current_user)) -> dict:
    auth.require(user, "run.control", "run", run_id)
    delivery.get_run(run_id)
    execute("UPDATE runs SET pause_requested = 1 WHERE id = ?", (run_id,))
    audit(user.username, "run.pause", entity_type="run", entity_id=run_id)
    return {"pause_requested": True}


@app.post("/api/runs/{run_id}/step-mode")
def step_mode(run_id: str, body: StepModeBody, user: User = Depends(current_user)) -> dict:
    auth.require(user, "run.control", "run", run_id)
    execute("UPDATE runs SET step_mode = ? WHERE id = ?", (int(body.enabled), run_id))
    return {"step_mode": body.enabled}


@app.post("/api/runs/{run_id}/request-implementation")
def request_implementation(run_id: str, user: User = Depends(current_user)) -> dict:
    system.request_implementation(run_id, user)
    return {}


@app.post("/api/runs/{run_id}/clarifications/apply-seeded")
def apply_seeded(run_id: str, user: User = Depends(current_user)) -> dict:
    return {"recorded": delivery.apply_seeded_decisions(run_id, user)}


@app.post("/api/runs/{run_id}/clarifications/{q_id}")
def decide(run_id: str, q_id: str, body: DecisionBody, user: User = Depends(current_user)) -> dict:
    delivery.decide_clarification(run_id, q_id, user, body.decision, body.rationale)
    return {"ok": True}


@app.post("/api/runs/{run_id}/requirements/{version}/approve")
def approve_requirements(run_id: str, version: int, user: User = Depends(current_user)) -> dict:
    plan = delivery.approve_requirement_set(run_id, version, user)
    return {"test_plan": plan}


@app.get("/api/runs/{run_id}/source")
def read_source(run_id: str, path: str) -> dict:
    return {"path": path, "content": workspace.read_source(run_id, path)}


# --- engineering / quality -------------------------------------------------------------

@app.get("/api/change-sets/{cs_id}")
def change_set(cs_id: str) -> dict:
    found = views.change_set(cs_id)
    if not found:
        raise NotFound("Change set not found")
    return found


@app.get("/api/test-runs/{test_run_id}")
def test_run(test_run_id: str) -> dict:
    found = rows("SELECT * FROM test_runs WHERE id = ?", (test_run_id,))
    if not found:
        raise NotFound("Test run not found")
    result = found[0]
    result.pop("report_json", None)
    return {"test_run": result, "results": delivery.test_results(test_run_id)}


@app.get("/api/static-checks/{check_id}")
def static_check(check_id: str) -> dict:
    found = rows("SELECT * FROM static_checks WHERE id = ?", (check_id,))
    if not found:
        raise NotFound("Static check not found")
    found[0]["findings"] = json.loads(found[0].pop("findings_json"))
    return found[0]


@app.get("/api/repository/log")
def repo_log() -> dict:
    return {"commits": workspace.log()}


# --- releases --------------------------------------------------------------------------

@app.get("/api/releases")
def releases() -> dict:
    return {"releases": rows("SELECT id, run_id, revision, kind, status, manifest_hash, created_at, deployed_at,"
                             " incident_id, label FROM releases ORDER BY created_at DESC"),
            "current": views.system_status()["current_release"],
            "last_known_good": views.system_status()["last_known_good"]}


@app.get("/api/releases/{release_id}")
def release(release_id: str) -> dict:
    found = delivery.get_release(release_id)
    if found["run_id"]:
        found["gates_now"] = delivery.evaluate_gates(found["run_id"], found["revision"])
        found["candidate_head"] = delivery.head_revision(found["run_id"])
    found["deployments"] = rows("SELECT * FROM deployments WHERE release_id = ? ORDER BY started_at", (release_id,))
    return found


@app.post("/api/releases/{release_id}/approve")
def approve_release(release_id: str, body: ApproveBody, user: User = Depends(current_user)) -> dict:
    return delivery.approve_release(release_id, user, body.manifest_hash)


@app.post("/api/releases/{release_id}/deploy")
def deploy_release(release_id: str, user: User = Depends(current_user)) -> dict:
    auth.require(user, "release.deploy", "release", release_id)
    return {"job_id": jobs.submit("deploy", None, lambda: system.deploy_and_resume(release_id, user),
                                  lock_key="deployment")}


@app.post("/api/releases/rollback")
def rollback(body: ReasonBody, user: User = Depends(current_user)) -> dict:
    auth.require(user, "release.rollback", "release")
    return {"job_id": jobs.submit("rollback", None, lambda: delivery.rollback(user, body.reason),
                                  lock_key="deployment")}


@app.get("/api/deployments")
def deployments() -> dict:
    items = rows("SELECT * FROM deployments ORDER BY started_at DESC LIMIT 50")
    for item in items:
        item["lifecycle"] = json.loads(item.pop("lifecycle_json"))
        item["health"] = json.loads(item.pop("health_json") or "{}")
    return {"deployments": items}


# --- operations / incidents ------------------------------------------------------------

@app.post("/api/ops/fault")
def fault(body: FaultBody, user: User = Depends(current_user)) -> dict:
    auth.require(user, "fault.inject", "fault", "inventory_timeout")
    state = inventory_sim.set_fault(body.active, user.username)
    resumed = None
    if not body.active:
        for inc in rows("SELECT id, run_id FROM incidents WHERE status != 'resolved' AND run_id IS NOT NULL"):
            snap = flows.snapshot(inc["run_id"], "incident", inc["id"])
            if any(i.get("waiting_for") == "fault_cleared" for i in snap["interrupts"]):
                resumed = flows.start(inc["run_id"], "incident", inc["id"])
    return {"fault": state, "resumed_job": resumed}


@app.post("/api/ops/traffic")
def generate_traffic(body: TrafficBody, user: User = Depends(current_user)) -> dict:
    auth.require(user, "traffic.generate")
    return {"job_id": jobs.submit("traffic", None, lambda: traffic.generate(body.journeys))}


@app.post("/api/incidents/analyse")
def analyse(user: User = Depends(current_user)) -> dict:
    auth.require(user, "incident.manage", "incident")
    return {"job_id": jobs.submit("incident_analysis", None, lambda: system.open_incident_and_start(user),
                                  lock_key="incident")}


@app.get("/api/incidents")
def list_incidents() -> dict:
    return {"incidents": rows("SELECT id, run_id, release_id, revision, status, title, opened_at, resolved_at"
                              " FROM incidents ORDER BY opened_at DESC")}


@app.get("/api/incidents/{incident_id}")
def incident(incident_id: str) -> dict:
    found = incidents.get_incident(incident_id)
    found["timeline"] = telemetry.timeline(300, since=found["analysis"].get("window_start"))
    return found


@app.get("/api/telemetry/summary")
def telemetry_summary(since: str | None = None) -> dict:
    return telemetry.summary(since=since)


@app.get("/api/telemetry/events")
def telemetry_events(limit: int = 200) -> dict:
    return {"events": telemetry.timeline(min(limit, 1000))}


# --- knowledge / templates / audit -----------------------------------------------------

@app.get("/api/documents")
def documents() -> dict:
    return {"documents": get_index().documents()}


@app.get("/api/documents/search")
def search(q: str) -> dict:
    return {"query": q, "results": get_index().search(q, k=5, min_score=0.5)}


@app.get("/api/templates")
def templates() -> dict:
    items = [json.loads(p.read_text()) for p in sorted((FIXTURES / "templates").glob("*.json"))]
    return {"templates": items, "flagship": {"id": "flagship-ontario-b2g1", "status": "implemented_end_to_end"}}


@app.get("/api/audit")
def audit_log(limit: int = 200) -> dict:
    return {"events": rows("SELECT * FROM audit_events ORDER BY seq DESC LIMIT ?", (min(limit, 1000),))}


@app.get("/api/evidence")
def evidence_log(run_id: str | None = None, limit: int = 300) -> dict:
    if run_id:
        return {"evidence": rows("SELECT * FROM evidence WHERE run_id = ? ORDER BY seq DESC LIMIT ?", (run_id, limit))}
    return {"evidence": rows("SELECT * FROM evidence ORDER BY seq DESC LIMIT ?", (min(limit, 1000),))}


# --- jobs / guided demo ----------------------------------------------------------------

@app.get("/api/jobs/{job_id}")
def job(job_id: str) -> dict:
    found = jobs.get(job_id)
    if not found:
        raise NotFound("Job not found")
    return found


@app.get("/api/demo")
def demo_state() -> dict:
    return demo.describe()


@app.post("/api/demo/run")
def demo_run(user: User = Depends(current_user)) -> dict:
    auth.require(user, "demo.control")
    return {"job_id": demo.run_or_continue()}


@app.post("/api/demo/pause")
def demo_pause(user: User = Depends(current_user)) -> dict:
    auth.require(user, "demo.control")
    return demo.request_pause()


@app.post("/api/demo/reset")
def demo_reset(user: User = Depends(current_user)) -> dict:
    auth.require(user, "demo.control")
    audit(user.username, "demo.reset.requested")
    return {"job_id": jobs.submit("reset", None, lambda: system.reset_demo(user.username), lock_key="guided-demo")}


# --- static control-room UI ------------------------------------------------------------

_static = get_settings().control_room_static
if _static.is_dir():
    app.mount("/assets", StaticFiles(directory=_static / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        candidate = (_static / path).resolve()
        if path and candidate.is_file() and _static.resolve() in candidate.parents:
            return FileResponse(candidate)
        index = _static / "index.html"
        if Path(index).exists():
            return FileResponse(index)
        raise NotFound("UI not built")
