"""Versioned migrations for the memory and execution-history database.

Only tables that did not exist before are created here; the platform database
(``platform.db``) keeps its own schema. Each migration runs once, inside a
transaction, and is recorded with a checksum so an edited migration is detected
instead of silently diverging.
"""

from __future__ import annotations

import sqlite3

from app.db import now_iso, sha256_text

MIGRATIONS: list[tuple[int, str, str]] = [
    (1, "conversations", """
CREATE TABLE conversations (
    id TEXT PRIMARY KEY, username TEXT NOT NULL, title TEXT NOT NULL,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, message_count INTEGER NOT NULL DEFAULT 0,
    context_json TEXT NOT NULL DEFAULT '{}', summary TEXT, summary_upto INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX conversations_user ON conversations (username, updated_at);
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL
        REFERENCES conversations (id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')), content TEXT NOT NULL,
    meta_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
);
CREATE INDEX messages_conversation ON messages (conversation_id, id);
CREATE VIRTUAL TABLE messages_fts USING fts5 (
    content, content = 'messages', content_rowid = 'id', tokenize = 'unicode61'
);
CREATE TRIGGER messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts (rowid, content) VALUES (new.id, new.content);
END;
CREATE TRIGGER messages_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts (messages_fts, rowid, content) VALUES ('delete', old.id, old.content);
END;
CREATE TRIGGER messages_au AFTER UPDATE OF content ON messages BEGIN
    INSERT INTO messages_fts (messages_fts, rowid, content) VALUES ('delete', old.id, old.content);
    INSERT INTO messages_fts (rowid, content) VALUES (new.id, new.content);
END;
"""),
    (2, "execution_history", """
CREATE TABLE agent_runs (
    id TEXT PRIMARY KEY, agent TEXT NOT NULL, parent_id TEXT, conversation_id TEXT, run_id TEXT,
    status TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT, duration_ms REAL,
    input_summary TEXT, output_summary TEXT, error TEXT, detail_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX agent_runs_started ON agent_runs (started_at);
CREATE INDEX agent_runs_conversation ON agent_runs (conversation_id);
CREATE TABLE tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT, agent_run_id TEXT NOT NULL
        REFERENCES agent_runs (id) ON DELETE CASCADE,
    tool TEXT NOT NULL, args_json TEXT NOT NULL DEFAULT '{}', status TEXT NOT NULL,
    started_at TEXT NOT NULL, duration_ms REAL, result_summary TEXT, error TEXT
);
CREATE INDEX tool_calls_run ON tool_calls (agent_run_id);
CREATE INDEX tool_calls_tool ON tool_calls (tool, started_at);
CREATE TABLE human_approvals (
    id TEXT PRIMARY KEY, subject_type TEXT NOT NULL, subject_id TEXT NOT NULL, decision TEXT NOT NULL,
    actor TEXT NOT NULL, reason TEXT, created_at TEXT NOT NULL
);
CREATE INDEX human_approvals_subject ON human_approvals (subject_type, subject_id);
CREATE TABLE evaluations (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, subject TEXT NOT NULL, metric TEXT NOT NULL,
    value REAL, passed INTEGER, detail_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
);
CREATE INDEX evaluations_kind ON evaluations (kind, created_at);
"""),
    (3, "assessments_and_inspections", """
CREATE TABLE architecture_assessments (
    id TEXT PRIMARY KEY, username TEXT NOT NULL, title TEXT NOT NULL, status TEXT NOT NULL,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX architecture_assessments_user ON architecture_assessments (username, updated_at);
CREATE TABLE architecture_answers (
    assessment_id TEXT NOT NULL REFERENCES architecture_assessments (id) ON DELETE CASCADE,
    question_id TEXT NOT NULL, revision INTEGER NOT NULL, value_json TEXT NOT NULL,
    answered_by TEXT NOT NULL, answered_at TEXT NOT NULL,
    PRIMARY KEY (assessment_id, question_id, revision)
);
CREATE TABLE inspection_batches (
    id TEXT PRIMARY KEY, username TEXT NOT NULL, title TEXT NOT NULL, status TEXT NOT NULL,
    conversation_id TEXT, notes TEXT, created_at TEXT NOT NULL
);
CREATE TABLE inspection_items (
    id TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES inspection_batches (id) ON DELETE CASCADE,
    file_ref TEXT NOT NULL, sha256 TEXT NOT NULL, bytes INTEGER NOT NULL, mime TEXT,
    width INTEGER, height INTEGER, result_json TEXT, created_at TEXT NOT NULL
);
CREATE INDEX inspection_items_batch ON inspection_items (batch_id);
"""),
    (4, "potato_inspection", """
ALTER TABLE inspection_batches ADD COLUMN supplier TEXT;
ALTER TABLE inspection_batches ADD COLUMN lot_code TEXT;
ALTER TABLE inspection_batches ADD COLUMN mm_per_px REAL;
ALTER TABLE inspection_batches ADD COLUMN thresholds_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE inspection_batches ADD COLUMN summary_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE inspection_batches ADD COLUMN detector TEXT;
ALTER TABLE inspection_batches ADD COLUMN updated_at TEXT;
CREATE INDEX inspection_batches_user ON inspection_batches (username, created_at);
ALTER TABLE inspection_items ADD COLUMN original_name TEXT;
ALTER TABLE inspection_items ADD COLUMN annotated_ref TEXT;
ALTER TABLE inspection_items ADD COLUMN scale REAL;
ALTER TABLE inspection_items ADD COLUMN duration_ms REAL;
CREATE TABLE inspection_potatoes (
    batch_id TEXT NOT NULL REFERENCES inspection_batches (id) ON DELETE CASCADE,
    potato_no INTEGER NOT NULL, item_id TEXT NOT NULL, grade TEXT, detection_score REAL,
    length_mm REAL, width_mm REAL, area_px INTEGER, elongation REAL, solidity REAL, dark_pct REAL,
    green_pct REAL, edge INTEGER NOT NULL DEFAULT 0, possible_cluster INTEGER, bbox_json TEXT NOT NULL,
    reasons_json TEXT NOT NULL DEFAULT '[]', metrics_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (batch_id, potato_no)
);
CREATE INDEX inspection_potatoes_grade ON inspection_potatoes (batch_id, grade);
"""),
]


def migrate(conn: sqlite3.Connection) -> list[int]:
    """Apply pending migrations; return the versions applied now."""
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL,"
                 " checksum TEXT NOT NULL, applied_at TEXT NOT NULL)")
    applied = {r[0]: r[1] for r in conn.execute("SELECT version, checksum FROM schema_migrations")}
    done = []
    for version, name, sql in MIGRATIONS:
        checksum = sha256_text(sql)
        if version in applied:
            if applied[version] != checksum:
                raise RuntimeError(f"Memory migration {version} ({name}) changed after it was applied")
            continue
        conn.execute("BEGIN IMMEDIATE")
        try:
            for statement in _statements(sql):
                conn.execute(statement)
            conn.execute("INSERT INTO schema_migrations (version, name, checksum, applied_at) VALUES (?, ?, ?, ?)",
                         (version, name, checksum, now_iso()))
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        conn.execute("COMMIT")
        done.append(version)
    return done


def _statements(sql: str) -> list[str]:
    """Split a migration into statements, keeping trigger bodies (which contain ';') whole."""
    out, buf = [], []
    for line in sql.strip().splitlines():
        buf.append(line)
        joined = "\n".join(buf).strip()
        if sqlite3.complete_statement(joined):
            out.append(joined)
            buf = []
    if "".join(buf).strip():
        raise ValueError("Incomplete statement in migration")
    return out
