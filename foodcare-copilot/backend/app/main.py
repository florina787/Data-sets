"""FoodCare Enterprise Copilot control-room API. Start with ``python -m app`` (see scripts/start.sh)."""

from __future__ import annotations

import json
import os
import time
import warnings
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import auth
from app.auth import User
from app.config import FIXTURES, get_settings
from app.copilot import engine as copilot
from app.db import execute, rows
from app.enterprise import data as edata
from app.enterprise import queries as equeries
from app.errors import NotFound, PlatformError
from app.graph import flows, jobs
from app.llm import local as local_llm
from app.memory import maintenance as memory_maintenance
from app.memory.store import get_store
from app.records import PROVENANCE, audit, list_activity
from app.services import delivery, demo, incidents, system, views
from app.tools import inventory_sim, telemetry, traffic, workspace
from app.tools.retrieval import get_index
from app.vision import service as vision

warnings.filterwarnings("ignore", message=".*allowed_objects.*")


@asynccontextmanager
async def lifespan(_: FastAPI):
    system.startup()
    yield
    # By default the deployed storefront keeps running across control-room restarts and
    # is re-adopted from its PID file. Test harnesses opt in to stopping it on exit.
    if os.environ.get("FOODCARE_STOP_STOREFRONT_ON_EXIT") == "1":
        from app.tools import deploy

        deploy.stop_current()


app = FastAPI(title="FoodCare Enterprise Copilot control room (demo)", lifespan=lifespan)
@app.middleware("http")
async def _metrics_middleware(request: Request, call_next):
    """Count requests and latency per route template (never the raw path, which can carry IDs)."""
    started = time.perf_counter()
    response = await call_next(request)
    route = request.scope.get("route")
    template = getattr(route, "path", None) or ("static" if request.method == "GET" else "unmatched")
    from app import observability

    observability.observe_request(request.method, template, response.status_code, time.perf_counter() - started)
    return response


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


def optional_user(authorization: str | None = Header(default=None)) -> User | None:
    """The signed-in user, or None (for read-only synthetic views that also work signed out)."""
    if not authorization:
        return None
    try:
        return current_user(authorization)
    except Exception:  # noqa: BLE001 - an expired token just means "signed out" here
        return None


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


# --- enterprise domains ---------------------------------------------------------------

@app.get("/api/enterprise/overview")
def enterprise_overview() -> dict:
    return equeries.executive_overview()


@app.get("/api/enterprise/sales")
def enterprise_sales(weeks: int = 4, province: str | None = None, sku: str | None = None,
                     channel: str | None = None) -> dict:
    return equeries.sales_summary(weeks, province, sku, channel)


@app.get("/api/enterprise/campaigns")
def enterprise_campaigns() -> dict:
    return {**equeries.campaign_performance(), "stock_risk": equeries.campaign_stock_risk(),
            "live_storefront": equeries.live_storefront_orders()}


@app.get("/api/enterprise/inventory")
def enterprise_inventory(warehouse: str | None = None, sku: str | None = None) -> dict:
    return equeries.inventory_status(warehouse, sku)


@app.get("/api/enterprise/compliance")
def enterprise_compliance(sku: str | None = None, channel: str | None = None) -> dict:
    result = equeries.compliance_check(sku, channel)
    result["records"] = [equeries.product_record(s) for s in equeries.products()]
    return result


@app.get("/api/enterprise/company")
def enterprise_company() -> dict:
    cfg = edata.company()
    return {k: cfg[k] for k in ("company", "note", "currency", "regions", "channels", "warehouses")}


# --- Ask Copilot -----------------------------------------------------------------------

class AskBody(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    conversation_id: str | None = Field(default=None, max_length=20)
    mode: str = Field(default="demo", pattern="^(demo|live)$")
    request_id: str | None = Field(default=None, pattern="^[A-Za-z0-9-]{8,40}$")


@app.post("/api/copilot/ask")
def copilot_ask(body: AskBody, user: User = Depends(current_user)) -> dict:
    return copilot.ask(body.question, user, body.conversation_id, body.mode, body.request_id)


@app.post("/api/copilot/cancel/{request_id}")
def copilot_cancel(request_id: str, user: User = Depends(current_user)) -> dict:
    return {"request_id": request_id, "cancelled": copilot.cancel(request_id, user.username)}


@app.get("/api/llm/status")
def llm_status(user: User = Depends(current_user)) -> dict:
    """Configuration, reachability (a model listing, which loads no weights), queue and latency."""
    return local_llm.status()


@app.get("/api/copilot/conversations")
def copilot_conversations(limit: int = 50, user: User = Depends(current_user)) -> dict:
    return {"conversations": get_store().list_conversations(user.username, limit)}


@app.get("/api/copilot/conversations/{conversation_id}")
def copilot_history(conversation_id: str, user: User = Depends(current_user)) -> dict:
    return {"messages": copilot.history(conversation_id, user.username)}


@app.delete("/api/copilot/conversations/{conversation_id}")
def copilot_delete(conversation_id: str, user: User = Depends(current_user)) -> dict:
    if not get_store().delete_conversation(conversation_id, user.username):
        raise NotFound("Conversation not found")
    audit(user.username, "memory.conversation.delete", entity_type="conversation", entity_id=conversation_id)
    return {"deleted": conversation_id}


@app.delete("/api/copilot/conversations")
def copilot_delete_all(user: User = Depends(current_user)) -> dict:
    deleted = get_store().delete_all(user.username)
    audit(user.username, "memory.conversation.delete_all", entity_type="conversation", deleted=deleted)
    return {"deleted": deleted}


@app.get("/api/copilot/search")
def copilot_search(q: str = Query(min_length=1, max_length=200), user: User = Depends(current_user)) -> dict:
    return {"query": q, "results": get_store().search(user.username, q)}


# --- potato inspection ----------------------------------------------------------------

class BatchBody(BaseModel):
    title: str = Field(default="Inspection", max_length=120)
    supplier: str | None = Field(default=None, max_length=80)
    lot_code: str | None = Field(default=None, max_length=40)
    mm_per_px: float | None = Field(default=None, gt=0, le=10)
    thresholds: dict[str, float] | None = None
    conversation_id: str | None = Field(default=None, max_length=20)


class ThresholdBody(BaseModel):
    thresholds: dict[str, float]


@app.get("/api/inspections")
def inspections(user: User = Depends(current_user)) -> dict:
    return {"batches": vision.list_batches(user.username), "detector": vision.detector_status(),
            "default_thresholds": vision.analyse.default_thresholds(), "queue": vision.gate().status()}


@app.post("/api/inspections")
def inspection_create(body: BatchBody, user: User = Depends(current_user)) -> dict:
    return vision.create_batch(user.username, body.title, body.supplier, body.lot_code, body.mm_per_px,
                               body.thresholds, body.conversation_id)


@app.post("/api/inspections/sample")
async def inspection_sample(user: User = Depends(current_user)) -> dict:
    """A rendered SYNTHETIC image (drawn shapes, not a photo) for trying the studio without a photo."""
    from app.vision import synthetic

    png, _ = synthetic.render(seed=int(time.time()) % 1000)
    batch = vision.create_batch(user.username, "Synthetic sample (rendered shapes, not a photo)",
                                supplier="Synthetic demo supplier", lot_code="SYN-001")
    return await run_in_threadpool(vision.add_image, batch["id"], user.username, png, "synthetic-sample.png")


@app.get("/api/inspections/{batch_id}")
def inspection_get(batch_id: str, user: User = Depends(current_user)) -> dict:
    return vision.get_batch(batch_id, user.username)


@app.delete("/api/inspections/{batch_id}")
def inspection_delete(batch_id: str, user: User = Depends(current_user)) -> dict:
    vision.delete_batch(batch_id, user.username)
    audit(user.username, "inspection.delete", entity_type="inspection", entity_id=batch_id)
    return {"deleted": batch_id}


@app.post("/api/inspections/{batch_id}/images")
async def inspection_upload(batch_id: str, request: Request, filename: str | None = None,
                            user: User = Depends(current_user)) -> dict:
    """Raw image body (Content-Type image/jpeg, image/png or image/webp); no multipart dependency."""
    limit = int(get_settings().vision_max_upload_mb * 1024 * 1024)
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > limit:
            raise PlatformError(f"Image is larger than {get_settings().vision_max_upload_mb:g} MB")
    if not data:
        raise PlatformError("Send the image bytes as the request body")
    return await run_in_threadpool(vision.add_image, batch_id, user.username, bytes(data), filename)


@app.put("/api/inspections/{batch_id}/thresholds")
def inspection_thresholds(batch_id: str, body: ThresholdBody, user: User = Depends(current_user)) -> dict:
    vision.regrade(batch_id, user.username, body.thresholds)
    return vision.get_batch(batch_id, user.username)


class CorrectionBody(BaseModel):
    grade: str = Field(pattern="^(Good|Moderate|Not Good)$")
    reason: str = Field(min_length=3, max_length=300)


@app.put("/api/inspections/{batch_id}/potatoes/{potato_no}/correction")
def inspection_correct(batch_id: str, potato_no: int, body: CorrectionBody,
                       user: User = Depends(current_user)) -> dict:
    return vision.correct_potato(batch_id, user.username, potato_no, body.grade, body.reason)


@app.get("/api/inspections/{batch_id}/corrections")
def inspection_corrections(batch_id: str, user: User = Depends(current_user)) -> dict:
    return {"corrections": vision.corrections(batch_id, user.username)}


@app.get("/api/inspections/{batch_id}/images/{item_id}")
def inspection_image(batch_id: str, item_id: str, annotated: bool = True,
                     user: User = Depends(current_user)) -> FileResponse:
    return FileResponse(vision.image_path(batch_id, user.username, item_id, annotated))


@app.get("/api/inspections/{batch_id}/potatoes/{potato_no}/image")
def inspection_potato_image(batch_id: str, potato_no: int, user: User = Depends(current_user)) -> Response:
    return Response(vision.potato_crop(batch_id, user.username, potato_no), media_type="image/png")


@app.get("/api/inspections/{batch_id}/report.csv")
def inspection_report_csv(batch_id: str, user: User = Depends(current_user)) -> Response:
    return Response(vision.report_csv(batch_id, user.username), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{batch_id}.csv"'})


@app.get("/api/inspections/{batch_id}/report.json")
def inspection_report_json(batch_id: str, user: User = Depends(current_user)) -> JSONResponse:
    return JSONResponse(vision.report_json(batch_id, user.username),
                        headers={"Content-Disposition": f'attachment; filename="{batch_id}.json"'})


# --- memory and execution history ------------------------------------------------------

@app.get("/api/memory/status")
def memory_status(user: User = Depends(current_user)) -> dict:
    s = get_settings()
    return {"backend": s.memory_backend, "stats": get_store().stats(),
            "retention_days": s.memory_retention_days, "context_turns": s.memory_context_turns,
            "backups": [{"name": b.name, "bytes": b.stat().st_size} for b in memory_maintenance.list_backups()]}


@app.post("/api/memory/backup")
def memory_backup(user: User = Depends(current_user)) -> dict:
    auth.require(user, "memory.admin", "memory")
    result = memory_maintenance.backup()
    audit(user.username, "memory.backup", entity_type="memory", path=result["path"], bytes=result["bytes"])
    return result


# --- model evaluation lab -------------------------------------------------------------

@app.get("/api/ml/registry")
def ml_registry(user: User = Depends(current_user)) -> dict:
    from app.ml import registry

    registry.ensure_builtins()
    return {"models": registry.models(), "datasets": registry.datasets(), "evaluations": registry.evaluations()}


@app.post("/api/ml/evaluations/synthetic")
async def ml_evaluate_synthetic(user: User = Depends(current_user)) -> dict:
    """Evaluate the current detector and grader on the registered SYNTHETIC set (about 25 s, one at a time)."""
    from app.ml import datasets, evaluate

    auth.require(user, "ml.evaluate", "model")

    def job() -> dict:
        with vision.gate().slot():
            return evaluate.run(datasets.ensure_synthetic(), "test", user.username)

    result = await run_in_threadpool(job)
    audit(user.username, "ml.evaluate", entity_type="model", entity_id=evaluate.DETECTOR,
          dataset="synthetic", evaluation=result["detection_evaluation"])
    return result


@app.get("/api/quality/overview")
def quality_overview(days: int | None = Query(default=None, ge=1, le=3650), supplier: str | None = None,
                     user: User = Depends(current_user)) -> dict:
    from app import quality

    return quality.overview(user.username, days, supplier)


@app.get("/api/graphs/knowledge")
def graph_knowledge(user: User = Depends(current_user)) -> dict:
    from app import graphs

    return graphs.knowledge(user.username)


@app.get("/api/graphs/context")
def graph_context(run: str | None = None, user: User = Depends(current_user)) -> dict:
    from app import graphs

    return graphs.context(user.username, run)


@app.get("/api/graphs/procedure")
def graph_procedure(user: User = Depends(current_user)) -> dict:
    from app import graphs

    return graphs.procedure(user.username)


@app.get("/api/agents/activity")
def agents_activity(limit: int = Query(default=60, ge=1, le=300), user: User = Depends(current_user)) -> dict:
    from app import graphs

    return graphs.activity(limit)


# --- MCP server, connectors, Executive Export Studio, Enterprise X-Ray --------------------

@app.post("/mcp", include_in_schema=False)
async def mcp_endpoint(request: Request, user: User = Depends(current_user)):
    """MCP (JSON-RPC 2.0 over HTTP): approved, read-only, policy-filtered tools."""
    from fastapi.responses import JSONResponse, Response

    from app import mcp_server

    try:
        message = await request.json()
    except ValueError:
        return JSONResponse({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
    if isinstance(message, list):
        out = [r for m in message[:20] if (r := await run_in_threadpool(mcp_server.handle, m, user)) is not None]
        return JSONResponse(out) if out else Response(status_code=202)
    result = await run_in_threadpool(mcp_server.handle, message, user)
    return JSONResponse(result) if result is not None else Response(status_code=202)


@app.get("/api/connectors")
def connector_registry(user: User = Depends(current_user)) -> dict:
    from app import connectors

    return {"connectors": connectors.registry(), "states": list(connectors.STATES)}


@app.post("/api/connectors/{connector_id}/test")
def connector_test(connector_id: str, user: User = Depends(current_user)) -> dict:
    """Run a real read-only test request (only for configured adapters)."""
    from app import connectors

    auth.require(user, "connector.test", "connector", connector_id)
    return connectors.test_connection(connector_id, user.username)


@app.get("/api/exports")
def export_kinds(user: User = Depends(current_user)) -> dict:
    from app import exports

    return {"kinds": exports.KINDS, "classification": exports.CLASSIFICATION}


@app.get("/api/exports/{kind}.pdf")
def export_pdf(kind: str, ref: str | None = Query(default=None, max_length=80), user: User = Depends(current_user)):
    """A policy-filtered PDF built in memory for this user (no temporary files)."""
    from fastapi.responses import Response

    from app import exports

    pdf, name = exports.build(kind, user, ref)
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"})


@app.get("/api/xray/{agent_run_id}")
def xray(agent_run_id: str, user: User = Depends(current_user)) -> dict:
    """Sanitized execution graph for one of the user's answers (no payloads, prompts or secrets)."""
    from app import connectors, privacy
    from app.memory.store import get_store

    store = get_store()
    run = next((r for r in store.query("SELECT * FROM agent_runs WHERE id = ?", (agent_run_id,))), None)
    detail = json.loads(run["detail_json"]) if run else {}
    if not run or detail.get("username") != user.username:
        raise NotFound("Trace not found")
    calls = store.tool_calls_for(agent_run_id)
    reg = {c["id"]: c for c in connectors.registry()}
    tool_source = {"supplier_scorecard": "demo_data", "workforce_summary": "demo_data", "sales_summary": "demo_data",
                   "campaign_stock_risk": "demo_data", "inventory_status": "demo_data", "compliance_check": "demo_data",
                   "technology_health": "app_records", "enterprise_priorities": "demo_data",
                   "geo_origin_trace": "demo_data", "local_llm.answer": "local_llm"}
    steps = [{"id": "question", "label": "Your question", "kind": "input",
              "detail": privacy.scrub(run["input_summary"])},
             {"id": "orchestrator", "label": "Jerry orchestrator", "kind": "agent",
              "detail": f"Intents: {', '.join(detail.get('intents', [])) or 'none'}; mode {detail.get('mode')}"},
             {"id": "policy", "label": "Policy engine", "kind": "policy",
              "detail": "Tenant isolation, field classification and minimisation applied before tools return data"}]
    for i, c in enumerate(calls):
        src = tool_source.get(c["tool"], "app_records")
        steps.append({"id": f"tool{i}", "label": c["tool"], "kind": "tool", "status": c["status"],
                      "duration_ms": c["duration_ms"], "source": src,
                      "source_state": reg.get(src, {}).get("state"), "detail": "Read-only tool (arguments withheld)"})
    steps += [{"id": "evidence", "label": f"Evidence ({len(detail.get('sources', []))} source(s))", "kind": "evidence",
               "detail": "; ".join(s_["label"] for s_ in detail.get("sources", []))[:600]},
              {"id": "answer", "label": "Visual answer", "kind": "output",
               "detail": privacy.scrub(run["output_summary"])[:300]}]
    return {"agent_run_id": agent_run_id, "status": run["status"], "duration_ms": run["duration_ms"],
            "started_at": run["started_at"], "steps": steps, "real_trace": True,
            "external_systems": [{"id": k, "name": reg[k]["name"], "state": reg[k]["state"]}
                                 for k in ("databricks", "kubernetes", "mcp_server")],
            "note": "Recorded execution of this answer. Arguments, prompts and payloads are withheld; only "
                    "tool names, timings, statuses and source states are shown."}


# --- Privacy Shield (see app/privacy.py) ------------------------------------------------

@app.get("/api/suppliers")
def supplier_scorecard(user: User = Depends(current_user)) -> dict:
    """Supplier scorecard after server-side minimisation for this user (purpose: ui)."""
    from app import privacy

    recs, rep = privacy.suppliers(privacy.principal_for(user), "ui")
    return {"suppliers": recs, "policy": rep.as_dict(), "provenance": "synthetic"}


@app.get("/api/privacy/policy")
def privacy_policy(user: User = Depends(current_user)) -> dict:
    """The classification and minimisation rules (field categories only — never values)."""
    from app import privacy

    return {
        "levels": list(privacy.LEVELS),
        "datasets": {d: {lvl: sorted({privacy.FIELD_LABEL.get(f, f.replace("_", " ")) for f, lv in cls.items()
                                      if lv == lvl}) for lvl in privacy.LEVELS}
                     for d, cls in privacy.CLASSIFICATION.items()},
        "your_role": user.role, "your_tenant": privacy.principal_for(user).tenant,
        "confidential_visible_to_you": {d: user.role in roles for d, roles in privacy.CONFIDENTIAL_GRANTS.items()},
        "minimised_purposes": sorted(privacy.MINIMISED_PURPOSES),
        "note": "Enforced on the server before data reaches the browser, Jerry, the local model, MCP clients, exports, "
                "logs or memory. Workspace lenses (including CTO) never unlock restricted data.",
    }


# --- Flo & Jerry 3.0: enterprise pulse and continuity (see app/pulse.py) ------------------

class LensBody(BaseModel):
    lens: str = Field(max_length=20)


class JournalDecisionBody(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    decision: str = Field(min_length=1, max_length=1000)
    problem: str | None = Field(default=None, max_length=1000)
    recommendation: str | None = Field(default=None, max_length=1000)
    owner: str | None = Field(default=None, max_length=120)
    priority_id: str | None = Field(default=None, max_length=80)
    follow_up_on: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class DecisionUpdate(BaseModel):
    outcome: str | None = Field(default=None, max_length=1000)
    status: str | None = Field(default=None, pattern="^(open|done|dropped)$")
    follow_up_on: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class InvestigationBody(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    priority_id: str | None = Field(default=None, max_length=80)
    geo: dict | None = None
    notes: str | None = Field(default=None, max_length=4000)


class InvestigationUpdate(BaseModel):
    notes: str | None = Field(default=None, max_length=4000)
    status: str | None = Field(default=None, pattern="^(open|closed)$")


class FeedbackBody(BaseModel):
    helpful: bool
    conversation_id: str | None = Field(default=None, max_length=80)
    agent_run_id: str | None = Field(default=None, max_length=80)
    comment: str | None = Field(default=None, max_length=1000)


@app.get("/api/pulse")
def enterprise_pulse(mark: bool = True, user: User = Depends(current_user)) -> dict:
    """Briefing, since-last-visit, enterprise health and priorities for the signed-in user."""
    from app import pulse

    return pulse.pulse(user.username, user.role, mark)


@app.get("/api/me/lens")
def get_lens(user: User = Depends(current_user)) -> dict:
    from app import pulse

    return pulse.state(user.username, user.role)


@app.put("/api/me/lens")
def put_lens(body: LensBody, user: User = Depends(current_user)) -> dict:
    """Change the workspace lens. A lens changes layout and emphasis only, never permissions."""
    from app import pulse

    try:
        pulse.set_lens(user.username, body.lens)
    except ValueError as exc:
        raise PlatformError(str(exc)) from None
    return pulse.state(user.username, user.role)


@app.get("/api/priorities")
def list_priorities(user: User = Depends(current_user)) -> dict:
    from app import pulse

    return {"priorities": pulse.priorities(user.username)}


@app.get("/api/decisions")
def decisions(user: User = Depends(current_user)) -> dict:
    from app import pulse

    return {"decisions": pulse.list_decisions(user.username)}


@app.post("/api/decisions")
def add_decision(body: JournalDecisionBody, user: User = Depends(current_user)) -> dict:
    """Record a decision in the user's own journal. Nothing is executed in an enterprise system."""
    from app import pulse

    return pulse.add_decision(user.username, body.model_dump())


@app.patch("/api/decisions/{decision_id}")
def update_decision(decision_id: str, body: DecisionUpdate, user: User = Depends(current_user)) -> dict:
    from app import pulse

    try:
        return pulse.update_decision(user.username, decision_id, body.model_dump(exclude_unset=True))
    except KeyError:
        raise NotFound("Decision not found") from None


@app.get("/api/investigations")
def investigations(user: User = Depends(current_user)) -> dict:
    from app import pulse

    return {"investigations": pulse.list_investigations(user.username)}


@app.post("/api/investigations")
def add_investigation(body: InvestigationBody, user: User = Depends(current_user)) -> dict:
    from app import pulse

    return pulse.add_investigation(user.username, body.model_dump())


@app.patch("/api/investigations/{inv_id}")
def update_investigation(inv_id: str, body: InvestigationUpdate, user: User = Depends(current_user)) -> dict:
    from app import pulse

    try:
        return pulse.update_investigation(user.username, inv_id, body.model_dump(exclude_unset=True))
    except KeyError:
        raise NotFound("Investigation not found") from None


@app.post("/api/copilot/feedback")
def copilot_feedback(body: FeedbackBody, user: User = Depends(current_user)) -> dict:
    """Helpful / not helpful on a Jerry answer (stored; used in the Technology trust signal)."""
    from app import pulse

    pulse.add_feedback(user.username, body.model_dump())
    return {"ok": True}


@app.get("/api/technology")
def technology(user: User = Depends(current_user)) -> dict:
    from app import pulse

    return {"questions": pulse.technology(user.username)}


@app.get("/api/reports/weekly")
def weekly_report(user: User = Depends(current_user)) -> dict:
    from app import pulse

    return pulse.weekly_review(user.username)


@app.get("/api/reports/history")
def history_report(user: User = Depends(current_user)) -> dict:
    from app import pulse

    return pulse.history(user.username)


# --- global supply-chain maps (synthetic scenario; see app/geo.py) ----------------------

@app.get("/api/geo/network")
def geo_network(country: str | None = Query(default=None, max_length=8), tier: str | None = Query(default=None),
                user: User | None = Depends(optional_user)) -> dict:
    """Synthetic global network with provenance on every item; your own located inspections if signed in."""
    from app import geo

    if tier and tier not in geo.TIERS:
        raise PlatformError(f"tier must be one of {', '.join(geo.TIERS)}")
    return geo.network(user.username if user else None, country, tier)


@app.get("/api/geo/node/{node_id}")
def geo_node(node_id: str, user: User | None = Depends(optional_user)) -> dict:
    from app import geo

    try:
        return geo.node_detail(node_id, user.username if user else None)
    except KeyError:
        raise NotFound("Unknown site") from None


@app.get("/api/geo/risk")
def geo_risk(country: str | None = Query(default=None, max_length=8), node: str | None = None) -> dict:
    from app import geo

    return geo.simulate(country, node)


@app.get("/api/geo/suppliers")
def geo_suppliers() -> dict:
    """Network supplier names: an inspection batch with one of these as supplier appears on the map."""
    from app import geo

    return {"suppliers": geo.supplier_names()}


@app.get("/api/data-sources")
def data_sources(user: User = Depends(current_user)) -> dict:
    """Which potato data sources feed the app, with live record counts and honest status."""
    from app import datasources

    return {"sources": datasources.sources(user.username)}


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    """Prometheus exposition format. Disable with FOODCARE_METRICS_ENABLED=0; on Kubernetes, restrict it to
    the monitoring namespace with the NetworkPolicy in deploy/k8s."""
    from app import observability

    if not get_settings().metrics_enabled:
        raise NotFound("Metrics are disabled")
    return Response(observability.prometheus_text(), media_type="text/plain; version=0.0.4; charset=utf-8")


@app.get("/api/llm/usage")
def llm_usage(days: int = Query(default=30, ge=1, le=365), mine: bool = False,
              user: User = Depends(current_user)) -> dict:
    """Local-model token usage (all users, aggregated; or only yours with mine=true)."""
    from app import observability

    return observability.token_usage(days, user.username if mine else None)


@app.get("/api/system/resources")
def system_resources() -> dict:
    """Measured CPU/RAM, the backend process, and the local-model and vision queues (no model probe)."""
    from app import resources

    llm = local_llm.status() if not get_settings().live_available else local_llm.get_llm().status(probe=False)
    return {**resources.snapshot(), "llm": llm, "vision_queue": vision.gate().status(),
            "memory_db": get_store().stats()}


@app.get("/api/agents/runs")
def agent_runs(limit: int = Query(default=50, ge=1, le=200), user: User = Depends(current_user)) -> dict:
    runs = get_store().agent_runs(limit)
    for r in runs:
        r["tool_calls"] = get_store().tool_calls_for(r["id"])
    return {"runs": runs}


@app.get("/api/copilot/examples")
def copilot_examples() -> dict:
    return {"examples": copilot.EXAMPLES}


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
