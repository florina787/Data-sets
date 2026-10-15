"""Stable source references for grounded answers.

A source names a workbook version, sheet, range and (for column ranges) the header text. The
id is a hash of those fields, so it is stable across requests. After a structural edit the
coordinates are revalidated against the header: if the column moved the source is relocated,
if it disappeared the source is marked stale.
"""
from __future__ import annotations

from openpyxl.utils.cell import range_boundaries

from ..common import stable_hash
from .model import WorkbookModel


def make_source(model: WorkbookModel, sheet: str, range_ref: str, header: str | None = None,
                label: str | None = None) -> dict:
    payload = {"workbook_id": model.workbook_id, "version": model.version, "sheet": sheet, "range": range_ref, "header": header}
    return {
        "id": "src_" + stable_hash(payload)[:12],
        **payload,
        "label": label or (f"{sheet}!{range_ref}" + (f" ({header})" if header else "")),
        "status": "current",
    }


def revalidate(sources: list[dict], model: WorkbookModel) -> list[dict]:
    out = []
    for src in sources:
        updated = dict(src)
        sheet = model.resolve_sheet(src["sheet"])
        if sheet is None:
            updated["status"] = "stale"
            updated["note"] = f"Sheet '{src['sheet']}' no longer exists."
            out.append(updated)
            continue
        table = model.table(sheet)
        header = src.get("header")
        if header and table is not None:
            col = table.column(header)
            if col is None:
                updated["status"] = "stale"
                updated["note"] = f"Column '{header}' is no longer present."
            else:
                min_col, _, max_col, _ = range_boundaries(src["range"])
                new_range = table.range_ref(col)
                if min_col != col.index or new_range != src["range"]:
                    updated["range"] = new_range
                    updated["status"] = "relocated"
                    updated["note"] = f"Column '{header}' now at {new_range}."
        updated["version"] = model.version
        updated["id"] = "src_" + stable_hash({k: updated[k] for k in ("workbook_id", "version", "sheet", "range", "header")})[:12]
        out.append(updated)
    return out
