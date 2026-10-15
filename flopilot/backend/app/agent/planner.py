"""Deterministic request planner ("demo mode" supervisor).

Maps a plain-English request onto a bounded plan of registered tool calls using the workbook
schema. It never computes numbers itself. When a request is ambiguous (e.g. "revenue" could be
Gross or Net Revenue) it returns a clarification instead of guessing. When an LLM provider is
configured, requests this planner cannot classify are handed to the LLM agent.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..workbook import values as V
from ..workbook.model import Column, SheetTable, WorkbookModel
from ..workbook.query import match_columns

NUMERIC_SEMANTICS = {"currency", "numeric", "percentage"}
MEASURE_TERMS = ["net revenue", "gross revenue", "revenue", "sales", "profit", "cost", "costs", "spend", "spending", "expenses",
                 "expense", "amount", "units", "quantity", "price", "budget", "margin", "discount", "value", "stock value", "on hand"]
TERM_ALIASES = {"sales": "revenue", "costs": "cost", "spending": "amount", "spend": "amount", "expenses": "amount", "expense": "amount"}
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]


@dataclass
class Plan:
    intent: str
    role: str
    steps: list[dict] = field(default_factory=list)
    clarification: dict | None = None
    assumptions: list[str] = field(default_factory=list)
    follow_ups: list[dict] = field(default_factory=list)
    message: str | None = None
    sheet: str | None = None

    def to_dict(self) -> dict:
        return {"intent": self.intent, "role": self.role, "steps": [{"tool": s["tool"], **({"args": s.get("args")} if s.get("args") else {}),
                **({"from_step": s["from_step"]} if "from_step" in s else {})} for s in self.steps],
                "assumptions": self.assumptions, "clarification": bool(self.clarification), "sheet": self.sheet}


class Ambiguous(Exception):
    def __init__(self, term: str, sheet: str, options: list[Column]):
        self.term, self.sheet, self.options = term, sheet, options


class Planner:
    def __init__(self, model: WorkbookModel, context: dict):
        self.model = model
        self.context = context

    # ------------------------------------------------------------------ helpers
    def tables(self) -> list[SheetTable]:
        out = []
        for s in self.model.sheet_names:
            if self.model.ws_f(s).sheet_state != "visible":
                continue
            t = self.model.table(s)
            if t is not None:
                out.append(t)
        return out

    def sheet_in(self, q: str) -> SheetTable | None:
        # A sheet named after "to/on/in/into" is the target ("add Segment from Customers to Sales").
        for s in self.model.sheet_names:
            if re.search(rf"\b(?:to|on|in|into)\s+(?:the\s+)?{re.escape(s.lower())}(?![\w])", q):
                return self.model.table(s)
        for s in sorted(self.model.sheet_names, key=len, reverse=True):
            if re.search(rf"(?<![\w]){re.escape(s.lower())}(?![\w])", q):
                return self.model.table(s)
        return None

    def default_table(self, q: str, prefer: list[str] | None = None) -> SheetTable | None:
        explicit = self.sheet_in(q)
        if explicit is not None:
            return explicit
        tables = self.tables()
        if prefer:
            scored = []
            for t in tables:
                score = sum(1 for term in prefer if match_columns(t, term))
                scored.append((score, t))
            scored.sort(key=lambda x: -x[0])
            if scored and scored[0][0] > 0:
                if not self.active_table() or scored[0][0] > sum(1 for term in prefer if match_columns(self.active_table(), term)):
                    return scored[0][1]
        active = self.active_table()
        return active or (tables[0] if tables else None)

    def active_table(self) -> SheetTable | None:
        sel = self.context.get("selection") or {}
        sheet = self.model.resolve_sheet(sel.get("sheet") or "")
        return self.model.table(sheet) if sheet else None

    def mentioned_columns(self, table: SheetTable, q: str) -> list[tuple[int, Column]]:
        found: list[tuple[int, Column]] = []
        taken: list[tuple[int, int]] = []
        for col in sorted(table.columns, key=lambda c: -len(c.name)):
            for m in re.finditer(rf"(?<![\w]){re.escape(col.name.lower())}s?(?![\w])", q):
                if not any(a <= m.start() < b for a, b in taken):
                    found.append((m.start(), col))
                    taken.append((m.start(), m.end()))
                    break
        return sorted(found, key=lambda x: x[0])

    def rule_for(self, term: str, table: SheetTable) -> Column | None:
        for rule in self.context.get("business_rules", []):
            if rule["term"] == term and rule["sheet"] == table.sheet:
                return table.column(rule["column"])
        return None

    def resolve_term(self, table: SheetTable, term: str, numeric: bool = True) -> Column | None:
        term = TERM_ALIASES.get(term, term)
        ruled = self.rule_for(term, table)
        if ruled:
            return ruled
        candidates = match_columns(table, term)
        if numeric:
            candidates = [c for c in candidates if c.semantic in NUMERIC_SEMANTICS or "number" in c.inferred_type]
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            raise Ambiguous(term, table.sheet, candidates)
        return None

    def measure(self, table: SheetTable, q: str, exclude: list[Column] | None = None) -> Column | None:
        exclude = exclude or []
        for _, col in self.mentioned_columns(table, q):
            if col not in exclude and (col.semantic in NUMERIC_SEMANTICS or "number" in col.inferred_type):
                return col
        for term in MEASURE_TERMS:
            if re.search(rf"\b{re.escape(term)}\b", q):
                col = self.resolve_term(table, term)
                if col and col not in exclude:
                    return col
        return None

    def group_by(self, table: SheetTable, q: str) -> list[Column]:
        m = re.search(r"\b(?:by|per|for each|across|split by|broken down by)\s+([a-z][\w\s/-]*?)(?=\s+(?:and|for|in|where|on|with|from|during|over|of|using|sorted)\b|[?.,!]|$)", q)
        if not m:
            return []
        phrase = m.group(1).strip()
        cols = []
        for part in re.split(r"\s+and\s+|,", phrase):
            part = part.strip()
            if not part or part in ("month", "months", "monthly"):
                continue
            hits = [c for _, c in self.mentioned_columns(table, part)] or match_columns(table, part)
            if hits:
                cols.append(hits[0])
        return cols

    def date_column(self, table: SheetTable, q: str) -> Column | None:
        for _, col in self.mentioned_columns(table, q):
            if col.semantic == "date":
                return col
        return next((c for c in table.columns if c.semantic == "date"), None)

    def value_filters(self, table: SheetTable, q: str, exclude: list[Column]) -> list[dict]:
        filters = []
        for col in table.columns:
            if col in exclude or col.semantic != "category":
                continue
            counts: dict[str, int] = {}
            for v in table.values(col):
                if isinstance(v, str) and len(v.strip()) >= 3:
                    counts[v.strip()] = counts.get(v.strip(), 0) + 1
            # longest first (so "North America" wins over "America"), most common spelling first
            for v in sorted(counts, key=lambda x: (-len(x), -counts[x])):
                if v.lower() == col.name.lower():
                    continue
                if re.search(rf"\b(?:in|for|from|of|where|only)\s+(?:the\s+)?{re.escape(v.lower())}\b", q):
                    filters.append({"column": col.name, "op": "eq", "value": v})
                    break
        month = re.search(rf"\b(?:in|during|for)\s+({'|'.join(MONTHS)})(?:\s+(\d{{4}}))?\b", q)
        if month:
            dcol = self.date_column(table, q)
            if dcol:
                mi = MONTHS.index(month.group(1)) + 1
                years = sorted({v.year for v in table.values(dcol) if hasattr(v, "year")})
                year = int(month.group(2)) if month.group(2) else (years[-1] if years else 2025)
                end_day = 31 if mi in (1, 3, 5, 7, 8, 10, 12) else 30 if mi != 2 else 29 if year % 4 == 0 else 28
                filters.append({"column": dcol.name, "op": "between", "value": [f"{year}-{mi:02d}-01", f"{year}-{mi:02d}-{end_day}"]})
        return filters

    def cell_ref(self, q_original: str) -> tuple[str | None, str | None]:
        m = re.search(r"(?:'([^']+)'|([A-Za-z][\w ]*?))!\$?([A-Za-z]{1,3})\$?(\d+)", q_original)
        if m:
            sheet = (m.group(1) or m.group(2)).strip()
            sheet = sheet.split()[-1] if self.model.resolve_sheet(sheet) is None else sheet
            return self.model.resolve_sheet(sheet), f"{m.group(3).upper()}{m.group(4)}"
        m = re.search(r"\b(?:cell\s+)?\$?([A-Z]{1,3})\$?(\d{1,7})\b", q_original)
        sel = self.context.get("selection") or {}
        if m:
            table = self.sheet_in(q_original.lower())
            return (table.sheet if table else self.model.resolve_sheet(sel.get("sheet") or "")), f"{m.group(1)}{m.group(2)}"
        if sel.get("sheet") and sel.get("cell"):
            return self.model.resolve_sheet(sel["sheet"]), sel["cell"]
        return None, None

    def clarify(self, intent: str, question: str, options: list[dict], original: str, term: str | None = None,
                sheet: str | None = None) -> Plan:
        return Plan(intent, "supervisor", clarification={"question": question, "options": options, "original": original,
                                                         "term": term, "sheet": sheet})

    # ------------------------------------------------------------------ main entry
    def plan(self, message: str) -> Plan | None:
        q = " ".join(message.lower().split())
        try:
            return self._plan(q, message)
        except Ambiguous as amb:
            names = [c.name for c in amb.options]
            return self.clarify("clarify_column", f"'{amb.term}' could mean {', '.join(names[:-1])} or {names[-1]} on {amb.sheet}. Which one should I use?",
                                [{"label": n, "prompt": f"Use {n} for {amb.term}", "column": n} for n in names], message, amb.term, amb.sheet)

    def _plan(self, q: str, original: str) -> Plan | None:
        # ---------------------------------------------------------- clarification answers
        pending = self.context.get("pending_clarification")
        if pending and pending.get("term"):
            m = re.match(r"^(?:use\s+)?(.+?)(?:\s+for\s+.+)?$", q)
            choice = m.group(1).strip() if m else q
            sheet = self.model.resolve_sheet(pending["sheet"])
            table = self.model.table(sheet) if sheet else None
            if table is not None:
                col = table.column(choice) or next((c for c in table.columns if c.name.lower() == choice), None)
                if col is not None:
                    return Plan("resolve_clarification", "supervisor", message=pending["original"],
                                assumptions=[f"'{pending['term']}' means {col.name} on {table.sheet} (confirmed by you)."],
                                steps=[{"tool": "_remember_rule", "args": {"term": pending["term"], "sheet": table.sheet, "column": col.name}}])

        # ---------------------------------------------------------- explicit business rule ("use Net Revenue for revenue")
        m = re.match(r"^(?:use|treat|take)\s+(.+?)\s+(?:for|as)\s+(?:the\s+)?([a-z][a-z ]{1,30}?)\.?$", q)
        if m:
            for table in self.tables():
                col = table.column(m.group(1).strip())
                if col is not None:
                    term = TERM_ALIASES.get(m.group(2).strip(), m.group(2).strip())
                    return Plan("set_business_rule", "supervisor",
                                message=f"Got it — on {table.sheet}, '{term}' now means {col.name} for this conversation.",
                                steps=[{"tool": "_remember_rule", "args": {"term": term, "sheet": table.sheet, "column": col.name}}])

        # ---------------------------------------------------------- restore / undo
        if re.search(r"\b(restore|roll ?back|revert|undo)\b", q):
            m = re.search(r"version\s*(\d+)|\bv(\d+)\b", q)
            target = int(m.group(1) or m.group(2)) if m else self.model.version - 1
            if target < 1 or target >= self.model.version:
                return Plan("restore", "validator", message=f"There is no earlier version to restore (current version is {self.model.version}).")
            return Plan("restore", "validator", steps=[{"tool": "propose_restore", "args": {"version": target}}])

        # ---------------------------------------------------------- report sheet from last result
        if re.search(r"\b(add|put|insert|embed|save)\b.*\b(chart|report|summary|table)\b.*\b(workbook|sheet|excel|file)\b|\bcreate (a )?report sheet\b", q):
            last = self.context.get("last_result")
            if not last or last.get("kind") not in ("aggregate", "time_series", "variance", "period_change") or last.get("stale"):
                return Plan("report", "visualization", message="Ask for a summary or chart first (for example “Summarize net revenue by region”), then ask me to add it to the workbook.")
            ctype = "line" if last.get("kind") == "time_series" else "bar"
            title = f"{last.get('measure') or last.get('actual') or 'Summary'} report"[:31]
            return Plan("report", "visualization", steps=[{"tool": "propose_report_sheet", "args": {"title": title, "result": last, "chart_type": ctype}}])

        # ---------------------------------------------------------- formulas
        if re.search(r"\bexplain\b.*\bformula\b|\bwhat does (this|the|that) formula\b|\bexplain (this|that|the) cell\b", q):
            sheet, cell = self.cell_ref(original)
            if not cell:
                return Plan("explain_formula", "formula_specialist", message="Select a cell that contains a formula (or name it, e.g. “Explain the formula in Expenses!H2”), then ask again.")
            return Plan("explain_formula", "formula_specialist", sheet=sheet, steps=[{"tool": "explain_formula", "args": {"sheet": sheet or "", "cell": cell}}])

        if re.search(r"#div|#n/a|#ref|#value|#name|formula error|error in|diagnos|why does .* show|broken formula", q):
            sheet, cell = self.cell_ref(original)
            if not cell:
                errs = [(s, e) for s in self.model.sheet_names for e in _errors(self.model, s)]
                if not errs:
                    return Plan("diagnose_formula", "formula_specialist", message="I didn't find any formula errors in the saved results of this workbook.")
                sheet, cell = errs[0][0], errs[0][1]
            steps = [{"tool": "diagnose_formula", "args": {"sheet": sheet or "", "cell": cell}}]
            if re.search(r"\bfix\b|\brepair\b|\bcorrect\b", q):
                steps.append({"tool": "propose_formula_fix", "args": {"sheet": sheet or "", "cell": cell}})
            return Plan("diagnose_formula", "formula_specialist", sheet=sheet, steps=steps,
                        follow_ups=[] if len(steps) > 1 else [{"label": "Propose a fix", "prompt": f"Fix the formula error in {sheet}!{cell}"}])

        if re.search(r"consisten", q):
            table = self.default_table(q)
            cols = [c for _, c in self.mentioned_columns(table, q)] if table else []
            col = cols[0] if cols else next((c for c in (table.columns if table else []) if any(k[1] == c.index for k in table.formulas)), None)
            if table is None or col is None:
                return Plan("consistency", "formula_specialist", message="Name a column with formulas, e.g. “Check formula consistency in Profit on Sales”.")
            return Plan("consistency", "formula_specialist", sheet=table.sheet, steps=[{"tool": "check_formula_consistency", "args": {"sheet": table.sheet, "column": col.name}}])

        if re.search(r"\b(add|create|insert|calculate|build|make|generate|write)\b.*\b(column|formula|field)\b|\b(add|calculate)\b.*\bmargin\b"
                     r"|\b(add|bring|pull|look ?up)\b.+\bfrom\s+(?:the\s+)?\w+.*\b(?:to|into|on)\b", q):
            return self._formula_plan(q, original)

        # ---------------------------------------------------------- cleaning
        if re.search(r"duplicate|dupes|double[- ]entered", q):
            table = self.default_table(q, prefer=["invoice"] if "invoice" in q else None)
            if table is None:
                return None
            assumptions = []
            if "invoice" in q and not match_columns(table, "invoice"):
                ident = next((c.name for c in table.columns if c.semantic == "identifier"), "each row")
                assumptions.append(f"No column is named 'invoice'; each row on {table.sheet} (identified by {ident}) is treated as one record.")
            keys = [c.name for _, c in self.mentioned_columns(table, q) if " on " in q or "using" in q]
            if re.search(r"\b(remove|delete|drop|eliminate)\b", q):
                return Plan("remove_duplicates", "data_quality", sheet=table.sheet, assumptions=assumptions,
                            steps=[{"tool": "propose_cleaning", "args": {"sheet": table.sheet, "action": "remove_duplicates", "columns": keys}}])
            if re.search(r"\b(flag|mark|label|highlight|tag)\b", q):
                return Plan("flag_duplicates", "data_quality", sheet=table.sheet, assumptions=assumptions,
                            steps=[{"tool": "propose_cleaning", "args": {"sheet": table.sheet, "action": "flag_duplicates", "columns": keys}}])
            return Plan("find_duplicates", "data_quality", sheet=table.sheet, assumptions=assumptions,
                        steps=[{"tool": "find_duplicates", "args": {"sheet": table.sheet, "key_columns": keys}}],
                        follow_ups=[{"label": "Flag them in a new column", "prompt": f"Flag the duplicates on {table.sheet}"},
                                    {"label": "Remove the extra copies", "prompt": f"Remove the duplicates on {table.sheet}"}])

        if re.search(r"\b(clean|tidy|fix (the )?data|fix (this|the) sheet)\b", q):
            table = self.default_table(q)
            if table is None:
                return None
            return Plan("clean_sheet", "data_quality", sheet=table.sheet, steps=[{"tool": "_clean_sheet", "args": {"sheet": table.sheet}}])

        if re.search(r"\bdates?\b", q) and re.search(r"standardi[sz]e|normali[sz]e|fix|convert|clean|consistent", q):
            table = self.default_table(q, prefer=["date"])
            col = self.date_column(table, q) if table else None
            if col is None:
                return Plan("standardize_dates", "data_quality", message="I couldn't find a date column on that sheet.")
            day_first = True if re.search(r"day[- ]first|dd/mm|european", q) else False if re.search(r"month[- ]first|mm/dd|us format|american", q) else None
            return Plan("standardize_dates", "data_quality", sheet=table.sheet,
                        steps=[{"tool": "propose_cleaning", "args": {"sheet": table.sheet, "action": "standardize_dates", "column": col.name, "day_first": day_first}}])

        if re.search(r"trim|whitespace|extra spaces", q):
            table = self.default_table(q)
            cols = [c.name for _, c in self.mentioned_columns(table, q)] if table else []
            return Plan("trim", "data_quality", sheet=table.sheet if table else None,
                        steps=[{"tool": "propose_cleaning", "args": {"sheet": table.sheet, "action": "trim_whitespace", "columns": cols}}] if table else [])

        if re.search(r"(normali[sz]e|standardi[sz]e|unify|consolidate|fix)\b.*\b(categor|spelling|names|values|labels|region|department|segment)", q):
            table = self.default_table(q)
            if table is None:
                return None
            cols = [c for _, c in self.mentioned_columns(table, q) if c.semantic == "category"]
            if not cols:
                from ..workbook.quality import category_variants
                cols = [c for c in table.columns if c.semantic == "category" and category_variants(table, c)]
            if not cols:
                return Plan("normalize_categories", "data_quality", message=f"I didn't find spelling variants on {table.sheet}.")
            return Plan("normalize_categories", "data_quality", sheet=table.sheet,
                        steps=[{"tool": "propose_cleaning", "args": {"sheet": table.sheet, "action": "normalize_categories", "column": cols[0].name}}])

        if re.search(r"(numbers? stored as text|text numbers|convert .*to numbers?)", q):
            table = self.default_table(q)
            cols = [c for _, c in self.mentioned_columns(table, q)] if table else []
            col = cols[0] if cols else next((c for c in table.columns if c.inferred_type == "mixed (number)"), None) if table else None
            if col is None:
                return Plan("convert_numeric_text", "data_quality", message="Name the column to convert.")
            return Plan("convert_numeric_text", "data_quality", sheet=table.sheet,
                        steps=[{"tool": "propose_cleaning", "args": {"sheet": table.sheet, "action": "convert_numeric_text", "column": col.name}}])

        if re.search(r"\bfill\b.*\b(blank|missing|empty)", q):
            table = self.default_table(q)
            cols = [c for _, c in self.mentioned_columns(table, q)] if table else []
            if not cols:
                return Plan("fill_missing", "data_quality", message="Name the column whose blanks should be filled, e.g. “Fill missing Segment on Customers with Unknown”.")
            m = re.search(r"\bwith\s+[\"']?([\w -]{1,40}?)[\"']?\s*$", original.strip(), re.I)
            return Plan("fill_missing", "data_quality", sheet=table.sheet,
                        steps=[{"tool": "propose_cleaning", "args": {"sheet": table.sheet, "action": "fill_missing", "column": cols[0].name,
                                                                     "fill_value": m.group(1).strip() if m else "Unknown"}}])

        if re.search(r"\bmissing\b|\bblanks?\b|\bempty (cells|values)\b|\bnulls?\b", q):
            table = self.default_table(q)
            if table is None:
                return None
            return Plan("missing_values", "data_quality", sheet=table.sheet, steps=[{"tool": "missing_by_column", "args": {"sheet": table.sheet}}],
                        follow_ups=[{"label": "Chart it", "prompt": f"Chart missing values on {table.sheet}"}])

        if re.search(r"unusual|outlier|anomal|abnormal|suspicious|unusually|extreme", q):
            table = self.default_table(q, prefer=["revenue", "amount"])
            if table is None:
                return None
            col = self.measure(table, q)
            if col is None and re.search(r"transaction|order|sale|invoice|deal", q):
                col = self.resolve_term(table, "revenue") or self.resolve_term(table, "amount")
            if col is None:
                return Plan("outliers", "data_quality", message="Name the numeric column to check.")
            if re.search(r"\b(flag|mark|label)\b", q):
                return Plan("flag_outliers", "data_quality", sheet=table.sheet,
                            steps=[{"tool": "propose_cleaning", "args": {"sheet": table.sheet, "action": "flag_outliers", "column": col.name}}])
            return Plan("outliers", "data_quality", sheet=table.sheet, steps=[{"tool": "find_outliers", "args": {"sheet": table.sheet, "column": col.name}}],
                        follow_ups=[{"label": "Flag them for review", "prompt": f"Flag unusual {col.name} on {table.sheet}"}])

        # ---------------------------------------------------------- analytics
        if re.search(r"\bbudget\b|\bactual\b", q):
            table = self.default_table(q, prefer=["budget"])
            if table is None or not match_columns(table, "budget"):
                return Plan("variance", "workbook_analyst", message="I couldn't find a Budget column to compare against.")
            budget = match_columns(table, "budget")[0]
            actual_hits = [c for c in match_columns(table, "actual") if c != budget]
            assumptions = []
            if actual_hits:
                actual = actual_hits[0]
            else:
                actual = next((c for c in table.columns if c.semantic == "currency" and c != budget), None)
                if actual is None:
                    return Plan("variance", "workbook_analyst", message="I couldn't find a column with actual amounts.")
                assumptions.append(f"No 'Actual' column exists; {actual.name} is used as actual spending.")
            groups = self.group_by(table, q)
            group = groups[0] if groups else next((c for c in table.columns if c.semantic == "category"), None)
            if not groups and group is not None:
                assumptions.append(f"Grouped by {group.name} (no grouping was specified).")
            return Plan("variance", "workbook_analyst", sheet=table.sheet, assumptions=assumptions,
                        steps=[{"tool": "compare_measures", "args": {"sheet": table.sheet, "actual": actual.name, "budget": budget.name,
                                                                     "group_by": group.name if group else None}},
                               {"tool": "create_chart", "from_step": 0, "args": {"chart_type": "bar"}}],
                        follow_ups=[{"label": "Add to workbook as a report", "prompt": "Add this summary to the workbook as a report sheet"}])

        if re.search(r"month[- ]over[- ]month|\bmom\b|declin|decreas|drop|fell|biggest (fall|loss)|growth|grew|increas", q):
            table = self.default_table(q, prefer=["date", "revenue"])
            if table is None:
                return None
            dcol = self.date_column(table, q)
            groups = self.group_by(table, q) or [c for _, c in self.mentioned_columns(table, q) if c.semantic == "category"]
            if not groups:
                for word in ("product", "region", "category", "department", "customer"):
                    if word in q:
                        groups = match_columns(table, word)[:1]
                        break
            meas = self.measure(table, q, exclude=groups)
            if meas is None:
                meas = self.resolve_term(table, "revenue")
            if dcol is None or meas is None or not groups:
                return Plan("period_change", "workbook_analyst", message="I need a date column, a measure and a grouping (e.g. “Which products had the largest month-over-month decline in net revenue?”).")
            return Plan("period_change", "workbook_analyst", sheet=table.sheet,
                        steps=[{"tool": "period_change", "args": {"sheet": table.sheet, "date_column": dcol.name, "measure": meas.name, "group_by": groups[0].name}},
                               {"tool": "create_chart", "from_step": 0, "args": {"chart_type": "bar"}}])

        if re.search(r"correlat|relationship between|\bvs\.?\b|versus|scatter", q):
            table = self.default_table(q)
            cols = [c for _, c in self.mentioned_columns(table, q) if c.semantic in NUMERIC_SEMANTICS] if table else []
            if len(cols) < 2:
                return Plan("correlation", "workbook_analyst", message="Name two numeric columns, e.g. “Correlation between Units and Discount on Sales”.")
            return Plan("correlation", "workbook_analyst", sheet=table.sheet,
                        steps=[{"tool": "correlation", "args": {"sheet": table.sheet, "x": cols[0].name, "y": cols[1].name}},
                               {"tool": "create_chart", "from_step": 0, "args": {"chart_type": "scatter"}}])

        if re.search(r"histogram|distribution|spread of", q):
            table = self.default_table(q)
            col = self.measure(table, q) if table else None
            if col is None:
                return Plan("histogram", "visualization", message="Name a numeric column to show its distribution.")
            return Plan("histogram", "visualization", sheet=table.sheet,
                        steps=[{"tool": "histogram", "args": {"sheet": table.sheet, "column": col.name}},
                               {"tool": "create_chart", "from_step": 0, "args": {"chart_type": "histogram"}}])

        wants_chart = bool(re.search(r"\bchart|graph|plot|visuali[sz]e|trend\b", q))
        if re.search(r"\btrend|over time|by month|monthly|per month|each month\b", q):
            table = self.default_table(q, prefer=["date"])
            if table is None:
                return None
            dcol = self.date_column(table, q)
            meas = self.measure(table, q)
            if dcol is None or meas is None:
                return Plan("time_series", "visualization", message="Name a measure and make sure the sheet has a date column, e.g. “Create a net revenue trend chart”.")
            groups = self.group_by(table, q)
            filters = self.value_filters(table, q, groups)
            return Plan("time_series", "visualization", sheet=table.sheet,
                        steps=[{"tool": "time_series", "args": {"sheet": table.sheet, "date_column": dcol.name, "measure": meas.name,
                                                                "group_by": groups[0].name if groups else None, "filters": filters}},
                               {"tool": "create_chart", "from_step": 0, "args": {"chart_type": "line"}}],
                        follow_ups=[{"label": "Add chart to workbook", "prompt": "Add this chart to the workbook as a report sheet"}])

        func = None
        if re.search(r"\b(average|avg|mean)\b", q):
            func = "average"
        elif re.search(r"\bmedian\b", q):
            func = "median"
        elif re.search(r"\b(max|maximum|highest|largest|biggest)\b", q) and not re.search(r"\bby\b|\btop\b", q):
            func = "max"
        elif re.search(r"\b(min|minimum|lowest|smallest)\b", q) and not re.search(r"\bby\b", q):
            func = "min"
        elif re.search(r"\bhow many\b|\bcount\b|\bnumber of\b", q):
            func = "count"
        elif re.search(r"\b(total|sum|summari[sz]e|summary|breakdown|break down|top \d+|by)\b", q) or wants_chart:
            func = "sum"
        if func:
            table = self.default_table(q, prefer=[t for t in MEASURE_TERMS if t in q][:2])
            if table is None:
                return None
            groups = self.group_by(table, q)
            meas = None if func == "count" else self.measure(table, q, exclude=groups)
            if func != "count" and meas is None:
                if re.search(r"summari[sz]e (this|the) (workbook|sheet|data)", q):
                    return Plan("overview", "workbook_analyst", steps=[{"tool": "inspect_workbook", "args": {}}])
                return Plan("aggregate", "workbook_analyst", message=f"Which column should I {func}? Columns on {table.sheet}: "
                            + ", ".join(c.name for c in table.columns if c.semantic in NUMERIC_SEMANTICS) + ".")
            filters = self.value_filters(table, q, groups)
            top = re.search(r"\btop (\d+)\b", q)
            steps = [{"tool": "calculate_aggregate", "args": {"sheet": table.sheet, "measure": meas.name if meas else None, "function": func,
                                                              "group_by": [g.name for g in groups], "filters": filters,
                                                              "limit": int(top.group(1)) if top else 50}}]
            if groups:
                steps.append({"tool": "create_chart", "from_step": 0, "args": {"chart_type": "bar"}})
            return Plan("aggregate", "workbook_analyst", sheet=table.sheet, steps=steps,
                        follow_ups=[{"label": "Add to workbook as a report", "prompt": "Add this summary to the workbook as a report sheet"}] if groups else [])

        if re.search(r"overview|what('?s| is) in|describe|data quality|issues|problems|explore|inspect", q):
            return Plan("overview", "workbook_analyst", steps=[{"tool": "inspect_workbook", "args": {}}])
        return None

    # ------------------------------------------------------------------ formula proposals
    def _formula_plan(self, q: str, original: str) -> Plan:
        table = self.default_table(q, prefer=["profit", "revenue"] if "margin" in q else None)
        if table is None:
            return Plan("propose_formula", "formula_specialist", message="Open a sheet with a table first.")
        name_m = re.search(r"(?:called|named)\s+[\"']?([\w %/-]{1,40})[\"']?", original, re.I)
        new_name = name_m.group(1).strip() if name_m else None
        spec: dict[str, Any] | None = None
        assumptions: list[str] = []
        if "margin" in q:
            profit = table.column("Profit") or next((c for c in table.columns if "profit" in c.name.lower()), None)
            revenue_like = [c for _, c in self.mentioned_columns(table, q) if re.search(r"revenue|sales|turnover", c.name.lower())]
            revenue = revenue_like[0] if revenue_like else self.resolve_term(table, "revenue")
            if revenue is None:
                return Plan("propose_formula", "formula_specialist", message=f"I couldn't find a revenue column on {table.sheet}.")
            if profit is not None:
                spec = {"kind": "margin", "profit": profit.name, "revenue": revenue.name}
            else:
                cost = self.resolve_term(table, "cost")
                if cost is None:
                    return Plan("propose_formula", "formula_specialist", message="I need a Profit column, or Revenue and Cost columns, to calculate margin.")
                spec = {"kind": "margin", "revenue": revenue.name, "cost": cost.name}
            spec["new_column"] = new_name or "Profit Margin"
        elif re.search(r"\b(lookup|look up|bring in|pull in|from (the )?\w+ sheet)\b", q) or self._lookup_target(table, q):
            target = self._lookup_target(table, q)
            if target is None:
                return Plan("propose_formula", "formula_specialist", message="Tell me which column to bring in and from which sheet, e.g. “Add the customer Segment from Customers to Sales”.")
            other, ret, key = target
            spec = {"kind": "lookup", "key": key.name, "lookup_sheet": other.sheet, "lookup_key": key.name, "return_column": ret.name,
                    "new_column": new_name or f"{ret.name}"}
        elif re.search(r"\b(year|month)\b", q) and self.date_column(table, q):
            part = "year_month" if re.search(r"year[- ]month|yyyy-mm|period", q) else "year" if "year" in q else "month"
            spec = {"kind": "date_part", "column": self.date_column(table, q).name, "part": part, "new_column": new_name}
        else:
            cols = [c for _, c in self.mentioned_columns(table, q)]
            num = [c for c in cols if c.semantic in NUMERIC_SEMANTICS or "number" in c.inferred_type]
            cond = re.search(r"(over|above|greater than|more than|exceeds?|below|under|less than)\s+\$?([\d,]+(?:\.\d+)?)", q)
            if cond and num:
                op = ">" if cond.group(1) in ("over", "above", "greater than", "more than", "exceed", "exceeds") else "<"
                spec = {"kind": "conditional", "column": num[0].name, "op": op, "threshold": float(cond.group(2).replace(",", "")),
                        "true_label": "High" if op == ">" else "Low", "false_label": "Normal", "new_column": new_name}
            elif len(num) >= 2 and re.search(r"minus|difference|subtract|less\b|-", q):
                spec = {"kind": "difference", "a": num[0].name, "b": num[1].name, "new_column": new_name}
            elif len(num) >= 2 and re.search(r"divided|ratio|per\b|share|percent|%", q):
                spec = {"kind": "ratio", "numerator": num[0].name, "denominator": num[1].name, "new_column": new_name}
            elif len(num) >= 2 and re.search(r"times|multipl|product", q):
                spec = {"kind": "product", "a": num[0].name, "b": num[1].name, "new_column": new_name}
            elif len(num) >= 2 and re.search(r"plus|sum of|add up|total of", q):
                spec = {"kind": "sum", "a": num[0].name, "b": num[1].name, "new_column": new_name}
        if spec is None:
            cols = ", ".join(c.name for c in table.columns[:12])
            return Plan("propose_formula", "formula_specialist", clarification={
                "question": f"What should the new column on {table.sheet} calculate? Available columns: {cols}.",
                "options": [{"label": "Profit margin", "prompt": f"Add a profit-margin column on {table.sheet}"},
                            {"label": "Year-Month from a date", "prompt": f"Add a year-month column on {table.sheet}"},
                            {"label": "Flag large values", "prompt": f"Add a column flagging rows where Net Revenue is over 10000 on {table.sheet}"}],
                "original": original, "term": None, "sheet": table.sheet})
        return Plan("propose_formula", "formula_specialist", sheet=table.sheet, assumptions=assumptions,
                    steps=[{"tool": "propose_formula", "args": {"sheet": table.sheet, "spec": {k: v for k, v in spec.items() if v is not None}}}])

    def _lookup_target(self, table: SheetTable, q: str):
        for other in self.tables():
            if other.sheet == table.sheet:
                continue
            for col in other.columns:
                if col.semantic == "identifier" or table.column(col.name):
                    continue
                if re.search(rf"\b{re.escape(col.name.lower())}\b", q):
                    shared = [c for c in other.columns if c.semantic == "identifier" and table.column(c.name)]
                    if shared:
                        return other, col, table.column(shared[0].name)
        return None


def _errors(model: WorkbookModel, sheet: str) -> list[str]:
    ws_f, ws_v = model.ws_f(sheet), model.ws_v(sheet)
    out = []
    for row in ws_f.iter_rows():
        for cell in row:
            if cell.data_type == "f" and V.is_error(ws_v[cell.coordinate].value):
                out.append(cell.coordinate)
    return out
