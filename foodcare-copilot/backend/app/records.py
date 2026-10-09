"""Append-oriented audit events, evidence registry and agent activity log."""

from __future__ import annotations

import json
from typing import Any

from app.db import new_id, now_iso, rows, session

# Provenance labels shown in the UI. Every artifact carries exactly one.
PROVENANCE = {
    "tool": "Executed tool result",
    "deterministic": "Deterministic calculation",
    "fixture": "Scripted fixture",
    "seeded_decision": "Selected demo decision",
    "live_ai": "Live AI output",
    "human": "Human action",
    "injected_fault": "Injected fault (demo)",
}


def audit(
    actor: str,
    action: str,
    outcome: str = "ok",
    entity_type: str | None = None,
    entity_id: str | None = None,
    **detail: Any,
) -> str:
    event_id = new_id("AUD")
    with session() as conn:
        conn.execute(
            "INSERT INTO audit_events (id, ts, actor, action, entity_type, entity_id, outcome,"
            " detail_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (event_id, now_iso(), actor, action, entity_type, entity_id, outcome,
             json.dumps(detail, default=str)),
        )
    return event_id


def evidence(
    type_: str,
    source: str,
    summary: str,
    provenance: str,
    revision: str | None = None,
    run_id: str | None = None,
    ref_table: str | None = None,
    ref_id: str | None = None,
) -> str:
    if provenance not in PROVENANCE:
        raise ValueError(f"unknown provenance {provenance}")
    evidence_id = new_id("EVD")
    with session() as conn:
        conn.execute(
            "INSERT INTO evidence (id, type, source, ts, revision, run_id, ref_table, ref_id,"
            " summary, provenance) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (evidence_id, type_, source, now_iso(), revision, run_id, ref_table, ref_id,
             summary, provenance),
        )
    return evidence_id


def activity(
    run_id: str, agent: str, kind: str, summary: str, provenance: str, **detail: Any
) -> None:
    """Concise, user-visible activity summaries. Never model chain-of-thought."""
    with session() as conn:
        conn.execute(
            "INSERT INTO activity (run_id, ts, agent, kind, provenance, summary, detail_json)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (run_id, now_iso(), agent, kind, provenance, summary,
             json.dumps(detail, default=str)),
        )


def list_activity(run_id: str, after_seq: int = 0) -> list[dict]:
    items = rows(
        "SELECT * FROM activity WHERE run_id = ? AND seq > ? ORDER BY seq", (run_id, after_seq)
    )
    for item in items:
        item["detail"] = json.loads(item.pop("detail_json"))
        item["provenance_label"] = PROVENANCE[item["provenance"]]
    return items
