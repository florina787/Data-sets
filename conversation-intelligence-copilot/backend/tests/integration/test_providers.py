"""Groq (OpenAI-compatible HTTP) and local llama.cpp providers, without network or model files."""

import json

import httpx
import pytest

from app.config import get_settings
from app.llm.gemini_client import LLMUnavailable
from app.llm.groq_client import GroqClient
from app.llm.local_client import LocalLlamaClient
from app.llm.structured_output import IntentOutput
from app.prompts.registry import get_prompt

GOOD = {"category": "leadership_priorities"}


def groq(handler, **overrides):
    s = get_settings().model_copy(update={"groq_api_key": "test", "gemini_max_retries": 2, **overrides})
    http = httpx.Client(base_url="https://groq.test/openai/v1", transport=httpx.MockTransport(handler))
    return GroqClient(s, http_client=http, sleep=lambda _: None)


def ok(content, usage=(100, 20)):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}],
                                     "usage": {"prompt_tokens": usage[0], "completion_tokens": usage[1], "total_tokens": sum(usage)}})


def call(client, user):
    return client.generate_json(get_prompt("intent_understanding"), user, IntentOutput, purpose="test")


def test_groq_json_mode_schema_and_usage(env):
    seen = {}

    def handler(req):
        seen.update(json.loads(req.content))
        return ok(json.dumps(GOOD))

    r = call(groq(handler), "groq-1")
    assert r.parsed.category == "leadership_priorities" and r.usage.total_tokens == 120
    assert seen["response_format"] == {"type": "json_object"} and "JSON Schema" in seen["messages"][0]["content"]
    assert seen["model"] == get_settings().groq_model


def test_groq_429_retry_after_then_success(env):
    replies = iter([httpx.Response(429, headers={"retry-after": "3"}, json={"error": {"message": "rate limited"}}), ok(json.dumps(GOOD))])
    slept = []
    c = groq(lambda req: next(replies))
    c._sleep = slept.append
    r = call(c, "groq-429")
    assert r.retries == 1 and slept == [3.0]


def test_groq_auth_error_opens_circuit(env):
    c = groq(lambda req: httpx.Response(401, json={"error": {"message": "Invalid API Key"}}))
    with pytest.raises(LLMUnavailable, match="Groq call failed"):
        call(c, "groq-401")
    assert c.status()["circuit"] == "open" and c.status()["provider"] == "groq"


class FakeLlama:
    def __init__(self, content):
        self.content, self.kwargs = content, None

    def create_chat_completion(self, **kw):
        self.kwargs = kw
        return {"choices": [{"message": {"content": self.content}}], "usage": {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60}}


def test_local_model_uses_schema_grammar_and_costs_nothing(env):
    fake = FakeLlama(json.dumps(GOOD))
    c = LocalLlamaClient(get_settings(), llama=fake)
    r = call(c, "local-1")
    assert r.parsed.category == "leadership_priorities" and r.usage.total_tokens == 60
    assert fake.kwargs["response_format"]["type"] == "json_object" and "properties" in fake.kwargs["response_format"]["schema"]
    assert c.costs == (0.0, 0.0) and c.status()["provider"] == "local"


def test_local_model_missing_file_is_reported(env, tmp_path):
    s = get_settings().model_copy(update={"local_model_dir": tmp_path})
    with pytest.raises(FileNotFoundError, match="llm-download"):
        LocalLlamaClient(s)


def test_confidence_router_calls_model_only_when_deterministic_stages_cannot_route(env):
    from app.agents.intent_agent import resolve_intent
    from app.llm import gemini_client

    fake = FakeLlama(json.dumps({"category": "root_cause"}))
    gemini_client.set_llm(LocalLlamaClient(get_settings(), llama=fake))
    intent, source, meta = resolve_intent("Which recurring customer concerns should contact-centre leadership review first?", None, [], "t")
    assert intent.category == "leadership_priorities" and source == "rules" and fake.kwargs is None  # high-precision rule: no model call
    intent, source, meta = resolve_intent("Which agents should be fired?", None, [], "t")
    assert intent.category == "unsupported" and meta["routing"]["method"] == "policy" and fake.kwargs is None  # policy refusal stands
    intent, source, meta = resolve_intent("Something feels off with our customers lately", None, [], "t")
    assert source == "llm" and intent.category == "root_cause" and fake.kwargs is not None  # nothing deterministic matched
    assert fake.kwargs["response_format"]["schema"]["properties"]["category"]["enum"][-1] == "clarify"  # constrained, closed set
    fake.kwargs = None
    _, _, meta = resolve_intent("Something feels off with our customers lately", None, [], "t", allow_llm=False)
    assert meta["routing"]["method"] == "clarify" and fake.kwargs is None  # Zero-LLM path never calls the model


def test_model_choice_needing_a_missing_entity_is_rejected(env):
    from app.agents.intent_agent import resolve_intent
    from app.llm import gemini_client

    fake = FakeLlama(json.dumps({"category": "agent_profile"}))
    gemini_client.set_llm(LocalLlamaClient(get_settings(), llama=fake))
    intent, _, meta = resolve_intent("Anything odd in the conversations recently", None, [], "t")
    assert meta["routing"]["method"] == "clarify" and "needs an entity" in meta["routing"]["llm"]["rejected"]
