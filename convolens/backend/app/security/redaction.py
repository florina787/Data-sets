"""PII redaction applied at ingestion, before storage, indexing, model calls and tracing.

Raw transcript text is never persisted: only the redacted text is stored and it is the
authoritative evidence for citations. Limitations are documented in docs/DATA_DICTIONARY.md.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter

REDACTOR_VERSION = "redact-v3"

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
_URL = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_CARD = re.compile(r"\b\d(?:[ -]?\d){12,18}\b")
_PHONE = re.compile(r"(?<![\w@])(?:\+?\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)[\s.-]?|\d{2,4}[\s.-])\d{3,4}[\s.-]?\d{3,4}\b")
_LONG_ID = re.compile(r"\b(?=[A-Z0-9-]*\d)[A-Z0-9][A-Z0-9-]{7,}\b")
_MENTION = re.compile(r"@(\w{1,30})")
_SIGNOFF = re.compile(r"(?:\s[\^*~]\s?[A-Z]{1,3}\b|\s-\s?[A-Z][a-z]{1,15}\s*$)")
# Agent sign-offs seen in real support replies (applied to support messages only):
#   ".^EM"  "(1/2)^SU"  "-RK"  "/LM"  "- SL"  "~ Jess"  "!-Jazz"  "--Sam"  "...this causes. Lewis"
_AGENT_SIGNOFFS = [
    re.compile(r"\s?[\^*]\s?[A-Z]{1,3}\b"),
    re.compile(r"(?:^|(?<=[\s.!?)\]:;,]))[-–—~/]{1,2}\s?[A-Z]{2,3}\s*$"),
    re.compile(r"[-–—~]{1,2}\s?[A-Z][a-z]{1,15}(?:\s[A-Z]\.?)?\s*$"),
    re.compile(r"(?<=[.!?)])\s+[A-Z][a-z]{2,12}\s*$"),
]
_SIGNOFF_NOT_NAMES = {"Thanks", "Cheers", "Regards", "Thank", "Sorry", "Enjoy", "Again", "Soon", "Today", "Please", "Best",
                      "Bye", "Ok", "Okay", "Yes", "No", "Sure", "Great", "Welcome", "Here", "There", "Now"}
# Support agents often greet customers by first name ("Hi Debbie,"). Not a proper name detector; see docs.
_GREETING_NAME = re.compile(r"\b((?i:hi|hello|hey|hiya|dear|thanks|thank you|sorry|welcome))\s+([A-Z][a-z]{2,15})\b(?=\s*[,!.:;)-]|\s+(?:we|i|we'd|we're|i'm|please|sorry|thanks|thank|what|can|could|that|this|let|you|it)\b)")
_NOT_NAMES = {"There", "Again", "Team", "Everyone", "All", "Guys", "Folks", "Friend", "Sir", "Madam", "You", "For", "Much", "So", "From", "Again", "Back", "Our", "The", "Please", "Again", "Very", "Delta", "Apple", "Amazon"}
_NAME_INTRO = re.compile(r"\b((?i:my name is|this is|name's))\s+([A-Z][a-z]{1,20})(\s[A-Z][a-z]{1,20})?\b")


def _luhn_ok(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


def redact(text: str, keep_handles: set[str] | None = None, agent: bool = False) -> tuple[str, dict[str, int]]:
    """Return (redacted_text, counts_by_type). ``keep_handles`` are public brand support accounts.
    ``agent=True`` (support messages) also removes agent sign-offs such as "~ Jess" or "-RK"."""
    keep = {h.lower() for h in (keep_handles or set())}
    counts: Counter[str] = Counter()

    def sub(pattern: re.Pattern, label: str, s: str, check=None) -> str:
        def repl(m: re.Match) -> str:
            if check and not check(m):
                return m.group(0)
            counts[label] += 1
            return f"[{label}]"
        return pattern.sub(repl, s)

    out = text or ""
    out = sub(_EMAIL, "EMAIL", out)
    out = sub(_URL, "URL", out)
    out = sub(_IP, "IP", out)
    out = sub(_CARD, "CARD", out, check=lambda m: _luhn_ok(re.sub(r"\D", "", m.group(0))))
    out = sub(_PHONE, "PHONE", out, check=lambda m: len(re.sub(r"\D", "", m.group(0))) >= 9)
    out = sub(_LONG_ID, "ID", out)

    def mention(m: re.Match) -> str:
        handle = m.group(1)
        if handle.lower() in keep:
            return m.group(0)
        counts["HANDLE"] += 1
        return "@[CUSTOMER]" if handle.isdigit() else "@[USER]"

    out = _MENTION.sub(mention, out)

    def name(m: re.Match) -> str:
        counts["NAME"] += 1
        return f"{m.group(1)} [NAME]"

    out = _NAME_INTRO.sub(name, out)

    def greeting(m: re.Match) -> str:
        if m.group(2) in _NOT_NAMES or m.group(2).lower() in keep:
            return m.group(0)
        counts["NAME"] += 1
        return f"{m.group(1)} [NAME]"

    out = _GREETING_NAME.sub(greeting, out)

    def signoff(m: re.Match) -> str:
        counts["AGENT_SIGNOFF"] += 1
        return " [AGENT]"

    out = _SIGNOFF.sub(signoff, out)
    if agent:
        def agent_signoff(m: re.Match) -> str:
            word = re.sub(r"[^A-Za-z]", "", m.group(0))
            if word in _SIGNOFF_NOT_NAMES or word.lower() in keep:
                return m.group(0)
            counts["AGENT_SIGNOFF"] += 1
            return " [AGENT]"
        for rx in _AGENT_SIGNOFFS:
            out = rx.sub(agent_signoff, out)
        out = re.sub(r"(\s*\[AGENT\])+", " [AGENT]", out)
    return out, dict(counts)


def pseudonymize(author_id: str, salt: str = "convolens") -> str:
    return "cust_" + hashlib.sha256(f"{salt}:{author_id}".encode()).hexdigest()[:10]


def scrub_for_trace(obj, _depth: int = 0):
    """Defence in depth for LangSmith payloads: re-apply redaction to any string."""
    if _depth > 12:
        return obj
    if isinstance(obj, str):
        return redact(obj)[0] if len(obj) < 20000 else redact(obj[:20000])[0] + "…[truncated]"
    if isinstance(obj, dict):
        return {k: scrub_for_trace(v, _depth + 1) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [scrub_for_trace(v, _depth + 1) for v in obj]
    return obj
