"""Gemini adapter: credentials stay in a header, prompts are PII-masked, provider policy (public data only) is enforced by
the policy engine, and ungrounded model output falls back to the deterministic renderer. Uses a fake HTTP transport -
no network calls and no real key."""
import json

import httpx
import pytest

import agents.specialists  # noqa: F401  (registers narrative templates)
from harness.models import GeminiModel, MockModel


def _transport(seen: list, text: str = "Rewritten narrative.", status: int = 200):
    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if status != 200:
            return httpx.Response(status, json={"error": {"message": "echo of request: secret prompt"}})
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}}],
                                         "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 30}})
    return httpx.MockTransport(handler)


def test_key_in_header_only_and_prompt_masked():
    seen: list = []
    g = GeminiModel(api_key="test-key-not-real", model_id="gemini-test", transport=_transport(seen))
    gen = g.chat("system", [{"role": "user", "content": "Email jane.doe@example.com about fees"}])
    req = seen[0]
    assert req.headers["x-goog-api-key"] == "test-key-not-real" and "test-key-not-real" not in str(req.url)
    body = json.loads(req.content)
    assert "jane.doe@example.com" not in json.dumps(body) and body["generationConfig"]["temperature"] == 0
    assert gen.text == "Rewritten narrative." and gen.tokens_in == 120 and gen.model == "gemini:gemini-test"


def test_errors_do_not_echo_response_bodies():
    g = GeminiModel(api_key="k", model_id="gemini-test", transport=_transport([], status=403))
    with pytest.raises(RuntimeError) as e:
        g.chat("s", [{"role": "user", "content": "hi"}])
    assert "403" in str(e.value) and "secret prompt" not in str(e.value)


def test_rejects_unsafe_model_ids():
    with pytest.raises(ValueError):
        GeminiModel(api_key="k", model_id="../../v1/files?x=")


def _budgeted(ctx):
    import time

    from harness.context import Budget
    ctx.budget = Budget(8, 20_000, 0.5, time.monotonic() + 30)
    return ctx


def test_policy_allows_gemini_for_public_data_only(ctx_for):
    from harness.runtime import get_harness
    seen: list = []
    g = GeminiModel(api_key="k", model_id="gemini-test", transport=_transport(seen, "Rewritten product summary."))
    ctx = _budgeted(ctx_for("u-external", model=g))
    facts = {"n": 3, "by_strategy": [], "window": 12}
    pub = get_harness().narrate(ctx, "product", facts, classification="public")
    assert pub.model == "gemini:gemini-test" and len(seen) == 1
    conf = get_harness().narrate(ctx, "product", facts, classification="confidential")
    assert conf.model == MockModel.name and len(seen) == 1  # denied by ABAC-MODEL-RESIDENCY: no request was sent
    assert any(p["action"] == "model:invoke" and not p["allowed"] for p in ctx.policy_log)


def test_hallucinated_numbers_fall_back_to_deterministic_text(ctx_for):
    from harness.runtime import get_harness
    g = GeminiModel(api_key="k", model_id="gemini-test", transport=_transport([], "Fees fell 99.9% across 777 funds."))
    gen = get_harness().narrate(_budgeted(ctx_for("u-external", model=g)), "product", {"n": 3, "by_strategy": [], "window": 12}, classification="public")
    assert gen.model == MockModel.name and "777" not in gen.text
