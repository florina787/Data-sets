"""Shared fixtures. Every test runs with outbound networking and LLM SDK imports blocked."""
from __future__ import annotations

import importlib.abc
import socket
import sys
from datetime import date

import pytest

from services.demo_engine import DemoEngine

FIXED_TODAY = date(2026, 10, 7)  # a Wednesday, so calendar maths is deterministic
PROHIBITED_MODULES = (
    "openai", "anthropic", "google.generativeai", "google.genai", "langchain_openai", "langchain_anthropic",
    "langchain_google_genai", "cohere", "mistralai", "groq", "together", "litellm", "requests", "httpx",
)


class NetworkBlocked(RuntimeError):
    pass


class _ProhibitedImportFinder(importlib.abc.MetaPathFinder):
    """Fails any attempt to import an LLM SDK or HTTP client during tests."""

    def find_spec(self, fullname, path=None, target=None):  # noqa: D401
        if any(fullname == name or fullname.startswith(name + ".") for name in PROHIBITED_MODULES):
            raise ImportError(f"Prohibited import in public demo: {fullname}")
        return None


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def guard(*args, **kwargs):
        raise NetworkBlocked(f"Network access attempted: {args!r}")

    monkeypatch.setattr(socket.socket, "connect", guard)
    monkeypatch.setattr(socket.socket, "connect_ex", guard)
    monkeypatch.setattr(socket, "create_connection", guard)
    monkeypatch.setattr(socket, "getaddrinfo", guard)
    yield


@pytest.fixture(autouse=True)
def no_llm_sdks(monkeypatch):
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    finder = _ProhibitedImportFinder()
    sys.meta_path.insert(0, finder)
    yield
    sys.meta_path.remove(finder)


@pytest.fixture
def engine() -> DemoEngine:
    return DemoEngine("test-session", today=FIXED_TODAY)


def nodes(run) -> list[str]:
    return [e["node"] for e in run.agent_events if e["status"] == "completed"]
