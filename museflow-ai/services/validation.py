"""Input validation and sanitisation for every visitor-provided value."""
from __future__ import annotations

import html
import re
import unicodedata

MAX_REQUEST_CHARS = 500
MAX_MEMORY_CHARS = 280
MAX_TITLE_CHARS = 80
MAX_UPLOAD_BYTES = 100_000
ALLOWED_UPLOAD_EXTENSIONS = (".txt", ".md")

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Patterns for data we refuse to store in the demo (we never want real PII).
_SENSITIVE_PATTERNS: dict[str, re.Pattern[str]] = {
    "email address": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "phone number": re.compile(r"(?:\+?\d[\s.-]?){9,}\d"),
    "card-like number": re.compile(r"\b(?:\d[ -]?){13,19}\b"),
    "government ID": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credential": re.compile(r"\b(password|passcode|api[_ -]?key|secret|token|pin code)\b", re.I),
}


class ValidationError(ValueError):
    """Raised when visitor input fails validation."""


def clean_text(value: object, *, max_chars: int, field: str = "input", allow_empty: bool = False) -> str:
    """Normalise, strip control characters and enforce a length limit."""
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be text.")
    text = unicodedata.normalize("NFKC", value)
    text = _CONTROL_CHARS.sub("", text).strip()
    if not text and not allow_empty:
        raise ValidationError(f"{field} cannot be empty.")
    if len(text) > max_chars:
        raise ValidationError(f"{field} must be at most {max_chars} characters (got {len(text)}).")
    return text


def find_sensitive(text: str) -> list[str]:
    """Return the kinds of sensitive data detected in ``text``."""
    return [kind for kind, pattern in _SENSITIVE_PATTERNS.items() if pattern.search(text)]


def ensure_not_sensitive(text: str, field: str = "input") -> None:
    found = find_sensitive(text)
    if found:
        raise ValidationError(
            f"{field} looks like it contains sensitive information ({', '.join(found)}). "
            "MuseFlow's public demo never stores personal data — please use a harmless example."
        )


def escape(value: object) -> str:
    """HTML-escape anything before it is placed inside custom markup."""
    return html.escape(str(value), quote=True)


def validate_choice(value: object, allowed: set[str] | list[str] | tuple[str, ...], field: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ValidationError(f"Unsupported {field}: {value!r}.")
    return value


def validate_time(value: object, field: str = "time") -> str:
    if not isinstance(value, str) or not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value):
        raise ValidationError(f"{field} must look like HH:MM.")
    return value


def validate_upload(name: str, data: bytes) -> str:
    """Validate an uploaded text document and return its decoded text."""
    lowered = name.lower()
    if not lowered.endswith(ALLOWED_UPLOAD_EXTENSIONS):
        raise ValidationError("Only .txt and .md files are supported in the demo.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValidationError(f"File is larger than {MAX_UPLOAD_BYTES // 1000} KB.")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError("File must be UTF-8 text.") from exc
    return clean_text(text.replace("\r\n", "\n"), max_chars=MAX_UPLOAD_BYTES, field="document")
