"""Static reference data: departments, workflow types, agents, tool permissions and price cards."""
from __future__ import annotations

from decimal import Decimal

DEPARTMENTS = {
    "portfolio_operations": "Portfolio operations",
    "python_engineering": "Python engineering",
    "azure_devops": "Azure DevOps",
    "risk_management": "Risk management",
    "compliance": "Compliance",
    "data_engineering": "Data engineering",
    "qa": "QA",
    "executive_reporting": "Executive reporting",
}

# workflow_type -> (department, label, human hours per task, loaded hourly rate USD)
# The baseline is a *configured assumption* owned by Finance, not a measurement. It is editable via the API.
WORKFLOW_BASELINES: dict[str, tuple[str, str, str, str]] = {
    "python_development": ("python_engineering", "Python development", "3.0", "95"),
    "azure_devops": ("azure_devops", "Azure DevOps", "2.0", "105"),
    "portfolio_reconciliation": ("portfolio_operations", "Portfolio reconciliation", "1.5", "80"),
    "qa_testing": ("qa", "QA testing", "2.5", "75"),
    "investment_risk_analysis": ("risk_management", "Investment risk analysis", "2.0", "120"),
    "compliance_reporting": ("compliance", "Compliance reporting", "3.0", "90"),
    "incident_investigation": ("azure_devops", "Incident investigation", "1.5", "110"),
    "data_engineering": ("data_engineering", "Data engineering", "2.5", "100"),
    "executive_reporting": ("executive_reporting", "Executive reporting", "2.0", "130"),
    "esg_review": ("compliance", "ESG review", "1.5", "95"),
    "security_review": ("azure_devops", "Security review", "1.75", "125"),
    "finops_review": ("executive_reporting", "FinOps review", "1.25", "110"),
}

# The eight workflow families compared in the Human vs AI chart.
HUMAN_VS_AI_WORKFLOWS = ["python_development", "azure_devops", "portfolio_reconciliation", "qa_testing",
                         "investment_risk_analysis", "compliance_reporting", "incident_investigation", "data_engineering"]

AGENTS: dict[str, dict] = {
    "python_coding": {"label": "Python Coding Agent", "workflow": "python_development",
                      "tools": ["repo.read", "python.ast_debug", "python.test_gen", "diff.propose"]},
    "azure_devops": {"label": "Azure DevOps Agent", "workflow": "azure_devops",
                     "tools": ["repo.read", "ado.work_items", "ado.pull_request.draft", "infra.config_review"]},
    "cicd": {"label": "CI/CD Agent", "workflow": "azure_devops",
             "tools": ["pipeline.yaml_lint", "pipeline.logs", "deploy.request_approval"]},
    "sre": {"label": "SRE Agent", "workflow": "incident_investigation",
            "tools": ["monitor.query", "appinsights.query", "aks.describe", "functions.diagnose", "adf.diagnose"]},
    "data_engineering": {"label": "Data Engineering Agent", "workflow": "data_engineering",
                         "tools": ["adf.diagnose", "sql.read", "data.profile"]},
    "portfolio_management": {"label": "Portfolio Management Agent", "workflow": "portfolio_reconciliation",
                             "tools": ["portfolio.read", "portfolio.reconcile"]},
    "investment_judgment": {"label": "Investment Judgment Agent", "workflow": "investment_risk_analysis",
                            "tools": ["portfolio.read", "guardian.evaluate"]},
    "risk_analytics": {"label": "Risk Analytics Agent", "workflow": "investment_risk_analysis",
                       "tools": ["portfolio.read", "risk.var", "risk.concentration"]},
    "esg": {"label": "ESG Agent", "workflow": "esg_review", "tools": ["portfolio.read", "esg.scores"]},
    "compliance": {"label": "Compliance Agent", "workflow": "compliance_reporting",
                   "tools": ["compliance.events", "policy.read", "report.generate"]},
    "qa": {"label": "QA Agent", "workflow": "qa_testing", "tools": ["python.test_gen", "tests.run_plan"]},
    "reporting": {"label": "Reporting Agent", "workflow": "executive_reporting",
                  "tools": ["finance.read", "report.generate"]},
    "security": {"label": "Security Agent", "workflow": "security_review",
                 "tools": ["repo.read", "secrets.scan", "infra.config_review"]},
    "finops": {"label": "FinOps Agent", "workflow": "finops_review", "tools": ["finance.read", "tokens.read"]},
    "verification": {"label": "Independent Verification Agent", "workflow": None,
                     "tools": ["verify.outputs", "finance.read"]},
}

# Tools that change state outside the harness always need a human decision first.
APPROVAL_REQUIRED_TOOLS = {"deploy.request_approval", "ado.pull_request.draft", "diff.propose"}

AI_COST_CATEGORIES = {
    "llm_inference": "LLM inference",
    "compute": "Compute",
    "azure_infrastructure": "Azure infrastructure",
    "storage": "Storage",
    "networking": "Networking",
    "monitoring": "Monitoring",
    "third_party_tools": "Third-party tools",
    "human_review": "Human review",
    "maintenance": "Maintenance",
    "implementation_allocated": "Allocated implementation",
}

# Synthetic price card for the paid model tier (USD per million tokens). Clearly an assumption.
PAID_MODEL = "paid-frontier-model"
PAID_PRICE_PER_M = {"input": Decimal("3.00"), "output": Decimal("15.00"), "cached": Decimal("0.30")}
LOCAL_MODEL = "qwen2.5:7b-instruct (Ollama)"

REVENUE_CATEGORIES = {
    "net_interest_income": "Net interest income",
    "fees_commissions": "Fees and commissions",
    "trading_income": "Trading income",
    "wealth_management_fees": "Wealth management fees",
    "other_income": "Other income",
}
OPEX_CATEGORIES = {
    "staff": "Staff costs",
    "technology": "Technology (excluding Sherin AI)",
    "technology_sherin_ai": "Technology - Sherin AI",
    "premises": "Premises",
    "marketing": "Marketing",
    "professional_services": "Professional services",
    "other_opex": "Other operating expenses",
}

IMPLEMENTATION_CAPEX_USD = Decimal("1200000.00")  # synthetic programme cost
IMPLEMENTATION_AMORTISATION_MONTHS = 36
