"""Persona catalogue. A persona is a UX preference: it changes suggested questions, explanation depth, terminology,
dashboard emphasis and how ambiguous questions are routed. It NEVER grants access - permissions come only from the
authenticated identity and the policy engine (a wealth advisor who picks "CEO" still gets wealth-advisor data)."""
from __future__ import annotations

from dataclasses import asdict, dataclass

STARTER_PROMPTS = [
    "Can you help manage my investment firm?",
    "Why is our AUM growing while profitability declines?",
    "How can we improve our advisor productivity?",
    "Analyze our portfolio concentration risk.",
    "Build a client retirement strategy.",
    "Compare our investment products.",
    "Simulate a market downturn.",
    "Prepare an executive leadership briefing.",
    "Identify opportunities to improve revenue.",
    "Create a 90-day wealth management transformation roadmap.",
]


@dataclass(frozen=True)
class Persona:
    id: str
    label: str
    short: str
    description: str
    typical_roles: tuple[str, ...]
    depth: str  # executive | analyst | advisor | client | operations
    terminology: str
    emphasis: tuple[str, ...]  # chart/KPI ids shown first when relevant
    owner_functions: tuple[str, ...]  # recommendation owners surfaced first
    prompts: tuple[str, ...]
    default_intent: str  # used only when a question is too vague to route on its own


PERSONAS: dict[str, Persona] = {p.id: p for p in [
    Persona("ceo", "CEO / Executive Leadership", "CEO", "Enterprise growth, profitability and strategic priorities.", ("executive",), "executive",
            "Board-level language; figures rounded to CAD millions/billions.", ("exec_kpis", "aum_trend", "margin_trend", "revenue_bridge"),
            ("Executive Leadership", "Finance", "Distribution"),
            ("Why is our AUM growing while profitability declines?", "Prepare an executive leadership briefing.",
             "Identify opportunities to improve revenue.", "Create a 90-day wealth management transformation roadmap."), "firm_overview"),
    Persona("cio", "CIO / Investment Leadership", "CIO", "Portfolio risk, concentration, performance and scenarios.", ("cio",), "analyst",
            "Investment terminology (TWR, drawdown, HHI, effective N).", ("concentration_top_issuers", "sector_exposure", "scenario_paths"),
            ("Investment Management", "Investment Risk"),
            ("Show our portfolio performance.", "Analyze our portfolio concentration risk.", "Simulate a 20% equity market downturn.",
             "What happens if rates rise by 200 basis points?"), "portfolio_performance"),
    Persona("cfo", "CFO / Financial Leadership", "CFO", "Revenue, expense drivers, margin and budget variance.", ("finance",), "analyst",
            "Financial-statement terminology; revenue yield in basis points.", ("revenue_expenses", "revenue_bridge", "margin_trend", "budget_variance"),
            ("Finance", "Executive Leadership"),
            ("Analyze our revenue and expense drivers.", "Why is our AUM growing while profitability declines?", "Identify opportunities to improve revenue.",
             "Show actual versus budget for the last 12 months."), "revenue_drivers"),
    Persona("wealth_advisor", "Wealth Advisor", "Advisor", "Client reviews, suitability screens, retirement planning and follow-ups.", ("wealth_advisor", "external_advisor"), "advisor",
            "Client-friendly language; suitability findings are review prompts, not determinations.", ("client_kpis", "risk_return", "retirement_projection"),
            ("Wealth Advisory", "Compliance"),
            ("Prepare a portfolio review for my top client.", "Build a client retirement strategy.", "Which of my clients need attention this month?",
             "Compare low-fee ETF products."), "book_overview"),
    Persona("institutional_pm", "Institutional Investment Manager", "Inst. PM", "Mandate-level exposure, stress tests and benchmark-relative results.",
            ("cio", "investment_analyst"), "analyst", "Institutional mandate terminology.", ("scenario_paths", "portfolio_impacts", "correlation"),
            ("Investment Management", "Investment Risk"),
            ("Simulate a market downturn.", "Which mandates are most affected by a severe stress?", "Show sector correlation risk.",
             "Analyze our portfolio concentration risk."), "scenario"),
    Persona("business_owner", "Business Owner / Prospective Client", "Owner", "Running and growing an advisory or wealth business.", ("prospect",), "client",
            "Plain language with definitions; every figure labelled by source.", ("firm_kpis", "firm_fee_sensitivity", "firm_data_readiness"),
            ("Business Owner", "Finance", "Operations"),
            ("Hello FLO, I own an investment advisory firm managing CAD 500 million. Can you help us manage the business and improve profitability?",
             "Can you help manage my investment firm?", "Create a 90-day wealth management transformation roadmap.", "Compare our investment products."),
            "business_onboarding"),
    Persona("relationship_manager", "Relationship Manager", "RM", "Client retention, engagement and service follow-ups.", ("wealth_advisor",), "advisor",
            "Relationship language; signals are prompts for outreach, not predictions.", ("retention_trend", "book_signals", "retention_by_segment"),
            ("Wealth Advisory", "Client Service"),
            ("Investigate client retention in my book.", "Which clients show attrition signals?", "Build a client retirement strategy.",
             "Prepare a portfolio review for my top client."), "client_retention"),
    Persona("risk_compliance", "Risk and Compliance Officer", "Risk", "Concentration exposure, policies, suitability and regulatory change.",
            ("risk_officer", "compliance_officer", "privacy_officer"), "analyst", "Control and policy terminology; AI does not make regulatory determinations.",
            ("concentration_top_issuers", "risk_heatmap"), ("Compliance", "Investment Risk"),
            ("Examine our concentration exposure.", "What is the client communications approval policy?", "Summarize suitability procedures.",
             "Show the enterprise risk heatmap."), "concentration_risk"),
    Persona("portfolio_analyst", "Portfolio Analyst", "Analyst", "Holdings analytics, benchmarks, correlation and market moves.", ("investment_analyst",),
            "analyst", "Quantitative terminology with formulas in methodology.", ("relative_return", "correlation", "market_benchmarks"),
            ("Investment Management",),
            ("How did our funds perform against benchmarks?", "Show sector correlation risk.", "What happened in markets last month?",
             "Compare our investment products."), "benchmark"),
    # FLOW WEALTH investment-research personas (historical Kaggle market data; trading speed and risk appetite are separate settings)
    Persona("beginner_investor", "Beginner Investor", "Beginner", "Plain-language market history, risk awareness and how to read evidence.",
            ("prospect",), "client", "Plain language; every figure labelled historical; no recommendations.",
            ("market_price_history", "market_drawdown"), ("Investor Education",),
            ("Analyze Apple's historical performance.", "Explain the latest available market regime.", "Which datasets are available?",
             "Compare Microsoft and Nvidia over the last 3 years."), "market_overview"),
    Persona("long_term_investor", "Long-term Investor", "Long-term", "Multi-year returns, drawdowns and diversification versus SPY.",
            ("wealth_advisor", "prospect", "cio"), "advisor", "Long-horizon language; historical data, not current prices.",
            ("market_compare", "market_price_history", "market_sectors"), ("Investment Management",),
            ("Compare Microsoft and Nvidia from 2012 to 2017.", "Show the market overview.", "Compare Bull and Bear evidence for AAPL.",
             "Show model accuracy over the holdout period."), "market_overview"),
    Persona("swing_trader", "Swing Trader (research)", "Swing", "Multi-day price behaviour and regime awareness; intraday and swift modes stay disabled without intraday data.",
            ("investment_analyst", "cio"), "analyst", "Trading research terminology; no execution.",
            ("model_holdout_equity", "market_regime_history"), ("Investment Research",),
            ("Compare Bull and Bear evidence for NVDA for an aggressive swing profile.", "Explain the latest available market regime.",
             "Show model accuracy over the holdout period.", "Why did the model reject this opportunity?"), "model_accuracy"),
    Persona("quant_researcher", "Quant Researcher", "Quant", "Models, gross versus net results, leakage controls and reproducibility.",
            ("investment_analyst", "cio", "ai_admin"), "analyst", "Quantitative terminology (rank IC, Sharpe, embargo, purging).",
            ("model_comparison", "model_holdout_equity", "prediction_accuracy"), ("Investment Research", "AI Operations"),
            ("Show model accuracy over the holdout period.", "Why did the model reject this opportunity?", "Show Prediction Memory.",
             "Which datasets are available?"), "model_accuracy"),
    Persona("ai_ops", "AI Operations Administrator", "AI Ops", "Agent health, failures, latency, data quality and evaluations.", ("ai_admin",), "operations",
            "Operational terminology (traces, p95, circuit breakers).", ("agent_graph",), ("AI Operations",),
            ("Why is an agent failing? Investigate the incident.", "Run data quality checks.", "Summarize evaluation results.",
             "Show the agent workflow for my last question."), "ai_operations"),
]}


def default_persona_for(roles: list[str] | tuple[str, ...]) -> str:
    rs = set(roles)
    for pid in ("cfo", "ceo", "cio", "portfolio_analyst", "wealth_advisor", "business_owner", "risk_compliance", "ai_ops"):
        if rs & set(PERSONAS[pid].typical_roles):
            return pid
    return "business_owner" if "prospect" in rs else "ceo"


def get(pid: str | None) -> Persona:
    return PERSONAS.get(pid or "", PERSONAS["ceo"])


def catalogue(roles: list[str] | tuple[str, ...]) -> dict:
    rs = set(roles)
    return {"starter_prompts": STARTER_PROMPTS, "default": default_persona_for(roles),
            "note": "Personas tailor suggestions and explanations. Your data access is determined by your sign-in and policy, not by the persona.",
            "personas": [{**asdict(p), "aligned_with_identity": bool(rs & set(p.typical_roles))} for p in PERSONAS.values()]}
