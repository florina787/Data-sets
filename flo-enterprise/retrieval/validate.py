"""File admission checks before parsing: extension allowlist, size limit, magic bytes, malware heuristics.
This is a demonstration-grade screen (EICAR test signature, executables, macro-enabled Office files, zip bombs).
Production deployments add an AV engine (e.g. ClamAV) via the FileScanner interface."""
from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass

ALLOWED = {".pdf", ".docx", ".xlsx", ".csv", ".md", ".txt"}
MAX_BYTES = 5 * 1024 * 1024
EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


@dataclass
class ScanResult:
    ok: bool
    reason: str = "clean"


def scan(filename: str, data: bytes) -> ScanResult:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED:
        return ScanResult(False, f"extension {ext or '(none)'} not allowed")
    if len(data) > MAX_BYTES:
        return ScanResult(False, "file exceeds 5 MB limit")
    if EICAR in data:
        return ScanResult(False, "malware signature detected (EICAR test)")
    if data[:2] == b"MZ" or data[:4] == b"\x7fELF":
        return ScanResult(False, "executable content")
    if ext == ".pdf":
        if not data.startswith(b"%PDF"):
            return ScanResult(False, "PDF magic bytes missing")
        if b"/JavaScript" in data or b"/Launch" in data:
            return ScanResult(False, "PDF contains active content")
    if ext in (".docx", ".xlsx"):
        if not data.startswith(b"PK"):
            return ScanResult(False, "Office file is not a valid zip container")
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names = z.namelist()
                if any(n.lower().endswith("vbaproject.bin") for n in names):
                    return ScanResult(False, "macro-enabled content")
                if sum(i.file_size for i in z.infolist()) > 50 * MAX_BYTES:
                    return ScanResult(False, "decompressed size too large (zip bomb heuristic)")
        except zipfile.BadZipFile:
            return ScanResult(False, "corrupt Office container")
    if ext in (".md", ".txt", ".csv"):
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            return ScanResult(False, "text file is not valid UTF-8")
    return ScanResult(True)
