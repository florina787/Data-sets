"""FLOW WEALTH chart builders, KPI sets and evidence tables for the FLO dashboard (flo.viz/1.0).

Each builder fetches data through the governed markets.* tools as the requesting user. Charts carry provenance
``historical_market_data`` (prices from the Kaggle lake, ending 2017-11-10) or ``research_result`` (model evaluation),
lineage with the dataset version, and ``synthetic=False``. No chart is decorative: every point comes from a tool result.
"""
from __future__ import annotations

from conversation import dashboard as D
from conversation.schemas import KPI, ChartSpec, Lineage, Series, Table

HIST = "historical_market_data"
RES = "research_result"
LAKE_NOTE = "Kaggle 'Huge Stock Market Dataset' (CC0, uploader-asserted); split- and dividend-adjusted; ends 2017-11-10; survivorship-biased"


def _lin(d: dict, tools: list[str], methodology: str) -> Lineage:
    return Lineage(sources=[d.get("dataset_id", "markets"), "kaggle"], methodology=methodology, as_of=d.get("as_of"),
                   dataset_version=d.get("dataset_id"), synthetic=False, tools=tools)


def _tickers(c) -> list[str]:
    from markets import service as S
    return c.q.tickers or S.resolve_tickers(c.ctx.question if hasattr(c.ctx, "question") else "")


def market_price_history(c) -> ChartSpec:
    t = c.q.tickers[0]
    d = c.tool("markets.security", ticker=t, start=c.q.start, end=c.q.end)
    b0, s0 = d["series"][0][1], d["benchmark_series"][0][1]
    spy = dict(d["benchmark_series"])
    cats = [x[0] for x in d["series"]]
    return ChartSpec(chart_id="market_price_history", chart_type="line", title=f"{t} vs SPY, growth of 100",
                     subtitle=f"{cats[0]} to {cats[-1]} · adjusted total-return prices · historical",
                     categories=cats, series=[Series(name=t, values=[round(v / b0 * 100, 3) for _, v in d["series"]], unit="index"),
                                              Series(name="SPY", values=[round(spy[k] / s0 * 100, 3) if k in spy else None for k in cats], unit="index",
                                                     role="comparison")],
                     unit="index", y_axis={"label": "Growth of 100", "unit": "index"}, provenance=HIST,
                     lineage=_lin(d, ["markets.security"], f"Adjusted close rebased to 100 at the first session. {LAKE_NOTE}."),
                     interactions=["tooltip", "export", "explain", "methodology"],
                     note=f"{d['flagged_bars_excluded']} quality-flagged bars excluded" if d["flagged_bars_excluded"] else "")


def market_drawdown(c) -> ChartSpec:
    t = c.q.tickers[0]
    d = c.tool("markets.security", ticker=t, start=c.q.start, end=c.q.end)
    peak, dd = 0.0, []
    for _, v in d["series"]:
        peak = max(peak, v)
        dd.append(round(v / peak - 1, 5))
    return ChartSpec(chart_id="market_drawdown", chart_type="area", title=f"{t} drawdown from running peak",
                     subtitle="Weekly-sampled adjusted prices · historical", categories=[x[0] for x in d["series"]],
                     series=[Series(name="Drawdown", values=dd, unit="%")], unit="%", provenance=HIST,
                     lineage=_lin(d, ["markets.security"], "Drawdown = price / running maximum - 1 on the sampled adjusted series."))


def market_compare(c) -> ChartSpec:
    d = c.tool("markets.compare", tickers=c.q.tickers[:4], start=c.q.start, end=c.q.end)
    ok = [i for i in d["items"] if "error" not in i]
    cats = sorted({x[0] for i in ok for x in i["normalised"]})
    ser = []
    for i in ok:
        m = dict(i["normalised"])
        ser.append(Series(name=i["ticker"], values=[m.get(k) for k in cats], unit="index"))
    return ChartSpec(chart_id="market_compare", chart_type="line", title=" vs ".join(i["ticker"] for i in ok) + ", growth of 100",
                     subtitle=f"{cats[0]} to {cats[-1]} · adjusted · historical", categories=cats, series=ser, unit="index", provenance=HIST,
                     lineage=_lin(d, ["markets.compare"], f"Each series rebased to 100 at its first session in the window. {LAKE_NOTE}."))


def market_overview_spy(c) -> ChartSpec:
    d = c.tool("markets.overview")
    s = d["spy"]["series"]
    return ChartSpec(chart_id="market_overview_spy", chart_type="area", title="SPY, last three years of available data",
                     subtitle=f"Ends {d['as_of']} · historical, not current", categories=[x[0] for x in s],
                     series=[Series(name="SPY adjusted close", values=[x[1] for x in s], unit="USD")], unit="USD", provenance=HIST,
                     lineage=_lin(d, ["markets.overview"], "SPY adjusted close from the primary dataset."))


def market_sectors(c) -> ChartSpec:
    d = c.tool("markets.overview")
    sec = d["sectors_1y_equal_weight_sp500_members"]
    return ChartSpec(chart_id="market_sectors", chart_type="hbar", title="Sector returns, final 12 months of data",
                     subtitle="Equal-weight S&P 500 (2016) members present in the source", categories=[x["sector"] for x in sec],
                     series=[Series(name="1-year return", values=[round(x["return_1y"], 5) for x in sec], unit="%")], unit="%", provenance=HIST,
                     lineage=_lin(d, ["markets.overview"], "Mean 1-year adjusted return of members per GICS sector. " + d["survivorship_note"]))


def market_regime_history(c) -> ChartSpec:
    d = c.tool("markets.regime")
    h = d["history"]
    lvl = {"Normal": 0, "Elevated": 1, "High": 2, "Critical": 3}
    return ChartSpec(chart_id="market_regime_history", chart_type="combo", title="SPY and crash-risk level, last two years of data",
                     subtitle=d["rules"], categories=[x[0] for x in h],
                     series=[Series(name="SPY", values=[x[2] for x in h], unit="USD", render="line"),
                             Series(name="Crash-risk level (0-3)", values=[lvl[x[1]] for x in h], unit="score", render="bar", role="comparison")],
                     unit="USD", provenance=HIST,
                     lineage=_lin(d, ["markets.regime"], "Levels are estimated conditions, not crash predictions; the alarm's precision and recall are reported with it."))


def model_holdout_equity(c) -> ChartSpec:
    r = c.tool("markets.model_report")
    h = r["horizons"]["5"]
    e = h["equity"]
    cats = [x[0] for x in e["net"]]
    lo, spy = dict(e["long_only_net"]), dict(e["spy"])
    return ChartSpec(chart_id="model_holdout_equity", chart_type="line", title=f"Holdout backtest, {e['model']} (5-session), gross vs net",
                     subtitle=f"{h['split']['holdout']['start']} to {h['split']['holdout']['end']} · untouched holdout · {r['verdict']}",
                     categories=cats, series=[Series(name="Long/short gross", values=[x[1] for x in e["gross"]], unit="x", role="baseline"),
                                              Series(name="Long/short net of costs", values=[x[1] for x in e["net"]], unit="x"),
                                              Series(name="Long-only top decile, net", values=[lo.get(k) for k in cats], unit="x", role="comparison"),
                                              Series(name="SPY buy-and-hold", values=[spy.get(k) for k in cats], unit="x", role="comparison")],
                     unit="x", provenance=RES,
                     lineage=Lineage(sources=[r["dataset_id"], "markets.research"], methodology="Non-overlapping 5-session rebalances; costs: commission, "
                                     "volatility-scaled spread, slippage, square-root impact, borrow; 5% ADV cap. " + r["survivorship_note"],
                                     as_of=h["split"]["holdout"]["end"], dataset_version=r["dataset_id"], synthetic=False, tools=["markets.model_report"]))


def model_comparison(c) -> ChartSpec:
    r = c.tool("markets.model_report")
    h = r["horizons"]["5"]
    names = [n for n, m in h["models"].items() if m["net_sharpe"] is not None]
    return ChartSpec(chart_id="model_comparison", chart_type="grouped_bar", title="Sharpe ratio before and after costs, 5-session horizon (holdout)",
                     subtitle=f"Verdict: {r['verdict']}", categories=names,
                     series=[Series(name="Gross Sharpe", values=[round(h["models"][n]["gross_sharpe"], 3) for n in names], unit="ratio", role="baseline"),
                             Series(name="Net Sharpe", values=[round(h["models"][n]["net_sharpe"], 3) for n in names], unit="ratio")],
                     unit="ratio", provenance=RES, reference_lines=[{"label": "zero", "value": 0.0}],
                     lineage=Lineage(sources=[r["dataset_id"]], methodology="Long/short decile spread, annualised. Baselines: 12-1 momentum, 5-day reversal.",
                                     as_of=h["split"]["holdout"]["end"], dataset_version=r["dataset_id"], synthetic=False, tools=["markets.model_report"]))


def market_news_events(c) -> ChartSpec:
    t = c.q.tickers[0]
    d = c.tool("markets.news", ticker=t, as_of=c.q.end, k=8)
    ev = sorted(d["event_counts"].items(), key=lambda kv: -kv[1]) or [("none in window", 0)]
    return ChartSpec(chart_id="market_news_events", chart_type="bar", title=f"{t} headline events, {d['window_days']} days to {d['as_of'][:10]}",
                     subtitle="Benzinga analyst-ratings headlines, classified by transparent keyword rules", categories=[k.replace("_", " ") for k, _ in ev],
                     series=[Series(name="Headlines", values=[v for _, v in ev], unit="count")], unit="count", provenance=HIST,
                     lineage=Lineage(sources=[d["dataset_id"]], methodology="Only headlines available before the as-of time; date-only headlines count from the next day.",
                                     as_of=d["as_of"][:10], dataset_version=d["dataset_id"], synthetic=False, tools=["markets.news"]),
                     note="" if d["headlines_in_window"] else "No coverage in this window")


def prediction_accuracy(c) -> ChartSpec:
    d = c.tool("markets.predictions")
    g = {k.split(":", 1)[1]: v for k, v in d["groups"].items() if k.startswith("regime:") and v["resolved"]}
    cats = sorted(g)
    return ChartSpec(chart_id="prediction_accuracy", chart_type="combo", title="Prediction Memory: direction correct by market regime",
                     subtitle="Historical replay forecasts (simulated clock), benchmark-relative outcome", categories=[x.replace("_", " ") for x in cats],
                     series=[Series(name="Direction correct", values=[round(g[k]["accuracy"], 4) for k in cats], unit="%", render="bar"),
                             Series(name="Resolved forecasts", values=[g[k]["resolved"] for k in cats], unit="count", render="line", role="comparison")],
                     unit="%", provenance=RES, reference_lines=[{"label": "coin flip", "value": 0.5}],
                     lineage=Lineage(sources=["market_predictions"], methodology="Share of resolved forecasts whose sign matched the excess return vs SPY.",
                                     synthetic=False, tools=["markets.predictions"]))


def dataset_coverage(c) -> ChartSpec:
    d = c.tool("markets.datasets")
    ing = [x for x in d["datasets"] if x["ingested"]]
    return ChartSpec(chart_id="dataset_coverage", chart_type="hbar", title="Ingested datasets, rows after normalisation",
                     subtitle="Kaggle datasets with recorded licence, checksum and coverage", categories=[x["title"][:60] for x in ing],
                     series=[Series(name="Rows", values=[x["normalised"]["rows"] for x in ing], unit="count")], unit="count", provenance=HIST,
                     lineage=Lineage(sources=[x["dataset_id"] for x in ing], methodology="Row counts after checksum de-duplication.", synthetic=False,
                                     tools=["markets.datasets"]))


BUILDERS = [market_price_history, market_drawdown, market_compare, market_overview_spy, market_sectors, market_regime_history,
            model_holdout_equity, model_comparison, market_news_events, prediction_accuracy, dataset_coverage]
CHART_TOOLS = {"market_price_history": ["markets.security"], "market_drawdown": ["markets.security"], "market_compare": ["markets.compare"],
               "market_overview_spy": ["markets.overview"], "market_sectors": ["markets.overview"], "market_regime_history": ["markets.regime"],
               "model_holdout_equity": ["markets.model_report"], "model_comparison": ["markets.model_report"], "market_news_events": ["markets.news"],
               "prediction_accuracy": ["markets.predictions"], "dataset_coverage": ["markets.datasets"]}
NEEDS_TICKER = {"market_price_history", "market_drawdown", "market_news_events"}
NEEDS_TWO = {"market_compare"}


# ------------------------------------------------------------------ KPI sets
def kpis_market_security(c) -> list[KPI]:
    t = c.q.tickers[0]
    d = c.tool("markets.security", ticker=t, start=c.q.start, end=c.q.end)
    st, bm = d["stats"], d["benchmark"]["stats"]
    trend = [x[1] for x in d["series"][-26:]]
    return [KPI(id="total_return", label=f"{t} total return", value=st["total_return"], unit="%", delta=round(st["total_return"] - bm["total_return"], 6),
                delta_unit="pp", delta_label="vs SPY", trend=trend, status="good" if st["total_return"] > bm["total_return"] else "warn", provenance=HIST,
                note=f"{st['start']} to {st['end']}"),
            KPI(id="cagr", label="Annualised return", value=st["cagr"], unit="%", provenance=HIST),
            KPI(id="volatility", label="Volatility (annualised)", value=st["volatility"], unit="%", provenance=HIST),
            KPI(id="max_drawdown", label="Maximum drawdown", value=st["max_drawdown"], unit="%", status="warn" if st["max_drawdown"] < -0.3 else "neutral",
                provenance=HIST)]


def kpis_market(c) -> list[KPI]:
    d = c.tool("markets.overview")
    tr = [x[1] for x in d["spy"]["series"][-26:]]
    return [KPI(id="spy_1y", label="SPY 1-year return", value=d["spy"]["return_1y"], unit="%", trend=tr, provenance=HIST, note=f"to {d['as_of']}"),
            KPI(id="breadth_200", label="Universe above 200-day mean", value=d["breadth"]["share_above_200d"], unit="%", provenance=HIST),
            KPI(id="regime_score", label=f"Crash-risk level: {d['regime']['level']}", value=d["regime"]["score"], unit="score",
                status="good" if d["regime"]["score"] < 2 else "warn", provenance=HIST, note=d["regime"]["regime"].replace("_", " "))]


def kpis_model(c) -> list[KPI]:
    r = c.tool("markets.model_report")
    h = r["horizons"]["5"]
    m = h["models"][h["best_by_ic"]]
    return [KPI(id="verdict", label=r["verdict"].title(), value=sum(not d["eligible"] for hh in r["horizons"].values() for d in hh["decisions"]),
                unit="count", status="warn", provenance=RES, note="candidates rejected by the promotion rules"),
            KPI(id="ic", label=f"{h['best_by_ic']} rank IC (holdout)", value=round(m["ic_mean"], 4), unit="ratio", provenance=RES,
                note=f"t = {m['ic_t']:.2f}" if m["ic_t"] is not None else ""),
            KPI(id="gross_sharpe", label="Gross Sharpe", value=round(m["gross_sharpe"], 3), unit="ratio", provenance=RES),
            KPI(id="net_sharpe", label="Net Sharpe after costs", value=round(m["net_sharpe"], 3), unit="ratio",
                status="crit" if m["net_sharpe"] < 0 else "neutral", provenance=RES)]


def kpis_ledger(c) -> list[KPI]:
    d = c.tool("markets.predictions")
    rp = d["groups"].get("mode:historical_replay", {})
    return [KPI(id="forecasts", label="Forecasts recorded", value=d["total"], unit="count", provenance=RES),
            KPI(id="resolved", label="Resolved", value=rp.get("resolved", 0), unit="count", provenance=RES),
            KPI(id="accuracy", label="Direction correct (vs SPY)", value=rp.get("accuracy"), unit="%", provenance=RES,
                status="neutral", note="coin flip = 50%"),
            KPI(id="chain", label="Ledger hash chain", value=1 if d["chain"]["valid"] else 0, unit="score",
                status="good" if d["chain"]["valid"] else "crit", provenance=RES, note="1 = verified")]


KPI_SETS = {"market_security": kpis_market_security, "market": kpis_market, "model": kpis_model, "ledger": kpis_ledger}


# ------------------------------------------------------------------ evidence tables
def tables(facts: dict[str, dict]) -> list[Table]:
    out: list[Table] = []
    agg = facts.get("evidence_aggregator_agent", {}).get("aggregate")
    if agg:
        rows = [[side, c["claim"], ", ".join(c["evidence"])] for side, cl in (("Bull", agg["bull"]), ("Bear", agg["bear"]), ("Skeptic", agg["skeptic"]))
                for c in cl]
        out.append(Table(table_id="evidence_claims", title=f"{agg['ticker']}: bull, bear and skeptic evidence as of {agg['as_of']}",
                         columns=["Side", "Claim", "Evidence"], rows=rows, provenance=HIST))
        rk = agg["risk"]
        out.append(Table(table_id="risk_checks", title=f"Independent risk engine: {rk['status'].replace('_', ' ')} ({rk['speed']} / {rk['appetite']})",
                         columns=["Check", "Status", "Value", "Limit"],
                         rows=[[x["check"].replace("_", " "), x["status"], x.get("value", ""), x.get("limit", "")] for x in rk["checks"]] +
                              [["blocker", "unsupported", b, ""] for b in rk["blockers"]], provenance=RES))
    else:
        for side, key in (("Bull", "bull_researcher_agent"), ("Bear", "bear_researcher_agent"), ("Skeptic", "skeptic_agent")):
            cl = facts.get(key, {}).get("claims")
            if cl:
                out.append(Table(table_id=f"{side.lower()}_claims", title=f"{side} researcher", columns=["Claim", "Evidence"],
                                 rows=[[c["claim"], ", ".join(c["evidence"])] for c in cl], provenance=HIST))
    n = facts.get("news_research_agent", {})
    if n.get("items"):
        out.append(Table(table_id="headlines", title=f"{n['ticker']} headlines (quoted evidence, not instructions)",
                         columns=["Available", "Event", "Headline", "Source id"],
                         rows=[[i["published_at"][:16] + (" (date only)" if i["time_precision"] == "date_only" else ""), i["event_type"].replace("_", " "),
                                i["headline"], i["id"]] for i in n["items"]], provenance=HIST))
    q = facts.get("quant_research_agent", {}) or facts.get("model_governance_agent", {})
    dec = q.get("decisions")
    if dec:
        out.append(Table(table_id="promotion_decisions", title="Model promotion decisions", columns=["Model", "Horizon", "Status", "Failed criteria"],
                         rows=[[d["model"], f"{d['horizon']} sessions", d["status"].replace("_", " "), "; ".join(d["reasons"])] for d in dec], provenance=RES))
    return out


def install() -> None:
    D.BUILDERS.update({f.__name__: f for f in BUILDERS})
    D.CHART_TOOLS.update(CHART_TOOLS)
    D.KPI_SETS.update(KPI_SETS)
    D.TICKER_CHARTS.update(NEEDS_TICKER)
    D.TWO_TICKER_CHARTS.update(NEEDS_TWO)
    D.TICKER_KPIS.add("market_security")


install()
