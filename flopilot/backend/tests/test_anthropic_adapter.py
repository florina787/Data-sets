"""Offline check of the Anthropic adapter: request shape and response parsing via a mock transport."""
from __future__ import annotations

import json

import pytest

anthropic = pytest.importorskip("anthropic")
httpx2 = pytest.importorskip("httpx2")

from app.llm.providers import AnthropicProvider  # noqa: E402


def test_request_shape_and_tool_use_parsing():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [{"type": "text", "text": "Let me calculate."},
                        {"type": "tool_use", "id": "toolu_1", "name": "calculate_aggregate",
                         "input": {"sheet": "Sales", "measure": "Net Revenue", "function": "sum"}}],
            "stop_reason": "tool_use", "stop_sequence": None, "usage": {"input_tokens": 120, "output_tokens": 30},
        })

    client = anthropic.Anthropic(api_key="test-key", base_url="https://api.example.test", max_retries=0,
                                 http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler)))
    provider = AnthropicProvider(client=client)
    tools = [{"name": "calculate_aggregate", "description": "sum", "input_schema": {"type": "object", "properties": {}}}]
    resp = provider.complete("system prompt", [{"role": "user", "content": "How much?"}], tools)

    body = seen["body"]
    assert seen["url"].endswith("/v1/messages?beta=true") or seen["url"].endswith("/v1/messages")
    assert body["model"] == "claude-opus-5-5" and body["fallbacks"] == "default"
    assert body["output_config"] == {"effort": "medium"} and body["tools"][0]["name"] == "calculate_aggregate"
    assert "server-side-fallback-2026-07-01" in seen["headers"].get("anthropic-beta", "")
    assert seen["headers"]["x-api-key"] == "test-key"
    assert resp.stop_reason == "tool_use" and resp.input_tokens == 120 and resp.output_tokens == 30
    assert resp.tool_uses[0].name == "calculate_aggregate" and resp.tool_uses[0].input["measure"] == "Net Revenue"
    assert resp.text == "Let me calculate."
