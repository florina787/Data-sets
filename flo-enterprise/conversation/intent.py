"""Deterministic intent classification for the conversational workspace (classifier `flo-intent-rules/1.0`).

The classifier turns a message plus conversation state into a structured Intent: business intent, supervisor domain,
specialist agents, entities, metrics, horizon, charts, data dependencies, risk classification and approval needs.
It only *plans*; every agent and tool call it implies is still authorized by the harness, gateway and policy engine.
Questions it does not recognise fall through to the LangGraph enterprise supervisor's own routing ("general").
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from conversation import onboarding
from conversation.personas import get as get_persona
from governance.identity import Principal
from harness.registry import REGISTRY

CLASSIFIER = "flo-intent-rules/1.0"
CLASS_ORDER = ["public", "internal", "confidential", "restricted"]


@dataclass(frozen=True)
class IntentDef:
    id: str
    label: str
    domain: str
    agents: tuple[str, ...]
    charts: tuple[str, ...]
    kpis: str | None = None
    metrics: tuple[str, ...] = ()
    data: tuple[str, ...] = ()
    needs_client: bool = False
    roadmap: bool = False


INTENTS: dict[str, IntentDef] = {d.id: d for d in [
    IntentDef("firm_overview", "Firm performance overview", "executive",
              ("aum_agent", "financial_performance_agent", "revenue_agent", "risk_agent"),
              ("aum_trend", "net_flows", "revenue_expenses", "margin_trend", "revenue_bridge", "risk_heatmap"), "exec",
              ("aum.total", "flows.net", "revenue.management_fees", "margin.operating", "revenue.yield_bps"), ("finance", "risk")),
    IntentDef("aum_profitability", "AUM growth versus profitability", "executive", ("aum_agent", "financial_performance_agent", "revenue_agent"),
              ("aum_trend", "net_flows", "revenue_expenses", "margin_trend", "revenue_yield", "revenue_bridge", "product_profitability"), "exec",
              ("aum.total", "aum.growth", "flows.net", "revenue.management_fees", "expenses.operating", "margin.operating", "revenue.yield_bps",
               "product.contribution"), ("finance",)),
    IntentDef("revenue_drivers", "Revenue and expense drivers", "executive", ("financial_performance_agent", "revenue_agent"),
              ("revenue_expenses", "revenue_bridge", "margin_trend", "budget_variance", "product_profitability"), "exec",
              ("revenue.management_fees", "expenses.operating", "margin.operating", "revenue.yield_bps", "budget.variance"), ("finance",)),
    IntentDef("revenue_opportunities", "Revenue improvement opportunities", "executive", ("revenue_agent", "financial_performance_agent", "aum_agent"),
              ("revenue_bridge", "product_profitability", "net_flows", "revenue_yield"), "exec",
              ("revenue.yield_bps", "product.contribution", "flows.net"), ("finance",), roadmap=True),
    IntentDef("advisor_productivity", "Advisor productivity", "executive", ("advisor_productivity_agent", "client_retention_agent"),
              ("advisor_productivity_scatter", "advisor_book_distribution", "book_segments"), "advisors",
              ("advisor.book_aum", "advisor.active_clients", "advisor.interactions"), ("wealth",), roadmap=True),
    IntentDef("client_retention", "Client retention", "wealth", ("client_retention_agent",),
              ("retention_trend", "retention_by_segment", "book_trend", "book_signals"), "retention",
              ("clients.retention", "clients.at_risk_signals"), ("wealth",)),
    IntentDef("book_overview", "Advisor book overview", "wealth", ("client_retention_agent", "product_research_agent"),
              ("book_segments", "book_signals", "book_trend"), "retention", ("advisor.book_aum", "clients.at_risk_signals"), ("wealth",), roadmap=True),
    IntentDef("concentration_risk", "Portfolio concentration risk", "investment", ("portfolio_agent", "risk_agent"),
              ("concentration_top_issuers", "sector_exposure", "geographic_exposure", "correlation", "risk_heatmap"), "concentration",
              ("risk.single_issuer", "risk.hhi", "exposure.geographic"), ("investment", "risk")),
    IntentDef("scenario", "Scenario simulation", "investment", ("scenario_agent",),
              ("scenario_paths", "scenario_by_asset_class", "portfolio_impacts", "scenario_comparison", "sensitivity_tornado"), "scenario",
              ("aum.total", "revenue.management_fees", "margin.operating"), ("finance", "investment")),
    IntentDef("client_review", "Client portfolio review", "wealth",
              ("client_intelligence_agent", "wealth_advisor_agent", "retirement_planning_agent", "client_meeting_agent"),
              ("client_allocation", "risk_return", "goal_progress", "retirement_projection"), "client",
              ("perf.twr", "risk.volatility", "risk.single_issuer"), ("wealth",), needs_client=True),
    IntentDef("retirement_strategy", "Client retirement strategy", "wealth", ("retirement_planning_agent", "wealth_advisor_agent"),
              ("retirement_projection", "cash_flow", "goal_progress", "risk_return"), "client", (), ("wealth",), needs_client=True),
    IntentDef("product_comparison", "Investment product comparison", "wealth", ("product_research_agent", "benchmark_agent"),
              ("product_fee_return", "fee_by_strategy", "relative_return"), "products", (), ("product",)),
    IntentDef("executive_briefing", "Executive leadership briefing", "executive", ("board_reporting_agent", "aum_agent", "financial_performance_agent"),
              ("aum_trend", "margin_trend", "budget_variance", "initiative_scorecard", "risk_heatmap"), "exec",
              ("aum.total", "margin.operating", "budget.variance", "strategy.initiative_progress"), ("finance", "strategy", "risk")),
    IntentDef("transformation_roadmap", "90-day transformation roadmap", "executive",
              ("aum_agent", "financial_performance_agent", "revenue_agent", "risk_agent"),
              ("margin_trend", "revenue_bridge", "net_flows", "initiative_scorecard"), "exec",
              ("margin.operating", "revenue.yield_bps", "flows.net"), ("finance", "strategy"), roadmap=True),
    IntentDef("business_onboarding", "Business onboarding and preliminary assessment", "executive", ("firm_diagnostic_agent",),
              ("firm_fee_sensitivity", "firm_market_scenarios", "firm_data_readiness"), "firm", (), ("user_supplied",), roadmap=True),
    IntentDef("risk_overview", "Enterprise risk review", "risk_compliance", ("risk_agent", "portfolio_agent"),
              ("risk_heatmap", "concentration_top_issuers", "correlation"), "concentration", ("risk.enterprise_score",), ("risk",)),
    IntentDef("greeting", "Welcome", "none", (), ()),
    IntentDef("help", "What FLO can do", "none", (), ()),
    IntentDef("general", "General question", "auto", (), ()),
]}

RULES: list[tuple[str, str]] = [
    (r"\b(i|we)\s+(own|run|manage|operate|founded|lead)\b.{0,60}\b(firm|business|practice|company|advisory|ria|dealer)\b", "business_onboarding"),
    (r"\b(my|our)\s+(advisory|wealth|investment)?\s*(firm|practice|business)\b.{0,80}\b(manag\w*|aum)\b.{0,30}\d", "business_onboarding"),
    (r"^\s*(hi|hello|hey|bonjour|hola|good (morning|afternoon|evening))\b[\s!,.]*(flo)?[\s!,.?]*$", "greeting"),
    (r"what can you do|how can you help( me)?\??$|^help\??$|what do you do", "help"),
    (r"roadmap|transformation|90[- ]day|action plan|implementation plan", "transformation_roadmap"),
    (r"board|leadership briefing|executive (briefing|summary)|briefing", "executive_briefing"),
    (r"(aum|assets under management).*(profit|margin)|(profit|margin).*(aum|assets under management)", "aum_profitability"),
    (r"advisor (productivity|performance|capacity|efficiency)|productivity", "advisor_productivity"),
    (r"retention|attrition|churn|losing clients|at[- ]risk clients|clients? (need|needing|that need) attention|attrition signals", "client_retention"),
    (r"retire", "retirement_strategy"),
    (r"\bC-\d{5}\b|client review|portfolio review|meeting prep|prepare.{0,30}(client|meeting)", "client_review"),
    (r"shock|scenario|stress|simulat|what if|what happens if|crash|downturn|bear market|bull market|rates? (rise|fall|increase|decrease|go up|go down|drop)|basis points|\bbps\b", "scenario"),
    (r"concentrat|single[- ]issuer|exposure", "concentration_risk"),
    (r"largest risk|biggest risk|top risk|risk heat ?map|risk register", "risk_overview"),
    (r"compar\w*.{0,30}(product|fund|etf)|(product|fund|etf).{0,30}compar|low[- ]fee|fund fees", "product_comparison"),
    (r"(opportunit|improve|grow|increase|boost).{0,40}(revenue|profit|margin)|revenue.{0,20}opportunit", "revenue_opportunities"),
    (r"revenue|expense|cost|margin|profit|budget|yield", "revenue_drivers"),
    (r"manag\w* (my|our|the) (investment )?(firm|business|company)|how (is|are) (the|our) (firm|business|company)|firm performance|business overview", "firm_overview"),
]

FOLLOWUP_CUE = re.compile(r"^\s*(now|and|also|what about|what if|what happens|then|ok(ay)?,?|break|show|explain|drill|compare|same|instead|prepare a board|"
                          r"how about|zoom|focus|only)\b", re.I)
GROUP_BY = {"product": r"by (fund|product)s?", "vehicle": r"by vehicle", "asset_class": r"by asset[- ]class", "region": r"by region",
            "segment": r"by (client )?segment", "sector": r"by sector", "issuer": r"by issuer"}


@dataclass
class Plan:
    intent: IntentDef
    entities: dict[str, Any] = field(default_factory=dict)
    modifiers: dict[str, Any] = field(default_factory=dict)
    follow_up_of: str | None = None


def months_of(text: str) -> int | None:
    t = text.lower()
    m = re.search(r"(?:last|past|trailing|previous)\s+(\d{1,2})\s+months", t)
    if m:
        return max(1, min(24, int(m.group(1))))
    if re.search(r"two years|2 years|24 months", t):
        return 24
    if re.search(r"last year|past year|12 months|one year|1 year", t):
        return 12
    return None


def scenario_of(text: str) -> dict[str, Any]:
    t = text.lower()
    out: dict[str, Any] = {}
    m = re.search(r"(\d{1,2}(?:\.\d+)?)\s?%\s*(?:equity|stock|market|equities)?\s*(?:market\s*)?(?:down|drop|fall|decline|crash|correction|downturn|sell[- ]?off)", t) \
        or re.search(r"(?:drop|fall|decline|crash|downturn|correction|sell[- ]?off)\w*\s+(?:of|by)?\s*(\d{1,2}(?:\.\d+)?)\s?%", t)
    if m:
        out["equity_shock"] = -float(m.group(1)) / 100
    m = re.search(r"rates?\s+(?:rise|rises|increase|increases|go up|goes up|climb|jump|up)\s+(?:by\s+)?(\d{1,3})\s*(?:bps|bp|basis points)", t) \
        or re.search(r"\+\s?(\d{1,3})\s*(?:bps|bp|basis points)", t)
    if m:
        out["rate_shock_bps"] = float(m.group(1))
    m = re.search(r"rates?\s+(?:fall|falls|drop|drops|decrease|decreases|go down|goes down|cut|are cut)\s+(?:by\s+)?(\d{1,3})\s*(?:bps|bp|basis points)", t)
    if m:
        out["rate_shock_bps"] = -float(m.group(1))
    if re.search(r"severe|crisis|crash", t):
        out["preset"] = "severe_stress"
    elif re.search(r"bull|rally", t):
        out["preset"] = "bull"
    elif re.search(r"downturn|bear|recession|sell[- ]?off|correction", t) or out.get("equity_shock"):
        out["preset"] = "bear"
    return out


def entities_of(text: str) -> dict[str, Any]:
    e: dict[str, Any] = {}
    if c := re.findall(r"\bC-\d{5}\b", text):
        e["client_id"] = c[0]
    if p := re.findall(r"\bPF-\d{4}\b", text):
        e["portfolio_id"] = p[0]
    if p := re.findall(r"\bP-\d{3}\b", text):
        e["product_id"] = p[0]
    if (m := months_of(text)) is not None:
        e["months"] = m
    for k, rx in GROUP_BY.items():
        if re.search(rx, text, re.I):
            e["group_by"] = k
            break
    return e


def _match(text: str) -> str | None:
    for rx, iid in RULES:
        if re.search(rx, text, re.I):
            return iid
    return None


def perms_of(principal: Principal, engine) -> set[str]:
    rbac = engine.bundle.rbac["roles"]
    return {p for r in principal.roles for p in rbac.get(r, [])}


def _variant(iid: str, perms: set[str], roles: set[str]) -> str:
    """Pick the workflow that answers the question for this identity. This selects WHICH analysis to run; it never widens access."""
    firm_level = {"firm_overview", "transformation_roadmap"}
    if iid in firm_level and "exec:read" not in perms and "finance:read" not in perms:
        if "wealth:read" in perms:
            return "book_overview"
        if "prospect" in roles:
            return "business_onboarding"
    if iid == "advisor_productivity" and "exec:read" not in perms and "wealth:read" in perms:
        return "book_overview"
    return iid


def classify(text: str, persona_id: str, principal: Principal, engine, state: dict | None = None, overrides: dict | None = None) -> Plan:
    state = state or {}
    overrides = overrides or {}
    persona = get_persona(persona_id)
    perms, roles = perms_of(principal, engine), set(principal.roles)
    ents = entities_of(text)
    scen = scenario_of(text)
    prev = state.get("last_intent")
    iid = overrides.get("intent") if overrides.get("intent") in INTENTS else _match(text)
    is_cue = prev is not None and (bool(FOLLOWUP_CUE.search(text)) or len(text.split()) <= 7)
    follow_up_of = prev if is_cue else None
    if is_cue and (iid is None or (iid == "revenue_drivers" and prev in ("aum_profitability", "firm_overview", "revenue_opportunities"))):
        iid = prev  # a modifier on the previous analysis: "now show the last 24 months", "break this down by product"
    if iid is None and len(text.split()) <= 6 and not re.search(r"\b(policy|regulat|complian|agent|market|benchmark|fund|research|decision)", text, re.I):
        iid = persona.default_intent  # too vague to route on its own: use the persona's home analysis
    profile = onboarding.extract_profile(text)
    in_onboarding = prev == "business_onboarding" or iid == "business_onboarding"
    if prev == "business_onboarding" and iid in (None, "general", "revenue_drivers", "firm_overview", "help") and (profile or is_cue):
        iid = "business_onboarding"
    iid = _variant(iid or "general", perms, roles)
    d = INTENTS[iid]
    # carry authorized-entity references (ids only) and analysis parameters; every reuse is re-authorized downstream
    entities = {k: state[k] for k in ("client_id", "portfolio_id") if state.get(k)}
    entities.update({k: v for k, v in ents.items() if k in ("client_id", "portfolio_id", "product_id")})
    if overrides.get("client_id"):
        entities["client_id"] = overrides["client_id"]
    mods: dict[str, Any] = {}
    months = overrides.get("months") or ents.get("months") or (state.get("months") if follow_up_of else None)
    if months:
        mods["months"] = max(1, min(24, int(months)))
    if overrides.get("group_by") or ents.get("group_by"):
        mods["group_by"] = overrides.get("group_by") or ents["group_by"]
    if d.id == "scenario":
        sc = {**((state.get("scenario") or {}) if prev == "scenario" and follow_up_of else {}), **scen, **(overrides.get("scenario") or {})}
        sc.setdefault("preset", "bear" if not sc else "base")
        mods["scenario"] = sc
    if d.id in ("business_onboarding", "transformation_roadmap") and (profile or (in_onboarding and state.get("business_profile"))):
        mods["business_profile"] = {**(state.get("business_profile") or {}), **profile}
    if overrides.get("focus"):
        mods["focus"] = str(overrides["focus"])[:120]
    return Plan(d, entities, mods, follow_up_of)


def describe(plan: Plan, persona_id: str, principal: Principal, perms: set[str]) -> dict:
    d = plan.intent
    agents = list(d.agents)
    if d.id == "transformation_roadmap" and "business_profile" in plan.modifiers:
        agents = ["firm_diagnostic_agent"]
    roles = set(principal.roles)
    ok = [a for a in agents if roles & REGISTRY.get(a).spec.allowed_roles]
    no = [a for a in agents if a not in ok]
    tools = sorted({t for a in ok for t in REGISTRY.get(a).spec.allowed_tools})
    cls = max((REGISTRY.get(a).spec.data_classification for a in agents), key=CLASS_ORDER.index, default="internal")
    approvals = sorted({x for a in agents for x in REGISTRY.get(a).spec.approval_actions})
    charts = list(d.charts)
    if plan.modifiers.get("group_by") == "product" and "product_revenue" not in charts:
        charts = ["product_revenue", "product_profitability"] + [c for c in charts if c != "product_profitability"]
    from conversation.dashboard import chart_relevant
    charts = [c for c in charts if chart_relevant(c, perms, bool(principal.advisor_id))]
    return {"classifier": CLASSIFIER, "intent": d.id, "label": d.label, "domain": d.domain, "persona": persona_id,
            "identity": {"user_id": principal.user_id, "tenant_id": principal.tenant_id, "roles": list(principal.roles),
                         "advisor_id": principal.advisor_id, "clearance": principal.clearance},
            "entities": plan.entities, "metrics": list(d.metrics), "time_horizon_months": plan.modifiers.get("months"),
            "agents": agents, "agents_authorized": ok, "agents_not_authorized": no, "tools": tools, "data_dependencies": list(d.data),
            "charts": charts, "risk_classification": cls, "approval_requirements": approvals, "follow_up_of": plan.follow_up_of,
            "modifiers": {k: v for k, v in plan.modifiers.items() if k != "business_profile"}}
