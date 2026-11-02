"""Persistent memory: conversations survive restarts, are private, searchable and bounded."""

from __future__ import annotations

import sqlite3

import pytest

from app import config
from app.copilot import engine
from app.enterprise import data
from app.errors import NotFound
from app.memory import maintenance
from app.memory.store import SqliteMemoryStore, fts_query, get_store

from conftest import user


@pytest.fixture()
def enterprise(platform):
    data.seed()
    return platform


def test_conversation_persists_across_a_new_store_instance(enterprise):
    first = engine.ask("How did our sales do in the last 4 weeks?", user("val.viewer"))
    reopened = SqliteMemoryStore()  # a fresh process would open the same file
    messages = reopened.messages(first["conversation_id"], "val.viewer")
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert messages[1]["meta"]["sources"], "citations are kept with the stored answer"


def test_conversations_are_private(enterprise):
    first = engine.ask("Give me a briefing", user("val.viewer"))
    with pytest.raises(NotFound):
        engine.history(first["conversation_id"], "maya.marketing")
    with pytest.raises(NotFound):
        engine.ask("And Quebec?", user("maya.marketing"), first["conversation_id"])
    assert get_store().list_conversations("maya.marketing") == []
    assert get_store().search("maya.marketing", "briefing") == []


def test_follow_up_reuses_previous_topic(enterprise):
    first = engine.ask("Top selling products in Ontario last 8 weeks", user("val.viewer"))
    follow = engine.ask("What about Quebec?", user("val.viewer"), first["conversation_id"])
    assert follow["follow_up"] and follow["intents"] == ["sales"]
    assert follow["entities"]["provinces"] == ["QC"] and follow["entities"]["weeks"] == 8
    unrelated = engine.ask("Which listings have allergen issues?", user("val.viewer"), first["conversation_id"])
    assert not unrelated["follow_up"] and unrelated["intents"] == ["compliance"]


def test_search_finds_earlier_questions_and_is_injection_safe(enterprise):
    engine.ask("Which products are running low in Vancouver?", user("val.viewer"))
    engine.ask("How did past promotions perform?", user("val.viewer"))
    hits = get_store().search("val.viewer", "vancouver")
    assert len(hits) == 1 and "Vancouver" in hits[0]["snippet"]
    assert fts_query('vancouver" OR content:*') == '"vancouver" "or" "content"'
    assert get_store().search("val.viewer", '") OR (" NEAR') == []


def test_delete_removes_messages_and_search_entries(enterprise):
    first = engine.ask("Which products are running low in Vancouver?", user("val.viewer"))
    assert get_store().delete_conversation(first["conversation_id"], "val.viewer")
    assert get_store().search("val.viewer", "vancouver") == []
    assert not get_store().delete_conversation(first["conversation_id"], "val.viewer")


def test_context_window_is_bounded(enterprise):
    config.configure(memory_summary_after=6, memory_context_turns=2)
    conv = None
    for question in ["Give me a briefing", "How did past promotions perform?", "Which listings have allergen issues?",
                     "Which products are running low in Vancouver?", "How did our sales do in the last 4 weeks?"]:
        conv = engine.ask(question, user("val.viewer"), conv and conv["conversation_id"])
    window = get_store().context_window(conv["conversation_id"], "val.viewer", 2)
    assert len(window["recent"]) == 4  # two exchanges, never the whole history
    assert window["summary"].startswith("Earlier questions in this conversation: Give me a briefing")


def test_agent_and_tool_runs_are_recorded_with_timings(enterprise):
    answer = engine.ask("Is there enough apple stock for the Ontario weekend campaign?", user("val.viewer"))
    runs = get_store().agent_runs(conversation_id=answer["conversation_id"])
    assert runs[0]["agent"] == "copilot.supervisor" and runs[0]["duration_ms"] >= 0
    calls = get_store().tool_calls_for(runs[0]["id"])
    assert [c["tool"] for c in calls] == ["campaign_stock_risk"]
    assert calls[0]["status"] == "ok" and calls[0]["duration_ms"] is not None


def test_retention_deletes_old_conversations(enterprise):
    first = engine.ask("Give me a briefing", user("val.viewer"))
    conn = get_store().connect()
    conn.execute("UPDATE conversations SET updated_at = '2000-01-01T00:00:00.000+00:00'")
    conn.close()
    assert get_store().apply_retention(days=0) == 0  # 0 keeps everything
    assert get_store().apply_retention(days=30) >= 1
    assert get_store().conversation(first["conversation_id"], "val.viewer") is None


def test_migrations_are_idempotent_and_checksummed(enterprise):
    store = get_store()
    store.init()  # the first call applies any pending migrations
    assert store.init() == []
    conn = store.connect()
    versions = [r[0] for r in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]
    conn.execute("UPDATE schema_migrations SET checksum = 'tampered' WHERE version = 1")
    conn.close()
    assert versions == [1, 2, 3, 4]
    with pytest.raises(RuntimeError, match="changed after it was applied"):
        store.init()


def test_backup_and_recovery_from_corruption(enterprise):
    first = engine.ask("Give me a briefing", user("val.viewer"))
    result = maintenance.backup()
    assert result["bytes"] > 0
    path = get_store().path
    for suffix in ("-wal", "-shm"):
        (path.parent / (path.name + suffix)).unlink(missing_ok=True)
    path.write_bytes(b"this is not a sqlite database" * 100)
    with pytest.raises(sqlite3.DatabaseError):
        sqlite3.connect(path).execute("SELECT * FROM conversations").fetchall()
    report = maintenance.startup()
    assert report["recovered"] and report["restored_from"]
    assert get_store().conversation(first["conversation_id"], "val.viewer") is not None


def test_memory_survives_demo_reset(enterprise):
    from app.services import system

    first = engine.ask("Give me a briefing", user("val.viewer"))
    system.reset_demo("test")
    assert get_store().conversation(first["conversation_id"], "val.viewer") is not None
