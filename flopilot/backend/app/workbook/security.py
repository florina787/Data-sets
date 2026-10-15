"""Untrusted-content handling: formula-injection protection and instruction-like text detection."""
from __future__ import annotations

import csv
import io
import re
from typing import Any

from . import values as V
from .model import WorkbookModel

_INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
_INSTRUCTION_LIKE = re.compile(
    r"ignore (all |any )?(previous|prior|above) (instructions|rules)|system override|you are now|"
    r"(reveal|print|show|send) (me |us )?(your |the )?(api[ _-]?key|password|secret|system prompt)|"
    r"disregard (the )?(rules|policy)|act as (an? )?(admin|administrator)|developer mode", re.I)


def neutralize_csv_text(value: Any) -> Any:
    """Prefix text that a spreadsheet would execute as a formula. Numbers are left alone."""
    if isinstance(value, str) and value.startswith(_INJECTION_PREFIXES):
        return "'" + value
    return value


def sheet_to_csv(model: WorkbookModel, sheet: str) -> str:
    ws = model.ws_v(sheet)
    out = io.StringIO()
    writer = csv.writer(out)
    for row in ws.iter_rows(values_only=True):
        writer.writerow([neutralize_csv_text(V.json_safe(v)) if v is not None else "" for v in row])
    return out.getvalue()


def find_instruction_like_text(model: WorkbookModel, limit: int = 20) -> list[dict]:
    hits = []
    for sheet in model.sheet_names:
        ws = model.ws_f(sheet)
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.data_type != "f" and _INSTRUCTION_LIKE.search(cell.value):
                    hits.append({"sheet": sheet, "cell": cell.coordinate, "hidden_sheet": ws.sheet_state != "visible"})
                    if len(hits) >= limit:
                        return hits
    return hits
