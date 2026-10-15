"""Value classification, parsing and display formatting shared by profiling, queries and cleaning."""
from __future__ import annotations

import math
import re
from datetime import date, datetime, time, timedelta
from typing import Any

EXCEL_ERRORS = {"#DIV/0!", "#N/A", "#NAME?", "#NULL!", "#NUM!", "#REF!", "#VALUE!", "#SPILL!", "#CALC!", "#GETTING_DATA"}

_NUMERIC_TEXT = re.compile(r"^\s*[-+(]?\s*[$€£¥]?\s*[-+]?(\d{1,3}(,\d{3})+|\d+)(\.\d+)?\s*%?\s*\)?\s*$")
_PLAIN_NUMBER = re.compile(r"^\s*-?\d+(\.\d+)?\s*$")

DATE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$"), "ISO"),
    (re.compile(r"^\d{4}/\d{1,2}/\d{1,2}$"), "YMD_SLASH"),
    (re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$"), "SLASH"),
    (re.compile(r"^\d{1,2}-\d{1,2}-\d{4}$"), "DASH"),
    (re.compile(r"^\d{1,2}\.\d{1,2}\.\d{4}$"), "DOT"),
    (re.compile(r"^\d{1,2}[ -][A-Za-z]{3,9}[ -]\d{4}$"), "D_MON_Y"),
    (re.compile(r"^[A-Za-z]{3,9} \d{1,2},? \d{4}$"), "MON_D_Y"),
]
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


def is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def is_error(value: Any) -> bool:
    return isinstance(value, str) and value.strip() in EXCEL_ERRORS


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and not (
        isinstance(value, float) and (math.isnan(value) or math.isinf(value)))


def parse_numeric_text(value: str) -> float | None:
    """'1,234.50' -> 1234.5, '$1,200' -> 1200, '(50)' -> -50, '12%' -> 0.12. Returns None if not numeric."""
    if not isinstance(value, str) or not _NUMERIC_TEXT.match(value):
        return None
    text = value.strip()
    negative = text.startswith("(") and text.endswith(")")
    percent = text.endswith("%")
    cleaned = re.sub(r"[\s$€£¥,()%+]", "", text)
    try:
        number = float(cleaned)
    except ValueError:
        return None
    if negative:
        number = -abs(number)
    if percent:
        number /= 100
    return int(number) if number.is_integer() and not percent and "." not in cleaned else number


def parse_plain_number(value: str) -> int | float | None:
    if not _PLAIN_NUMBER.match(value):
        return None
    number = float(value)
    return int(number) if "." not in value else number


def date_text_kind(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    for pattern, kind in DATE_PATTERNS:
        if pattern.match(text):
            return kind
    return None


def parse_date_text(value: str, day_first: bool | None) -> tuple[date | None, bool]:
    """Parse a date string. Returns (date, ambiguous).

    `day_first` resolves dd/mm vs mm/dd. When None and both readings are valid, the result
    is flagged ambiguous and the month-first reading is used.
    """
    text = value.strip()
    kind = date_text_kind(text)
    try:
        if kind in ("ISO", "YMD_SLASH"):
            y, m, d = (int(p) for p in re.split(r"[-/]", text))
            return date(y, m, d), False
        if kind in ("SLASH", "DASH", "DOT"):
            a, b, y = (int(p) for p in re.split(r"[/.\-]", text))
            if a > 12 and b <= 12:
                return date(y, b, a), False
            if b > 12 and a <= 12:
                return date(y, a, b), False
            if a == b:
                return date(y, a, b), False
            if day_first is None:
                return date(y, a, b), True
            return (date(y, b, a), False) if day_first else (date(y, a, b), False)
        if kind == "D_MON_Y":
            d, mon, y = re.split(r"[ -]", text)
            return date(int(y), _MONTHS[mon[:3].lower()], int(d)), False
        if kind == "MON_D_Y":
            parts = text.replace(",", "").split()
            return date(int(parts[2]), _MONTHS[parts[0][:3].lower()], int(parts[1])), False
    except (ValueError, KeyError):
        return None, False
    return None, False


def slash_order_evidence(value: str) -> str | None:
    """For an a/b/yyyy string, say whether it proves day-first ('DMY') or month-first ('MDY')."""
    if date_text_kind(value) not in ("SLASH", "DASH", "DOT"):
        return None
    a, b, _ = (int(p) for p in re.split(r"[/.\-]", value.strip()))
    if a > 12 >= b:
        return "DMY"
    if b > 12 >= a:
        return "MDY"
    return None


def classify(value: Any) -> str:
    """Return a coarse type: blank, error, number, bool, date, numeric_text, date_text, text."""
    if is_blank(value):
        return "blank"
    if isinstance(value, bool):
        return "bool"
    if is_number(value):
        return "number"
    if isinstance(value, (datetime, date)):
        return "date"
    if isinstance(value, time):
        return "time"
    if isinstance(value, timedelta):
        return "duration"
    if isinstance(value, str):
        if is_error(value):
            return "error"
        if date_text_kind(value):
            return "date_text"
        if parse_numeric_text(value) is not None:
            return "numeric_text"
        return "text"
    return "text"


def to_number(value: Any) -> float | None:
    """Best-effort numeric view used by aggregations. Text numbers are NOT coerced silently;
    callers decide whether to count them (see query.coerce_numeric)."""
    if is_number(value):
        return float(value)
    return None


def as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(sep=" ") if (value.hour or value.minute or value.second) else value.date().isoformat()
    if isinstance(value, (date, time)):
        return value.isoformat()
    if isinstance(value, timedelta):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 10)
    return value


def format_display(value: Any, number_format: str | None) -> str:
    """Approximate Excel display formatting for the preview grid (not a full format engine)."""
    if value is None:
        return ""
    fmt = (number_format or "General").strip()
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, datetime):
        if any(tok in fmt.lower() for tok in ("h:", "hh", "ss")):
            return value.strftime("%Y-%m-%d %H:%M")
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.isoformat()
    if is_number(value):
        number = float(value)
        section = fmt.split(";")[0]
        if "%" in section:
            decimals = _decimals(section)
            return f"{number * 100:,.{decimals}f}%".replace(",", "") if "#,##" not in section else f"{number * 100:,.{decimals}f}%"
        currency = next((sym for sym in ("$", "€", "£", "¥") if sym in section), "")
        if "0" in section or "#" in section:
            decimals = _decimals(section)
            grouped = "#,##" in section or "," in section.replace('"', "")
            text = f"{abs(number):,.{decimals}f}" if grouped else f"{abs(number):.{decimals}f}"
            sign = "-" if number < 0 else ""
            sections = fmt.split(";")
            if number < 0 and len(sections) > 1 and "(" in sections[1]:
                return f"({currency}{text})"
            return f"{sign}{currency}{text}"
        if float(number).is_integer() and abs(number) < 1e15:
            return str(int(number))
        return f"{number:.10g}"
    return str(value)


def _decimals(section: str) -> int:
    match = re.search(r"0\.(0+)", section)
    return len(match.group(1)) if match else 0
