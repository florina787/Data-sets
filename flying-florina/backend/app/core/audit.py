"""Append-only audit log with chained SHA-256 hashes.

Each event stores the hash of the previous event; altering or deleting any
row breaks verification of every later row. This demonstrates tamper
*evidence*. It is not tamper-proof: an administrator with write access to the
SQLite file can recompute the whole chain. Production use needs an external
anchor (WORM storage, a signed timestamping service or an HSM-backed signer).
"""

from __future__ import annotations

import sqlite3
from typing import Any

from app.core import db
from app.core.util import new_id, now_iso, redact_obj, sha256_json

GENESIS = "0" * 64


def _event_hash(event_id: str, ts: str, actor: str, kind: str, summary: str, data_json: str, prev: str) -> str:
    return sha256_json([event_id, ts, actor, kind, summary, data_json, prev])


def append(actor: str, kind: str, summary: str, data: dict[str, Any] | None = None,
           conn: sqlite3.Connection | None = None) -> str:
    """Append one event. Payload is redacted before it is stored."""
    if conn is None:
        with db.session(write=True) as c:
            return append(actor, kind, summary, data, c)
    with db._write_lock:  # serialize chain extension
        last = conn.execute("SELECT hash FROM audit_events ORDER BY seq DESC LIMIT 1").fetchone()
        prev = last["hash"] if last else GENESIS
        event_id = new_id("AUD")
        ts = now_iso()
        data_json = db.jdump(redact_obj(data or {}))
        h = _event_hash(event_id, ts, actor, kind, summary, data_json, prev)
        conn.execute(
            "INSERT INTO audit_events (id, ts, actor, kind, summary, data_json, prev_hash, hash) VALUES (?,?,?,?,?,?,?,?)",
            (event_id, ts, actor, kind, summary, data_json, prev, h),
        )
        return event_id


def list_events(limit: int = 200, kind: str | None = None, offset: int = 0) -> list[dict[str, Any]]:
    sql = "SELECT seq, id, ts, actor, kind, summary, data_json, prev_hash, hash FROM audit_events"
    params: list[Any] = []
    if kind:
        sql += " WHERE kind = ?"
        params.append(kind)
    sql += " ORDER BY seq DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    out = db.query(sql, params)
    for e in out:
        e["data"] = db.jload(e.pop("data_json"), {})
    return out


def verify(events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Recompute the chain. Accepts an exported list (oldest first) or reads the DB."""
    if events is None:
        events = db.query("SELECT id, ts, actor, kind, summary, data_json, prev_hash, hash FROM audit_events ORDER BY seq ASC")
    prev = GENESIS
    for index, e in enumerate(events):
        data_json = e.get("data_json")
        if data_json is None:
            data_json = db.jdump(e.get("data", {}))
        if e["prev_hash"] != prev:
            return {"valid": False, "checked": index, "broken_at": e["id"], "reason": "prev_hash does not match previous event hash"}
        expected = _event_hash(e["id"], e["ts"], e["actor"], e["kind"], e["summary"], data_json, prev)
        if expected != e["hash"]:
            return {"valid": False, "checked": index, "broken_at": e["id"], "reason": "event content does not match its hash"}
        prev = e["hash"]
    return {
        "valid": True,
        "checked": len(events),
        "head": prev,
        "limits": "Tamper-evident only. A privileged host administrator can rewrite the SQLite file and recompute the chain.",
    }


def export_chain() -> list[dict[str, Any]]:
    return db.query("SELECT id, ts, actor, kind, summary, data_json, prev_hash, hash FROM audit_events ORDER BY seq ASC")
