"""FLOW WEALTH market research inside FLO: governed tools and specialist agents over PUBLIC market data.

* Tools resolve to a ``market_dataset`` resource classified ``public`` and need ``market:read`` (data, news) or
  ``quant:read`` (model results, evidence packs). The gateway authorizes every call for the human principal and audits it.
* Market agents allowlist ONLY ``markets.*`` tools, so even a compromised plan cannot reach client or firm records.
* Agent classification is ``public``: narration may use the Gemini provider, which policy approves for public data only.
* Bull, bear and skeptic agents reason over the same evidence pack via markets.debate; the aggregator keeps attribution and
  attaches the independent risk engine's output, which no agent can change.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from pydantic import BaseModel, Field

from agents.specialists import AgentOutput, _out, spec
from governance.policy import Resource
from harness.models import template
from harness.registry import REGISTRY
from harness.tools import TOOLS, ToolSpec
from markets import catalog, debate, ledger_view, risk as mrisk, service as S

TICKER = r"^[A-Z]{1,5}(-[A-Z])?$"
DAY = r"^\d{4}-\d{2}-\d{2}$"
MKT_ROLES = frozenset({"executive", "finance", "cio", "investment_analyst", "wealth_advisor", "external_advisor", "risk_officer", "ai_admin",
                       "prospect"})
QUANT_ROLES = frozenset({"executive", "cio", "investment_analyst", "wealth_advisor", "risk_officer", "ai_admin"})


def _res(ctx, _a) -> Resource:
    return Resource("market_dataset", catalog.PRIMARY, ctx.principal.tenant_id, {"classification": "public"})


class NoArgs(BaseModel):
    model_config = {"extra": "forbid"}


class TickerArgs(BaseModel):
    model_config = {"extra": "forbid"}
    ticker: str = Field(pattern=TICKER)
    start: str | None = Field(None, pattern=DAY)
    end: str | None = Field(None, pattern=DAY)


class CompareArgs(BaseModel):
    model_config = {"extra": "forbid"}
    tickers: list[str] = Field(min_length=2, max_length=4)
    start: str | None = Field(None, pattern=DAY)
    end: str | None = Field(None, pattern=DAY)


class NewsArgs(BaseModel):
    model_config = {"extra": "forbid"}
    ticker: str = Field(pattern=TICKER)
    as_of: str | None = Field(None, pattern=DAY)
    k: int = Field(8, ge=1, le=25)


class RejectArgs(BaseModel):
    model_config = {"extra": "forbid"}
    model: str | None = Field(None, pattern=r"^[a-z0-9_]{2,40}$")
    horizon: str | None = Field(None, pattern=r"^(1|5|20)$")


class RiskArgs(BaseModel):
    model_config = {"extra": "forbid"}
    ticker: str = Field(pattern=TICKER)
    speed: str = Field("swing", pattern=r"^(long_term|position|swing|intraday|swift)$")
    appetite: str = Field("moderate", pattern=r"^(conservative|moderate|aggressive)$")


def _reg(name, desc, perm, model, handler, timeout=20.0):
    TOOLS.register(ToolSpec(name, desc, perm, model, handler, _res, "market_lake", timeout, 600, False, "public"))


def _risk(ctx, a: RiskArgs) -> dict:
    ev = S.evidence_pack(a.ticker)
    vol = ev["features"].get("vol_20")
    adv = S._q("SELECT adv_usd FROM features WHERE ticker = ? AND date <= ? ORDER BY date DESC LIMIT 1", [a.ticker, ev["as_of"]])
    return mrisk.assess(ticker=a.ticker, volatility_annual=None if vol is None else vol * 252 ** 0.5, drawdown_1y=ev["features"].get("dd_252"),
                        adv_usd=float(adv.adv_usd.iloc[0]) if len(adv) and adv.adv_usd.iloc[0] == adv.adv_usd.iloc[0] else None,
                        data_status=S.DATA_STATUS, speed=a.speed, appetite=a.appetite)


_reg("markets.datasets", "Market dataset catalog: licences, provenance, checksums, coverage, quality and feed status", "market:read", NoArgs,
     lambda c, a: S.datasets())
_reg("markets.security", "Historical price history and statistics for one security vs SPY (adjusted, historical)", "market:read", TickerArgs,
     lambda c, a: S.security(a.ticker, a.start, a.end))
_reg("markets.compare", "Compare up to four securities over a period (normalised to 100)", "market:read", CompareArgs,
     lambda c, a: S.compare(a.tickers, a.start, a.end))
_reg("markets.overview", "Latest available market overview: SPY, sectors, breadth, regime", "market:read", NoArgs, lambda c, a: S.overview())
_reg("markets.regime", "Market regime and crash-risk level with the alarm's measured precision and recall", "market:read", NoArgs,
     lambda c, a: S.regime())
_reg("markets.news", "Point-in-time headlines for a ticker (untrusted text, injection-scanned)", "market:read", NewsArgs,
     lambda c, a: S.news(a.ticker, f"{a.as_of} 21:00" if a.as_of else None, a.k))
_reg("markets.model_report", "Model evaluation report: holdout metrics, gross vs net backtests, promotion decisions", "quant:read", NoArgs,
     lambda c, a: S.model_report())
_reg("markets.why_rejected", "Promotion decision and failed criteria for research models", "quant:read", RejectArgs,
     lambda c, a: S.why_rejected(a.model, a.horizon))
_reg("markets.evidence", "Point-in-time evidence pack for one security (features, research model score, regime, headlines)", "quant:read",
     TickerArgs, lambda c, a: S.evidence_pack(a.ticker, a.end))
_reg("markets.predictions", "Prediction Memory summary and recent ledger rows", "quant:read", NoArgs, lambda c, a: ledger_view.summary())
_reg("markets.risk", "Independent research risk assessment for a security under a speed/appetite profile", "market:read", RiskArgs, _risk)

MARKET_TOOLS = tuple(n for n in TOOLS.tools if n.startswith("markets."))


class MarketQ(BaseModel):
    model_config = {"extra": "forbid"}
    question: str = Field("", max_length=4000)
    months: int = Field(12, ge=1, le=24)
    language: str = Field("en", pattern=r"^(en|fr|es|hi|ta|ko)$")
    tickers: list[str] = Field(default_factory=list, max_length=4)
    start: str | None = Field(None, pattern=DAY)
    end: str | None = Field(None, pattern=DAY)
    speed: str = Field("swing", pattern=r"^(long_term|position|swing|intraday|swift)$")
    appetite: str = Field("moderate", pattern=r"^(conservative|moderate|aggressive)$")


def _p1(x):
    return None if x is None else round(x * 100, 1)


def _mspec(name, desc, roles, tools, **kw):
    return spec(name, "investment", "investment_supervisor", desc, roles, tools, MarketQ, data_classification="public",
                owner="Market Research AI Product Owner", version="1.0.0", timeout_s=kw.pop("timeout_s", 30), **kw)


def _tickers(ctx, q: MarketQ) -> list[str]:
    return q.tickers or S.resolve_tickers(q.question)


# ------------------------------------------------------------------ market data agent
@template("market_security")
def _t_sec(f):
    return (f"{f['name'] or f['ticker']} ({f['ticker']}) from {f['start']} to {f['end']}: total return {f['tr']}% "
            f"({f['cagr']}% a year), volatility {f['vol']}% a year, maximum drawdown {f['mdd']}%. SPY returned {f['spy_tr']}% over the same "
            f"period, so the difference was {f['xs']} percentage points. Historical data from {f['dataset']}, ending {f['end']}; not current prices.")


@template("market_compare")
def _t_cmp(f):
    parts = "; ".join(f"{x['ticker']} {x['tr']}% (max drawdown {x['mdd']}%)" for x in f["items"])
    return f"From {f['start']} to {f['end']}: {parts}. The strongest was {f['best']}. Historical, split- and dividend-adjusted data; not current prices."


@template("market_overview")
def _t_ov(f):
    return (f"Latest available session {f['as_of']} (historical, not today): SPY returned {f['r1y']}% over 1 year and {f['r3y']}% over 3 years. "
            f"{f['b200']}% of the 1,000-stock universe traded above its 200-session average. Regime: {f['regime']} with crash-risk level "
            f"{f['level']} (score {f['score']} of 4). Best sector over 1 year among S&P 500 members: {f['best_sector']} ({f['best_sector_r']}%).")


@REGISTRY.register(_mspec("market_data_agent", "Historical prices, comparisons and the market overview from the Kaggle research lake.", MKT_ROLES,
                          ["markets.security", "markets.compare", "markets.overview"]))
def market_data_agent(ctx, q: MarketQ):
    tk = _tickers(ctx, q)
    start, end = (q.start, q.end) if q.start or q.end else S.parse_period(q.question)
    if len(tk) >= 2:
        d = ctx.tool("markets.compare", tickers=tk, start=start, end=end)
        ok = [i for i in d["items"] if "error" not in i]
        items = [{"ticker": i["ticker"], "tr": _p1(i["stats"]["total_return"]), "mdd": _p1(i["stats"]["max_drawdown"]),
                  "vol": _p1(i["stats"]["volatility"])} for i in ok]
        facts = {"start": ok[0]["stats"]["start"], "end": ok[0]["stats"]["end"], "items": items,
                 "best": max(items, key=lambda x: x["tr"])["ticker"], "dataset": d["dataset_id"], "data_status": d["data_status"]}
        return _out(ctx, "market_data_agent", "market_compare", facts, ["market_compare"])
    if len(tk) == 1:
        d = ctx.tool("markets.security", ticker=tk[0], start=start, end=end)
        st, bm = d["stats"], d["benchmark"]["stats"]
        facts = {"ticker": d["ticker"], "name": d["name"], "sector": d["sector"], "start": st["start"], "end": st["end"],
                 "tr": _p1(st["total_return"]), "cagr": _p1(st["cagr"]), "vol": _p1(st["volatility"]), "mdd": _p1(st["max_drawdown"]),
                 "spy_tr": _p1(bm["total_return"]), "xs": _p1(st["total_return"] - bm["total_return"]), "dataset": d["dataset_id"],
                 "observations": st["observations"], "flagged_excluded": d["flagged_bars_excluded"], "data_status": d["data_status"]}
        return _out(ctx, "market_data_agent", "market_security", facts, ["market_price_history", "market_drawdown"])
    d = ctx.tool("markets.overview")
    best = d["sectors_1y_equal_weight_sp500_members"][0]
    facts = {"as_of": d["as_of"], "r1y": _p1(d["spy"]["return_1y"]), "r3y": _p1(d["spy"]["return_3y"]), "b200": _p1(d["breadth"]["share_above_200d"]),
             "regime": d["regime"]["regime"].replace("_", " "), "level": d["regime"]["level"], "score": d["regime"]["score"],
             "best_sector": best["sector"], "best_sector_r": _p1(best["return_1y"]), "data_status": d["data_status"]}
    return _out(ctx, "market_data_agent", "market_overview", facts, ["market_overview_spy", "market_sectors"])


# ------------------------------------------------------------------ regime agent
@template("market_regime")
def _t_rg(f):
    return (f"As of {f['as_of']} (historical) the market regime was {f['regime']} and the crash-risk level {f['level']} (score {f['score']} of 4): "
            f"20-session volatility {f['vol']}% a year ({f['vol_pct']}th percentile of the past year), SPY {f['trend']}% versus its 200-session "
            f"average and {f['dd']}% from its 1-year high. Track record: when this alarm read High or above, SPY fell at least 10% within "
            f"20 sessions {f['prec']}% of the time (base rate {f['base']}%), and it caught {f['rec']}% of such days.")


@REGISTRY.register(_mspec("market_regime_agent", "Explains the latest available market regime and the crash-risk alarm's measured track record.",
                          MKT_ROLES, ["markets.regime"]))
def market_regime_agent(ctx, q: MarketQ):
    d = ctx.tool("markets.regime")
    hi = next(e for e in d["evaluation"]["by_alarm_level"] if e["alarm_at"] == "High")
    i = d["inputs"]
    facts = {"as_of": d["as_of"], "regime": d["regime"].replace("_", " "), "level": d["level"], "score": d["score"],
             "vol": _p1(i["vol_20_annualised"]), "vol_pct": _p1(i["vol_percentile_1y"]), "trend": _p1(i["spy_vs_200d_mean"]),
             "dd": _p1(i["drawdown_from_1y_high"]), "prec": _p1(hi["precision"]), "rec": _p1(hi["recall"]),
             "base": _p1(d["evaluation"]["base_rate"]), "data_status": d["data_status"]}
    return _out(ctx, "market_regime_agent", "market_regime", facts, ["market_regime_history"])


# ------------------------------------------------------------------ quant research agent
@template("quant_report")
def _t_q(f):
    return (f"Verdict: {f['verdict']}. On the untouched holdout ({f['hold_start']} to {f['hold_end']}), the best 5-session model, {f['best']}, "
            f"had rank IC {f['ic']} (t = {f['ic_t']}), top-decile precision {f['prec']}% against a 10% base rate, gross Sharpe {f['gross']} and "
            f"net Sharpe {f['net']} after costs (95% interval {f['ci_lo']} to {f['ci_hi']}). Its long-only top decile returned {f['lo_xs']} percentage "
            f"points a year versus SPY after costs. {f['n_rejected']} of {f['n_models']} model-horizon candidates were rejected. Universe is "
            f"survivorship-biased; results are research, not advice.")


@REGISTRY.register(_mspec("quant_research_agent", "Reports model accuracy, gross vs net backtests and promotion decisions.", QUANT_ROLES,
                          ["markets.model_report", "markets.why_rejected"]))
def quant_research_agent(ctx, q: MarketQ):
    r = ctx.tool("markets.model_report")
    h = r["horizons"]["5"]
    best = h["best_by_ic"]
    m = h["models"][best]
    ci = m.get("net_sharpe_ci95") or [None, None]
    dec = [d for hh in r["horizons"].values() for d in hh["decisions"]]
    facts = {"verdict": r["verdict"], "best": best, "hold_start": h["split"]["holdout"]["start"], "hold_end": h["split"]["holdout"]["end"],
             "ic": round(m["ic_mean"], 4), "ic_t": round(m["ic_t"], 2) if m["ic_t"] is not None else None,
             "prec": _p1(m["top_decile_precision"]), "gross": round(m["gross_sharpe"], 2), "net": round(m["net_sharpe"], 2),
             "ci_lo": None if ci[0] is None else round(ci[0], 2), "ci_hi": None if ci[1] is None else round(ci[1], 2),
             "lo_xs": _p1(m["long_only_net_excess_vs_spy"]), "n_rejected": sum(not d["eligible"] for d in dec), "n_models": len(dec),
             "decisions": dec, "data_status": r["data_status"]}
    return _out(ctx, "quant_research_agent", "quant_report", facts, ["model_holdout_equity", "model_comparison"])


@template("quant_rejection")
def _t_rej(f):
    return f"{f['model']} for the {f['horizon']}-session horizon was {f['status']} because: {f['reasons']}. Overall verdict: {f['verdict']}."


@REGISTRY.register(_mspec("model_governance_agent", "Explains why a model was rejected or approved under the promotion criteria.", QUANT_ROLES,
                          ["markets.why_rejected"]))
def model_governance_agent(ctx, q: MarketQ):
    import re
    model = next((m for m in ("lightgbm", "xgboost", "ridge") if re.search(m, q.question, re.I)), "lightgbm")
    hz = re.search(r"\b(1|5|20)[- ]?(day|session)", q.question)
    d = ctx.tool("markets.why_rejected", model=model, horizon=hz.group(1) if hz else "5")
    dec = d["decisions"][0]
    facts = {"model": model, "horizon": dec["horizon"], "status": dec["status"].replace("_", " "),
             "reasons": "; ".join(dec["reasons"]) or "all criteria met", "verdict": d["verdict"], "criteria": d["criteria"]}
    return _out(ctx, "model_governance_agent", "quant_rejection", facts, ["model_comparison"])


# ------------------------------------------------------------------ news agent
@template("market_news")
def _t_news(f):
    if f["n"] == 0:
        return (f"No headlines for {f['ticker']} were available in the {f['window']} days to {f['as_of']}. Coverage for this ticker in the dataset runs "
                f"{f['first']} to {f['last']} ({f['total']} headlines). Missing headlines are not evidence that nothing happened.")
    return (f"{f['n']} headlines for {f['ticker']} were available in the {f['window']} days to {f['as_of']}: {f['summary']}. "
            f"{f['flagged']} contained instruction-like text and were neutralised. Single publisher family; headlines are context, not causes.")


@REGISTRY.register(_mspec("news_research_agent", "Point-in-time headline evidence for a security, with event types and injection screening.",
                          MKT_ROLES, ["markets.news"]))
def news_research_agent(ctx, q: MarketQ):
    tk = _tickers(ctx, q)
    if not tk:
        return _out(ctx, "news_research_agent", "market_news", {"ticker": "?", "n": 0, "window": 120, "as_of": str(S.last_session()),
                                                                 "first": "-", "last": "-", "total": 0}, [], ["no ticker recognised"])
    d = ctx.tool("markets.news", ticker=tk[0], as_of=q.end, k=8)
    cov = d["coverage"]
    facts = {"ticker": d["ticker"], "n": d["headlines_in_window"], "window": d["window_days"], "as_of": d["as_of"][:10],
             "summary": ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in sorted(d["event_counts"].items(), key=lambda kv: -kv[1])),
             "flagged": d["injection_flagged"], "first": (cov["first"] or "-")[:10], "last": (cov["last"] or "-")[:10],
             "total": cov["headlines_for_ticker"], "items": d["items"], "data_status": d["data_status"]}
    return _out(ctx, "news_research_agent", "market_news", facts, ["market_news_events"])


# ------------------------------------------------------------------ bull / bear / skeptic / aggregator
def _pack(ctx, q: MarketQ):
    tk = _tickers(ctx, q)
    if not tk:
        raise ValueError("no ticker recognised in the question")
    return ctx.tool("markets.evidence", ticker=tk[0], end=q.end)


def _claims_text(claims: list[dict]) -> str:
    return " ".join(f"({i + 1}) {c['claim']}" for i, c in enumerate(claims)) or "No claim met its evidence threshold."


@template("bull_case")
def _t_bull(f):
    return f"Bull researcher on {f['ticker']} as of {f['as_of']}: {f['text']}"


@template("bear_case")
def _t_bear(f):
    return f"Bear researcher on {f['ticker']} as of {f['as_of']}: {f['text']}"


@template("skeptic_case")
def _t_skep(f):
    return f"Skeptic on {f['ticker']}: {f['text']}"


def _role_agent(name: str, tmpl: str, fn):
    def run(ctx, q: MarketQ):
        ev = _pack(ctx, q)
        claims = fn(ev)
        facts = {"ticker": ev["ticker"], "as_of": ev["as_of"], "claims": claims, "text": _claims_text(claims), "data_status": ev["data_status"]}
        return _out(ctx, name, tmpl, facts, ["evidence_balance"])
    run.__name__ = name
    return run


REGISTRY.register(_mspec("bull_researcher_agent", "Argues the positive case strictly from point-in-time evidence, with citations.", QUANT_ROLES,
                         ["markets.evidence"]))(_role_agent("bull_researcher_agent", "bull_case", debate.bull_claims))
REGISTRY.register(_mspec("bear_researcher_agent", "Argues the negative case from the same evidence, with citations.", QUANT_ROLES,
                         ["markets.evidence"]))(_role_agent("bear_researcher_agent", "bear_case", debate.bear_claims))


@REGISTRY.register(_mspec("skeptic_agent", "Challenges stale data, survivorship, missing inputs and unsupported confidence.", QUANT_ROLES,
                          ["markets.evidence", "markets.model_report"]))
def skeptic_agent(ctx, q: MarketQ):
    ev = _pack(ctx, q)
    rep = ctx.tool("markets.model_report")
    claims = debate.skeptic_checks(ev, rep, datetime.now(timezone.utc).date())
    facts = {"ticker": ev["ticker"], "as_of": ev["as_of"], "claims": claims, "text": _claims_text(claims), "data_status": ev["data_status"]}
    return _out(ctx, "skeptic_agent", "skeptic_case", facts, ["evidence_balance"])


@template("evidence_summary")
def _t_agg(f):
    return (f"Evidence on {f['ticker']} as of {f['as_of']}: {f['n_bull']} bull points, {f['n_bear']} bear points and {f['n_skeptic']} skeptic checks, "
            f"citing {f['n_refs']} sources. Independent risk engine: {f['risk_status']} for a {f['speed']} / {f['appetite']} profile. {f['conclusion']}")


@REGISTRY.register(_mspec("evidence_aggregator_agent", "Combines bull, bear and skeptic evidence with attribution and the independent risk check.",
                          QUANT_ROLES, ["markets.evidence", "markets.model_report", "markets.risk"]))
def evidence_aggregator_agent(ctx, q: MarketQ):
    ev = _pack(ctx, q)
    rep = ctx.tool("markets.model_report")
    rk = ctx.tool("markets.risk", ticker=ev["ticker"], speed=q.speed, appetite=q.appetite)
    agg = debate.aggregate(ev, rep, rk, datetime.now(timezone.utc).date())
    facts = {"ticker": ev["ticker"], "as_of": ev["as_of"], "n_bull": len(agg["bull"]), "n_bear": len(agg["bear"]), "n_skeptic": len(agg["skeptic"]),
             "n_refs": len(agg["evidence_refs"]), "risk_status": rk["status"].replace("_", " "), "speed": q.speed, "appetite": q.appetite,
             "conclusion": agg["conclusion"], "aggregate": agg, "data_status": ev["data_status"]}
    return _out(ctx, "evidence_aggregator_agent", "evidence_summary", facts, ["evidence_balance"])


# ------------------------------------------------------------------ prediction memory + data intelligence
@template("prediction_memory")
def _t_pm(f):
    return (f"Prediction Memory holds {f['total']} forecasts ({f['replay']} historical replay, {f['forward']} forward). {f['resolved']} are resolved "
            f"with {f['acc']}% directional accuracy against the benchmark-relative outcome; {f['pending']} are pending. Hash chain: {f['chain']}. "
            f"Replay forecasts were recorded on a simulated clock over past data and are not forward tests.")


@REGISTRY.register(_mspec("prediction_memory_agent", "Summarises the immutable forecast ledger and how forecasts turned out.", QUANT_ROLES,
                          ["markets.predictions"]))
def prediction_memory_agent(ctx, q: MarketQ):
    d = ctx.tool("markets.predictions")
    g = d["groups"]
    rp, fw = g.get("mode:historical_replay", {}), g.get("mode:forward", {})
    resolved = rp.get("resolved", 0) + fw.get("resolved", 0)
    correct = (rp.get("correct", 0) + fw.get("correct", 0))
    facts = {"total": d["total"], "replay": rp.get("n", 0), "forward": fw.get("n", 0), "resolved": resolved,
             "acc": round(correct / resolved * 100, 1) if resolved else 0, "pending": rp.get("pending", 0) + fw.get("pending", 0),
             "chain": "verified" if d["chain"]["valid"] else "BROKEN", "groups": g}
    return _out(ctx, "prediction_memory_agent", "prediction_memory", facts, ["prediction_accuracy"])


@template("data_intelligence")
def _t_di(f):
    return (f"{f['n_ingested']} of {f['n_catalog']} catalogued Kaggle datasets are ingested. The primary price dataset holds {f['rows']} daily "
            f"bars for {f['tickers']} tickers from {f['start']} to {f['end']}, licence {f['licence']}, quality score {f['score']} of 100. "
            f"{f['dups']} duplicate files were skipped by checksum. Current feed: {f['feed']}.")


@REGISTRY.register(_mspec("data_intelligence_agent", "Explains which market datasets exist, their licences, coverage, quality and limits.",
                          MKT_ROLES, ["markets.datasets"]))
def data_intelligence_agent(ctx, q: MarketQ):
    d = ctx.tool("markets.datasets")
    p = next(x for x in d["datasets"] if x["dataset_id"] == catalog.PRIMARY)
    facts = {"n_ingested": sum(x["ingested"] for x in d["datasets"]), "n_catalog": len(d["datasets"]), "rows": f"{p['normalised']['rows']:,}",
             "tickers": f"{p['normalised']['tickers']:,}", "start": p["normalised"]["start"], "end": p["normalised"]["end"],
             "licence": p["kaggle_license"], "score": d["research_lake"]["quality"]["score"], "dups": f"{p['files']['duplicates_skipped']:,}",
             "feed": "disabled: " + " ".join(d["current_feed"]["reasons"]) if not d["current_feed"]["scheduler_enabled"] else "enabled"}
    return _out(ctx, "data_intelligence_agent", "data_intelligence", facts, ["dataset_coverage"])


MARKET_AGENTS = ("market_data_agent", "market_regime_agent", "quant_research_agent", "model_governance_agent", "news_research_agent",
                 "bull_researcher_agent", "bear_researcher_agent", "skeptic_agent", "evidence_aggregator_agent", "prediction_memory_agent",
                 "data_intelligence_agent")
_ = (date,)
