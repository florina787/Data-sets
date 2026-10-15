"""Registered tools. Inputs are pydantic models (typed + validated); outputs are JSON dicts.

Roles: workbook_analyst, formula_specialist, data_quality, visualization, validator.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..common import AppError
from ..services import operations as ops
from ..services import workbooks as W
from ..workbook import cleaning, formulas, query
from ..workbook.changes import build_set_formula, build_summary_sheet
from ..workbook.profile import compact_schema, profile_sheet
from ..workbook.quality import find_duplicates, outlier_candidates
from .runtime import RunContext, tool
from .viz import chart_from_result


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Empty(_In):
    pass


class SheetIn(_In):
    sheet: str = Field(..., max_length=64)


class RangeIn(_In):
    sheet: str = Field(..., max_length=64)
    range: str = Field(..., max_length=32, description="A1-style range such as B2:D20")


class Filter(_In):
    column: str = Field(..., max_length=128)
    op: Literal["eq", "neq", "gt", "gte", "lt", "lte", "contains", "in", "between", "not_blank", "is_blank"] = "eq"
    value: Any = None


class QueryIn(_In):
    sheet: str = Field(..., max_length=64)
    filters: list[Filter] = Field(default_factory=list, max_length=8)
    columns: list[str] = Field(default_factory=list, max_length=20)
    limit: int = Field(20, ge=1, le=50)


class AggregateIn(_In):
    sheet: str = Field(..., max_length=64)
    measure: str | None = Field(None, max_length=128)
    function: Literal["sum", "average", "count", "min", "max", "median", "distinct_count"] = "sum"
    group_by: list[str] = Field(default_factory=list, max_length=3)
    filters: list[Filter] = Field(default_factory=list, max_length=8)
    sort: Literal["asc", "desc"] = "desc"
    limit: int = Field(50, ge=1, le=200)


class TimeSeriesIn(_In):
    sheet: str
    date_column: str
    measure: str
    function: Literal["sum", "average", "count", "min", "max"] = "sum"
    group_by: str | None = None
    filters: list[Filter] = Field(default_factory=list, max_length=8)


class PeriodChangeIn(_In):
    sheet: str
    date_column: str
    measure: str
    group_by: str


class CompareIn(_In):
    sheet: str
    actual: str
    budget: str
    group_by: str | None = None


class TwoColIn(_In):
    sheet: str
    x: str
    y: str


class ColumnIn(_In):
    sheet: str
    column: str


class DuplicatesIn(_In):
    sheet: str
    key_columns: list[str] = Field(default_factory=list, max_length=6)


class CellIn(_In):
    sheet: str
    cell: str = Field(..., max_length=12)


class ExplainIn(_In):
    sheet: str = ""
    cell: str | None = Field(None, max_length=12)
    formula: str | None = Field(None, max_length=2000)


class FormulaSpec(_In):
    kind: Literal["ratio", "margin", "difference", "sum", "product", "conditional", "date_part", "lookup", "custom"]
    new_column: str | None = Field(None, max_length=60)
    numerator: str | None = None
    denominator: str | None = None
    as_percent: bool = True
    profit: str | None = None
    revenue: str | None = None
    cost: str | None = None
    a: str | None = None
    b: str | None = None
    column: str | None = None
    op: str | None = None
    threshold: float | None = None
    true_label: str | None = Field(None, max_length=40)
    false_label: str | None = Field(None, max_length=40)
    part: Literal["year", "month", "year_month"] | None = None
    key: str | None = None
    lookup_sheet: str | None = None
    lookup_key: str | None = None
    return_column: str | None = None
    template: str | None = Field(None, max_length=500, description="Custom formula using {Column Name} for same-row cells, e.g. ={Net Revenue}-{Cost}")


class ProposeFormulaIn(_In):
    sheet: str
    spec: FormulaSpec


class CleaningIn(_In):
    sheet: str
    action: Literal["trim_whitespace", "normalize_categories", "standardize_dates", "convert_numeric_text", "fill_missing",
                    "flag_duplicates", "remove_duplicates", "flag_outliers"]
    column: str | None = None
    columns: list[str] = Field(default_factory=list, max_length=20)
    day_first: bool | None = None
    fill_value: str | None = Field(None, max_length=60)
    mapping: dict[str, str] | None = None


class ReportIn(_In):
    title: str = Field("Report", max_length=60)
    result: dict
    chart_type: Literal["bar", "line", "none"] = "bar"


class ChartIn(_In):
    result: dict
    chart_type: Literal["auto", "bar", "line", "scatter", "histogram", "table"] = "auto"
    title: str | None = Field(None, max_length=100)


class RestoreIn(_In):
    version: int = Field(..., ge=1)


class OperationIn(_In):
    operation_id: str = Field(..., max_length=40)


# ----------------------------------------------------------------------- helpers
def _model(ctx: RunContext):
    return W.get_model(ctx.principal, ctx.workbook_id, ctx.version)


def _filters(fs: list[Filter]) -> list[dict]:
    return [f.model_dump() for f in fs]


def _propose(ctx: RunContext, change_set: dict, builder: dict) -> dict:
    change_set.setdefault("details", {})["builder"] = builder
    op = ops.propose(ctx.principal, ctx.workbook_id, ctx.version, change_set, run_id=ctx.run_id)
    return {"kind": "proposal", "operation": op}


# ----------------------------------------------------------------------- workbook analyst
@tool("inspect_workbook", "List sheets, detected tables, column names/types and the data-quality issue summary.", Empty, "read", "workbook_analyst")
def inspect_workbook(ctx: RunContext, args: Empty) -> dict:
    profile = W.get_profile(ctx.principal, ctx.workbook_id, ctx.version)
    return {"kind": "schema", **compact_schema(profile),
            "issues": [{k: i[k] for k in ("sheet", "column", "kind", "severity", "message")} for i in profile["issues"]]}


@tool("profile_sheet", "Detailed profile of one sheet: inferred types, missing values, formulas, errors and issues.", SheetIn, "read", "workbook_analyst")
def profile_sheet_tool(ctx: RunContext, args: SheetIn) -> dict:
    model = _model(ctx)
    sheet = model.resolve_sheet(args.sheet)
    if sheet is None:
        raise AppError("sheet_not_found", f"There is no sheet named '{args.sheet}'.", 404)
    return {"kind": "sheet_profile", **profile_sheet(model, sheet)}


@tool("read_range", "Read values and formulas from a small range (max 400 cells).", RangeIn, "read", "workbook_analyst")
def read_range(ctx: RunContext, args: RangeIn) -> dict:
    return query.read_range(_model(ctx), args.sheet, args.range)


@tool("query_table", "Return rows of a sheet table that match filters (max 50 rows).", QueryIn, "read", "workbook_analyst")
def query_table(ctx: RunContext, args: QueryIn) -> dict:
    model = _model(ctx)
    table = query.require_table(model, args.sheet)
    rows, described = query.apply_filters(table, _filters(args.filters))
    cols = [query.require_column(table, c) for c in args.columns] or table.columns
    from ..workbook.sources import make_source
    from ..workbook.values import json_safe

    return {
        "kind": "rows", "sheet": table.sheet, "columns": [c.name for c in cols], "match_count": len(rows),
        "rows": [{"row": r, "values": [json_safe(vals[table.col_pos(c)]) for c in cols]} for r, vals in rows[:args.limit]],
        "filters": described, "method": "Rows filtered by FloPilot's deterministic engine.",
        "sources": [make_source(model, table.sheet, table.range_ref())],
    }


@tool("calculate_aggregate", "Deterministic SUM/AVERAGE/COUNT/MIN/MAX/MEDIAN of a column, optionally grouped and filtered.", AggregateIn, "read", "workbook_analyst")
def calculate_aggregate(ctx: RunContext, args: AggregateIn) -> dict:
    return query.aggregate(_model(ctx), args.sheet, args.measure, args.function, args.group_by, _filters(args.filters), args.sort, args.limit)


@tool("time_series", "Aggregate a measure per calendar month of a date column (gaps shown as null).", TimeSeriesIn, "read", "workbook_analyst")
def time_series(ctx: RunContext, args: TimeSeriesIn) -> dict:
    return query.time_series(_model(ctx), args.sheet, args.date_column, args.measure, args.function, _filters(args.filters), args.group_by)


@tool("period_change", "Month-over-month change of a measure per group for the latest two months with data.", PeriodChangeIn, "read", "workbook_analyst")
def period_change(ctx: RunContext, args: PeriodChangeIn) -> dict:
    return query.period_change(_model(ctx), args.sheet, args.date_column, args.measure, args.group_by)


@tool("compare_measures", "Compare two numeric columns (e.g. actual vs budget) with variance and %.", CompareIn, "read", "workbook_analyst")
def compare_measures(ctx: RunContext, args: CompareIn) -> dict:
    return query.compare_measures(_model(ctx), args.sheet, args.actual, args.budget, args.group_by)


@tool("correlation", "Pearson correlation between two numeric columns (association, not causation).", TwoColIn, "read", "workbook_analyst")
def correlation(ctx: RunContext, args: TwoColIn) -> dict:
    return query.correlation(_model(ctx), args.sheet, args.x, args.y)


@tool("histogram", "Distribution of a numeric column in equal-width bins.", ColumnIn, "read", "visualization")
def histogram(ctx: RunContext, args: ColumnIn) -> dict:
    return query.histogram(_model(ctx), args.sheet, args.column)


@tool("missing_by_column", "Count blank cells per column of a sheet.", SheetIn, "read", "data_quality")
def missing_by_column(ctx: RunContext, args: SheetIn) -> dict:
    return query.missing_by_column(_model(ctx), args.sheet)


@tool("find_duplicates", "Find potential duplicate rows (optionally on key columns). Candidates for review.", DuplicatesIn, "read", "data_quality")
def find_duplicates_tool(ctx: RunContext, args: DuplicatesIn) -> dict:
    model = _model(ctx)
    table = query.require_table(model, args.sheet)
    keys = [query.require_column(table, k) for k in args.key_columns] or None
    result = find_duplicates(table, keys)
    from ..workbook.sources import make_source
    return {"kind": "duplicates", "sheet": table.sheet, **result, "rows": [{"group": g} for g in result["groups"]],
            "method": f"Rows whose normalised values match on {', '.join(result['compared_columns'])} (case, spacing and punctuation ignored).",
            "sources": [make_source(model, table.sheet, table.range_ref())]}


@tool("find_outliers", "Find unusually large/small values in a numeric column (candidates for review).", ColumnIn, "read", "data_quality")
def find_outliers(ctx: RunContext, args: ColumnIn) -> dict:
    model = _model(ctx)
    table = query.require_table(model, args.sheet)
    col = query.require_column(table, args.column)
    result = outlier_candidates(table, col)
    from ..workbook.sources import make_source
    from ..workbook.values import json_safe
    id_col = next((c for c in table.columns if c.semantic == "identifier"), None)
    lookup = dict(table.rows)
    for c in result["candidates"]:
        c["id"] = json_safe(lookup[c["row"]][table.col_pos(id_col)]) if id_col else None
        c["cell"] = f"{col.letter}{c['row']}"
    return {"kind": "outliers", "sheet": table.sheet, "column": col.name, **result, "semantic": col.semantic,
            "number_format": col.number_format, "id_column": id_col.name if id_col else None,
            "sources": [make_source(model, table.sheet, table.range_ref(col), col.name)]}


# ----------------------------------------------------------------------- formula specialist
@tool("explain_formula", "Explain a formula (from a cell or given text) in plain English with references and compatibility.", ExplainIn, "read", "formula_specialist")
def explain_formula(ctx: RunContext, args: ExplainIn) -> dict:
    model = _model(ctx)
    sheet = model.resolve_sheet(args.sheet) or ""
    formula = args.formula
    if args.cell:
        if not sheet:
            raise AppError("sheet_not_found", f"There is no sheet named '{args.sheet}'.", 404)
        raw, _ = model.cell(sheet, args.cell.upper())
        cell_obj = model.ws_f(sheet)[args.cell.upper()]
        if cell_obj.data_type != "f":
            raise AppError("no_formula", f"{sheet}!{args.cell.upper()} does not contain a formula.", 422)
        formula = str(getattr(raw, "text", raw))
    if not formula:
        raise AppError("no_formula", "Select a cell with a formula or provide the formula text.", 422)
    from ..workbook.sources import make_source
    result = formulas.explain_formula(formula, model, sheet, args.cell.upper() if args.cell else None)
    if args.cell:
        result["sources"] = [make_source(model, sheet, args.cell.upper())]
    return result


@tool("diagnose_formula", "Diagnose a formula error (#DIV/0!, #N/A, …) in a cell and suggest a fix.", CellIn, "read", "formula_specialist")
def diagnose_formula(ctx: RunContext, args: CellIn) -> dict:
    model = _model(ctx)
    result = formulas.diagnose_cell(model, args.sheet, args.cell)
    from ..workbook.sources import make_source
    result["sources"] = [make_source(model, result["sheet"], result["cell"])]
    return result


@tool("check_formula_consistency", "Check that a formula column uses the same pattern on every row.", ColumnIn, "read", "formula_specialist")
def check_consistency(ctx: RunContext, args: ColumnIn) -> dict:
    model = _model(ctx)
    result = formulas.consistency_check(model, args.sheet, args.column)
    table = query.require_table(model, args.sheet)
    from ..workbook.sources import make_source
    col = query.require_column(table, args.column)
    result["sources"] = [make_source(model, table.sheet, table.range_ref(col), col.name)]
    return result


@tool("propose_formula", "Propose a new formula column (header + per-row formula). Requires approval before it is inserted.", ProposeFormulaIn, "propose", "formula_specialist")
def propose_formula(ctx: RunContext, args: ProposeFormulaIn) -> dict:
    from ..workbook.changes import build_formula_column
    from ..workbook.evaluator import evaluate_formula

    model = _model(ctx)
    spec = args.spec.model_dump(exclude_none=True)
    proposal = formulas.build_formula_proposal(model, args.sheet, spec)

    def resolver(sheet: str, row: int, col: int):
        s = model.resolve_sheet(sheet)
        return model.ws_v(s).cell(row, col).value if s else "#REF!"

    previews, not_evaluated = {}, None
    for r in proposal["rows"]:
        value, reason = evaluate_formula(proposal["template"].replace("{r}", str(r)), proposal["sheet"], resolver)
        if reason:
            not_evaluated = reason
            break
        previews[r] = value
    proposal["preview_status"] = ("not_evaluated" if not_evaluated else "preview")
    proposal["preview_note"] = (f"Preview values not computed: {not_evaluated}." if not_evaluated else
                                "Preview values were computed by FloPilot's limited formula evaluator from saved cell values; "
                                "Excel recalculates the real results when the file is opened.")
    cs = build_formula_column(model, proposal, previews if not not_evaluated else {})
    return _propose(ctx, cs, {"name": "propose_formula", "args": args.model_dump(exclude_none=True)})


@tool("propose_formula_fix", "Propose replacing an erroring formula with a guarded version. Requires approval.", CellIn, "propose", "formula_specialist")
def propose_formula_fix(ctx: RunContext, args: CellIn) -> dict:
    model = _model(ctx)
    diag = formulas.diagnose_cell(model, args.sheet, args.cell)
    if not diag.get("suggested_formula"):
        raise AppError("nothing_to_change", f"{diag['sheet']}!{diag['cell']} has no error to fix.", 422)
    cs = build_set_formula(model, diag["sheet"], diag["cell"], diag["suggested_formula"],
                           f"Replace {diag['formula']} with {diag['suggested_formula']} so the cell shows blank instead of {diag['error']}.")
    cs["details"]["diagnosis"] = {k: diag[k] for k in ("error", "meaning", "findings", "fix_note")}
    return _propose(ctx, cs, {"name": "propose_formula_fix", "args": args.model_dump()})


# ----------------------------------------------------------------------- data-quality specialist
@tool("propose_cleaning", "Propose a cleaning operation (trim, normalize categories, standardize dates, convert text numbers, fill blanks, flag/remove duplicates, flag outliers). Requires approval.", CleaningIn, "propose", "data_quality")
def propose_cleaning(ctx: RunContext, args: CleaningIn) -> dict:
    model = _model(ctx)
    a = args.action
    if a == "trim_whitespace":
        cs = cleaning.trim_whitespace(model, args.sheet, args.columns or ([args.column] if args.column else None))
    elif a == "normalize_categories":
        cs = cleaning.normalize_categories(model, args.sheet, _need(args.column), args.mapping)
    elif a == "standardize_dates":
        cs = cleaning.standardize_dates(model, args.sheet, _need(args.column), args.day_first)
    elif a == "convert_numeric_text":
        cs = cleaning.convert_numeric_text(model, args.sheet, _need(args.column))
    elif a == "fill_missing":
        cs = cleaning.fill_missing(model, args.sheet, _need(args.column), args.fill_value or "Unknown")
    elif a in ("flag_duplicates", "remove_duplicates"):
        cs = cleaning.duplicates_change(model, args.sheet, a == "remove_duplicates", args.columns or None)
    else:
        cs = cleaning.flag_outliers(model, args.sheet, _need(args.column))
    return _propose(ctx, cs, {"name": "propose_cleaning", "args": args.model_dump(exclude_none=True)})


def _need(column: str | None) -> str:
    if not column:
        raise AppError("column_required", "This action needs a column.", 422)
    return column


# ----------------------------------------------------------------------- visualization specialist
@tool("create_chart", "Build a validated chart specification (shown in FloPilot; not embedded in the workbook).", ChartIn, "read", "visualization")
def create_chart(ctx: RunContext, args: ChartIn) -> dict:
    return chart_from_result(args.result, args.chart_type, args.title)


@tool("propose_report_sheet", "Propose a new report sheet with a summary table and a native Excel chart. Requires approval.", ReportIn, "propose", "visualization")
def propose_report_sheet(ctx: RunContext, args: ReportIn) -> dict:
    model = _model(ctx)
    result = args.result
    chart = None
    if args.chart_type != "none":
        y = result.get("measure") or result.get("actual") or "Value"
        chart = {"type": args.chart_type, "title": args.title, "y_title": y,
                 "x_title": ", ".join(result.get("group_by") or []) or ("Month" if result.get("kind") == "time_series" else "")}
    cs = build_summary_sheet(model, result, args.title, chart)
    return _propose(ctx, cs, {"name": "propose_report_sheet", "args": {"title": args.title, "chart_type": args.chart_type}})


# ----------------------------------------------------------------------- validator / versions
@tool("preview_changes", "Show the stored preview (diff, flags, dry-run validation) for a proposed operation.", OperationIn, "read", "validator")
def preview_changes(ctx: RunContext, args: OperationIn) -> dict:
    return {"kind": "operation", "operation": ops.get_operation(ctx.principal, args.operation_id)}


@tool("validate_workbook", "Check that the current version reopens and summarise its formula errors.", Empty, "read", "validator")
def validate_workbook(ctx: RunContext, args: Empty) -> dict:
    profile = W.get_profile(ctx.principal, ctx.workbook_id, ctx.version)
    errors = [e for s in profile["sheets"] for e in s["error_cells"]]
    return {"kind": "validation", "version": ctx.version, "reopens": True, "formula_errors": errors[:20],
            "issue_counts": profile["issue_counts"]}


@tool("propose_restore", "Propose restoring an earlier version (creates a new version; history is kept). Requires approval.", RestoreIn, "propose", "validator")
def propose_restore(ctx: RunContext, args: RestoreIn) -> dict:
    cs = ops.restore_change_set(ctx.principal, ctx.workbook_id, args.version)
    return _propose(ctx, cs, {"name": "propose_restore", "args": args.model_dump()})


# ----------------------------------------------------------------------- user-only tools (policy-blocked for the model)
@tool("apply_approved_changes", "Apply an operation a person approved. User-only.", OperationIn, "mutate", "validator")
def apply_approved_changes(ctx: RunContext, args: OperationIn) -> dict:  # pragma: no cover - API path is used instead
    raise AppError("tool_not_allowed", "Changes are applied only through the approval endpoint.", 403)


@tool("export_workbook", "Export a workbook version. User-only.", Empty, "export", "validator")
def export_workbook(ctx: RunContext, args: Empty) -> dict:  # pragma: no cover
    raise AppError("tool_not_allowed", "Exports are started by a person from the interface.", 403)


@tool("restore_version", "Apply a version restore. User-only.", RestoreIn, "restore", "validator")
def restore_version(ctx: RunContext, args: RestoreIn) -> dict:  # pragma: no cover
    raise AppError("tool_not_allowed", "Restores are applied only through the approval endpoint.", 403)


