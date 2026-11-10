import json

import pytest

from app.llm.gemini_client import LLMUnavailable
from app.llm.structured_output import IntentOutput
from app.observability.store import get_telemetry
from app.prompts.registry import get_prompt
from tests.fakes import APIError, fake_gemini

GOOD = json.dumps({"category": "negative_topics", "time_window": {"type": "last_month"}, "top_n": 5})


def call(client, user="q"):
    return client.generate_json(get_prompt("intent_understanding"), user, IntentOutput, request_id="R-test", purpose="intent")


def test_structured_output_parsed_and_usage_recorded(env):
    client, models = fake_gemini([GOOD])
    r = call(client, "unique-1")
    assert r.parsed.category == "negative_topics" and r.usage.total_tokens == 150 and not r.cache_hit
    calls = get_telemetry()._all("SELECT * FROM llm_calls WHERE request_id='R-test' ORDER BY id DESC LIMIT 1")
    assert calls[0]["total_tokens"] == 150 and calls[0]["status"] == "ok"


def test_cache_hit_on_identical_request(env):
    client, models = fake_gemini([GOOD])
    call(client, "unique-cache")
    r = call(client, "unique-cache")
    assert r.cache_hit and len(models.calls) == 1


def test_invalid_json_gets_one_repair_attempt(env):
    client, models = fake_gemini(["not json", GOOD])
    r = call(client, "unique-repair")
    assert r.repaired and len(models.calls) == 2 and "did not match the required JSON schema" in models.calls[1]


def test_invalid_enum_twice_is_rejected(env):
    bad = json.dumps({"category": "make_up_numbers"})
    client, _ = fake_gemini([bad, bad])
    with pytest.raises(LLMUnavailable, match="schema validation"):
        call(client, "unique-bad")


def test_rate_limit_retries_with_server_delay(env):
    slept = []
    client, models = fake_gemini([APIError(429, "RESOURCE_EXHAUSTED", {"retryDelay": "7s"}), GOOD])
    client._sleep = slept.append
    r = call(client, "unique-429")
    assert r.retries == 1 and slept == [7.0]


def test_timeouts_exhaust_retries_then_fail(env):
    client, models = fake_gemini([TimeoutError("timed out")] * 3)
    with pytest.raises(LLMUnavailable):
        call(client, "unique-timeout")
    assert len(models.calls) == 3  # 1 + max_retries(2)


def test_auth_error_is_permanent_and_opens_circuit(env):
    client, models = fake_gemini([APIError(401, "UNAUTHENTICATED API_KEY_SERVICE_BLOCKED")])
    with pytest.raises(LLMUnavailable):
        call(client, "unique-401")
    assert len(models.calls) == 1 and client.status()["circuit"] == "open" and not client.available()
    with pytest.raises(LLMUnavailable, match="circuit open"):
        call(client, "unique-401b")


def test_streamed_text_usage_is_not_double_counted(env):
    client, _ = fake_gemini(["Hello world, streamed."])
    r = client.generate_text(get_prompt("grounded_explanation"), "x", purpose="test")
    assert r.text == "Hello world, streamed." and r.usage.total_tokens == 145
