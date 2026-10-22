"""Zero-LLM Intelligence Router decisions and honest token accounting."""

from app.agents.intent_rules import parse_intent
from app.agents.router import decide
from app.llm.usage import Usage, aggregate_stream_usage, estimate_cost, usage_from_metadata, usage_from_openai
from app.observability.store import usage_summary


def route(q, mode="auto", available=True):
    return decide(q, mode, parse_intent(q), available, "no key")


def test_auto_routes_fact_questions_to_analytics_only():
    for q in ["What were the top 5 topics most associated with negative customer sentiment in the last month?",
              "Show the sentiment trend over time.", "What does the dataset cover?"]:
        assert route(q)["route"] == "analytics_only" and route(q)["llm_steps"] == []


def test_auto_routes_interpretation_and_unparsed_questions_to_hybrid():
    r = route("Why is duplicate charge the most negative topic?")
    assert r["route"] == "hybrid_ai" and r["llm_steps"] == ["explanation"] and r["interpretive_cue"].lower() == "why"
    r = route("Where is customer frustration concentrated?")
    assert r["route"] == "hybrid_ai" and "intent" in r["llm_steps"]


def test_policy_refusals_and_unavailable_llm_are_analytics_only():
    assert route("Which agents should be fired?")["route"] == "analytics_only"
    r = route("Why is sentiment falling?", mode="hybrid_ai", available=False)
    assert r["route"] == "analytics_only" and r["reason"].startswith("HYBRID AI requested, but no LLM")
    assert route("Why is sentiment falling?", mode="analytics_only")["route"] == "analytics_only"
    assert route("Show the sentiment trend.", mode="hybrid_ai")["llm_steps"] == ["intent", "explanation"]


def test_missing_usage_metadata_is_unknown_not_zero():
    assert usage_from_metadata(None).reported is False
    assert usage_from_openai(None).reported is False and usage_from_openai({"prompt_tokens": 3, "completion_tokens": 2}).total_tokens == 5
    assert aggregate_stream_usage([None, None]).reported is False
    # cumulative streaming counts are not summed
    s = aggregate_stream_usage([{"prompt_token_count": 10, "candidates_token_count": 1}, {"prompt_token_count": 10, "candidates_token_count": 7}])
    assert (s.input_tokens, s.output_tokens, s.reported) == (10, 7, True)
    assert estimate_cost(Usage(reported=False), 1, 1) is None
    assert Usage(1, 1, 2).add(Usage(reported=False)).reported is False


def row(total, cache=False, purpose="explanation"):
    return {"purpose": purpose, "model": "m", "input_tokens": total, "output_tokens": 0 if total is not None else None, "total_tokens": total,
            "cache_hit": int(cache), "status": "ok", "latency_ms": 1.0, "estimated_cost_usd": 0.0 if total is not None else None}


def test_usage_summary_null_vs_zero():
    assert usage_summary([])["total_tokens"] == 0  # no call made: genuinely zero
    assert usage_summary([row(None)])["total_tokens"] is None  # call made, nothing reported: unknown
    s = usage_summary([row(100), row(None)])
    assert s["total_tokens"] == 100 and s["complete"] is False and s["unreported_calls"] == 1
    s = usage_summary([row(0, cache=True)])
    assert s["total_tokens"] == 0 and s["cache_hits"] == 1 and s["model_calls"] == 0
