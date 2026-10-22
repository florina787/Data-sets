"""Untrusted-content handling: prompt-injection screening and upload validation.

All user requests, uploaded documents and retrieved policy text are treated as DATA.
Instruction-like content is flagged (and quarantined for documents); it never changes
agent routing, tool permissions or deterministic decisions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above) (instructions|rules|prompts)",
    r"disregard (the |all )?(system|previous|above)",
    r"you are now",
    r"system prompt",
    r"reveal (your|the) (instructions|prompt|api key|secrets?)",
    r"(approve|deny) (all|every|this) claims?",
    r"override (the )?(rules?|adjudication|policy)",
    r"(print|show|return|output) .*api[_ ]?key",
    r"execute (this|the following) (command|code)",
    r"<\s*/?\s*(system|assistant|tool)\s*>",
]
_INJECTION_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)

ALLOWED_UPLOAD_EXTENSIONS = {".md", ".txt"}
_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-. ]{0,100}$")


@dataclass
class ScreenResult:
    flagged: bool
    matches: list[str] = field(default_factory=list)
    cleaned_text: str = ""


def screen_text(text: str) -> ScreenResult:
    """Flag instruction-like phrases. Returns cleaned text with offending lines removed."""
    matches: list[str] = []
    kept: list[str] = []
    for line in text.splitlines():
        if _INJECTION_RE.search(line):
            matches.append(line.strip()[:160])
            continue
        kept.append(line)
    return ScreenResult(flagged=bool(matches), matches=matches, cleaned_text="\n".join(kept))


class UploadValidationError(ValueError):
    pass


def validate_upload(filename: str, content: bytes, max_bytes: int) -> str:
    """Validate an uploaded policy document. Returns decoded UTF-8 text."""
    if not _FILENAME_RE.match(filename or "") or ".." in filename or "/" in filename or "\\" in filename:
        raise UploadValidationError("invalid filename")
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise UploadValidationError(f"file type '{ext or 'none'}' not allowed; allowed: {sorted(ALLOWED_UPLOAD_EXTENSIONS)}")
    if len(content) == 0:
        raise UploadValidationError("empty file")
    if len(content) > max_bytes:
        raise UploadValidationError(f"file exceeds size limit of {max_bytes} bytes")
    if b"\x00" in content:
        raise UploadValidationError("binary content not allowed")
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UploadValidationError("file must be UTF-8 text") from exc


SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[=:]\s*['\"]?[^\s'\"]{6,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]


def redact_secrets(text: str) -> str:
    out = text
    for pat in SECRET_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out
