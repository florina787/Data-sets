import random

import pytest

from app.agents.grounding import allowed_numbers, ungrounded_numbers
from app.llm.cache import cache_key
from app.llm.resilience import CircuitBreaker, RateLimiter, backoff_delay, retry_after_seconds
from app.llm.usage import Usage, aggregate_stream_usage, estimate_cost, usage_from_metadata
from app.prompts.registry import get_prompt, load_all


def test_stream_usage_is_cumulative_not_summed():
    chunks = [{"prompt_token_count": 100, "candidates_token_count": 5, "total_token_count": 105},
              {"prompt_token_count": 100, "candidates_token_count": 40, "total_token_count": 140},
              None,
              {"prompt_token_count": 100, "candidates_token_count": 80, "total_token_count": 180}]
    u = aggregate_stream_usage(chunks)
    assert (u.input_tokens, u.output_tokens, u.total_tokens) == (100, 80, 180)
    naive = sum(usage_from_metadata(c).total_tokens for c in chunks)
    assert naive == 425 and naive != u.total_tokens


def test_usage_includes_thinking_tokens_and_cost():
    u = usage_from_metadata({"prompt_token_count": 1000, "candidates_token_count": 100, "thoughts_token_count": 50, "total_token_count": 1150})
    assert u.output_tokens == 150
    assert estimate_cost(Usage(1_000_000, 1_000_000, 2_000_000), 0.3, 2.5) == pytest.approx(2.8)


def test_backoff_is_bounded_with_jitter():
    rng = random.Random(1)
    vals = [backoff_delay(a, base=1, cap=8, rng=rng) for a in range(10)]
    assert all(0 <= v <= 8 for v in vals) and len(set(vals)) > 5


def test_retry_after_parsing():
    class E(Exception):
        details = {"error": {"details": [{"@type": "RetryInfo", "retryDelay": "17s"}]}}

    assert retry_after_seconds(E("429 RESOURCE_EXHAUSTED")) == 17.0
    assert retry_after_seconds(Exception("boom")) is None


def test_circuit_breaker_opens_and_half_opens():
    t = [0.0]
    cb = CircuitBreaker(threshold=2, cooldown=10, clock=lambda: t[0])
    cb.failure("x")
    assert cb.state == "closed"
    cb.failure("y")
    assert cb.state == "open" and not cb.allow()
    t[0] = 11
    assert cb.state == "half_open" and cb.allow()
    cb.success()
    assert cb.state == "closed"
    cb.failure("401", permanent=True)
    assert cb.state == "open"


def test_rate_limiter_waits_when_window_full():
    t = [0.0]
    slept = []

    def sleep(s):
        slept.append(s)
        t[0] += s

    rl = RateLimiter(rpm=2, max_concurrency=5, clock=lambda: t[0], sleep=sleep)
    for _ in range(3):
        rl.acquire(timeout=120)
        rl.release()
    assert rl.waits > 0 and t[0] >= 59


def test_cache_key_changes_with_any_material_input():
    base = cache_key("m", "p", "1.0", "sys", "user", "S", {"temperature": 0})
    assert base == cache_key("m", "p", "1.0", "sys", "user", "S", {"temperature": 0})
    for k in [cache_key("m2", "p", "1.0", "sys", "user", "S", {"temperature": 0}), cache_key("m", "p", "1.1", "sys", "user", "S", {"temperature": 0}),
              cache_key("m", "p", "1.0", "sys", "user2", "S", {"temperature": 0}), cache_key("m", "p", "1.0", "sys", "user", "S", {"temperature": 0.5})]:
        assert k != base


def test_grounding_detects_invented_numbers():
    facts = {"metrics": [{"value": 0.3504}, {"value": 239}, {"value": 682}]}
    ok = "239 of 682 conversations (35.0%) were negative; 35% overall, 95% CI shown."
    assert ungrounded_numbers(ok, allowed_numbers(facts)) == []
    assert ungrounded_numbers("Negative rate rose to 41.7% and cost $12,000.", allowed_numbers(facts)) == ["41.7", "12,000"]


def test_prompt_registry_loads_active_versions_and_validates_vars():
    prompts = load_all()
    assert {"intent_understanding", "message_classification", "grounded_explanation"} <= set(prompts)
    p = get_prompt("intent_understanding")
    assert p.status == "active" and p.output_schema == "IntentOutput"
    with pytest.raises(KeyError):
        p.render(question="x")
