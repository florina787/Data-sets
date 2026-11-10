"""PII detection and masking.

Applied to every message before it can reach an external model, the retrieval
index, logs or the UI. Names in the source are pseudonymous handles
(e.g. `CustTWCIO`); customer handles are still replaced with a salted hash
because the analysis never needs them.
"""

from __future__ import annotations

import hashlib
import re

PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "upi_id": re.compile(r"\b[A-Za-z0-9._-]{2,}@(?:ok)?(?:upi|ybl|paytm|axl|ibl|sbi|icici|hdfcbank|okaxis|oksbi|okhdfcbank)\b", re.I),
    "card_number": re.compile(r"\b(?:\d[ -]?){13,19}\b"),
    "phone": re.compile(r"(?<![\w-])(?:\+?\d{1,3}[ -]?)?(?:\(?\d{3,5}\)?[ -]?)\d{3,4}[ -]?\d{3,4}\b"),
    "account_number": re.compile(r"\b(?:acc(?:ount)?|a/c)\s*(?:no\.?|number|#)?\s*[:#]?\s*\d{6,}\b", re.I),
    "ip_address": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
}

_ORDER = ["email", "upi_id", "account_number", "card_number", "ip_address", "phone"]


def mask_text(text: str, names: list[str] | None = None) -> tuple[str, dict[str, int]]:
    """Mask PII in `text`. Returns the masked text and counts per PII type."""
    counts: dict[str, int] = {}
    out = text
    for kind in _ORDER:
        out, n = PII_PATTERNS[kind].subn(f"[{kind.upper()}]", out)
        if n:
            counts[kind] = n
    for name in names or []:
        if name and len(name) >= 3:
            out, n = re.subn(re.escape(name), "[NAME]", out, flags=re.I)
            if n:
                counts["name"] = counts.get("name", 0) + n
    return out, counts


def contains_pii(text: str) -> bool:
    return any(p.search(text) for p in PII_PATTERNS.values())


def pseudonymize(value: str, prefix: str, salt: str = "cic") -> str:
    digest = hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()[:10]
    return f"{prefix}-{digest}"
