"""Deterministic financial calculation engine. All arithmetic is Decimal; no model output ever enters a figure.

Definitions (also returned to the UI through DEFINITIONS so every figure is explained where it is shown):

  Bank operating profit        = Bank revenue - Bank operating expenditure
  AI-assisted workflow cost    = model + compute + infrastructure + tooling + human review + rework   (per task)
  Human-equivalent value       = baseline hours x loaded hourly rate                                    (verified tasks only)
  Estimated cost avoidance     = Human-equivalent value - AI-assisted workflow cost                    (verified tasks only)
  Unrecovered AI cost          = workflow cost of failed / unverified tasks + platform overhead
  Net AI economic benefit      = Realized AI-attributed incremental profit
                                 + Estimated cost avoidance (verified)
                                 - Unrecovered AI cost
                                 - Allocated implementation cost
       ( == incremental profit + human-equivalent value of verified work - total Sherin AI cost )
  AI ROI                       = Net AI economic benefit / Total Sherin AI cost in the period x 100

Double counting is avoided because workflow-level AI costs are netted once inside cost avoidance and only the
costs NOT already netted (failed work, overhead, implementation) are subtracted afterwards. Attributed revenue is
a carve-out of fee income, not additional revenue. Portfolio AUM, unrealised returns and labour capacity are never
classified as bank revenue.
"""
from __future__ import annotations

import calendar
import datetime as dt
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app import catalog as C
from app import models as M

CENT = Decimal("0.01")
ZERO = Decimal("0")


def q(x) -> Decimal:
    if x is None:
        return ZERO
    return Decimal(str(x)).quantize(CENT, rounding=ROUND_HALF_UP)


def D(x) -> Decimal:
    return ZERO if x is None else Decimal(str(x))


DEFINITIONS = {
    "bank_revenue": "Sum of ledger revenue lines (net interest income, fees and commissions, trading, wealth fees, other). Excludes AUM and unrealised portfolio returns.",
    "bank_opex": "Sum of ledger operating expenditure lines, including the Sherin AI cash cost line.",
    "operating_profit": "Bank revenue - bank operating expenditure.",
    "ai_cost": "Total Sherin AI economic cost: model inference, compute, Azure infrastructure, storage, networking, monitoring, third-party tools, human review and rework, maintenance, and allocated implementation (capex / 36 months).",
    "ai_revenue": "Fee income attributed to AI-assisted workflows (a carve-out of fees and commissions, not additional revenue). Attribution method stated on each record.",
    "cost_avoidance": "For tasks that passed independent verification: human-only baseline cost - AI-assisted workflow cost (incl. human review and rework). An estimate of labour capacity released, not cash and not revenue.",
    "roi": "Net AI economic benefit / total Sherin AI cost in the same period x 100. Net benefit = realized incremental profit + verified cost avoidance - unrecovered AI cost (failed work, platform overhead) - allocated implementation.",
    "verified_work": "Agent tasks that succeeded, passed quality checks and were confirmed by the Independent Verification Agent.",
    "realized_savings": "Cash savings actually booked against budgets. A subset of cost avoidance, shown for context and never added to net benefit.",
}


# ---------------------------------------------------------------------------------------------- periods
@dataclass(frozen=True)
class Period:
    start: dt.date
    end: dt.date  # inclusive
    kind: str
    label: str

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def as_dict(self) -> dict:
        return {"start": self.start.isoformat(), "end": self.end.isoformat(), "kind": self.kind, "label": self.label}


def _month_bounds(y: int, m: int) -> tuple[dt.date, dt.date]:
    return dt.date(y, m, 1), dt.date(y, m, calendar.monthrange(y, m)[1])


def resolve_period(kind: str = "month", value: str | None = None, start: str | None = None, end: str | None = None,
                   default_month: str = "2026-10") -> Period:
    if kind == "custom":
        s, e = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
        if e < s:
            raise ValueError("end must be on or after start")
        return Period(s, e, "custom", f"{s.isoformat()} to {e.isoformat()}")
    value = value or default_month
    if kind == "month":
        y, m = map(int, value.split("-")[:2])
        s, e = _month_bounds(y, m)
        return Period(s, e, "month", s.strftime("%b %Y"))
    if kind == "quarter":  # value: YYYY-Qn or YYYY-MM (quarter containing month)
        if "Q" in value:
            y, qn = int(value[:4]), int(value[-1])
        else:
            y, mm = map(int, value.split("-")[:2])
            qn = (mm - 1) // 3 + 1
        s, _ = _month_bounds(y, 3 * qn - 2)
        _, e = _month_bounds(y, 3 * qn)
        return Period(s, e, "quarter", f"Q{qn} {y}")
    if kind == "year":
        y = int(value[:4])
        return Period(dt.date(y, 1, 1), dt.date(y, 12, 31), "year", str(y))
    if kind == "ttm":  # trailing twelve months ending in value's month
        y, m = map(int, value.split("-")[:2])
        _, e = _month_bounds(y, m)
        sy, sm = (y - 1, m + 1) if m < 12 else (y, 1)
        s, _ = _month_bounds(sy, sm)
        return Period(s, e, "ttm", f"12 months to {e.strftime('%b %Y')}")
    raise ValueError(f"unknown period kind {kind}")


def prior_period(p: Period) -> Period:
    if p.kind == "month":
        y, m = p.start.year, p.start.month - 1
        if m == 0:
            y, m = y - 1, 12
        s, e = _month_bounds(y, m)
        return Period(s, e, "month", s.strftime("%b %Y"))
    if p.kind == "quarter":
        y, m = p.start.year, p.start.month - 3
        if m <= 0:
            y, m = y - 1, m + 12
        return resolve_period("quarter", f"{y}-{m:02d}")
    if p.kind == "year":
        return resolve_period("year", str(p.start.year - 1))
    if p.kind == "ttm":
        y, m = p.end.year - 1, p.end.month
        return resolve_period("ttm", f"{y}-{m:02d}")
    e = p.start - dt.timedelta(days=1)
    return Period(e - dt.timedelta(days=p.days - 1), e, "custom", "prior period")


# ---------------------------------------------------------------------------------------------- currency
@dataclass(frozen=True)
class Fx:
    currency: str
    rate: Decimal
    source: str
    as_of: str | None
    data_class: str

    def conv(self, usd) -> float:
        return float((D(usd) * self.rate).quantize(CENT, rounding=ROUND_HALF_UP))

    def as_dict(self) -> dict:
        return {"currency": self.currency, "base": "USD", "rate": float(self.rate), "source": self.source, "as_of": self.as_of,
                "data_class": self.data_class}


SUPPORTED_CURRENCIES = ("USD", "INR", "CAD")


def fx_for(db: Session, currency: str = "USD", at: dt.date | None = None) -> Fx:
    currency = (currency or "USD").upper()
    if currency not in SUPPORTED_CURRENCIES:
        raise ValueError(f"Unsupported currency {currency}; supported: {', '.join(SUPPORTED_CURRENCIES)}")
    if currency == "USD":
        return Fx("USD", Decimal(1), "Base currency", None, "n/a")
    stmt = select(M.FxRate).where(M.FxRate.base == "USD", M.FxRate.quote == currency)
    if at is not None:
        stmt = stmt.where(M.FxRate.as_of <= dt.datetime.combine(at, dt.time.max))
    row = db.scalars(stmt.order_by(M.FxRate.as_of.desc(), M.FxRate.id.desc()).limit(1)).first()
    if row is None:
        raise ValueError(f"No FX rate configured for USD/{currency}")
    return Fx(currency, D(row.rate), row.source, row.as_of.isoformat(), row.data_class)


# ---------------------------------------------------------------------------------------------- aggregates
def _between(col, p: Period):
    if _is_dt(col):
        return and_(col >= dt.datetime.combine(p.start, dt.time.min), col <= dt.datetime.combine(p.end, dt.time.max))
    return and_(col >= p.start, col <= p.end)


def _is_dt(col) -> bool:
    from sqlalchemy import DateTime
    return isinstance(col.type, DateTime)


def bank_totals(db: Session, p: Period, dc: str) -> dict:
    rows = db.execute(select(M.LedgerLine.kind, M.LedgerLine.category, func.sum(M.LedgerLine.amount_usd))
                      .where(_between(M.LedgerLine.date, p), M.LedgerLine.data_class == dc)
                      .group_by(M.LedgerLine.kind, M.LedgerLine.category)).all()
    rev = {c: q(a) for k, c, a in rows if k == "revenue"}
    opex = {c: q(a) for k, c, a in rows if k == "opex"}
    revenue, expenditure = sum(rev.values(), ZERO), sum(opex.values(), ZERO)
    return {"revenue": revenue, "opex": expenditure, "operating_profit": revenue - expenditure,
            "revenue_by_category": rev, "opex_by_category": opex, "ai_cash_opex": opex.get("technology_sherin_ai", ZERO)}


def ai_cost_totals(db: Session, p: Period, dc: str) -> dict:
    rows = db.execute(select(M.AiCostRecord.category, (M.AiCostRecord.task_id.is_not(None)).label("linked"), func.sum(M.AiCostRecord.amount_usd))
                      .where(_between(M.AiCostRecord.date, p), M.AiCostRecord.data_class == dc)
                      .group_by(M.AiCostRecord.category, "linked")).all()
    by_cat: dict[str, Decimal] = {k: ZERO for k in C.AI_COST_CATEGORIES}
    linked = overhead = impl = ZERO
    for cat, is_linked, amt in rows:
        a = q(amt)
        by_cat[cat] = by_cat.get(cat, ZERO) + a
        if cat == "implementation_allocated":
            impl += a
        elif is_linked:
            linked += a
        else:
            overhead += a
    total = sum(by_cat.values(), ZERO)
    return {"total": total, "by_category": by_cat, "workflow_linked": linked, "overhead": overhead, "implementation": impl,
            "cash": total - by_cat.get("human_review", ZERO)}


def _wf_cost_expr():
    t = M.AgentTask
    return t.cost_model + t.cost_compute + t.cost_infra + t.cost_tooling + t.cost_human_review + t.cost_rework


def task_aggregate(db: Session, p: Period, dc: str, group_by: tuple = ()) -> list[dict]:
    t = M.AgentTask
    wf = _wf_cost_expr()
    base = t.baseline_hours * t.baseline_rate_usd
    cols = [
        func.count().label("tasks"),
        func.sum(case((t.status == "succeeded", 1), else_=0)).label("succeeded"),
        func.sum(case((t.verified.is_(True), 1), else_=0)).label("verified"),
        func.sum(case((t.quality_pass.is_(True), 1), else_=0)).label("quality_pass"),
        func.sum(wf).label("wf_cost_all"),
        func.sum(case((t.verified.is_(True), wf), else_=0)).label("wf_cost_verified"),
        func.sum(case((t.verified.is_(True), base), else_=0)).label("value_verified"),
        func.sum(case((t.verified.is_(True), t.baseline_hours), else_=0)).label("baseline_hours_verified"),
        func.sum(t.cost_model).label("model"), func.sum(t.cost_compute).label("compute"), func.sum(t.cost_infra).label("infra"),
        func.sum(t.cost_tooling).label("tooling"), func.sum(t.cost_human_review).label("review"), func.sum(t.cost_rework).label("rework"),
        func.sum(t.duration_s).label("duration_s"), func.sum(t.human_review_min).label("review_min"), func.sum(t.rework_min).label("rework_min"),
        func.sum(case((t.verified.is_(True), t.human_review_min + t.rework_min), else_=0)).label("human_min_verified"),
        func.sum(t.retries).label("retries"), func.sum(t.tool_calls).label("tool_calls"),
    ]
    stmt = select(*group_by, *cols).where(_between(t.created_at, p), t.data_class == dc)
    if group_by:
        stmt = stmt.group_by(*group_by)
    out = []
    for r in db.execute(stmt).mappings():
        d = dict(r)
        for k in ("wf_cost_all", "wf_cost_verified", "value_verified", "model", "compute", "infra", "tooling", "review", "rework"):
            d[k] = q(d[k])
        for k in ("baseline_hours_verified", "review_min", "rework_min", "human_min_verified"):
            d[k] = D(d[k])
        for k in ("tasks", "succeeded", "verified", "quality_pass", "duration_s", "retries", "tool_calls"):
            d[k] = int(d[k] or 0)
        d["wf_cost_unverified"] = d["wf_cost_all"] - d["wf_cost_verified"]
        d["cost_avoidance"] = d["value_verified"] - d["wf_cost_verified"]
        out.append(d)
    return out


def attribution_totals(db: Session, p: Period, dc: str) -> dict:
    # Attribution is recorded monthly; include months whose first day falls in the period.
    rows = db.execute(select(func.sum(M.RevenueAttribution.attributed_revenue_usd),
                             func.sum(case((M.RevenueAttribution.realized.is_(True), M.RevenueAttribution.incremental_profit_usd), else_=0)))
                      .where(M.RevenueAttribution.period.in_(_months_in(p)), M.RevenueAttribution.data_class == dc)).one()
    return {"attributed_revenue": q(rows[0]), "incremental_profit": q(rows[1])}


def realized_savings_total(db: Session, p: Period, dc: str) -> Decimal:
    v = db.scalar(select(func.sum(M.RealizedSaving.amount_usd)).where(M.RealizedSaving.period.in_(_months_in(p)), M.RealizedSaving.data_class == dc))
    return q(v)


def _months_in(p: Period) -> list[str]:
    out, d = [], dt.date(p.start.year, p.start.month, 1)
    while d <= p.end:
        out.append(d.strftime("%Y-%m"))
        d = dt.date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return out


def budget_for(db: Session, p: Period, scope: str, dc: str) -> Decimal | None:
    """Budgets are monthly; partial months are pro-rated by days."""
    months = _months_in(p)
    rows = db.execute(select(M.Budget.period, M.Budget.amount_usd).where(M.Budget.scope == scope, M.Budget.period.in_(months),
                                                                         M.Budget.data_class == dc)).all()
    if not rows:
        return None
    total = ZERO
    for per, amt in rows:
        y, m = map(int, per.split("-"))
        ms, me = _month_bounds(y, m)
        overlap = (min(me, p.end) - max(ms, p.start)).days + 1
        total += D(amt) * Decimal(overlap) / Decimal((me - ms).days + 1)
    return q(total)


def economics(db: Session, p: Period, dc: str) -> dict:
    """The single source of truth that every financial chart and chat answer reads from."""
    bank = bank_totals(db, p, dc)
    ai = ai_cost_totals(db, p, dc)
    tk = (task_aggregate(db, p, dc) or [None])[0] or {}
    attr = attribution_totals(db, p, dc)
    realized = realized_savings_total(db, p, dc)
    value_verified = tk.get("value_verified", ZERO)
    wf_verified = tk.get("wf_cost_verified", ZERO)
    wf_unverified = tk.get("wf_cost_unverified", ZERO)
    cost_avoidance = value_verified - wf_verified
    unrecovered = wf_unverified + ai["overhead"]
    net = attr["incremental_profit"] + cost_avoidance - unrecovered - ai["implementation"]
    roi = (net / ai["total"] * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP) if ai["total"] > 0 else None
    return {
        "period": p, "bank": bank, "ai": ai, "tasks": tk, "attribution": attr, "realized_savings": realized,
        "value_verified": value_verified, "wf_cost_verified": wf_verified, "wf_cost_unverified": wf_unverified,
        "cost_avoidance": cost_avoidance, "unrecovered": unrecovered, "net_benefit": net, "roi_pct": roi,
        "verified_tasks": tk.get("verified", 0), "total_tasks": tk.get("tasks", 0),
    }


# ---------------------------------------------------------------------------------------------- KPI cards
KPI_ORDER = ["bank_revenue", "bank_opex", "operating_profit", "ai_cost", "ai_revenue", "cost_avoidance", "roi", "verified_work"]
KPI_LABELS = {"bank_revenue": "Total Bank Revenue", "bank_opex": "Bank Operating Expenditure", "operating_profit": "Bank Operating Profit",
              "ai_cost": "Sherin AI Operating Cost", "ai_revenue": "Sherin AI Attributed Revenue", "cost_avoidance": "Estimated Automation Savings",
              "roi": "AI Return on Investment", "verified_work": "Total Verified Work Completed"}
KPI_BASIS = {"bank_revenue": "actual", "bank_opex": "actual", "operating_profit": "actual", "ai_cost": "actual", "ai_revenue": "estimated",
             "cost_avoidance": "estimated", "roi": "estimated", "verified_work": "actual"}
KPI_GOOD_DIRECTION = {"bank_opex": "down", "ai_cost": "down"}


def _kpi_values(e: dict) -> dict[str, Decimal | int | None]:
    return {"bank_revenue": e["bank"]["revenue"], "bank_opex": e["bank"]["opex"], "operating_profit": e["bank"]["operating_profit"],
            "ai_cost": e["ai"]["total"], "ai_revenue": e["attribution"]["attributed_revenue"], "cost_avoidance": e["cost_avoidance"],
            "roi": e["roi_pct"], "verified_work": e["verified_tasks"]}


def _pct_change(cur, prev) -> float | None:
    if cur is None or prev is None or D(prev) == 0:
        return None
    return float(((D(cur) - D(prev)) / abs(D(prev)) * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def kpis(db: Session, p: Period, fx: Fx, dc: str) -> dict:
    cur, prev = economics(db, p, dc), economics(db, prior_period(p), dc)
    cv, pv = _kpi_values(cur), _kpi_values(prev)
    budgets = {"bank_revenue": budget_for(db, p, "bank_revenue", dc), "bank_opex": budget_for(db, p, "bank_opex", dc),
               "ai_cost": budget_for(db, p, "ai_cost", dc)}
    cards = []
    for k in KPI_ORDER:
        is_money = k not in ("roi", "verified_work")
        v, pvv = cv[k], pv[k]
        card = {"key": k, "label": KPI_LABELS[k], "unit": "currency" if is_money else ("pct" if k == "roi" else "count"),
                "value": fx.conv(v) if is_money and v is not None else (float(v) if v is not None else None),
                "prior": fx.conv(pvv) if is_money and pvv is not None else (float(pvv) if pvv is not None else None),
                "mom_pct": _pct_change(v, pvv) if k != "roi" else None,
                "mom_pts": float(D(v) - D(pvv)) if k == "roi" and v is not None and pvv is not None else None,
                "good_direction": KPI_GOOD_DIRECTION.get(k, "up"), "basis": KPI_BASIS[k], "data_class": dc,
                "definition": DEFINITIONS.get(k, DEFINITIONS.get({"operating_profit": "operating_profit"}.get(k, k), "")),
                "budget": None, "budget_variance_pct": None, "budget_utilization_pct": None}
        if k in budgets and budgets[k] is not None and v is not None:
            card["budget"] = fx.conv(budgets[k])
            card["budget_variance_pct"] = _pct_change(v, budgets[k])
            card["budget_utilization_pct"] = float((D(v) / budgets[k] * 100).quantize(Decimal("0.1"))) if budgets[k] else None
        if k == "verified_work":
            card["sub"] = {"total_tasks": cur["total_tasks"], "human_hours_equivalent": float(cur["tasks"].get("baseline_hours_verified", 0))}
        if k == "roi":
            card["sub"] = {"numerator": fx.conv(cur["net_benefit"]), "denominator": fx.conv(cur["ai"]["total"]),
                           "denominator_label": "Total Sherin AI cost in period"}
        if k == "cost_avoidance":
            card["sub"] = {"realized_savings": fx.conv(cur["realized_savings"])}
        cards.append(card)
    return {"period": p.as_dict(), "prior_period": prior_period(p).as_dict(), "fx": fx.as_dict(), "data_class": dc, "cards": cards,
            "net_benefit": fx.conv(cur["net_benefit"]), "definitions": DEFINITIONS}


def kpi_drilldown(db: Session, key: str, p: Period, fx: Fx, dc: str) -> dict:
    if key not in KPI_ORDER:
        raise KeyError(key)
    e = economics(db, p, dc)
    rows: list[dict] = []
    if key == "bank_revenue":
        rows = [{"label": C.REVENUE_CATEGORIES.get(k, k), "value": fx.conv(v)} for k, v in e["bank"]["revenue_by_category"].items()]
    elif key == "bank_opex":
        rows = [{"label": C.OPEX_CATEGORIES.get(k, k), "value": fx.conv(v)} for k, v in e["bank"]["opex_by_category"].items()]
    elif key == "operating_profit":
        rows = [{"label": "Bank revenue", "value": fx.conv(e["bank"]["revenue"])}, {"label": "Bank operating expenditure", "value": -fx.conv(e["bank"]["opex"])},
                {"label": "Operating profit", "value": fx.conv(e["bank"]["operating_profit"])}]
    elif key == "ai_cost":
        rows = [{"label": C.AI_COST_CATEGORIES[k], "category": k, "value": fx.conv(v)} for k, v in e["ai"]["by_category"].items()]
    elif key == "ai_revenue":
        for r in db.scalars(select(M.RevenueAttribution).where(M.RevenueAttribution.period.in_(_months_in(p)), M.RevenueAttribution.data_class == dc)):
            rows.append({"label": f"{r.period} - {r.workflow}", "value": fx.conv(r.attributed_revenue_usd), "incremental_profit": fx.conv(r.incremental_profit_usd),
                         "method": r.method, "realized": r.realized})
    elif key in ("cost_avoidance", "verified_work"):
        for d in task_aggregate(db, p, dc, (M.AgentTask.department,)):
            rows.append({"label": C.DEPARTMENTS.get(d["department"], d["department"]), "value": fx.conv(d["cost_avoidance"]) if key == "cost_avoidance" else d["verified"],
                         "verified": d["verified"], "tasks": d["tasks"]})
    elif key == "roi":
        rows = [{"label": "Realized AI-attributed incremental profit", "value": fx.conv(e["attribution"]["incremental_profit"])},
                {"label": "Estimated cost avoidance (verified tasks)", "value": fx.conv(e["cost_avoidance"])},
                {"label": "Unrecovered AI cost (failed work + platform overhead)", "value": -fx.conv(e["unrecovered"])},
                {"label": "Allocated implementation cost", "value": -fx.conv(e["ai"]["implementation"])},
                {"label": "Net AI economic benefit", "value": fx.conv(e["net_benefit"])},
                {"label": "Denominator: total Sherin AI cost", "value": fx.conv(e["ai"]["total"])}]
    return {"key": key, "label": KPI_LABELS[key], "period": p.as_dict(), "fx": fx.as_dict(), "data_class": dc, "rows": rows,
            "definition": DEFINITIONS.get(key, "")}


# ---------------------------------------------------------------------------------------------- Graph A
def _bucket(d: dt.date, g: str) -> str:
    if g == "day":
        return d.isoformat()
    if g == "week":
        return (d - dt.timedelta(days=d.weekday())).isoformat()
    if g == "month":
        return d.strftime("%Y-%m")
    if g == "quarter":
        return f"{d.year}-Q{(d.month - 1) // 3 + 1}"
    if g == "year":
        return str(d.year)
    raise ValueError(f"unknown granularity {g}")


def revenue_vs_expenditure(db: Session, p: Period, granularity: str, fx: Fx, dc: str) -> dict:
    led = db.execute(select(M.LedgerLine.date, M.LedgerLine.kind, M.LedgerLine.category, func.sum(M.LedgerLine.amount_usd))
                     .where(_between(M.LedgerLine.date, p), M.LedgerLine.data_class == dc)
                     .group_by(M.LedgerLine.date, M.LedgerLine.kind, M.LedgerLine.category)).all()
    ai = db.execute(select(M.AiCostRecord.date, func.sum(M.AiCostRecord.amount_usd)).where(_between(M.AiCostRecord.date, p), M.AiCostRecord.data_class == dc)
                    .group_by(M.AiCostRecord.date)).all()
    b: dict[str, dict[str, Decimal]] = {}
    for d, kind, cat, amt in led:
        k = _bucket(d, granularity)
        row = b.setdefault(k, {"revenue": ZERO, "opex": ZERO, "ai_cash": ZERO, "ai_total": ZERO})
        row[kind] += D(amt)
        if cat == "technology_sherin_ai":
            row["ai_cash"] += D(amt)
    for d, amt in ai:
        b.setdefault(_bucket(d, granularity), {"revenue": ZERO, "opex": ZERO, "ai_cash": ZERO, "ai_total": ZERO})["ai_total"] += D(amt)
    keys = sorted(b)
    return {"granularity": granularity, "period": p.as_dict(), "fx": fx.as_dict(), "data_class": dc, "x": keys,
            "series": {"bank_revenue": [fx.conv(b[k]["revenue"]) for k in keys], "bank_opex": [fx.conv(b[k]["opex"]) for k in keys],
                       "ai_opex_cash": [fx.conv(b[k]["ai_cash"]) for k in keys], "ai_cost_total": [fx.conv(b[k]["ai_total"]) for k in keys],
                       "operating_profit": [fx.conv(b[k]["revenue"] - b[k]["opex"]) for k in keys]},
            "notes": ["Sherin AI cash expenditure is already included in bank operating expenditure (ledger line 'Technology - Sherin AI').",
                      "Sherin AI total cost additionally includes human review time, which is booked inside staff costs."]}


# ---------------------------------------------------------------------------------------------- Graph B
def contribution(db: Session, p: Period, fx: Fx, dc: str) -> dict:
    e = economics(db, p, dc)
    ai = e["ai"]
    waterfall = [
        {"label": "Realized incremental profit (AI-attributed)", "value": fx.conv(e["attribution"]["incremental_profit"]), "measure": "relative"},
        {"label": "Human-equivalent value of verified work", "value": fx.conv(e["value_verified"]), "measure": "relative"},
        {"label": "AI workflow cost - verified tasks", "value": -fx.conv(e["wf_cost_verified"]), "measure": "relative"},
        {"label": "AI workflow cost - failed / unverified", "value": -fx.conv(e["wf_cost_unverified"]), "measure": "relative"},
        {"label": "Platform overhead", "value": -fx.conv(ai["overhead"]), "measure": "relative"},
        {"label": "Allocated implementation", "value": -fx.conv(ai["implementation"]), "measure": "relative"},
        {"label": "Net AI economic benefit", "value": fx.conv(e["net_benefit"]), "measure": "total"},
    ]
    # Monthly series for the stacked view.
    months = []
    for m in _months_in(e["period"]):
        mp = resolve_period("month", m)
        me = economics(db, mp, dc)
        months.append({"month": m, "attributed_revenue": fx.conv(me["attribution"]["attributed_revenue"]),
                       "cost_avoidance": fx.conv(me["cost_avoidance"]), "realized_savings": fx.conv(me["realized_savings"]),
                       "ai_opex": fx.conv(me["ai"]["total"] - me["ai"]["implementation"]), "implementation": fx.conv(me["ai"]["implementation"]),
                       "net_benefit": fx.conv(me["net_benefit"])})
    return {"period": p.as_dict(), "fx": fx.as_dict(), "data_class": dc, "waterfall": waterfall, "monthly": months,
            "summary": {"attributed_revenue": fx.conv(e["attribution"]["attributed_revenue"]), "incremental_profit": fx.conv(e["attribution"]["incremental_profit"]),
                        "cost_avoidance": fx.conv(e["cost_avoidance"]), "realized_savings": fx.conv(e["realized_savings"]),
                        "ai_opex": fx.conv(ai["total"] - ai["implementation"]), "implementation": fx.conv(ai["implementation"]),
                        "net_benefit": fx.conv(e["net_benefit"]), "roi_pct": float(e["roi_pct"]) if e["roi_pct"] is not None else None},
            "notes": ["Cost avoidance is an estimate of labour capacity released; it is not revenue and not booked cash.",
                      "Realized savings are a subset of cost avoidance and are not added again.",
                      "Attributed revenue is part of fee income already in bank revenue; only its incremental profit enters net benefit."]}


# ---------------------------------------------------------------------------------------------- Graph C
def human_vs_ai(db: Session, p: Period, fx: Fx, dc: str) -> dict:
    baselines = {b.workflow_type: b for b in db.scalars(select(M.HumanBaseline))}
    rows = []
    for d in task_aggregate(db, p, dc, (M.AgentTask.workflow_type,)):
        wf = d["workflow_type"]
        if wf not in C.HUMAN_VS_AI_WORKFLOWS:
            continue
        v = d["verified"]
        b = baselines[wf]
        human_per = q(D(b.hours_per_task) * D(b.hourly_rate_usd))
        # AI cost per *verified* task carries the cost of failed attempts too.
        per = (lambda x: q(x / v) if v else ZERO)
        rows.append({"workflow_type": wf, "label": b.label, "verified_tasks": v, "tasks": d["tasks"],
                     "human_only_per_task": fx.conv(human_per), "human_only_total": fx.conv(human_per * v),
                     "ai_per_task": {"model": fx.conv(per(d["model"])), "compute": fx.conv(per(d["compute"])), "infrastructure": fx.conv(per(d["infra"])),
                                     "tooling": fx.conv(per(d["tooling"])), "human_review": fx.conv(per(d["review"])), "rework": fx.conv(per(d["rework"]))},
                     "ai_assisted_per_task": fx.conv(per(d["wf_cost_all"])), "ai_assisted_total": fx.conv(d["wf_cost_all"]),
                     "baseline_source": b.source, "baseline_data_class": b.data_class,
                     "baseline_hours": float(b.hours_per_task), "baseline_rate": fx.conv(b.hourly_rate_usd)})
    order = {w: i for i, w in enumerate(C.HUMAN_VS_AI_WORKFLOWS)}
    rows.sort(key=lambda r: order[r["workflow_type"]])
    return {"period": p.as_dict(), "fx": fx.as_dict(), "data_class": dc, "rows": rows,
            "notes": ["AI-assisted cost per task = all workflow cost of the type (including failed attempts, human review and rework) / verified tasks.",
                      "Human-only baselines are configured assumptions; edit them in Settings."]}


# ---------------------------------------------------------------------------------------------- Graph D
def ai_cost_breakdown(db: Session, p: Period, fx: Fx, dc: str) -> dict:
    ai = ai_cost_totals(db, p, dc)
    monthly = db.execute(select(M.AiCostRecord.date, M.AiCostRecord.category, func.sum(M.AiCostRecord.amount_usd))
                         .where(_between(M.AiCostRecord.date, p), M.AiCostRecord.data_class == dc)
                         .group_by(M.AiCostRecord.date, M.AiCostRecord.category)).all()
    mb: dict[str, dict[str, Decimal]] = {}
    for d, cat, amt in monthly:
        mb.setdefault(d.strftime("%Y-%m"), {}).setdefault(cat, ZERO)
        mb[d.strftime("%Y-%m")][cat] += D(amt)
    months = sorted(mb)
    return {"period": p.as_dict(), "fx": fx.as_dict(), "data_class": dc, "total": fx.conv(ai["total"]),
            "categories": [{"category": k, "label": C.AI_COST_CATEGORIES[k], "value": fx.conv(v),
                            "share_pct": float((v / ai["total"] * 100).quantize(Decimal("0.1"))) if ai["total"] else 0.0}
                           for k, v in sorted(ai["by_category"].items(), key=lambda kv: -kv[1])],
            "monthly": {"x": months, "series": {k: [fx.conv(mb[m].get(k, ZERO)) for m in months] for k in C.AI_COST_CATEGORIES}}}


def cost_records(db: Session, p: Period, category: str, fx: Fx, dc: str, limit: int = 200, offset: int = 0) -> dict:
    if category not in C.AI_COST_CATEGORIES:
        raise KeyError(category)
    base = select(M.AiCostRecord).where(_between(M.AiCostRecord.date, p), M.AiCostRecord.category == category, M.AiCostRecord.data_class == dc)
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.scalars(base.order_by(M.AiCostRecord.amount_usd.desc(), M.AiCostRecord.id).limit(limit).offset(offset)).all()
    return {"category": category, "label": C.AI_COST_CATEGORIES[category], "count": total, "fx": fx.as_dict(), "data_class": dc,
            "records": [{"id": r.id, "date": r.date.isoformat(), "subcategory": r.subcategory, "agent": r.agent, "task_id": r.task_id,
                         "amount": fx.conv(r.amount_usd), "description": r.description, "vendor": r.vendor, "basis": r.basis,
                         "data_class": r.data_class} for r in rows]}


# ---------------------------------------------------------------------------------------------- Graph E
def token_analytics(db: Session, p: Period, granularity: str, fx: Fx, dc: str) -> dict:
    tu = M.TokenUsage
    cost = tu.api_cost_usd + tu.local_compute_usd + tu.local_energy_usd
    by_day = db.execute(select(func.date(tu.ts), tu.provider, func.sum(tu.input_tokens), func.sum(tu.output_tokens), func.sum(tu.cached_tokens), func.sum(cost))
                        .where(_between(tu.ts, p), tu.data_class == dc).group_by(func.date(tu.ts), tu.provider)).all()
    buckets: dict[str, dict] = {}
    totals = {"local_qwen": {"input": 0, "output": 0, "cached": 0, "cost": ZERO}, "paid_api": {"input": 0, "output": 0, "cached": 0, "cost": ZERO}}
    for d, prov, i, o, c, co in by_day:
        d = d if isinstance(d, dt.date) else dt.date.fromisoformat(str(d))
        k = _bucket(d, granularity)
        row = buckets.setdefault(k, {"input": 0, "output": 0, "cached": 0, "local_qwen": 0, "paid_api": 0, "cost": ZERO})
        i, o, c = int(i or 0), int(o or 0), int(c or 0)
        row["input"] += i
        row["output"] += o
        row["cached"] += c
        row[prov] = row.get(prov, 0) + i + o
        row["cost"] += D(co)
        t = totals.setdefault(prov, {"input": 0, "output": 0, "cached": 0, "cost": ZERO})
        t["input"] += i
        t["output"] += o
        t["cached"] += c
        t["cost"] += D(co)
    keys = sorted(buckets)
    per_agent = db.execute(select(tu.agent, func.sum(tu.input_tokens + tu.output_tokens), func.sum(cost), func.count(func.distinct(tu.task_id)))
                           .where(_between(tu.ts, p), tu.data_class == dc).group_by(tu.agent)).all()
    tk = (task_aggregate(db, p, dc) or [{}])[0]
    total_tokens = sum(t["input"] + t["output"] for t in totals.values())
    total_cost = sum((t["cost"] for t in totals.values()), ZERO)
    tasks_n = tk.get("tasks", 0) or 0
    verified_n = tk.get("verified", 0) or 0

    def per_m(t):
        n = t["input"] + t["output"]
        return fx.conv(t["cost"] / n * 1_000_000) if n else None

    s = db.execute(select(func.sum(tu.api_cost_usd), func.sum(tu.local_compute_usd), func.sum(tu.local_energy_usd)).where(_between(tu.ts, p), tu.data_class == dc)).one()
    return {
        "period": p.as_dict(), "granularity": granularity, "fx": fx.as_dict(), "data_class": dc,
        "x": keys,
        "series": {"input": [buckets[k]["input"] for k in keys], "output": [buckets[k]["output"] for k in keys],
                   "cached": [buckets[k]["cached"] for k in keys], "total": [buckets[k]["input"] + buckets[k]["output"] for k in keys],
                   "local_qwen": [buckets[k].get("local_qwen", 0) for k in keys], "paid_api": [buckets[k].get("paid_api", 0) for k in keys],
                   "cost": [fx.conv(buckets[k]["cost"]) for k in keys]},
        "providers": {prov: {"input": t["input"], "output": t["output"], "cached": t["cached"], "total": t["input"] + t["output"],
                             "cost": fx.conv(t["cost"]), "cost_per_million": per_m(t)} for prov, t in totals.items()},
        "local_cost_components": {"api_charges": fx.conv(D(s[0])), "allocated_compute": fx.conv(D(s[1])), "electricity": fx.conv(D(s[2]))},
        "per_agent": sorted([{"agent": a, "label": C.AGENTS.get(a, {}).get("label", a), "tokens": int(n or 0), "cost": fx.conv(D(c)), "tasks": int(t or 0),
                              "tokens_per_task": int((n or 0) / t) if t else 0} for a, n, c, t in per_agent], key=lambda r: -r["tokens"]),
        "totals": {"tokens": total_tokens, "cost": fx.conv(total_cost), "cached": sum(t["cached"] for t in totals.values()),
                   "input": sum(t["input"] for t in totals.values()), "output": sum(t["output"] for t in totals.values()),
                   "tokens_per_task": int(total_tokens / tasks_n) if tasks_n else None,
                   "tokens_per_successful_task": int(total_tokens / verified_n) if verified_n else None,
                   "cost_per_million": fx.conv(total_cost / total_tokens * 1_000_000) if total_tokens else None,
                   "verified_tasks_per_million_tokens": round(verified_n / total_tokens * 1_000_000, 2) if total_tokens else None},
        "notes": ["Local Qwen inference has no API charge but carries allocated GPU/host compute and electricity cost.",
                  f"Paid model prices are a synthetic price card: input ${C.PAID_PRICE_PER_M['input']}/M, output ${C.PAID_PRICE_PER_M['output']}/M, cached ${C.PAID_PRICE_PER_M['cached']}/M."],
    }


# ---------------------------------------------------------------------------------------------- Graph G / H
def agent_productivity(db: Session, p: Period, fx: Fx, dc: str) -> dict:
    tu = M.TokenUsage
    tok = dict(db.execute(select(tu.agent, func.sum(tu.input_tokens + tu.output_tokens)).where(_between(tu.ts, p), tu.data_class == dc).group_by(tu.agent)).all())
    rows = []
    for d in task_aggregate(db, p, dc, (M.AgentTask.agent,)):
        a = d["agent"]
        hours_still = (d["human_min_verified"] / 60)
        rows.append({"agent": a, "label": C.AGENTS[a]["label"], "tasks": d["tasks"], "completed": d["verified"],
                     "human_hours_avoided": float((d["baseline_hours_verified"] - hours_still).quantize(Decimal("0.1"))),
                     "human_hours_required": float(((d["review_min"] + d["rework_min"]) / 60).quantize(Decimal("0.1"))),
                     "ai_execution_hours": round(d["duration_s"] / 3600, 1),
                     "cost_per_successful_task": fx.conv(d["wf_cost_all"] / d["verified"]) if d["verified"] else None,
                     "quality_pass_rate": round(d["quality_pass"] / d["tasks"] * 100, 1) if d["tasks"] else None,
                     "net_estimated_savings": fx.conv(d["cost_avoidance"] - d["wf_cost_unverified"]),
                     "tokens": int(tok.get(a) or 0), "retries": d["retries"]})
    rows.sort(key=lambda r: -r["net_estimated_savings"])
    vtok = int(tok.get("verification") or 0)
    return {"period": p.as_dict(), "fx": fx.as_dict(), "data_class": dc, "rows": rows,
            "verification_agent": {"tokens": vtok, "note": "The Independent Verification Agent's model cost is included in each verified task's workflow cost."},
            "notes": ["Net estimated savings by agent = cost avoidance on verified tasks - workflow cost of that agent's failed / unverified tasks. Platform overhead and implementation are not allocated to agents."]}


def department_value(db: Session, p: Period, fx: Fx, dc: str) -> dict:
    attr = dict(db.execute(select(M.RevenueAttribution.department, func.sum(M.RevenueAttribution.incremental_profit_usd))
                           .where(M.RevenueAttribution.period.in_(_months_in(p)), M.RevenueAttribution.data_class == dc)
                           .group_by(M.RevenueAttribution.department)).all())
    rows = []
    for d in task_aggregate(db, p, dc, (M.AgentTask.department,)):
        dep = d["department"]
        hours_avoided = d["baseline_hours_verified"] - d["human_min_verified"] / 60
        rows.append({"department": dep, "label": C.DEPARTMENTS[dep], "verified_tasks": d["verified"], "tasks": d["tasks"],
                     "hours_avoided": float(hours_avoided.quantize(Decimal("0.1"))),
                     "productivity_gain_pct": float((hours_avoided / d["baseline_hours_verified"] * 100).quantize(Decimal("0.1"))) if d["baseline_hours_verified"] else None,
                     "cost_avoidance": fx.conv(d["cost_avoidance"]), "incremental_profit": fx.conv(q(attr.get(dep))),
                     "unrecovered_cost": fx.conv(d["wf_cost_unverified"]),
                     "financial_impact": fx.conv(d["cost_avoidance"] + q(attr.get(dep)) - d["wf_cost_unverified"])})
    order = {k: i for i, k in enumerate(C.DEPARTMENTS)}
    rows.sort(key=lambda r: order.get(r["department"], 99))
    return {"period": p.as_dict(), "fx": fx.as_dict(), "data_class": dc, "rows": rows,
            "notes": ["Productivity gain = (baseline hours of verified work - human review and rework hours) / baseline hours."]}


# ---------------------------------------------------------------------------------------------- Graph F
def _linfit(ys: list[float]) -> tuple[float, float]:
    n = len(ys)
    xs = list(range(n))
    mx, my = sum(xs) / n, sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs) or 1
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
    return my - b * mx, b


SCENARIOS = {
    "best": {"label": "Best case", "revenue_trend": 1.4, "usage_growth": 1.3, "cost_per_task": 0.90, "verification_rate": 0.01},
    "base": {"label": "Base case", "revenue_trend": 1.0, "usage_growth": 1.0, "cost_per_task": 1.00, "verification_rate": 0.0},
    "downside": {"label": "Downside", "revenue_trend": 0.0, "usage_growth": 0.5, "cost_per_task": 1.15, "verification_rate": -0.05},
}


def forecast(db: Session, end_month: str, fx: Fx, dc: str, horizon: int = 12, lookback: int = 6, months_available: list[str] | None = None) -> dict:
    hist_months = months_available or []
    if not hist_months:
        rows = db.execute(select(M.Budget.period).where(M.Budget.data_class == dc).distinct()).scalars().all()
        hist_months = sorted(m for m in rows if m <= end_month)
    hist = []
    for m in hist_months:
        e = economics(db, resolve_period("month", m), dc)
        tk = e["tasks"]
        hist.append({"month": m, "revenue": float(e["bank"]["revenue"]), "opex": float(e["bank"]["opex"]), "ai_cost": float(e["ai"]["total"]),
                     "ai_cost_ex_impl": float(e["ai"]["total"] - e["ai"]["implementation"]), "implementation": float(e["ai"]["implementation"]),
                     "tasks": tk.get("tasks", 0), "verified": tk.get("verified", 0),
                     "value_per_verified": float(e["value_verified"] / tk["verified"]) if tk.get("verified") else 0.0,
                     "var_cost_per_task": float(e["ai"]["workflow_linked"] / tk["tasks"]) if tk.get("tasks") else 0.0,
                     "overhead": float(e["ai"]["overhead"]), "incremental_profit": float(e["attribution"]["incremental_profit"]),
                     "net_benefit": float(e["net_benefit"])})
    if len(hist) < 3:
        return {"available": False, "reason": "At least three months of history are required for a forecast.", "data_class": dc}
    lb = hist[-lookback:]
    a_rev, b_rev = _linfit([h["revenue"] for h in lb])
    a_opx, b_opx = _linfit([h["opex"] - h["ai_cost_ex_impl"] for h in lb])
    g_tasks = (lb[-1]["tasks"] / lb[0]["tasks"]) ** (1 / max(1, len(lb) - 1)) - 1 if lb[0]["tasks"] else 0.0
    ver_rate = sum(h["verified"] for h in lb) / max(1, sum(h["tasks"] for h in lb))
    value_pv = sum(h["value_per_verified"] for h in lb) / len(lb)
    var_cpt = sum(h["var_cost_per_task"] for h in lb) / len(lb)
    overhead = sum(h["overhead"] for h in lb) / len(lb)
    impl = hist[-1]["implementation"]
    profit_g = (lb[-1]["incremental_profit"] / lb[0]["incremental_profit"]) ** (1 / max(1, len(lb) - 1)) - 1 if lb[0]["incremental_profit"] else 0.0
    y, mth = map(int, hist[-1]["month"].split("-"))
    future = []
    for i in range(1, horizon + 1):
        mth += 1
        if mth == 13:
            y, mth = y + 1, 1
        future.append(f"{y:04d}-{mth:02d}")
    capex = float(C.IMPLEMENTATION_CAPEX_USD)
    cum_hist = 0.0
    hist_breakeven = None
    for h in hist:  # cumulative economic benefit before amortisation, against the full capex outlay
        cum_hist += h["net_benefit"] + h["implementation"]
        if hist_breakeven is None and cum_hist >= capex:
            hist_breakeven = h["month"]
    scenarios = {}
    for key, sc in SCENARIOS.items():
        tasks = lb[-1]["tasks"]
        prof = lb[-1]["incremental_profit"]
        cum = cum_hist - capex
        series = []
        breakeven = hist_breakeven
        n0 = len(lb)
        for i, m in enumerate(future, start=1):
            tasks = tasks * (1 + g_tasks * sc["usage_growth"])
            prof = prof * (1 + profit_g * sc["usage_growth"])
            vr = min(1.0, max(0.0, ver_rate + sc["verification_rate"]))
            revenue = a_rev + b_rev * (n0 - 1 + i) * 1.0
            revenue = lb[-1]["revenue"] + (revenue - lb[-1]["revenue"]) * sc["revenue_trend"]
            ai_opex = tasks * var_cpt * sc["cost_per_task"] + overhead
            value = tasks * vr * value_pv
            net_pre_impl = prof + value - ai_opex
            cum += net_pre_impl
            if breakeven is None and cum >= 0:
                breakeven = m
            opex_ex_ai = a_opx + b_opx * (n0 - 1 + i)
            series.append({"month": m, "revenue": fx.conv(revenue), "opex": fx.conv(opex_ex_ai + ai_opex + impl), "ai_opex": fx.conv(ai_opex),
                           "estimated_savings": fx.conv(value - tasks * vr * var_cpt * sc["cost_per_task"]), "tasks": int(tasks),
                           "net_benefit": fx.conv(net_pre_impl - impl), "cumulative_vs_capex": fx.conv(cum)})
        scenarios[key] = {"label": sc["label"], "assumptions": sc, "series": series, "breakeven_month": breakeven,
                          "breakeven_basis": "historical" if hist_breakeven else ("forecast" if breakeven else None)}
    return {"available": True, "data_class": dc, "basis": "forecast", "fx": fx.as_dict(),
            "history": [{"month": h["month"], "revenue": fx.conv(h["revenue"]), "opex": fx.conv(h["opex"]), "ai_cost": fx.conv(h["ai_cost"]),
                         "net_benefit": fx.conv(h["net_benefit"])} for h in hist],
            "assumptions": {"lookback_months": len(lb), "revenue_trend_per_month": fx.conv(b_rev), "task_growth_per_month_pct": round(g_tasks * 100, 2),
                            "verification_rate_pct": round(ver_rate * 100, 1), "value_per_verified_task": fx.conv(value_pv),
                            "variable_ai_cost_per_task": fx.conv(var_cpt), "monthly_platform_overhead": fx.conv(overhead),
                            "incremental_profit_growth_per_month_pct": round(profit_g * 100, 2), "implementation_capex": fx.conv(capex),
                            "cumulative_benefit_before_amortisation_to_date": fx.conv(cum_hist)},
            "scenarios": scenarios,
            "disclaimer": "Forecasts are scenario projections from trailing trends and stated assumptions. They are not guarantees and are not management guidance."}


# ---------------------------------------------------------------------------------------------- cost drivers
def cost_drivers(db: Session, current: Period, baseline: Period, fx: Fx, dc: str, top: int = 6) -> dict:
    """Explain why AI spend changed between two periods, using only recorded cost rows (normalised per day)."""
    def by(col, p):
        return {k or "platform (no agent)": D(v) for k, v in db.execute(select(col, func.sum(M.AiCostRecord.amount_usd))
                                                                         .where(_between(M.AiCostRecord.date, p), M.AiCostRecord.data_class == dc)
                                                                         .group_by(col)).all()}
    cur_cat, base_cat = by(M.AiCostRecord.category, current), by(M.AiCostRecord.category, baseline)
    cur_ag, base_ag = by(M.AiCostRecord.agent, current), by(M.AiCostRecord.agent, baseline)
    cd, bd = Decimal(current.days), Decimal(baseline.days)

    def deltas(cur, base, labels):
        out = []
        for k in set(cur) | set(base):
            c, b = cur.get(k, ZERO) / cd, base.get(k, ZERO) / bd
            out.append({"key": k, "label": labels.get(k, k), "current_per_day": fx.conv(c), "baseline_per_day": fx.conv(b), "delta_per_day": fx.conv(c - b),
                        "delta_pct": _pct_change(c, b)})
        return sorted(out, key=lambda r: -abs(r["delta_per_day"]))[:top]
    tot_c = sum(cur_cat.values(), ZERO) / cd
    tot_b = sum(base_cat.values(), ZERO) / bd
    tk_c = (task_aggregate(db, current, dc) or [{}])[0]
    tk_b = (task_aggregate(db, baseline, dc) or [{}])[0]
    tu = M.TokenUsage

    def tok(p):
        r = db.execute(select(func.sum(tu.input_tokens + tu.output_tokens), func.sum(case((tu.provider == "paid_api", tu.input_tokens + tu.output_tokens), else_=0)))
                       .where(_between(tu.ts, p), tu.data_class == dc)).one()
        return int(r[0] or 0), int(r[1] or 0)
    tc, tb = tok(current), tok(baseline)
    return {"current": current.as_dict(), "baseline": baseline.as_dict(), "fx": fx.as_dict(), "data_class": dc,
            "total_per_day": {"current": fx.conv(tot_c), "baseline": fx.conv(tot_b), "delta": fx.conv(tot_c - tot_b), "delta_pct": _pct_change(tot_c, tot_b)},
            "by_category": deltas(cur_cat, base_cat, C.AI_COST_CATEGORIES), "by_agent": deltas(cur_ag, base_ag, {k: v["label"] for k, v in C.AGENTS.items()}),
            "volume": {"tasks_per_day_current": round(tk_c.get("tasks", 0) / current.days, 1), "tasks_per_day_baseline": round(tk_b.get("tasks", 0) / baseline.days, 1),
                       "tokens_per_day_current": int(tc[0] / current.days), "tokens_per_day_baseline": int(tb[0] / baseline.days),
                       "paid_token_share_current_pct": round(tc[1] / tc[0] * 100, 1) if tc[0] else None,
                       "paid_token_share_baseline_pct": round(tb[1] / tb[0] * 100, 1) if tb[0] else None,
                       "retries_per_task_current": round(tk_c.get("retries", 0) / tk_c["tasks"], 2) if tk_c.get("tasks") else None,
                       "retries_per_task_baseline": round(tk_b.get("retries", 0) / tk_b["tasks"], 2) if tk_b.get("tasks") else None}}


def data_bounds(db: Session, dc: str) -> dict:
    r = db.execute(select(func.min(M.LedgerLine.date), func.max(M.LedgerLine.date)).where(M.LedgerLine.data_class == dc)).one()
    t = db.execute(select(func.min(M.AgentTask.created_at), func.max(M.AgentTask.created_at)).where(M.AgentTask.data_class == dc)).one()
    return {"ledger_start": r[0].isoformat() if r[0] else None, "ledger_end": r[1].isoformat() if r[1] else None,
            "tasks_start": t[0].date().isoformat() if t[0] else None, "tasks_end": t[1].date().isoformat() if t[1] else None}
