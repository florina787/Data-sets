"""Canonical feature registry and plan configuration.

Every billable feature has exactly one entry here. The registry is seeded into the
``feature_catalog`` / ``feature_entitlements`` tables at start-up so SQL reporting can join on it,
but this module stays the source of truth the metering code reads.
"""
from __future__ import annotations

from dataclasses import dataclass, field

TRIAL_LIMIT = 2  # every new account: exactly two successful uses of every premium feature


@dataclass(frozen=True)
class Feature:
    id: str
    name: str
    description: str
    unit: str
    # Rough marginal cost per use in CAD cents (CPU inference + provider calls); used for margin estimates.
    est_cost_cents: float = 0.5
    trial_limit: int = TRIAL_LIMIT


FEATURES: dict[str, Feature] = {f.id: f for f in [
    Feature("job_discovery", "AI Job Discovery", "Search, filter and de-duplicate jobs across providers.", "search", 0.3),
    Feature("job_board_search", "Indeed / LinkedIn Search", "Indeed- and LinkedIn-origin postings through an authorised aggregator.", "search", 0.4),
    Feature("job_matching", "Job Matching", "Explainable match score between your verified resume and a job.", "analysis", 0.2),
    Feature("resume_optimization", "Resume Optimization", "Tailor your resume to a job without inventing facts; PDF/DOCX export.", "resume", 1.5),
    Feature("ats_intelligence", "ATS Intelligence", "Keyword coverage, structure and parse-ability check.", "analysis", 0.2),
    Feature("cover_letter", "Cover Letter Generation", "Tailored cover letter and recruiter message from verified facts.", "letter", 1.0),
    Feature("mock_interview", "AI Mock Interviews", "Interactive technical / behavioural interview with rubric feedback.", "session", 2.0),
    Feature("coding_coach", "Live Coding Coach", "Coding exercises evaluated in a sandbox.", "session", 0.5),
    Feature("company_research", "Company Research", "Company brief from verifiable public sources with citations.", "report", 0.8),
    Feature("salary_intelligence", "Salary Intelligence", "Published-salary distribution and negotiation scenarios.", "report", 0.3),
    Feature("portfolio_analysis", "GitHub Portfolio Analysis", "Analyse public repositories and map projects to a job.", "analysis", 0.6),
    Feature("recruiter_intelligence", "Recruiter Intelligence", "Recruiter relationship report and follow-up plan.", "report", 0.5),
    Feature("application_automation", "Application Automation", "Prepare an application package with approval gates.", "workflow", 2.5),
    Feature("career_analytics", "Career Analytics", "Funnel, conversion, salary and skill-gap report.", "report", 0.1),
    Feature("ai_chat", "AI Career Assistant", "A bounded conversation with the Qwen career assistant.", "conversation", 3.0),
    Feature("multi_agent_workflow", "Multi-Agent Workflows", "Supervisor-coordinated multi-step career workflow.", "workflow", 4.0),
    Feature("career_graph", "Career Graph Intelligence", "Knowledge, context and procedural graphs: what's true, what matters now, what to do next.", "graph", 0.2),
]}


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    price_cents: int
    currency: str
    priority: int
    # Monthly allowance per feature; features missing from the dict are not included in the plan.
    monthly_limits: dict[str, int] = field(default_factory=dict)
    highlights: tuple[str, ...] = ()


_PRO = {
    "job_discovery": 150, "job_board_search": 60, "job_matching": 200, "resume_optimization": 40,
    "ats_intelligence": 80, "cover_letter": 40, "mock_interview": 20, "coding_coach": 30,
    "company_research": 30, "salary_intelligence": 30, "recruiter_intelligence": 20,
    "application_automation": 10, "career_analytics": 60, "ai_chat": 60, "multi_agent_workflow": 10, "career_graph": 60,
}
_PREMIUM = {k: v * 3 for k, v in _PRO.items()} | {"portfolio_analysis": 30, "multi_agent_workflow": 40}

PLANS: dict[str, Plan] = {
    "free": Plan("free", "Free", 0, "CAD", 0, {}, (
        "Account and profile", "2 free uses of every premium feature", "Access to your saved records")),
    "pro": Plan("pro", "Pro", 999, "CAD", 1, _PRO, (
        "Higher monthly AI allowances", "Resume optimisation & job matching", "Mock interviews",
        "Career analytics & tracking", "Standard processing priority")),
    "premium": Plan("premium", "Premium", 1999, "CAD", 2, _PREMIUM, (
        "Everything in Pro with ~3x allowances", "Advanced multi-agent workflows", "GitHub portfolio intelligence",
        "Interview coaching", "Priority processing")),
}

# Paid subscriptions in these Stripe states grant plan entitlements.
ENTITLED_STATUSES = {"active", "trialing"}
# past_due keeps access during Stripe's retry window (Smart Retries); unpaid/canceled do not.
GRACE_STATUSES = {"past_due"}


# Chatbot conversation bounds (shown to the user before a session starts).
CHAT_LIMITS = {"max_messages": 20, "max_tokens": 12000, "max_minutes": 30, "max_tool_calls": 12}
