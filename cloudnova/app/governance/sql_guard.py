"""Structural SQL validation (specs/query_interface.md §3). Not a keyword blacklist: the statement is
parsed with sqlglot and walked; anything that is not a read-only SELECT over allow-listed tables and
known columns is rejected. The executor adds database-level read-only + no external access on top.
"""
from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp

from ..errors import AppError

ALLOWED_TABLES = {"invoices", "accounts", "monthly_revenue", "dq_issues", "dedup_conflicts"}
_FORBIDDEN_NODES = tuple(t for t in (
    getattr(exp, n, None) for n in ("Insert", "Update", "Delete", "Drop", "Create", "Alter", "Command", "Copy",
                                    "Attach", "Detach", "Pragma", "Set", "Use", "Merge", "TruncateTable",
                                    "Install", "Load", "Export", "Transaction", "Commit", "Rollback")) if t is not None)


@dataclass
class GuardResult:
    sql: str
    tables: set[str]


def check_sql(sql: str, schema: dict[str, set[str]]) -> GuardResult:
    """Validate `sql` against `schema` ({table: {columns}}). Raises AppError('sql_rejected')."""
    def reject(reason: str):
        raise AppError("sql_rejected", f"Query rejected: {reason}.", 422, details={"reason": reason})

    text = (sql or "").strip().rstrip(";").strip()
    if not text:
        reject("empty query")
    try:
        statements = [s for s in sqlglot.parse(text, read="duckdb") if s is not None]
    except sqlglot.errors.ParseError:
        reject("not valid SQL")
    if len(statements) != 1:
        reject("exactly one statement is allowed")
    tree = statements[0]
    if not isinstance(tree, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        reject(f"only SELECT queries are allowed (got {tree.key.upper()})")
    for node in tree.walk():
        if isinstance(node, _FORBIDDEN_NODES):
            reject(f"{node.key.upper()} is not allowed")
        if isinstance(node, (exp.Anonymous,)) and node.name.lower().startswith(("read_", "glob", "query", "sniff")):
            reject(f"function {node.name} is not allowed")
        if isinstance(node, exp.Func) and type(node).__name__.lower().startswith(("read", "glob")):
            reject(f"function {node.sql()[:30]} is not allowed")
    ctes = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    tables: set[str] = set()
    for t in tree.find_all(exp.Table):
        if t.args.get("db") or t.args.get("catalog"):
            reject("schema-qualified tables are not allowed")
        if not isinstance(t.this, exp.Identifier):
            reject("table functions are not allowed")
        name = t.name.lower()
        if name in ctes:
            continue
        if name not in ALLOWED_TABLES:
            reject(f"table '{t.name}' is not allowed")
        tables.add(name)
    # column validation: every bare column must exist in some referenced table, or be a select alias / CTE column
    known = set().union(*(schema.get(t, set()) for t in tables)) if tables else set()
    aliases = {a.alias.lower() for a in tree.find_all(exp.Alias)}
    if ctes:
        return GuardResult(text, tables)  # CTE outputs are derived; columns inside CTEs were still parsed
    for col in tree.find_all(exp.Column):
        name = col.name.lower()
        if name == "*" or name in aliases:
            continue
        if name not in known:
            reject(f"unknown column '{col.name}'")
    return GuardResult(text, tables)
