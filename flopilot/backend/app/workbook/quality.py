"""Deterministic data-quality detectors. All findings are *candidates for review*, never verdicts."""
from __future__ import annotations

import difflib
import re
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime
from typing import Any

from . import values as V
from .model import Column, SheetTable


def normalize_key(value: Any) -> Any:
    if isinstance(value, str):
        return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", value.strip().lower()))
    if isinstance(value, datetime):
        return value.date()
    if V.is_number(value):
        return round(float(value), 2)
    return value


def category_variants(table: SheetTable, col: Column, threshold: float = 0.85) -> list[dict]:
    """Groups of spellings that probably mean the same category (case/spacing/typos)."""
    # Count spellings exactly as stored so whitespace-only variants ("Europe ") are reported too.
    counts = Counter(v for v in table.values(col) if isinstance(v, str) and v.strip() and not V.is_error(v))
    if not counts or len(counts) > 300:
        return []
    by_key: dict[str, Counter] = defaultdict(Counter)
    for original, n in counts.items():
        by_key[normalize_key(original)][original] += n
    keys = sorted(by_key, key=lambda k: -sum(by_key[k].values()))
    merged: list[list[str]] = []
    assigned: set[str] = set()
    for key in keys:
        if key in assigned:
            continue
        group = [key]
        assigned.add(key)
        for other in keys:
            if other in assigned or len(key) < 4 or len(other) < 4:
                continue
            if difflib.SequenceMatcher(None, key, other).ratio() >= threshold:
                group.append(other)
                assigned.add(other)
        merged.append(group)
    results = []
    for group in merged:
        spellings: Counter = Counter()
        for key in group:
            spellings.update(by_key[key])
        if len(spellings) > 1:
            canonical = max(spellings.items(), key=lambda kv: (kv[1], kv[0] == kv[0].strip(), kv[0].istitle()))[0]
            results.append({
                "canonical": canonical,
                "variants": {s: n for s, n in spellings.items() if s != canonical},
                "total": sum(spellings.values()),
            })
    return results


def whitespace_cells(table: SheetTable, col: Column) -> list[int]:
    return [r for r, vals in table.rows
            if isinstance(vals[table.col_pos(col)], str)
            and vals[table.col_pos(col)] != re.sub(r"\s+", " ", vals[table.col_pos(col)]).strip()]


def find_duplicates(table: SheetTable, key_columns: list[Column] | None = None,
                    id_columns: list[Column] | None = None) -> dict:
    """Potential duplicate rows.

    * With `key_columns`: rows whose normalised key values match.
    * Without: rows that match on every non-identifier column (the identifier itself may differ,
      which is the usual shape of a double-entered record), plus repeated identifier values.
    """
    id_columns = id_columns if id_columns is not None else [c for c in table.columns if c.semantic == "identifier"]
    compare = key_columns or [c for c in table.columns if c not in id_columns] or table.columns
    positions = [table.col_pos(c) for c in compare]
    groups: dict[tuple, list[int]] = defaultdict(list)
    for row_no, vals in table.rows:
        key = tuple(normalize_key(vals[p]) for p in positions)
        if all(k in (None, "") for k in key):
            continue
        groups[key].append(row_no)
    dup_groups = [rows for rows in groups.values() if len(rows) > 1]

    id_dups: list[dict] = []
    if not key_columns:
        for col in id_columns:
            seen: dict[Any, list[int]] = defaultdict(list)
            for row_no, vals in table.rows:
                v = vals[table.col_pos(col)]
                if not V.is_blank(v):
                    seen[normalize_key(v)].append(row_no)
            for value, rows in seen.items():
                if len(rows) > 1:
                    id_dups.append({"column": col.name, "value": value, "rows": rows})
    return {
        "compared_columns": [c.name for c in compare],
        "groups": dup_groups,
        "extra_rows": sum(len(g) - 1 for g in dup_groups),
        "repeated_identifiers": id_dups,
    }


def outlier_candidates(table: SheetTable, col: Column, k: float = 3.0) -> dict:
    """Tukey's far-out fences (outside Q1 - k*IQR .. Q3 + k*IQR, k=3).

    Chosen over z-scores because business amounts are usually skewed; z-scores flag many
    ordinary large orders. Results are candidates for human review, not errors.
    """
    pos = table.col_pos(col)
    points = [(r, float(vals[pos])) for r, vals in table.rows if V.is_number(vals[pos])]
    if len(points) < 8:
        return {"method": "insufficient data (fewer than 8 numeric values)", "candidates": [], "n": len(points)}
    nums = [v for _, v in points]
    q1, _, q3 = statistics.quantiles(nums, n=4)
    iqr = q3 - q1
    lo, hi = q1 - k * iqr, q3 + k * iqr
    median = statistics.median(nums)
    candidates = []
    if iqr > 0:
        for r, v in points:
            if v < lo or v > hi:
                candidates.append({"row": r, "value": v, "score": round((v - median) / iqr, 2)})
    candidates.sort(key=lambda c: -abs(c["score"] or 0))
    return {"method": f"Tukey far-out fences: outside {lo:,.2f} .. {hi:,.2f} (Q1 - {k}×IQR, Q3 + {k}×IQR)",
            "median": median, "q1": q1, "q3": q3, "lower": lo, "upper": hi, "n": len(points), "candidates": candidates}


def date_format_mix(table: SheetTable, col: Column) -> dict:
    """Describe how dates are stored in a column: real dates vs text in various formats."""
    kinds: Counter = Counter()
    evidence: Counter = Counter()
    for v in table.values(col):
        if isinstance(v, (datetime, date)):
            kinds["excel_date"] += 1
        elif isinstance(v, str) and (k := V.date_text_kind(v)):
            kinds[f"text:{k}"] += 1
            if ev := V.slash_order_evidence(v):
                evidence[ev] += 1
    order = None
    if evidence and len(evidence) == 1:
        order = next(iter(evidence))
    return {"kinds": dict(kinds), "slash_order_evidence": dict(evidence), "inferred_order": order}
