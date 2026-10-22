"""Dashboard composition: the visualization agent and its allowlisted chart and KPI builders.

The visualization agent is a registered specialist like any other. Every chart's data is fetched through the tool
gateway as the requesting user, so a chart the user may not see is withheld (and the denial audited), never rendered
from cached or elevated data. Builders emit `ChartSpec` objects validated against the versioned `flo.viz/1.0` schema;
the browser renders data, it never executes chart code.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

from agents.specialists import AgentOutput, ctx_harness, spec
from conversation.schemas import KPI, ChartSpec, FilterSpec, Lineage, MetricDef, Node, Series, Table
from harness.errors import HarnessError, PolicyDenied
from harness.models import template
from harness.registry import REGISTRY

VIZ_TOOLS = ["finance.kpis", "finance.aum_trend", "finance.aum_waterfall", "finance.net_flows_by", "finance.revenue_expenses", "finance.margin_trend",
             "finance.revenue_attribution", "finance.product_profitability", "finance.actual_vs_budget", "finance.retention", "strategy.initiatives",
             "investment.enterprise_concentration", "investment.correlation", "investment.geographic_exposure", "investment.fund_list", "risk.heatmap",
             "scenario.run", "scenario.compare", "scenario.sensitivity", "wealth.advisor_productivity", "wealth.book_health", "advisory.firm_model",
             "client.profile", "client.portfolios", "client.goals", "client.suitability", "client.retirement"]
VIZ_ROLES = frozenset({"executive", "finance", "cio", "investment_analyst", "wealth_advisor", "external_advisor", "compliance_officer",
                       "privacy_officer", "ai_admin", "risk_officer", "prospect"})
MONTH_FILTER = lambda v: FilterSpec(id="months", label="Window", options=[12, 24], value=v)  # noqa: E731


class VizQ(BaseModel):
    model_config = {"extra": "forbid"}
    charts: list[str] = Field(default_factory=list, max_length=12)
    kpis: str | None = None
    months: int = Field(12, ge=1, le=24)
    group_by: str | None = None
    client_id: str | None = Field(None, pattern=r"^C-\d{5}$")
    scenario: dict[str, Any] = {}
    business_profile: dict[str, Any] = {}
    persona: str = "ceo"


class Ctx:
    """Per-run memo so several charts can share one governed tool call."""

    def __init__(self, ctx, q: VizQ):
        self.ctx, self.q, self.memo, self.denied, self.tools = ctx, q, {}, [], []
        self.client_choices: list[dict] = []

    def tool(self, name: str, **args) -> dict:
        key = (name, tuple(sorted(args.items(), key=lambda kv: kv[0])))
        if key not in self.memo:
            self.memo[key] = self.ctx.tool(name, **args)
            self.tools.append(name)
        return self.memo[key]


def _lin(raw: dict | None, tools: list[str], methodology: str = "") -> Lineage:
    raw = raw or {}
    return Lineage(sources=[s.get("system", s.get("category", "")) for s in raw.get("sources", [])], methodology=raw.get("methodology", methodology),
                   as_of=raw.get("as_of"), refreshed_at=raw.get("refreshed_at"), dataset_version=raw.get("dataset_version"),
                   semantic_layer_version=raw.get("semantic_layer_version"), synthetic=raw.get("synthetic", True), tools=tools)


def _metrics(raw: dict | None) -> list[MetricDef]:
    return [MetricDef(id=m["id"], name=m["name"], definition=m["definition"], formula=m.get("formula", ""), unit=m.get("unit", ""))
            for m in (raw or {}).get("metrics", [])]


def _f(x) -> float:
    return round(float(x), 4)


# ------------------------------------------------------------------------------------------------ chart builders
def aum_trend(c: Ctx) -> ChartSpec:
    gb = c.q.group_by if c.q.group_by in ("asset_class", "vehicle", "region", "strategy") else "asset_class"
    months = max(c.q.months, 12)
    r = c.tool("finance.aum_trend", months=months, group_by=gb)
    d = r["data"]
    return ChartSpec(chart_id="aum_trend", chart_type="stacked_area", title="AUM trend", subtitle=f"Month-end AUM by {gb.replace('_', ' ')}",
                     categories=d["months"], series=[Series(name=s["name"], values=s["values"], unit="CAD", metric_id="aum.total") for s in d["series"]],
                     y_axis={"label": "AUM", "unit": "CAD"}, unit="CAD", metrics=_metrics(r["lineage"]), lineage=_lin(r["lineage"], ["finance.aum_trend"]),
                     filters={"months": months, "group_by": gb}, available_filters=[MONTH_FILTER(months),
                     FilterSpec(id="group_by", label="Group by", options=["asset_class", "vehicle", "region", "strategy"], value=gb)],
                     drilldown={"dimension": gb, "prompt_template": "Explain the AUM trend for {value}."},
                     interactions=["tooltip", "drilldown", "filter", "export", "explain", "methodology"])


def aum_waterfall(c: Ctx) -> ChartSpec:
    r = c.tool("finance.aum_waterfall", months=c.q.months)
    d = r["data"]
    return ChartSpec(chart_id="aum_waterfall", chart_type="waterfall", title="AUM roll-forward", subtitle=f"{d['period'][0]} to {d['period'][1]}",
                     categories=[s["step"] for s in d["steps"]], series=[Series(name="AUM change", values=[_f(s["value"]) for s in d["steps"]], unit="CAD")],
                     unit="CAD", metrics=_metrics(r["lineage"]), lineage=_lin(r["lineage"], ["finance.aum_waterfall"]), filters={"months": c.q.months},
                     available_filters=[MONTH_FILTER(c.q.months)], note="Reconciles to the cent" if d["reconciliation"]["balanced"] else "Reconciliation break")


def net_flows(c: Ctx) -> ChartSpec:
    gb = c.q.group_by if c.q.group_by in ("vehicle", "asset_class", "region") else "vehicle"
    months = max(c.q.months, 12)
    r = c.tool("finance.net_flows_by", months=months, group_by=gb)
    d = r["data"]
    return ChartSpec(chart_id="net_flows", chart_type="stacked_bar", title="Net client flows", subtitle=f"Subscriptions minus redemptions by {gb.replace('_', ' ')}",
                     categories=d["months"], series=[Series(name=s["name"], values=s["net"], unit="CAD", metric_id="flows.net", stack="net") for s in d["series"]],
                     unit="CAD", y_axis={"label": "Net flows", "unit": "CAD"}, metrics=_metrics(r["lineage"]), lineage=_lin(r["lineage"], ["finance.net_flows_by"]),
                     filters={"months": months, "group_by": gb}, available_filters=[MONTH_FILTER(months),
                     FilterSpec(id="group_by", label="Group by", options=["vehicle", "asset_class", "region"], value=gb)],
                     drilldown={"dimension": gb, "prompt_template": "Why are net flows what they are for {value}?"},
                     interactions=["tooltip", "drilldown", "filter", "export", "explain", "methodology"])


def revenue_expenses(c: Ctx) -> ChartSpec:
    r = c.tool("finance.revenue_expenses", months=24)
    d = r["data"]
    n = max(c.q.months, 12)
    cats = d["months"][-n:]
    series = [Series(name=k.replace("expense_", "").replace("_", " ").title(), values=v[-n:], unit="CAD", render="bar", stack="expenses",
                     metric_id="expenses.operating") for k, v in d["expenses"].items()]
    series.append(Series(name="Revenue", values=d["revenue"][-n:], unit="CAD", render="line", metric_id="revenue.management_fees"))
    return ChartSpec(chart_id="revenue_expenses", chart_type="combo", title="Revenue versus expenses", subtitle="Monthly management fee revenue and expense lines",
                     categories=cats, series=series, unit="CAD", metrics=_metrics(r["lineage"]), lineage=_lin(r["lineage"], ["finance.revenue_expenses"]),
                     filters={"months": n}, available_filters=[MONTH_FILTER(n)],
                     drilldown={"dimension": "expense_line", "prompt_template": "What is driving {value} expenses?"},
                     interactions=["tooltip", "drilldown", "filter", "export", "explain", "methodology"])


def margin_trend(c: Ctx) -> ChartSpec:
    r = c.tool("finance.margin_trend", months=24)
    d = r["data"]
    n = max(c.q.months, 12)
    return ChartSpec(chart_id="margin_trend", chart_type="line", title="Operating margin trend", subtitle="Operating income / revenue, monthly",
                     categories=d["months"][-n:], series=[Series(name="Operating margin", values=d["operating_margin"][-n:], unit="%", metric_id="margin.operating")],
                     unit="%", reference_lines=[{"label": "average", "type": "average"}], metrics=_metrics(r["lineage"]),
                     lineage=_lin(r["lineage"], ["finance.margin_trend"]), filters={"months": n}, available_filters=[MONTH_FILTER(n)],
                     interactions=["tooltip", "filter", "compare", "export", "explain", "methodology"])


def revenue_yield(c: Ctx) -> ChartSpec:
    r = c.tool("finance.margin_trend", months=24)
    d = r["data"]
    n = max(c.q.months, 12)
    return ChartSpec(chart_id="revenue_yield", chart_type="line", title="Revenue yield", subtitle="Annualized management fee revenue / average AUM",
                     categories=d["months"][-n:], series=[Series(name="Revenue yield", values=d["revenue_yield_bps"][-n:], unit="bps", metric_id="revenue.yield_bps")],
                     unit="bps", metrics=_metrics(r["lineage"]), lineage=_lin(r["lineage"], ["finance.margin_trend"]), filters={"months": n},
                     available_filters=[MONTH_FILTER(n)])


def revenue_bridge(c: Ctx) -> ChartSpec:
    r = c.tool("finance.revenue_attribution", months=12)
    d = r["data"]
    steps = [("Prior 12m revenue", d["annualized_revenue_0"]), ("Volume effect", d["volume_effect"]), ("Mix effect", d["mix_effect"]),
             ("Fee change effect", d["fee_change_effect"]), ("Current 12m revenue", d["annualized_revenue_1"])]
    return ChartSpec(chart_id="revenue_bridge", chart_type="waterfall", title="Revenue bridge", subtitle=f"Yield {d['yield_bps_0']} → {d['yield_bps_1']} bps",
                     categories=[s[0] for s in steps], series=[Series(name="Revenue", values=[_f(s[1]) for s in steps], unit="CAD")], unit="CAD",
                     metrics=_metrics(r["lineage"]), lineage=_lin(r["lineage"], ["finance.revenue_attribution"]),
                     drilldown={"dimension": "effect", "prompt_template": "Explain the {value} in the revenue bridge."},
                     interactions=["tooltip", "drilldown", "export", "explain", "methodology"])


def product_profitability(c: Ctx) -> ChartSpec:
    r = c.tool("finance.product_profitability", months=c.q.months)
    d = r["data"]
    nodes = []
    for g in d["tree"]:
        nodes.append(Node(id=g["name"], name=g["name"]))
        for p in g["children"]:
            nodes.append(Node(id=p["id"], name=p["name"].replace(" (SYN)", ""), value=p["revenue"], parent=g["name"], color_value=p["margin"],
                              meta={"margin": p["margin"], "fee_bps": p["fee_bps"], "contribution": p["contribution"], "vehicle": p["vehicle"]}))
    return ChartSpec(chart_id="product_profitability", chart_type="treemap", title="Product profitability", subtitle="Area = revenue · colour = contribution margin",
                     nodes=nodes, unit="CAD", metrics=_metrics(r["lineage"]), lineage=_lin(r["lineage"], ["finance.product_profitability"]),
                     filters={"months": c.q.months}, drilldown={"dimension": "product", "prompt_template": "Explain the profitability of {value}."},
                     interactions=["tooltip", "drilldown", "export", "explain", "methodology"])


def product_revenue(c: Ctx) -> ChartSpec:
    r = c.tool("finance.product_profitability", months=c.q.months)
    rows = sorted((p for g in r["data"]["tree"] for p in g["children"]), key=lambda p: -p["revenue"])[:12]
    return ChartSpec(chart_id="product_revenue", chart_type="hbar", title="Revenue and contribution by product", subtitle="Top 12 products by revenue",
                     categories=[p["name"].replace(" (SYN)", "") for p in rows],
                     series=[Series(name="Revenue", values=[p["revenue"] for p in rows], unit="CAD"),
                             Series(name="Contribution", values=[p["contribution"] for p in rows], unit="CAD", role="comparison")],
                     unit="CAD", metrics=_metrics(r["lineage"]), lineage=_lin(r["lineage"], ["finance.product_profitability"]), filters={"months": c.q.months},
                     drilldown={"dimension": "product", "prompt_template": "Explain the profitability of {value}."},
                     interactions=["tooltip", "drilldown", "compare", "export", "explain", "methodology"])


def budget_variance(c: Ctx) -> ChartSpec:
    r = c.tool("finance.actual_vs_budget", months=c.q.months)
    lines = r["data"]["lines"]
    return ChartSpec(chart_id="budget_variance", chart_type="grouped_bar", title="Actual versus budget", subtitle=f"{r['data']['period'][0]} to {r['data']['period'][1]}",
                     categories=[x["line"].replace("expense_", "").replace("revenue_", "").replace("_", " ") for x in lines],
                     series=[Series(name="Actual", values=[x["actual"] for x in lines], unit="CAD"),
                             Series(name="Budget", values=[x["budget"] for x in lines], unit="CAD", role="baseline")],
                     unit="CAD", metrics=_metrics(r["lineage"]), lineage=_lin(r["lineage"], ["finance.actual_vs_budget"]), filters={"months": c.q.months},
                     available_filters=[MONTH_FILTER(c.q.months)], interactions=["tooltip", "compare", "filter", "export", "explain", "methodology"])


def initiative_scorecard(c: Ctx) -> ChartSpec:
    r = c.tool("strategy.initiatives")
    rows = r["data"]["initiatives"]
    return ChartSpec(chart_id="initiative_scorecard", chart_type="scorecard", title="Strategic initiatives", subtitle="Reported progress vs plan",
                     nodes=[Node(id=i["id"], name=i["name"], value=i["progress_pct"], x=i["planned_progress_pct"],
                                 status="crit" if i["status"] == "behind" else "ok" if i["status"] in ("on_track", "complete", "completed") else "warn",
                                 meta={"owner": i["owner"], "status": i["status"], "target_kpi": i["target_kpi"]}) for i in rows],
                     unit="%", metrics=_metrics(r["lineage"]), lineage=_lin(r["lineage"], ["strategy.initiatives"]),
                     drilldown={"dimension": "initiative", "prompt_template": "Why is the initiative {value} where it is?"},
                     interactions=["tooltip", "drilldown", "export", "explain", "methodology"])


def risk_heatmap(c: Ctx) -> ChartSpec:
    r = c.tool("risk.heatmap")
    g = r["data"]["grid"]
    cells = [[j, i, g[i][j]] for i in range(5) for j in range(5)]
    return ChartSpec(chart_id="risk_heatmap", chart_type="heatmap", title="Enterprise risk heatmap", subtitle="Count of register risks by likelihood × impact",
                     x_labels=["1", "2", "3", "4", "5"], y_labels=["1", "2", "3", "4", "5"], cells=cells, x_axis={"label": "Likelihood"},
                     y_axis={"label": "Impact"}, unit="count", metrics=_metrics(r["lineage"]), lineage=_lin(r["lineage"], ["risk.heatmap"]),
                     drilldown={"dimension": "cell", "prompt_template": "Explain the largest risk."})


def concentration_top_issuers(c: Ctx) -> ChartSpec:
    r = c.tool("investment.enterprise_concentration")
    d = r["data"]
    top = d["top_holdings"][:10]
    return ChartSpec(chart_id="concentration_top_issuers", chart_type="hbar", title="Largest issuer exposures", subtitle=f"{d['portfolios_breaching_single_issuer_limit']} portfolios breach the {round(d['limit'] * 100)}% single-issuer limit",
                     categories=[h["name"] for h in top], series=[Series(name="Share of portfolio assets", values=[h["weight"] for h in top], unit="%", metric_id="risk.single_issuer")],
                     reference_lines=[{"label": "single-issuer limit", "value": d["limit"]}], unit="%", metrics=_metrics(r.get("lineage")),
                     lineage=_lin(r.get("lineage"), ["investment.enterprise_concentration"], "Aggregate look-through across managed portfolios."),
                     drilldown={"dimension": "issuer", "prompt_template": "Which portfolios hold {value} and how should exposure be reviewed?"},
                     interactions=["tooltip", "drilldown", "export", "explain", "methodology"])


def sector_exposure(c: Ctx) -> ChartSpec:
    r = c.tool("investment.enterprise_concentration")
    secs = r["data"]["sector_exposure"]
    top, rest = secs[:7], secs[7:]
    cats = [s["sector"] for s in top] + (["Other"] if rest else [])
    vals = [s["weight"] for s in top] + ([round(sum(s["weight"] for s in rest), 6)] if rest else [])
    return ChartSpec(chart_id="sector_exposure", chart_type="donut", title="Sector exposure", subtitle="Share of managed portfolio assets",
                     categories=cats, series=[Series(name="Weight", values=vals, unit="%")], unit="%",
                     lineage=_lin(r.get("lineage"), ["investment.enterprise_concentration"], "Aggregate sector weights across managed portfolios."))


def geographic_exposure(c: Ctx) -> ChartSpec:
    r = c.tool("investment.geographic_exposure")
    rows = r["data"]["countries"]
    return ChartSpec(chart_id="geographic_exposure", chart_type="geo", title="Geographic exposure", subtitle="Look-through by issuer country",
                     nodes=[Node(id=x["country"], name=x["country"], value=x["value"], lat=x["lat"], lon=x["lon"], group=x["region"], meta={"weight": x["weight"]})
                            for x in rows], unit="CAD", metrics=_metrics(r["lineage"]), lineage=_lin(r["lineage"], ["investment.geographic_exposure"]))


def correlation(c: Ctx) -> ChartSpec:
    r = c.tool("investment.correlation")
    d = r["data"]
    n = len(d["labels"])
    return ChartSpec(chart_id="correlation", chart_type="matrix", title="Sector correlation", subtitle="Pairwise correlation of monthly sector returns",
                     x_labels=d["labels"], y_labels=d["labels"], cells=[[j, i, round(d["matrix"][i][j], 3)] for i in range(n) for j in range(n)],
                     unit="ratio", lineage=_lin(r.get("lineage"), ["investment.correlation"], "Pearson correlation of 24 monthly sector returns."))


def _scenario_args(c: Ctx) -> dict:
    s = c.q.scenario or {}
    return {k: s[k] for k in ("preset", "equity_shock", "rate_shock_bps") if s.get(k) is not None} or {"preset": "bear"}


def scenario_paths(c: Ctx) -> ChartSpec:
    a = _scenario_args(c)
    r = c.tool("scenario.run", **a)
    base = c.tool("scenario.run", preset="base")
    hz = r["horizon_months"]
    return ChartSpec(chart_id="scenario_paths", chart_type="line", title="AUM path under the scenario", subtitle=f"'{r['scenario']}' vs base over {hz} months",
                     categories=[f"M{t}" for t in range(hz + 1)],
                     series=[Series(name=f"Scenario: {r['scenario']}", values=[_f(x) for x in r["aum_path"]], unit="CAD", role="scenario"),
                             Series(name="Base case", values=[_f(x) for x in base["aum_path"]], unit="CAD", role="baseline")],
                     unit="CAD", lineage=Lineage(sources=["scenario engine"], methodology=r["method"], tools=["scenario.run"]),
                     interactions=["tooltip", "compare", "export", "explain", "methodology"], note=_assumption_line(r))


def _assumption_line(r: dict) -> str:
    a = {x["name"]: x["value"] for x in r["assumptions"]}
    return (f"Assumptions: equity {a['equity_shock'] * 100:.0f}%, rates {a['rate_shock_bps']:+.0f} bps, net flows {a['net_flows_pct'] * 100:.1f}% p.a., "
            f"fee compression {a['fee_compression_bps']:.0f} bps. Conditional outputs, not forecasts.")


def scenario_by_asset_class(c: Ctx) -> ChartSpec:
    r = c.tool("scenario.run", **_scenario_args(c))
    rows = r["by_asset_class"]
    return ChartSpec(chart_id="scenario_by_asset_class", chart_type="bar", title="Scenario impact by asset class", subtitle="Change in AUM over the horizon",
                     categories=[x["asset_class"] for x in rows], series=[Series(name="AUM change", values=[x["change_pct"] for x in rows], unit="%")],
                     unit="%", lineage=Lineage(sources=["scenario engine"], methodology=r["method"], tools=["scenario.run"]), note=_assumption_line(r),
                     drilldown={"dimension": "asset_class", "prompt_template": "Why does {value} move the way it does in this scenario?"},
                     interactions=["tooltip", "drilldown", "export", "explain", "methodology"])


def portfolio_impacts(c: Ctx) -> ChartSpec:
    r = c.tool("scenario.run", **_scenario_args(c))
    bm = r["portfolio_impacts"]["by_mandate"]
    return ChartSpec(chart_id="portfolio_impacts", chart_type="hbar", title="Immediate impact by mandate", subtitle="Average shock to managed portfolios",
                     categories=list(bm), series=[Series(name="Impact", values=list(bm.values()), unit="%")], unit="%",
                     lineage=Lineage(sources=["scenario engine", "portfolio_management"], methodology=r["method"], tools=["scenario.run"]))


def scenario_comparison(c: Ctx) -> ChartSpec:
    r = c.tool("scenario.compare")
    sc = r["scenarios"]
    return ChartSpec(chart_id="scenario_comparison", chart_type="grouped_bar", title="Scenario comparison", subtitle="Operating income and revenue by preset",
                     categories=[x["scenario"].replace("_", " ") for x in sc],
                     series=[Series(name="Revenue", values=[_f(x["revenue"]) for x in sc], unit="CAD"),
                             Series(name="Operating income", values=[_f(x["operating_income"]) for x in sc], unit="CAD")],
                     unit="CAD", lineage=Lineage(sources=["scenario engine"], methodology="Deterministic presets; conditional outputs, not forecasts.",
                                                 tools=["scenario.compare"]), interactions=["tooltip", "compare", "export", "explain", "methodology"])


def sensitivity_tornado(c: Ctx) -> ChartSpec:
    r = c.tool("scenario.sensitivity")
    t = r["tornado"]
    return ChartSpec(chart_id="sensitivity_tornado", chart_type="tornado", title="Operating income sensitivity", subtitle="Each driver moved ± one step",
                     categories=[x["driver"].replace("_", " ") for x in t],
                     series=[Series(name="Downside", values=[_f(x["operating_income_low"]) for x in t], unit="CAD"),
                             Series(name="Upside", values=[_f(x["operating_income_high"]) for x in t], unit="CAD")],
                     unit="CAD", lineage=Lineage(sources=["scenario engine"], methodology=r["method"], tools=["scenario.sensitivity"]))


def advisor_productivity_scatter(c: Ctx) -> ChartSpec:
    r = c.tool("wealth.advisor_productivity")
    rows = r["data"]["advisors"]
    return ChartSpec(chart_id="advisor_productivity_scatter", chart_type="scatter", title="Advisor books: clients versus AUM",
                     subtitle="Each point is an advisor · size = interactions in 12 months",
                     nodes=[Node(id=a["advisor_id"], name=a["advisor"], x=a["active_clients"], y=a["book_aum"], size=a["interactions_12m"], group=a["region"],
                                 meta={"retention_12m": a["retention_12m"], "kyc_stale": a["kyc_stale"]}) for a in rows],
                     x_axis={"label": "Active clients", "unit": "count"}, y_axis={"label": "Book AUM", "unit": "CAD"}, unit="CAD",
                     metrics=_metrics(r["lineage"]), lineage=_lin(r["lineage"], ["wealth.advisor_productivity"]),
                     drilldown={"dimension": "advisor", "prompt_template": "What could help {value}'s book grow?"},
                     interactions=["tooltip", "drilldown", "export", "explain", "methodology"])


def advisor_book_distribution(c: Ctx) -> ChartSpec:
    r = c.tool("wealth.advisor_productivity")
    rows = r["data"]["advisors"]
    return ChartSpec(chart_id="advisor_book_distribution", chart_type="bar", title="Book AUM by advisor", subtitle="Ranked; dispersion shows where coaching or rebalancing may help",
                     categories=[a["advisor_id"] for a in rows], series=[Series(name="Book AUM", values=[a["book_aum"] for a in rows], unit="CAD", metric_id="advisor.book_aum")],
                     reference_lines=[{"label": "median", "value": r["data"]["summary"]["median_book_aum"]}], unit="CAD",
                     metrics=_metrics(r["lineage"]), lineage=_lin(r["lineage"], ["wealth.advisor_productivity"]))


def retention_trend(c: Ctx) -> ChartSpec:
    r = c.tool("finance.retention")
    t = r["data"]["trend"]
    return ChartSpec(chart_id="retention_trend", chart_type="combo", title="Active clients and closures", subtitle="Enterprise, monthly",
                     categories=[x["month"] for x in t], series=[Series(name="Active clients", values=[x["active_clients"] for x in t], unit="count", render="line"),
                                                                Series(name="Closures", values=[x["closures"] for x in t], unit="count", render="bar")],
                     unit="count", metrics=_metrics(r["lineage"]), lineage=_lin(r["lineage"], ["finance.retention"]))


def retention_by_segment(c: Ctx) -> ChartSpec:
    r = c.tool("finance.retention")
    s = [x for x in r["data"]["by_segment"] if x["retention_12m"] is not None]
    return ChartSpec(chart_id="retention_by_segment", chart_type="bar", title="12-month retention by segment", categories=[x["segment"] for x in s],
                     series=[Series(name="Retention", values=[x["retention_12m"] for x in s], unit="%", metric_id="clients.retention")], unit="%",
                     metrics=_metrics(r["lineage"]), lineage=_lin(r["lineage"], ["finance.retention"]),
                     drilldown={"dimension": "segment", "prompt_template": "Why is retention lower in the {value} segment?"},
                     interactions=["tooltip", "drilldown", "export", "explain", "methodology"])


def book_trend(c: Ctx) -> ChartSpec:
    r = c.tool("wealth.book_health")
    t = r["data"]["trend"]
    return ChartSpec(chart_id="book_trend", chart_type="combo", title="Your book: active clients and closures", categories=[x["month"] for x in t],
                     series=[Series(name="Active clients", values=[x["active_clients"] for x in t], unit="count", render="line"),
                             Series(name="Closures", values=[x["closures"] for x in t], unit="count", render="bar")],
                     unit="count", metrics=_metrics(r["lineage"]), lineage=_lin(r["lineage"], ["wealth.book_health"]))


def book_signals(c: Ctx) -> ChartSpec:
    r = c.tool("wealth.book_health")
    sc = r["data"]["signal_counts"]
    labels = {"negative_sentiment_6m": "Negative sentiment (6m)", "follow_up_flagged_90d": "Follow-up flagged (90d)", "kyc_stale": "KYC older than policy"}
    return ChartSpec(chart_id="book_signals", chart_type="hbar", title="Client review signals in your book", subtitle="Observable prompts for outreach, not predictions",
                     categories=[labels[k] for k in sc], series=[Series(name="Clients", values=list(sc.values()), unit="count", metric_id="clients.at_risk_signals")],
                     unit="count", metrics=_metrics(r["lineage"]), lineage=_lin(r["lineage"], ["wealth.book_health"]),
                     drilldown={"dimension": "signal", "prompt_template": "Which clients show the signal '{value}' and what should I do?"},
                     interactions=["tooltip", "drilldown", "export", "explain", "methodology"])


def book_segments(c: Ctx) -> ChartSpec:
    r = c.tool("wealth.book_health")
    s = r["data"]["segments"]
    if not s:
        raise PolicyDenied("no advisor book for this identity", code="NO-BOOK")
    c.client_choices = r["data"]["retirement_goal_clients"]
    return ChartSpec(chart_id="book_segments", chart_type="donut", title="Your book by segment", subtitle="Client value at the latest month-end",
                     categories=[x["segment"] for x in s], series=[Series(name="Client value", values=[x["value"] for x in s], unit="CAD")], unit="CAD",
                     metrics=_metrics(r["lineage"]), lineage=_lin(r["lineage"], ["wealth.book_health"]))


def product_fee_return(c: Ctx) -> ChartSpec:
    r = c.tool("investment.fund_list")
    funds = r["data"]["funds"]
    return ChartSpec(chart_id="product_fee_return", chart_type="scatter", title="Fee versus 12-month return", subtitle="Each point is a fund · general information, not a recommendation",
                     nodes=[Node(id=f["id"], name=f["name"], x=f["fee_bps"], y=f["return_12m"], size=f["aum"], group=f["asset_class"],
                                 meta={"vehicle": f["vehicle"], "benchmark_12m": f["benchmark_12m"]}) for f in funds],
                     x_axis={"label": "Management fee", "unit": "bps"}, y_axis={"label": "12-month return", "unit": "%"}, unit="%",
                     metrics=_metrics(r.get("lineage")), lineage=_lin(r.get("lineage"), ["investment.fund_list"]),
                     drilldown={"dimension": "fund", "prompt_template": "Tell me more about {value}."},
                     interactions=["tooltip", "drilldown", "export", "explain", "methodology"])


def fee_by_strategy(c: Ctx) -> ChartSpec:
    r = c.tool("investment.fund_list")
    by: dict[str, list[float]] = {}
    for f in r["data"]["funds"]:
        by.setdefault(f["strategy"], []).append(f["fee_bps"])
    cats = sorted(by)
    return ChartSpec(chart_id="fee_by_strategy", chart_type="grouped_bar", title="Fees by strategy", subtitle="Lowest and average management fee",
                     categories=cats, series=[Series(name="Lowest fee", values=[min(by[k]) for k in cats], unit="bps"),
                                              Series(name="Average fee", values=[round(sum(by[k]) / len(by[k]), 1) for k in cats], unit="bps", role="comparison")],
                     unit="bps", lineage=_lin(r.get("lineage"), ["investment.fund_list"]))


def relative_return(c: Ctx) -> ChartSpec:
    r = c.tool("investment.fund_list")
    funds = sorted(r["data"]["funds"], key=lambda f: f["return_12m"] - f["benchmark_12m"])
    pick = funds[:6] + funds[-6:]
    return ChartSpec(chart_id="relative_return", chart_type="hbar", title="12-month return relative to benchmark", subtitle="Six weakest and six strongest funds (gross of fees)",
                     categories=[f["name"] for f in pick], series=[Series(name="Relative return", values=[round(f["return_12m"] - f["benchmark_12m"], 6) for f in pick], unit="%")],
                     unit="%", lineage=_lin(r.get("lineage"), ["investment.fund_list"]))


def client_allocation(c: Ctx) -> ChartSpec:
    cid = c.q.client_id
    p = c.tool("client.profile", client_id=cid)
    ps = c.tool("client.portfolios", client_id=cid)["portfolios"]
    cats = [f["name"] for f in p["fund_positions"]] + [f"{x['id']} ({x['mandate']})" for x in ps]
    vals = [f["market_value"] for f in p["fund_positions"]] + [x["market_value"] for x in ps]
    return ChartSpec(chart_id="client_allocation", chart_type="donut", title=f"{cid} holdings", subtitle="Fund positions and managed portfolios",
                     categories=cats, series=[Series(name="Market value", values=vals, unit="CAD")], unit="CAD",
                     lineage=Lineage(sources=["crm", "portfolio_management"], methodology="Latest month-end market values.", tools=["client.profile", "client.portfolios"]))


def risk_return(c: Ctx) -> ChartSpec:
    cid = c.q.client_id
    ps = c.tool("client.portfolios", client_id=cid)["portfolios"]
    s = c.tool("client.suitability", client_id=cid)
    return ChartSpec(chart_id="risk_return", chart_type="scatter", title="Risk versus return", subtitle=f"Volatility band for a {s['risk_profile']} profile: {s['volatility_band'] * 100:.0f}%",
                     nodes=[Node(id=x["id"], name=f"{x['id']} {x['mandate']}", x=x["volatility"], y=x["twr_annualized"], size=x["market_value"],
                                 status="warn" if x["volatility"] > s["volatility_band"] else "ok") for x in ps],
                     x_axis={"label": "Volatility", "unit": "%"}, y_axis={"label": "Annualized TWR", "unit": "%"}, unit="%",
                     reference_lines=[{"label": "volatility band", "axis": "x", "value": s["volatility_band"]}],
                     lineage=Lineage(sources=["portfolio_management"], methodology=f"Suitability rules {s['rules_version']}; 24 monthly returns.",
                                     tools=["client.portfolios", "client.suitability"]))


def goal_progress(c: Ctx) -> ChartSpec:
    g = c.tool("client.goals", client_id=c.q.client_id)["goals"]
    return ChartSpec(chart_id="goal_progress", chart_type="hbar", title="Goal funding", subtitle="Funded today and projected at target date",
                     categories=[f"{x['goal_type'].replace('_', ' ')} ({x['target_date'][:4]})" for x in g],
                     series=[Series(name="Funded today", values=[x["funded_pct"] for x in g], unit="%"),
                             Series(name="Projected at target", values=[x["projected_funded_pct"] for x in g], unit="%", role="comparison")],
                     reference_lines=[{"label": "fully funded", "value": 1.0}], unit="%",
                     lineage=Lineage(sources=["crm"], methodology="Goal projections use approved planning return assumptions.", tools=["client.goals"]))


def retirement_projection(c: Ctx) -> ChartSpec:
    r = c.tool("client.retirement", client_id=c.q.client_id)
    path = r["path"]
    return ChartSpec(chart_id="retirement_projection", chart_type="area", title="Retirement projection", subtitle="Nominal and inflation-adjusted balance by year",
                     categories=[f"Y{x['year']}" for x in path],
                     series=[Series(name="Balance (nominal)", values=[_f(x["balance"]) for x in path], unit="CAD"),
                             Series(name="Balance (today's dollars)", values=[_f(x["real_balance"]) for x in path], unit="CAD", role="comparison")],
                     unit="CAD", lineage=Lineage(sources=["crm", "portfolio_management"],
                                                 methodology=f"Deterministic projection; return {r['assumptions']['expected_return'] * 100:.1f}%, inflation "
                                                             f"{r['assumptions']['inflation'] * 100:.1f}%, {r['assumptions']['retirement_years']} retirement years. Not guaranteed.",
                                                 tools=["client.retirement"]))


def cash_flow(c: Ctx) -> ChartSpec:
    r = c.tool("client.retirement", client_id=c.q.client_id)
    m = r["cash_flow_forecast"]["months"]
    return ChartSpec(chart_id="cash_flow", chart_type="stacked_bar", title="12-month cash-flow forecast", categories=[f"M{x['month']}" for x in m],
                     series=[Series(name="Planned goal contributions", values=[_f(x["planned_goal_contributions"]) for x in m], unit="CAD", stack="cf"),
                             Series(name="Expected contributions", values=[_f(x["expected_portfolio_contributions"]) for x in m], unit="CAD", stack="cf"),
                             Series(name="Expected withdrawals", values=[_f(x["expected_withdrawals"]) for x in m], unit="CAD", stack="cf")],
                     unit="CAD", lineage=Lineage(sources=["crm", "portfolio_management"], methodology=r["cash_flow_forecast"]["basis"], tools=["client.retirement"]))


def _firm(c: Ctx) -> dict:
    prof = {k: v for k, v in (c.q.business_profile or {}).items() if v is not None}
    return c.tool("advisory.firm_model", **prof)


def firm_fee_sensitivity(c: Ctx) -> ChartSpec:
    a = _firm(c)
    if a.get("fee_range"):
        rows, prov, sub = a["fee_range"], "illustrative_assumption", "Illustrative: your AUM at a range of planning fee rates"
        cats, vals = [f"{x['fee_bps']} bps" for x in rows], [x["revenue"] for x in rows]
    elif a["sensitivities"]:
        s = a["sensitivities"]
        prov, sub = s["provenance"], f"Your AUM at your fee ({s['fee_bps_used']} bps) and ±10 bps"
        aum = a["profile"]["aum"]
        cats = [f"{s['fee_bps_used'] + d:g} bps" for d in (-10, 0, 10)]
        vals = [round(aum * (s["fee_bps_used"] + d) / 10000, 2) for d in (-10, 0, 10)]
    else:
        raise PolicyDenied("needs AUM", code="NEEDS-DATA")
    return ChartSpec(chart_id="firm_fee_sensitivity", chart_type="bar", title="Annual fee revenue sensitivity", subtitle=sub, categories=cats,
                     series=[Series(name="Annual fee revenue", values=vals, unit="CAD")], unit="CAD", provenance=prov,
                     lineage=Lineage(sources=["figures you provided"], methodology="AUM x fee rate / 10,000. Arithmetic, not a forecast.", synthetic=False,
                                     tools=["advisory.firm_model"]), note=a["disclaimer"])


def firm_market_scenarios(c: Ctx) -> ChartSpec:
    a = _firm(c)
    ms = a["market_scenarios"]
    if not ms:
        raise PolicyDenied("needs AUM", code="NEEDS-DATA")
    return ChartSpec(chart_id="firm_market_scenarios", chart_type="grouped_bar", title="Market moves: AUM and fee revenue",
                     subtitle="Instantaneous market move applied to your stated AUM",
                     categories=[f"{x['market_move'] * 100:+.0f}%" for x in ms],
                     series=[Series(name="AUM", values=[x["aum"] for x in ms], unit="CAD"),
                             Series(name="Annual fee revenue", values=[x["annual_fee_revenue"] for x in ms], unit="CAD", role="comparison")],
                     unit="CAD", provenance=ms[0]["provenance"],
                     lineage=Lineage(sources=["figures you provided"], methodology="AUM x (1 + move); revenue at the fee shown in the assumptions.", synthetic=False,
                                     tools=["advisory.firm_model"]))


def firm_data_readiness(c: Ctx) -> ChartSpec:
    a = _firm(c)
    return ChartSpec(chart_id="firm_data_readiness", chart_type="scorecard", title="Dashboard readiness", subtitle="What can be shown from the data you have shared",
                     nodes=[Node(id=f"m{i}", name=x["module"], value=100 if x["status"] == "available" else 0, status="ok" if x["status"] == "available" else "neutral",
                                 meta={"status": x["status"], "needs": ", ".join(x["needs"])}) for i, x in enumerate(a["data_readiness"])],
                     unit="%", provenance="user_supplied",
                     lineage=Lineage(sources=["figures you provided"], methodology="Modules light up as you share or connect the data they need.", synthetic=False,
                                     tools=["advisory.firm_model"]))


BUILDERS: dict[str, Callable[[Ctx], ChartSpec]] = {f.__name__: f for f in [
    aum_trend, aum_waterfall, net_flows, revenue_expenses, margin_trend, revenue_yield, revenue_bridge, product_profitability, product_revenue,
    budget_variance, initiative_scorecard, risk_heatmap, concentration_top_issuers, sector_exposure, geographic_exposure, correlation, scenario_paths,
    scenario_by_asset_class, portfolio_impacts, scenario_comparison, sensitivity_tornado, advisor_productivity_scatter, advisor_book_distribution,
    retention_trend, retention_by_segment, book_trend, book_signals, book_segments, product_fee_return, fee_by_strategy, relative_return,
    client_allocation, risk_return, goal_progress, retirement_projection, cash_flow, firm_fee_sensitivity, firm_market_scenarios, firm_data_readiness]}
# agent chart hints that map onto builders
ALIASES = {"concentration": "concentration_top_issuers", "sector_treemap": "sector_exposure", "fee_comparison": "fee_by_strategy",
           "allocation": "client_allocation", "actual_vs_budget": "budget_variance", "benchmarks": "relative_return", "timeline": None,
           "drawdown": None, "performance": None, "goal_progress": "goal_progress", "firm_kpis": None}
CLIENT_CHARTS = {"client_allocation", "risk_return", "goal_progress", "retirement_projection", "cash_flow"}
# tools each chart reads; used to compose dashboards from data the identity can use (the gateway still enforces every call)
CHART_TOOLS = {"aum_trend": ["finance.aum_trend"], "aum_waterfall": ["finance.aum_waterfall"], "net_flows": ["finance.net_flows_by"],
               "revenue_expenses": ["finance.revenue_expenses"], "margin_trend": ["finance.margin_trend"], "revenue_yield": ["finance.margin_trend"],
               "revenue_bridge": ["finance.revenue_attribution"], "product_profitability": ["finance.product_profitability"],
               "product_revenue": ["finance.product_profitability"], "budget_variance": ["finance.actual_vs_budget"], "initiative_scorecard": ["strategy.initiatives"],
               "risk_heatmap": ["risk.heatmap"], "concentration_top_issuers": ["investment.enterprise_concentration"],
               "sector_exposure": ["investment.enterprise_concentration"], "geographic_exposure": ["investment.geographic_exposure"],
               "correlation": ["investment.correlation"], "scenario_paths": ["scenario.run"], "scenario_by_asset_class": ["scenario.run"],
               "portfolio_impacts": ["scenario.run"], "scenario_comparison": ["scenario.compare"], "sensitivity_tornado": ["scenario.sensitivity"],
               "advisor_productivity_scatter": ["wealth.advisor_productivity"], "advisor_book_distribution": ["wealth.advisor_productivity"],
               "retention_trend": ["finance.retention"], "retention_by_segment": ["finance.retention"], "book_trend": ["wealth.book_health"],
               "book_signals": ["wealth.book_health"], "book_segments": ["wealth.book_health"], "product_fee_return": ["investment.fund_list"],
               "fee_by_strategy": ["investment.fund_list"], "relative_return": ["investment.fund_list"], "client_allocation": ["client.profile", "client.portfolios"],
               "risk_return": ["client.portfolios", "client.suitability"], "goal_progress": ["client.goals"], "retirement_projection": ["client.retirement"],
               "cash_flow": ["client.retirement"], "firm_fee_sensitivity": ["advisory.firm_model"], "firm_market_scenarios": ["advisory.firm_model"],
               "firm_data_readiness": ["advisory.firm_model"]}


def chart_relevant(chart_id: str, perms: set[str], has_book: bool) -> bool:
    """Compose the dashboard from data this identity can use at all; record-level checks still happen in the gateway."""
    from harness.tools import TOOLS
    if chart_id.startswith("book_") and not has_book:
        return False
    return all(TOOLS.tools[t].permission in perms for t in CHART_TOOLS.get(chart_id, []))


# ------------------------------------------------------------------------------------------------ KPI sets
def _delta_pct(a, b):
    return round(a / b - 1, 4) if a is not None and b else None


def kpis_exec(c: Ctx) -> list[KPI]:
    r = c.tool("finance.kpis", months=c.q.months)
    k, p = r["data"], r["data"]["prior_period"] or {}
    trend = c.tool("finance.margin_trend", months=24)["data"]
    aum_t = c.tool("finance.aum_trend", months=24, group_by="asset_class")["data"]["total"]
    n = k["period"]["months"]
    out = [KPI(id="aum", label="Total AUM", value=k["total_aum"], unit="CAD", delta=k["aum_growth"], delta_unit="%", delta_label=f"over {n} months",
               trend=aum_t[-n:], status="good" if k["aum_growth"] > 0 else "warn", metric_id="aum.total"),
           KPI(id="net_flows", label="Net client flows", value=k["net_flows"], unit="CAD", delta_label=f"{n} months", metric_id="flows.net",
               status="good" if k["net_flows"] > 0 else "warn"),
           KPI(id="revenue", label="Management fee revenue", value=k["management_fee_revenue"], unit="CAD", delta=_delta_pct(k["management_fee_revenue"], p.get("revenue")),
               delta_unit="%", delta_label="vs prior period", metric_id="revenue.management_fees", status="good"),
           KPI(id="opex", label="Operating expenses", value=k["operating_expenses"], unit="CAD", delta=_delta_pct(k["operating_expenses"], p.get("operating_expenses")),
               delta_unit="%", delta_label="vs prior period", metric_id="expenses.operating",
               status="warn" if (_delta_pct(k["operating_expenses"], p.get("operating_expenses")) or 0) > (_delta_pct(k["management_fee_revenue"], p.get("revenue")) or 0) else "neutral"),
           KPI(id="margin", label="Operating margin", value=k["operating_margin"], unit="%",
               delta=round(k["operating_margin"] - p["operating_margin"], 4) if p.get("operating_margin") is not None else None, delta_unit="pp",
               delta_label="vs prior period", trend=trend["operating_margin"][-n:], metric_id="margin.operating",
               status="warn" if p.get("operating_margin") is not None and k["operating_margin"] < p["operating_margin"] else "good"),
           KPI(id="yield", label="Revenue yield", value=k["revenue_yield_bps"], unit="bps",
               delta=round(k["revenue_yield_bps"] - p["revenue_yield_bps"], 2) if p.get("revenue_yield_bps") is not None else None, delta_unit="bps",
               delta_label="vs prior period", trend=trend["revenue_yield_bps"][-n:], metric_id="revenue.yield_bps",
               status="warn" if p.get("revenue_yield_bps") is not None and k["revenue_yield_bps"] < p["revenue_yield_bps"] else "neutral")]
    if k.get("client_retention") is not None:
        out.append(KPI(id="retention", label="Client retention", value=k["client_retention"], unit="%", delta_label="12 months", metric_id="clients.retention"))
    return out


def kpis_advisors(c: Ctx) -> list[KPI]:
    s = c.tool("wealth.advisor_productivity")["data"]["summary"]
    return [KPI(id="advisors", label="Advisors", value=s["advisors"], unit="count"),
            KPI(id="median_book", label="Median book AUM", value=s["median_book_aum"], unit="CAD", metric_id="advisor.book_aum"),
            KPI(id="median_clients", label="Median active clients", value=s["median_active_clients"], unit="count", metric_id="advisor.active_clients"),
            KPI(id="dispersion", label="Top vs bottom quartile book", value=s["top_to_bottom_quartile_ratio"], unit="x", status="warn"),
            KPI(id="kyc_stale", label="Clients with stale KYC", value=s["kyc_stale_total"], unit="count", status="warn" if s["kyc_stale_total"] else "good")]


def kpis_retention(c: Ctx) -> list[KPI]:
    out: list[KPI] = []
    try:
        d = c.tool("finance.retention")["data"]
        out += [KPI(id="retention", label="Client retention (12m)", value=d["retention_12m"], unit="%",
                    delta=round(d["retention_12m"] - d["retention_prior_12m"], 4) if d["retention_prior_12m"] is not None else None, delta_unit="pp",
                    delta_label="vs prior 12m", metric_id="clients.retention",
                    status="warn" if d["retention_prior_12m"] is not None and d["retention_12m"] < d["retention_prior_12m"] else "good"),
                KPI(id="closures", label="Client closures (12m)", value=d["closed_12m"], unit="count")]
    except PolicyDenied:
        pass
    if c.ctx.principal.advisor_id:
        try:
            b = c.tool("wealth.book_health")["data"]
            out += [KPI(id="book_clients", label="Active clients in your book", value=b["active_clients"], unit="count"),
                    KPI(id="book_value", label="Book value", value=b["book_value"], unit="CAD", metric_id="advisor.book_aum"),
                    KPI(id="book_retention", label="Your 12-month retention", value=b["retention_12m"], unit="%", metric_id="clients.retention"),
                    KPI(id="at_risk", label="Clients with review signals", value=b["at_risk_total"], unit="count", status="warn" if b["at_risk_total"] else "good",
                        metric_id="clients.at_risk_signals")]
        except PolicyDenied:
            pass
    return out


def kpis_concentration(c: Ctx) -> list[KPI]:
    d = c.tool("investment.enterprise_concentration")["data"]
    t = d["top_holdings"][0]
    return [KPI(id="top_issuer", label=f"Largest issuer: {t['name']}", value=t["weight"], unit="%", metric_id="risk.single_issuer",
                status="warn" if t["weight"] > d["limit"] / 2 else "neutral"),
            KPI(id="breaches", label="Portfolios over single-issuer limit", value=d["portfolios_breaching_single_issuer_limit"], unit="count",
                status="crit" if d["portfolios_breaching_single_issuer_limit"] else "good"),
            KPI(id="top10", label="Top-10 issuer weight", value=d["top10_weight"], unit="%"),
            KPI(id="eff_n", label="Effective number of issuers", value=d["effective_n"], unit="count", metric_id="risk.hhi")]


def kpis_scenario(c: Ctx) -> list[KPI]:
    r = c.tool("scenario.run", **_scenario_args(c))
    res, pi = r["results"], r["portfolio_impacts"]
    return [KPI(id="aum_change", label=f"AUM change ({r['scenario'].replace('_', ' ')})", value=res["aum_change_pct"], unit="%",
                status="crit" if res["aum_change_pct"] < -0.1 else "warn" if res["aum_change_pct"] < 0 else "good"),
            KPI(id="aum_end", label="AUM at horizon", value=_f(res["aum_end"]), unit="CAD", delta_label=f"{r['horizon_months']} months"),
            KPI(id="scn_revenue", label="Revenue over horizon", value=_f(res["revenue"]), unit="CAD"),
            KPI(id="scn_margin", label="Operating margin under scenario", value=res["operating_margin"], unit="%",
                status="warn" if (res["operating_margin"] or 0) < 0.2 else "neutral"),
            KPI(id="port_impact", label="Immediate portfolio impact", value=_f(pi["total_impact"]), unit="CAD", status="warn")]


def kpis_client(c: Ctx) -> list[KPI]:
    cid = c.q.client_id
    p = c.tool("client.profile", client_id=cid)
    ps = c.tool("client.portfolios", client_id=cid)["portfolios"]
    s = c.tool("client.suitability", client_id=cid)
    value = sum(f["market_value"] for f in p["fund_positions"]) + sum(x["market_value"] for x in ps)
    out = [KPI(id="client_value", label="Client holdings", value=round(value, 2), unit="CAD"),
           KPI(id="portfolios", label="Managed portfolios", value=len(ps), unit="count"),
           KPI(id="findings", label="Suitability screen findings", value=len(s["findings"]), unit="count", status="warn" if s["findings"] else "good",
               note=f"rules {s['rules_version']}; review prompts, not determinations")]
    try:
        r = c.tool("client.retirement", client_id=cid)
        out.append(KPI(id="ret_balance", label="Projected balance at 65", value=_f(r["balance_at_retirement"]), unit="CAD", note="deterministic projection"))
    except PolicyDenied:
        pass
    return out


def kpis_products(c: Ctx) -> list[KPI]:
    f = c.tool("investment.fund_list")["data"]["funds"]
    return [KPI(id="funds", label="Funds compared", value=len(f), unit="count"),
            KPI(id="min_fee", label="Lowest management fee", value=min(x["fee_bps"] for x in f), unit="bps"),
            KPI(id="beat", label="Funds ahead of benchmark (12m)", value=sum(x["return_12m"] > x["benchmark_12m"] for x in f), unit="count")]


def kpis_firm(c: Ctx) -> list[KPI]:
    a = _firm(c)
    units = {"CAD": "CAD", "ratio": "%", "bps": "bps", "count": "count"}
    return [KPI(id=m["key"], label=m["label"], value=m["value"], unit=units.get(m["unit"], "count"), provenance=m["provenance"], note=m["basis"])
            for m in a["metrics"]]


KPI_SETS = {"exec": kpis_exec, "advisors": kpis_advisors, "retention": kpis_retention, "concentration": kpis_concentration, "scenario": kpis_scenario,
            "client": kpis_client, "products": kpis_products, "firm": kpis_firm}


# ------------------------------------------------------------------------------------------------ the agent
@template("viz")
def _t_viz(f):
    s = f"Prepared {f['n']} visualization(s) from governed data"
    if f["withheld"]:
        s += f"; {f['withheld']} withheld because your role is not authorized for the underlying data"
    return s + "."


@REGISTRY.register(spec("visualization_agent", "workspace", "enterprise_supervisor",
                        "Composes the dashboard for a question from allowlisted chart builders; data is fetched through the tool gateway as the user.",
                        VIZ_ROLES, VIZ_TOOLS, VizQ, max_iterations=24, timeout_s=25, max_retries=0))
def visualization_agent(ctx, q: VizQ):
    c = Ctx(ctx, q)
    charts, withheld, kpis, notes = [], [], [], []
    if q.kpis in KPI_SETS:
        try:
            kpis = [k.model_dump() for k in KPI_SETS[q.kpis](c)]
        except HarnessError as e:
            notes.append(f"KPIs withheld: {e.code}")
    for cid in q.charts:
        b = BUILDERS.get(cid)
        if b is None or (cid in CLIENT_CHARTS and not q.client_id):
            continue
        try:
            charts.append(b(c).model_dump())
        except PolicyDenied as e:
            withheld.append({"chart_id": cid, "code": e.code})
        except HarnessError as e:
            withheld.append({"chart_id": cid, "code": e.failure_class})
    facts = {"n": len(charts), "withheld": len(withheld)}
    gen = ctx_harness().narrate(ctx, "viz", facts, classification="public")
    return AgentOutput(agent="visualization_agent", narrative=gen.text, facts={**facts, "charts": charts, "kpis": kpis, "withheld_charts": withheld,
                                                                                "notes": notes, "tools": c.tools, "client_choices": c.client_choices})


def tables_for(intent: str, facts_by_agent: dict[str, dict]) -> list[Table]:
    out: list[Table] = []
    ret = facts_by_agent.get("client_retention_agent", {})
    if ret.get("at_risk_clients"):
        out.append(Table(table_id="book_at_risk", title="Clients with review signals (your book)",
                         columns=["Client", "Segment", "Signals", "Client value (CAD)", "KYC age (days)"],
                         rows=[[r["client_id"], r["segment"], ", ".join(s.replace("_", " ") for s in r["signals"]), r["client_value"], r["kyc_age_days"]]
                               for r in ret["at_risk_clients"][:10]]))
    ap = facts_by_agent.get("advisor_productivity_agent", {})
    if ap.get("advisor_rows"):
        rows = ap["advisor_rows"]
        out.append(Table(table_id="advisor_quartiles", title="Advisor productivity (top and bottom five by book AUM)",
                         columns=["Advisor", "Active clients", "Book AUM (CAD)", "Interactions / client (12m)", "Retention (12m)", "Stale KYC"],
                         rows=[[a["advisor"], a["active_clients"], a["book_aum"], a["interactions_per_client"], a["retention_12m"], a["kyc_stale"]]
                               for a in rows[:5] + rows[-5:]]))
    sc = facts_by_agent.get("scenario_agent", {})
    if sc.get("most_impacted"):
        out.append(Table(table_id="most_impacted", title="Most impacted portfolios", columns=["Portfolio", "Mandate", "Market value (CAD)", "Impact"],
                         rows=[[x["portfolio_id"], x["mandate"], float(x["market_value"]), x["impact_pct"]] for x in sc["most_impacted"][:8]]))
    meet = facts_by_agent.get("client_meeting_agent", {})
    if meet.get("agenda"):
        out.append(Table(table_id="meeting_agenda", title="Meeting agenda", columns=["#", "Item"], rows=[[i + 1, a] for i, a in enumerate(meet["agenda"])]))
    wa = facts_by_agent.get("wealth_advisor_agent", {})
    if wa.get("findings"):
        out.append(Table(table_id="suitability_findings", title="Suitability screen findings (review prompts, not determinations)",
                         columns=["Rule", "Severity", "Portfolio", "Detail"],
                         rows=[[f["rule"], f["severity"], f.get("portfolio_id", "—"), ", ".join(f"{k}={v}" for k, v in f["detail"].items())] for f in wa["findings"]]))
    fd = facts_by_agent.get("firm_diagnostic_agent", {})
    if fd.get("assessment", {}).get("integrations"):
        out.append(Table(table_id="integrations", title="Data integrations that would unlock verified analytics", columns=["System", "Data", "Enables"],
                         rows=[[x["system"], x["data"], x["enables"]] for x in fd["assessment"]["integrations"]], provenance="user_supplied"))
    return out
