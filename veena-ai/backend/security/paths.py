"""Safe file handling: filename sanitising and path containment checks."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

ALLOWED_DOC_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".markdown", ".csv", ".json"}

_WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class UnsafePathError(ValueError):
    pass


def sanitize_filename(name: str) -> str:
    name = unicodedata.normalize("NFKC", name or "")
    # Strip any directory part a client may have sent, on either separator.
    name = re.split(r"[\\/]", name)[-1]
    name = re.sub(r"[\x00-\x1f<>:\"|?*]", "_", name).strip(" .")
    if not name or name in {".", ".."}:
        raise UnsafePathError("empty or invalid filename")
    stem = name.split(".", 1)[0].upper()
    if stem in _WINDOWS_RESERVED:
        name = f"_{name}"
    return name[:180]


def safe_join(base: Path, *parts: str) -> Path:
    base_resolved = base.resolve()
    candidate = base_resolved.joinpath(*parts).resolve()
    if candidate != base_resolved and base_resolved not in candidate.parents:
        raise UnsafePathError("path escapes the allowed directory")
    return candidate


def check_extension(name: str) -> str:
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_DOC_EXTENSIONS:
        raise UnsafePathError(f"unsupported file type {ext or '(none)'}")
    return ext
