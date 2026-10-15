"""Workbooks and their immutable versions. Every read goes through an access check."""
from __future__ import annotations

import threading
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .. import audit, db
from ..auth import Principal
from ..common import AppError, new_id, now_iso, sha256_bytes
from ..config import get_settings
from ..storage import get_storage
from ..workbook.fidelity import detect_features
from ..workbook.ingest import ValidatedUpload, validate_upload
from ..workbook.model import WorkbookModel, csv_to_xlsx, load_model, model_cache
from ..workbook.profile import profile_workbook

DEMO_WORKBOOK = Path(__file__).resolve().parents[2] / "sample_data" / "flopilot_demo_workbook.xlsx"

_wb_locks: dict[str, threading.Lock] = {}
_wb_locks_guard = threading.Lock()


def workbook_lock(workbook_id: str) -> threading.Lock:
    """Serialises version publication per workbook (single-process deployment)."""
    with _wb_locks_guard:
        return _wb_locks.setdefault(workbook_id, threading.Lock())


def _row_to_workbook(row: dict) -> dict:
    return {k: row[k] for k in ("id", "name", "source_format", "current_version", "created_at", "owner_id")} | {
        "is_demo": bool(row["is_demo"])}


def create_workbook(principal: Principal, upload: ValidatedUpload, is_demo: bool = False) -> dict:
    # Uploading user data needs write-level access; viewers may still open the synthetic demo.
    principal.require("read" if is_demo else "propose")
    wb_id = new_id("wb")
    storage = get_storage()
    ts = now_iso()
    original_key = f"{principal.workspace_id}/{wb_id}/original.{upload.fmt}"
    storage.put_immutable(original_key, upload.data)
    if upload.fmt == "csv":
        xlsx = csv_to_xlsx(upload.data, sheet_name=Path(upload.filename).stem[:31] or "Data")
        kind, note = "converted_from_csv", "Converted from the uploaded CSV (original CSV kept unchanged)."
    else:
        xlsx = upload.data
        kind, note = "original", "Original upload (immutable)."
    # Parse once before registering, so malformed files never become workbooks.
    model = load_model(xlsx, wb_id, 1)
    key = f"{principal.workspace_id}/{wb_id}/v1.xlsx"
    storage.put_immutable(key, xlsx)
    with db.tx() as conn:
        conn.execute(
            "INSERT INTO workbooks(id,workspace_id,owner_id,name,source_format,current_version,is_demo,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (wb_id, principal.workspace_id, principal.user_id, upload.filename, upload.fmt, 1, int(is_demo), ts))
        conn.execute(
            "INSERT INTO versions(id,workbook_id,version_no,storage_key,sha256,size_bytes,kind,operation_id,note,created_by,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (new_id("ver"), wb_id, 1, key, sha256_bytes(xlsx), len(xlsx), kind, None, note, principal.user_id, ts))
    model_cache.get((wb_id, 1), lambda: model)
    audit.record("workbook_uploaded", user_id=principal.user_id, workspace_id=principal.workspace_id, workbook_id=wb_id,
                 workbook_version=1, format=upload.fmt, size_bytes=len(upload.data), is_demo=is_demo,
                 original_sha256=sha256_bytes(upload.data))
    return get_workbook(principal, wb_id)


def create_demo_workbook(principal: Principal) -> dict:
    data = DEMO_WORKBOOK.read_bytes()
    return create_workbook(principal, validate_upload("FloPilot demo workbook (synthetic).xlsx", data), is_demo=True)


def get_workbook_row(principal: Principal, workbook_id: str) -> dict:
    row = db.fetchone("SELECT * FROM workbooks WHERE id = ? AND deleted_at IS NULL", (workbook_id,))
    # Same response for "missing" and "not yours" so ids cannot be probed across workspaces.
    if not row or row["workspace_id"] != principal.workspace_id:
        raise AppError("workbook_not_found", "Workbook not found.", 404)
    principal.require("read")
    return row


def get_workbook(principal: Principal, workbook_id: str) -> dict:
    return _row_to_workbook(get_workbook_row(principal, workbook_id))


def list_workbooks(principal: Principal) -> list[dict]:
    principal.require("read")
    rows = db.fetchall("SELECT * FROM workbooks WHERE workspace_id = ? AND deleted_at IS NULL ORDER BY created_at DESC",
                       (principal.workspace_id,))
    return [_row_to_workbook(r) for r in rows]


def list_versions(principal: Principal, workbook_id: str) -> list[dict]:
    get_workbook_row(principal, workbook_id)
    rows = db.fetchall("SELECT version_no, kind, operation_id, note, created_by, created_at, sha256, size_bytes FROM versions "
                       "WHERE workbook_id = ? ORDER BY version_no DESC", (workbook_id,))
    return rows


def version_bytes(workbook_id: str, version: int) -> bytes:
    row = db.fetchone("SELECT storage_key, sha256 FROM versions WHERE workbook_id = ? AND version_no = ?", (workbook_id, version))
    if not row:
        raise AppError("version_not_found", f"Version {version} does not exist.", 404)
    data = get_storage().get(row["storage_key"])
    if sha256_bytes(data) != row["sha256"]:
        raise AppError("integrity_error", "A stored workbook version failed its integrity check.", 500)
    return data


def get_model(principal: Principal, workbook_id: str, version: int | None = None) -> WorkbookModel:
    row = get_workbook_row(principal, workbook_id)
    v = version or row["current_version"]
    if v < 1 or v > row["current_version"]:
        raise AppError("version_not_found", f"Version {v} does not exist.", 404)
    return model_cache.get((workbook_id, v), lambda: load_model(version_bytes(workbook_id, v), workbook_id, v))


_profile_cache: OrderedDict[tuple[str, int], dict] = OrderedDict()
_profile_lock = threading.Lock()


def get_profile(principal: Principal, workbook_id: str, version: int | None = None) -> dict:
    model = get_model(principal, workbook_id, version)
    key = (workbook_id, model.version)
    with _profile_lock:
        if key in _profile_cache:
            _profile_cache.move_to_end(key)
            return _profile_cache[key]
    profile = profile_workbook(model)
    profile["fidelity"] = detect_features(version_bytes(workbook_id, model.version))
    with _profile_lock:
        _profile_cache[key] = profile
        while len(_profile_cache) > 16:
            _profile_cache.popitem(last=False)
    return profile


def publish_version(principal: Principal, workbook_id: str, base_version: int, data: bytes, kind: str,
                    operation_id: str | None, note: str) -> int:
    """Atomically publish `data` as the next version, only if `base_version` is still current."""
    with workbook_lock(workbook_id):
        row = db.fetchone("SELECT current_version, workspace_id FROM workbooks WHERE id = ?", (workbook_id,))
        if row is None or row["workspace_id"] != principal.workspace_id:
            raise AppError("workbook_not_found", "Workbook not found.", 404)
        if row["current_version"] != base_version:
            raise AppError("stale_version", f"The workbook changed (now version {row['current_version']}) after this change was prepared.", 409)
        new_version = base_version + 1
        key = f"{row['workspace_id']}/{workbook_id}/v{new_version}.xlsx"
        get_storage().put_immutable(key, data)
        with db.tx() as conn:
            updated = conn.execute("UPDATE workbooks SET current_version = ? WHERE id = ? AND current_version = ?",
                                   (new_version, workbook_id, base_version)).rowcount
            if updated != 1:  # pragma: no cover - guarded by the lock above
                raise AppError("stale_version", "The workbook changed while publishing.", 409)
            conn.execute(
                "INSERT INTO versions(id,workbook_id,version_no,storage_key,sha256,size_bytes,kind,operation_id,note,created_by,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (new_id("ver"), workbook_id, new_version, key, sha256_bytes(data), len(data), kind, operation_id, note,
                 principal.user_id, now_iso()))
        return new_version


def delete_workbook(principal: Principal, workbook_id: str) -> None:
    row = get_workbook_row(principal, workbook_id)
    if row["owner_id"] != principal.user_id and principal.role != "admin":
        raise AppError("forbidden", "Only the owner or an admin can delete this workbook.", 403)
    _purge(workbook_id)
    audit.record("workbook_deleted", user_id=principal.user_id, workspace_id=principal.workspace_id, workbook_id=workbook_id)


def _purge(workbook_id: str) -> None:
    storage = get_storage()
    for v in db.fetchall("SELECT storage_key FROM versions WHERE workbook_id = ?", (workbook_id,)):
        storage.delete(v["storage_key"])
    row = db.fetchone("SELECT workspace_id, source_format FROM workbooks WHERE id = ?", (workbook_id,))
    if row:
        storage.delete(f"{row['workspace_id']}/{workbook_id}/original.{row['source_format']}")
    # Remove derived content that can contain cell values: chat history, change sets, run results.
    with db.tx() as conn:
        conn.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE workbook_id = ?)", (workbook_id,))
        conn.execute("DELETE FROM conversations WHERE workbook_id = ?", (workbook_id,))
        conn.execute("UPDATE operations SET payload = ?, result = NULL WHERE workbook_id = ?",
                     (db.dumps({"purged": True}), workbook_id))
        conn.execute("UPDATE runs SET result = NULL, plan = NULL WHERE workbook_id = ?", (workbook_id,))
        conn.execute("UPDATE workbooks SET deleted_at = ? WHERE id = ?", (now_iso(), workbook_id))
    model_cache.drop_workbook(workbook_id)


def apply_retention() -> int:
    """Delete workbook contents older than FLOPILOT_RETENTION_DAYS (metadata and audit are kept)."""
    days = get_settings().retention_days
    if days <= 0:
        return 0
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = db.fetchall("SELECT id FROM workbooks WHERE deleted_at IS NULL AND created_at < ?", (cutoff,))
    for r in rows:
        _purge(r["id"])
        audit.record("workbook_retention_purge", workbook_id=r["id"], retention_days=days)
    return len(rows)
