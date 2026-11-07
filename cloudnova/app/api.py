"""HTTP API + static UI (specs/query_interface.md §1)."""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import db
from .agent import memory, supervisor
from .config import ROOT, get_settings
from .errors import AppError
from .pipeline.build import build

log = logging.getLogger("cloudnova.api")
STATIC = Path(__file__).parent / "web" / "static"

@asynccontextmanager
async def _lifespan(_: FastAPI):
    build(quiet=True)  # idempotent: rebuilds only if the raw CSV hash or FX rule changed
    yield


app = FastAPI(title="CloudNova Revenue Intelligence Copilot", version="1.0", lifespan=_lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    session_id: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_\-]+$")


@app.exception_handler(AppError)
async def _app_error(_: Request, exc: AppError):
    return JSONResponse(exc.to_dict(), status_code=exc.status)


@app.exception_handler(Exception)
async def _unexpected(_: Request, exc: Exception):
    log.exception("unhandled error")
    return JSONResponse({"schema_version": "1.0", "code": "internal_error", "message": "Something went wrong.",
                         "details": {}, "retryable": False}, status_code=500)


v1 = APIRouter(tags=["v1"])


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@v1.get("/health")
def health():
    """Liveness + readiness: data loaded, local Qwen reachable (analytics work without it)."""
    return supervisor.health()


@v1.post("/ask")
def ask(req: AskRequest):
    """Natural-language question → routed query agent → answer + executed SQL + caveats + trace."""
    return supervisor.ask(req.question, req.session_id)


@v1.get("/reconciliation")
def reconcile():
    """Raw → clean row accounting and its financial impact (naive vs deduplicated revenue, conflict swing)."""
    from .reconciliation import reconciliation
    return reconciliation()


@v1.get("/metrics")
def metrics_catalog():
    """The approved metric catalog (definitions + SQL) the semantic planner compiles from."""
    from .semantic.catalog import DIMENSIONS, METRICS
    return {"metrics": [{"id": m.id, "label": m.label, "grain": m.grain, "unit": m.unit, "definition": m.definition, "sql": m.sql}
                        for m in METRICS.values()],
            "dimensions": [{"id": d.id, "label": d.label, "invoice_grain": d.invoice_sql is not None,
                            "account_grain": d.account_sql is not None} for d in DIMENSIONS.values()]}


@v1.get("/sources")
def sources():
    """Configured source adapters and their provenance (see docs/INTEGRATION_ARCHITECTURE.md)."""
    from .sources import get_source
    src = get_source(get_settings())
    m = json.loads((get_settings().data_dir / "manifest.json").read_text())
    return {"active": [{"adapter": src.name, "system_type": src.system_type, "file": m["raw_csv"], "sha256": m["raw_sha256"],
                        "rows": m["raw_rows"]}]}


# ---------------------------------------------------------------- enhancements (branch: enhancements)
class StatusUpdate(BaseModel):
    status: str = Field(pattern=r"^(open|investigating|resolved|dismissed)$")
    note: str = Field(default="", max_length=500)


@v1.get("/leakage/findings", tags=["enhancements"])
def leakage_findings():
    """Revenue Leakage Investigator: deterministic checks with evidence, $ at stake and investigation status."""
    from .enhancements.leakage import run_checks, summary
    fs = run_checks()
    return {"findings": fs, "summary": summary(fs)}


@v1.patch("/leakage/findings/{finding_id}", tags=["enhancements"])
def leakage_update(finding_id: str, body: StatusUpdate):
    """Update a finding's investigation status (stored in the runtime DB — the ledger is never modified)."""
    from .enhancements.leakage import set_status
    return set_status(finding_id, body.status, body.note)


@v1.post("/simulator/scenarios", tags=["enhancements"])
def simulate(scenario: dict):
    """What-if simulator: hypothetical scenario vs observed baseline. Read-only."""
    from pydantic import ValidationError

    from .enhancements.simulator import Scenario
    from .enhancements.simulator import simulate as run
    try:
        sc = Scenario.model_validate(scenario)
    except ValidationError as exc:
        raise AppError("invalid_scenario", "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()[:5]), 422) from exc
    return run(sc)


class LegacyPreview(BaseModel):
    text: str | None = Field(default=None, description="pipe-delimited legacy export; omit to use the bundled simulated sample")


@v1.post("/integrations/legacy-billing/preview", tags=["enhancements"])
def legacy_preview(req: LegacyPreview):
    """Map a (simulated) legacy billing export to the raw contract, validate, attach lineage, and preview it through
    the ledger's cleaning rules. Read-only: nothing is written to the analytics database."""
    from .sources.legacy_billing import LegacyBillingAdapter, preview
    return preview(LegacyBillingAdapter.sample() if req.text is None else LegacyBillingAdapter(req.text, "uploaded.psv"))


# ---------------------------------------------------------------- financial policy decisions (approval-gated)
class PolicyApproval(BaseModel):
    key: str = Field(max_length=40)
    option: str = Field(max_length=40)
    approver: str = Field(min_length=2, max_length=80)
    role: str = Field(max_length=40)
    rationale: str = Field(min_length=20, max_length=2000)
    impact_hash: str = Field(max_length=32)
    pin: str = Field(max_length=64)


@v1.get("/policy", tags=["decisions"])
def policy_overview():
    """Active vs original policy, open decisions with live impact reports, and the decision log."""
    from .policy import overview
    return overview()


@v1.post("/policy/decisions", tags=["decisions"])
def policy_approve(body: PolicyApproval):
    """Record a finance-owner decision. Does NOT change anything until applied."""
    from .policy import approve
    return approve(body.key, body.option, body.approver, body.role, body.rationale, body.impact_hash, body.pin)


@v1.post("/policy/decisions/{decision_id}/apply", tags=["decisions"])
def policy_apply(decision_id: int):
    """Apply an approved decision: write a new policy version and rebuild from the raw CSV."""
    from .policy import apply
    return apply(decision_id)


@v1.get("/journey", tags=["journey"])
def journey():
    """Nova's Guided Journey: seven scenes whose narration is generated from the live engine and eval artifacts."""
    from .journey import scenes
    return scenes()


@v1.get("/sessions/{session_id}")
def session(session_id: str):
    return {"session_id": session_id, "turns": memory.history(session_id, 50)}


@v1.delete("/sessions/{session_id}")
def clear_session(session_id: str):
    return {"session_id": session_id, "deleted_turns": memory.clear(session_id)}


def _q(sql: str) -> dict:
    r = db.run_query(sql, max_rows=500)
    return {"columns": r["columns"], "rows": r["rows"], "sql": r["sql"]}


@v1.get("/kpis")
def kpis():
    inv = db.run_query("""SELECT SUM(amount_usd) FILTER (WHERE status='paid'), SUM(amount_usd) FILTER (WHERE status IN ('paid','refunded')),
        SUM(amount_usd) FILTER (WHERE status='refunded'), SUM(amount_usd) FILTER (WHERE status IN ('pending','failed')),
        COUNT(*) FILTER (WHERE status IN ('pending','failed')), COUNT(*) FROM invoices""")["rows"][0]
    acc = db.run_query("""SELECT SUM(current_mrr_usd) FILTER (WHERE is_active), COUNT(*) FILTER (WHERE is_active), COUNT(*),
        AVG(CASE WHEN churned THEN 1.0 ELSE 0.0 END) FILTER (WHERE churned IS NOT NULL), AVG(csat_score) FROM accounts""")["rows"][0]
    manifest = json.loads((get_settings().data_dir / "manifest.json").read_text())
    defs = {"paid_revenue": "status = paid, USD", "net_revenue": "paid + refunded (negative)", "refunds": "status = refunded",
            "exposure": "status in pending/failed", "mrr": "Σ list×seats×(1−disc) over active accounts (latest invoice)",
            "churn_rate": "share of accounts whose latest snapshot is churned"}
    return {"paid_revenue": inv[0], "net_revenue": inv[1], "refunds": inv[2], "exposure": inv[3], "exposure_count": inv[4],
            "invoices": inv[5], "mrr": acc[0], "active_accounts": acc[1], "accounts": acc[2], "churn_rate": acc[3],
            "avg_csat": acc[4], "definitions": defs, "manifest": manifest}


@v1.get("/dashboard")
def dashboard():
    return {
        "monthly": _q("SELECT invoice_month, paid_revenue_usd, refunds_usd, net_revenue_usd, exposure_usd FROM monthly_revenue "
                      "WHERE invoice_month <= strftime(current_date, '%Y-%m') ORDER BY invoice_month"),
        "by_region": _q("SELECT region, SUM(amount_usd) FILTER (WHERE status IN ('paid','refunded')) AS net_revenue FROM invoices "
                        "GROUP BY region ORDER BY net_revenue DESC"),
        "by_plan": _q("SELECT plan, SUM(amount_usd) FILTER (WHERE status IN ('paid','refunded')) AS net_revenue, "
                      "COUNT(DISTINCT account_id) AS accounts FROM invoices GROUP BY plan ORDER BY net_revenue DESC"),
        "status_mix": _q("SELECT status, COUNT(*) AS invoices, SUM(amount_usd) AS amount_usd FROM invoices GROUP BY status ORDER BY invoices DESC"),
        "mrr_by_region": _q("SELECT region, AVG(current_mrr_usd) FILTER (WHERE is_active) AS avg_mrr FROM accounts GROUP BY region ORDER BY avg_mrr DESC"),
        "churn_by_plan": _q("SELECT plan, AVG(CASE WHEN churned THEN 1.0 ELSE 0.0 END) FILTER (WHERE churned IS NOT NULL) AS churn_rate, "
                            "COUNT(*) AS accounts FROM accounts GROUP BY plan ORDER BY churn_rate DESC"),
        "top_accounts": _q("SELECT account_id, account_name, region, plan, net_revenue_usd, csat_score, "
                           "COALESCE(csat_score <= 2, FALSE) AS low_csat FROM accounts ORDER BY net_revenue_usd DESC, account_id LIMIT 10"),
        "csat_dist": _q("SELECT COALESCE(CAST(csat_score AS VARCHAR), 'blank') AS csat, COUNT(*) AS accounts, "
                        "AVG(CASE WHEN churned THEN 1.0 ELSE 0.0 END) AS churn_rate FROM accounts GROUP BY 1 ORDER BY 1"),
        "discount": _q("SELECT CAST(discount_pct AS INTEGER) AS discount_pct, COUNT(*) AS paid_invoices, SUM(amount_usd) AS paid_revenue "
                       "FROM invoices WHERE status = 'paid' GROUP BY 1 ORDER BY 1"),
    }


@v1.get("/data-quality")
def data_quality():
    manifest = json.loads((get_settings().data_dir / "manifest.json").read_text())
    return {"manifest": manifest,
            "issues": _q("SELECT issue_code, \"column\", n_rows, example, action FROM dq_issues ORDER BY n_rows DESC"),
            "conflicts": _q("SELECT invoice_id, raw_statuses, winner_status, usd_at_stake FROM dedup_conflicts ORDER BY usd_at_stake DESC"),
            "fx": _q("SELECT currency, COUNT(*) AS paid_invoices, SUM(amount_local) AS amount_local, SUM(amount_usd) AS usd_documented, "
                     "SUM(amount_usd_alt) AS usd_inverse FROM invoices WHERE status='paid' GROUP BY currency ORDER BY currency")}


@v1.get("/traces")
def traces(limit: int = 50):
    from .llm.provider import provider_status
    runs = memory.recent_runs(min(max(limit, 1), 200))
    evals_path = ROOT / "evals" / "results" / "latest.json"
    evals = json.loads(evals_path.read_text()) if evals_path.exists() else None
    ok = [r for r in runs if r["status"] == "ok"]
    return {"llm": provider_status(), "runs": runs, "evals": evals,
            "summary": {"requests": len(runs), "ok": len(ok), "failed": len(runs) - len(ok),
                        "avg_total_ms": round(sum(r["total_ms"] for r in runs) / len(runs), 1) if runs else None,
                        "llm_requests": sum(1 for r in runs if r["llm_ms"]),
                        "by_planner": {p: sum(1 for r in runs if r["planner"] == p) for p in ("semantic", "llm_sql", "none")}}}


# v1 is the contract; unversioned paths are kept as aliases (hidden from the schema) for the CLI docs and early clients.
app.include_router(v1, prefix="/api/v1")
app.include_router(v1, prefix="/api", include_in_schema=False)
app.add_api_route("/ask", ask, methods=["POST"], include_in_schema=False)
app.add_api_route("/health", health, methods=["GET"], include_in_schema=False)
