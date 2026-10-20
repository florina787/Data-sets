"""PII and secret detection.

Detection = pattern recognizers + custom validators (Luhn for SIN, context words for account numbers and dates of
birth) + a gazetteer of known person names from the CRM. When Microsoft Presidio is installed
(`pip install presidio-analyzer` + a spaCy model) its PERSON/LOCATION results are merged in (see `presidio_available`).
Without it, unknown names that are not preceded by an honorific may be missed — a documented limitation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

ENTITY_TYPES = ["SECRET", "EMAIL", "PHONE", "SIN", "ACCOUNT", "CLIENT_ID", "DOB", "ADDRESS", "POSTAL_CODE", "PERSON",
                "LINKED_AMOUNT"]


@dataclass(frozen=True)
class Finding:
    type: str
    start: int
    end: int
    text: str
    score: float
    recognizer: str


_NAMES: set[str] = set()
_CLIENT_NAMES: dict[str, str] = {}


def register_names(names: list[str], client_index: dict[str, str] | None = None) -> None:
    """Register person names (gazetteer) from the directory/CRM; client_index maps full name -> client id."""
    _NAMES.update(n for n in names if n)
    if client_index:
        _CLIENT_NAMES.update(client_index)


def luhn_valid(digits: str) -> bool:
    d = [int(c) for c in digits if c.isdigit()]
    if len(d) != 9:
        return False
    total = 0
    for i, x in enumerate(reversed(d)):
        if i % 2 == 1:
            x *= 2
            if x > 9:
                x -= 9
        total += x
    return total % 10 == 0


SECRET_PATTERNS = [
    (r"AKIA[0-9A-Z]{16}", "aws_access_key"),
    (r"\bsk-(?:ant-|live-|test-|proj-)?[A-Za-z0-9_\-]{20,}", "api_secret_key"),
    (r"\bgh[pousr]_[A-Za-z0-9]{30,}", "github_token"),
    (r"\bxox[abpr]-[A-Za-z0-9-]{10,}", "slack_token"),
    (r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}", "jwt"),
    (r"(?i)\b(?:api[_-]?key|secret|password|passwd|token|bearer)\b\s*[:=]?\s*['\"]?[A-Za-z0-9_\-./+=]{8,}", "credential_assignment"),
    (r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----", "private_key"),
]
RX = {
    "EMAIL": re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
    "PHONE": re.compile(r"(?:\+?1[\s.\-]?)?(?:\(\d{3}\)|\b\d{3})[\s.\-]\d{3}[\s.\-]\d{4}\b"),
    "NINE": re.compile(r"\b\d{3}[ \-]?\d{3}[ \-]?\d{3}\b"),
    "LONG_ACCT": re.compile(r"(?i)\b(?:account|acct|compte|cuenta|계좌|खाता|கணக்கு)\s*(?:no\.?|number|#|num[eé]ro)?\s*[:#]?\s*(\d[\d\- ]{5,15}\d)"),
    "CLIENT_ID": re.compile(r"\bC-\d{5}\b"),
    "DOB": re.compile(r"(?i)(?:born(?: on)?|d\.?o\.?b\.?|date of birth|birth ?date|date de naissance|fecha de nacimiento)\s*[:\-]?\s*"
                      r"(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|[A-Z][a-z]+ \d{1,2},? \d{4}|\d{1,2} [A-Z][a-z]+ \d{4})"),
    "ADDRESS": re.compile(r"\b\d{1,5}\s+(?:[A-Z][a-zé]+\s){1,3}(?:Street|St\.?|Avenue|Ave\.?|Road|Rd\.?|Crescent|Cres\.?|Drive|Dr\.?|"
                          r"Boulevard|Blvd\.?|Lane|Way|Court|Rue|Chemin)\b"),
    "POSTAL_CODE": re.compile(r"\b[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z][ \-]?\d[ABCEGHJ-NPRSTV-Z]\d\b"),
    "HONORIFIC_NAME": re.compile(r"\b(?:Mr|Mrs|Ms|Miss|Dr|Mx|M\.|Mme|Sr|Sra)\.?\s+([A-Z][\w'\-]+(?:\s+[A-Z][\w'\-]+)?)"),
    "CLIENT_NAMED": re.compile(r"\b(?:[Cc]lient|[Cc]liente|[Hh]ousehold)\s+([A-Z][\w'\-]+\s+[A-Z][\w'\-]+)"),
    "CAP_PAIR": re.compile(r"\b([A-ZÀ-ÖØ-Þ][\wÀ-ÿ'\-]+)\s+([A-ZÀ-ÖØ-Þ][\wÀ-ÿ'\-]+)\b"),
    "AMOUNT": re.compile(r"(?:CAD|C?\$|USD)\s?\d[\d,]*(?:\.\d{1,2})?\s?(?:[kKmMbB](?:illion|n)?)?\b"),
}
SECRET_RX = [(re.compile(p), n) for p, n in SECRET_PATTERNS]


def presidio_available() -> bool:
    try:
        import presidio_analyzer  # noqa: F401
        return True
    except ImportError:
        return False


def detect(text: str) -> list[Finding]:
    if not text:
        return []
    f: list[Finding] = []
    for rx, name in SECRET_RX:
        f += [Finding("SECRET", m.start(), m.end(), m.group(0), 0.95, name) for m in rx.finditer(text)]
    f += [Finding("EMAIL", m.start(), m.end(), m.group(0), 0.99, "email_regex") for m in RX["EMAIL"].finditer(text)]
    for m in RX["LONG_ACCT"].finditer(text):
        f.append(Finding("ACCOUNT", m.start(1), m.end(1), m.group(1), 0.9, "account_context"))
    for m in RX["NINE"].finditer(text):
        if luhn_valid(m.group(0)):
            f.append(Finding("SIN", m.start(), m.end(), m.group(0), 0.85, "sin_luhn"))
        elif re.fullmatch(r"77\d{7}", m.group(0)):
            f.append(Finding("ACCOUNT", m.start(), m.end(), m.group(0), 0.8, "flo_account_format"))
    f += [Finding("PHONE", m.start(), m.end(), m.group(0), 0.85, "nanp_phone") for m in RX["PHONE"].finditer(text)]
    f += [Finding("CLIENT_ID", m.start(), m.end(), m.group(0), 0.99, "client_id_format") for m in RX["CLIENT_ID"].finditer(text)]
    f += [Finding("DOB", m.start(1), m.end(1), m.group(1), 0.9, "dob_context") for m in RX["DOB"].finditer(text)]
    f += [Finding("ADDRESS", m.start(), m.end(), m.group(0), 0.8, "street_address") for m in RX["ADDRESS"].finditer(text)]
    f += [Finding("POSTAL_CODE", m.start(), m.end(), m.group(0), 0.8, "ca_postal_code") for m in RX["POSTAL_CODE"].finditer(text)]
    for key in ("HONORIFIC_NAME", "CLIENT_NAMED"):
        f += [Finding("PERSON", m.start(1), m.end(1), m.group(1), 0.75, key.lower()) for m in RX[key].finditer(text)]
    for m in RX["CAP_PAIR"].finditer(text):
        full = f"{m.group(1)} {m.group(2)}"
        if full in _NAMES:
            f.append(Finding("PERSON", m.start(), m.end(), full, 0.97, "crm_gazetteer"))
    if presidio_available():  # pragma: no cover - optional dependency
        f += _presidio(text)
    f = _resolve_overlaps(f)
    # financial amounts in a sentence that identifies a person are personal information
    if any(x.type in ("PERSON", "CLIENT_ID", "ACCOUNT", "SIN") for x in f):
        person_spans = [(x.start, x.end) for x in f if x.type in ("PERSON", "CLIENT_ID", "ACCOUNT", "SIN")]
        for m in RX["AMOUNT"].finditer(text):
            s0 = text.rfind(".", 0, m.start()) + 1
            s1 = text.find(".", m.end())
            s1 = len(text) if s1 == -1 else s1
            if any(s0 <= a < s1 for a, _ in person_spans) and not any(x.start <= m.start() < x.end for x in f):
                f.append(Finding("LINKED_AMOUNT", m.start(), m.end(), m.group(0), 0.7, "amount_linked_to_person"))
    return sorted(f, key=lambda x: x.start)


def _presidio(text: str) -> list[Finding]:  # pragma: no cover
    from presidio_analyzer import AnalyzerEngine
    eng = AnalyzerEngine()
    out = []
    for r in eng.analyze(text=text, language="en", entities=["PERSON", "LOCATION"]):
        if r.score >= 0.6:
            out.append(Finding("PERSON" if r.entity_type == "PERSON" else "ADDRESS", r.start, r.end, text[r.start:r.end], r.score, "presidio"))
    return out


_PRIORITY = {t: i for i, t in enumerate(ENTITY_TYPES)}


def _resolve_overlaps(f: list[Finding]) -> list[Finding]:
    f = sorted(f, key=lambda x: (x.start, _PRIORITY[x.type], -(x.end - x.start)))
    out: list[Finding] = []
    for x in f:
        if out and x.start < out[-1].end:
            prev = out[-1]
            if (_PRIORITY[x.type], -(x.end - x.start)) < (_PRIORITY[prev.type], -(prev.end - prev.start)):
                out[-1] = x
            continue
        out.append(x)
    return out


def redact_text(text: str) -> str:
    out, last = [], 0
    for x in detect(text):
        out.append(text[last:x.start])
        out.append(f"[REDACTED:{x.type}]")
        last = x.end
    out.append(text[last:])
    return "".join(out)


def mask_value(kind: str, value: str) -> str:
    """Partial masking for display (keeps the minimum needed to recognize a record)."""
    if kind == "EMAIL" and "@" in value:
        local, dom = value.split("@", 1)
        return f"{local[:1]}***@{dom}"
    digits = re.sub(r"\D", "", value)
    if kind in ("PHONE", "ACCOUNT", "SIN"):
        return "*" * max(0, len(digits) - 4) + digits[-4:] if kind != "SIN" else "*** *** " + digits[-3:]
    if kind == "PERSON":
        parts = value.split()
        return " ".join(p[0] + "." for p in parts)
    if kind == "DOB":
        return value[:4] + "-**-**" if re.match(r"\d{4}-", value) else "**/**/****"
    return "*" * min(8, len(value))


def mask_text(text: str) -> str:
    out, last = [], 0
    for x in detect(text):
        out.append(text[last:x.start])
        out.append(mask_value(x.type, x.text))
        last = x.end
    out.append(text[last:])
    return "".join(out)


def redact_structure(obj: Any, _depth: int = 0) -> Any:
    if _depth > 8:
        return "[TRUNCATED]"
    if isinstance(obj, str):
        return redact_text(obj) if len(obj) < 20000 else redact_text(obj[:20000]) + "[TRUNCATED]"
    if isinstance(obj, dict):
        return {k: redact_structure(v, _depth + 1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact_structure(v, _depth + 1) for v in obj]
    return obj


def contains_pii(text: str) -> bool:
    return any(x.type != "LINKED_AMOUNT" for x in detect(text))
