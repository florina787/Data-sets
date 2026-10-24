"""Core API: identity, demo control, chat/workflows, operational read models, simulation, reports."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import ApiError, envelope, labels_for, require
from app.core import audit, db, egress
from app.core.config import APP_VERSION, SEED, get_settings
from app.core.security import Actor, current_actor, issue_token, load_actor
from app.core.util import DEMO_TODAY
from app.reports import generator as reports
from app.retrieval.search import get_document, search
from app.seed.generator import reset_database
from app.services import catalog, data
from app.simulation.engine import DelayScenarioInputs, RoiInputs, compare_delays, roi
from app.workflows import engine, orchestrator
from app.workflows.graphs import GRAPHS

router = APIRouter()


# ---------------------------------------------------------------- health, config, identity

@router.get("/health")
def health(request: Request) -> dict[str, Any]:
    return envelope(request, {"status": "ok", "version": APP_VERSION})


@router.get("/api/config")
def config(request: Request) -> dict[str, Any]:
    s = get_settings()
    return envelope(request, {
        "app": "Flying_Florina", "version": APP_VERSION, "tagline": "From legacy systems to trusted industrial intelligence.",
        "demo_mode": s.demo_mode, "offline_mode": s.offline_mode, "llm_enabled": s.llm_enabled,
        "brand_assets_authorized": s.brand_assets_authorized, "seed": SEED, "demo_today": DEMO_TODAY,
        "inference": "local rules engine" + (" + optional local LLM" if s.llm_enabled else ""),
        "disclaimer": "Independent concept demo | Not affiliated with or endorsed by IFS",
    })


class LoginBody(BaseModel):
    user_id: str = Field(max_length=64)


@router.post("/api/auth/login")
def login(request: Request, body: LoginBody) -> dict[str, Any]:
    if not get_settings().demo_mode:
        raise ApiError(403, "demo_login_disabled", "Persona login exists only in DEMO_MODE. Configure an enterprise IdP.")
    actor = load_actor(body.user_id)
    if actor is None:
        raise ApiError(404, "unknown_user", "No such synthetic user.")
    audit.append(actor.id, "auth.login", f"Demo login as {actor.id}", {"role": actor.role})
    return envelope(request, {"token": issue_token(actor.id), "actor": actor.as_dict()})


@router.get("/api/auth/me")
def me(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    return envelope(request, actor.as_dict())


@router.get("/api/personas")
def personas(request: Request) -> dict[str, Any]:
    return envelope(request, catalog.PERSONAS)


@router.get("/api/demo/status")
def demo_status(request: Request) -> dict[str, Any]:
    meta = {r["key"]: r["value"] for r in db.query("SELECT key, value FROM meta")}
    return envelope(request, {"seed": meta.get("seed"), "demo_today": meta.get("demo_today"), "counts": json.loads(meta.get("counts", "{}")),
                              "egress_guard": egress.status(), "offline_mode": get_settings().offline_mode,
                              "kill_switch": (db.query_one("SELECT value FROM governance_state WHERE key='kill_switch'") or {}).get("value"),
                              "export_tool_executed": meta.get("export_tool_executed")})


@router.post("/api/demo/reset")
def demo_reset(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    if not get_settings().demo_mode:
        raise ApiError(403, "demo_only", "Reset is available only in DEMO_MODE.")
    counts = reset_database()
    from app.services import tools

    tools._registry = None
    return envelope(request, {"reset": True, "counts": counts}, warnings=["All sessions, approvals, decisions and audit events were regenerated."])


# ---------------------------------------------------------------- sessions, chat, workflows

class SessionBody(BaseModel):
    title: str = Field(default="New session", max_length=120)


@router.get("/api/sessions")
def list_sessions(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    sessions = db.query("SELECT * FROM sessions WHERE user_id = ? ORDER BY updated DESC LIMIT 50", (actor.id,))
    for s in sessions:
        s["runs"] = db.query("SELECT id, query, workflow, status, created FROM workflow_runs WHERE session_id = ? ORDER BY created", (s["id"],))
    return envelope(request, sessions)


@router.post("/api/sessions")
def create_session(request: Request, body: SessionBody, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    sid = orchestrator.ensure_session(actor, None, body.title)
    return envelope(request, {"id": sid, "title": body.title})


class QueryBody(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    persona: str | None = Field(default=None, max_length=64)
    session_id: str | None = Field(default=None, max_length=64)
    wait: bool = True
    options: dict[str, Any] = Field(default_factory=dict)


ALLOWED_OPTIONS = {"inject_failure", "inject_failure_permanent", "step_delay_ms", "inject_tool_timeout", "simulation", "roi", "force_workflow"}


@router.post("/api/chat/query")
def chat_query(request: Request, body: QueryBody, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    unknown = set(body.options) - ALLOWED_OPTIONS
    if unknown:
        raise ApiError(422, "unknown_option", f"Unsupported options: {sorted(unknown)}")
    state = orchestrator.start(actor, body.query, body.persona, body.session_id, body.options, wait=body.wait)
    run = orchestrator.get_run(state.run_id)
    return envelope(request, _run_view(run), warnings=state.warnings if body.wait else [])


def _run_view(run: dict[str, Any]) -> dict[str, Any]:
    st = run["state"]
    finished = bool(st.get("workspace")) and run["status"] not in ("queued", "running")
    return {"run_id": run["id"], "session_id": run["session_id"], "workflow": run["workflow"], "status": run["status"], "query": run["query"],
            "finished": finished, "state": st, "graph": GRAPHS[run["workflow"]]().describe() if run["workflow"] in GRAPHS else None,
            "events": engine.events(run["id"]), "replay_of": run.get("replay_of"), "options": run.get("options", {})}


def _owned_run(run_id: str, actor: Actor) -> dict[str, Any]:
    run = orchestrator.get_run(run_id)
    if not run:
        raise ApiError(404, "not_found", "Workflow run not found.")
    if run["user_id"] != actor.id and actor.role not in ("security_officer", "auditor"):
        raise ApiError(403, "not_owner", "Runs are visible to their owner, security officers and auditors.")
    return run


@router.get("/api/workflows")
def list_runs(request: Request, limit: int = Query(50, ge=1, le=200), actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    if actor.role in ("security_officer", "auditor"):
        runs = db.query("SELECT id, user_id, persona, query, workflow, status, created, replay_of FROM workflow_runs ORDER BY created DESC LIMIT ?", (limit,))
    else:
        runs = db.query("SELECT id, user_id, persona, query, workflow, status, created, replay_of FROM workflow_runs WHERE user_id = ? ORDER BY created DESC LIMIT ?", (actor.id, limit))
    return envelope(request, runs)


@router.get("/api/workflows/{run_id}")
def get_workflow(request: Request, run_id: str, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    return envelope(request, _run_view(_owned_run(run_id, actor)))


@router.get("/api/workflows/{run_id}/events")
def workflow_events(request: Request, run_id: str, after: int = Query(0, ge=0), actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    run = _owned_run(run_id, actor)
    return envelope(request, {"status": run["status"], "finished": bool(run["state"].get("workspace")), "events": engine.events(run_id, after)})


@router.get("/api/workflows/{run_id}/stream")
async def workflow_stream(run_id: str, actor: Actor = Depends(current_actor)) -> StreamingResponse:
    _owned_run(run_id, actor)

    async def gen():
        last = 0
        for _ in range(600):
            evs = engine.events(run_id, last)
            for e in evs:
                last = e["id"]
                yield f"event: step\ndata: {json.dumps(e, default=str)}\n\n"
            run = orchestrator.get_run(run_id)
            if run and run["state"].get("workspace") and run["status"] not in ("queued", "running"):
                yield f"event: done\ndata: {json.dumps({'status': run['status']})}\n\n"
                return
            await asyncio.sleep(0.25)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-store"})


@router.post("/api/workflows/{run_id}/cancel")
def cancel_workflow(request: Request, run_id: str, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    _owned_run(run_id, actor)
    return envelope(request, {"cancelled": orchestrator.cancel(run_id, actor)})


@router.post("/api/workflows/{run_id}/replay")
def replay_workflow(request: Request, run_id: str, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    run = _owned_run(run_id, actor)
    opts = {k: v for k, v in run["options"].items() if k in ALLOWED_OPTIONS}
    state = orchestrator.start(actor, run["query"], run["persona"], run["session_id"], opts, wait=True, replay_of=run_id)
    new = orchestrator.get_run(state.run_id)
    a, b = run["state"], new["state"]
    comparable = ["workflow", "answer"]
    same = {k: a.get(k) == b.get(k) for k in comparable}
    return envelope(request, {**_run_view(new), "reproducibility": {"replay_of": run_id, "identical_fields": same,
                                                                   "note": "Run IDs, timestamps, approval and draft IDs differ by design."}})


# ---------------------------------------------------------------- operational read models

@router.get("/api/fleet/overview")
def fleet_overview(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "fleet:overview", "INTERNAL")
    return envelope(request, data.fleet_overview())


@router.get("/api/fleet/trends")
def fleet_trends(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "fleet:trends", "INTERNAL")
    return envelope(request, {"maintenance_by_month": data.maintenance_frequency_by_month(), "downtime_by_month": data.downtime_by_month(),
                              "vibration_band": data.fleet_vibration_band(90), "incidents": data.incidents()})


@router.get("/api/aircraft/{ac_id}")
def aircraft(request: Request, ac_id: str, days: int = Query(90, ge=7, le=548), actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", f"aircraft:{ac_id}", "INTERNAL")
    d = data.aircraft_detail(ac_id.upper())
    if not d:
        raise ApiError(404, "not_found", "Aircraft not in synthetic fleet.")
    allowed = labels_for(actor)
    d["open_work_orders"] = [w for w in d["open_work_orders"] if w["classification"] in allowed]
    d["telemetry"] = data.telemetry_series(ac_id.upper(), days)
    return envelope(request, d, warnings=["Health score is a demo heuristic, not an airworthiness determination."])


@router.get("/api/maintenance/work-orders")
def work_orders(request: Request, status: str | None = Query(None, max_length=20), aircraft_id: str | None = Query(None, max_length=10),
                limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0), actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "work_orders", "INTERNAL")
    res = data.work_orders(status, aircraft_id, labels_for(actor), limit, offset)
    hidden = data.work_orders(status, aircraft_id, None, 1, 0)["total"] - res["total"]
    res["withheld_by_classification"] = hidden
    res["duplicates"] = data.duplicate_work_orders()
    return envelope(request, res, warnings=[f"{hidden} work orders withheld by classification."] if hidden else [])


@router.get("/api/parts/availability")
def parts_availability(request: Request, part_number: str | None = Query(None, max_length=12), actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "parts:availability", "INTERNAL")
    return envelope(request, {"items": data.part_availability(part_number.upper() if part_number else None),
                              "critical": data.critical_stock(), "suppliers": data.supplier_reliability(),
                              "substitutes": data.substitution_check(part_number.upper()) if part_number else []})


@router.get("/api/incidents")
def incidents(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "incidents", "INTERNAL")
    return envelope(request, data.incidents())


@router.get("/api/documents")
def documents(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    allowed = labels_for(actor)
    docs = data.document_freshness()
    visible = [d for d in docs if d["classification"] in allowed]
    return envelope(request, {"items": visible, "withheld": len(docs) - len(visible)})


@router.get("/api/documents/search")
def doc_search(request: Request, q: str = Query(min_length=2, max_length=300), actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "search", "documents", "PUBLIC")
    return envelope(request, search(actor, q, 10))


@router.get("/api/documents/{doc_id}")
def document(request: Request, doc_id: str, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    d = db.query_one("SELECT classification FROM documents WHERE id = ?", (doc_id,))
    if not d:
        raise ApiError(404, "not_found", "Document not found.")
    require(actor, "read", f"doc:{doc_id}", d["classification"])
    doc, why = get_document(actor, doc_id)
    if doc is None:
        raise ApiError(403, "policy_denied", why)
    return envelope(request, doc)


@router.get("/api/agents/catalog")
def agents_catalog(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    from app.services.tools import registry

    stats = {r["agent"]: r for r in db.query("SELECT agent, COUNT(*) steps, SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) failed, "
                                              "AVG(duration_ms) avg_ms FROM workflow_events WHERE status IN ('completed','failed') GROUP BY agent")}
    tools = registry().tools
    return envelope(request, [{"name": n, "description": d, "tools": [{"name": t, "version": tools[t].version} for t in ts if t in tools],
                               "steps_run": (stats.get(n) or {}).get("steps", 0), "failures": (stats.get(n) or {}).get("failed", 0),
                               "avg_ms": round((stats.get(n) or {}).get("avg_ms") or 0, 1)} for n, d, ts in catalog.AGENTS])


@router.get("/api/integrations")
def integrations(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    return envelope(request, {"connectors": catalog.connectors(), "matrix": catalog.INTEGRATION_MATRIX})


# ---------------------------------------------------------------- simulation

@router.post("/api/simulations/compare")
def simulate(request: Request, body: DelayScenarioInputs, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "simulate", "simulation:delay", "INTERNAL")
    res = compare_delays(body)
    _save_sim(actor, body.model_dump(), res)
    return envelope(request, res)


@router.post("/api/simulations/roi")
def simulate_roi(request: Request, body: RoiInputs, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "query", "simulation:roi", "INTERNAL")
    res = roi(body)
    _save_sim(actor, body.model_dump(), res)
    return envelope(request, res)


def _save_sim(actor: Actor, inputs: dict[str, Any], res: dict[str, Any]) -> None:
    from app.core.util import new_id, now_iso

    with db.session(write=True) as conn:
        conn.execute("INSERT INTO simulations VALUES (?,?,?,?,?,?)", (new_id("SIM"), now_iso(), actor.id, db.jdump(inputs), db.jdump(res), res.get("version", "roi-1")))


@router.get("/api/simulations")
def simulations(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    rows_ = db.query("SELECT id, ts, actor, version, inputs_json FROM simulations WHERE actor = ? ORDER BY ts DESC LIMIT 30", (actor.id,))
    for r in rows_:
        r["inputs"] = db.jload(r.pop("inputs_json"), {})
    return envelope(request, rows_)


# ---------------------------------------------------------------- reports

class ReportBody(BaseModel):
    kind: str = Field(max_length=40)
    fmt: str = Field(max_length=8)
    run_id: str | None = Field(default=None, max_length=64)


@router.post("/api/reports/generate")
def generate_report(request: Request, body: ReportBody, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    label = reports.LABEL.get(body.kind, "INTERNAL")
    if body.kind == "audit_packet":
        require(actor, "audit_export", "report:audit_packet", label)
    require(actor, "export", f"report:{body.kind}", label, destination="local_download")
    ctx: dict[str, Any] = {}
    if body.run_id:
        ctx = _owned_run(body.run_id, actor)["state"]
    elif body.kind in ("executive_brief", "one_page_brief"):
        from app.integrations.legacy import xray
        from app.simulation.engine import RoiInputs, roi as roi_fn

        months = data.downtime_by_month()
        ls = xray.landscape()
        from app.core import policy as pol

        ctx = {"exec": {"fleet": {k: v for k, v in data.fleet_overview().items() if k in ("total_aircraft", "available_pct", "aog_count", "open_work_orders")},
                        "downtime_last": months[-1], "downtime_prev": months[-2], "legacy": ls["summary"],
                        "denied_actions": len(pol.list_decisions("DENY", 1000))},
               "roi": roi_fn(RoiInputs()), "roadmap": xray.roadmap()}
    try:
        rep = reports.generate(actor, body.kind, body.fmt, ctx)
    except ValueError as err:
        raise ApiError(422, "invalid_report", str(err)) from err
    return envelope(request, rep)


@router.get("/api/reports")
def list_reports(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    rows_ = db.query("SELECT id, ts, actor, kind, fmt, sha256, classification, title FROM reports WHERE actor = ? ORDER BY ts DESC LIMIT 100", (actor.id,))
    return envelope(request, rows_)


MEDIA = {"pdf": "application/pdf", "md": "text/markdown", "html": "text/html", "json": "application/json", "csv": "text/csv"}


@router.get("/api/reports/{report_id}/download")
def download_report(report_id: str, actor: Actor = Depends(current_actor)) -> FileResponse:
    rep = reports.get(report_id)
    if not rep:
        raise ApiError(404, "not_found", "Report not found.")
    if rep["actor"] != actor.id and actor.role not in ("security_officer", "auditor"):
        raise ApiError(403, "not_owner", "Reports are downloadable by their creator, security officers and auditors.")
    require(actor, "export", f"report:{report_id}", rep["classification"], destination="local_download")
    from pathlib import Path

    path = Path(rep["path"]).resolve()
    if get_settings().reports_dir.resolve() not in path.parents:
        raise ApiError(400, "bad_path", "Report path outside the reports directory.")
    return FileResponse(path, media_type=MEDIA.get(rep["fmt"], "application/octet-stream"), filename=f"flying_florina_{rep['kind']}_{report_id}.{rep['fmt']}")
