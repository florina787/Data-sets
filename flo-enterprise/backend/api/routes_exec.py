"""Executive Command Center, decision memory, exports and background jobs."""
from __future__ import annotations

import csv
import io
import uuid
from datetime import date, datetime, timezone
from html import escape

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from analytics import decisions as dec
from analytics import service as S
from backend.api.deps import Ctx, authorize, cached, current, require
from backend.config import get_settings
from backend.db import models as m
from governance import audit

router = APIRouter(prefix="/api")


def _filters(asset_class: str | None, vehicle: str | None, region: str | None) -> dict:
    return {"asset_class": asset_class, "vehicle": vehicle, "region": region}


@router.get("/executive/kpis")
def kpis(request: Request, months: int = Query(12, ge=1, le=24), ctx: Ctx = Depends(require("exec:read"))):
    return cached(ctx, request, lambda: S.executive_kpis(ctx.adapters, months))


@router.get("/executive/aum-trend")
def aum_trend(request: Request, months: int = Query(24, ge=1, le=24), group_by: str = Query("asset_class", pattern="^(asset_class|vehicle|region|strategy)$"),
              asset_class: str | None = None, vehicle: str | None = None, region: str | None = None, ctx: Ctx = Depends(require("finance:read"))):
    return cached(ctx, request, lambda: S.aum_trend(ctx.adapters, months, _filters(asset_class, vehicle, region), group_by))


@router.get("/executive/aum-waterfall")
def aum_waterfall(request: Request, months: int = Query(12, ge=1, le=24), asset_class: str | None = None, vehicle: str | None = None,
                  region: str | None = None, ctx: Ctx = Depends(require("finance:read"))):
    return cached(ctx, request, lambda: S.aum_waterfall(ctx.adapters, months, _filters(asset_class, vehicle, region)))


@router.get("/executive/revenue-expenses")
def revenue_expenses(request: Request, months: int = Query(24, ge=1, le=24), ctx: Ctx = Depends(require("finance:read"))):
    return cached(ctx, request, lambda: S.revenue_expenses(ctx.adapters, months))


@router.get("/executive/net-flows")
def net_flows(request: Request, months: int = Query(24, ge=1, le=24), group_by: str = Query("vehicle", pattern="^(asset_class|vehicle|region|strategy)$"),
              asset_class: str | None = None, vehicle: str | None = None, ctx: Ctx = Depends(require("finance:read"))):
    return cached(ctx, request, lambda: S.net_flows(ctx.adapters, months, _filters(asset_class, vehicle, None), group_by))


@router.get("/executive/product-profitability")
def product_profitability(request: Request, months: int = Query(12, ge=1, le=24), ctx: Ctx = Depends(require("finance:read"))):
    return cached(ctx, request, lambda: S.product_profitability(ctx.adapters, months))


@router.get("/executive/margin-trend")
def margin_trend(request: Request, months: int = Query(24, ge=1, le=24), ctx: Ctx = Depends(require("finance:read"))):
    return cached(ctx, request, lambda: S.margin_trend(ctx.adapters, months))


@router.get("/executive/revenue-attribution")
def revenue_attribution(request: Request, months: int = Query(12, ge=1, le=12), ctx: Ctx = Depends(require("finance:read"))):
    return cached(ctx, request, lambda: S.revenue_attribution(ctx.adapters, months))


@router.get("/executive/risk-heatmap")
def risk_heatmap(request: Request, ctx: Ctx = Depends(require("risk:read_aggregate"))):
    return cached(ctx, request, lambda: S.risk_heatmap(ctx.adapters))


@router.get("/executive/geographic-exposure")
def geographic(request: Request, scope: str = Query("enterprise", pattern="^(enterprise|products|portfolios)$"),
               ctx: Ctx = Depends(require("investment:read_aggregate"))):
    return cached(ctx, request, lambda: S.geographic_exposure(ctx.adapters, scope))


@router.get("/executive/actual-vs-budget")
def actual_vs_budget(request: Request, months: int = Query(12, ge=1, le=24), ctx: Ctx = Depends(require("finance:read"))):
    return cached(ctx, request, lambda: S.actual_vs_budget(ctx.adapters, months))


@router.get("/executive/initiatives")
def initiatives(request: Request, ctx: Ctx = Depends(require("decisions:read"))):
    return cached(ctx, request, lambda: S.initiative_scorecard(ctx.adapters))


@router.get("/executive/retention")
def retention(request: Request, ctx: Ctx = Depends(require("exec:read"))):
    return cached(ctx, request, lambda: S.retention_trend(ctx.adapters))


# ------------------------------------------------------------------ decision memory
@router.get("/decisions")
def decisions(ctx: Ctx = Depends(require("decisions:read"))):
    as_of = ctx.adapters.market.months()[-1]
    return {"decisions": dec.decisions_view(ctx.adapters, as_of), "summary": dec.summary(ctx.adapters, as_of), "as_of": as_of.isoformat()}


class DecisionIn(BaseModel):
    title: str = Field(min_length=5, max_length=200)
    rationale: str = Field(min_length=5, max_length=4000)
    target_kpi: str = Field(max_length=60)
    baseline_value: float
    target_value: float
    deadline: date
    expected_impact: str = Field(max_length=2000)
    assumptions: list[str] = []
    evidence: list[str] = []
    initiative_id: str | None = None


@router.post("/decisions")
def record_decision(body: DecisionIn, ctx: Ctx = Depends(require("decisions:write"))):
    n = ctx.db.scalar(select(m.Decision.id).order_by(m.Decision.id.desc()).limit(1))
    did = f"D-{int(n.split('-')[1]) + 1:04d}" if n else "D-0001"
    d = m.Decision(id=did, tenant_id=ctx.principal.tenant_id, title=body.title, owner=ctx.principal.title or ctx.principal.user_id,
                   decision_date=date.today(), rationale=body.rationale, evidence=body.evidence, assumptions=body.assumptions,
                   expected_impact=body.expected_impact, target_kpi=body.target_kpi, baseline_value=body.baseline_value,
                   target_value=body.target_value, observed_value=None, deadline=body.deadline, approval_status="proposed",
                   approver="Executive Committee", follow_ups=[], outcome_status="pending", initiative_id=body.initiative_id)
    ctx.db.add(d)
    ctx.db.flush()
    from integrations.mock.store import invalidate
    invalidate()
    audit.record(tenant_id=ctx.principal.tenant_id, actor=ctx.principal.user_id, action="decisions:write", resource_type="decision",
                 resource_id=did, decision="allow", details={"title": body.title})
    return {"id": did, "status": "recorded"}


class OutcomeIn(BaseModel):
    observed_value: float


@router.patch("/decisions/{decision_id}/outcome")
def record_outcome(decision_id: str, body: OutcomeIn, ctx: Ctx = Depends(require("decisions:write"))):
    d = ctx.db.get(m.Decision, decision_id)
    if d is None or d.tenant_id != ctx.principal.tenant_id:
        raise HTTPException(404, "decision not found")
    d.observed_value = body.observed_value
    d.outcome_status = dec.classify({"observed_value": body.observed_value, "baseline_value": d.baseline_value, "target_value": d.target_value})
    from integrations.mock.store import invalidate
    invalidate()
    audit.record(tenant_id=ctx.principal.tenant_id, actor=ctx.principal.user_id, action="decisions:outcome", resource_type="decision",
                 resource_id=decision_id, decision="allow", details={"observed": body.observed_value})
    return {"id": decision_id, "outcome_status": d.outcome_status}


# ------------------------------------------------------------------ exports (aggregates only; client-level exports use approvals)
EXPORTS = {
    "kpis": ("exec:read", lambda a, n: [S.executive_kpis(a, n)["data"]]),
    "aum-trend": ("finance:read", lambda a, n: [{"month": mth, **{s["name"]: s["values"][i] for s in d["series"]}, "total": d["total"][i]}
                                                for d in [S.aum_trend(a, 24)["data"]] for i, mth in enumerate(d["months"])]),
    "net-flows": ("finance:read", lambda a, n: [{"month": mth, "group": s["name"], "subscriptions": s["subscriptions"][i], "redemptions": s["redemptions"][i],
                                                 "net": s["net"][i]} for d in [S.net_flows(a, 24)["data"]] for s in d["series"] for i, mth in enumerate(d["months"])]),
    "actual-vs-budget": ("finance:read", lambda a, n: S.actual_vs_budget(a, n)["data"]["lines"]),
    "funds": ("product_research:read", lambda a, n: S.fund_list(a)["data"]["funds"]),
    "portfolios": ("investment:read", lambda a, n: [{k: v for k, v in p.items() if k not in ("client_id", "name")} for p in S.portfolio_list(a)["data"]["portfolios"]]),
    "initiatives": ("decisions:read", lambda a, n: S.initiative_scorecard(a)["data"]["initiatives"]),
    "product-profitability": ("finance:read", lambda a, n: [c for g in S.product_profitability(a, n)["data"]["tree"] for c in g["children"]]),
}


@router.get("/exports/{dataset}.csv")
def export_csv(dataset: str, months: int = Query(12, ge=1, le=24), ctx: Ctx = Depends(current)):
    if dataset not in EXPORTS:
        raise HTTPException(404, "unknown dataset")
    perm, fn = EXPORTS[dataset]
    authorize(ctx, perm)
    authorize(ctx, "export:standard", audit_allow=True)
    rows = fn(ctx.adapters, months)
    buf = io.StringIO()
    buf.write(f"# SYNTHETIC DATA - FLO demonstration export - {dataset} - generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} by {ctx.principal.user_id}\n")
    flat = [{k: v for k, v in r.items() if not isinstance(v, (dict, list))} for r in rows]
    if flat:
        w = csv.DictWriter(buf, fieldnames=list(flat[0].keys()))
        w.writeheader()
        w.writerows(flat)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="flo-{dataset}.csv"'})


@router.get("/exports/board-report.html", response_class=HTMLResponse)
def board_report(months: int = Query(12, ge=1, le=24), ctx: Ctx = Depends(require("board:prepare"))):
    a = ctx.adapters
    k = S.executive_kpis(a, months)["data"]
    b = S.actual_vs_budget(a, months)["data"]["lines"]
    ini = S.initiative_scorecard(a)["data"]["initiatives"]
    ra = S.revenue_attribution(a, min(months, 12))["data"]
    risks = S.risk_heatmap(a)["data"]["items"][:5]
    pct = lambda x: f"{x * 100:.2f}%"  # noqa: E731
    cad = lambda x: f"CAD {float(x) / 1e6:,.1f}m"  # noqa: E731
    rows = "".join(f"<tr><td>{escape(x['line'])}</td><td>{cad(x['actual'])}</td><td>{cad(x['budget'])}</td><td>{cad(x['variance'])}</td></tr>" for x in b)
    irows = "".join(f"<tr><td>{escape(i['name'])}</td><td>{i['progress_pct']}%</td><td>{i['planned_progress_pct']}%</td><td>{i['status']}</td></tr>" for i in ini)
    rrows = "".join(f"<li>{escape(r['title'])} (score {r['score']})</li>" for r in risks)
    audit.record(tenant_id=ctx.principal.tenant_id, actor=ctx.principal.user_id, action="board:prepare", resource_type="board_report",
                 resource_id=f"BR-{k['period']['end']}", decision="allow")
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>FLO Board Report (SYNTHETIC)</title>
<style>body{{font-family:system-ui;margin:32px;color:#111}}table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:4px 8px}}
.banner{{background:#fde68a;padding:8px;font-weight:600}}</style></head><body>
<div class="banner">SYNTHETIC DATA - independent architecture demonstration - draft, not approved for distribution</div>
<h1>FLO Board Performance Report</h1><p>Period {k['period']['start']} to {k['period']['end']} ({k['period']['months']} months, CAD)</p>
<h2>Highlights</h2><ul><li>Total AUM {cad(k['total_aum'])}, growth {pct(k['aum_growth'])}; net flows {cad(k['net_flows'])}</li>
<li>Management fee revenue {cad(k['management_fee_revenue'])}; operating margin {pct(k['operating_margin'])} (prior {pct(k['prior_period']['operating_margin']) if k['prior_period'] else 'n/a'})</li>
<li>Revenue change attribution: volume {cad(ra['volume_effect'])}, mix {cad(ra['mix_effect'])}, fee changes {cad(ra['fee_change_effect'])}</li></ul>
<h2>Actual vs budget</h2><table><tr><th>Line</th><th>Actual</th><th>Budget</th><th>Variance</th></tr>{rows}</table>
<h2>Strategic initiatives</h2><table><tr><th>Initiative</th><th>Progress</th><th>Planned</th><th>Status</th></tr>{irows}</table>
<h2>Top enterprise risks</h2><ul>{rrows}</ul>
<p><small>Metric definitions: FLO semantic layer v{S.SEMANTIC_LAYER_VERSION}. Distribution requires executive approval (board:distribute).</small></p></body></html>"""


@router.get("/exports/files/{name}")
def export_file(name: str, ctx: Ctx = Depends(current)):
    """Files produced by an executed export:sensitive approval; only the requester may download."""
    apr = ctx.db.get(m.Approval, name.replace(".csv", ""))
    if apr is None or apr.tenant_id != ctx.principal.tenant_id or apr.requested_by != ctx.principal.user_id or apr.status != "executed":
        raise HTTPException(404, "not found")
    path = get_settings().export_dir + "/" + f"{apr.id}.csv"
    audit.record(tenant_id=ctx.principal.tenant_id, actor=ctx.principal.user_id, action="export.download", resource_type="export",
                 resource_id=apr.id, decision="allow")
    return FileResponse(path, media_type="text/csv", filename=f"flo-export-{apr.id}.csv")


# ------------------------------------------------------------------ async jobs (long-running analytics)
class JobIn(BaseModel):
    kind: str = Field(pattern="^(scenario_compare|scenario_sensitivity|data_quality|portfolio_metrics)$")
    params: dict = {}


JOB_PERMS = {"scenario_compare": "scenarios:run", "scenario_sensitivity": "scenarios:run", "data_quality": "aiops:read",
             "portfolio_metrics": "investment:read"}


@router.post("/jobs", status_code=202)
def submit_job(body: JobIn, ctx: Ctx = Depends(current)):
    authorize(ctx, JOB_PERMS[body.kind])
    pending = ctx.db.query(m.Job).filter(m.Job.status.in_(["queued", "running"])).count()
    if pending > 200:
        raise HTTPException(503, {"code": "BACKPRESSURE", "message": "job queue is full; retry later"}, headers={"Retry-After": "30"})
    j = m.Job(id=f"JOB-{uuid.uuid4().hex[:12]}", tenant_id=ctx.principal.tenant_id, requested_by=ctx.principal.user_id, kind=body.kind,
              params=body.params, status="queued", created_at=datetime.now(timezone.utc).replace(tzinfo=None))
    ctx.db.add(j)
    return {"id": j.id, "status": "queued"}


@router.get("/jobs/{job_id}")
def get_job(job_id: str, ctx: Ctx = Depends(current)):
    j = ctx.db.get(m.Job, job_id)
    if j is None or j.tenant_id != ctx.principal.tenant_id or j.requested_by != ctx.principal.user_id:
        raise HTTPException(404, "not found")
    return {"id": j.id, "kind": j.kind, "status": j.status, "result": j.result, "error": j.error, "created_at": j.created_at.isoformat(),
            "finished_at": j.finished_at.isoformat() if j.finished_at else None}
