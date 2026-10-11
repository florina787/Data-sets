"""Visitor isolation: stores, checkpoints, runs and audit logs never cross sessions."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from services.demo_engine import DemoEngine
from tests.conftest import FIXED_TODAY

ROOT = Path(__file__).resolve().parent.parent


def test_two_sessions_do_not_share_state():
    alice, bob = DemoEngine("alice", today=FIXED_TODAY), DemoEngine("bob", today=FIXED_TODAY)
    alice.start("personal_memory", {"text": "I love violet ink.", "category": "Preferences", "operation": "add"})
    run = alice.start("email_followup")
    alice.resume(run.run_id, "approved")
    assert len(alice.stores.memory) == 1 and len(bob.stores.memory) == 0
    assert alice.stores.outbox and not bob.stores.outbox
    assert len(alice.audit) > 0 and len(bob.audit) == 0
    recall = bob.start("memory_recall")
    assert recall.outputs["memory"]["memories"] == []


def test_checkpoints_are_per_session():
    alice, bob = DemoEngine("alice", today=FIXED_TODAY), DemoEngine("bob", today=FIXED_TODAY)
    run = alice.start("email_followup")
    assert alice.checkpoints.saver is not bob.checkpoints.saver
    assert all(t.startswith("alice:") for t in alice.checkpoints.threads())
    assert not bob.checkpoints.owns(run.thread_id)
    # Bob cannot see or resume Alice's checkpointed thread.
    assert bob.graph.get_state({"configurable": {"thread_id": run.thread_id}}).values == {}
    with pytest.raises(KeyError):
        bob.resume(run.run_id, "approved")


def test_no_shared_streamlit_caches_for_mutable_state():
    """Visitor objects must never live in st.cache_resource / st.cache_data."""
    offenders = []
    for path in ROOT.rglob("*.py"):
        if "tests" in path.parts or "venv" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Attribute) and node.attr in {"cache_resource", "cache_data", "experimental_singleton"}:
                offenders.append(str(path))
    assert offenders == []


def test_streamlit_sessions_are_isolated():
    from streamlit.testing.v1 import AppTest

    first = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    first.session_state["_museflow_ctx"].engine.stores.memory.add("Goals", "Plant a lavender field.")
    first.sidebar.radio[0].set_value("memory").run()
    second = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    second.sidebar.radio[0].set_value("memory").run()
    assert len(second.session_state["_museflow_ctx"].engine.stores.memory) == 0
    assert first.session_state["_museflow_ctx"].session_id != second.session_state["_museflow_ctx"].session_id
    assert any("lavender" in m.value for m in first.markdown)
    assert not any("lavender" in m.value for m in second.markdown)
