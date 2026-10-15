"""Visualization specialist: turns deterministic results into validated chart specifications.

Charts produced here are rendered by the FloPilot web app only (`web_only: true`). Embedding a
native chart in the workbook is a separate, approval-gated operation (propose_report_sheet).
"""
from __future__ import annotations


from ..common import AppError

MAX_CATEGORIES = 12


def _unit(result: dict) -> str | None:
    fmt = result.get("number_format") or ""
    if result.get("semantic") == "percentage" or "%" in fmt:
        return "%"
    for sym, name in (("$", "USD ($)"), ("€", "EUR (€)"), ("£", "GBP (£)")):
        if sym in fmt:
            return name
    if result.get("semantic") == "currency":
        return "currency (unit not specified in the workbook)"
    return None


def chart_from_result(result: dict, chart_type: str = "auto", title: str | None = None) -> dict:
    kind = result.get("kind")
    notes: list[str] = []
    filters = result.get("filters") or []
    sources = result.get("sources") or []
    unit = _unit(result)
    if kind in ("aggregate", "missing", "histogram", "period_change"):
        rows = [r for r in result["rows"] if r.get("value") is not None]
        if kind == "aggregate" and not result.get("group_by"):
            raise AppError("not_chartable", "A single total cannot be charted; group it by a category or date first.", 422)
        if len(rows) > MAX_CATEGORIES and kind == "aggregate":
            head, tail = rows[:MAX_CATEGORIES - 1], rows[MAX_CATEGORIES - 1:]
            if result.get("function") in ("sum", "count"):
                rows = head + [{"group": ["Other"], "value": sum(r["value"] for r in tail)}]
                notes.append(f"{len(tail)} smaller categories combined into 'Other'.")
            else:
                rows = head
                notes.append(f"Showing the top {len(head)} of {len(head) + len(tail)} categories.")
        ctype = "histogram" if kind == "histogram" else ("bar" if chart_type == "auto" else chart_type)
        label_y = {"missing": "Missing cells", "histogram": "Rows", "period_change": f"Change in {result.get('measure')}"}.get(
            kind, f"{(result.get('function') or 'sum').title()} of {result.get('measure') or 'rows'}")
        label_x = ", ".join(result.get("group_by") or []) or {"missing": "Column", "histogram": result.get("measure")}.get(kind, "")
        series = [{"name": label_y, "points": [{"x": " / ".join(map(str, r["group"])), "y": r["value"]} for r in rows]}]
        default_title = {"missing": f"Missing values by column — {result.get('sheet')}",
                         "histogram": f"Distribution of {result.get('measure')}",
                         "period_change": f"{result.get('measure')} change {result.get('previous_period')} → {result.get('current_period')}"}.get(
            kind, f"{label_y} by {label_x}")
    elif kind == "time_series":
        ctype = "line" if chart_type in ("auto", "line") else chart_type
        series = [{"name": g, "points": [{"x": p["period"], "y": p["value"]} for p in pts]} for g, pts in result["series"].items()]
        if len(series) > 8:
            series = sorted(series, key=lambda s: -sum(p["y"] or 0 for p in s["points"]))[:8]
            notes.append("Showing the 8 largest series.")
        if any(p["y"] is None for s in series for p in s["points"]):
            notes.append("Months without data are shown as gaps, not zero.")
        label_y = f"{result['function'].title()} of {result['measure']}"
        label_x = f"Month ({result['date_column']})"
        default_title = f"{result['measure']} trend by month"
        if result.get("undated_rows"):
            notes.append(f"{result['undated_rows']} row(s) without a real date are excluded.")
    elif kind == "variance":
        ctype = "bar"
        series = [{"name": result["actual"], "points": [{"x": r["group"][0], "y": r["actual"]} for r in result["rows"]]},
                  {"name": result["budget"], "points": [{"x": r["group"][0], "y": r["budget"]} for r in result["rows"]]}]
        label_y, label_x = "Amount", ", ".join(result["group_by"]) or ""
        default_title = f"{result['actual']} vs {result['budget']}"
    elif kind == "correlation":
        ctype = "scatter"
        series = [{"name": f"{result['y']} vs {result['x']}", "points": result["points"]}]
        label_x, label_y = result["x"], result["y"]
        default_title = f"{result['y']} vs {result['x']} (r = {result['value']})"
        notes.append("Association only; this does not show causation.")
    elif kind == "outliers":
        ctype = "table"
        series = [{"name": "Candidates", "points": [{"x": c.get("id") or f"Row {c['row']}", "y": c["value"]} for c in result["candidates"]]}]
        label_x, label_y = "Record", result["column"]
        default_title = f"Unusual {result['column']} values (for review)"
    else:
        raise AppError("not_chartable", "This result cannot be charted.", 422)
    points = sum(len(s["points"]) for s in series)
    if points == 0:
        raise AppError("not_chartable", "There is no data to chart.", 422)
    return {
        "kind": "chart", "schema_version": "1.0", "type": ctype, "title": title or default_title,
        "x_label": label_x, "y_label": label_y + (f" ({unit})" if unit and ctype != "histogram" else ""), "unit": unit,
        "series": series, "filters": filters, "sources": sources, "notes": notes + list(result.get("warnings") or []),
        "web_only": True, "embedded_in_workbook": False, "result_kind": kind,
    }
