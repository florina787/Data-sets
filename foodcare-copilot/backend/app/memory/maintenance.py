"""Safe initialisation, backups and recovery for the memory database."""

from __future__ import annotations

import shutil
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.memory.store import get_store


def backups_dir() -> Path:
    return get_settings().memory_dir / "backups"


def list_backups() -> list[Path]:
    return sorted(backups_dir().glob("memory-*.db"))


def backup() -> dict:
    """Consistent online copy via the SQLite backup API; keeps the newest N copies."""
    store = get_store()
    store.init()
    target_dir = backups_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = target_dir / f"memory-{stamp}.db"
    started = time.perf_counter()
    src = store.connect()
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    kept = get_settings().memory_backups_kept
    for old in list_backups()[:-kept] if kept > 0 else []:
        old.unlink(missing_ok=True)
    return {"path": str(target), "bytes": target.stat().st_size,
            "duration_ms": round((time.perf_counter() - started) * 1000, 1), "kept": len(list_backups())}


def integrity_ok(path: Path) -> bool:
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
        try:
            return conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        return False


def startup() -> dict:
    """Check, recover if needed, migrate, apply retention and take a periodic backup."""
    settings = get_settings()
    store = get_store()
    path = store.path
    report: dict = {"recovered": False}
    if path.exists() and not integrity_ok(path):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        quarantine = path.with_name(f"{path.name}.corrupt-{stamp}")
        for suffix in ("", "-wal", "-shm"):
            part = Path(str(path) + suffix)
            if part.exists():
                part.rename(Path(str(quarantine) + suffix))
        candidates = [b for b in reversed(list_backups()) if integrity_ok(b)]
        if candidates:
            shutil.copy2(candidates[0], path)
        report = {"recovered": True, "quarantined": str(quarantine),
                  "restored_from": str(candidates[0]) if candidates else None}
    report["migrations_applied"] = store.init()
    report["retention_deleted"] = store.apply_retention()
    latest = list_backups()[-1:] if list_backups() else []
    age_h = (time.time() - latest[0].stat().st_mtime) / 3600 if latest else None
    if settings.memory_backup_interval_h > 0 and (age_h is None or age_h >= settings.memory_backup_interval_h):
        report["backup"] = backup()
    return report
