"""Logical backup and restore (JSON, all tables, FK-ordered).
  python -m app.backup dump  <file.json>
  python -m app.backup restore <file.json>     (demo mode only; replaces current data)
For production, use database-native backups (pg_dump / PITR); see docs/PRODUCTION_ARCHITECTURE.md."""
from __future__ import annotations

import json
import sys
from datetime import datetime

from sqlalchemy import DateTime, insert, select

from app.config import get_settings
from app.db import Base, get_engine
from app.models import orm  # noqa: F401


def dump(path: str) -> dict:
    eng = get_engine()
    out = {"format": "beauty-ai-backup-v1", "created_at": datetime.utcnow().isoformat() + "Z", "tables": {}}
    with eng.connect() as c:
        for t in Base.metadata.sorted_tables:
            rows = [dict(r._mapping) for r in c.execute(select(t))]
            out["tables"][t.name] = rows
    with open(path, "w") as f:
        json.dump(out, f, default=lambda o: o.isoformat() if isinstance(o, datetime) else str(o))
    return {t: len(r) for t, r in out["tables"].items()}


def restore(path: str) -> dict:
    if not get_settings().demo:
        raise SystemExit("Restore via this tool is demo-only; use database-native restore in production.")
    data = json.load(open(path))
    if data.get("format") != "beauty-ai-backup-v1":
        raise SystemExit("Unknown backup format")
    eng = get_engine()
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    counts = {}
    with eng.begin() as c:
        for t in Base.metadata.sorted_tables:
            rows = data["tables"].get(t.name, [])
            dt_cols = [col.name for col in t.columns if isinstance(col.type, DateTime)]
            for r in rows:
                for k in dt_cols:
                    if r.get(k):
                        r[k] = datetime.fromisoformat(r[k])
            if rows:
                c.execute(insert(t), rows)
            counts[t.name] = len(rows)
    return counts


if __name__ == "__main__":
    cmd, path = sys.argv[1], sys.argv[2]
    print(json.dumps(dump(path) if cmd == "dump" else restore(path)))
