"""Business rules from specs/cloudnova_data_contract.md §4–5 and BUSINESS_CONTEXT.md.

Pure functions, no pandas, so each rule is unit-testable on its own. Every parser returns
``None`` (never a guess) when the input does not match a documented pattern.
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

LIST_PRICE_USD = {"Starter": 49, "Pro": 99, "Enterprise": 299}
BILLED_MONTHS = {"monthly": 1, "annual": 10}  # annual = 12 months for the price of 10
STATUS_PRECEDENCE = ["refunded", "paid", "failed", "void", "pending"]  # dedup conflicts (spec §3)
REVENUE_STATUSES = ("paid", "refunded")
REGIONS = {"NA", "EMEA", "APAC", "LATAM"}
CURRENCIES = {"USD", "EUR", "GBP"}

PLAN_MAP = {
    "starter": "Starter", "start": "Starter", "tier 1": "Starter",
    "pro": "Pro", "professional": "Pro", "tier 2": "Pro",
    "enterprise": "Enterprise", "ent": "Enterprise", "tier 3": "Enterprise",
}
CYCLE_MAP = {"monthly": "monthly", "month": "monthly", "mo": "monthly",
             "annual": "annual", "annually": "annual", "yearly": "annual", "year": "annual", "yr": "annual"}
STATUS_MAP = {
    "paid": "paid", "complete": "paid", "completed": "paid", "success": "paid",
    "pending": "pending", "in_review": "pending", "awaiting": "pending",
    "failed": "failed", "declined": "failed", "error": "failed",
    "refunded": "refunded", "refund": "refunded", "charged_back": "refunded",
    "void": "void", "cancelled": "void", "canceled": "void",
}
PAYMENT_MAP = {"credit_card": "credit_card", "credit card": "credit_card", "ach": "ach",
               "wire": "wire", "wire transfer": "wire", "invoice": "invoice"}
BOOL_TRUE = {"true", "yes", "1", "y"}
BOOL_FALSE = {"false", "no", "0", "n"}

_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_SYMBOL_CCY = {"$": "USD", "€": "EUR", "£": "GBP"}


def _key(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).lower()


def norm_plan(v: str | None) -> str | None:
    return PLAN_MAP.get(_key(v))


def norm_cycle(v: str | None) -> str | None:
    return CYCLE_MAP.get(_key(v))


def norm_status(v: str | None) -> str | None:
    return STATUS_MAP.get(_key(v))


def norm_payment(v: str | None) -> str | None:
    return PAYMENT_MAP.get(_key(v))


def norm_bool(v: str | None) -> bool | None:
    k = _key(v)
    return True if k in BOOL_TRUE else False if k in BOOL_FALSE else None


def norm_text(v: str | None) -> str | None:
    s = re.sub(r"\s+", " ", (v or "").strip())
    return s or None


def norm_email(v: str | None) -> tuple[str | None, bool]:
    """Returns (email or None, was_repaired). `_at_` → `@`; invalid after repair → None."""
    s = (v or "").strip().lower()
    if not s:
        return None, False
    repaired = False
    if "@" not in s and "_at_" in s:
        s, repaired = s.replace("_at_", "@", 1), True
    return (s if _EMAIL.match(s) else None), repaired


def parse_amount(v: str | None) -> tuple[Decimal | None, str | None]:
    """Parse '$-4,900.00', '€1,270.08', '1,200.00 EUR', '31432' → (Decimal, embedded_currency|None)."""
    s = (v or "").strip()
    if not s:
        return None, None
    ccy = None
    m = re.search(r"\s*([A-Za-z]{3})$", s)
    if m:
        ccy, s = m.group(1).upper(), s[: m.start()].strip()
    for sym, code in _SYMBOL_CCY.items():
        if sym in s:
            if ccy and ccy != code:
                return None, None
            ccy, s = code, s.replace(sym, "")
    s = s.replace(",", "").replace(" ", "")
    if not re.fullmatch(r"-?\d+(\.\d+)?", s):
        return None, ccy
    try:
        return Decimal(s), ccy
    except InvalidOperation:  # pragma: no cover - regex guarantees validity
        return None, ccy


def parse_date(v: str | None) -> tuple[date | None, bool]:
    """Returns (date or None, was_ambiguous). Rules: spec §5.2 (evidence-based orders)."""
    s = (v or "").strip()
    try:
        if m := re.fullmatch(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s):      # YYYY-MM-DD, YYYY/MM/DD
            return date(int(m[1]), int(m[2]), int(m[3])), False
        if m := re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s):            # MM/DD/YYYY
            return date(int(m[3]), int(m[1]), int(m[2])), False
        if m := re.fullmatch(r"(\d{1,2})-(\d{1,2})-(\d{4})", s):            # DD-MM-YYYY
            d, mo = int(m[1]), int(m[2])
            return date(int(m[3]), mo, d), (d <= 12 and mo <= 12 and d != mo)
        if m := re.fullmatch(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})", s):  # Jan 5 2024
            mo = _MONTHS.get(m[1].lower())
            return (date(int(m[3]), mo, int(m[2])), False) if mo else (None, False)
    except ValueError:
        return None, False
    return None, False


def parse_int(v: str | None) -> int | None:
    s = (v or "").strip()
    return int(s) if re.fullmatch(r"-?\d+", s) else None


def mrr_usd(plan: str, seats: int, discount_pct: Decimal) -> Decimal:
    """MRR = list_price[plan] × seats × (1 − discount_pct/100), USD. Independent of cycle/currency."""
    return (Decimal(LIST_PRICE_USD[plan]) * seats * (1 - discount_pct / 100)).quantize(Decimal("0.01"))


def to_usd(amount_local: Decimal, rate: float, direction: str = "documented") -> Decimal:
    r = Decimal(str(rate))
    v = amount_local * r if direction == "documented" else amount_local / r
    return v.quantize(Decimal("0.01"))


def status_rank(status: str) -> int:
    return STATUS_PRECEDENCE.index(status)
