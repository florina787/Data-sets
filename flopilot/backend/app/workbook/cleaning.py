"""Data-quality specialist: turns detected issues into concrete change sets (never applied here)."""
from __future__ import annotations

import re
from datetime import datetime

from ..common import AppError
from . import values as V
from .changes import build_delete_rows, build_flag_column, make_change_set, value_change
from .model import WorkbookModel
from .quality import category_variants, date_format_mix, find_duplicates, outlier_candidates
from .query import require_column, require_table


def trim_whitespace(model: WorkbookModel, sheet: str, columns: list[str] | None = None) -> dict:
    table = require_table(model, sheet)
    cols = [require_column(table, c) for c in columns] if columns else [c for c in table.columns if c.inferred_type in ("text", "mixed (text)")]
    changes = []
    for col in cols:
        pos = table.col_pos(col)
        for r, vals in table.rows:
            v = vals[pos]
            if (r, col.index) in table.formulas or not isinstance(v, str):
                continue
            cleaned = re.sub(r"\s+", " ", v).strip()
            if cleaned != v:
                changes.append(value_change(model, table.sheet, f"{col.letter}{r}", cleaned or None))
    if not changes:
        raise AppError("nothing_to_change", "No extra spaces were found in the selected columns.", 422)
    return make_change_set("trim_whitespace", f"Trim extra spaces ({len(changes)} cells)",
                           f"Remove leading, trailing and repeated spaces in {', '.join(c.name for c in cols)}.",
                           table.sheet, changes, ", ".join(table.range_ref(c) for c in cols))


def normalize_categories(model: WorkbookModel, sheet: str, column: str, mapping: dict[str, str] | None = None) -> dict:
    table = require_table(model, sheet)
    col = require_column(table, column)
    if mapping is None:
        groups = category_variants(table, col)
        mapping = {variant: g["canonical"] for g in groups for variant in g["variants"]}
    mapping = {k: v for k, v in mapping.items() if k != v}
    if not mapping:
        raise AppError("nothing_to_change", f"No spelling variants were found in '{col.name}'.", 422)
    pos = table.col_pos(col)
    changes = []
    for r, vals in table.rows:
        v = vals[pos]
        if isinstance(v, str) and (r, col.index) not in table.formulas:
            target = mapping.get(v) or mapping.get(v.strip())
            if target is not None and target != v:
                changes.append(value_change(model, table.sheet, f"{col.letter}{r}", target))
    if not changes:
        raise AppError("nothing_to_change", f"No values in '{col.name}' matched the mapping.", 422)
    readable = "; ".join(f"'{k}' → '{v}'" for k, v in list(mapping.items())[:8])
    return make_change_set("normalize_categories", f"Normalize {col.name} spelling ({len(changes)} cells)",
                           f"Replace spelling variants in {col.name}: {readable}.", table.sheet, changes, table.range_ref(col),
                           details={"mapping": mapping},
                           warnings=["Review each mapping: similar spellings are not always the same category."])


def standardize_dates(model: WorkbookModel, sheet: str, column: str, day_first: bool | None = None) -> dict:
    table = require_table(model, sheet)
    col = require_column(table, column)
    mix = date_format_mix(table, col)
    if day_first is None and mix["inferred_order"]:
        day_first = mix["inferred_order"] == "DMY"
        inferred_note = f"Day/month order inferred as {'day-first' if day_first else 'month-first'} from unambiguous values in the column."
    else:
        inferred_note = None
    pos = table.col_pos(col)
    changes, ambiguous, unparsed = [], [], []
    for r, vals in table.rows:
        v = vals[pos]
        if not isinstance(v, str) or (r, col.index) in table.formulas or V.is_blank(v):
            continue
        parsed, is_ambiguous = V.parse_date_text(v, day_first)
        if parsed is None:
            unparsed.append(f"{col.letter}{r}")
            continue
        if is_ambiguous:
            ambiguous.append(f"{col.letter}{r}")
        changes.append(value_change(model, table.sheet, f"{col.letter}{r}", datetime(parsed.year, parsed.month, parsed.day), "yyyy-mm-dd"))
    if ambiguous and day_first is None:
        raise AppError("ambiguous_date_order",
                       f"{len(ambiguous)} date(s) in '{col.name}' such as {ambiguous[0]} could be day-first or month-first. "
                       "Tell FloPilot which order the data uses.", 422,
                       {"cells": ambiguous[:20], "column": col.name, "sheet": table.sheet,
                        "choices": ["day-first (DD/MM/YYYY)", "month-first (MM/DD/YYYY)"]})
    if not changes:
        raise AppError("nothing_to_change", f"All dates in '{col.name}' are already stored as real dates.", 422)
    warnings = []
    if unparsed:
        warnings.append(f"{len(unparsed)} value(s) could not be read as dates and are left unchanged: {', '.join(unparsed[:5])}.")
    if inferred_note:
        warnings.append(inferred_note)
    return make_change_set("standardize_dates", f"Standardize {col.name} dates ({len(changes)} cells)",
                           f"Convert text dates in {col.name} to real Excel dates formatted yyyy-mm-dd.", table.sheet, changes,
                           table.range_ref(col), warnings=warnings,
                           details={"day_first": day_first, "formats_found": mix["kinds"]})


def convert_numeric_text(model: WorkbookModel, sheet: str, column: str) -> dict:
    table = require_table(model, sheet)
    col = require_column(table, column)
    pos = table.col_pos(col)
    changes = []
    for r, vals in table.rows:
        v = vals[pos]
        if isinstance(v, str) and (r, col.index) not in table.formulas and V.classify(v) == "numeric_text":
            changes.append(value_change(model, table.sheet, f"{col.letter}{r}", V.parse_numeric_text(v), col.number_format))
    if not changes:
        raise AppError("nothing_to_change", f"No numbers stored as text were found in '{col.name}'.", 422)
    return make_change_set("convert_numeric_text", f"Convert {len(changes)} text number(s) in {col.name}",
                           f"Turn numbers stored as text in {col.name} into real numbers so totals include them.",
                           table.sheet, changes, table.range_ref(col))


def fill_missing(model: WorkbookModel, sheet: str, column: str, value: str = "Unknown") -> dict:
    table = require_table(model, sheet)
    col = require_column(table, column)
    pos = table.col_pos(col)
    if col.semantic in ("currency", "numeric", "percentage"):
        raise AppError("unsafe_fill", f"'{col.name}' is numeric. Filling blanks with a value would change totals and averages; FloPilot will not do this automatically.", 422)
    changes = [value_change(model, table.sheet, f"{col.letter}{r}", value)
               for r, vals in table.rows if V.is_blank(vals[pos]) and (r, col.index) not in table.formulas]
    if not changes:
        raise AppError("nothing_to_change", f"'{col.name}' has no blank cells.", 422)
    return make_change_set("fill_missing", f"Fill {len(changes)} blank(s) in {col.name}",
                           f"Write '{value}' into blank cells of {col.name}.", table.sheet, changes, table.range_ref(col))


def duplicates_change(model: WorkbookModel, sheet: str, remove: bool, key_columns: list[str] | None = None) -> dict:
    table = require_table(model, sheet)
    keys = [require_column(table, k) for k in key_columns] if key_columns else None
    dups = find_duplicates(table, keys)
    if not dups["groups"]:
        raise AppError("nothing_to_change", f"No potential duplicate rows were found on {table.sheet}.", 422)
    extra = {r: f"Possible duplicate of row {g[0]}" for g in dups["groups"] for r in g[1:]}
    reason = (f"Rows matching another row on {', '.join(dups['compared_columns'])}. The first occurrence in each group is kept.")
    if remove:
        return build_delete_rows(model, table, list(extra), reason)
    return build_flag_column(model, table, "Duplicate Check", extra, reason + " Rows are only labelled, nothing is removed.")


def flag_outliers(model: WorkbookModel, sheet: str, column: str) -> dict:
    table = require_table(model, sheet)
    col = require_column(table, column)
    out = outlier_candidates(table, col)
    if not out["candidates"]:
        raise AppError("nothing_to_change", f"No unusual values were found in '{col.name}'.", 422)
    flags = {c["row"]: "Review: unusual value" for c in out["candidates"]}
    return build_flag_column(model, table, f"{col.name} Review", flags, f"Label values flagged by the {out['method']}.")
