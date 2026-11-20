"""Cost and ROI engines are deterministic; ROI can reject AI."""

from __future__ import annotations

import pytest

from app.cost.engine import calculate_cost
from app.cost.pricing import PricingError, load_pricing
from app.models.enums import ArchitectureOption, ROIVerdict
from app.models.inputs import CostInputs, ROIInputs
from app.roi.engine import calculate_roi

A = ArchitectureOption


# 11
def test_cost_calculations_are_deterministic():
    inputs = CostInputs(requests_per_month=123_456, avg_input_tokens=1800, avg_output_tokens=420, cache_hit_rate=0.4, small_model_routing_pct=0.3)
    first = calculate_cost(inputs, A.RAG_GENAI)
    for _ in range(5):
        assert calculate_cost(inputs, A.RAG_GENAI).model_dump() == first.model_dump()


def test_cost_matches_hand_calculation():
    pricing = load_pricing()
    premium = pricing["models"]["premium_model"]
    inputs = CostInputs(
        requests_per_month=1000, avg_input_tokens=1000, avg_output_tokens=100, rag_top_k=0, cache_hit_rate=0.0,
        small_model_routing_pct=0.0, batch_pct=0.0, human_review_pct=0.0, infrastructure_cost_month=0.0, llm_calls_per_request=1,
    )
    c = calculate_cost(inputs, A.GENERATIVE_AI)
    expected_per_request = (1000 * premium["input_per_mtok"] + 100 * premium["output_per_mtok"]) / 1_000_000
    assert c.cost_per_request == pytest.approx(expected_per_request)
    assert c.model_cost_month == pytest.approx(expected_per_request * 1000, abs=0.01)


def test_optimizations_reduce_model_cost():
    base = CostInputs(cache_hit_rate=0.0, small_model_routing_pct=0.0, max_output_tokens=None)
    tuned = base.model_copy(update={"cache_hit_rate": 0.5, "small_model_routing_pct": 0.6, "max_output_tokens": 200, "batch_pct": 0.3})
    assert calculate_cost(tuned, A.RAG_GENAI).model_cost_month < calculate_cost(base, A.RAG_GENAI).model_cost_month
    assert calculate_cost(tuned, A.RAG_GENAI).optimization_savings_month > 0


def test_agentic_costs_more_than_rag_and_no_ai_costs_nothing_new():
    inputs = CostInputs(current_monthly_cost=1000)
    agent = calculate_cost(inputs, A.AGENTIC_AI)
    rag = calculate_cost(inputs, A.RAG_GENAI)
    keep = calculate_cost(inputs, A.KEEP_EXISTING)
    assert agent.model_cost_month > rag.model_cost_month
    assert keep.model_cost_month == 0 and keep.proposed_cost_month == 1000 and keep.expected_savings_month == 0
    assert set(agent.comparison_by_architecture) == {o.value for o in A}


def test_pricing_file_is_labelled_as_sample():
    pricing = load_pricing()
    assert "SAMPLE" in pricing["_disclaimer"].upper()


def test_unknown_model_raises():
    with pytest.raises(PricingError):
        calculate_cost(CostInputs(primary_model="does-not-exist"), A.GENERATIVE_AI)


# 9
def test_roi_can_conclude_do_not_implement_ai():
    roi = calculate_roi(ROIInputs(tasks_per_month=100, minutes_per_task=5, hourly_cost=40, implementation_cost=200_000), ai_operating_cost_annual=30_000)
    assert roi.verdict is ROIVerdict.NOT_JUSTIFIED
    assert roi.verdict.value == "ROI DOES NOT JUSTIFY AI"
    assert roi.payback_months is None


def test_roi_low_value_scenario_results_in_no_ai(assess):
    r = assess("general-hr-faq-low-roi")
    assert r.decision.ai_recommended is False
    assert r.decision.ai_verdict_label == "DO NOT USE AI"
    assert r.roi.verdict is ROIVerdict.NOT_JUSTIFIED
    assert r.challenger.revisions_applied >= 1
    assert any("ROI" in rule for rule in r.decision.triggered_rules)


def test_roi_justified_with_payback():
    roi = calculate_roi(ROIInputs(tasks_per_month=6000, minutes_per_task=25, hourly_cost=70, implementation_cost=350_000, expected_time_reduction_pct=40), 200_000)
    assert roi.verdict is ROIVerdict.JUSTIFIED
    assert roi.payback_months is not None and roi.payback_months < 18
    assert roi.net_annual_benefit == pytest.approx(roi.estimated_annual_benefit - 200_000)


def test_roi_is_deterministic():
    inputs = ROIInputs()
    assert calculate_roi(inputs, 50_000).model_dump() == calculate_roi(inputs, 50_000).model_dump()
