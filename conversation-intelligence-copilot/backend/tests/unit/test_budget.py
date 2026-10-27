"""Explanation time budget: calls that cannot finish are not started, overruns are stopped, and neither opens the circuit."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.llm.budget import DeadlineExceeded, model_budget, remaining
from app.llm.gemini_client import LLMUnavailable
from app.llm.local_client import LocalLlamaClient
from app.prompts.registry import get_prompt


class SlowLlama:
    """Streams `tokens` one-token chunks; counts how often it was asked to generate."""

    def __init__(self, tokens: int = 50):
        self.calls, self.tokens = 0, tokens

    def tokenize(self, text: bytes, add_bos: bool = False):
        return list(range(len(text.split())))

    def create_chat_completion(self, stream: bool = False, **kw):
        self.calls += 1

        def gen():
            for _ in range(self.tokens):
                yield {"choices": [{"delta": {"content": "x"}}]}
        return gen()


def _client(tmp_path, llama) -> LocalLlamaClient:
    s = Settings(llm_cache_path=tmp_path / "c.sqlite")
    return LocalLlamaClient(s, llama=llama)


def test_budget_context_sets_and_clears_the_deadline():
    assert remaining() is None
    with model_budget(5):
        assert 4 < remaining() <= 5
    assert remaining() is None
    with model_budget(0):  # 0 disables the budget
        assert remaining() is None


def test_call_predicted_not_to_fit_is_never_started(tmp_path):
    llama = SlowLlama()
    c = _client(tmp_path, llama)
    c.prompt_tokens_per_s, c.gen_tokens_per_s = 60.0, 12.0  # measured CPU speeds: a ~120-token answer alone needs ~10 s
    prompt = get_prompt("grounded_explanation")
    with model_budget(5), pytest.raises(DeadlineExceeded, match="needs"):
        c._invoke(prompt, "short question", None, True)
    assert llama.calls == 0


def test_overrun_stops_generation_without_opening_the_circuit(tmp_path, monkeypatch):
    llama = SlowLlama(tokens=100)
    c = _client(tmp_path, llama)
    c.prompt_tokens_per_s, c.gen_tokens_per_s = 1e9, 1e9  # predicted to fit
    import app.llm.local_client as lc

    left = iter([10.0] + [1.0] * 5 + [-0.1] * 200)
    monkeypatch.setattr(lc, "remaining", lambda: next(left))
    prompt = get_prompt("grounded_explanation")
    with pytest.raises(LLMUnavailable, match="time budget"):
        c._call(prompt, "q", None, True)
    assert llama.calls == 1 and c.breaker.allow()
