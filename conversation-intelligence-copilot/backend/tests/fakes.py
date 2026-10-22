"""Scripted stand-ins for the google-genai SDK and the LLM client."""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.config import get_settings
from app.llm.gemini_client import GeminiClient


class APIError(Exception):
    def __init__(self, code: int, message: str, details=None):
        super().__init__(f"{code} {message}")
        self.code = code
        self.details = details or {}


class FakeModels:
    def __init__(self, script: list):
        self.script = list(script)
        self.calls = []

    def _next(self, contents):
        self.calls.append(contents)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        if callable(item):
            item = item(contents)
        return item

    def generate_content(self, model, contents, config):
        text = self._next(contents)
        return SimpleNamespace(text=text, usage_metadata={"prompt_token_count": 120, "candidates_token_count": 30, "total_token_count": 150})

    def generate_content_stream(self, model, contents, config):
        text = self._next(contents)
        half = len(text) // 2
        return [SimpleNamespace(text=text[:half], usage_metadata={"prompt_token_count": 120, "candidates_token_count": 10, "total_token_count": 130}),
                SimpleNamespace(text=text[half:], usage_metadata={"prompt_token_count": 120, "candidates_token_count": 25, "total_token_count": 145})]


def fake_gemini(script: list, **overrides) -> tuple[GeminiClient, FakeModels]:
    s = get_settings().model_copy(update={"gemini_api_key": "test", "gemini_max_retries": 2, "gemini_requests_per_minute": 1000, **overrides})
    models = FakeModels(script)
    client = GeminiClient(s, sdk_client=SimpleNamespace(models=models), sleep=lambda _: None)
    return client, models


def router(intent: dict | None = None, explanation: dict | None = None):
    """A content-aware fake: answers intent prompts and explanation prompts differently."""

    def respond(contents: str) -> str:
        if "TAXONOMY" in contents and "SESSION_CONTEXT" in contents:
            return json.dumps(intent)
        if "VERIFIED_FACTS" in contents:
            return json.dumps(explanation)
        raise AssertionError("unexpected prompt")

    return respond
