"""Security restrictions of the public demo.

These combine runtime guards (network + import blocking from conftest, dependency
injection of tool registries) with static AST checks as a second line of defence.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

from services.validation import (
    ValidationError,
    clean_text,
    ensure_not_sensitive,
    escape,
    validate_upload,
)
from tests.conftest import PROHIBITED_MODULES, NetworkBlocked
from workflows.params import validate_params

ROOT = Path(__file__).resolve().parent.parent
SOURCE_FILES = [p for p in ROOT.rglob("*.py") if "tests" not in p.parts and "venv" not in p.parts and ".venv" not in p.parts]
FORBIDDEN_CALLS = {"eval", "exec", "compile", "__import__"}
FORBIDDEN_MODULES = {"pickle", "marshal", "shelve", "subprocess", "dill", "cloudpickle", "yaml", "requests", "httpx",
                     "urllib.request", "http.client", "smtplib", "imaplib", "socket", "webbrowser", "ctypes"}
LLM_PACKAGES = {"openai", "anthropic", "google-generativeai", "google-genai", "langchain-openai", "langchain-anthropic",
                "langchain-google-genai", "cohere", "mistralai", "groq", "litellm", "together"}


def test_all_scenarios_run_with_network_and_llm_imports_blocked(engine):
    """Runtime proof: every workflow completes while sockets and LLM SDK imports would raise."""
    from services import scenario_loader as fixtures

    for spec in fixtures.list_scenarios():
        run = engine.start(spec.id)
        if run.status == "awaiting_approval":
            run = engine.resume(run.run_id, "approved")
        assert run.status == "completed", (spec.id, run.values.get("errors"))
    assert not [m for m in sys.modules if m.split(".")[0] in {"openai", "anthropic", "cohere", "mistralai", "litellm"}]


def test_network_guard_is_active():
    import socket

    with pytest.raises(NetworkBlocked):
        socket.create_connection(("example.com", 443))


def test_llm_import_guard_is_active():
    for name in ("openai", "anthropic"):
        with pytest.raises(ImportError, match="Prohibited"):
            __import__(name)
    assert "openai" in PROHIBITED_MODULES


def test_requirements_have_no_llm_clients():
    for req_file in ("requirements.txt", "requirements-dev.txt"):
        path = ROOT / req_file
        if not path.exists():
            continue
        names = {re.split(r"[<>=\[ ;]", line.strip(), maxsplit=1)[0].lower()
                 for line in path.read_text().splitlines() if line.strip() and not line.startswith("#")}
        assert not names & LLM_PACKAGES, names & LLM_PACKAGES


def test_source_has_no_dangerous_calls_or_imports():
    problems = []
    for path in SOURCE_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                problems.append(f"{path.name}: call {node.func.id}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"system", "popen", "spawnl"}:
                problems.append(f"{path.name}: os.{node.func.attr}")
            if isinstance(node, ast.Import):
                problems += [f"{path.name}: import {a.name}" for a in node.names if a.name in FORBIDDEN_MODULES or a.name.split(".")[0] in LLM_PACKAGES]
            if isinstance(node, ast.ImportFrom) and node.module and (node.module in FORBIDDEN_MODULES or node.module.split(".")[0] in {"openai", "anthropic"}):
                problems.append(f"{path.name}: from {node.module}")
    assert problems == []


def test_source_never_reads_api_keys_or_contains_secrets():
    secret_patterns = [re.compile(p) for p in (r"sk-[A-Za-z0-9]{20,}", r"AKIA[0-9A-Z]{16}", r"AIza[0-9A-Za-z_-]{30,}", r"xox[bp]-")]
    for path in [*SOURCE_FILES, *ROOT.rglob("*.json"), *ROOT.rglob("*.toml")]:
        text = path.read_text(encoding="utf-8")
        assert "os.environ" not in text and "getenv" not in text, path
        assert not any(p.search(text) for p in secret_patterns), path
    assert not (ROOT / ".streamlit" / "secrets.toml").exists()


def test_html_escaping():
    payload = '<script>alert("x")</script><img src=x onerror=alert(1)>'
    escaped = escape(payload)
    assert "<script>" not in escaped and "<img" not in escaped and "&lt;script&gt;" in escaped


def test_visitor_text_is_escaped_in_memory_garden():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    at.session_state["_museflow_ctx"].engine.stores.memory.add("Goals", "<b onclick=alert(1)>bold</b>")
    at.sidebar.radio[0].set_value("memory").run()
    rendered = "\n".join(m.value for m in at.markdown)
    assert "&lt;b onclick=alert(1)&gt;" in rendered and "<b onclick" not in rendered


@pytest.mark.parametrize("text", [
    "my password is hunter2", "email me at real.person@gmail.com", "call +1 415 555 0100 99",
    "card 4111 1111 1111 1111", "ssn 123-45-6789", "here is my api key",
])
def test_sensitive_data_is_rejected(text):
    with pytest.raises(ValidationError):
        ensure_not_sensitive(text)


def test_input_limits_and_control_chars():
    assert clean_text("hi\x00\x07 there", max_chars=20) == "hi there"
    with pytest.raises(ValidationError):
        clean_text("x" * 501, max_chars=500)
    with pytest.raises(ValidationError):
        clean_text("   ", max_chars=5)
    with pytest.raises(ValidationError):
        clean_text(123, max_chars=5)


def test_scenario_params_are_allowlisted():
    with pytest.raises(ValidationError, match="Unsupported parameter"):
        validate_params("research", {"topic": "ai_frameworks", "shell": "rm -rf /"})
    with pytest.raises(ValidationError):
        validate_params("research", {"topic": "../../etc/passwd"})
    with pytest.raises(ValidationError):
        validate_params("browser", {"task": "https://real-bank.com"})
    with pytest.raises(ValidationError):
        validate_params("document_analysis", {"document_id": "../../app.py"})
    with pytest.raises(ValidationError):
        validate_params("not_a_scenario", {})
    with pytest.raises(ValidationError):
        validate_params("schedule_meeting", {"start": "25:99"})
    with pytest.raises(ValidationError):
        validate_params("dream_team", {"goals": ["research", "launch_missiles"]})


def test_engine_rejects_bad_input(engine):
    with pytest.raises(ValidationError):
        engine.start()
    with pytest.raises(ValidationError):
        engine.start("personal_memory", {"text": "my password is 1234", "category": "Goals", "operation": "add"})
    assert len(engine.stores.memory) == 0


def test_upload_validation():
    assert validate_upload("notes.md", b"# Hi\nOwner: Me") .startswith("# Hi")
    for name, data in (("evil.exe", b"MZ"), ("big.txt", b"a" * 100_001), ("bad.txt", b"\xff\xfe\xfa")):
        with pytest.raises(ValidationError):
            validate_upload(name, data)


def test_injected_non_allowlisted_action_is_denied(engine):
    """Governance + supervisor stop an action whose tool is not on the allowlist."""
    from agents import email as email_mod
    from agents.base import AgentResult, agent_node
    import workflows.graph as graph_mod

    original = graph_mod.NODE_FUNCTIONS["email"]

    def rogue(state, ctx, tools):
        return AgentResult(output={"headline": "rogue"}, updates={"action": {"tool": "shell.exec", "agent": "email",
                           "summary": "pwn", "args": {"cmd": "cat /etc/passwd"}}})
    try:
        graph_mod.NODE_FUNCTIONS["email"] = agent_node("email", "email")(rogue)
        engine.rebuild_graph()
        run = engine.start("email_followup")
        assert run.status == "denied"
        assert "approval" not in [e["node"] for e in run.agent_events]
        assert "simulate_action" not in [e["node"] for e in run.agent_events]
    finally:
        graph_mod.NODE_FUNCTIONS["email"] = original
    assert email_mod.email is original
