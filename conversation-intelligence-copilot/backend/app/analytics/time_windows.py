"""Date-window resolution from the timestamps actually present in the data.

"Last month" never means the real-world current month: it means the latest
calendar month represented in the selected dataset, dated by each
conversation's earliest timestamp.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from app.analytics.db import AnalyticsDB, DATASET_SOURCES
from app.schemas.analysis import DateWindow


def _month_bounds(month: str) -> tuple[str, str]:
    start = pd.Period(month, freq="M")
    return start.start_time.date().isoformat(), (start + 1).start_time.date().isoformat()


def available_months(db: AnalyticsDB, dataset_mode: str) -> pd.DataFrame:
    src = DATASET_SOURCES[dataset_mode]
    return db.query(
        f"SELECT month, COUNT(*) AS conversations, MIN(start_timestamp) AS first_start, MAX(start_timestamp) AS last_start "
        f"FROM conversations WHERE dataset_source IN ({','.join('?' * len(src))}) AND month IS NOT NULL GROUP BY month ORDER BY month",
        src,
    )


def data_range(db: AnalyticsDB, dataset_mode: str) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    src = DATASET_SOURCES[dataset_mode]
    row = db.query(
        f"SELECT MIN(m.timestamp) AS lo, MAX(m.timestamp) AS hi FROM messages m WHERE m.dataset_source IN ({','.join('?' * len(src))})", src
    ).iloc[0]
    return (row["lo"] if pd.notna(row["lo"]) else None, row["hi"] if pd.notna(row["hi"]) else None)


def resolve_window(db: AnalyticsDB, dataset_mode: str, spec: dict | None) -> DateWindow:
    spec = spec or {"type": "all"}
    kind = spec.get("type", "all")
    months = available_months(db, dataset_mode)
    lo, hi = data_range(db, dataset_mode)
    span = f"Data spans {lo:%d %b %Y} to {hi:%d %b %Y}" if lo is not None else "No usable timestamps"

    if kind == "all" or months.empty:
        if kind != "all" and months.empty:
            return DateWindow(label="All dates", rule="all", explanation="No usable timestamps, so the requested date filter cannot be applied reliably.")
        return DateWindow(label="All dates", rule="all", explanation=f"{span}; no date filter applied.")

    if kind == "last_month":
        latest = months.iloc[-1]
        month = latest["month"]
        start, end = _month_bounds(month)
        # A month is treated as partial only if the data stops before its last day AND its volume is
        # under half the median of the other months (e.g. 48 vs ~800). Ending a day early alone is not enough.
        others = months.iloc[:-1]["conversations"]
        low_volume = len(others) > 0 and int(latest["conversations"]) < 0.5 * float(others.median())
        covered = hi is not None and hi.date() >= date.fromisoformat(end) - pd.Timedelta(days=1)
        complete = covered or not low_volume
        if not complete and len(months) > 1:
            prev = months.iloc[-2]["month"]
            p_start, p_end = _month_bounds(prev)
            return DateWindow(start=p_start, end=p_end, label=pd.Period(prev).strftime("%B %Y"), rule="latest_complete_month",
                              explanation=f"{span}. {pd.Period(month).strftime('%B %Y')} is only partly covered ({int(latest['conversations'])} conversations, under half a typical month), so the latest complete month, "
                                          f"{pd.Period(prev).strftime('%B %Y')}, is used. Conversations are dated by their earliest message.")
        return DateWindow(start=start, end=end, label=pd.Period(month).strftime("%B %Y"), rule="latest_month",
                          explanation=f"{span}. The latest calendar month in which conversations start is {pd.Period(month).strftime('%B %Y')} "
                                      f"({int(latest['conversations'])} conversations); conversations are dated by their earliest message.")

    if kind in ("month", "previous_month", "next_month"):
        month = spec.get("month") or months.iloc[-1]["month"]
        period = pd.Period(month, freq="M")
        if kind == "previous_month":
            period -= 1
        elif kind == "next_month":
            period += 1
        month = period.strftime("%Y-%m")
        start, end = _month_bounds(month)
        n = months.loc[months["month"] == month, "conversations"]
        note = f"{int(n.iloc[0])} conversations start in this month." if len(n) else "No conversations start in this month in the selected dataset."
        return DateWindow(start=start, end=end, label=period.strftime("%B %Y"), rule=kind, explanation=f"{span}. {note}")

    if kind == "last_n_months":
        n = max(1, int(spec.get("n", 3)))
        chosen = months.iloc[-n:]["month"].tolist()
        start, _ = _month_bounds(chosen[0])
        _, end = _month_bounds(chosen[-1])
        return DateWindow(start=start, end=end, label=f"{pd.Period(chosen[0]).strftime('%b %Y')} – {pd.Period(chosen[-1]).strftime('%b %Y')}",
                          rule="last_n_months", explanation=f"{span}. The last {len(chosen)} months with data.")

    if kind == "range":
        return DateWindow(start=spec.get("start"), end=spec.get("end"), label=f"{spec.get('start')} to {spec.get('end')}", rule="range",
                          explanation=f"{span}. Explicit date range (end exclusive).")

    raise ValueError(f"Unsupported window type: {kind}")
