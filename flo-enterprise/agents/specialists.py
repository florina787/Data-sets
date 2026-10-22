"""The FLO specialist agents. Each registers a full contract (AgentSpec) with the harness registry.

Agents are deterministic orchestrations of governed tools; narratives are rendered by the model adapter from tool facts
and must pass numeric grounding. Optional tools that the principal may not use are skipped with a visible warning
(the denial itself is enforced and audited by the gateway)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

import agents.tools  # noqa: F401  (registers tools)
from harness.errors import PolicyDenied
from harness.models import template
from harness.registry import REGISTRY, AgentSpec

EXEC = frozenset({"executive", "finance"})
INV = frozenset({"cio", "investment_analyst"})
ADV = frozenset({"wealth_advisor"})
COMP = frozenset({"compliance_officer"})
OPS = frozenset({"ai_admin"})
RISK = frozenset({"risk_officer"})
ALL = frozenset({"executive", "finance", "cio", "investment_analyst", "wealth_advisor", "external_advisor", "compliance_officer",
                 "privacy_officer", "ai_admin", "risk_officer", "prospect"})


# ------------------------------------------------------------------ schemas
class Question(BaseModel):
    model_config = {"extra": "forbid"}
    question: str = Field("", max_length=4000)
    months: int = Field(12, ge=1, le=24)
    language: str = Field("en", pattern=r"^(en|fr|es|hi|ta|ko)$")


class PortfolioQ(Question):
    portfolio_id: str | None = Field(None, pattern=r"^PF-\d{4}$")


class ClientQ(Question):
    client_id: str = Field(pattern=r"^C-\d{5}$")
    draft_language: str | None = Field(None, pattern=r"^(en|fr|es|hi|ta|ko)$")


class ScenarioQ(Question):
    preset: Literal["base", "bull", "bear", "severe_stress"] = "base"
    equity_shock: float | None = Field(None, ge=-0.8, le=0.8)
    rate_shock_bps: float | None = Field(None, ge=-500, le=500)


class AgentOutput(BaseModel):
    agent: str
    narrative: str
    facts: dict
    citations: list[dict] = []
    warnings: list[str] = []
    approval: dict | None = None
    charts: list[str] = []


def _out(ctx, name, template_id, facts, charts=(), warnings=(), approval=None, cite=True) -> AgentOutput:
    gen = ctx_harness().narrate(ctx, template_id, facts, classification=getattr(ctx.agent, "data_classification", "confidential"))
    cites = [c for c in ctx.citations if c.get("agent") == name] if cite else []
    return AgentOutput(agent=name, narrative=gen.text, facts=facts, citations=cites, warnings=list(warnings), approval=approval,
                       charts=list(charts))


def ctx_harness():
    from harness.runtime import get_harness
    return get_harness()


def try_tool(ctx, warnings: list, name: str, **args):
    try:
        return ctx.tool(name, **args)
    except PolicyDenied as e:
        warnings.append(f"{name} skipped: not authorized for your role ({e.code})")
        return None


def pct(x, nd=2):
    return round(x * 100, nd)


def bn(x):
    return round(float(x) / 1e9, 2)


def mn(x):
    return round(float(x) / 1e6, 1)


def spec(name, domain, sup, desc, roles, tools, inp, **kw):
    return AgentSpec(name=name, version=kw.pop("version", "1.2.0"), owner=kw.pop("owner", f"{domain.title()} AI Product Owner (synthetic)"),
                     domain=domain, supervisor=sup, description=desc, allowed_roles=roles, allowed_tools=tuple(tools),
                     input_model=inp, output_model=AgentOutput, **kw)


# ------------------------------------------------------------------ 1 AUM
@template("aum")
def _t_aum(f):
    rec = "reconciles to the cent" if f["reconciled"] else f"does NOT reconcile ({f['reconciliation_difference']})"
    return (f"Total AUM was CAD {f['aum_bn']}bn at {f['period_end']}, {f['aum_growth_pct']}% higher than CAD {f['aum_open_bn']}bn at the start of the "
            f"{f['months']}-month period. Net client flows contributed CAD {f['net_flows_bn']}bn (subscriptions CAD {f['subs_bn']}bn, redemptions "
            f"CAD {f['reds_bn']}bn) and market movement contributed CAD {f['market_bn']}bn. The AUM roll-forward {rec}. "
            f"By vehicle, net flows were led by {f['top_flow_group']} (CAD {f['top_flow_bn']}bn) while {f['bottom_flow_group']} saw CAD {f['bottom_flow_bn']}bn.")


@REGISTRY.register(spec("aum_agent", "executive", "executive_supervisor", "Explains AUM level, growth and drivers (flows vs market).",
                        EXEC | INV, ["finance.kpis", "finance.aum_waterfall", "finance.net_flows"], Question))
def aum_agent(ctx, q: Question):
    k = ctx.tool("finance.kpis", months=q.months)["data"]
    w = ctx.tool("finance.aum_waterfall", months=q.months)["data"]
    nf = ctx.tool("finance.net_flows", months=q.months)["data"]["net_by_group"]
    top, bottom = max(nf, key=nf.get), min(nf, key=nf.get)
    facts = {"period_end": k["period"]["end"], "months": k["period"]["months"], "aum_bn": bn(k["total_aum"]), "aum_open_bn": bn(k["aum_open"]),
             "aum_growth_pct": pct(k["aum_growth"]), "net_flows_bn": bn(k["net_flows"]), "subs_bn": bn(k["subscriptions"]),
             "reds_bn": bn(k["redemptions"]), "market_bn": bn(k["market_movement"]), "reconciled": w["reconciliation"]["balanced"],
             "reconciliation_difference": w["reconciliation"]["difference"], "top_flow_group": top, "top_flow_bn": bn(nf[top]),
             "bottom_flow_group": bottom, "bottom_flow_bn": bn(nf[bottom]), "net_flows_by_vehicle": nf}
    return _out(ctx, "aum_agent", "aum", facts, ["aum_trend", "aum_waterfall", "net_flows"])


# ------------------------------------------------------------------ 2 Financial performance
@template("finperf")
def _t_fin(f):
    s = (f"Over the {f['months']} months to {f['period_end']}, management fee revenue was CAD {f['revenue_m']}m and operating expenses "
         f"CAD {f['opex_m']}m, giving an operating margin of {f['margin_pct']}%.")
    if f.get("prior_margin_pct") is not None:
        s += (f" In the prior {f['months']} months the margin was {f['prior_margin_pct']}%: revenue grew {f['revenue_growth_pct']}% while operating "
              f"expenses grew {f['opex_growth_pct']}%, so expenses outpaced revenue by {f['gap_pp']} percentage points.")
    s += f" The largest expense increase was {f['top_expense_line']} (+CAD {f['top_expense_increase_m']}m year over year)."
    return s


@REGISTRY.register(spec("financial_performance_agent", "executive", "executive_supervisor", "Explains profitability, margin and expense drivers.",
                        EXEC, ["finance.kpis", "finance.revenue_expenses", "finance.margin_trend"], Question))
def financial_performance_agent(ctx, q: Question):
    k = ctx.tool("finance.kpis", months=q.months)["data"]
    re_ = ctx.tool("finance.revenue_expenses", months=24)["data"]
    n = q.months
    inc = {}
    for line, vals in re_["expenses"].items():
        if len(vals) >= 2 * n:
            inc[line] = sum(vals[-n:]) - sum(vals[-2 * n:-n])
    top = max(inc, key=inc.get) if inc else "n/a"
    p = k["prior_period"]
    facts = {"months": n, "period_end": k["period"]["end"], "revenue_m": mn(k["management_fee_revenue"]), "opex_m": mn(k["operating_expenses"]),
             "margin_pct": pct(k["operating_margin"]), "top_expense_line": top.replace("expense_", "").replace("_", " "),
             "top_expense_increase_m": mn(inc.get(top, 0)), "expense_increases": {k2: round(v, 2) for k2, v in inc.items()}}
    if p:
        rg = k["management_fee_revenue"] / p["revenue"] - 1
        og = k["operating_expenses"] / p["operating_expenses"] - 1
        facts.update(prior_margin_pct=pct(p["operating_margin"]), revenue_growth_pct=pct(rg), opex_growth_pct=pct(og),
                     gap_pp=round(pct(og) - pct(rg), 2), prior_revenue_m=mn(p["revenue"]), prior_opex_m=mn(p["operating_expenses"]))
    return _out(ctx, "financial_performance_agent", "finperf", facts, ["revenue_expenses", "margin_trend"])


# ------------------------------------------------------------------ 3 Revenue
@template("revenue")
def _t_rev(f):
    return (f"Annualized management fee revenue changed by CAD {f['change_m']}m between {f['p0']} and {f['p1']}. Higher average AUM "
            f"(volume effect) added CAD {f['volume_m']}m, while a lower revenue yield (rate effect) subtracted CAD {f['rate_abs_m']}m: "
            f"revenue yield fell from {f['y0']} bps to {f['y1']} bps. Within the rate effect, product mix shift toward lower-fee "
            f"vehicles accounted for CAD {f['mix_m']}m and fee changes for CAD {f['fee_m']}m. {f['mix_line']}")


@REGISTRY.register(spec("revenue_agent", "executive", "executive_supervisor", "Attributes revenue change to volume, mix and fee effects.",
                        EXEC, ["finance.revenue_attribution"], Question))
def revenue_agent(ctx, q: Question):
    r = ctx.tool("finance.revenue_attribution", months=q.months)["data"]
    mix = r["mix_by_vehicle"]
    growth = max(mix, key=lambda x: x["aum_share_1"] - x["aum_share_0"])
    facts = {"p0": f"{r['period_0'][0]}..{r['period_0'][1]}", "p1": f"{r['period_1'][0]}..{r['period_1'][1]}",
             "change_m": mn(r["change"]), "volume_m": mn(r["volume_effect"]), "rate_m": mn(r["rate_effect"]),
             "rate_abs_m": abs(mn(r["rate_effect"])), "mix_m": mn(r["mix_effect"]), "fee_m": mn(r["fee_change_effect"]),
             "y0": float(r["yield_bps_0"]), "y1": float(r["yield_bps_1"]), "mix_by_vehicle": mix,
             "fastest_share_gain": growth["vehicle"], "share0_pct": pct(growth["aum_share_0"]), "share1_pct": pct(growth["aum_share_1"]),
             "yield_of_fastest": growth["yield_bps_1"]}
    facts["mix_line"] = (f"The {growth['vehicle']} share of AUM rose from {facts['share0_pct']}% to {facts['share1_pct']}% at a revenue yield of "
                         f"about {growth['yield_bps_1']} bps.")
    return _out(ctx, "revenue_agent", "revenue", facts, ["margin_trend", "product_profitability"])


# ------------------------------------------------------------------ 4 Portfolio
@template("portfolio_one")
def _t_p1(f):
    s = (f"Portfolio {f['id']} ({f['mandate']}) is valued at CAD {f['mv']} with a 24-month time-weighted return of {f['twr_ann_pct']}% per year "
         f"versus {f['bench_ann_pct']}% for its benchmark, volatility {f['vol_pct']}%, Sharpe {f['sharpe']} and maximum drawdown {f['mdd_pct']}%. "
         f"The largest holding is {f['top_name']} at {f['top_pct']}% (limit {f['limit_pct']}%); effective number of holdings {f['eff_n']}; "
         f"allocation drift from target {f['drift_pct']}%.")
    if f["breaches"]:
        s += f" {f['breaches']} holding(s) exceed the single-issuer limit."
    return s


@template("portfolio_enterprise")
def _t_pe(f):
    return (f"Across {f['portfolio_count']} managed portfolios (CAD {f['total_bn']}bn), the largest issuer exposure is {f['top_name']} at "
            f"{f['top_pct']}% of portfolio assets, held in {f['top_holders']} portfolios. The ten largest issuers represent {f['top10_pct']}% "
            f"and the effective number of issuers is {f['eff_n']}. {f['breaching']} portfolios currently exceed the {f['limit_pct']}% single-issuer "
            f"limit. The largest sector exposure is {f['top_sector']} at {f['top_sector_pct']}%.")


@REGISTRY.register(spec("portfolio_agent", "investment", "investment_supervisor", "Portfolio and enterprise holdings analytics (performance, concentration, drift).",
                        INV | ADV | EXEC | RISK, ["investment.portfolio_detail", "investment.enterprise_concentration"], PortfolioQ))
def portfolio_agent(ctx, q: PortfolioQ):
    if q.portfolio_id:
        d = ctx.tool("investment.portfolio_detail", portfolio_id=q.portfolio_id)["data"]
        mtr, h = d["metrics"], d["holdings"][0]
        facts = {"id": q.portfolio_id, "mandate": mtr["mandate"], "mv": f"{mtr['market_value']:,.2f}", "market_value": mtr["market_value"],
                 "twr_ann_pct": pct(mtr["twr_annualized"]), "bench_ann_pct": pct(mtr["twr_annualized"] - mtr["excess_annualized"]),
                 "vol_pct": pct(mtr["volatility"]), "sharpe": round(mtr["sharpe"], 2), "mdd_pct": pct(mtr["max_drawdown"]),
                 "top_name": h["name"], "top_pct": pct(h["current_weight"]), "limit_pct": pct(d["concentration"]["limit"]),
                 "eff_n": mtr["effective_n"], "drift_pct": pct(mtr["drift"]), "breaches": len(d["concentration"]["breaches"]),
                 "mwr_ann_pct": pct(d["mwr_annualized"]) if d["mwr_annualized"] is not None else None, "window_months": 24}
        return _out(ctx, "portfolio_agent", "portfolio_one", facts, ["performance", "drawdown", "allocation"])
    c = ctx.tool("investment.enterprise_concentration")["data"]
    t, sct = c["top_holdings"][0], c["sector_exposure"][0]
    facts = {"portfolio_count": c["portfolio_count"], "total_bn": bn(c["total_portfolio_aum"]), "top_name": t["name"], "top_pct": pct(t["weight"]),
             "top_holders": t["portfolios_holding"], "top10_pct": pct(c["top10_weight"]), "eff_n": c["effective_n"],
             "breaching": c["portfolios_breaching_single_issuer_limit"], "limit_pct": pct(c["limit"]), "top_sector": sct["sector"],
             "top_sector_pct": pct(sct["weight"]), "top_holdings": c["top_holdings"][:5]}
    return _out(ctx, "portfolio_agent", "portfolio_enterprise", facts, ["concentration", "sector_treemap"])


# ------------------------------------------------------------------ 5 Benchmark
@template("benchmark")
def _t_bm(f):
    return (f"Over the last 12 months, {f['beat']} of {f['n']} funds outperformed their benchmark (gross of fees). The strongest relative result was "
            f"{f['best']} ({f['best_rel_pct']} percentage points) and the weakest {f['worst']} ({f['worst_rel_pct']} percentage points). "
            f"The best-performing benchmark was {f['best_bm']} at {f['best_bm_pct']}% over 12 months.")


@REGISTRY.register(spec("benchmark_agent", "investment", "investment_supervisor", "Compares fund and portfolio returns with benchmarks.",
                        INV | EXEC, ["investment.fund_list", "market.intelligence"], Question, timeout_s=12))
def benchmark_agent(ctx, q: Question):
    funds = ctx.tool("investment.fund_list")["data"]["funds"]
    rel = sorted(funds, key=lambda f: f["return_12m"] - f["benchmark_12m"])
    w: list = []
    mi = try_tool(ctx, w, "market.intelligence")
    bms = sorted(mi["data"]["benchmarks"], key=lambda b: -b["twelve_month"]) if mi else []
    facts = {"n": len(funds), "beat": sum(f["return_12m"] > f["benchmark_12m"] for f in funds), "best": rel[-1]["name"],
             "best_rel_pct": pct(rel[-1]["return_12m"] - rel[-1]["benchmark_12m"]), "worst": rel[0]["name"],
             "worst_rel_pct": pct(rel[0]["return_12m"] - rel[0]["benchmark_12m"]),
             "best_bm": bms[0]["name"] if bms else "n/a", "best_bm_pct": pct(bms[0]["twelve_month"]) if bms else 0, "window": 12}
    return _out(ctx, "benchmark_agent", "benchmark", facts, ["relative_return"], w)


# ------------------------------------------------------------------ 6 Investment research (model-planned; retrieved text is evidence only)
@template("research")
def _t_research(f):
    if not f["sources"]:
        return "No authorized research documents matched the question. No answer is given without evidence."
    lines = " ".join(f"[{i + 1}] {s['title']} - {s['section']}: {s['excerpt']}" for i, s in enumerate(f["sources"]))
    return f"Relevant authorized research ({f['count']} sources, cited): {lines}"


def _plan_and_search(ctx, name, q, doc_types, warnings):
    default = [{"tool": "docs.search", "args": {"query": q.question or "market outlook", "k": 4, "doc_types": doc_types}}]
    plan = ctx.model.plan(q.question, list(ctx.agent.allowed_tools), default)
    hits = []
    for step in plan[:ctx.agent.max_iterations]:
        try:
            r = ctx.tool(step["tool"], **step.get("args", {}))
            if step["tool"] == "docs.search":
                hits += r["results"]
        except PolicyDenied as e:
            warnings.append(f"blocked tool call '{step['tool']}' ({e.code}) - enforced by the tool gateway")
    return hits


def _sources(hits):
    return [{"document_id": h["document_id"], "title": h["title"], "section": h["section"], "version": h["version"],
             "excerpt": h["text"][:220].replace("\n", " ")} for h in hits]


@REGISTRY.register(spec("investment_research_agent", "investment", "investment_supervisor", "Answers research questions from authorized documents with citations.",
                        INV | EXEC | ADV, ["docs.search"], Question, eval_requirements=("citations",)))
def investment_research_agent(ctx, q: Question):
    w: list = []
    hits = _plan_and_search(ctx, "investment_research_agent", q, ["research", "strategy_memo", "decision_memo", "board_report"], w)
    facts = {"count": len(hits), "sources": _sources(hits), "refs": list(range(1, len(hits) + 1))}
    return _out(ctx, "investment_research_agent", "research", facts, [], w)


# ------------------------------------------------------------------ 7 Market intelligence
@template("market")
def _t_mkt(f):
    return (f"In the latest month ({f['as_of']}) the best-performing benchmark was {f['best']} ({f['best_pct']}%) and the weakest {f['worst']} "
            f"({f['worst_pct']}%). Over 12 months, {f['best12']} returned {f['best12_pct']}%. The strongest sector last month was {f['sec_best']} "
            f"({f['sec_best_pct']}%) and the weakest {f['sec_worst']} ({f['sec_worst_pct']}%). Source: synthetic market data provider (mock adapter).")


@REGISTRY.register(spec("market_intelligence_agent", "investment", "investment_supervisor", "Summarizes market moves from the market data provider.",
                        INV | EXEC | ADV | frozenset({"external_advisor"}), ["market.intelligence"], Question, timeout_s=10))
def market_intelligence_agent(ctx, q: Question):
    d = ctx.tool("market.intelligence")["data"]
    b = sorted(d["benchmarks"], key=lambda x: x["last_month"])
    b12 = max(d["benchmarks"], key=lambda x: x["twelve_month"])
    sec = sorted(d["sector_last_month"].items(), key=lambda kv: kv[1])
    facts = {"as_of": d["months"][-1], "best": b[-1]["name"], "best_pct": pct(b[-1]["last_month"]), "worst": b[0]["name"],
             "worst_pct": pct(b[0]["last_month"]), "best12": b12["name"], "best12_pct": pct(b12["twelve_month"]),
             "sec_best": sec[-1][0], "sec_best_pct": pct(sec[-1][1]), "sec_worst": sec[0][0], "sec_worst_pct": pct(sec[0][1]),
             "window": 12}
    return _out(ctx, "market_intelligence_agent", "market", facts, ["benchmarks"])


# ------------------------------------------------------------------ 8 Risk
@template("risk")
def _t_risk(f):
    s = (f"The enterprise risk register holds {f['n_risks']} risks; the highest-rated is '{f['top_risk']}' (score {f['top_score']} of 25). "
         f"{f['high']} risks score 12 or more.")
    if f.get("top_issuer"):
        s += (f" Concentration: {f['top_issuer']} represents {f['top_issuer_pct']}% of managed portfolio assets and {f['breaching']} portfolios exceed "
              f"the single-issuer limit.")
    if f.get("max_corr_pair"):
        s += f" The most correlated sector pair is {f['max_corr_pair']} ({f['max_corr']})."
    return s


@REGISTRY.register(spec("risk_agent", "risk", "risk_compliance_supervisor", "Enterprise, concentration and correlation risk.",
                        INV | EXEC | RISK, ["risk.heatmap", "investment.enterprise_concentration", "investment.correlation"], Question))
def risk_agent(ctx, q: Question):
    w: list = []
    h = ctx.tool("risk.heatmap")["data"]["items"]
    facts = {"n_risks": len(h), "top_risk": h[0]["title"], "top_score": h[0]["score"], "high": sum(1 for x in h if x["score"] >= 12),
             "score_max": 25, "high_threshold": 12}
    c = try_tool(ctx, w, "investment.enterprise_concentration")
    if c:
        t = c["data"]["top_holdings"][0]
        facts.update(top_issuer=t["name"], top_issuer_pct=pct(t["weight"]), breaching=c["data"]["portfolios_breaching_single_issuer_limit"])
    corr = try_tool(ctx, w, "investment.correlation")
    if corr:
        lab, mtx = corr["data"]["labels"], corr["data"]["matrix"]
        best = max(((i, j) for i in range(len(lab)) for j in range(i + 1, len(lab))), key=lambda ij: mtx[ij[0]][ij[1]])
        facts.update(max_corr_pair=f"{lab[best[0]]} / {lab[best[1]]}", max_corr=mtx[best[0]][best[1]])
    return _out(ctx, "risk_agent", "risk", facts, ["risk_heatmap", "correlation"], w)


# ------------------------------------------------------------------ 9 Scenario
@template("scenario")
def _t_scn(f):
    return (f"Under the '{f['scenario']}' scenario ({f['assumption_line']}), AUM would move from CAD {f['aum0_bn']}bn to CAD {f['aum1_bn']}bn "
            f"({f['aum_chg_pct']}%) over {f['horizon']} months, with revenue of CAD {f['rev_m']}m, expenses of CAD {f['exp_m']}m and operating income of "
            f"CAD {f['oi_m']}m (margin {f['margin_pct']}%). Across {f['n_ports']} managed portfolios the immediate market impact would be "
            f"CAD {f['port_impact_m']}m; the most affected mandate is {f['worst_mandate']} ({f['worst_mandate_pct']}%). These are deterministic outputs "
            f"conditional on the stated assumptions, not forecasts.")


@REGISTRY.register(spec("scenario_agent", "investment", "investment_supervisor", "Runs deterministic market and business scenarios.",
                        INV | EXEC | RISK, ["scenario.run", "scenario.compare"], ScenarioQ))
def scenario_agent(ctx, q: ScenarioQ):
    r = ctx.tool("scenario.run", preset=q.preset, equity_shock=q.equity_shock, rate_shock_bps=q.rate_shock_bps)
    res, pi = r["results"], r["portfolio_impacts"]
    a = {x["name"]: x["value"] for x in r["assumptions"]}
    worst = min(pi["by_mandate"].items(), key=lambda kv: kv[1])
    facts = {"scenario": r["scenario"], "assumption_line": f"equity {pct(a['equity_shock'])}%, rates {a['rate_shock_bps']} bps, net flows "
                                                        f"{pct(a['net_flows_pct'])}% p.a., fee compression {a['fee_compression_bps']} bps",
             "equity_shock_pct": pct(a["equity_shock"]), "rate_bps": a["rate_shock_bps"], "flows_pct": pct(a["net_flows_pct"]), "fee_bps": a["fee_compression_bps"],
             "aum0_bn": bn(res["aum_start"]), "aum1_bn": bn(res["aum_end"]), "aum_chg_pct": pct(res["aum_change_pct"]), "horizon": r["horizon_months"],
             "rev_m": mn(res["revenue"]), "exp_m": mn(res["expenses"]), "oi_m": mn(res["operating_income"]),
             "margin_pct": pct(res["operating_margin"]) if res["operating_margin"] is not None else None, "n_ports": pi["count"],
             "port_impact_m": mn(pi["total_impact"]), "worst_mandate": worst[0], "worst_mandate_pct": pct(worst[1]),
             "assumptions": r["assumptions"], "most_impacted": pi["most_impacted"][:5]}
    return _out(ctx, "scenario_agent", "scenario", facts, ["scenario_paths", "portfolio_impacts"])


# ------------------------------------------------------------------ 10 Client intelligence
@template("client_intel")
def _t_ci(f):
    return (f"{f['name']} ({f['client_id']}) - segment {f['segment']}, age {f['age']}, risk profile {f['risk_profile']}, preferred language {f['language']}. "
            f"They hold {f['n_funds']} fund position(s) worth CAD {f['funds_value']} and {f['n_portfolios']} managed portfolio(s). Of the last "
            f"{f['n_int']} interactions, {f['neg']} were negative in sentiment and {f['followups']} require follow-up; most recent topic: {f['last_topic']} "
            f"({f['last_date']}). KYC last reviewed {f['kyc']}.")


@REGISTRY.register(spec("client_intelligence_agent", "wealth", "wealth_supervisor", "Client 360 relationship summary.",
                        ADV | COMP, ["client.profile", "client.interactions"], ClientQ, data_classification="confidential"))
def client_intelligence_agent(ctx, q: ClientQ):
    p = ctx.tool("client.profile", client_id=q.client_id)
    it = ctx.tool("client.interactions", client_id=q.client_id)["interactions"]
    facts = {"client_id": q.client_id, "name": p["full_name"], "segment": p["segment"], "age": p["age"], "risk_profile": p["risk_profile"],
             "language": p["language"], "n_funds": len(p["fund_positions"]), "funds_value": f"{sum(x['market_value'] for x in p['fund_positions']):,.2f}",
             "n_portfolios": len(p["portfolio_ids"]), "n_int": len(it), "neg": sum(i["sentiment"] == "negative" for i in it),
             "followups": sum(i["follow_up_required"] for i in it), "last_topic": it[0]["topic"] if it else "none",
             "last_date": it[0]["ts"][:10] if it else "n/a", "kyc": p["kyc_last_review"], "portfolio_ids": p["portfolio_ids"]}
    return _out(ctx, "client_intelligence_agent", "client_intel", facts, ["timeline"])


# ------------------------------------------------------------------ 11 Wealth advisor (portfolio health + suitability screen)
@template("wealth_health")
def _t_wh(f):
    s = f"Portfolio health for {f['client_id']}: "
    s += " ".join(f"{p['id']} ({p['mandate']}) volatility {p['vol_pct']}% vs band {f['band_pct']}%, top holding {p['top_pct']}%, drift {p['drift_pct']}%." for p in f["portfolios"])
    s += f" Suitability screen (rules {f['rules_version']}): {f['status']} with {f['n_findings']} finding(s). Findings are inputs to advisor and compliance review, not a determination."
    return s


@REGISTRY.register(spec("wealth_advisor_agent", "wealth", "wealth_supervisor", "Portfolio health and rule-based suitability screening for a client.",
                        ADV | COMP, ["client.portfolios", "client.suitability"], ClientQ, data_classification="confidential",
                        approval_actions=("recommendation:deliver",)))
def wealth_advisor_agent(ctx, q: ClientQ):
    ps = ctx.tool("client.portfolios", client_id=q.client_id)["portfolios"]
    s = ctx.tool("client.suitability", client_id=q.client_id)
    facts = {"client_id": q.client_id, "window_months": 24, "band_pct": pct(s["volatility_band"]), "rules_version": s["rules_version"], "status": s["status"],
             "n_findings": len(s["findings"]), "findings": s["findings"],
             "portfolios": [{"id": p["id"], "mandate": p["mandate"], "vol_pct": pct(p["volatility"]), "top_pct": pct(p["top_weight"]),
                             "drift_pct": pct(p["drift"]), "twr_ann_pct": pct(p["twr_annualized"])} for p in ps]}
    w = ["Personalized recommendations require compliance approval (recommendation:deliver)."] if s["findings"] else []
    return _out(ctx, "wealth_advisor_agent", "wealth_health", facts, ["allocation", "risk_return"], w)


# ------------------------------------------------------------------ 12 Retirement planning
@template("retirement")
def _t_ret(f):
    return (f"Retirement projection for {f['client_id']} (age {f['age']}): current savings CAD {f['savings']} plus CAD {f['monthly']} per month, at an assumed "
            f"{f['er_pct']}% return and {f['inf_pct']}% inflation, projects CAD {f['at_ret']} at age 65 (CAD {f['real_at_ret']} in today's dollars). "
            f"That supports a first-year withdrawal of about CAD {f['withdrawal']} rising with inflation for {f['years']} years. Assumptions are "
            f"illustrative planning inputs from approved rules; results are not guaranteed.")


@REGISTRY.register(spec("retirement_planning_agent", "wealth", "wealth_supervisor", "Deterministic retirement projection and goal progress.",
                        ADV, ["client.retirement", "client.goals"], ClientQ, data_classification="confidential"))
def retirement_planning_agent(ctx, q: ClientQ):
    r = ctx.tool("client.retirement", client_id=q.client_id)
    g = ctx.tool("client.goals", client_id=q.client_id)
    a = r["assumptions"]
    facts = {"client_id": q.client_id, "age": r["age"], "savings": f"{float(r['current_savings']):,.2f}", "monthly": f"{float(r['monthly_contribution']):,.2f}",
             "er_pct": pct(a["expected_return"]), "inf_pct": pct(a["inflation"]), "at_ret": f"{float(r['balance_at_retirement']):,.2f}",
             "real_at_ret": f"{float(r['real_balance_at_retirement']):,.2f}", "withdrawal": f"{float(r['sustainable_first_year_withdrawal']):,.2f}",
             "years": a["retirement_years"], "retirement_age": 65, "goals": g["goals"], "path": r["path"], "cash_flow_forecast": r["cash_flow_forecast"]}
    return _out(ctx, "retirement_planning_agent", "retirement", facts, ["retirement_projection", "goal_progress", "cash_flow"])


# ------------------------------------------------------------------ 13 Product research (public; no client data)
@template("product")
def _t_prod(f):
    s = f"Product research ({f['n']} funds, general information, not a recommendation): "
    s += " ".join(f"{x['strategy']}: lowest fee {x['name']} at {x['fee_bps']} bps, 12-month return {x['ret_pct']}%." for x in f["by_strategy"])
    return s


@REGISTRY.register(spec("product_research_agent", "wealth", "wealth_supervisor", "Public product comparisons (fees, returns); no client data.",
                        ALL, ["investment.fund_list", "docs.search"], Question, data_classification="public"))
def product_research_agent(ctx, q: Question):
    funds = ctx.tool("investment.fund_list")["data"]["funds"]
    by: dict = {}
    for f in funds:
        if f["strategy"] not in by or f["fee_bps"] < by[f["strategy"]]["fee_bps"]:
            by[f["strategy"]] = f
    w: list = []
    try_tool(ctx, w, "docs.search", query=q.question or "fund fees comparison", k=3, doc_types=["product_research"])
    facts = {"n": len(funds), "by_strategy": [{"strategy": k, "name": v["name"], "fee_bps": v["fee_bps"], "ret_pct": pct(v["return_12m"])}
                                              for k, v in sorted(by.items())], "window": 12}
    return _out(ctx, "product_research_agent", "product", facts, ["fee_comparison"], w)


# ------------------------------------------------------------------ 14 Client meeting (agenda + optional approved-template draft)
@template("meeting")
def _t_meet(f):
    s = f"Meeting preparation for {f['client_id']}. Agenda: " + "; ".join(f"{i + 1}. {a}" for i, a in enumerate(f["agenda"])) + "."
    if f.get("draft_language"):
        s += (f" A client follow-up draft in '{f['draft_language']}' was prepared from approved template {f['template']}; translation validation "
              f"{'passed' if f['translation_valid'] else 'FAILED'}, compliance pre-check {'passed' if f['precheck'] else 'FAILED'}. Sending requires compliance approval.")
    return s


@REGISTRY.register(spec("client_meeting_agent", "wealth", "wealth_supervisor", "Builds meeting agendas and approved-template follow-up drafts.",
                        ADV, ["client.profile", "client.goals", "client.suitability", "client.interactions", "comms.draft"], ClientQ,
                        data_classification="confidential", approval_actions=("comms:send",), max_iterations=10))
def client_meeting_agent(ctx, q: ClientQ):
    g = ctx.tool("client.goals", client_id=q.client_id)["goals"]
    s = ctx.tool("client.suitability", client_id=q.client_id)
    it = ctx.tool("client.interactions", client_id=q.client_id)["interactions"]
    agenda = ["Review performance versus benchmark and objectives"]
    off = [x for x in g if not x["on_track"]]
    if off:
        agenda.append(f"Discuss {len(off)} goal(s) not on track: " + ", ".join(x["goal_type"] for x in off))
    for f in s["findings"]:
        agenda.append({"SUIT-VOL-BAND": "Review risk level against risk profile", "SUIT-SINGLE-ISSUER": "Review single-issuer concentration",
                       "SUIT-KYC-STALE": "Refresh KYC information (required before any recommendation)"}[f["rule"]])
    pend = [i for i in it if i["follow_up_required"]]
    if pend:
        agenda.append(f"Close {len(pend)} open follow-up(s), latest: {pend[0]['topic']}")
    agenda = list(dict.fromkeys(agenda))
    facts = {"client_id": q.client_id, "agenda": agenda, "agenda_numbers": list(range(1, len(agenda) + 1)), "goals": g,
             "suitability_status": s["status"]}
    if q.draft_language:
        d = ctx.tool("comms.draft", client_id=q.client_id, purpose="portfolio_review", language=q.draft_language)
        facts.update(draft_language=q.draft_language, template=d["template_version"], translation_valid=d["translation_validation"]["valid"],
                     precheck=d["compliance_precheck"]["passed"], draft=d)
    return _out(ctx, "client_meeting_agent", "meeting", facts, ["goal_progress", "timeline"])


# ------------------------------------------------------------------ 15 Compliance research (model-planned)
@template("compliance")
def _t_comp(f):
    if not f["sources"]:
        return "No authorized policy or regulatory sources matched. FLO does not answer compliance questions without evidence."
    s = "Relevant policy and regulatory references (cited; AI does not make legal or regulatory determinations): "
    s += " ".join(f"[{i + 1}] {x['title']} v{x['version']} - {x['section']}: {x['excerpt']}" for i, x in enumerate(f["sources"]))
    if f.get("open_exceptions") is not None:
        s += f" Open compliance exceptions: {f['open_exceptions']} ({f['open_high']} high or critical)."
    return s


@REGISTRY.register(spec("compliance_research_agent", "risk", "risk_compliance_supervisor", "Policy and regulatory research with citations.",
                        COMP | EXEC | ADV | INV | RISK, ["docs.search", "compliance.events"], Question, eval_requirements=("citations",)))
def compliance_research_agent(ctx, q: Question):
    w: list = []
    hits = _plan_and_search(ctx, "compliance_research_agent", q, ["policy", "procedure", "standard", "regulatory_reference"], w)
    facts = {"count": len(hits), "sources": _sources(hits), "refs": list(range(1, len(hits) + 1))}
    if "compliance_officer" in ctx.principal.roles:
        ev = try_tool(ctx, w, "compliance.events")
        if ev:
            op = [e for e in ev["events"] if e["status"] != "closed"]
            facts.update(open_exceptions=len(op), open_high=sum(e["severity"] in ("high", "critical") for e in op))
    return _out(ctx, "compliance_research_agent", "compliance", facts, [], w)


# ------------------------------------------------------------------ 16 Board reporting
@template("board")
def _t_board(f):
    return (f"Board report draft ({f['period']}): AUM CAD {f['aum_bn']}bn ({f['growth_pct']}% over {f['months']} months); revenue CAD {f['rev_m']}m; "
            f"operating margin {f['margin_pct']}% versus {f['prior_margin_pct']}% in the prior period. Budget: {f['unfav']} of {f['lines']} ledger lines "
            f"unfavourable, largest variance {f['worst_line']} (CAD {f['worst_var_m']}m). Initiatives: {f['behind']} of {f['n_init']} behind plan. "
            f"Top risk: {f['top_risk']}. Distribution to the board requires executive approval (board:distribute).")


@REGISTRY.register(spec("board_reporting_agent", "executive", "executive_supervisor", "Drafts the board performance report (distribution is approval-gated).",
                        frozenset({"executive"}), ["finance.kpis", "finance.actual_vs_budget", "strategy.initiatives", "risk.heatmap"], Question,
                        approval_actions=("board:distribute",)))
def board_reporting_agent(ctx, q: Question):
    k = ctx.tool("finance.kpis", months=q.months)["data"]
    b = ctx.tool("finance.actual_vs_budget", months=q.months)["data"]["lines"]
    i = ctx.tool("strategy.initiatives")["data"]["initiatives"]
    r = ctx.tool("risk.heatmap")["data"]["items"]
    unfav = [x for x in b if not x["favourable"]]
    worst = max(unfav, key=lambda x: abs(x["variance"])) if unfav else b[0]
    facts = {"period": f"{k['period']['start']}..{k['period']['end']}", "months": k["period"]["months"], "aum_bn": bn(k["total_aum"]),
             "growth_pct": pct(k["aum_growth"]), "rev_m": mn(k["management_fee_revenue"]), "margin_pct": pct(k["operating_margin"]),
             "prior_margin_pct": pct(k["prior_period"]["operating_margin"]) if k["prior_period"] else None, "unfav": len(unfav), "lines": len(b),
             "worst_line": worst["line"], "worst_var_m": mn(worst["variance"]), "behind": sum(x["status"] == "behind" for x in i), "n_init": len(i),
             "top_risk": r[0]["title"], "budget_lines": b}
    return _out(ctx, "board_reporting_agent", "board", facts, ["actual_vs_budget", "initiative_scorecard"],
                ["Board distribution is approval-gated; submit via the approvals workflow."])


# ------------------------------------------------------------------ 17 Decision memory
@template("decisions")
def _t_dec(f):
    s = (f"Decision memory: {f['delivered']} decisions delivered their target KPI, {f['partial']} partially, {f['not_delivered']} did not, and "
         f"{f['pending']} are pending. {f['behind']} strategic initiatives are behind schedule and {f['unresolved']} follow-up commitments are overdue.")
    if f.get("d1_after") is not None:
        s += (f" For D-0001 (fee repositioning), average monthly net flows of the repriced funds moved from CAD {f['d1_before']}m before to "
              f"CAD {f['d1_after']}m after; the non-repriced comparison group moved from CAD {f['d1_ctrl_before']}m to CAD {f['d1_ctrl_after']}m.")
    s += " " + f["caveat"]
    return s


@REGISTRY.register(spec("decision_memory_agent", "executive", "executive_supervisor", "Executive decision memory: outcomes, assumptions, commitments.",
                        EXEC | frozenset({"cio", "compliance_officer"}), ["strategy.decisions", "strategy.decision_list"], Question))
def decision_memory_agent(ctx, q: Question):
    s = ctx.tool("strategy.decisions")
    lst = ctx.tool("strategy.decision_list")["decisions"]
    c = s["counts_by_outcome"]
    d1 = next((d for d in lst if d["id"] == "D-0001"), None)
    facts = {"delivered": c.get("delivered", 0), "partial": c.get("partially_delivered", 0), "not_delivered": c.get("not_delivered", 0),
             "pending": c.get("pending", 0), "behind": len(s["behind_schedule_initiatives"]), "unresolved": s["unresolved_commitment_count"],
             "caveat": s["caveat"], "behind_initiatives": [x["name"] for x in s["behind_schedule_initiatives"]],
             "top_delivered": [{"id": d["id"], "title": d["title"], "kpi": d["target_kpi"]} for d in s["delivered"][:5]],
             "assumptions_examples": [{"id": d["id"], "assumptions": d["assumptions"]} for d in lst[:4]],
             "overdue_commitments": s["unresolved_commitments"][:8], "decision_id": "D-0001"}
    if d1 and d1.get("measurement"):
        m = d1["measurement"]
        facts.update(d1_before=m["avg_monthly_net_flows_before_cad_m"], d1_after=m["avg_monthly_net_flows_after_cad_m"],
                     d1_ctrl_before=m["comparison_group_before_cad_m"], d1_ctrl_after=m["comparison_group_after_cad_m"])
    return _out(ctx, "decision_memory_agent", "decisions", facts, ["decision_timeline"])


# ------------------------------------------------------------------ 18 Operational intelligence
@template("ops")
def _t_ops(f):
    s = (f"Across {f['total']} agent traces, the agent with the highest failure rate is {f['worst']} ({f['worst_rate_pct']}%, {f['worst_fail']} failures, "
         f"p95 latency {f['worst_p95']} ms). Dominant failure class: {f['worst_class']}. Failures cluster on {f['peak_day']} ({f['peak_n']} failures). "
         f"Open circuit breakers: {f['open_breakers']}.")
    if f["sources"]:
        s += " Related incident record: " + "; ".join(f"[{i + 1}] {x['title']} - {x['section']}" for i, x in enumerate(f["sources"]))
    return s


@REGISTRY.register(spec("operational_intelligence_agent", "aiops", "ai_operations_supervisor", "Investigates agent failures, latency and incidents.",
                        OPS, ["aiops.traces", "aiops.breakers", "docs.search"], Question))
def operational_intelligence_agent(ctx, q: Question):
    t = ctx.tool("aiops.traces")
    b = ctx.tool("aiops.breakers")["breakers"]
    worst = t["agents"][0]
    days = t["worst_agent_failures_by_day"]
    peak = max(days, key=days.get) if days else "n/a"
    hits = ctx.tool("docs.search", query=f"incident {worst['agent'].replace('_', ' ')} timeout circuit breaker", k=2, doc_types=["incident_report"])["results"]
    facts = {"total": t["total_traces"], "worst": worst["agent"], "worst_rate_pct": pct(worst["failure_rate"]), "worst_fail": worst["failures"],
             "worst_p95": worst["p95_latency_ms"], "worst_class": max(worst["failure_classes"], key=worst["failure_classes"].get) if worst["failure_classes"] else "none",
             "peak_day": peak, "peak_n": days.get(peak, 0), "open_breakers": [x["name"] for x in b if x["state"] != "closed"] or "none",
             "agents": t["agents"][:6], "sources": _sources(hits), "refs": [1, 2], "percentile": 95}
    return _out(ctx, "operational_intelligence_agent", "ops", facts, ["agent_failures"])


# ------------------------------------------------------------------ 19 Data quality
@template("dq")
def _t_dq(f):
    s = f"Data quality: {f['passed']} of {f['total']} checks passed ({f['rate_pct']}%) on dataset version {f['version']}."
    if f["failed"]:
        s += " Failing: " + "; ".join(f"{x['check_id']} {x['name']} ({x['detail']})" for x in f["failed"])
    return s


@REGISTRY.register(spec("data_quality_agent", "aiops", "ai_operations_supervisor", "Runs and explains data product quality checks.",
                        OPS | EXEC, ["data_quality.run"], Question))
def data_quality_agent(ctx, q: Question):
    r = ctx.tool("data_quality.run")
    failed = [c for c in r["checks"] if not c["passed"]]
    facts = {"passed": r["passed"], "total": r["total"], "rate_pct": pct(r["pass_rate"]), "version": r["dataset_version"], "failed": failed}
    return _out(ctx, "data_quality_agent", "dq", facts, ["data_quality"])


# ------------------------------------------------------------------ 20 Evaluation
@template("evals")
def _t_ev(f):
    return (f"Evaluation summary over {f['runs']} recorded agent runs: success rate {f['success_pct']}%, mean evaluation score {f['mean_score']}, "
            f"policy denials {f['denials']}. Lowest-scoring agent: {f['lowest_agent']} ({f['lowest_score']}). Release gate: {f['gate']}.")


@REGISTRY.register(spec("evaluation_agent", "aiops", "ai_operations_supervisor", "Summarizes evaluation scores and the release gate.",
                        OPS, ["aiops.traces"], Question))
def evaluation_agent(ctx, q: Question):
    import json
    from backend.config import ROOT
    from sqlalchemy import select
    from backend.db import models as m
    from backend.db.session import session_scope
    ctx.tool("aiops.traces")
    with session_scope() as s:
        rows = list(s.execute(select(m.AgentTrace.agent_id, m.AgentTrace.status, m.AgentTrace.eval_score, m.AgentTrace.policy_outcome)
                              .where(m.AgentTrace.tenant_id == ctx.principal.tenant_id)))
    scores: dict = {}
    for a, st, sc, _ in rows:
        if sc is not None:
            scores.setdefault(a, []).append(sc)
    mean = {a: round(sum(v) / len(v), 3) for a, v in scores.items()}
    low = min(mean, key=mean.get)
    gate_file = ROOT / "var" / "release_gate.json"
    gate = json.loads(gate_file.read_text())["status"] if gate_file.exists() else "not yet run (run `make release-gate`)"
    facts = {"runs": len(rows), "success_pct": pct(sum(r[1] == "succeeded" for r in rows) / max(1, len(rows))),
             "mean_score": round(sum(sum(v) for v in scores.values()) / max(1, sum(len(v) for v in scores.values())), 3),
             "denials": sum(r[3] == "deny" for r in rows), "lowest_agent": low, "lowest_score": mean[low], "gate": gate, "by_agent": mean}
    return _out(ctx, "evaluation_agent", "evals", facts, ["eval_scores"])


# ------------------------------------------------------------------ 21 Advisor productivity (enterprise aggregate)
@template("advisor_productivity")
def _t_ap(f):
    s = (f"Across {f['advisors']} advisors, book AUM totals CAD {f['total_bn']}bn, with a median book of CAD {f['median_m']}m and a median of "
         f"{f['median_clients']} active clients per advisor. The top quartile of advisors averages CAD {f['top_q_m']}m per book versus "
         f"CAD {f['bottom_q_m']}m for the bottom quartile")
    s += f" ({f['ratio']}x)." if f.get("ratio") is not None else "."
    s += (f" The median advisor logged {f['median_ipc']} interactions per client over 12 months; {f['followups']} interactions were flagged for "
          f"follow-up and {f['kyc_stale']} active clients have KYC older than the approved maximum. Activity counts describe workload, not advisor quality.")
    return s


@REGISTRY.register(spec("advisor_productivity_agent", "executive", "executive_supervisor", "Advisor productivity: book size, client load, activity and dispersion.",
                        EXEC, ["wealth.advisor_productivity"], Question))
def advisor_productivity_agent(ctx, q: Question):
    d = ctx.tool("wealth.advisor_productivity")["data"]
    s = d["summary"]
    facts = {"advisors": s["advisors"], "total_bn": bn(s["total_book_aum"]), "median_m": mn(s["median_book_aum"]), "median_clients": s["median_active_clients"],
             "top_q_m": mn(s["top_quartile_avg_aum"]), "bottom_q_m": mn(s["bottom_quartile_avg_aum"]), "ratio": s["top_to_bottom_quartile_ratio"],
             "median_ipc": s["median_interactions_per_client"], "followups": s["follow_ups_flagged_total"], "kyc_stale": s["kyc_stale_total"],
             "as_of": s["as_of"], "window": 12, "advisor_rows": d["advisors"]}
    return _out(ctx, "advisor_productivity_agent", "advisor_productivity", facts, ["advisor_productivity_scatter", "advisor_book_distribution"])


# ------------------------------------------------------------------ 22 Client retention (enterprise trend and/or the advisor's own book)
@template("retention")
def _t_retention(f):
    parts = []
    if f.get("ent_retention_pct") is not None:
        parts.append(f"Enterprise client retention over the 12 months to {f['as_of']} was {f['ent_retention_pct']}%, versus {f['ent_prior_pct']}% in the "
                     f"prior 12 months, with {f['ent_closed']} client closures. The lowest-retention segment was {f['low_seg']} at {f['low_seg_pct']}%.")
    if f.get("book_clients") is not None:
        s = f"Your book has {f['book_clients']} active clients"
        s += f"; 12-month retention was {f['book_retention_pct']}% with {f['book_closed']} closure(s)." if f.get("book_retention_pct") is not None else "."
        s += (f" {f['at_risk']} active clients show at least one review signal ({f['sig_neg']} negative sentiment in the last 6 months, {f['sig_fu']} "
              f"follow-ups flagged in the last 90 days, {f['sig_kyc']} with stale KYC). Signals are prompts for review, not predictions.")
        parts.append(s)
    return " ".join(parts)


@REGISTRY.register(spec("client_retention_agent", "wealth", "wealth_supervisor", "Client retention: enterprise trend and the advisor's own book signals.",
                        EXEC | ADV, ["finance.retention", "wealth.book_health"], Question, data_classification="confidential"))
def client_retention_agent(ctx, q: Question):
    w: list = []
    facts: dict = {"window": 12, "months_6": 6, "days_90": 90}
    ent = try_tool(ctx, w, "finance.retention") if "exec:read" in _perms(ctx) else None
    if ent:
        d = ent["data"]
        low = min((x for x in d["by_segment"] if x["retention_12m"] is not None), key=lambda x: x["retention_12m"])
        facts.update(as_of=d["as_of"], ent_retention_pct=pct(d["retention_12m"]), ent_prior_pct=pct(d["retention_prior_12m"]),
                     ent_closed=d["closed_12m"], low_seg=low["segment"], low_seg_pct=pct(low["retention_12m"]), by_segment=d["by_segment"])
    if ctx.principal.advisor_id:
        book = try_tool(ctx, w, "wealth.book_health")
        if book:
            b = book["data"]
            facts.update(as_of=b["as_of"], book_clients=b["active_clients"], book_closed=b["closed_12m"],
                         book_retention_pct=pct(b["retention_12m"]) if b["retention_12m"] is not None else None, at_risk=b["at_risk_total"],
                         sig_neg=b["signal_counts"]["negative_sentiment_6m"], sig_fu=b["signal_counts"]["follow_up_flagged_90d"],
                         sig_kyc=b["signal_counts"]["kyc_stale"], at_risk_clients=b["at_risk_clients"], kyc_max_age_days=b["kyc_max_age_days"])
    if "ent_retention_pct" not in facts and "book_clients" not in facts:
        raise PolicyDenied("no retention data is authorized for this identity", code="RETENTION-NOT-AUTHORIZED")
    return _out(ctx, "client_retention_agent", "retention", facts, ["retention_trend", "retention_by_segment", "book_signals"], w)


def _perms(ctx) -> set[str]:
    """Permissions granted to the principal's roles (used only to skip calls that would certainly be denied; the gateway still decides)."""
    rbac = ctx.engine.bundle.rbac["roles"]
    return {p for r in ctx.principal.roles for p in rbac.get(r, [])}


# ------------------------------------------------------------------ 23 Firm diagnostic for a prospective client (user-supplied figures only)
class FirmQ(Question):
    aum: float | None = Field(None, ge=0, le=1e13)
    fee_bps: float | None = Field(None, ge=0, le=500)
    revenue: float | None = Field(None, ge=0, le=1e12)
    expenses: float | None = Field(None, ge=0, le=1e12)
    advisors: int | None = Field(None, ge=1, le=100000)
    clients: int | None = Field(None, ge=1, le=10000000)
    net_flows: float | None = Field(None, ge=-1e12, le=1e12)


_PROV = {"user_supplied": "you provided", "calculated_from_user_inputs": "calculated from your inputs",
         "illustrative_assumption": "illustrative, based on a planning assumption"}


def _fmt_metric(m: dict) -> str:
    v, u = m["value"], m["unit"]
    if u == "CAD":
        return f"CAD {v:,.0f}"
    if u == "ratio":
        return f"{pct(v)}%"
    if u == "bps":
        return f"{v:.1f} bps"
    return f"{v:,.1f}"


@template("firm")
def _t_firm(f):
    if not f["known"]:
        return ("Thank you for reaching out. To build a preliminary view of your business I need a few facts, starting with your assets under "
                "management. " + " ".join(f["discovery_questions"][:3]))
    s = "Preliminary assessment based only on the figures you provided"
    s += " and clearly labelled planning assumptions: " if f["assumption_used"] else ": "
    s += " ".join(f"{m['label']}: {m['display']} ({_PROV[m['provenance']]})." for m in f["metrics"])
    if f.get("per_bp") is not None:
        s += (f" Sensitivity: each {f['unit_bp']} bp of average fee is worth about CAD {f['per_bp']:,.0f} of annual revenue on your AUM, and each "
              f"{f['unit_pct']}% of AUM added through net new assets adds about CAD {f['per_pct']:,.0f} at a {f['fee_used']} bps fee.")
    s += f" Still needed for a fuller view: {', '.join(f['missing_labels'])}." if f["missing_labels"] else ""
    return s


@REGISTRY.register(spec("firm_diagnostic_agent", "executive", "executive_supervisor",
                        "Preliminary business assessment for a prospective client from figures they supply (no platform data).",
                        ALL, ["advisory.firm_model"], FirmQ, data_classification="confidential"))
def firm_diagnostic_agent(ctx, q: FirmQ):
    args = {k: getattr(q, k) for k in ("aum", "fee_bps", "revenue", "expenses", "advisors", "clients", "net_flows") if getattr(q, k) is not None}
    a = ctx.tool("advisory.firm_model", **args)
    from analytics.firm_model import FIELDS
    metrics = [{**m, "display": _fmt_metric(m)} for m in a["metrics"]]
    sens = a.get("sensitivities") or {}
    facts = {"known": a["known"], "missing": a["missing"], "missing_labels": [FIELDS[k].lower() for k in a["missing"]][:4], "metrics": metrics,
             "assumption_used": bool(a["assumptions"]), "assumptions": a["assumptions"], "discovery_questions": a["discovery_questions"],
             "per_bp": sens.get("revenue_per_1bp_fee"), "per_pct": sens.get("revenue_per_1pct_net_new_assets"), "fee_used": sens.get("fee_bps_used"),
             "unit_bp": 1, "unit_pct": 1, "assessment": a}
    return _out(ctx, "firm_diagnostic_agent", "firm", facts, ["firm_kpis", "firm_fee_sensitivity", "firm_market_scenarios", "firm_data_readiness"])
