"""Unit tests for the conversational workspace: firm model (hand-computed), figure extraction, intent rules, the
allowlisted chart schema, recommendation evidence and practice analytics consistency."""
from decimal import Decimal as D

import pytest
from pydantic import ValidationError

from analytics import practice, service as fin
from analytics.firm_model import FirmProfile, assess
from conversation import recommend
from conversation.intent import classify, scenario_of
from conversation.onboarding import extract_profile
from conversation.schemas import ChartSpec, Recommendation
from integrations.mock.adapters import Adapters


def _m(a, key):
    return next(x for x in a["metrics"] if x["key"] == key)


def test_firm_model_aum_only_uses_labelled_fee_range():
    a = assess(FirmProfile(aum=D("500000000")))
    rev = _m(a, "revenue")
    assert rev["value"] == 3_750_000 and rev["provenance"] == "illustrative_assumption"  # 500m x 75 bps
    assert [x["revenue"] for x in a["fee_range"]] == [2_500_000, 3_750_000, 5_000_000]  # 50 / 75 / 100 bps
    assert a["sensitivities"]["revenue_per_1bp_fee"] == 50_000 and a["sensitivities"]["provenance"] == "illustrative_assumption"
    assert a["assumptions"][0]["name"] == "average_fee_bps" and "operating_margin" not in [m["key"] for m in a["metrics"]]
    assert _m(a, "aum")["provenance"] == "user_supplied"


def test_firm_model_with_user_figures_is_hand_computed():
    a = assess(FirmProfile(aum=D("500000000"), fee_bps=D("85"), expenses=D("3100000"), advisors=8, clients=1200))
    assert _m(a, "revenue")["value"] == 4_250_000 and _m(a, "revenue")["provenance"] == "calculated_from_user_inputs"
    assert _m(a, "operating_margin")["value"] == pytest.approx((4_250_000 - 3_100_000) / 4_250_000, abs=1e-4)
    assert _m(a, "aum_per_advisor")["value"] == 62_500_000 and _m(a, "revenue_per_advisor")["value"] == 531_250
    assert _m(a, "clients_per_advisor")["value"] == 150 and _m(a, "aum_per_client")["value"] == pytest.approx(416_666.67, abs=0.01)
    assert not a["assumptions"]  # nothing assumed once the fee is supplied
    down20 = next(x for x in a["market_scenarios"] if x["market_move"] == -0.2)
    assert down20["aum"] == 400_000_000 and down20["annual_fee_revenue"] == 3_400_000
    assert {x["module"]: x["status"] for x in a["data_readiness"]}["Profitability"] == "available"


@pytest.mark.parametrize("text,expected", [
    ("I own an investment advisory firm managing CAD 500 million.", {"aum": 500e6}),
    ("We have 8 advisors, 1,200 client households, an average fee of 0.85% and expenses of CAD 3.1 million.",
     {"advisors": 8, "clients": 1200, "fee_bps": 85.0, "expenses": 3.1e6}),
    ("Revenue was $4.2m last year and net inflows of CAD 25 million", {"revenue": 4.2e6, "net_flows": 25e6}),
    ("our fee is 90 bps", {"fee_bps": 90.0}),
    ("In 2026 we had 3 offsites", {}),
    ("Prepare a review for C-00226", {}),
])
def test_extract_profile_only_explicit_figures(text, expected):
    assert extract_profile(text) == expected


def test_scenario_parsing():
    assert scenario_of("Simulate a 20% equity market downturn") == {"equity_shock": -0.2, "preset": "bear"}
    assert scenario_of("What happens if rates rise by 200 basis points?") == {"rate_shock_bps": 200.0}
    assert scenario_of("rates fall 50 bps") == {"rate_shock_bps": -50.0}
    assert scenario_of("severe stress test")["preset"] == "severe_stress"


@pytest.mark.parametrize("user,text,state,intent,mods", [
    ("u-ceo", "Why is our AUM growing while profitability declines?", {}, "aum_profitability", {}),
    ("u-ceo", "Now show the last 24 months.", {"last_intent": "aum_profitability"}, "aum_profitability", {"months": 24}),
    ("u-ceo", "Break this down by product.", {"last_intent": "aum_profitability"}, "aum_profitability", {"group_by": "product"}),
    ("u-ceo", "What happens if rates rise by 200 basis points?", {"last_intent": "aum_profitability"}, "scenario", {"scenario": {"rate_shock_bps": 200.0, "preset": "base"}}),
    ("u-ceo", "Prepare a board-level summary.", {"last_intent": "scenario"}, "executive_briefing", {}),
    ("u-ceo", "Explain the largest risk.", {"last_intent": "aum_profitability"}, "risk_overview", {}),
    ("u-cio", "Simulate a 20% equity market downturn.", {}, "scenario", {"scenario": {"equity_shock": -0.2, "preset": "bear"}}),
    ("u-advisor", "Prepare a portfolio review for client C-00226.", {}, "client_review", {}),
    ("u-advisor", "Can you help manage my investment firm?", {}, "book_overview", {}),
    ("u-prospect", "Can you help manage my investment firm?", {}, "business_onboarding", {}),
    ("u-ceo", "Hello FLO, I own an investment advisory firm managing CAD 500 million.", {}, "business_onboarding", {}),
    ("u-ceo", "hello", {}, "greeting", {}),
])
def test_intent_rules(P, engine, user, text, state, intent, mods):
    plan = classify(text, "ceo", P[user], engine, state)
    assert plan.intent.id == intent
    for k, v in mods.items():
        assert plan.modifiers.get(k) == v


def test_followup_carries_entity_ids_not_values(P, engine):
    plan = classify("Build a client retirement strategy.", "wealth_advisor", P["u-advisor"], engine, {"last_intent": "client_review", "client_id": "C-00226"})
    assert plan.intent.id == "retirement_strategy" and plan.entities == {"client_id": "C-00226"}


def _chart(**kw):
    base = dict(chart_id="t1", chart_type="line", title="t", categories=["a", "b"], series=[{"name": "s", "values": [1, 2]}])
    return ChartSpec(**{**base, **kw})


def test_chart_schema_allowlist_and_shape():
    assert _chart().schema_version == "flo.viz/1.0"
    with pytest.raises(ValidationError):
        _chart(chart_type="custom_js")  # not in the allowlist
    with pytest.raises(ValidationError):
        _chart(series=[{"name": "s", "values": [1, 2, 3]}])  # length mismatch
    with pytest.raises(ValidationError):
        _chart(series=[{"name": "s", "values": [1, float("nan")]}])  # non-finite
    with pytest.raises(ValidationError):
        _chart(chart_id="Bad Id;")
    with pytest.raises(ValidationError):
        ChartSpec(chart_id="h", chart_type="heatmap", title="h", x_labels=["1"], y_labels=["1"], cells=[[3, 0, 1]])
    with pytest.raises(ValidationError):
        ChartSpec(chart_id="g", chart_type="agent_graph", title="g", nodes=[{"id": "a", "name": "a"}], edges=[{"source": "a", "target": "zz"}])
    with pytest.raises(ValidationError):
        _chart(categories=[str(i) for i in range(3000)], series=[{"name": s, "values": [1] * 3000} for s in ("a", "b")])


def test_recommendations_require_evidence_and_carry_no_invented_returns():
    with pytest.raises(ValidationError):
        Recommendation(id="R1", title="x", priority="P1", rationale="r", evidence=[], expected_benefit="b", complexity="low", owner_function="f",
                       timeframe="0-30 days")
    assert not {"roi", "confidence", "expected_return", "probability"} & set(Recommendation.model_fields)


def test_recommendation_engine_cites_facts():
    facts = {"financial_performance_agent": {"margin_pct": 27.85, "prior_margin_pct": 30.69, "revenue_growth_pct": 4.89, "opex_growth_pct": 9.19,
                                             "gap_pp": 4.3, "top_expense_line": "technology", "top_expense_increase_m": 5.1}}
    out = recommend.build("revenue_drivers", facts, True, ("Finance",))
    r = out["recommendations"][0]
    assert r.priority == "P1" and r.owner_function == "Finance" and {e.fact for e in r.evidence} >= {"gap_pp", "top_expense_line"}
    assert out["plan"] is not None and len(out["plan"].phases) == 3


def test_retention_definition_matches_executive_kpi(st):
    a = Adapters(st, "t-flo")
    assert practice.retention_overview(a)["data"]["retention_12m"] == fin.executive_kpis(a, 12)["data"]["client_retention"]


def test_advisor_productivity_reconciles_to_active_clients(st):
    a = Adapters(st, "t-flo")
    rows = practice.advisor_productivity(a)["data"]["advisors"]
    assert sum(r["active_clients"] for r in rows) == sum(1 for c in a.crm.clients() if c["status"] == "active")
    assert all(r["advisor_id"].startswith("A-") for r in rows) and "full_name" not in rows[0]


def test_book_health_is_scoped_to_one_advisor(st):
    a = Adapters(st, "t-flo")
    b = practice.book_health(a, "A-001")["data"]
    mine = {c["id"] for c in a.crm.clients("A-001")}
    assert {x["client_id"] for x in b["at_risk_clients"]} <= mine and b["active_clients"] == sum(1 for c in a.crm.clients("A-001") if c["status"] == "active")
    assert practice.book_health(a, None)["data"]["active_clients"] == 0
