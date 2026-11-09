"""LIVE mode against a local OpenAI-compatible model server (a mock stands in for Qwen).

The mock implements the two endpoints the adapter uses: ``GET /v1/models`` and
streamed ``POST /v1/chat/completions``. It records requests so the tests can check
that nothing loads a model or changes its context size.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from app import config
from app.copilot import engine
from app.enterprise import data
from app.errors import LiveModeUnavailable, LocalModelBusy, PlatformError, RequestCancelled
from app.llm import local
from app.memory.store import get_store

from conftest import user

MODEL = "qwen2.5:7b-instruct"


class MockModel:
    def __init__(self) -> None:
        self.reply = '{"answer": "Revenue fell [S1].", "cited_source_ids": ["S1"]}'
        self.chunk_delay = 0.0
        self.status = 200
        self.requests: list[dict] = []
        self.paths: list[str] = []
        self.closed_early = threading.Event()


@pytest.fixture()
def mock_model():
    state = MockModel()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep test output quiet
            pass

        def do_GET(self):  # noqa: N802
            state.paths.append(self.path)
            body = json.dumps({"object": "list", "data": [{"id": MODEL, "object": "model"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):  # noqa: N802
            state.paths.append(self.path)
            state.requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            if state.status != 200:
                self.send_response(state.status)
                self.send_header("Content-Length", "5")
                self.end_headers()
                self.wfile.write(b"error")
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            pieces = [state.reply[i:i + 8] for i in range(0, len(state.reply), 8)]
            try:
                for piece in pieces:
                    chunk = {"choices": [{"delta": {"content": piece}, "finish_reason": None}]}
                    self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                    self.wfile.flush()
                    time.sleep(state.chunk_delay)
                final = {"choices": [{"delta": {}, "finish_reason": "stop"}],
                         "usage": {"prompt_tokens": 120, "completion_tokens": 20}}
                self.wfile.write(f"data: {json.dumps(final)}\n\ndata: [DONE]\n\n".encode())
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                state.closed_early.set()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    config.configure(llm_base_url=f"http://127.0.0.1:{server.server_port}/v1", llm_model=MODEL,
                     llm_timeout_s=5, llm_concurrency=1, llm_queue_size=4, llm_queue_wait_s=2)
    yield state
    server.shutdown()
    server.server_close()


@pytest.fixture()
def enterprise(platform):
    data.seed()
    return platform


def live_ask(question: str, **kw) -> dict:
    return engine.ask(question, user("val.viewer"), mode="live", **kw)


def test_not_configured_is_reported_and_falls_back(enterprise):
    assert local.status()["configured"] is False
    answer = live_ask("How did our sales do in the last 4 weeks?")
    assert answer["mode"] == "demo" and "FOODCARE_LLM_BASE_URL" in answer["notice"]


def test_live_answer_uses_the_local_model_with_bounded_settings(enterprise, mock_model):
    answer = live_ask("How did our sales do in the last 4 weeks?")
    assert answer["mode"] == "live" and answer["provenance"] == "live_ai"
    assert answer["answer"] == "Revenue fell [S1]."
    assert answer["usage"]["model"] == MODEL and answer["usage"]["output_tokens"] == 20
    body = mock_model.requests[0]
    assert body["model"] == MODEL and body["stream"] is True
    assert body["response_format"]["type"] == "json_schema"
    assert "num_ctx" not in json.dumps(body) and "options" not in body  # never changes the context size
    assert len(body["messages"][1]["content"]) <= config.get_settings().llm_max_prompt_chars
    run = get_store().agent_runs(conversation_id=answer["conversation_id"])[0]
    assert "local_llm.answer" in [t["tool"] for t in get_store().tool_calls_for(run["id"])]


def test_qwen_reasoning_block_and_code_fence_are_tolerated(enterprise, mock_model):
    mock_model.reply = ('<think>The user wants sales.</think>\n```json\n'
                        '{"answer": "Revenue fell [S1].", "cited_source_ids": ["S1"]}\n```')
    assert live_ask("How did our sales do in the last 4 weeks?")["mode"] == "live"


def test_uncited_or_invented_citations_are_rejected(enterprise, mock_model):
    mock_model.reply = '{"answer": "Revenue fell [S9].", "cited_source_ids": ["S9"]}'
    answer = live_ask("How did our sales do in the last 4 weeks?")
    assert answer["mode"] == "demo" and "cited sources that were not provided" in answer["notice"]
    mock_model.reply = '{"answer": "Revenue fell.", "cited_source_ids": []}'
    answer = live_ask("Which listings have allergen issues?")
    assert answer["mode"] == "demo" and "did not cite" in answer["notice"]


def test_identical_prompts_are_served_from_cache(enterprise, mock_model):
    first = live_ask("How did our sales do in the last 4 weeks?")
    second = live_ask("How did our sales do in the last 4 weeks?")  # new conversation, same prompt
    assert first["usage"]["cached"] is False and second["usage"]["cached"] is True
    assert len(mock_model.requests) == 1


def test_server_down_and_http_errors_fall_back_visibly(enterprise, mock_model):
    mock_model.status = 500
    answer = live_ask("How did our sales do in the last 4 weeks?")
    assert answer["mode"] == "demo" and "HTTP 500" in answer["notice"]
    config.configure(llm_base_url="http://127.0.0.1:9/v1")
    answer = live_ask("Which listings have allergen issues?")
    assert answer["mode"] == "demo" and "Could not reach the local model server" in answer["notice"]


def test_timeout_is_enforced(enterprise, mock_model):
    mock_model.chunk_delay = 0.3
    config.configure(llm_timeout_s=0.5)
    started = time.monotonic()
    answer = live_ask("How did our sales do in the last 4 weeks?")
    assert answer["mode"] == "demo" and "did not finish" in answer["notice"]
    assert time.monotonic() - started < 3


def _slow_call(results: list, question: str = "slow") -> threading.Thread:
    def run():
        try:
            results.append(local.get_llm().structured("sys", question, engine.LiveAnswer, request_id="REQ-SLOW-1"))
        except Exception as exc:  # noqa: BLE001 - the test inspects it
            results.append(exc)
    thread = threading.Thread(target=run)
    thread.start()
    return thread


def test_queue_limit_returns_busy_instead_of_piling_up(enterprise, mock_model):
    mock_model.chunk_delay = 0.2
    config.configure(llm_queue_size=0)
    results: list = []
    thread = _slow_call(results)
    for _ in range(50):
        if local.get_llm().status(probe=False)["in_flight"]:
            break
        time.sleep(0.02)
    with pytest.raises(LocalModelBusy):
        local.get_llm().structured("sys", "second", engine.LiveAnswer)
    thread.join()
    assert not isinstance(results[0], Exception)


def test_cancellation_stops_generation(enterprise, mock_model):
    mock_model.chunk_delay = 0.2
    results: list = []
    thread = _slow_call(results)
    for _ in range(50):
        if local.get_llm().status(probe=False)["in_flight"]:
            break
        time.sleep(0.02)
    assert local.cancel("REQ-SLOW-1")
    thread.join(timeout=5)
    assert isinstance(results[0], RequestCancelled)
    assert mock_model.closed_early.wait(3), "the stream to the model server was closed"


def test_copilot_cancel_is_owner_only(enterprise, mock_model):
    assert engine.cancel("REQ-NOT-MINE", "val.viewer") is False


def test_prompt_size_is_capped(enterprise, mock_model):
    config.configure(llm_max_prompt_chars=100)
    with pytest.raises(PlatformError, match="context limit"):
        local.get_llm().structured("sys", "x" * 101, engine.LiveAnswer)


def test_status_probe_lists_models_without_generating(enterprise, mock_model):
    info = local.status()
    assert info["reachable"] and info["model_listed"] and info["queue_depth"] == 0
    assert mock_model.paths == ["/v1/models"] and mock_model.requests == []


def test_one_shared_client_per_configuration(enterprise, mock_model):
    assert local.get_llm() is local.get_llm()


def test_no_external_or_second_inference_dependency():
    root = Path(__file__).resolve().parents[2]
    pyproject = (root / "pyproject.toml").read_text()
    for banned in ("anthropic", "openai", "ollama", "llama", "transformers", "vllm", "accelerate", "sentencepiece"):
        assert banned not in pyproject.lower()
    # PyTorch is approved for the potato vision classifier only: no LLM code may import it.
    app_dir = root / "backend" / "app"
    torch_users = sorted(str(p.relative_to(app_dir)) for p in app_dir.rglob("*.py")
                         if "import torch" in p.read_text() or "from torch" in p.read_text())
    assert torch_users == ["ml/classifier.py"]
    with pytest.raises(LiveModeUnavailable):
        config.configure(llm_base_url=None, llm_model=None)
        local.LocalLLM(config.get_settings())
