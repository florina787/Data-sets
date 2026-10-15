"""Windowed cell access for the virtualized spreadsheet preview."""
from __future__ import annotations

from openpyxl.utils import get_column_letter

from ..common import AppError
from . import values as V
from .model import WorkbookModel

MAX_WINDOW_ROWS = 500
MAX_WINDOW_COLS = 120


def _color(c) -> str | None:
    try:
        rgb = c.rgb if c is not None and c.type == "rgb" else None
    except Exception:
        return None
    if isinstance(rgb, str) and len(rgb) == 8 and rgb not in ("00000000", "FF000000"):
        return "#" + rgb[2:]
    return None


def window(model: WorkbookModel, sheet: str, r0: int, r1: int, c0: int, c1: int) -> dict:
    resolved = model.resolve_sheet(sheet)
    if resolved is None:
        raise AppError("sheet_not_found", f"There is no sheet named '{sheet}'.", 404)
    ws_f, ws_v = model.ws_f(resolved), model.ws_v(resolved)
    max_row, max_col = max(ws_f.max_row or 1, 1), max(ws_f.max_column or 1, 1)
    r0, c0 = max(1, r0), max(1, c0)
    r1 = min(r1, r0 + MAX_WINDOW_ROWS - 1, max_row)
    c1 = min(c1, c0 + MAX_WINDOW_COLS - 1, max_col)
    rows = []
    if r1 >= r0 and c1 >= c0:
        for r_idx, (row_f, row_v) in enumerate(zip(ws_f.iter_rows(min_row=r0, max_row=r1, min_col=c0, max_col=c1),
                                                   ws_v.iter_rows(min_row=r0, max_row=r1, min_col=c0, max_col=c1))):
            cells = []
            for cf, cv in zip(row_f, row_v):
                if cf.value is None and not cf.has_style:
                    continue
                is_formula = cf.data_type == "f"
                value = cv.value if is_formula else cf.value
                entry = {"c": cf.column, "v": V.format_display(value, cf.number_format), "t": V.classify(value)}
                if value is not None:
                    entry["raw"] = V.json_safe(value)
                if is_formula:
                    entry["f"] = str(getattr(cf.value, "text", cf.value))
                    if cv.value is None:
                        entry["uncalculated"] = True
                if cf.has_style:
                    style = {}
                    if cf.font is not None:
                        if cf.font.b:
                            style["b"] = 1
                        if cf.font.i:
                            style["i"] = 1
                        col = _color(cf.font.color)
                        if col:
                            style["color"] = col
                    if cf.fill is not None and cf.fill.fill_type == "solid":
                        bg = _color(cf.fill.fgColor)
                        if bg:
                            style["bg"] = bg
                    if cf.alignment is not None and cf.alignment.horizontal:
                        style["align"] = cf.alignment.horizontal
                    if cf.number_format and cf.number_format != "General":
                        style["fmt"] = cf.number_format
                    if style:
                        entry["s"] = style
                cells.append(entry)
            rows.append({"r": r0 + r_idx, "cells": cells})
    widths = {}
    for c in range(c0, c1 + 1):
        letter = get_column_letter(c)
        dim = ws_f.column_dimensions.get(letter)
        if dim is not None and dim.width:
            widths[letter] = round(dim.width * 7 + 5)
    hidden_rows = [r for r, d in ws_f.row_dimensions.items() if d.hidden and r0 <= r <= r1]
    return {
        "sheet": resolved, "version": model.version, "max_row": max_row, "max_col": max_col,
        "r0": r0, "r1": r1, "c0": c0, "c1": c1, "rows": rows, "col_widths": widths,
        "freeze_panes": ws_f.freeze_panes, "merged": [str(m) for m in ws_f.merged_cells.ranges][:200],
        "hidden_rows": hidden_rows, "state": ws_f.sheet_state,
    }


def find_rows(model: WorkbookModel, sheet: str, text: str, limit: int = 200) -> dict:
    """Rows whose displayed values contain `text` (case-insensitive), plus the frozen header rows."""
    resolved = model.resolve_sheet(sheet)
    if resolved is None:
        raise AppError("sheet_not_found", f"There is no sheet named '{sheet}'.", 404)
    needle = text.strip().lower()
    if not needle:
        raise AppError("empty_query", "Type something to find.", 422)
    ws_f = model.ws_f(resolved)
    max_col = min(ws_f.max_column or 1, MAX_WINDOW_COLS)
    table = model.table(resolved)
    header_row = table.header_row if table else 1
    matches: list[int] = []
    for r in range(header_row + 1, (ws_f.max_row or 1) + 1):
        win = window(model, resolved, r, r, 1, max_col)
        if any(needle in c["v"].lower() for row in win["rows"] for c in row["cells"]):
            matches.append(r)
            if len(matches) >= limit:
                break
    rows = []
    for r in [header_row] + matches:
        rows += window(model, resolved, r, r, 1, max_col)["rows"]
    return {"sheet": resolved, "query": text, "match_count": len(matches), "truncated": len(matches) >= limit, "rows": rows}
