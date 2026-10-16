"""Privacy and security guards (Agent 16): redaction, prompt-injection screening,
data-minimisation checks. Used before telemetry export, audit logging and
whenever untrusted text (user input, tool / MCP output) enters the workflow."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("HEALTH_CARD", re.compile(r"\b\d{4}[\s-]?\d{3}[\s-]?\d{3}(?:[\s-]?[A-Z]{2})?\b")),
    ("PHONE", re.compile(r"(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b")),
    ("POSTAL_CODE", re.compile(r"\b[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z][ -]?\d[ABCEGHJ-NPRSTV-Z]\d\b", re.I)),
    ("DOB", re.compile(r"\b(19|20)\d{2}[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])\b")),
    ("NAME", re.compile(r"\b(my name is|i am|i'm)\s+[A-Z][a-z]+(\s+[A-Z][a-z]+)?", re.I)),
]

SENSITIVE_KEYS = {"message", "messages", "text", "content", "prompt", "notes", "symptoms", "name", "email",
                  "phone", "health_card", "requisition", "requisition_text", "dob", "address", "postal_code",
                  "patient_name", "free_text", "input", "output", "transcript"}


def redact_text(text: str) -> str:
    out = text
    for label, pat in _PATTERNS:
        out = pat.sub(f"[REDACTED_{label}]", out)
    return out


def redact(obj: Any, depth: int = 0) -> Any:
    """Recursively redact a payload. Free-text sensitive keys are replaced entirely."""
    if depth > 8:
        return "[TRUNCATED]"
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if str(k).lower() in SENSITIVE_KEYS and isinstance(v, (str, list, dict)):
                out[k] = f"[REDACTED:{type(v).__name__}]"
            else:
                out[k] = redact(v, depth + 1)
        return out
    if isinstance(obj, (list, tuple)):
        return [redact(v, depth + 1) for v in obj]
    if isinstance(obj, str):
        return redact_text(obj)
    return obj


INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above) (instructions|prompts|rules)",
    r"disregard (the |your )?(system|previous|safety)",
    r"you are now", r"act as (an? )?(admin|administrator|developer|system)",
    r"(reveal|print|show) (your|the) (system prompt|instructions|api key|secrets?)",
    r"(book|cancel|confirm) (the |this |an |my )?appointment (now|immediately|without)",
    r"(send|share|email|forward) (the |all )?(patient|user)('s)? (data|records|information)",
    r"approve (it|this|the request) automatically", r"bypass (approval|authorization|consent|safety)",
    r"<\s*/?\s*(system|assistant|tool)\s*>", r"\bBEGIN (SYSTEM|ADMIN) PROMPT\b",
]
_INJ = [re.compile(p, re.I) for p in INJECTION_PATTERNS]


class InjectionResult(BaseModel):
    suspicious: bool
    matches: list[str]


def detect_injection(text: str) -> InjectionResult:
    hits = [p.pattern for p in _INJ if p.search(text or "")]
    return InjectionResult(suspicious=bool(hits), matches=hits)


def sanitize_untrusted(value: Any) -> tuple[Any, list[str]]:
    """Neutralise instruction-like content in untrusted tool output. Returns (value, findings)."""
    findings: list[str] = []

    def walk(v: Any) -> Any:
        if isinstance(v, str):
            r = detect_injection(v)
            if r.suspicious:
                findings.extend(r.matches)
                return "[REMOVED: instruction-like content in untrusted data]"
            return v
        if isinstance(v, dict):
            return {k: walk(x) for k, x in v.items()}
        if isinstance(v, list):
            return [walk(x) for x in v]
        return v

    return walk(value), findings


# Data minimisation: fields the patient workflow is permitted to collect.
ALLOWED_INTAKE_FIELDS = {"service", "location", "radius_km", "existing_appointment_date", "requisition_status",
                         "requisition_format", "include_private_pay", "needs_wheelchair_access", "prefer_transit",
                         "earliest_date", "max_travel_minutes", "scenario", "request_booking"}


def excess_fields(payload: dict) -> list[str]:
    return sorted(k for k in payload if k not in ALLOWED_INTAKE_FIELDS)
