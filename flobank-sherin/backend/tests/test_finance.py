"""Money engine: reconciliation, double counting, currency, token accounting, cost allocation."""
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app import models as M
from app.finance import engine as E

PERIODS = [("month", "2026-10"), ("month", "2025-12"), ("quarter", "2026-Q3"), ("ttm", "2026-10")]


@pytest.mark.parametrize("kind,value", PERIODS)
def test_reconciliation_identities_hold(client, kind, value):
    r = client.get("/api/finance/reconciliation", params={"period": kind, "value": value}).json()
    failed = [c for c in r["checks"] if not c["ok"]]
    assert not failed, failed


@pytest.mark.parametrize("kind,value", PERIODS)
def test_net_benefit_formula_and_no_double_counting(db, kind, value):
    p = E.resolve_period(kind, value)
    e = E.economics(db, p, "synthetic")
    ai = e["ai"]
    # Formula as specified, with workflow costs netted exactly once.
    assert e["net_benefit"] == e["attribution"]["incremental_profit"] + e["cost_avoidance"] - e["wf_cost_unverified"] - ai["overhead"] - ai["implementation"]
    # Equivalent identity: every AI cost is subtracted exactly once.
    assert e["net_benefit"] == e["attribution"]["incremental_profit"] + e["value_verified"] - ai["total"]
    assert ai["total"] == ai["workflow_linked"] + ai["overhead"] + ai["implementation"]
    # Attributed revenue itself is never added to net benefit (only its incremental profit).
    assert e["attribution"]["attributed_revenue"] > e["attribution"]["incremental_profit"]
    # Realized savings are a subset of cost avoidance and are not added.
    assert e["realized_savings"] <= e["cost_avoidance"]


def test_roi_definition(db):
    p = E.resolve_period("month", "2026-10")
    e = E.economics(db, p, "synthetic")
    assert e["roi_pct"] == (e["net_benefit"] / e["ai"]["total"] * 100).quantize(Decimal("0.1"))


def test_attributed_revenue_is_inside_fee_income_every_month(db):
    months = sorted({r for r in db.scalars(select(M.RevenueAttribution.period).distinct())})
    assert len(months) >= 12
    for m in months:
        e = E.economics(db, E.resolve_period("month", m), "synthetic")
        assert e["attribution"]["attributed_revenue"] <= e["bank"]["revenue_by_category"]["fees_commissions"], m
        assert e["realized_savings"] <= e["cost_avoidance"], m


def test_bank_revenue_excludes_aum_and_unrealised_returns(db):
    p = E.resolve_period("month", "2026-10")
    b = E.bank_totals(db, p, "synthetic")
    assert set(b["revenue_by_category"]) == {"net_interest_income", "fees_commissions", "trading_income", "wealth_management_fees", "other_income"}
    nav = db.scalar(select(func.sum(M.Position.market_value_usd)))
    assert b["revenue"] < Decimal(nav) / 10  # AUM (~1.6B) is nowhere near monthly revenue


def test_ai_cash_cost_is_a_line_inside_bank_opex(db):
    p = E.resolve_period("ttm", "2026-10")
    b, ai = E.bank_totals(db, p, "synthetic"), E.ai_cost_totals(db, p, "synthetic")
    assert b["opex_by_category"]["technology_sherin_ai"] == ai["total"] - ai["by_category"]["human_review"]


def test_token_rows_sum_to_task_model_cost(db):
    t, tu = M.AgentTask, M.TokenUsage
    sub = select(tu.task_id, func.sum(tu.api_cost_usd + tu.local_compute_usd + tu.local_energy_usd).label("c")).group_by(tu.task_id).subquery()
    mismatches = db.execute(select(t.id, t.cost_model, sub.c.c).join(sub, sub.c.task_id == t.id)).all()
    bad = [(i, a, b) for i, a, b in mismatches if E.q(a) != E.q(b)]
    assert mismatches and not bad, bad[:5]


def test_token_totals_match_rows(db):
    p = E.resolve_period("month", "2026-10")
    ta = E.token_analytics(db, p, "day", E.fx_for(db, "USD"), "synthetic")
    tu = M.TokenUsage
    i, o = db.execute(select(func.sum(tu.input_tokens), func.sum(tu.output_tokens)).where(E._between(tu.ts, p), tu.data_class == "synthetic")).one()
    assert ta["totals"]["tokens"] == i + o
    assert sum(ta["series"]["total"]) == i + o
    assert sum(r["tokens"] for r in ta["per_agent"]) == i + o
    assert ta["providers"]["local_qwen"]["cost"] > 0  # local inference still has compute + electricity cost
    assert ta["local_cost_components"]["allocated_compute"] > 0 and ta["local_cost_components"]["electricity"] > 0


def test_workflow_cost_allocation_by_category(db):
    t, r = M.AgentTask, M.AiCostRecord
    tasks = db.execute(select(func.sum(t.cost_model), func.sum(t.cost_compute), func.sum(t.cost_infra), func.sum(t.cost_tooling),
                              func.sum(t.cost_human_review + t.cost_rework)).where(t.data_class == "synthetic")).one()
    by = dict(db.execute(select(r.category, func.sum(r.amount_usd)).where(r.task_id.is_not(None), r.data_class == "synthetic").group_by(r.category)).all())
    assert [E.q(x) for x in tasks] == [E.q(by["llm_inference"]), E.q(by["compute"]), E.q(by["azure_infrastructure"]), E.q(by["third_party_tools"]), E.q(by["human_review"])]


@pytest.mark.parametrize("cur", ["INR", "CAD"])
def test_currency_conversion_is_exact_and_consistent(client, db, cur):
    usd = client.get("/api/finance/kpis").json()
    other = client.get("/api/finance/kpis", params={"currency": cur}).json()
    rate = Decimal(str(other["fx"]["rate"]))
    assert other["fx"]["source"] and other["fx"]["as_of"] and other["fx"]["data_class"] == "synthetic"
    for a, b in zip(usd["cards"], other["cards"]):
        if a["unit"] == "currency":
            assert Decimal(str(b["value"])) == (Decimal(str(a["value"])) * rate).quantize(Decimal("0.01")) or \
                   abs(Decimal(str(b["value"])) - Decimal(str(a["value"])) * rate) <= Decimal("0.01") * rate
        else:
            assert a["value"] == b["value"]  # ROI and task counts do not change with currency
    # Same metric, same number, on every chart that shows it.
    ai_card = next(c for c in other["cards"] if c["key"] == "ai_cost")["value"]
    br = client.get("/api/finance/ai-costs", params={"currency": cur}).json()
    assert br["total"] == ai_card


def test_charts_share_the_same_validated_metrics(client):
    k = {c["key"]: c for c in client.get("/api/finance/kpis").json()["cards"]}
    c = client.get("/api/finance/contribution").json()
    br = client.get("/api/finance/ai-costs").json()
    assert c["summary"]["net_benefit"] == client.get("/api/finance/kpis").json()["net_benefit"]
    assert round(c["summary"]["ai_opex"] + c["summary"]["implementation"], 2) == k["ai_cost"]["value"] == br["total"]
    assert c["summary"]["cost_avoidance"] == k["cost_avoidance"]["value"]
    assert c["summary"]["attributed_revenue"] == k["ai_revenue"]["value"]
    wf = c["waterfall"]
    assert round(sum(w["value"] for w in wf if w["measure"] == "relative"), 2) == wf[-1]["value"]
    re_ = client.get("/api/finance/revenue-expenditure", params={"granularity": "day"}).json()
    assert round(sum(re_["series"]["bank_revenue"]), 2) == k["bank_revenue"]["value"]
    assert round(sum(re_["series"]["ai_cost_total"]), 2) == k["ai_cost"]["value"]
    dept = client.get("/api/finance/departments").json()
    assert round(sum(r["cost_avoidance"] for r in dept["rows"]), 2) == k["cost_avoidance"]["value"]


@pytest.mark.parametrize("g", ["day", "week", "month", "quarter", "year"])
def test_granularities_preserve_totals(client, g):
    base = client.get("/api/finance/revenue-expenditure", params={"granularity": "day", "period": "ttm"}).json()
    r = client.get("/api/finance/revenue-expenditure", params={"granularity": g, "period": "ttm"}).json()
    assert round(sum(r["series"]["bank_opex"]), 2) == round(sum(base["series"]["bank_opex"]), 2)


def test_kpi_cards_have_mom_budget_and_labels(client):
    k = client.get("/api/finance/kpis").json()
    assert [c["key"] for c in k["cards"]] == E.KPI_ORDER
    for c in k["cards"]:
        assert c["basis"] in ("actual", "estimated") and c["data_class"] == "synthetic" and c["definition"]
    by = {c["key"]: c for c in k["cards"]}
    assert by["operating_profit"]["value"] == round(by["bank_revenue"]["value"] - by["bank_opex"]["value"], 2)
    assert by["ai_cost"]["budget"] and by["ai_cost"]["budget_utilization_pct"] and by["bank_revenue"]["mom_pct"] is not None
    assert by["cost_avoidance"]["basis"] == "estimated"
    for key in E.KPI_ORDER:
        d = client.get(f"/api/finance/kpis/{key}").json()
        assert d["rows"], key


def test_forecast_is_labelled_and_has_three_scenarios(client):
    f = client.get("/api/finance/forecast").json()
    assert f["available"] and f["basis"] == "forecast" and "not guarantees" in f["disclaimer"]
    assert set(f["scenarios"]) == {"best", "base", "downside"}
    assert len(f["scenarios"]["base"]["series"]) == 12


def test_cost_records_drilldown(client):
    r = client.get("/api/finance/ai-costs/llm_inference/records", params={"limit": 5}).json()
    assert r["count"] > 0 and len(r["records"]) == 5 and all(x["task_id"] for x in r["records"])
    assert client.get("/api/finance/ai-costs/bogus/records").status_code == 404


def test_human_vs_ai_includes_review_and_rework(client):
    rows = client.get("/api/finance/human-vs-ai").json()["rows"]
    assert len(rows) == 8
    for r in rows:
        parts = r["ai_per_task"]
        assert parts["human_review"] > 0
        assert abs(sum(parts.values()) - r["ai_assisted_per_task"]) < 0.08  # per-component rounding


def test_measured_and_synthetic_are_separate(client):
    k = client.get("/api/finance/kpis", params={"dc": "measured"}).json()
    by = {c["key"]: c for c in k["cards"]}
    assert by["bank_revenue"]["value"] == 0  # no fabricated revenue in the measured view
