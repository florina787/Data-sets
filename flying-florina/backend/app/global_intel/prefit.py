"""Fit (or load) the forecasting models ahead of time, like seeding: `python -m app.global_intel.prefit`.

Used by scripts/setup.sh and the e2e web server so the first map request never waits for model fitting, and so fitting never
competes for CPU with other work (it slows down sharply under contention).
"""

from __future__ import annotations

import time

from app.core import db
from app.seed.generator import ensure_seeded


def main() -> None:
    t0 = time.perf_counter()
    ensure_seeded()
    with db.session(write=True) as conn:
        db.init_schema(conn)
    from app.global_intel.forecast import engine

    e = engine()
    how = "loaded from cache" if getattr(e, "loaded_from_cache", False) else f"fitted in {e.build_ms:.0f} ms"
    print(f"forecasting models ready ({how}; {time.perf_counter() - t0:.1f} s total)")


if __name__ == "__main__":
    main()
