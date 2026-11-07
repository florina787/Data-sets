import pytest

from app.agent import supervisor
from app.errors import AppError
from app.semantic.planner import apply_followup, compile_sql, plan_question


@pytest.mark.parametrize("q,metric,dim,filters", [
    ("What was our total recognized revenue in USD for paid invoices in 2024?", "paid_revenue", None, {"invoice_year": [2024]}),
    ("Which region has the highest average MRR per account?", "avg_mrr", "region", {}),
    ("How much have we given back in refunds?", "refunds", None, {}),
    ("What's the churn rate among Enterprise accounts vs Starter?", "churn_rate", "plan", {"plan": ["Enterprise", "Starter"]}),
    ("List the top 5 accounts by revenue, and flag any with CSAT ≤ 2.", "net_revenue", "account", {}),
    ("How many invoices are stuck in pending/failed and what's the exposed $?", "exposure_count", None, {}),
    ("net revenue by industry in 2023", "net_revenue", "industry", {"invoice_year": [2023]}),
    ("monthly revenue trend", "net_revenue", "invoice_month", {}),
    ("churn rate by region", "churn_rate", "region", {}),
    ("revenue from customers with low CSAT", "net_revenue", None, {"csat_max": [2]}),
])
def test_plans(q, metric, dim, filters):
    p = plan_question(q)
    assert p.primary == metric and p.group_by == dim and p.filters == filters


def test_unmodeled_measure_lowers_confidence():
    assert plan_question("average support tickets for churned accounts").confidence < 0.6


def test_flag_is_not_a_filter():
    p = plan_question("List the top 5 accounts by revenue, and flag any with CSAT ≤ 2.")
    assert p.flag_low_csat and "csat_max" not in p.filters and p.limit == 5


def test_account_metric_drops_invoice_filters_with_note():
    p = plan_question("churn rate in 2024")
    assert "invoice_year" not in p.filters and p.notes


def test_followups_patch_previous_plan():
    p = plan_question("Show revenue by region")
    p2 = apply_followup(p, "Only Enterprise")
    assert p2.group_by == "region" and p2.filters == {"plan": ["Enterprise"]}
    p3 = apply_followup(p2, "now by plan")
    assert p3.group_by == "plan" and p3.filters == {"plan": ["Enterprise"]}
    assert apply_followup(p3, "turn it into a chart").chart
    assert "i.plan = 'Enterprise'" in compile_sql(p3)


def test_supervisor_routes_and_memory():
    sid = supervisor.new_session()
    r = supervisor.ask("Show revenue by region", sid)
    assert r["intent"] == "analytics" and r["planner"] == "semantic" and r["sql"] and r["chart"]["type"] == "bar"
    r2 = supervisor.ask("Only Enterprise", sid)
    assert "Enterprise" in r2["answer"] and r2["filters"] == {"plan": "Enterprise"}
    assert supervisor.ask("Why did Acme Ltd churn?", sid)["intent"] == "out_of_scope"
    assert supervisor.ask("forecast revenue for next year", sid)["intent"] == "out_of_scope"
    assert supervisor.ask("how did you parse ambiguous dates?", sid)["intent"] == "data_quality"


def test_general_chat_without_llm_is_an_error_not_a_fabrication():
    with pytest.raises(AppError) as e:
        supervisor.ask("hello there")
    assert e.value.code == "llm_unavailable"


def test_unmapped_data_question_without_llm_asks_to_clarify():
    r = supervisor.ask("average support tickets for churned accounts")
    assert r["intent"] == "clarify" and r["sql"] is None
