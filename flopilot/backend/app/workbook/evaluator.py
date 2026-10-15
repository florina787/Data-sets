"""A small, safe Excel formula evaluator used ONLY for previews.

It supports arithmetic, comparisons, text concatenation, cell/range references (same or other
sheet) and a short list of functions. Anything else raises `Unsupported`, and the preview says
"not evaluated". Results are always labelled as FloPilot preview values; Excel (or the optional
LibreOffice recalculation) is the source of truth.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable

from openpyxl.formula import Tokenizer
from openpyxl.formula.tokenizer import Token
from openpyxl.utils.cell import column_index_from_string, coordinate_from_string, range_boundaries

from . import values as V


class Unsupported(Exception):
    pass


@dataclass(frozen=True)
class XLError:
    code: str

    def __str__(self) -> str:
        return self.code


DIV0, VALUE, NA, REF, NAME = XLError("#DIV/0!"), XLError("#VALUE!"), XLError("#N/A"), XLError("#REF!"), XLError("#NAME?")

SUPPORTED_FUNCTIONS = {
    "SUM", "AVERAGE", "MIN", "MAX", "COUNT", "COUNTA", "IF", "IFERROR", "IFNA", "ROUND", "ABS", "AND", "OR", "NOT",
    "YEAR", "MONTH", "DAY", "LEN", "UPPER", "LOWER", "TRIM", "CONCAT", "CONCATENATE", "ISBLANK", "INDEX", "MATCH",
    "SUMIF", "COUNTIF",
}

PRECEDENCE = {"=": 1, "<>": 1, "<": 1, ">": 1, "<=": 1, ">=": 1, "&": 2, "+": 3, "-": 3, "*": 4, "/": 4, "^": 5}

# Resolver: (sheet, row, col) -> value
Resolver = Callable[[str, int, int], Any]


class _Parser:
    def __init__(self, formula: str):
        tokens = Tokenizer(formula).items
        self.tokens = [t for t in tokens if t.type != Token.WSPACE]
        self.i = 0

    def peek(self) -> Token | None:
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def take(self) -> Token:
        tok = self.peek()
        if tok is None:
            raise Unsupported("unexpected end of formula")
        self.i += 1
        return tok

    def parse(self):
        node = self.expr(0)
        if self.peek() is not None:
            raise Unsupported(f"unexpected token {self.peek().value!r}")
        return node

    def expr(self, min_prec: int):
        left = self.unary()
        while True:
            tok = self.peek()
            if tok is None or tok.type != Token.OP_IN or tok.value not in PRECEDENCE:
                break
            prec = PRECEDENCE[tok.value]
            if prec < min_prec:
                break
            self.take()
            right = self.expr(prec + 1)  # Excel evaluates every binary operator left-to-right, including ^
            left = ("bin", tok.value, left, right)
        return left

    def unary(self):
        tok = self.peek()
        if tok is not None and tok.type == Token.OP_PRE:
            self.take()
            operand = self.unary()
            return ("neg", operand) if tok.value == "-" else operand
        node = self.primary()
        tok = self.peek()
        if tok is not None and tok.type == Token.OP_POST and tok.value == "%":
            self.take()
            node = ("bin", "/", node, ("num", 100.0))
        return node

    def primary(self):
        tok = self.take()
        if tok.type == Token.OPERAND:
            if tok.subtype == Token.NUMBER:
                return ("num", float(tok.value))
            if tok.subtype == Token.TEXT:
                return ("str", tok.value[1:-1].replace('""', '"'))
            if tok.subtype == Token.LOGICAL:
                return ("bool", tok.value.upper() == "TRUE")
            if tok.subtype == Token.ERROR:
                return ("err", XLError(tok.value))
            if tok.subtype == Token.RANGE:
                return ("ref", tok.value)
        if tok.type == Token.FUNC and tok.subtype == Token.OPEN:
            name = tok.value[:-1].upper().removeprefix("_XLFN.")
            args = []
            nxt = self.peek()
            if nxt is not None and nxt.type == Token.FUNC and nxt.subtype == Token.CLOSE:
                self.take()
                return ("fn", name, args)
            while True:
                args.append(self.expr(0))
                sep = self.take()
                if sep.type == Token.SEP and sep.subtype == Token.ARG:
                    continue
                if sep.type == Token.FUNC and sep.subtype == Token.CLOSE:
                    break
                raise Unsupported("malformed function call")
            return ("fn", name, args)
        if tok.type == Token.PAREN and tok.subtype == Token.OPEN:
            node = self.expr(0)
            close = self.take()
            if close.type != Token.PAREN:
                raise Unsupported("unbalanced parentheses")
            return node
        raise Unsupported(f"unsupported token {tok.value!r}")


def parse_ref(ref: str, default_sheet: str) -> tuple[str, int, int, int, int]:
    """'A1' / 'Sheet!A1:B2' / "'My Sheet'!$A$1" -> (sheet, min_row, min_col, max_row, max_col)."""
    if "[" in ref:
        raise Unsupported("external workbook references are not evaluated")
    sheet = default_sheet
    if "!" in ref:
        sheet, ref = ref.rsplit("!", 1)
        sheet = sheet.strip("'").replace("''", "'")
    ref = ref.replace("$", "")
    if ":" not in ref:
        col, row = coordinate_from_string(ref)
        c = column_index_from_string(col)
        return sheet, row, c, row, c
    min_col, min_row, max_col, max_row = range_boundaries(ref)
    if min_row is None or max_row is None:
        raise Unsupported("whole-column references are not evaluated in previews")
    return sheet, min_row, min_col, max_row, max_col


class Evaluator:
    def __init__(self, resolver: Resolver, sheet: str):
        self.resolver = resolver
        self.sheet = sheet

    def evaluate(self, formula: str) -> Any:
        node = _Parser(formula).parse()
        return self._eval(node)

    # -- helpers
    def _range_values(self, node) -> list[Any]:
        if node[0] != "ref":
            v = self._eval(node)
            return v if isinstance(v, list) else [v]
        sheet, r1, c1, r2, c2 = parse_ref(node[1], self.sheet)
        if (r2 - r1 + 1) * (c2 - c1 + 1) > 100_000:
            raise Unsupported("range too large for preview")
        return [self.resolver(sheet, r, c) for r in range(r1, r2 + 1) for c in range(c1, c2 + 1)]

    @staticmethod
    def _num(v: Any) -> float | XLError:
        if isinstance(v, XLError):
            return v
        if v is None or v == "":
            return 0.0
        if isinstance(v, bool):
            return 1.0 if v else 0.0
        if V.is_number(v):
            return float(v)
        if isinstance(v, (date, datetime)):
            base = datetime(1899, 12, 30)
            dt = v if isinstance(v, datetime) else datetime(v.year, v.month, v.day)
            return (dt - base).days + (dt - base).seconds / 86400
        if isinstance(v, str):
            if V.is_error(v):
                return XLError(v.strip())
            n = V.parse_numeric_text(v)
            return float(n) if n is not None else VALUE
        return VALUE

    def _eval(self, node) -> Any:
        kind = node[0]
        if kind in ("num", "str", "bool", "err"):
            return node[1]
        if kind == "ref":
            sheet, r1, c1, r2, c2 = parse_ref(node[1], self.sheet)
            if (r1, c1) == (r2, c2):
                v = self.resolver(sheet, r1, c1)
                if isinstance(v, str) and V.is_error(v):
                    return XLError(v.strip())
                return v
            return self._range_values(node)
        if kind == "neg":
            v = self._num(self._eval(node[1]))
            return v if isinstance(v, XLError) else -v
        if kind == "bin":
            return self._binary(node[1], self._eval(node[2]), self._eval(node[3]))
        if kind == "fn":
            return self._call(node[1], node[2])
        raise Unsupported(kind)

    def _binary(self, op: str, a: Any, b: Any) -> Any:
        if isinstance(a, list) or isinstance(b, list):
            raise Unsupported("array arithmetic")
        if isinstance(a, XLError):
            return a
        if isinstance(b, XLError):
            return b
        if op == "&":
            return f"{_text(a)}{_text(b)}"
        if op in ("=", "<>", "<", ">", "<=", ">="):
            x, y = _cmp(a), _cmp(b)
            try:
                return {"=": x == y, "<>": x != y, "<": x < y, ">": x > y, "<=": x <= y, ">=": x >= y}[op]
            except TypeError:
                # Excel orders numbers < text < booleans
                rank = lambda v: 0 if isinstance(v, (int, float)) else 1 if isinstance(v, str) else 2  # noqa: E731
                return {"<": rank(x) < rank(y), ">": rank(x) > rank(y), "<=": rank(x) <= rank(y), ">=": rank(x) >= rank(y),
                        "=": False, "<>": True}[op]
        x, y = self._num(a), self._num(b)
        if isinstance(x, XLError):
            return x
        if isinstance(y, XLError):
            return y
        if op == "+":
            return x + y
        if op == "-":
            return x - y
        if op == "*":
            return x * y
        if op == "/":
            return DIV0 if y == 0 else x / y
        if op == "^":
            try:
                return math.pow(x, y)
            except (ValueError, OverflowError):
                return XLError("#NUM!")
        raise Unsupported(op)

    def _call(self, name: str, args: list) -> Any:
        if name not in SUPPORTED_FUNCTIONS:
            raise Unsupported(f"function {name} is not supported by the preview evaluator")
        if name in ("IF",):
            cond = self._eval(args[0])
            if isinstance(cond, XLError):
                return cond
            truthy = bool(self._num(cond)) if not isinstance(cond, str) else bool(cond)
            if truthy:
                return self._eval(args[1]) if len(args) > 1 else True
            return self._eval(args[2]) if len(args) > 2 else False
        if name in ("IFERROR", "IFNA"):
            v = self._eval(args[0])
            if isinstance(v, XLError) and (name == "IFERROR" or v == NA):
                return self._eval(args[1])
            return v
        if name in ("SUM", "AVERAGE", "MIN", "MAX", "COUNT", "COUNTA"):
            flat: list[Any] = []
            for a in args:
                flat.extend(self._range_values(a) if a[0] == "ref" else [self._eval(a)])
            errs = [v for v in flat if isinstance(v, XLError) or (isinstance(v, str) and V.is_error(v))]
            if errs and name != "COUNTA":
                return errs[0] if isinstance(errs[0], XLError) else XLError(errs[0])
            nums = [float(v) for v in flat if V.is_number(v)]
            if name == "SUM":
                return math.fsum(nums)
            if name == "AVERAGE":
                return DIV0 if not nums else math.fsum(nums) / len(nums)
            if name == "MIN":
                return min(nums) if nums else 0.0
            if name == "MAX":
                return max(nums) if nums else 0.0
            if name == "COUNT":
                return float(len(nums))
            return float(sum(v not in (None, "") for v in flat))
        if name == "ROUND":
            x, d = self._num(self._eval(args[0])), self._num(self._eval(args[1]))
            if isinstance(x, XLError):
                return x
            factor = 10 ** int(d)
            return math.floor(abs(x) * factor + 0.5) / factor * (1 if x >= 0 else -1)
        if name == "ABS":
            x = self._num(self._eval(args[0]))
            return x if isinstance(x, XLError) else abs(x)
        if name in ("AND", "OR"):
            vals = [bool(self._num(self._eval(a))) for a in args]
            return all(vals) if name == "AND" else any(vals)
        if name == "NOT":
            return not bool(self._num(self._eval(args[0])))
        if name in ("YEAR", "MONTH", "DAY"):
            v = self._eval(args[0])
            if isinstance(v, (date, datetime)):
                return float({"YEAR": v.year, "MONTH": v.month, "DAY": v.day}[name])
            return VALUE
        if name in ("LEN", "UPPER", "LOWER", "TRIM"):
            v = self._eval(args[0])
            if isinstance(v, XLError):
                return v
            t = _text(v)
            return {"LEN": float(len(t)), "UPPER": t.upper(), "LOWER": t.lower(), "TRIM": " ".join(t.split())}[name]
        if name in ("CONCAT", "CONCATENATE"):
            parts = [self._eval(a) for a in args]
            for p in parts:
                if isinstance(p, XLError):
                    return p
            return "".join(_text(p) for p in parts)
        if name == "ISBLANK":
            v = self._eval(args[0])
            return v is None
        if name == "MATCH":
            target = self._eval(args[0])
            values = self._range_values(args[1])
            mode = self._num(self._eval(args[2])) if len(args) > 2 else 1
            if mode != 0:
                raise Unsupported("approximate MATCH")
            for i, v in enumerate(values, start=1):
                if _cmp(v) == _cmp(target):
                    return float(i)
            return NA
        if name == "INDEX":
            values = self._range_values(args[0])
            idx = self._num(self._eval(args[1]))
            if isinstance(idx, XLError):
                return idx
            if len(args) > 2:
                raise Unsupported("two-dimensional INDEX")
            i = int(idx)
            return values[i - 1] if 1 <= i <= len(values) else REF
        if name in ("SUMIF", "COUNTIF"):
            crit_range = self._range_values(args[0])
            criterion = self._eval(args[1])
            sum_range = self._range_values(args[2]) if len(args) > 2 else crit_range
            if isinstance(criterion, str) and criterion[:1] in "<>=":
                raise Unsupported("operator criteria")
            hits = [i for i, v in enumerate(crit_range) if _cmp(v) == _cmp(criterion)]
            if name == "COUNTIF":
                return float(len(hits))
            return math.fsum(float(sum_range[i]) for i in hits if i < len(sum_range) and V.is_number(sum_range[i]))
        raise Unsupported(name)


def _text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _cmp(v: Any) -> Any:
    if isinstance(v, str):
        return v.strip().lower()
    if isinstance(v, bool):
        return v
    if V.is_number(v):
        return float(v)
    if isinstance(v, datetime):
        return v.date()
    if v is None:
        return 0.0
    return v


def evaluate_formula(formula: str, sheet: str, resolver: Resolver) -> tuple[Any, str | None]:
    """Returns (value, None) or (None, reason-not-evaluated). Errors are returned as their code."""
    text = formula[1:] if formula.startswith("=") else formula
    try:
        value = Evaluator(resolver, sheet).evaluate("=" + text)
    except Unsupported as exc:
        return None, str(exc)
    except RecursionError:
        return None, "formula nesting too deep for preview"
    if isinstance(value, XLError):
        return value.code, None
    if isinstance(value, list):
        return None, "array results are not previewed"
    return value, None


def referenced_functions(formula: str) -> list[str]:
    tokens = Tokenizer(formula if formula.startswith("=") else "=" + formula).items
    return sorted({t.value[:-1].upper().removeprefix("_XLFN.") for t in tokens if t.type == Token.FUNC and t.subtype == Token.OPEN})


def referenced_ranges(formula: str) -> list[str]:
    tokens = Tokenizer(formula if formula.startswith("=") else "=" + formula).items
    return [t.value for t in tokens if t.type == Token.OPERAND and t.subtype == Token.RANGE]
