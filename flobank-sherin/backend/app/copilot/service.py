"""Sherin copilot: answers financial and engineering questions from application records.

Every figure in an answer comes from app.finance.engine (the same functions that feed the dashboard charts), so a
chat answer and the chart it links to can never disagree. Intent detection is deterministic. If the local Qwen
model is available it is used only for open questions outside the known intents, with the engine's figures as
context, and the answer is labelled as model-generated.
"""
from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import catalog as C
from app import models as M
from app.agents import llm
from app.approvals import service as approvals
from app.config import get_settings
from app.finance import engine as E

SUGGESTIONS = [
    "Sherin, how much money did you cost us this month?",
    "How much revenue did FLO Bank generate?",
    "What is your net economic contribution?",
    "Which agent is consuming the most tokens?",
    "Show the most expensive Azure DevOps workflows.",
    "Compare your work against equivalent human effort.",
    "Which portfolio investments require manager approval?",
    "Show the last 30 days of AI costs and savings.",
    "Why did our AI expenditure increase?",
    "How can we reduce operating costs without compromising quality?",
]

SYMBOL = {"USD": "$", "INR": "₹", "CAD": "C$"}


def money(v: float | None, cur: str) -> str:
    if v is None:
        return "n/a"
    s = SYMBOL.get(cur, "")
    a = abs(v)
    if a >= 1e9:
        t = f"{a / 1e9:,.2f}B"
    elif a >= 1e6:
        t = f"{a / 1e6:,.2f}M"
    elif a >= 1e4:
        t = f"{a / 1e3:,.1f}K"
    else:
        t = f"{a:,.2f}"
    return f"{'-' if v < 0 else ''}{s}{t}"


def pct(v) -> str:
    return "n/a" if v is None else f"{v:+.1f}%"


def _period_from_text(text: str, end_month: str, end_day: dt.date) -> tuple[E.Period, str]:
    t = text.lower()
    m = re.search(r"last (\d+) days", t)
    if m:
        n = int(m.group(1))
        return E.Period(end_day - dt.timedelta(days=n - 1), end_day, "custom", f"last {n} days to {end_day.isoformat()}"), "custom"
    if "today" in t:
        return E.Period(end_day, end_day, "custom", f"{end_day.isoformat()} (latest day in the ledger)"), "day"
    if "last month" in t:
        p = E.prior_period(E.resolve_period("month", end_month))
        return p, "month"
    if "quarter" in t:
        return E.resolve_period("quarter", end_month), "quarter"
    if re.search(r"\b(this year|ytd|year to date|annual)\b", t):
        p = E.resolve_period("year", end_month)
        return E.Period(p.start, end_day, "custom", f"{p.start.year} year to date"), "custom"
    if re.search(r"12 months|twelve months|ttm|past year", t):
        return E.resolve_period("ttm", end_month), "ttm"
    return E.resolve_period("month", end_month), "month"


INTENTS: list[tuple[str, str]] = [
    ("why_spend", r"why .*(spend|spent|expenditure|cost).*(increase|more|up|rise|higher)|why did (sherin|you|our ai) spend|cost driver"),
    ("reduce_costs", r"reduce .*(cost|spend|expenditure)|cut .*cost|save money|optimi[sz]e .*cost|without compromising"),
    ("approvals", r"(require|need|pending|awaiting).*(approval|sign-?off)|manager approval|approval inbox"),
    ("guardian", r"\bTP-\d+\b|guardian|pre-?trade|investment (judg|decision)|block(ed)? trade"),
    ("tokens", r"token"),
    ("azure_expensive", r"(expensive|costly|cost).*(azure|devops|pipeline|workflow)|azure devops workflows"),
    ("human_vs_ai", r"human (effort|equivalent|baseline)|compare .*(human|people)|human vs|versus human"),
    ("net_contribution", r"net (economic )?(contribution|benefit|value)|\broi\b|return on investment|economic contribution|worth it"),
    ("last_n_days", r"last \d+ days"),
    ("forecast", r"forecast|projection|break-?even|next (year|quarter|12 months)|scenario"),
    ("department", r"department|which team|by team"),
    ("agent_productivity", r"agent(s)? (productiv|efficien|perform)|most efficient agent|least efficient|which agents? .*(efficient|productive)"),
    ("ai_cost", r"(how much|what).*(you|sherin|ai).*(cost|spend|spent)|ai (cost|spend|expenditure)|cost us|operating cost of (sherin|ai)"),
    ("bank_revenue", r"revenue|income|earn|profit|how much money did (we|flo)"),
    ("budget", r"budget"),
    ("fx", r"exchange rate|\bfx\b|currency"),
    ("harness", r"^(run|start|fix|debug|diagnose|repair|reconcile|evaluate|scan|review)\b"),
]


def detect_intent(text: str) -> str:
    t = text.strip().lower()
    for name, pat in INTENTS:
        if re.search(pat, t, re.I):
            return name
    return "general"


class Ctx:
    def __init__(self, db: Session, currency: str, dc: str):
        s = get_settings()
        self.db, self.dc, self.cur = db, dc, currency.upper()
        self.fx = E.fx_for(db, self.cur)
        b = E.data_bounds(db, dc)
        self.end_day = dt.date.fromisoformat(b["ledger_end"]) if b["ledger_end"] else dt.date.today()
        self.end_month = self.end_day.strftime("%Y-%m") if b["ledger_end"] else s.demo_end_month
        self.m = lambda v: money(v, self.cur)


def _base(intent: str, ctx: Ctx, text: str, p: E.Period, **kw) -> dict:
    out = {"intent": intent, "text": text, "charts": [], "links": [], "approvals": [], "diff": None, "followups": [], "sources": [],
           "data_class": ctx.dc, "currency": ctx.cur, "fx": ctx.fx.as_dict(), "period": p.as_dict(), "activity": []}
    out.update(kw)
    if ctx.dc == "synthetic":
        out["text"] += "\n\n_All figures are synthetic demonstration data, not FLO Bank's actual business performance._"
    return out


def answer(db: Session, question: str, currency: str = "USD", dc: str = "synthetic") -> dict:
    ctx = Ctx(db, currency, dc)
    intent = detect_intent(question)
    p, _ = _period_from_text(question, ctx.end_month, ctx.end_day)
    handler = HANDLERS.get(intent, h_general)
    res = handler(ctx, question, p)
    res["activity"] = [{"step": 1, "tool": "intent.detect", "detail": f"intent = {intent}"},
                       {"step": 2, "tool": "period.resolve", "detail": p.label}] + res.get("activity", [])
    return res


# ---------------------------------------------------------------------------------------------- handlers
def h_ai_cost(ctx: Ctx, q: str, p: E.Period) -> dict:
    k = E.kpis(ctx.db, p, ctx.fx, ctx.dc)
    card = next(c for c in k["cards"] if c["key"] == "ai_cost")
    br = E.ai_cost_breakdown(ctx.db, p, ctx.fx, ctx.dc)
    top = br["categories"][:3]
    text = (f"In **{p.label}** I cost FLO Bank **{ctx.m(card['value'])}** in total (Sherin AI operating cost, including human review and "
            f"allocated implementation). That is {pct(card['mom_pct'])} vs the prior period"
            + (f" and {pct(card['budget_variance_pct'])} vs budget ({ctx.m(card['budget'])}, {card['budget_utilization_pct']}% utilised)." if card["budget"] else ".")
            + "\n\nLargest cost lines:\n" + "\n".join(f"- **{c['label']}**: {ctx.m(c['value'])} ({c['share_pct']}%)" for c in top))
    return _base("ai_cost", ctx, text, p,
                 charts=[{"id": "ai_cost_breakdown", "kind": "pie", "title": "Sherin AI cost breakdown",
                          "labels": [c["label"] for c in br["categories"]], "values": [c["value"] for c in br["categories"]]}],
                 links=[{"label": "Open Graph D - AI cost breakdown", "route": "/#graph-d"}, {"label": "AI Savings", "route": "/savings"}],
                 followups=["Why did our AI expenditure increase?", "How can we reduce operating costs without compromising quality?"],
                 sources=["ai_cost_records", "budgets"], activity=[{"step": 3, "tool": "finance.kpis", "detail": "ai_cost card"},
                                                                   {"step": 4, "tool": "finance.ai_cost_breakdown", "detail": f"{len(br['categories'])} categories"}])


def h_bank_revenue(ctx: Ctx, q: str, p: E.Period) -> dict:
    k = {c["key"]: c for c in E.kpis(ctx.db, p, ctx.fx, ctx.dc)["cards"]}
    rev, opex, prof = k["bank_revenue"], k["bank_opex"], k["operating_profit"]
    dd = E.kpi_drilldown(ctx.db, "bank_revenue", p, ctx.fx, ctx.dc)
    text = (f"FLO Bank generated **{ctx.m(rev['value'])}** of revenue in **{p.label}** ({pct(rev['mom_pct'])} vs prior period"
            + (f", {pct(rev['budget_variance_pct'])} vs budget" if rev["budget"] else "") + f"). Operating expenditure was {ctx.m(opex['value'])}, "
            f"giving an operating profit of **{ctx.m(prof['value'])}**.\n\nRevenue by line:\n"
            + "\n".join(f"- {r['label']}: {ctx.m(r['value'])}" for r in sorted(dd["rows"], key=lambda r: -r["value"]))
            + "\n\nRevenue excludes assets under management and unrealised portfolio returns.")
    ts = E.revenue_vs_expenditure(ctx.db, E.resolve_period("ttm", ctx.end_month), "month", ctx.fx, ctx.dc)
    return _base("bank_revenue", ctx, text, p,
                 charts=[{"id": "rev_vs_exp", "kind": "line", "title": "Revenue vs expenditure (12 months)", "x": ts["x"],
                          "series": {"Bank revenue": ts["series"]["bank_revenue"], "Bank opex": ts["series"]["bank_opex"],
                                     "Operating profit": ts["series"]["operating_profit"]}}],
                 links=[{"label": "Open Graph A - Revenue vs Expenditure", "route": "/#graph-a"}],
                 followups=["What is your net economic contribution?", "Show the revenue forecast."], sources=["ledger_lines", "budgets"],
                 activity=[{"step": 3, "tool": "finance.kpis", "detail": "bank revenue, opex, profit"}])


def h_net(ctx: Ctx, q: str, p: E.Period) -> dict:
    c = E.contribution(ctx.db, p, ctx.fx, ctx.dc)
    s = c["summary"]
    wf = c["waterfall"]
    text = (f"My net economic contribution in **{p.label}** was **{ctx.m(s['net_benefit'])}**, an AI ROI of **{s['roi_pct']}%** "
            f"(net benefit / total Sherin AI cost).\n\nHow it is built:\n" + "\n".join(f"- {w['label']}: {ctx.m(w['value'])}" for w in wf)
            + f"\n\nAttributed revenue of {ctx.m(s['attributed_revenue'])} is part of fee income, so only its incremental profit "
            f"({ctx.m(s['incremental_profit'])}) is counted. Cost avoidance is an estimate of labour capacity released, not cash; "
            f"{ctx.m(s['realized_savings'])} of it has been realized in budgets and is not added again.")
    return _base("net_contribution", ctx, text, p,
                 charts=[{"id": "net_waterfall", "kind": "waterfall", "title": "Net AI economic benefit", "labels": [w["label"] for w in wf],
                          "values": [w["value"] for w in wf], "measures": [w["measure"] for w in wf]}],
                 links=[{"label": "Open Graph B - AI financial contribution", "route": "/#graph-b"}, {"label": "AI Savings", "route": "/savings"}],
                 followups=["Compare your work against equivalent human effort.", "Show the forecast and break-even."],
                 sources=["agent_tasks", "ai_cost_records", "revenue_attribution", "human_baselines"],
                 activity=[{"step": 3, "tool": "finance.contribution", "detail": "waterfall"}])


def h_tokens(ctx: Ctx, q: str, p: E.Period) -> dict:
    t = E.token_analytics(ctx.db, p, "day", ctx.fx, ctx.dc)
    pa = t["per_agent"]
    if not pa:
        return _base("tokens", ctx, f"No token usage is recorded for {p.label}.", p)
    top = pa[0]
    tot = t["totals"]
    lq, pd = t["providers"].get("local_qwen", {}), t["providers"].get("paid_api", {})
    text = (f"The **{top['label']}** consumed the most tokens in **{p.label}**: **{top['tokens']:,}** tokens across {top['tasks']} tasks "
            f"({top['tokens_per_task']:,} per task), costing {ctx.m(top['cost'])}.\n\nIn total {tot['tokens']:,} tokens were used "
            f"({tot['tokens_per_successful_task'] or 0:,} per verified task). Local Qwen: {lq.get('total', 0):,} tokens, {ctx.m(lq.get('cost'))} "
            f"(compute and electricity, no API charge). Paid model: {pd.get('total', 0):,} tokens, {ctx.m(pd.get('cost'))}.")
    return _base("tokens", ctx, text, p,
                 charts=[{"id": "tokens_by_agent", "kind": "bar", "title": "Tokens by agent", "x": [r["label"] for r in pa[:10]],
                          "series": {"Tokens": [r["tokens"] for r in pa[:10]]}}],
                 links=[{"label": "Open Token Analytics", "route": "/tokens"}, {"label": "Graph E", "route": "/#graph-e"}],
                 followups=["How can we reduce operating costs without compromising quality?"], sources=["token_usage"],
                 activity=[{"step": 3, "tool": "tokens.read", "detail": f"{len(pa)} agents"}])


def h_azure(ctx: Ctx, q: str, p: E.Period) -> dict:
    t = M.AgentTask
    wfc = t.cost_model + t.cost_compute + t.cost_infra + t.cost_tooling + t.cost_human_review + t.cost_rework
    rows = ctx.db.execute(select(t.id, t.title, t.agent, t.created_at, wfc.label("cost"), t.duration_s, t.human_review_min, t.verified,
                                 t.baseline_hours, t.baseline_rate_usd)
                          .where(t.department == "azure_devops", t.data_class == ctx.dc, E._between(t.created_at, p))
                          .order_by(wfc.desc()).limit(8)).all()
    if not rows:
        return _base("azure_expensive", ctx, f"No Azure DevOps workflows are recorded for {p.label}.", p)
    lines = []
    table = []
    for r in rows:
        base = float(Decimal(r.baseline_hours) * Decimal(r.baseline_rate_usd))
        lines.append(f"- **{r.id}** {r.title} ({C.AGENTS[r.agent]['label']}): {ctx.m(ctx.fx.conv(r.cost))} - "
                     f"{r.duration_s / 60:.0f} min agent time, {float(r.human_review_min):.0f} min human review; human baseline {ctx.m(ctx.fx.conv(base))}"
                     + ("" if r.verified else " _(not verified)_"))
        table.append({"Task": r.id, "Workflow": r.title, "Agent": C.AGENTS[r.agent]["label"], "Cost": ctx.fx.conv(r.cost),
                      "Agent min": round(r.duration_s / 60), "Review min": float(r.human_review_min), "Baseline": ctx.fx.conv(base), "Verified": r.verified})
    text = f"The most expensive Azure DevOps workflows in **{p.label}** (full AI-assisted cost incl. human review and rework):\n\n" + "\n".join(lines)
    return _base("azure_expensive", ctx, text, p, charts=[{"id": "azure_top", "kind": "table", "title": "Most expensive Azure DevOps workflows", "rows": table}],
                 links=[{"label": "Open Azure DevOps", "route": "/azure"}], followups=["Why did our AI expenditure increase?"], sources=["agent_tasks"],
                 activity=[{"step": 3, "tool": "sql.agent_tasks", "detail": "department = azure_devops, order by workflow cost"}])


def h_human_vs_ai(ctx: Ctx, q: str, p: E.Period) -> dict:
    h = E.human_vs_ai(ctx.db, p, ctx.fx, ctx.dc)
    rows = h["rows"]
    tot_h = sum(r["human_only_total"] for r in rows)
    tot_a = sum(r["ai_assisted_total"] for r in rows)
    text = (f"For verified work in **{p.label}**, the equivalent human-only effort would have cost **{ctx.m(tot_h)}**; "
            f"the AI-assisted workflows cost **{ctx.m(tot_a)}** including human review, rework and failed attempts.\n\n"
            + "\n".join(f"- **{r['label']}**: human {ctx.m(r['human_only_per_task'])}/task vs AI-assisted {ctx.m(r['ai_assisted_per_task'])}/task "
                        f"({r['verified_tasks']} verified)" for r in rows)
            + "\n\nHuman baselines are configured synthetic assumptions (editable in Settings), not measurements.")
    return _base("human_vs_ai", ctx, text, p,
                 charts=[{"id": "human_vs_ai", "kind": "bar", "title": "Human-only vs AI-assisted cost per task", "x": [r["label"] for r in rows],
                          "series": {"Human-only": [r["human_only_per_task"] for r in rows], "AI-assisted": [r["ai_assisted_per_task"] for r in rows]}}],
                 links=[{"label": "Open Graph C - Human vs AI", "route": "/#graph-c"}], followups=["What is your net economic contribution?"],
                 sources=["agent_tasks", "human_baselines"], activity=[{"step": 3, "tool": "finance.human_vs_ai", "detail": f"{len(rows)} workflows"}])


def h_approvals(ctx: Ctx, q: str, p: E.Period) -> dict:
    from app.guardian import engine as G
    props = ctx.db.scalars(select(M.TradeProposal).order_by(M.TradeProposal.id)).all()
    lines, cards = [], []
    for pr in props:
        r = G.evaluate(ctx.db, pr)
        need = "manager approval required" if r["decision"] in ("PASS", "REVIEW") else ("cannot be approved - mandatory block" if r["decision"] == "BLOCK" else "needs data before approval")
        lines.append(f"- **{pr.id}** {pr.side} {pr.issuer} ({ctx.m(ctx.fx.conv(pr.notional_usd))}, {pr.portfolio_id}): Guardian **{r['decision']}** - {need}"
                     + (" (material: risk officer sign-off also required)" if r["material"] and r["decision"] in ("PASS", "REVIEW") else ""))
    for a in approvals.inbox(ctx.db, "open")[:6]:
        cards.append(a)
    text = ("Every investment action proposed through Sherin needs **SHERIN_MANAGER** approval; material trades also need the **RISK_OFFICER**. "
            "A Guardian PASS is not authorization to trade, and a BLOCK cannot be approved by anyone.\n\n" + "\n".join(lines))
    return _base("approvals", ctx, text, p, approvals=cards, links=[{"label": "Open Manager Approval Center", "route": "/approvals"},
                                                                   {"label": "Investment Judgment Center", "route": "/guardian"}],
                 followups=["Evaluate TP-1001 with Guardian.", "Why was TP-1002 blocked?"], sources=["trade_proposals", "positions", "portfolios", "approvals"],
                 activity=[{"step": 3, "tool": "guardian.evaluate", "detail": f"{len(props)} proposals"}, {"step": 4, "tool": "approvals.inbox", "detail": f"{len(cards)} open"}])


def h_guardian(ctx: Ctx, q: str, p: E.Period) -> dict:
    from app.guardian import engine as G
    m = re.search(r"TP-\d+", q, re.I)
    if not m:
        return h_approvals(ctx, q, p)
    pr = ctx.db.get(M.TradeProposal, m.group(0).upper())
    if pr is None:
        return _base("guardian", ctx, f"I could not find trade proposal {m.group(0)}.", p)
    r = G.evaluate(ctx.db, pr)
    fails = [c for c in r["checks"] if c["status"] != "PASS"]
    text = (f"Guardian decision for **{pr.id}** ({pr.side} {pr.issuer}, {ctx.m(ctx.fx.conv(pr.notional_usd))}): **{r['decision']}**. {r['meaning']}\n\n"
            + ("\n".join(f"- {c['name']}: **{c['status']}** - {c['detail']}" for c in fails) if fails else "- All configured controls passed."))
    return _base("guardian", ctx, text, p,
                 charts=[{"id": "guardian_exposure", "kind": "bar", "title": "Sector exposure pre/post trade (%)", "x": [e["sector"] for e in r["exposures"]["by_sector"]],
                          "series": {"Pre-trade": [e["pre_pct"] for e in r["exposures"]["by_sector"]], "Post-trade": [e["post_pct"] for e in r["exposures"]["by_sector"]]}}],
                 links=[{"label": "Open Investment Judgment Center", "route": f"/guardian?proposal={pr.id}"}], sources=["trade_proposals", "positions"],
                 activity=[{"step": 3, "tool": "guardian.evaluate", "detail": f"{len(r['checks'])} controls"}])


def h_last_n(ctx: Ctx, q: str, p: E.Period) -> dict:
    ts = E.revenue_vs_expenditure(ctx.db, p, "day", ctx.fx, ctx.dc)
    e = E.economics(ctx.db, p, ctx.dc)
    daily_av = {}
    t = M.AgentTask
    base = t.baseline_hours * t.baseline_rate_usd
    wfc = t.cost_model + t.cost_compute + t.cost_infra + t.cost_tooling + t.cost_human_review + t.cost_rework
    from sqlalchemy import case, func
    for d, v in ctx.db.execute(select(func.date(t.created_at), func.sum(case((t.verified.is_(True), base - wfc), else_=0)))
                               .where(E._between(t.created_at, p), t.data_class == ctx.dc).group_by(func.date(t.created_at))).all():
        daily_av[str(d)] = ctx.fx.conv(v)
    text = (f"Over the **{p.label}**: Sherin AI cost **{ctx.m(ctx.fx.conv(e['ai']['total']))}** "
            f"({ctx.m(ctx.fx.conv(e['ai']['total'] / p.days))}/day) and produced estimated cost avoidance of **{ctx.m(ctx.fx.conv(e['cost_avoidance']))}** "
            f"on {e['verified_tasks']} verified tasks. Net economic benefit: **{ctx.m(ctx.fx.conv(e['net_benefit']))}**.")
    return _base("last_n_days", ctx, text, p,
                 charts=[{"id": "cost_savings_daily", "kind": "line", "title": "Daily AI cost vs estimated savings", "x": ts["x"],
                          "series": {"AI cost (total)": ts["series"]["ai_cost_total"], "Estimated savings (verified)": [daily_av.get(x, 0) for x in ts["x"]]}}],
                 links=[{"label": "Open AI Savings", "route": "/savings"}, {"label": "Token Analytics", "route": "/tokens"}],
                 followups=["Why did our AI expenditure increase?"], sources=["ai_cost_records", "agent_tasks"],
                 activity=[{"step": 3, "tool": "finance.timeseries", "detail": "daily"}])


def h_why(ctx: Ctx, q: str, p: E.Period) -> dict:
    if p.days == 1:
        base = E.Period(p.start - dt.timedelta(days=7), p.start - dt.timedelta(days=1), "custom", "previous 7 days")
    else:
        base = E.prior_period(p)
    d = E.cost_drivers(ctx.db, p, base, ctx.fx, ctx.dc)
    tot = d["total_per_day"]
    up = [r for r in d["by_category"] if r["delta_per_day"] > 0][:4]
    ag = [r for r in d["by_agent"] if r["delta_per_day"] > 0][:3]
    v = d["volume"]
    direction = "increased" if tot["delta"] > 0 else "decreased"
    text = (f"AI spend {direction} from {ctx.m(tot['baseline'])}/day ({base.label}) to **{ctx.m(tot['current'])}/day** ({p.label}), {pct(tot['delta_pct'])}.\n\n"
            f"**Cost drivers (per day):**\n" + ("\n".join(f"- {r['label']}: {ctx.m(r['baseline_per_day'])} -> {ctx.m(r['current_per_day'])} ({pct(r['delta_pct'])})" for r in up) or "- No category increased.")
            + "\n\n**Agents with the largest increase:**\n" + ("\n".join(f"- {r['label']}: +{ctx.m(r['delta_per_day'])}/day" for r in ag) or "- none")
            + f"\n\n**Volume:** {v['tasks_per_day_baseline']} -> {v['tasks_per_day_current']} tasks/day; tokens {v['tokens_per_day_baseline']:,} -> {v['tokens_per_day_current']:,}/day; "
            f"paid-model token share {v['paid_token_share_baseline_pct']}% -> {v['paid_token_share_current_pct']}%; retries/task {v['retries_per_task_baseline']} -> {v['retries_per_task_current']}.")
    return _base("why_spend", ctx, text, p,
                 charts=[{"id": "cost_drivers", "kind": "bar", "title": "Change in AI cost per day by category", "x": [r["label"] for r in d["by_category"]],
                          "series": {"Delta per day": [r["delta_per_day"] for r in d["by_category"]]}}],
                 links=[{"label": "Open System Metrics", "route": "/metrics"}, {"label": "Graph D - cost breakdown", "route": "/#graph-d"}],
                 followups=["How can we reduce operating costs without compromising quality?"], sources=["ai_cost_records", "token_usage", "agent_tasks"],
                 activity=[{"step": 3, "tool": "finance.cost_drivers", "detail": f"{p.label} vs {base.label}"}])


def h_reduce(ctx: Ctx, q: str, p: E.Period) -> dict:
    ta = E.token_analytics(ctx.db, p, "month", ctx.fx, ctx.dc)
    ap = E.agent_productivity(ctx.db, p, ctx.fx, ctx.dc)
    br = {c["category"]: c for c in E.ai_cost_breakdown(ctx.db, p, ctx.fx, ctx.dc)["categories"]}
    lq, pdp = ta["providers"].get("local_qwen", {}), ta["providers"].get("paid_api", {})
    recs = []
    if pdp.get("cost_per_million") and lq.get("cost_per_million") is not None and pdp["total"]:
        shift = 0.25 * pdp["total"]
        saving = shift / 1e6 * (pdp["cost_per_million"] - lq["cost_per_million"])
        recs.append(f"**Route 25% more paid-model tokens to local Qwen** for agents whose quality pass rate stays >= 95% on local inference: "
                    f"about {ctx.m(saving)} per period at observed cost per million tokens ({ctx.m(pdp['cost_per_million'])} paid vs {ctx.m(lq['cost_per_million'])} local). "
                    "Gate it with the Independent Verification Agent's pass rate per agent.")
    hr = br.get("human_review")
    if hr:
        recs.append(f"**Human review is {hr['share_pct']}% of AI cost** ({ctx.m(hr['value'])}). Reduce rework rather than review: target the agents with the "
                    f"most rework hours; do not remove review on material actions.")
    worst = sorted([r for r in ap["rows"] if r["tasks"] >= 10], key=lambda r: (r["quality_pass_rate"] or 100))[:2]
    for r in worst:
        recs.append(f"**{r['label']}**: quality pass rate {r['quality_pass_rate']}%, {r['retries']} retries. Failed attempts are unrecovered cost; "
                    f"improve its tool prompts/tests before scaling volume.")
    mt = br.get("maintenance")
    if mt:
        recs.append(f"**Platform overhead** (maintenance {ctx.m(mt['value'])}) is fixed; it falls per task as verified volume grows.")
    text = (f"Options to reduce Sherin's operating cost in **{p.label}** without lowering quality (estimates from recorded data):\n\n" + "\n".join(f"{i}. {r}" for i, r in enumerate(recs, 1))
            + "\n\nNone of these remove human approval for material investment actions, production deployments or sensitive data changes.")
    return _base("reduce_costs", ctx, text, p, links=[{"label": "Agent productivity (Graph G)", "route": "/#graph-g"}, {"label": "Token Analytics", "route": "/tokens"}],
                 sources=["token_usage", "agent_tasks", "ai_cost_records"], followups=["Which agent is consuming the most tokens?"],
                 activity=[{"step": 3, "tool": "tokens.read", "detail": "provider cost per million"}, {"step": 4, "tool": "finance.agent_productivity", "detail": "quality vs retries"}])


def h_forecast(ctx: Ctx, q: str, p: E.Period) -> dict:
    f = E.forecast(ctx.db, ctx.end_month, ctx.fx, ctx.dc)
    if not f.get("available"):
        return _base("forecast", ctx, f.get("reason", "Forecast unavailable."), p)
    sc = f["scenarios"]
    text = ("**Scenario forecast (12 months)** - projections, not guarantees.\n\n" + "\n".join(
        f"- **{v['label']}**: month-12 AI opex {ctx.m(v['series'][-1]['ai_opex'])}, estimated savings {ctx.m(v['series'][-1]['estimated_savings'])}, "
        f"net benefit {ctx.m(v['series'][-1]['net_benefit'])}; break-even vs implementation capex: {v['breakeven_month'] or 'not within horizon'}" for v in sc.values())
        + f"\n\nAssumptions: task growth {f['assumptions']['task_growth_per_month_pct']}%/month, verification rate {f['assumptions']['verification_rate_pct']}%, "
        f"variable AI cost {ctx.m(f['assumptions']['variable_ai_cost_per_task'])}/task. {f['disclaimer']}")
    return _base("forecast", ctx, text, p, links=[{"label": "Open Graph F - Forecast", "route": "/#graph-f"}], sources=["ledger_lines", "agent_tasks", "ai_cost_records"],
                 charts=[{"id": "forecast", "kind": "line", "title": "Net benefit forecast by scenario", "x": [s["month"] for s in sc["base"]["series"]],
                          "series": {v["label"]: [s["net_benefit"] for s in v["series"]] for v in sc.values()}}])


def h_department(ctx: Ctx, q: str, p: E.Period) -> dict:
    d = E.department_value(ctx.db, p, ctx.fx, ctx.dc)
    rows = sorted(d["rows"], key=lambda r: -r["financial_impact"])
    text = f"Financial value by department in **{p.label}**:\n\n" + "\n".join(
        f"- **{r['label']}**: {ctx.m(r['financial_impact'])} impact, {r['hours_avoided']:,.0f} hours avoided ({r['productivity_gain_pct']}% productivity gain)" for r in rows)
    return _base("department", ctx, text, p, links=[{"label": "Open Graph H", "route": "/#graph-h"}], sources=["agent_tasks", "revenue_attribution"],
                 charts=[{"id": "dept", "kind": "bar", "title": "Financial impact by department", "x": [r["label"] for r in rows], "series": {"Impact": [r["financial_impact"] for r in rows]}}])


def h_agents(ctx: Ctx, q: str, p: E.Period) -> dict:
    a = E.agent_productivity(ctx.db, p, ctx.fx, ctx.dc)["rows"]
    text = f"Agent economics for **{p.label}** (ranked by net estimated savings):\n\n" + "\n".join(
        f"- **{r['label']}**: {r['completed']} verified tasks, {ctx.m(r['cost_per_successful_task'])}/successful task, quality {r['quality_pass_rate']}%, net {ctx.m(r['net_estimated_savings'])}" for r in a)
    return _base("agent_productivity", ctx, text, p, links=[{"label": "Open Graph G", "route": "/#graph-g"}, {"label": "Agent Harness", "route": "/harness"}], sources=["agent_tasks", "token_usage"])


def h_budget(ctx: Ctx, q: str, p: E.Period) -> dict:
    k = {c["key"]: c for c in E.kpis(ctx.db, p, ctx.fx, ctx.dc)["cards"]}
    lines = [f"- {k[x]['label']}: {ctx.m(k[x]['value'])} vs budget {ctx.m(k[x]['budget'])} ({k[x]['budget_utilization_pct']}% utilised)" for x in ("bank_revenue", "bank_opex", "ai_cost") if k[x]["budget"]]
    return _base("budget", ctx, f"Budget position for **{p.label}**:\n\n" + "\n".join(lines), p, links=[{"label": "Financial Command Center", "route": "/"}], sources=["budgets"])


def h_fx(ctx: Ctx, q: str, p: E.Period) -> dict:
    rows = ctx.db.scalars(select(M.FxRate).order_by(M.FxRate.as_of.desc()).limit(4)).all()
    text = "Current exchange rates (base USD):\n\n" + "\n".join(f"- USD/{r.quote}: {float(r.rate):.4f} - {r.source}, as of {r.as_of:%Y-%m-%d} ({r.data_class})" for r in rows)
    return _base("fx", ctx, text, p, links=[{"label": "Settings - currency", "route": "/settings"}], sources=["fx_rates"])


def h_harness(ctx: Ctx, q: str, p: E.Period) -> dict:
    return _base("harness", ctx, "Starting an agent run for this request. Follow its progress in the agent graph.", p, start_run=True,
                 links=[{"label": "Open Agent Harness", "route": "/harness"}])


def h_general(ctx: Ctx, q: str, p: E.Period) -> dict:
    e = E.economics(ctx.db, p, ctx.dc)
    facts = (f"Period {p.label}: bank revenue {ctx.m(ctx.fx.conv(e['bank']['revenue']))}, bank opex {ctx.m(ctx.fx.conv(e['bank']['opex']))}, "
             f"Sherin AI cost {ctx.m(ctx.fx.conv(e['ai']['total']))}, estimated cost avoidance {ctx.m(ctx.fx.conv(e['cost_avoidance']))}, "
             f"net AI benefit {ctx.m(ctx.fx.conv(e['net_benefit']))}, verified tasks {e['verified_tasks']}.")
    g = llm.generate(f"Facts from FLO Bank's records ({ctx.dc} data):\n{facts}\n\nQuestion: {q}\nAnswer briefly using only these facts. If they do not answer the question, say so.",
                     system="You are Sherin, FLO Bank's AI. Never invent figures.", max_tokens=350)
    if g:
        text = g["text"].strip() + f"\n\n_Model-generated narrative ({g['model']}, {g['input_tokens'] + g['output_tokens']} tokens). Figures: {facts}_"
    else:
        text = ("I answer from FLO Bank's records. I did not recognise that question, and the local Qwen model is not available for open questions. "
                f"Here is the current position: {facts}\n\nTry one of the suggested questions.")
    return _base("general", ctx, text, p, followups=SUGGESTIONS[:4], links=[{"label": "Financial Command Center", "route": "/"}], sources=["ledger_lines", "ai_cost_records", "agent_tasks"])


HANDLERS = {"ai_cost": h_ai_cost, "bank_revenue": h_bank_revenue, "net_contribution": h_net, "tokens": h_tokens, "azure_expensive": h_azure,
            "human_vs_ai": h_human_vs_ai, "approvals": h_approvals, "guardian": h_guardian, "last_n_days": h_last_n, "why_spend": h_why,
            "reduce_costs": h_reduce, "forecast": h_forecast, "department": h_department, "agent_productivity": h_agents, "budget": h_budget,
            "fx": h_fx, "harness": h_harness, "general": h_general}
