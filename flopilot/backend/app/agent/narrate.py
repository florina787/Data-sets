"""Deterministic narration of tool results. Every number printed comes from the result dict."""
from __future__ import annotations

from typing import Any


def fmt(value: Any, result: dict | None = None, kind: str | None = None) -> str:
    if value is None:
        return "—"
    if isinstance(value, str):
        return value
    result = result or {}
    nf = result.get("number_format") or ""
    semantic = result.get("semantic")
    if kind == "pct":
        return f"{value:+.1f}%"
    if kind == "count":
        return f"{int(value):,}"
    if semantic == "percentage" or "%" in nf:
        return f"{value * 100:.1f}%"
    if "$" in nf or semantic == "currency":
        sign = "-" if value < 0 else ""
        sym = "$" if "$" in nf else ""
        return f"{sign}{sym}{abs(value):,.2f}"
    if isinstance(value, float) and not value.is_integer():
        return f"{value:,.2f}"
    return f"{int(value):,}"


def narrate(result: dict) -> str:
    kind = result.get("kind")
    fn = {
        "aggregate": _aggregate, "missing": _missing, "time_series": _time_series, "period_change": _period_change,
        "variance": _variance, "correlation": _correlation, "histogram": _histogram, "duplicates": _duplicates,
        "outliers": _outliers, "formula_explanation": _explanation, "formula_diagnosis": _diagnosis,
        "consistency": _consistency, "rows": _rows, "schema": _schema, "sheet_profile": _sheet_profile,
    }.get(kind)
    return fn(result) if fn else ""


def _aggregate(r: dict) -> str:
    func = r["function"]
    target = f"{func} of **{r['measure']}**" if r.get("measure") else "row count"
    head = f"{target[0].upper()}{target[1:]} on **{r['sheet']}**"
    if r["filters"]:
        head += " where " + ", ".join(f"{f['column']} {f['op']} {f['value']}" for f in r["filters"])
    if not r["group_by"]:
        v = r["rows"][0]["value"] if r["rows"] else None
        k = "count" if func in ("count", "distinct_count") else None
        return f"{head}: **{fmt(v, r, k)}** ({r['rows_considered']:,} rows considered)."
    lines = [f"{head}, by {', '.join(r['group_by'])}:"]
    k = "count" if func in ("count", "distinct_count") else None
    for row in r["rows"][:12]:
        lines.append(f"- {' / '.join(map(str, row['group']))}: **{fmt(row['value'], r, k)}** ({row['rows']:,} rows)")
    if r["group_count"] > 12:
        lines.append(f"- …and {r['group_count'] - 12} more group(s) (see the table).")
    if r.get("total") is not None and func in ("sum", "count"):
        lines.append(f"Total: **{fmt(r['total'], r, k)}**.")
        top = r["rows"][0] if r["rows"] else None
        if top and r["total"] and func == "sum" and top["value"] is not None and r["total"] > 0:
            lines.append(f"{' / '.join(map(str, top['group']))} is the largest group at {top['value'] / r['total'] * 100:.1f}% of the total.")
    return "\n".join(lines)


def _missing(r: dict) -> str:
    rows = [x for x in r["rows"] if x["value"]]
    if not rows:
        return f"No missing values on **{r['sheet']}** ({r['rows_considered']:,} rows checked)."
    lines = [f"Missing values on **{r['sheet']}** ({r['rows_considered']:,} rows checked):"]
    lines += [f"- {x['group'][0]}: **{x['value']}** ({x['pct']}%)" for x in rows]
    clean = len(r["rows"]) - len(rows)
    if clean:
        lines.append(f"{clean} other column(s) have no blanks.")
    return "\n".join(lines)


def _time_series(r: dict) -> str:
    lines = [f"Monthly {r['function']} of **{r['measure']}** on **{r['sheet']}** by {r['date_column']}:"]
    for g, pts in list(r["series"].items())[:4]:
        vals = ", ".join(f"{p['period']}: {fmt(p['value'], r)}" for p in pts)
        lines.append(f"- {g}: {vals}" if len(r["series"]) > 1 else f"- {vals}")
    return "\n".join(lines)


def _period_change(r: dict) -> str:
    lines = [f"Change in **{r['measure']}** by {', '.join(r['group_by'])}, {r['previous_period']} → {r['current_period']} (largest decline first):"]
    for row in r["rows"][:8]:
        pct = f" ({fmt(row['pct'], r, 'pct')})" if row.get("pct") is not None else ""
        lines.append(f"- {row['group'][0]}: {fmt(row['previous'], r)} → {fmt(row['current'], r)}, change **{fmt(row['value'], r)}**{pct}")
    return "\n".join(lines)


def _variance(r: dict) -> str:
    lines = [f"**{r['actual']}** vs **{r['budget']}** on **{r['sheet']}**" + (f" by {r['group_by'][0]}" if r["group_by"] else "") + ":"]
    for row in r["rows"]:
        pct = f" ({fmt(row['pct'], r, 'pct')})" if row.get("pct") is not None else ""
        status = "over" if (row["value"] or 0) > 0 else "under" if (row["value"] or 0) < 0 else "on"
        lines.append(f"- {row['group'][0]}: {fmt(row['actual'], r)} vs {fmt(row['budget'], r)} → **{fmt(row['value'], r)}** {status} budget{pct}")
    t = r["total"]
    lines.append(f"Overall: {fmt(t['actual'], r)} actual vs {fmt(t['budget'], r)} budget (difference {fmt(t['actual'] - t['budget'], r)}).")
    return "\n".join(lines)


def _correlation(r: dict) -> str:
    v = r["value"]
    strength = "strong" if abs(v) >= 0.7 else "moderate" if abs(v) >= 0.4 else "weak"
    direction = "positive" if v > 0 else "negative"
    return (f"Pearson correlation between **{r['x']}** and **{r['y']}** on {r['sheet']}: **{v}** ({strength} {direction} "
            f"association, n = {r['n']:,}). This shows association only, not that one causes the other.")


def _histogram(r: dict) -> str:
    peak = max(r["rows"], key=lambda x: x["value"])
    return (f"Distribution of **{r['measure']}** ({r['rows_considered']:,} numeric values, {len(r['rows'])} bins). "
            f"The most common range is {peak['group'][0]} with {peak['value']:,} values.")


def _duplicates(r: dict) -> str:
    if not r["groups"] and not r["repeated_identifiers"]:
        return f"No potential duplicates found on **{r['sheet']}** (compared {', '.join(r['compared_columns'])})."
    lines = [f"Potential duplicates on **{r['sheet']}** (candidates for review):"]
    for g in r["groups"][:8]:
        lines.append(f"- Rows {', '.join(map(str, g))} have identical values in {len(r['compared_columns'])} compared columns.")
    for rep in r["repeated_identifiers"][:5]:
        lines.append(f"- {rep['column']} value '{rep['value']}' appears in rows {', '.join(map(str, rep['rows']))}.")
    lines.append(f"Compared columns: {', '.join(r['compared_columns'])}. Identifier columns are excluded from the row comparison so re-keyed copies are caught.")
    return "\n".join(lines)


def _outliers(r: dict) -> str:
    if not r["candidates"]:
        return f"No unusual values found in **{r['column']}** ({r['method']})."
    lines = [f"Unusual **{r['column']}** values on {r['sheet']} — candidates for review, not confirmed errors:"]
    for c in r["candidates"][:8]:
        who = f"{c['id']} " if c.get("id") else ""
        lines.append(f"- {who}(row {c['row']}): **{fmt(c['value'], r)}**")
    lines.append(f"Method: {r['method']}; median {fmt(r['median'], r)}.")
    return "\n".join(lines)


def _explanation(r: dict) -> str:
    lines = [f"`{r['formula']}`", "", r["plain_english"] + "."]
    if r["references"]:
        lines.append("References: " + "; ".join(f"{x['ref']}" + (f" ({x['header']})" if x["header"] else "") + f" — {x['anchoring']}" for x in r["references"]))
    if r["functions"]:
        lines.append("Functions: " + "; ".join(f"{f['name']} {f['description']}" for f in r["functions"]))
    lines.append("Compatibility: " + " ".join(r["compatibility"]))
    return "\n".join(lines)


def _diagnosis(r: dict) -> str:
    if not r.get("has_formula"):
        return r["message"]
    if not r.get("error"):
        return f"{r['sheet']}!{r['cell']} (`{r['formula']}`) has no error. Saved result: {r['cached_value']}."
    lines = [f"{r['sheet']}!{r['cell']} shows **{r['error']}**: {r['meaning']}", f"Formula: `{r['formula']}`"]
    lines += [f"- {f}" for f in r["findings"]]
    if r.get("suggested_formula"):
        lines.append(f"Suggested fix: `{r['suggested_formula']}`. {r['fix_note']}")
    return "\n".join(lines)


def _consistency(r: dict) -> str:
    lines = [r["message"]]
    if r.get("dominant_pattern"):
        lines.append(f"Dominant pattern (written for the first data row): `{r['dominant_pattern']}`.")
    for x in r.get("inconsistent", [])[:6]:
        lines.append(f"- {x['cell']}: `{x['formula']}` (expected `{x['expected']}`)")
    if r.get("hardcoded_rows"):
        lines.append(f"Typed values instead of formulas in rows: {', '.join(map(str, r['hardcoded_rows'][:10]))}.")
    return "\n".join(lines)


def _rows(r: dict) -> str:
    return f"{r['match_count']:,} matching row(s) on **{r['sheet']}**; showing {len(r['rows'])}."


def _schema(r: dict) -> str:
    lines = ["Here is what's in this workbook:"]
    for s in r["sheets"]:
        hidden = " (hidden)" if s["state"] != "visible" else ""
        cols = ", ".join(c["name"] for c in s["columns"][:8])
        lines.append(f"- **{s['sheet']}**{hidden}: {s['rows']:,} rows — {cols}{'…' if len(s['columns']) > 8 else ''}")
    issues = r.get("issues", [])
    if issues:
        lines.append(f"I found {len(issues)} data-quality item(s); the most important:")
        for i in issues[:5]:
            lines.append(f"- {i['sheet']}: {i['message']}")
    return "\n".join(lines)


def _sheet_profile(r: dict) -> str:
    t = r.get("table") or {}
    lines = [f"**{r['name']}**: {t.get('row_count', 0):,} rows × {t.get('column_count', 0)} columns, {r['formula_cells']} formula cell(s)."]
    for i in r.get("issues", [])[:8]:
        lines.append(f"- {i['message']}")
    return "\n".join(lines)
