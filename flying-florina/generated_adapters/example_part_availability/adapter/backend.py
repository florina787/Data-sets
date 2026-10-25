"""Mock 'authorized system endpoint': a read-only synthetic snapshot of V_PART_AVAILABILITY.

In production this module would call the approved read-only DB view or the
documented ERP projection with a *service* credential and parameterized
queries. It never receives the end user's token.
"""
import json
import time
from datetime import date
from pathlib import Path

from adapter.models import PartAvailability, StockLocation

DATA = json.loads((Path(__file__).resolve().parents[1] / "mock_backend" / "data.json").read_text())
AS_OF = date.fromisoformat(DATA["as_of"])
CRITICAL_VERIFY_DAYS = 30


class BackendTimeout(Exception):
    pass


def _canonical(part_number: str, rows: list[dict]) -> PartAvailability:
    locs = []
    for r in rows:
        counted = date.fromisoformat(r["LAST_CNT_DT"])
        critical = r["CRIT_CODE"] in ("C", "H")
        stale = critical and (AS_OF - counted).days > CRITICAL_VERIFY_DAYS
        verified = not stale and r["LOT_NO"] != "UNKNOWN"
        note = ("stale count; " if stale else "") + ("untraceable lot; " if r["LOT_NO"] == "UNKNOWN" else "")
        locs.append(StockLocation(location=r["BASE_CODE"], quantity_on_hand=max(0, int(r["QTY_OH"] or 0)), lot=r["LOT_NO"],
                                  last_counted=counted, verified=verified, note=note.strip("; ")))
    return PartAvailability(part_number=part_number, description=rows[0]["PART_DESC"],
                            total_verified=sum(loc.quantity_on_hand for loc in locs if loc.verified), locations=locs)


def get_part_availability(part_number: str, timeout_s: float = 2.0) -> PartAvailability | None:
    started = time.perf_counter()
    rows = [r for r in DATA["rows"] if r["PART_NO"] == part_number]  # parameter compared, never interpolated
    if time.perf_counter() - started > timeout_s:
        raise BackendTimeout("backend exceeded timeout")
    return _canonical(part_number, rows) if rows else None


def list_parts(limit: int, offset: int) -> tuple[list[PartAvailability], int]:
    numbers = sorted({r["PART_NO"] for r in DATA["rows"]})
    page = numbers[offset:offset + limit]
    return [get_part_availability(p) for p in page], len(numbers)
