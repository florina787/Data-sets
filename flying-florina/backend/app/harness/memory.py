"""Persistent conversational memory (SQLite): messages, structured summaries, slot memory, retrieval, deletion.

Survives restarts because it lives in the same SQLite file as everything else. The language model never receives the whole
history: `context_for_model` returns a bounded window (recent turns + the session summary + a few retrieved older turns) under a
character budget. Only text is stored; uploaded footage and raw tool outputs are not.
"""

from __future__ import annotations

import re
from typing import Any

from app.core import db
from app.core.util import now_iso

CONTEXT_BUDGET_CHARS = 2400
RECENT_TURNS = 6


def add(session_id: str, user_id: str, role: str, content: str, run_id: str | None = None, intent: str | None = None,
        slots: dict[str, Any] | None = None) -> None:
    content = content.strip()[:4000]
    if not content:
        return
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO messages (session_id, user_id, role, content, run_id, intent, slots_json, ts) VALUES (?,?,?,?,?,?,?,?)",
                     (session_id, user_id, role, content, run_id, intent, db.jdump(slots or {}), now_iso()))
        conn.execute("INSERT INTO messages_fts (session_id, user_id, content) VALUES (?,?,?)", (session_id, user_id, content))
        _summarise(conn, session_id, user_id)


def _summarise(conn: Any, session_id: str, user_id: str) -> None:
    """Deterministic structured summary: topics asked, last slots, turn count (no model needed, so it is always available)."""
    rows = db.rows(conn, "SELECT role, content, intent, slots_json FROM messages WHERE session_id = ? ORDER BY id", (session_id,))
    users = [r for r in rows if r["role"] == "user"]
    intents = [r["intent"] for r in users if r["intent"]]
    slots: dict[str, Any] = {}
    for r in users:
        slots.update({k: v for k, v in db.jload(r["slots_json"], {}).items() if v not in (None, "", [])})
    topics = list(dict.fromkeys(intents))[-6:]
    summary = (f"{len(users)} question(s). Topics: {', '.join(t.replace('_', ' ') for t in topics) or 'none yet'}. "
               f"Last question: \"{users[-1]['content'][:140]}\"." if users else "")
    conn.execute("INSERT INTO conversation_summaries VALUES (?,?,?,?,?,?) ON CONFLICT(session_id) DO UPDATE SET summary=excluded.summary, "
                 "slots_json=excluded.slots_json, turns=excluded.turns, updated=excluded.updated",
                 (session_id, user_id, summary, db.jdump(slots), len(rows), now_iso()))


def history(session_id: str, user_id: str, limit: int = 200) -> list[dict[str, Any]]:
    return db.query("SELECT id, role, content, run_id, intent, slots_json, ts FROM messages WHERE session_id = ? AND user_id = ? ORDER BY id LIMIT ?",
                    (session_id, user_id, limit))


def conversations(user_id: str) -> list[dict[str, Any]]:
    return db.query("SELECT s.id, s.title, s.created, s.updated, c.summary, c.turns FROM sessions s LEFT JOIN conversation_summaries c ON c.session_id = s.id "
                    "WHERE s.user_id = ? ORDER BY s.updated DESC LIMIT 100", (user_id,))


def delete(session_id: str, user_id: str) -> bool:
    with db.session(write=True) as conn:
        own = conn.execute("SELECT 1 FROM sessions WHERE id = ? AND user_id = ?", (session_id, user_id)).fetchone()
        if not own:
            return False
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM messages_fts WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM conversation_summaries WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM conversation_context WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        # workflow runs stay: they are part of the audit trail (their queries remain visible to auditors)
    return True


_FTS_WORD = re.compile(r"[A-Za-z0-9]{3,}")


def recall(user_id: str, query: str, session_id: str | None = None, limit: int = 5) -> dict[str, Any]:
    """The user's own earlier turns, newest investigations first, plus FTS matches for the query. Never another user's data."""
    words = _FTS_WORD.findall(query)[:8]
    hits: list[dict[str, Any]] = []
    if words:
        expr = " OR ".join(f'"{w}"' for w in words)
        hits = db.query("SELECT f.session_id, f.content FROM messages_fts f WHERE messages_fts MATCH ? AND f.user_id = ? LIMIT ?", (expr, user_id, limit * 3))
    runs = db.query("SELECT r.id, r.session_id, r.query, r.workflow, r.status, r.created FROM workflow_runs r WHERE r.user_id = ? AND r.workflow NOT IN "
                    "('greeting','clarify','unsupported','general_knowledge','policy_refusal','memory_recall','agent_trace') ORDER BY r.created DESC LIMIT ?",
                    (user_id, limit + 1))
    answers = []
    for r in runs:
        st = db.query_one("SELECT content FROM messages WHERE run_id = ? AND role = 'assistant' ORDER BY id DESC LIMIT 1", (r["id"],))
        answers.append({**r, "answer_excerpt": (st["content"][:400] if st else None)})
    summary = db.query_one("SELECT summary, slots_json, turns FROM conversation_summaries WHERE session_id = ? AND user_id = ?", (session_id, user_id)) if session_id else None
    return {"previous_runs": answers, "matches": hits[:limit], "session_summary": summary}


def context_for_model(session_id: str, user_id: str, query: str) -> str:
    """Bounded context for Qwen: session summary + recent turns + up to 2 retrieved older turns, capped at CONTEXT_BUDGET_CHARS."""
    s = db.query_one("SELECT summary FROM conversation_summaries WHERE session_id = ?", (session_id,))
    recent = db.query("SELECT role, content FROM messages WHERE session_id = ? AND user_id = ? ORDER BY id DESC LIMIT ?", (session_id, user_id, RECENT_TURNS))
    parts = [f"SESSION SUMMARY: {s['summary']}"] if s and s["summary"] else []
    parts += [f"{r['role'].upper()}: {r['content'][:300]}" for r in reversed(recent)]
    rec = recall(user_id, query, session_id, 2)["matches"]
    parts += [f"EARLIER: {m['content'][:200]}" for m in rec]
    out, used = [], 0
    for p in parts:
        if used + len(p) > CONTEXT_BUDGET_CHARS:
            break
        out.append(p)
        used += len(p)
    return "\n".join(out)


def preferences(user_id: str) -> dict[str, str]:
    return {r["key"]: r["value"] for r in db.query("SELECT key, value FROM user_preferences WHERE user_id = ?", (user_id,))}


def set_preference(user_id: str, key: str, value: str) -> None:
    db.execute("INSERT INTO user_preferences VALUES (?,?,?,?) ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value, updated=excluded.updated",
               (user_id, key[:40], value[:200], now_iso()))
