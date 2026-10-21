"""CSV export helpers with spreadsheet formula-injection protection."""
from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Sequence

_DANGEROUS = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value) -> str:
    if value is None:
        return ""
    s = str(value)
    if s and s[0] in _DANGEROUS:
        # Plain numbers such as -3 or +2.5 are safe and stay numeric.
        try:
            float(s)
            return s
        except ValueError:
            return "'" + s
    return s


def to_csv(header: Sequence[str], rows: Iterable[Sequence]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([safe_cell(h) for h in header])
    for r in rows:
        w.writerow([safe_cell(v) for v in r])
    return buf.getvalue()
