"""Upload validation (the demo validates but does not persist uploads)."""

from __future__ import annotations

from app.security.injection import detect_injection

ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}
MAX_BYTES = 5 * 1024 * 1024
MAGIC = {".pdf": b"%PDF", ".docx": b"PK\x03\x04"}


def validate_upload(filename: str, content: bytes) -> dict:
    errors: list[str] = []
    name = filename.strip()
    ext = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
    if not name or "/" in name or "\\" in name or ".." in name:
        errors.append("Invalid filename.")
    if ext not in ALLOWED_EXTENSIONS:
        errors.append(f"File type '{ext or 'none'}' is not allowed.")
    if len(content) == 0:
        errors.append("File is empty.")
    if len(content) > MAX_BYTES:
        errors.append("File exceeds 5 MB limit.")
    if ext in MAGIC and not content.startswith(MAGIC[ext]):
        errors.append("File content does not match its extension.")
    injection = []
    if ext in (".txt", ".md"):
        try:
            injection = detect_injection(content.decode("utf-8", errors="strict"))
        except UnicodeDecodeError:
            errors.append("Text file is not valid UTF-8.")
    return {"filename": name, "valid": not errors, "errors": errors, "size_bytes": len(content),
            "untrusted_instruction_patterns": injection,
            "handling": "Embedded instructions are treated as data and cannot change permissions." if injection else None}
