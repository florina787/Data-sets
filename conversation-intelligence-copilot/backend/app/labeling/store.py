"""Persistent store for model-produced labels (survives dataset rebuilds).

Labels are keyed by a hash of (clean text, speaker role, is-opening) plus the
model, prompt version and taxonomy version, so a change to any of those
invalidates the cache instead of silently reusing stale labels.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.labeling.taxonomy import TAXONOMY_VERSION

SCHEMA = """
CREATE TABLE IF NOT EXISTS text_labels (
    key TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    taxonomy_version TEXT NOT NULL,
    clean_text TEXT NOT NULL,
    role TEXT NOT NULL,
    is_opening INTEGER NOT NULL,
    status TEXT NOT NULL,           -- valid | failed
    label_json TEXT,
    error TEXT,
    attempts INTEGER NOT NULL DEFAULT 1,
    labeled_at TEXT NOT NULL,
    PRIMARY KEY (key, model, prompt_version, taxonomy_version)
);
"""


def text_key(clean_text: str, role: str, is_opening: bool) -> str:
    return hashlib.sha256(f"{role}|{int(is_opening)}|{clean_text.strip()}".encode()).hexdigest()


class LabelStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def get(self, key: str, model: str, prompt_version: str) -> dict | None:
        with self._conn() as c:
            row = c.execute(
                "SELECT status, label_json, attempts FROM text_labels WHERE key=? AND model=? AND prompt_version=? AND taxonomy_version=?",
                (key, model, prompt_version, TAXONOMY_VERSION),
            ).fetchone()
        if not row:
            return None
        return {"status": row[0], "label": json.loads(row[1]) if row[1] else None, "attempts": row[2]}

    def put(self, key: str, model: str, prompt_version: str, clean_text: str, role: str, is_opening: bool,
            label: dict | None, error: str | None = None) -> None:
        status = "valid" if label is not None else "failed"
        with self._conn() as c:
            c.execute(
                """INSERT INTO text_labels VALUES (?,?,?,?,?,?,?,?,?,?,1,?)
                   ON CONFLICT(key, model, prompt_version, taxonomy_version) DO UPDATE SET
                   status=excluded.status, label_json=excluded.label_json, error=excluded.error,
                   attempts=text_labels.attempts+1, labeled_at=excluded.labeled_at""",
                (key, model, prompt_version, TAXONOMY_VERSION, clean_text, role, int(is_opening), status,
                 json.dumps(label) if label else None, error, datetime.now(UTC).isoformat()),
            )

    def valid_labels(self) -> dict[str, dict]:
        """Latest valid label per text key for the current taxonomy version."""
        out: dict[str, dict] = {}
        with self._conn() as c:
            rows = c.execute(
                "SELECT key, model, prompt_version, label_json FROM text_labels WHERE status='valid' AND taxonomy_version=? ORDER BY labeled_at",
                (TAXONOMY_VERSION,),
            ).fetchall()
        for key, model, pv, lj in rows:
            out[key] = {**json.loads(lj), "model": model, "prompt_version": pv}
        return out

    def summary(self) -> dict:
        with self._conn() as c:
            rows = c.execute(
                "SELECT model, prompt_version, status, COUNT(*) FROM text_labels WHERE taxonomy_version=? GROUP BY 1,2,3",
                (TAXONOMY_VERSION,),
            ).fetchall()
        return {"taxonomy_version": TAXONOMY_VERSION, "groups": [
            {"model": m, "prompt_version": p, "status": s, "count": n} for m, p, s, n in rows]}
