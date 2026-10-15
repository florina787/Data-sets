"""Scoped conversation context: active workbook/version, selection, confirmed business rules,
recent results/operations and pending clarifications. Invalidated when the workbook changes."""
from __future__ import annotations

from typing import Any

from .. import db
from ..auth import Principal
from ..common import AppError, new_id, now_iso
from ..workbook.model import WorkbookModel
from ..workbook.sources import revalidate


def get_or_create_conversation(principal: Principal, workbook_id: str, conversation_id: str | None, title: str) -> dict:
    if conversation_id:
        row = db.fetchone("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
        if not row or row["workbook_id"] != workbook_id or row["user_id"] != principal.user_id:
            raise AppError("conversation_not_found", "Conversation not found.", 404)
        row["context"] = db.loads(row["context"], {})
        return row
    cid = new_id("conv")
    ts = now_iso()
    ctx = {"workbook_id": workbook_id, "version": None, "business_rules": [], "recent_operations": [], "selection": None}
    db.execute("INSERT INTO conversations(id,workbook_id,user_id,title,context,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
               (cid, workbook_id, principal.user_id, title[:80], db.dumps(ctx), ts, ts))
    return {"id": cid, "workbook_id": workbook_id, "user_id": principal.user_id, "title": title[:80], "context": ctx}


def save_context(conversation_id: str, context: dict) -> None:
    db.execute("UPDATE conversations SET context = ?, updated_at = ? WHERE id = ?", (db.dumps(context), now_iso(), conversation_id))


def refresh_for_version(context: dict, model: WorkbookModel) -> list[str]:
    """Drop or revalidate facts that belonged to an older workbook version."""
    notes: list[str] = []
    if context.get("version") not in (None, model.version):
        last = context.get("last_result")
        if last:
            last["sources"] = revalidate(last.get("sources", []), model)
            last["stale"] = True
            notes.append(f"The workbook changed (now version {model.version}); earlier results are marked out of date.")
        kept = []
        for rule in context.get("business_rules", []):
            sheet = model.resolve_sheet(rule["sheet"])
            table = model.table(sheet) if sheet else None
            if table and table.column(rule["column"]):
                kept.append(rule)
            else:
                notes.append(f"Business rule '{rule['term']} = {rule['column']}' no longer applies (column not found).")
        context["business_rules"] = kept
        if context.get("pending_clarification"):
            context["pending_clarification"] = None
    context["version"] = model.version
    return notes


def add_message(conversation_id: str, role: str, content: dict, run_id: str | None = None) -> str:
    mid = new_id("msg")
    db.execute("INSERT INTO messages(id,conversation_id,role,content,run_id,created_at) VALUES(?,?,?,?,?,?)",
               (mid, conversation_id, role, db.dumps(content), run_id, now_iso()))
    return mid


def list_messages(principal: Principal, conversation_id: str) -> list[dict]:
    conv = db.fetchone("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
    if not conv or conv["user_id"] != principal.user_id:
        raise AppError("conversation_not_found", "Conversation not found.", 404)
    rows = db.fetchall("SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at", (conversation_id,))
    for r in rows:
        r["content"] = db.loads(r["content"], {})
    return rows


def list_conversations(principal: Principal, workbook_id: str) -> list[dict]:
    return db.fetchall("SELECT id, title, created_at, updated_at FROM conversations WHERE workbook_id = ? AND user_id = ? "
                       "ORDER BY updated_at DESC LIMIT 30", (workbook_id, principal.user_id))


def compact_result(result: dict | None, limit: int = 60) -> dict | None:
    """Keep a bounded copy of the last result for follow-up requests ("add this chart to the workbook")."""
    if not result:
        return None
    out: dict[str, Any] = {}
    for k, v in result.items():
        if isinstance(v, list) and len(v) > limit:
            out[k] = v[:limit]
        else:
            out[k] = v
    return out
