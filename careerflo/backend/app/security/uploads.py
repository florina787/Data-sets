"""Upload validation: size, extension, magic bytes, zip-bomb and macro checks."""
from __future__ import annotations

import io
import zipfile

from fastapi import HTTPException

ALLOWED = {".pdf": "application/pdf",
           ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
           ".txt": "text/plain", ".md": "text/markdown"}
MAX_UNZIPPED = 30 * 1024 * 1024
MAX_ZIP_ENTRIES = 2000


def validate_upload(filename: str, data: bytes, max_bytes: int) -> str:
    name = (filename or "").lower().strip()
    ext = "." + name.rsplit(".", 1)[-1] if "." in name else ""
    if ext not in ALLOWED:
        raise HTTPException(415, "Only PDF, DOCX, TXT or Markdown files are accepted.")
    if not data:
        raise HTTPException(400, "The file is empty.")
    if len(data) > max_bytes:
        raise HTTPException(413, f"File too large (max {max_bytes // (1024 * 1024)} MB).")
    if ext == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise HTTPException(415, "File content is not a PDF.")
        lowered = data.lower()
        if b"/javascript" in lowered or b"/launch" in lowered or b"/embeddedfile" in lowered:
            raise HTTPException(415, "PDFs with embedded scripts, launch actions or attachments are not accepted.")
    elif ext == ".docx":
        if not data.startswith(b"PK"):
            raise HTTPException(415, "File content is not a DOCX document.")
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                infos = zf.infolist()
                if len(infos) > MAX_ZIP_ENTRIES or sum(i.file_size for i in infos) > MAX_UNZIPPED:
                    raise HTTPException(415, "Document is too large when decompressed.")
                names = {i.filename for i in infos}
                if "word/document.xml" not in names:
                    raise HTTPException(415, "Not a Word document.")
                if any(n.lower().endswith("vbaproject.bin") for n in names):
                    raise HTTPException(415, "Documents containing macros are not accepted.")
        except zipfile.BadZipFile as exc:
            raise HTTPException(415, "Corrupted DOCX file.") from exc
    else:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(415, "Text files must be UTF-8.") from exc
    return ALLOWED[ext]
