"""Validation gates run on every candidate version before it can be published."""
from __future__ import annotations

import io
import math
from typing import Any

import openpyxl

from . import values as V
from .changes import decode, encode
from .fidelity import compare_packages


def _snapshot(wb) -> dict[str, dict[str, Any]]:
    snap = {}
    for ws in wb.worksheets:
        cells = {}
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is None:
                    continue
                v = cell.value
                cells[cell.coordinate] = ("f", str(getattr(v, "text", v))) if cell.data_type == "f" else ("v", encode(v)["value"])
        snap[ws.title] = cells
    return snap


def _features(ws) -> dict:
    return {
        "freeze_panes": ws.freeze_panes,
        "merged": sorted(str(r) for r in ws.merged_cells.ranges),
        "auto_filter": bool(ws.auto_filter and ws.auto_filter.ref),
        "tables": sorted(ws.tables.keys()),
        "data_validations": len(ws.data_validations.dataValidation) if ws.data_validations else 0,
        "conditional_formats": len(list(ws.conditional_formatting)),
        "widths": {k: d.width for k, d in ws.column_dimensions.items() if d.width},
    }


def validate_candidate(base: bytes, candidate: bytes, cs: dict, acknowledged_risks: bool = False) -> dict:
    checks: list[dict] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    try:
        wb_a = openpyxl.load_workbook(io.BytesIO(base))
        wb_b = openpyxl.load_workbook(io.BytesIO(candidate))
        check("reopens", True, "The new version opens successfully.")
    except Exception as exc:  # pragma: no cover - defensive
        check("reopens", False, f"The new version could not be reopened ({type(exc).__name__}).")
        return {"passed": False, "checks": checks}

    names_a, names_b = wb_a.sheetnames, wb_b.sheetnames
    added = [n for n in names_b if n not in names_a]
    removed = [n for n in names_a if n not in names_b]
    expected_added = [cs["new_sheet"]["name"]] if cs.get("new_sheet") else []
    check("no_sheet_removed", not removed, "No sheets were removed." if not removed else f"Sheets removed: {removed}.")
    check("sheet_order", [n for n in names_b if n in names_a] == names_a and added == expected_added,
          "Sheet names and order are preserved" + (f"; added '{added[0]}' as planned." if added else "."))

    snap_a, snap_b = _snapshot(wb_a), _snapshot(wb_b)
    expected = {(c["sheet"], c["cell"]) for c in cs["changes"]}
    deleting = cs.get("structural") and cs["structural"].get("delete_rows")
    unexpected: list[str] = []
    formula_overwrites: list[str] = []
    for sheet in names_a:
        if deleting and sheet == cs["sheet"]:
            continue
        a, b = snap_a.get(sheet, {}), snap_b.get(sheet, {})
        for coord in set(a) | set(b):
            if a.get(coord) != b.get(coord) and (sheet, coord) not in expected:
                unexpected.append(f"{sheet}!{coord}")
                if a.get(coord, ("", ""))[0] == "f":
                    formula_overwrites.append(f"{sheet}!{coord}")
    planned_formula_replacements = {(c["sheet"], c["cell"]) for c in cs["changes"] if c["before"]["formula"]}
    check("only_planned_cells_changed", not unexpected,
          f"Exactly the {len(expected)} planned cell(s) changed." if not unexpected else f"Unplanned changes: {', '.join(unexpected[:10])}.")
    check("no_unexpected_formula_overwrites", not formula_overwrites,
          f"No formulas were overwritten except {len(planned_formula_replacements)} planned replacement(s)." if not formula_overwrites
          else f"Unplanned formula overwrites: {', '.join(formula_overwrites[:10])}.")

    # every planned change landed as described
    mismatched = []
    for c in cs["changes"]:
        got = snap_b.get(c["sheet"], {}).get(c["cell"])
        if c["after"].get("formula"):
            want = ("f", c["after"]["formula"])
        elif c["after"]["type"] == "blank":
            want = None
        else:
            want = ("v", encode(decode(c["after"]))["value"])
        if got != want:
            mismatched.append(f"{c['sheet']}!{c['cell']}")
    check("changes_applied_exactly", not mismatched,
          "Every planned change is present." if not mismatched else f"Changes not applied as planned: {', '.join(mismatched[:10])}.")

    if deleting:
        _validate_deletion(wb_a, wb_b, cs, check)
    _reconcile_totals(wb_a, wb_b, cs, check)

    for sheet in names_a:
        if sheet in names_b:
            fa, fb = _features(wb_a[sheet]), _features(wb_b[sheet])
            fb_widths = {k: v for k, v in fb.pop("widths").items() if k in fa["widths"]}
            fa_widths = fa.pop("widths")
            same = fa == fb and fa_widths == fb_widths
            check(f"features_preserved:{sheet}", same,
                  f"Frozen panes, merged cells, filters, tables, validation, conditional formats and widths intact on '{sheet}'." if same
                  else f"Feature differences on '{sheet}': before={fa}, after={fb}.")

    fidelity = compare_packages(base, candidate)
    lost = fidelity["lost"]
    lost_ok = not lost or acknowledged_risks
    check("package_fidelity", lost_ok,
          "No workbook features were lost." if not lost else
          (f"Features reduced: {', '.join(lost)} (acknowledged by approver)." if acknowledged_risks
           else f"Features would be lost: {', '.join(lost)}. Explicit acknowledgement is required."))
    return {"passed": all(c["passed"] for c in checks), "checks": checks, "fidelity": fidelity}


def _validate_deletion(wb_a, wb_b, cs: dict, check) -> None:
    ws_a, ws_b = wb_a[cs["sheet"]], wb_b[cs["sheet"]]
    deleted = set(cs["structural"]["delete_rows"])
    rows_a = [tuple(c.value for c in row) for i, row in enumerate(ws_a.iter_rows(), start=1) if i not in deleted]
    rows_b = [tuple(c.value for c in row) for row in ws_b.iter_rows()]
    width = max((len(r) for r in rows_a), default=0)
    norm = lambda rows: [tuple(list(r) + [None] * (width - len(r)))[:width] for r in rows]  # noqa: E731
    a, b = norm(rows_a), norm(rows_b)
    while b and all(v is None for v in b[-1]):
        b.pop()
    while a and all(v is None for v in a[-1]):
        a.pop()
    check("rows_deleted_exactly", a == b and ws_a.max_row - ws_b.max_row == len(deleted),
          f"Exactly {len(deleted)} row(s) removed; all other rows kept in order." if a == b else "Remaining rows do not match the plan.")


def _reconcile_totals(wb_a, wb_b, cs: dict, check) -> None:
    """Numeric totals per column must move exactly by the planned deltas."""
    sheet = cs.get("sheet")
    if not sheet or sheet not in wb_a.sheetnames or sheet not in wb_b.sheetnames:
        return
    ws_a, ws_b = wb_a[sheet], wb_b[sheet]

    def totals(ws) -> dict[int, float]:
        t: dict[int, float] = {}
        for row in ws.iter_rows():
            for cell in row:
                if cell.data_type != "f" and V.is_number(cell.value):
                    t[cell.column] = t.get(cell.column, 0.0) + float(cell.value)
        return t

    ta, tb = totals(ws_a), totals(ws_b)
    from openpyxl.utils.cell import column_index_from_string, coordinate_from_string

    expected = dict(ta)
    for c in cs["changes"]:
        if c["sheet"] != sheet:
            continue
        col = column_index_from_string(coordinate_from_string(c["cell"])[0])
        before = c["before"]["value"] if c["before"]["formula"] is None and c["before"]["type"] == "number" else 0.0
        after = c["after"]["value"] if not c["after"].get("formula") and c["after"]["type"] == "number" else 0.0
        expected[col] = expected.get(col, 0.0) - float(before) + float(after)
    if cs.get("structural") and cs["structural"].get("delete_rows"):
        for removed in cs["structural"]["removed"]:
            for offset, enc in enumerate(removed["values"]):
                if enc["type"] == "number":
                    # removed values are recorded relative to the table's first column
                    col = _first_table_col(ws_a, cs) + offset
                    expected[col] = expected.get(col, 0.0) - float(enc["value"])
    diffs = [col for col in set(expected) | set(tb)
             if not math.isclose(expected.get(col, 0.0), tb.get(col, 0.0), rel_tol=1e-9, abs_tol=1e-6)]
    check("totals_reconcile", not diffs,
          "Numeric column totals changed only by the planned amounts." if not diffs
          else f"Unexpected total changes in column(s) {diffs}.")


def _first_table_col(ws, cs: dict) -> int:
    header_row = cs["structural"].get("header_row", 1)
    for cell in ws[header_row]:
        if cell.value not in (None, ""):
            return cell.column
    return 1
