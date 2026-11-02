"""Flying Florina 3.0: Agent Harness Control Tower, conversation memory, visual-analysis lab and software change impact APIs.

Control Tower panels read only recorded execution data (workflow_events, tool_invocations, policy_decisions, approvals, harness_plans,
llm_calls). Nothing is simulated or animated here.
"""

from __future__ import annotations

import base64
import io
import json
from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.api.deps import ApiError, envelope, require
from app.core import audit, db
from app.core.security import Actor, current_actor
from app.core.util import new_id, now_iso

router = APIRouter()
HARNESS_FLOWS = ("global_shortages", "demand_forecast", "supplier_delays", "supply_delay_impact", "component_degradation", "resilience_scenario",
                 "forecast_evidence", "forecast_accuracy", "agent_trace", "memory_recall", "visual_analysis", "change_impact")


# ------------------------------------------------------------------ probes
@router.get("/ready")
def ready(request: Request) -> dict[str, Any]:
    """Readiness: database reachable and every schema migration applied. Forecast models may still be fitting (reported, not required)."""
    from app.core import migrations
    from app.global_intel import forecast

    with db.session() as conn:
        applied = [m["version"] for m in migrations.status(conn)]
    missing = [v for v, _n, _s in migrations.MIGRATIONS if v not in applied]
    if missing:
        raise ApiError(503, "not_ready", f"Migrations pending: {missing}")
    return envelope(request, {"status": "ready", "migrations": applied, "forecast_models_ready": forecast._engine is not None})


# ------------------------------------------------------------------ control tower
@router.get("/api/harness/registry")
def harness_registry(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "harness:registry", "INTERNAL")
    from app.harness.core import registry_view

    return envelope(request, registry_view())


def _own_runs(actor: Actor) -> str:
    return "" if actor.role in ("security_officer", "auditor") else " AND user_id = ?"


@router.get("/api/harness/control-tower")
def control_tower(request: Request, run_id: str | None = Query(None, max_length=40), actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "harness:control_tower", "INTERNAL")
    from app.llm import telemetry
    from app.workflows.engine import events
    from app.workflows.graphs import GRAPHS

    own = _own_runs(actor)
    args: tuple = () if not own else (actor.id,)
    runs = db.query(f"SELECT id, workflow, query, status, created, updated, user_id FROM workflow_runs WHERE 1=1{own} ORDER BY created DESC LIMIT 60", args)  # noqa: S608
    sel = next((r for r in runs if r["id"] == run_id), None) if run_id else next((r for r in runs if r["workflow"] in GRAPHS), None)
    panel1 = panel2 = None
    if sel:
        evs = events(sel["id"])
        g = GRAPHS[sel["workflow"]]().describe() if sel["workflow"] in GRAPHS else None
        per: dict[str, dict[str, Any]] = {}
        for e in evs:
            p = per.setdefault(e["step"], {"step": e["step"], "agent": e["agent"], "status": "pending", "attempts": 0, "retries": 0, "duration_ms": 0.0})
            p["status"] = e["status"]
            p["attempts"] = max(p["attempts"], e["attempt"] or 0)
            p["retries"] += 1 if e["status"] == "retrying" else 0
            p["duration_ms"] = round(p["duration_ms"] + (e["duration_ms"] or 0), 1)
        tools = db.query("SELECT tool, status, duration_ms, ts FROM tool_invocations WHERE run_id = ? ORDER BY ts", (sel["id"],))
        plan = db.query_one("SELECT * FROM harness_plans WHERE run_id = ?", (sel["id"],))
        panel1 = {"run": sel, "graph": g, "nodes": list(per.values()), "tools": tools,
                  "plan": {k: (db.jload(plan[k]) if k.endswith("_json") else plan[k]) for k in plan} if plan else None}
        panel2 = [{k: e[k] for k in ("id", "ts", "step", "agent", "status", "attempt", "duration_ms", "summary")} for e in evs]
    scope = "" if not own else " WHERE run_id IN (SELECT id FROM workflow_runs WHERE user_id = ?)"
    dec = db.query(f"SELECT decision, policy_id, action, tool, reason, ts FROM policy_decisions{scope} ORDER BY ts DESC LIMIT 400", args)  # noqa: S608
    approvals = db.query("SELECT id, title, status, requested_by, requested_at, risk FROM approvals ORDER BY requested_at DESC LIMIT 50")
    plans = db.query(f"SELECT run_id, intent, usage_json, outcome, budget_json FROM harness_plans{' WHERE user_id = ?' if own else ''} ORDER BY ts DESC LIMIT 200", args)  # noqa: S608
    gov_events = db.query(f"SELECT step, status, summary FROM workflow_events WHERE step IN ('evidence_challenger','governance_validation','evidence_validation')"  # noqa: S608 - fixed SQL fragments only; values are bound parameters
                          f"{' AND run_id IN (SELECT id FROM workflow_runs WHERE user_id = ?)' if own else ''} ORDER BY id DESC LIMIT 300", args)  # noqa: S608
    panel3 = {"allowed": sum(d["decision"] == "ALLOW" for d in dec), "denied": sum(d["decision"] == "DENY" for d in dec),
              "by_policy": Counter(d["policy_id"] for d in dec if d["decision"] == "DENY").most_common(8),
              "blocked": [d for d in dec if d["decision"] == "DENY"][:12],
              "pending_approvals": [a for a in approvals if a["status"] == "pending"], "approved": sum(a["status"] == "approved" for a in approvals),
              "validation_failures": [e for e in gov_events if e["status"] == "failed" or "Missing" in (e["summary"] or "")][:12]}
    m = telemetry.metrics()
    active = db.query_one(f"SELECT COUNT(*) n FROM workflow_runs WHERE status IN ('queued','running'){own}", args)["n"]  # noqa: S608
    from app.llm.gateway import gateway

    st = gateway().status()
    panel4 = {"qwen": {"available": st.get("available"), "model": st.get("discovery", {}).get("model"), "mode": st.get("mode"), "required": st.get("required"),
                       "reason": st.get("discovery", {}).get("reason")}, "metrics": m, "queue_depth": active,
              "note": "Latency, tokens, CPU and memory come from the local llm_calls table and the operating system; empty until Qwen answers."}
    fl = db.query(f"SELECT workflow, status FROM workflow_runs WHERE workflow IN ({','.join('?' * len(HARNESS_FLOWS))}){own}", (*HARNESS_FLOWS, *args))  # noqa: S608
    tool_rows = db.query(f"SELECT status FROM tool_invocations WHERE ts > datetime('now','-30 days'){' AND actor = ?' if own else ''}", args)  # noqa: S608
    chal = [e for e in gov_events if e["step"] == "evidence_challenger"]
    usages = [db.jload(p["usage_json"], {}) for p in plans]
    from app.global_intel.forecast import _engine

    panel5 = {"task_success_rate": round(sum(r["status"] in ("completed", "awaiting_approval") for r in fl) / len(fl), 4) if fl else None, "harness_runs": len(fl),
              "evidence_coverage": round(sum(p["outcome"] == "validated" for p in plans) / len(plans), 4) if plans else None,
              "tool_call_reliability": round(sum(t["status"] == "ok" for t in tool_rows) / len(tool_rows), 4) if tool_rows else None, "tool_calls": len(tool_rows),
              "hallucination_eval": {"explanations_checked": len(chal), "passed": sum("Verdict pass" in (e["summary"] or "") for e in chal),
                                     "note": "Evidence Challenger verdicts on Qwen explanations (0 when Qwen is not connected)."},
              "forecast_quality": {k: v for k, v in ((_engine.metrics.get("demand", {}).get("by_horizon", {}).get("30d", {}) if _engine else {}) or {}).items()
                                   if k in ("mae", "coverage_80", "mae_improvement_vs_moving_average")},
              "workflow_failure_rate": round(sum(r["status"] in ("failed", "completed_with_errors", "budget_exceeded") for r in fl) / len(fl), 4) if fl else None,
              "mean_tool_calls_per_run": round(sum(u.get("tool_calls", 0) for u in usages) / len(usages), 2) if usages else None}
    retries = db.query(f"SELECT run_id, step, agent, attempt, summary, ts FROM workflow_events WHERE status = 'retrying'"  # noqa: S608 - fixed SQL fragments only; values are bound parameters
                       f"{' AND run_id IN (SELECT id FROM workflow_runs WHERE user_id = ?)' if own else ''} ORDER BY id DESC LIMIT 20", args)  # noqa: S608
    failed = [r for r in runs if r["status"] in ("failed", "completed_with_errors", "budget_exceeded", "cancelled")]
    panel6 = {"failed_runs": failed[:15], "retries": retries, "escalations": panel3["pending_approvals"],
              "partial_results": [p for p in plans if p["outcome"] == "missing_evidence"][:15]}
    return envelope(request, {"runs": runs, "selected": panel1, "timeline": panel2, "governance": panel3, "model": panel4, "evaluation": panel5,
                              "recovery": panel6, "mode": "live (recorded events only)"})


# ------------------------------------------------------------------ memory
@router.get("/api/memory/conversations")
def memory_list(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "memory:conversations", "INTERNAL")
    from app.harness import memory

    return envelope(request, memory.conversations(actor.id))


@router.get("/api/memory/conversations/{session_id}")
def memory_get(request: Request, session_id: str, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "memory:conversations", "INTERNAL")
    from app.harness import memory

    msgs = memory.history(session_id[:40], actor.id)
    s = db.query_one("SELECT * FROM conversation_summaries WHERE session_id = ? AND user_id = ?", (session_id[:40], actor.id))
    return envelope(request, {"messages": msgs, "summary": s})


@router.post("/api/memory/conversations/{session_id}/delete")
def memory_delete(request: Request, session_id: str, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "memory:conversations", "INTERNAL")
    from app.harness import memory

    if not memory.delete(session_id[:40], actor.id):
        raise ApiError(404, "not_found", "No such conversation for this user.")
    audit.append(actor.id, "memory.deleted", f"Conversation {session_id[:40]} deleted by its owner", {"session_id": session_id[:40]})
    return envelope(request, {"deleted": session_id[:40]})


class PrefBody(BaseModel):
    key: str = Field(max_length=40, pattern=r"^[a-z_]+$")
    value: str = Field(max_length=200)


@router.get("/api/memory/preferences")
def prefs_get(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    from app.harness import memory

    return envelope(request, memory.preferences(actor.id))


@router.post("/api/memory/preferences")
def prefs_set(request: Request, body: PrefBody, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "memory:preferences", "INTERNAL")
    from app.harness import memory

    memory.set_preference(actor.id, body.key, body.value)
    return envelope(request, memory.preferences(actor.id))


# ------------------------------------------------------------------ visual lab
@router.get("/api/visual/capabilities")
def visual_caps(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "visual:capabilities", "INTERNAL")
    from app.visual import lab

    return envelope(request, lab.capabilities())


@router.get("/api/visual/demo")
def visual_demo(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "visual:demo", "INTERNAL")
    from app.visual import lab

    items = lab.demo_set()
    out = []
    for it in items:
        files = [it["file"]] if it["kind"] == "image" else [f["file"] for f in it["frames"]]
        out.append({**it, "thumbs": [base64.b64encode(lab.demo_image(f)).decode() for f in files]})
    return envelope(request, out, provenance={"source": "synthetic labelled frames rendered locally", "synthetic": True})


@router.get("/api/visual/evaluation")
def visual_eval(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "visual:evaluation", "INTERNAL")
    from app.visual import lab

    return envelope(request, lab.evaluate())


class DemoBody(BaseModel):
    item_id: str = Field(max_length=12, pattern=r"^(IMG|CLIP)-\d{1,2}$")


def _store(actor: Actor, source: str, filename: str, sha: str, result: dict[str, Any]) -> str:
    aid = new_id("VIS")
    slim = {k: v for k, v in result.items() if k != "frames"} | {"frames": [{k: v for k, v in f.items() if k != "thumbnail_png_b64"} for f in result["frames"]]}
    db.execute("INSERT INTO visual_analyses VALUES (?,?,?,?,?,?,?,?,?)", (aid, actor.id, now_iso(), source, filename[:120], sha, result["frames_total"], result["method"], db.jdump(slim)))
    audit.append(actor.id, "visual.analysed", f"{source}: {result['summary'][:120]}", {"analysis_id": aid, "sha256": sha, "method": result["method"]})
    return aid


@router.post("/api/visual/analyze-demo")
def visual_analyze_demo(request: Request, body: DemoBody, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "analyze_media", "visual:analyze", "INTERNAL")
    from PIL import Image

    from app.visual import lab

    it = next((i for i in lab.demo_set() if i["id"] == body.item_id), None)
    if not it:
        raise ApiError(404, "not_found", "Unknown demo item.")
    files = [it] if it["kind"] == "image" else it["frames"]
    frames = [Image.open(io.BytesIO(lab.demo_image(f["file"]))).convert("RGB") for f in files]
    r = lab.analyze_frames(frames)
    for f, gt in zip(r["frames"], files, strict=True):
        f["ground_truth"] = gt["label"]
        f["ground_truth_object"] = gt["object"]
    aid = _store(actor, "demo", it["id"], it["id"], r)
    return envelope(request, {**r, "analysis_id": aid, "item": it["id"]})


@router.post("/api/visual/upload")
async def visual_upload(request: Request, file: UploadFile = File(...), actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "analyze_media", "visual:analyze", "INTERNAL")
    from app.visual import lab

    raw = await file.read(lab.MAX_UPLOAD + 1)
    try:
        frames = lab.frames_from_upload(raw, file.filename or "upload")
        r = lab.analyze_frames(frames)
    except (ValueError, OSError) as err:
        raise ApiError(422, "unsupported_media", str(err)) from err
    aid = _store(actor, "upload", file.filename or "upload", lab.sha256(raw), r)
    return envelope(request, {**r, "analysis_id": aid, "stored": "hash and results only; pixels were not stored"})


@router.get("/api/visual/history")
def visual_history(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    rows = db.query("SELECT id, ts, source, filename, frames, method, result_json FROM visual_analyses WHERE user_id = ? ORDER BY ts DESC LIMIT 50", (actor.id,))
    for r in rows:
        res = db.jload(r.pop("result_json"), {})
        r["summary"], r["frames_flagged"] = res.get("summary"), res.get("frames_flagged")
    return envelope(request, rows)


@router.get("/api/visual/report/{analysis_id}", response_class=PlainTextResponse)
def visual_report(request: Request, analysis_id: str, actor: Actor = Depends(current_actor)) -> PlainTextResponse:
    require(actor, "export", "visual:report", "INTERNAL", destination="local_download")
    from app.visual import lab

    r = db.query_one("SELECT * FROM visual_analyses WHERE id = ? AND user_id = ?", (analysis_id[:40], actor.id))
    if not r:
        raise ApiError(404, "not_found", "No such analysis.")
    md = lab.report_markdown(json.loads(r["result_json"]), r["filename"])
    return PlainTextResponse(md, media_type="text/markdown", headers={"Content-Disposition": f'attachment; filename="{analysis_id[:40]}.md"'})


# ------------------------------------------------------------------ software change impact
@router.get("/api/change-impact/overview")
def ci_overview(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "engineering:change_impact", "INTERNAL")
    from app.engineering import change_impact

    return envelope(request, change_impact.overview(), provenance={"source": "static analysis of this repository", "synthetic": False})


@router.get("/api/change-impact/analyze")
def ci_analyze(request: Request, target: str = Query(..., min_length=2, max_length=120, pattern=r"^[A-Za-z0-9_./{}\-]+$"),
               actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "engineering:change_impact", "INTERNAL")
    from app.engineering import change_impact

    return envelope(request, change_impact.analyze(target), provenance={"source": "static analysis of this repository", "synthetic": False})


@router.get("/api/change-impact/traceability")
def ci_trace(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "engineering:change_impact", "INTERNAL")
    from app.engineering import change_impact

    return envelope(request, change_impact.traceability())


class ConfigBody(BaseModel):
    before: dict[str, Any]
    after: dict[str, Any]


@router.post("/api/change-impact/compare-config")
def ci_config(request: Request, body: ConfigBody, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "engineering:change_impact", "INTERNAL")
    from app.engineering import change_impact

    if len(json.dumps(body.before)) + len(json.dumps(body.after)) > 100_000:
        raise ApiError(413, "too_large", "Configuration too large.")
    return envelope(request, change_impact.compare_config(body.before, body.after))


@router.get("/api/change-impact/report", response_class=PlainTextResponse)
def ci_report(request: Request, target: str = Query(..., min_length=2, max_length=120, pattern=r"^[A-Za-z0-9_./{}\-]+$"),
              actor: Actor = Depends(current_actor)) -> PlainTextResponse:
    require(actor, "export", "engineering:report", "INTERNAL", destination="local_download")
    from app.engineering import change_impact

    r = change_impact.analyze(target)
    if r.get("error"):
        raise ApiError(404, "not_found", r["error"])
    lines = [f"# Release impact report: {target}", "", "> Static import analysis of this repository. Not line coverage; not a certification argument.", "",
             f"Risk: **{r['risk']}** · modules {len(r['affected_modules'])} · routes {len(r['affected_routes'])} · frontend files {len(r['affected_frontend'])}", "",
             "## Recommended regression tests", ""] + [f"* `{t['test']}` (via {', '.join(t['via'])})" for t in r["recommended_tests"]] + \
            ["", "## Affected modules", ""] + [f"* `{m['module']}` ({m['distance']} hop(s))" for m in r["affected_modules"]] + \
            ["", "## Affected API routes", ""] + [f"* {x}" for x in r["affected_routes"]] + \
            ["", "## Requirements", ""] + [f"* {q['id']} {q['title']} — {q['status']}" for q in r["requirements"]] + \
            ["", "## Untested affected modules", ""] + [f"* `{m}`" for m in r["untested_affected_modules"]]
    return PlainTextResponse("\n".join(lines), media_type="text/markdown", headers={"Content-Disposition": 'attachment; filename="release_impact.md"'})
