"""Background jobs. The UI polls job status, so progress waits on real tool completion."""

from __future__ import annotations

import json
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from app.db import new_id, now_iso, row, session
from app.errors import PlatformError

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="job")
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for(key: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(key, threading.Lock())


def submit(kind: str, run_id: str | None, fn: Callable[[], Any], lock_key: str | None = None) -> str:
    job_id = new_id("JOB")
    lock = _lock_for(lock_key) if lock_key else None
    if lock is not None and not lock.acquire(blocking=False):
        raise PlatformError("Another job is already running for this item", lock=lock_key)
    created_at = now_iso()
    with session() as conn:
        conn.execute("INSERT INTO jobs (id, kind, run_id, status, created_at) VALUES (?, ?, ?, 'running', ?)",
                     (job_id, kind, run_id, created_at))

    def runner() -> None:
        try:
            result = fn()
            status, error = "succeeded", None
        except PlatformError as exc:
            result, status, error = {"details": exc.details}, "failed", exc.message
        except Exception as exc:  # noqa: BLE001 - recorded and surfaced to the UI
            result, status, error = {"trace": traceback.format_exc()[-2000:]}, "failed", f"{type(exc).__name__}: {exc}"
        finally:
            if lock is not None:
                lock.release()
        # Upsert: a demo reset recreates the database while its own job is running.
        with session() as conn:
            conn.execute(
                "INSERT INTO jobs (id, kind, run_id, status, created_at, finished_at, result_json, error)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET status = excluded.status,"
                " finished_at = excluded.finished_at, result_json = excluded.result_json, error = excluded.error",
                (job_id, kind, run_id, status, created_at, now_iso(), json.dumps(result, default=str), error))

    _executor.submit(runner)
    return job_id


def get(job_id: str) -> dict | None:
    found = row("SELECT * FROM jobs WHERE id = ?", (job_id,))
    if found:
        found["result"] = json.loads(found.pop("result_json") or "null")
    return found


def mark_interrupted() -> None:
    """On startup, jobs left 'running' by a previous process are marked interrupted."""
    with session() as conn:
        conn.execute("UPDATE jobs SET status = 'interrupted', finished_at = ?, error = 'process restarted'"
                     " WHERE status = 'running'", (now_iso(),))
