"""Inference adapter tests: HF router provider (fake router), llama.cpp body, safe failure without credentials."""
import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.config import get_settings
from app.llm import qwen


class _FakeRouter(BaseHTTPRequestHandler):
    seen: list = []

    def log_message(self, *a):  # silence
        pass

    def do_GET(self):  # /v1/models and /api/whoami-v2
        if self.path.startswith("/api/whoami"):
            ok = self.headers.get("Authorization") == "Bearer hf_test_token"
            self.send_response(200 if ok else 401); self.end_headers(); self.wfile.write(b'{"name":"tester"}' if ok else b"{}"); return
        body = json.dumps({"data": [{"id": "Qwen/Qwen3.5-9B"}]}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)

    def do_POST(self):
        n = int(self.headers["Content-Length"])
        req = json.loads(self.rfile.read(n))
        _FakeRouter.seen.append({"auth": self.headers.get("Authorization"), "bill": self.headers.get("X-HF-Bill-To"), "body": req})
        if self.headers.get("Authorization") != "Bearer hf_test_token":
            self.send_response(401); self.end_headers(); self.wfile.write(b'{"error":"unauthorized"}'); return
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
        for chunk in [{"choices": [{"delta": {"reasoning": "ignored"}}]}, {"choices": [{"delta": {"content": "Hello "}}]},
                      {"choices": [{"delta": {"content": "from the router"}}]}, {"choices": [], "usage": {"prompt_tokens": 12, "completion_tokens": 4}}]:
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")


@pytest.fixture
def fake_router():
    srv = HTTPServer(("127.0.0.1", 0), _FakeRouter)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def _client(monkeypatch, **env):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    get_settings.cache_clear()
    qwen.reset_llm()
    return qwen.QwenClient()


def test_hf_router_streams_with_server_side_token(monkeypatch, fake_router):
    c = _client(monkeypatch, LLM_PROVIDER="hf", LLM_MODEL="Qwen/Qwen3.5-9B", HF_TOKEN="hf_test_token", HF_ROUTER_URL=fake_router, HF_HUB_URL=fake_router, HF_BILL_TO="career-org")
    try:
        r = asyncio.run(c.complete([{"role": "system", "content": "s"}, {"role": "user", "content": "hi"}], purpose="test"))
        assert r.text == "Hello from the router" and r.completion_tokens == 4
        seen = _FakeRouter.seen[-1]
        assert seen["auth"] == "Bearer hf_test_token" and seen["bill"] == "career-org"
        assert seen["body"]["model"] == "Qwen/Qwen3.5-9B" and "chat_template_kwargs" not in seen["body"]
        h = asyncio.run(c.health())
        assert h["ok"] and h["model_loaded"]
        bad = _client(monkeypatch, HF_TOKEN="hf_wrong")
        assert asyncio.run(bad.health())["ok"] is False
    finally:
        get_settings.cache_clear(); qwen.reset_llm()


def test_hf_provider_without_token_fails_safely(monkeypatch, fake_router):
    c = _client(monkeypatch, LLM_PROVIDER="hf", LLM_MODEL="Qwen/Qwen3.5-9B", HF_TOKEN="", HF_ROUTER_URL=fake_router)
    try:
        with pytest.raises(qwen.LLMUnavailable):
            asyncio.run(c.complete([{"role": "user", "content": "hi"}], purpose="test"))
        assert asyncio.run(c.health())["ok"] is False
    finally:
        get_settings.cache_clear(); qwen.reset_llm()


def test_hf_provider_refuses_non_qwen(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "hf"); monkeypatch.setenv("LLM_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError):
            qwen.QwenClient()
    finally:
        get_settings.cache_clear(); qwen.reset_llm()
