"""Recommendation engine: findings, risks, opportunities, prioritized recommendations and an implementation plan.

Rules read ONLY the facts that governed agents returned for this request (every value already passed through the tool
gateway for this user). Each insight and recommendation cites the agent and fact it rests on. Expected benefits are
described qualitatively with the KPI that would show them; no ROI, probability, confidence score or expected return is
invented. Personalized client recommendations are framed as items for advisor review and are approval-gated.
"""
from __future__ import annotations

from typing import Any

from conversation.schemas import EvidenceRef, ImplementationPlan, Insight, Recommendation, RoadmapPhase

Facts = dict[str, dict[str, Any]]


def _ev(agent: str, fact: str, facts: Facts, tool: str | None = None) -> EvidenceRef:
    v = facts.get(agent, {}).get(fact)
    return EvidenceRef(agent=agent, fact=fact, value="" if v is None else str(v)[:120], tool=tool)


class Builder:
    def __init__(self, facts: Facts):
        self.f = facts
        self.insights: list[Insight] = []
        self.recs: list[Recommendation] = []
        self.limitations: list[str] = []

    def has(self, agent: str, *keys: str) -> bool:
        a = self.f.get(agent)
        return a is not None and all(a.get(k) is not None for k in keys)

    def ins(self, section, title, detail="", severity="info", ev=()):
        self.insights.append(Insight(id=f"I{len(self.insights) + 1}", section=section, title=title, detail=detail, severity=severity, evidence=list(ev)))

    def rec(self, **kw):
        if not any(r.title == kw["title"] for r in self.recs):
            self.recs.append(Recommendation(id=f"R{len(self.recs) + 1}", **kw))


def _executive(b: Builder) -> None:
    f = b.f
    if b.has("aum_agent", "aum_bn", "aum_growth_pct"):
        a = f["aum_agent"]
        ev = [_ev("aum_agent", "aum_bn", f, "finance.kpis"), _ev("aum_agent", "aum_growth_pct", f), _ev("aum_agent", "net_flows_bn", f),
              _ev("aum_agent", "market_bn", f)]
        driver = "market movement" if abs(a["market_bn"]) > abs(a["net_flows_bn"]) else "net client flows"
        b.ins("current_state", f"AUM is CAD {a['aum_bn']}bn, up {a['aum_growth_pct']}% over {a['months']} months",
              f"Net flows contributed CAD {a['net_flows_bn']}bn and market movement CAD {a['market_bn']}bn; growth was led by {driver}.",
              "positive" if a["aum_growth_pct"] > 0 else "warning", ev)
        if driver == "market movement":
            b.ins("risk", "Growth depends more on markets than on new money",
                  "A market reversal would remove growth that flows are not replacing.", "warning", ev[2:])
        if a.get("bottom_flow_bn") is not None and a["bottom_flow_bn"] < 0:
            b.rec(title=f"Diagnose redemptions in {a['bottom_flow_group']} and reinforce {a['top_flow_group']} distribution", priority="P2",
                  rationale=f"{a['bottom_flow_group']} saw net outflows of CAD {a['bottom_flow_bn']}bn while {a['top_flow_group']} led inflows (CAD {a['top_flow_bn']}bn).",
                  evidence=[_ev("aum_agent", "bottom_flow_group", f), _ev("aum_agent", "bottom_flow_bn", f), _ev("aum_agent", "top_flow_bn", f)],
                  expected_benefit="Better organic growth that is less dependent on market returns.", kpis=["flows.net", "aum.growth"],
                  complexity="medium", dependencies=["Redemption reason codes from distribution", "Product-level flow data"],
                  owner_function="Distribution", timeframe="31-60 days", approvals_required=[],
                  validation_criteria=[f"Net flows in {a['bottom_flow_group']} improve for two consecutive quarters"])
    if b.has("financial_performance_agent", "margin_pct"):
        p = f["financial_performance_agent"]
        ev = [_ev("financial_performance_agent", "margin_pct", f, "finance.kpis"), _ev("financial_performance_agent", "prior_margin_pct", f)]
        if p.get("prior_margin_pct") is not None and p["margin_pct"] < p["prior_margin_pct"]:
            b.ins("finding", f"Operating margin fell from {p['prior_margin_pct']}% to {p['margin_pct']}%",
                  f"Revenue grew {p['revenue_growth_pct']}% while operating expenses grew {p['opex_growth_pct']}% ({p['gap_pp']} pp gap).", "warning",
                  ev + [_ev("financial_performance_agent", "revenue_growth_pct", f), _ev("financial_performance_agent", "opex_growth_pct", f)])
            b.rec(title=f"Run an expense-growth review led by {p['top_expense_line']}", priority="P1",
                  rationale=f"Expenses outpaced revenue by {p['gap_pp']} pp; the largest increase was {p['top_expense_line']} (+CAD {p['top_expense_increase_m']}m).",
                  evidence=[_ev("financial_performance_agent", "gap_pp", f), _ev("financial_performance_agent", "top_expense_line", f),
                            _ev("financial_performance_agent", "top_expense_increase_m", f, "finance.revenue_expenses")],
                  expected_benefit="Restores the link between expense growth and revenue growth, which protects operating margin.",
                  kpis=["margin.operating", "expenses.operating"], complexity="medium", dependencies=["Cost-centre detail from the general ledger"],
                  owner_function="Finance", timeframe="0-30 days", approvals_required=["Budget changes follow delegated financial authority (human decision)"],
                  validation_criteria=["Operating expense growth at or below revenue growth for two consecutive quarters"])
        elif p.get("prior_margin_pct") is not None:
            b.ins("current_state", f"Operating margin is {p['margin_pct']}% (prior period {p['prior_margin_pct']}%)", "", "positive", ev)
    if b.has("revenue_agent", "y0", "y1"):
        r = f["revenue_agent"]
        if r["y1"] < r["y0"]:
            b.ins("finding", f"Revenue yield fell from {r['y0']} to {r['y1']} bps",
                  f"Volume added CAD {r['volume_m']}m but the rate effect subtracted CAD {r['rate_abs_m']}m; mix shift accounted for CAD {r['mix_m']}m. {r['mix_line']}",
                  "warning", [_ev("revenue_agent", "y0", f, "finance.revenue_attribution"), _ev("revenue_agent", "y1", f), _ev("revenue_agent", "mix_m", f),
                              _ev("revenue_agent", "volume_m", f)])
            b.ins("opportunity", f"Growth is concentrating in {r['fastest_share_gain']}",
                  f"Its AUM share rose from {r['share0_pct']}% to {r['share1_pct']}% at about {r['yield_of_fastest']} bps.", "info",
                  [_ev("revenue_agent", "fastest_share_gain", f), _ev("revenue_agent", "share1_pct", f)])
            b.rec(title="Review pricing and product-mix strategy for lower-fee vehicles", priority="P2",
                  rationale=f"Mix shift toward lower-fee vehicles reduced revenue by CAD {r['mix_m']}m while AUM grew.",
                  evidence=[_ev("revenue_agent", "mix_m", f), _ev("revenue_agent", "fastest_share_gain", f), _ev("revenue_agent", "y1", f)],
                  expected_benefit="Revenue growth that keeps pace with AUM growth; clarity on which products earn their cost to serve.",
                  kpis=["revenue.yield_bps", "product.contribution"], complexity="high",
                  dependencies=["Product profitability by vehicle", "Distribution agreements", "Competitive fee research"], owner_function="Product & Distribution",
                  timeframe="31-60 days", approvals_required=["Fee changes require product governance and regulatory review"],
                  validation_criteria=["Revenue yield stabilizes for two consecutive quarters", "No fee change is made without product-governance approval"])
    if b.has("risk_agent", "top_risk"):
        k = f["risk_agent"]
        b.ins("risk", f"Top enterprise risk: {k['top_risk']} (score {k['top_score']} of {k['score_max']})", f"{k['high']} risks score {k['high_threshold']} or more.",
              "warning", [_ev("risk_agent", "top_risk", f, "risk.heatmap"), _ev("risk_agent", "top_score", f), _ev("risk_agent", "high", f)])
    if b.has("board_reporting_agent", "unfav"):
        k = f["board_reporting_agent"]
        b.ins("finding", f"{k['unfav']} of {k['lines']} budget lines are unfavourable", f"Largest variance: {k['worst_line']} (CAD {k['worst_var_m']}m).", "warning",
              [_ev("board_reporting_agent", "unfav", f, "finance.actual_vs_budget"), _ev("board_reporting_agent", "worst_line", f)])
        if k["behind"]:
            b.rec(title=f"Recover the {k['behind']} strategic initiatives behind plan", priority="P2",
                  rationale=f"{k['behind']} of {k['n_init']} initiatives report progress behind their time-elapsed plan.",
                  evidence=[_ev("board_reporting_agent", "behind", f, "strategy.initiatives"), _ev("board_reporting_agent", "n_init", f)],
                  expected_benefit="Initiative benefits arrive on the committed timeline, or are re-scoped transparently.",
                  kpis=["strategy.initiative_progress"], complexity="medium", dependencies=["Initiative owners' recovery plans"],
                  owner_function="Strategy Office", timeframe="0-30 days", approvals_required=["Re-baselining requires executive committee approval"],
                  validation_criteria=["Schedule variance back within 10 pp or a re-baseline approved"])


def _investment(b: Builder) -> None:
    f = b.f
    if b.has("portfolio_agent", "top_name", "breaching"):
        p = f["portfolio_agent"]
        b.ins("finding", f"{p['top_name']} is {p['top_pct']}% of managed portfolio assets, held in {p['top_holders']} portfolios",
              f"The ten largest issuers are {p['top10_pct']}%; effective number of issuers {p['eff_n']}.", "warning" if p["breaching"] else "info",
              [_ev("portfolio_agent", "top_name", f, "investment.enterprise_concentration"), _ev("portfolio_agent", "top_pct", f), _ev("portfolio_agent", "top_holders", f)])
        if p["breaching"]:
            b.ins("risk", f"{p['breaching']} portfolios exceed the {p['limit_pct']}% single-issuer limit", "", "critical",
                  [_ev("portfolio_agent", "breaching", f), _ev("portfolio_agent", "limit_pct", f)])
            b.rec(title="Remediate single-issuer limit breaches", priority="P1",
                  rationale=f"{p['breaching']} portfolios exceed the {p['limit_pct']}% limit; {p['top_name']} is the largest exposure.",
                  evidence=[_ev("portfolio_agent", "breaching", f), _ev("portfolio_agent", "top_name", f), _ev("portfolio_agent", "limit_pct", f)],
                  expected_benefit="Exposure returns within approved limits, reducing idiosyncratic risk for affected clients.",
                  kpis=["risk.single_issuer", "risk.hhi"], complexity="medium", dependencies=["Portfolio manager review of each breaching mandate", "Client suitability context"],
                  owner_function="Investment Risk", timeframe="0-30 days",
                  approvals_required=["Portfolio changes require portfolio-manager and CIO approval", "FLO never executes trades"],
                  validation_criteria=["Portfolios over the single-issuer limit = 0", "Each remediation documented with PM rationale"])
    if b.has("risk_agent", "max_corr_pair"):
        k = f["risk_agent"]
        b.ins("risk", f"Most correlated sector pair: {k['max_corr_pair']} ({k['max_corr']})", "Diversification across these sectors is weaker than labels suggest.",
              "info", [_ev("risk_agent", "max_corr_pair", f, "investment.correlation"), _ev("risk_agent", "max_corr", f)])
    if b.has("scenario_agent", "aum_chg_pct"):
        s = f["scenario_agent"]
        ev = [_ev("scenario_agent", "scenario", f, "scenario.run"), _ev("scenario_agent", "aum_chg_pct", f), _ev("scenario_agent", "margin_pct", f),
              _ev("scenario_agent", "port_impact_m", f)]
        label = s["scenario"] + (f", equity {s['equity_shock_pct']}%" if s.get("equity_shock_pct") else "") + (f", rates {s['rate_bps']:+g} bps" if s.get("rate_bps") else "")
        b.ins("finding", f"Under '{label}', AUM moves {s['aum_chg_pct']}% to CAD {s['aum1_bn']}bn over {s['horizon']} months",
              f"Operating margin {s['margin_pct']}%; immediate portfolio impact CAD {s['port_impact_m']}m; most affected mandate {s['worst_mandate']} "
              f"({s['worst_mandate_pct']}%). Conditional on stated assumptions; not a forecast.", "critical" if s["aum_chg_pct"] < -10 else "warning", ev)
        if s["aum_chg_pct"] < 0:
            b.rec(title=f"Prepare contingency actions for the '{s['scenario']}' scenario", priority="P2",
                  rationale=f"The scenario reduces AUM by {abs(s['aum_chg_pct'])}% and compresses fee revenue; {s['worst_mandate']} mandates are most exposed.",
                  evidence=ev, expected_benefit="Pre-agreed responses (client communications, cost levers, liquidity checks) shorten reaction time if markets fall.",
                  kpis=["aum.total", "margin.operating", "revenue.management_fees"], complexity="medium",
                  dependencies=["Finance cost-lever inventory", "Client communication templates (approval-gated)"], owner_function="Executive Leadership",
                  timeframe="31-60 days", approvals_required=["Client communications require compliance approval"],
                  validation_criteria=["Trigger thresholds agreed by Finance and the CIO", "Playbook rehearsed once"])
        if s["worst_mandate_pct"] < 0:
            b.rec(title=f"Review positioning of {s['worst_mandate']} mandates against the stress result", priority="P2",
                  rationale=f"{s['worst_mandate']} mandates show the largest immediate impact ({s['worst_mandate_pct']}%) under this scenario.",
                  evidence=[_ev("scenario_agent", "worst_mandate", f), _ev("scenario_agent", "worst_mandate_pct", f)],
                  expected_benefit="Mandate risk reviewed against client risk profiles before markets move, not after.", kpis=["risk.volatility", "risk.max_drawdown"],
                  complexity="medium", dependencies=["Portfolio manager review"], owner_function="Investment Management", timeframe="0-30 days",
                  approvals_required=["Portfolio changes require PM and CIO approval; FLO never executes trades"],
                  validation_criteria=["Each affected mandate reviewed and decision documented"])
        b.limitations.append("Scenario outputs are deterministic arithmetic on stated assumptions; they carry no probability.")
    if b.has("benchmark_agent", "beat", "n"):
        k = f["benchmark_agent"]
        b.ins("current_state", f"{k['beat']} of {k['n']} funds beat their benchmark over 12 months (gross of fees)",
              f"Strongest {k['best']} ({k['best_rel_pct']} pp), weakest {k['worst']} ({k['worst_rel_pct']} pp).", "info",
              [_ev("benchmark_agent", "beat", f, "investment.fund_list"), _ev("benchmark_agent", "worst", f)])


def _wealth(b: Builder) -> None:
    f = b.f
    ci = f.get("client_intelligence_agent")
    if ci:
        b.ins("current_state", f"{ci['client_id']}: {ci['segment']}, risk profile {ci['risk_profile']}",
              f"{ci['n_portfolios']} managed portfolio(s); {ci['neg']} negative and {ci['followups']} follow-up interactions among the last {ci['n_int']}; "
              f"KYC reviewed {ci['kyc']}.", "info", [_ev("client_intelligence_agent", "segment", f, "client.profile"), _ev("client_intelligence_agent", "kyc", f)])
    wa = f.get("wealth_advisor_agent")
    if wa:
        for fd in wa.get("findings", []):
            label = {"SUIT-VOL-BAND": "Portfolio volatility above the band for the client's risk profile",
                     "SUIT-SINGLE-ISSUER": "Single-issuer concentration above limit", "SUIT-KYC-STALE": "KYC information is older than policy allows"}[fd["rule"]]
            b.ins("risk", label, f"Rule {fd['rule']} ({fd['severity']}); a screen for advisor and compliance review, not a determination.",
                  "critical" if fd["severity"] == "high" else "warning", [_ev("wealth_advisor_agent", "findings", f, "client.suitability")])
        rules = {x["rule"] for x in wa.get("findings", [])}
        if "SUIT-KYC-STALE" in rules:
            b.rec(title=f"Refresh KYC for {wa['client_id']} before any recommendation", priority="P1",
                  rationale="The suitability screen flags KYC older than the approved maximum age.", evidence=[_ev("wealth_advisor_agent", "findings", f)],
                  expected_benefit="Advice rests on current client circumstances, as policy requires.", kpis=["KYC age (days)"], complexity="low",
                  dependencies=["Client meeting"], owner_function="Wealth Advisory", timeframe="0-30 days", approvals_required=[],
                  validation_criteria=["KYC review date updated in CRM"])
        if rules & {"SUIT-VOL-BAND", "SUIT-SINGLE-ISSUER"}:
            b.rec(title=f"Review {wa['client_id']}'s risk level and concentration with the client", priority="P1",
                  rationale="Screen findings show risk or concentration outside the profile's rules.", evidence=[_ev("wealth_advisor_agent", "findings", f)],
                  expected_benefit="Portfolio risk aligned with the documented risk profile.", kpis=["risk.volatility", "risk.single_issuer"], complexity="medium",
                  dependencies=["Current KYC", "Portfolio manager input"], owner_function="Wealth Advisory", timeframe="0-30 days",
                  approvals_required=["Personalized recommendations require compliance approval (recommendation:deliver)"],
                  validation_criteria=["Screen re-run shows no high-severity findings", "Recommendation approved before delivery"])
    rp = f.get("retirement_planning_agent")
    if rp:
        b.ins("finding", f"Projected CAD {rp['at_ret']} at age {rp['retirement_age']} (CAD {rp['real_at_ret']} in today's dollars)",
              f"Supports a first-year withdrawal of about CAD {rp['withdrawal']} rising with inflation for {rp['years']} years, at {rp['er_pct']}% assumed return "
              f"and {rp['inf_pct']}% inflation. Not guaranteed.", "info",
              [_ev("retirement_planning_agent", "at_ret", f, "client.retirement"), _ev("retirement_planning_agent", "withdrawal", f)])
        off = [g for g in rp.get("goals", []) if not g.get("on_track")]
        if off:
            b.rec(title=f"Discuss {len(off)} off-track goal(s) and contribution options with {rp['client_id']}", priority="P2",
                  rationale="Deterministic goal projections fall short of target at the target date: " + ", ".join(g["goal_type"] for g in off) + ".",
                  evidence=[_ev("retirement_planning_agent", "goals", f, "client.goals")],
                  expected_benefit="The client sees the trade-offs (contribution, horizon, target) and decides.", kpis=["Projected funded %"], complexity="low",
                  dependencies=["Client meeting"], owner_function="Wealth Advisory", timeframe="0-30 days",
                  approvals_required=["Personalized recommendations require compliance approval (recommendation:deliver)"],
                  validation_criteria=["Updated plan documented and acknowledged by the client"])
        b.limitations.append("Retirement projections are deterministic and use approved planning assumptions; actual results will differ.")
    cm = f.get("client_meeting_agent")
    if cm and cm.get("agenda"):
        b.ins("opportunity", f"Meeting agenda prepared ({len(cm['agenda'])} items)", "; ".join(cm["agenda"][:3]), "info",
              [_ev("client_meeting_agent", "agenda", f, "client.goals")])
    ret = f.get("client_retention_agent")
    if ret:
        if ret.get("ent_retention_pct") is not None:
            sev = "warning" if ret["ent_retention_pct"] < ret["ent_prior_pct"] else "positive"
            b.ins("current_state", f"Client retention {ret['ent_retention_pct']}% (prior 12 months {ret['ent_prior_pct']}%)",
                  f"{ret['ent_closed']} closures; lowest segment {ret['low_seg']} at {ret['low_seg_pct']}%.", sev,
                  [_ev("client_retention_agent", "ent_retention_pct", f, "finance.retention"), _ev("client_retention_agent", "low_seg", f)])
            b.rec(title=f"Investigate closures in the {ret['low_seg']} segment", priority="P2",
                  rationale=f"{ret['low_seg']} has the lowest 12-month retention ({ret['low_seg_pct']}%).",
                  evidence=[_ev("client_retention_agent", "low_seg", f), _ev("client_retention_agent", "low_seg_pct", f)],
                  expected_benefit="Understand why these clients leave and which service changes would address it.", kpis=["clients.retention"],
                  complexity="medium", dependencies=["Closure reason codes", "Exit-interview notes"], owner_function="Client Service",
                  timeframe="31-60 days", approvals_required=[], validation_criteria=["Closure reasons coded for 100% of closures", "Segment retention trend reviewed quarterly"])
        if ret.get("book_clients") is not None:
            b.ins("current_state", f"Your book: {ret['book_clients']} active clients, {ret['at_risk']} with review signals",
                  f"{ret['sig_neg']} negative sentiment (6 months), {ret['sig_fu']} follow-ups flagged (90 days), {ret['sig_kyc']} stale KYC.",
                  "warning" if ret["at_risk"] else "positive", [_ev("client_retention_agent", "at_risk", f, "wealth.book_health"), _ev("client_retention_agent", "sig_kyc", f)])
            if ret["at_risk"]:
                b.rec(title=f"Reach out to the {ret['at_risk']} clients with review signals", priority="P1",
                      rationale="Observable signals (negative sentiment, open follow-ups, stale KYC) are prompts to re-engage before clients disengage.",
                      evidence=[_ev("client_retention_agent", "at_risk", f), _ev("client_retention_agent", "sig_neg", f), _ev("client_retention_agent", "sig_fu", f)],
                      expected_benefit="Earlier service recovery and up-to-date KYC across the book.", kpis=["clients.retention", "clients.at_risk_signals"],
                      complexity="low", dependencies=["Approved communication templates"], owner_function="Wealth Advisory", timeframe="0-30 days",
                      approvals_required=["Client communications require compliance approval (comms:send)"],
                      validation_criteria=["Every flagged client contacted and follow-ups closed", "Stale KYC count falls to zero"])
            if ret.get("sig_kyc"):
                b.rec(title=f"Clear the {ret['sig_kyc']} stale KYC reviews in your book", priority="P1",
                      rationale=f"KYC older than {ret['kyc_max_age_days']} days blocks personalized recommendations.",
                      evidence=[_ev("client_retention_agent", "sig_kyc", f), _ev("client_retention_agent", "kyc_max_age_days", f)],
                      expected_benefit="Advice and suitability screens rest on current information.", kpis=["Stale KYC count"], complexity="low",
                      dependencies=["Client meetings"], owner_function="Wealth Advisory", timeframe="0-30 days", approvals_required=[],
                      validation_criteria=["Stale KYC count = 0"])
    ap = f.get("advisor_productivity_agent")
    if ap:
        ev = [_ev("advisor_productivity_agent", "ratio", f, "wealth.advisor_productivity"), _ev("advisor_productivity_agent", "median_m", f),
              _ev("advisor_productivity_agent", "median_ipc", f)]
        b.ins("finding", f"Top-quartile books average CAD {ap['top_q_m']}m versus CAD {ap['bottom_q_m']}m for the bottom quartile",
              f"Median book CAD {ap['median_m']}m with {ap['median_clients']} active clients; median {ap['median_ipc']} interactions per client in 12 months.",
              "warning", ev)
        b.rec(title="Pair bottom-quartile advisors with top-quartile peers on client engagement practices", priority="P2",
              rationale=f"Book size varies {ap['ratio']}x between quartiles; engagement practices are a controllable difference to examine.", evidence=ev,
              expected_benefit="Shared practices raise engagement and client coverage in smaller books.", kpis=["advisor.book_aum", "advisor.interactions"],
              complexity="medium", dependencies=["Advisor consent and HR policy", "Engagement data by advisor"], owner_function="Wealth Management Leadership",
              timeframe="31-60 days", approvals_required=["People-management actions follow HR policy (human decisions)"],
              validation_criteria=["Bottom-quartile interactions per client rise over two quarters"])
        b.rec(title="Free advisor time by automating meeting preparation and follow-up drafting", priority="P2",
              rationale=f"{ap['followups']} interactions were flagged for follow-up; FLO already drafts agendas and approval-gated letters.",
              evidence=[_ev("advisor_productivity_agent", "followups", f)],
              expected_benefit="More advisor time for client conversations; measure it rather than assume it.", kpis=["advisor.interactions", "Follow-up closure time"],
              complexity="low", dependencies=["Approved templates", "Advisor training"], owner_function="Operations", timeframe="0-30 days",
              approvals_required=["Outbound client communications remain compliance-approved"],
              validation_criteria=["Measured change in prep time and follow-up closure time over 60 days (no assumed savings)"])
        if ap.get("kyc_stale"):
            b.rec(title=f"Run a KYC refresh campaign for the {ap['kyc_stale']} clients with stale KYC", priority="P1",
                  rationale="Stale KYC blocks compliant personalized advice.", evidence=[_ev("advisor_productivity_agent", "kyc_stale", f)],
                  expected_benefit="Compliance exposure reduced; advisors can resume recommendations.", kpis=["Stale KYC count"], complexity="low",
                  dependencies=["Advisor capacity"], owner_function="Compliance", timeframe="0-30 days", approvals_required=[],
                  validation_criteria=["Stale KYC count reduced to zero"])
        b.limitations.append("Activity counts describe workload, not advisor quality; compare like-for-like books before drawing conclusions about people.")
    pr = f.get("product_research_agent")
    if pr:
        b.ins("current_state", f"{pr['n']} funds compared on fee and 12-month return", "General product information, not a recommendation.", "info",
              [_ev("product_research_agent", "n", f, "investment.fund_list")])
        b.limitations.append("Product comparisons are general information; suitability for any client requires an advisor review.")


def _firm(b: Builder) -> None:
    fd = b.f.get("firm_diagnostic_agent")
    if not fd:
        return
    a = fd["assessment"]
    for m in fd["metrics"]:
        b.ins("current_state", f"{m['label']}: {m['display']}", f"Source: {m['provenance'].replace('_', ' ')}. {m['basis']}",
              "info", [_ev("firm_diagnostic_agent", "metrics", b.f, "advisory.firm_model")])
    ev = [_ev("firm_diagnostic_agent", "missing", b.f, "advisory.firm_model")]
    b.rec(title="Establish a verified KPI baseline", priority="P1",
          rationale="Recommendations become specific once AUM, revenue, expenses, flows and client counts are verified from your systems.", evidence=ev,
          expected_benefit="Decisions rest on measured data rather than assumptions.", kpis=["AUM", "Revenue yield", "Operating margin", "Net flows"],
          complexity="low", dependencies=[x["system"] for x in a["integrations"][:3]], owner_function="Business Owner", timeframe="0-30 days",
          approvals_required=["Data-sharing agreement before any integration"], validation_criteria=["Baseline reconciled to financial statements"])
    if "operating_margin" not in [m["key"] for m in a["metrics"]]:
        b.rec(title="Map your expense structure", priority="P1", rationale="Profitability cannot be assessed without operating expenses.", evidence=ev,
              expected_benefit="Identifies which cost lines grow faster than revenue.", kpis=["Operating margin", "Expense growth vs revenue growth"],
              complexity="low", dependencies=["General ledger"], owner_function="Finance", timeframe="0-30 days", approvals_required=[],
              validation_criteria=["Expense lines categorised and reconciled"])
    b.rec(title="Segment clients by household assets and service model", priority="P2",
          rationale="Segmentation shows where revenue and servicing effort concentrate.", evidence=ev,
          expected_benefit="Service levels and pricing matched to segment economics.", kpis=["Revenue by segment", "Clients per advisor"], complexity="medium",
          dependencies=["CRM data"], owner_function="Client Service", timeframe="31-60 days", approvals_required=[],
          validation_criteria=["Every household assigned to a segment"])
    b.rec(title="Review pricing against your cost to serve", priority="P2",
          rationale=f"Each 1 bp of average fee is worth about CAD {fd['per_bp']:,.0f} a year on your AUM." if fd.get("per_bp") else "Fee rate is a primary profitability lever.",
          evidence=[_ev("firm_diagnostic_agent", "per_bp", b.f, "advisory.firm_model")],
          expected_benefit="Pricing decisions informed by segment economics; no change without client-impact review.", kpis=["Revenue yield"], complexity="high",
          dependencies=["Segmentation", "Fee schedules"], owner_function="Business Owner", timeframe="61-90 days",
          approvals_required=["Fee changes require client disclosure and regulatory review"], validation_criteria=["Pricing decision documented with client impact"])
    b.rec(title="Introduce advisor productivity and retention tracking", priority="P3",
          rationale="Productivity and retention modules need CRM data you have not yet connected.", evidence=ev,
          expected_benefit="Early warning on client attrition and capacity constraints.", kpis=["clients.retention", "AUM per advisor"], complexity="medium",
          dependencies=["CRM integration"], owner_function="Operations", timeframe="61-90 days", approvals_required=[],
          validation_criteria=["Monthly retention and productivity report produced"])
    b.limitations.append("Preliminary: built from figures you typed and labelled planning assumptions; nothing is verified against your systems.")
    for x in a["assumptions"]:
        b.limitations.append(f"Assumption: {x['name']} = {x['value']} {x['unit']} ({x['source']}). {x['note']}")


GENERIC_PHASE_GATES = ["Data validated against source systems", "Client-facing actions approved by compliance", "No trades executed by FLO"]


def build_plan(recs: list[Recommendation], title: str) -> ImplementationPlan | None:
    if not recs:
        return None
    windows = [("Days 0-30", "0-30 days", "Baseline and quick wins"), ("Days 31-60", "31-60 days", "Execute priority changes"),
               ("Days 61-90", "61-90 days", "Scale and measure")]
    phases = []
    for i, (win, tf, name) in enumerate(windows):
        rs = [r for r in recs if r.timeframe == tf] or ([r for r in recs if r.priority == "P1"] if i == 0 else [])
        acts = [f"{r.id}: {r.title}" for r in rs]
        if i == 0:
            acts.append("Confirm KPI baselines and owners for every recommendation")
        if i == 2:
            acts.append("Review KPI movement against the validation criteria; keep, adjust or stop each action")
        phases.append(RoadmapPhase(name=name, window=win, objectives=[r.expected_benefit for r in rs][:3] or ["Consolidate results and plan the next cycle"],
                                   actions=acts, milestones=[c for r in rs for c in r.validation_criteria][:4] or ["Quarterly KPI review completed"],
                                   kpis=sorted({k for r in rs for k in r.kpis})[:6], governance_gates=GENERIC_PHASE_GATES if i == 0 else
                                   sorted({a for r in rs for a in r.approvals_required})[:3]))
    return ImplementationPlan(title=title, phases=phases,
                              basis="Sequenced from the recommendations above by timeframe and priority. Windows are a planning structure, "
                                    "not effort estimates; owners confirm scope and dates.")


FOLLOWUPS = {
    "aum_profitability": ["Break this down by product.", "Now show the last 24 months.", "What happens if rates rise by 200 basis points?",
                          "Explain the largest risk.", "Prepare a board-level summary."],
    "firm_overview": ["Why is our AUM growing while profitability declines?", "Identify opportunities to improve revenue.", "Simulate a market downturn.",
                      "Create a 90-day wealth management transformation roadmap."],
    "revenue_drivers": ["Break this down by product.", "Show actual versus budget.", "Identify opportunities to improve revenue."],
    "revenue_opportunities": ["Break this down by product.", "Simulate fee compression in a downturn.", "Create a 90-day roadmap for these actions."],
    "concentration_risk": ["Which portfolios hold the largest issuer?", "Simulate a 20% equity market downturn.", "Explain the largest risk."],
    "scenario": ["What happens if rates rise by 200 basis points?", "Compare all scenario presets.", "Which mandates are most affected?",
                 "Prepare a board-level summary."],
    "client_review": ["Build a retirement strategy for this client.", "Draft a follow-up letter in French for approval.", "Show this client's goals."],
    "retirement_strategy": ["Prepare a portfolio review for this client.", "What if contributions rise by 10%?", "Draft a follow-up letter for approval."],
    "client_retention": ["Which clients show attrition signals?", "Create a 90-day retention roadmap.", "Build a client retirement strategy."],
    "book_overview": ["Investigate client retention in my book.", "Prepare a portfolio review for my top client.", "Compare low-fee ETF products."],
    "advisor_productivity": ["Create a 90-day roadmap for advisor productivity.", "Investigate client retention.", "Show the advisors with the most stale KYC."],
    "product_comparison": ["Compare fees by strategy.", "How did our funds perform against benchmarks?"],
    "executive_briefing": ["Why is our AUM growing while profitability declines?", "Simulate a market downturn.", "Explain the largest risk."],
    "transformation_roadmap": ["Explain the first 30 days in detail.", "Which KPIs should the board track?", "Simulate a market downturn."],
    "business_onboarding": ["We have 8 advisors, 1,200 client households, an average fee of 0.85% and expenses of CAD 3.1 million.",
                            "Create a 90-day wealth management transformation roadmap.", "What data would you need from our CRM and custodian?"],
    "risk_overview": ["Analyze our portfolio concentration risk.", "Simulate a severe stress scenario."],
}


def build(intent: str, facts: Facts, roadmap: bool, persona_functions: tuple[str, ...]) -> dict:
    b = Builder(facts)
    _executive(b)
    _investment(b)
    _wealth(b)
    _firm(b)
    order = {"P1": 0, "P2": 1, "P3": 2}
    pref = {fn: i for i, fn in enumerate(persona_functions)}
    b.recs.sort(key=lambda r: (order[r.priority], pref.get(r.owner_function, 99)))
    for i, r in enumerate(b.recs):
        r.id = f"R{i + 1}"
    plan = build_plan(b.recs, "90-day implementation roadmap") if (roadmap or intent == "transformation_roadmap") else None
    return {"insights": b.insights, "recommendations": b.recs, "plan": plan, "limitations": b.limitations, "followups": FOLLOWUPS.get(intent, [])}
