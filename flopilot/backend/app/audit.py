"""Audit trail.

Audit events record *what happened* (ids, versions, counts, durations, tokens) but never raw
cell contents or prompts unless FLOPILOT_LOG_WORKBOOK_CONTENT is enabled.
"""
from __future__ import annotations

import logging
from typing import Any

from . import db
from .common import new_id, now_iso
from .config import get_settings

log = logging.getLogger("flopilot.audit")

_SENSITIVE_KEYS = {"message", "prompt", "values", "sample", "before", "after", "text", "question"}


def _redact(detail: dict[str, Any]) -> dict[str, Any]:
    if get_settings().log_workbook_content:
        return detail
    clean: dict[str, Any] = {}
    for key, value in detail.items():
        if key in _SENSITIVE_KEYS:
            clean[key] = "[redacted]"
        elif isinstance(value, dict):
            clean[key] = _redact(value)
        else:
            clean[key] = value
    return clean


def record(event_type: str, *, run_id: str | None = None, correlation_id: str | None = None,
           user_id: str | None = None, workspace_id: str | None = None, workbook_id: str | None = None,
           workbook_version: int | None = None, **detail: Any) -> None:
    safe = _redact(detail)
    db.execute(
        "INSERT INTO audit_events(id,ts,event_type,run_id,correlation_id,user_id,workspace_id,workbook_id,"
        "workbook_version,detail) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (new_id("evt"), now_iso(), event_type, run_id, correlation_id, user_id, workspace_id, workbook_id,
         workbook_version, db.dumps(safe)),
    )
    log.info("audit %s run=%s wb=%s v=%s", event_type, run_id, workbook_id, workbook_version)


def list_for_workbook(workbook_id: str, limit: int = 200) -> list[dict]:
    rows = db.fetchall(
        "SELECT * FROM audit_events WHERE workbook_id = ? ORDER BY ts DESC LIMIT ?", (workbook_id, limit)
    )
    for row in rows:
        row["detail"] = db.loads(row["detail"], {})
    return rows
