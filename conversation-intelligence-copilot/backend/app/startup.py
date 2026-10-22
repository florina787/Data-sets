"""Startup validation: configuration, dataset, database, index, model, dependencies."""

from __future__ import annotations

import importlib
from datetime import UTC, datetime

from app.config import get_settings

_last: dict | None = None


def _check(name: str, ok: bool, detail: str, required: bool = True) -> dict:
    return {"check": name, "status": "ok" if ok else ("error" if required else "degraded"), "detail": detail, "required": required}


def startup_report(refresh: bool = False) -> dict:
    global _last
    if _last is not None and not refresh:
        return _last
    s = get_settings()
    checks = [_check("raw_dataset", s.raw_dataset_path.exists(), str(s.raw_dataset_path.name))]
    try:
        from app.analytics.db import get_db

        meta = get_db().metadata()
        checks.append(_check("analytics_database", True, f"built {meta['built_at'][:19]}Z, {meta['label_coverage']['messages']} labelled messages"))
    except Exception as e:  # noqa: BLE001
        checks.append(_check("analytics_database", False, f"{e}. Run `make prepare`."))
    from app.retrieval.index import retriever_status

    r = retriever_status()
    checks.append(_check("retrieval_index", bool(r.get("available")),
                         f"{r.get('chunks')} chunks, {r.get('embedding_backend')}" if r.get("available") else r.get("reason", ""), required=False))
    from app.llm.gemini_client import get_llm

    m = get_llm().status()
    checks.append(_check("gemini", bool(m.get("available")), f"{m.get('model')}: {m.get('reason') or m.get('mode')}", required=False))
    for mod in ("duckdb", "faiss", "langgraph", "google.genai"):
        try:
            importlib.import_module(mod)
            checks.append(_check(f"dependency:{mod}", True, "importable"))
        except ImportError as e:
            checks.append(_check(f"dependency:{mod}", False, str(e)))
    try:
        from app.memory.store import get_memory

        purged = get_memory().purge_older_than(s.session_retention_days)
        checks.append(_check("memory_store", True, f"SQLite ready; {purged} expired session(s) purged"))
    except Exception as e:  # noqa: BLE001
        checks.append(_check("memory_store", False, str(e)))
    status = "error" if any(c["status"] == "error" for c in checks) else "degraded" if any(c["status"] == "degraded" for c in checks) else "ok"
    _last = {"status": status, "checked_at": datetime.now(UTC).isoformat(), "checks": checks, "dataset_mode": s.dataset_mode}
    return _last
