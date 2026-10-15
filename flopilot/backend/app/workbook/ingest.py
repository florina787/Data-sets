"""Upload validation. Runs *before* any parsing library touches the file.

Supported: .xlsx (Office Open XML workbook) and .csv. Everything else is rejected with an
explicit, user-readable limitation. Macros are never executed, external links are never
followed and data connections are never refreshed: openpyxl does not do any of these, and
.xlsm/.xlsb/.xls are refused outright.
"""
from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass

from ..common import AppError
from ..config import get_settings

OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # legacy .xls and *encrypted* OOXML containers
ZIP_MAGIC = b"PK\x03\x04"

UNSUPPORTED = {
    ".xls": "Legacy .xls (Excel 97-2003) files are not supported yet. In Excel, use File > Save As > Excel Workbook (.xlsx), then upload again.",
    ".xlsm": "Macro-enabled .xlsm files are not supported. FloPilot never runs macros; save a macro-free copy as .xlsx to analyse it.",
    ".xlsb": "Binary .xlsb workbooks are not supported. Save as .xlsx in Excel, then upload again.",
    ".xltx": "Excel templates are not supported. Save as .xlsx, then upload again.",
    ".xltm": "Macro-enabled templates are not supported.",
    ".ods": "OpenDocument spreadsheets are not supported yet. Save as .xlsx, then upload again.",
    ".numbers": "Apple Numbers files are not supported. Export to .xlsx, then upload again.",
    ".tsv": "Tab-separated files are not supported yet. Save as .csv or .xlsx.",
}


@dataclass
class ValidatedUpload:
    filename: str
    fmt: str  # "xlsx" | "csv"
    data: bytes


def _ext(filename: str) -> str:
    name = filename.lower().strip()
    return name[name.rfind("."):] if "." in name else ""


def safe_filename(filename: str) -> str:
    keep = "".join(ch for ch in filename if ch.isalnum() or ch in " ._-()")
    return (keep.strip() or "workbook")[:120]


def validate_upload(filename: str, data: bytes) -> ValidatedUpload:
    settings = get_settings()
    ext = _ext(filename)
    if not data:
        raise AppError("empty_file", "The uploaded file is empty.")
    if len(data) > settings.max_upload_bytes:
        raise AppError("file_too_large", f"The file is larger than the {settings.max_upload_mb} MB limit.", 413)
    if ext in UNSUPPORTED:
        raise AppError("unsupported_format", UNSUPPORTED[ext], 415)

    if data.startswith(OLE_MAGIC):
        # An OLE container with an .xlsx/.csv name is either a renamed .xls or a password-protected workbook.
        raise AppError(
            "password_protected_or_legacy",
            "This file appears to be password-protected (encrypted) or a legacy .xls file. "
            "FloPilot cannot open encrypted workbooks. Remove the password in Excel (File > Info > Protect Workbook) "
            "or save as .xlsx, then upload again.",
            415,
        )

    if ext == ".xlsx":
        _validate_xlsx_container(data)
        return ValidatedUpload(safe_filename(filename), "xlsx", data)
    if ext == ".csv":
        _validate_csv(data)
        return ValidatedUpload(safe_filename(filename), "csv", data)
    raise AppError("unsupported_format", "Only .xlsx and .csv files are supported.", 415)


def _validate_xlsx_container(data: bytes) -> None:
    settings = get_settings()
    if not data.startswith(ZIP_MAGIC):
        raise AppError("malformed_file", "This file is not a valid .xlsx workbook (it is not an Office Open XML package).")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = set(zf.namelist())
            total = 0
            for info in zf.infolist():
                total += info.file_size
                if info.compress_size and info.file_size / max(info.compress_size, 1) > 200 and info.file_size > 5_000_000:
                    raise AppError("suspicious_file", "The workbook has an unusual compression ratio and was rejected for safety.")
                if ".." in info.filename or info.filename.startswith("/"):
                    raise AppError("suspicious_file", "The workbook package contains unsafe paths.")
            if total > settings.max_uncompressed_mb * 1024 * 1024:
                raise AppError("file_too_large", f"The workbook expands to more than {settings.max_uncompressed_mb} MB.", 413)
    except zipfile.BadZipFile as exc:
        raise AppError("malformed_file", "The .xlsx file is damaged or incomplete.") from exc
    if "xl/workbook.xml" not in names:
        raise AppError("malformed_file", "This package is not an Excel workbook (missing xl/workbook.xml).")
    if "xl/vbaProject.bin" in names:
        raise AppError("macros_present", UNSUPPORTED[".xlsm"], 415)


def decode_csv(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            text = data.decode(encoding)
            if "\x00" in text:
                continue
            return text
        except UnicodeDecodeError:
            continue
    raise AppError("malformed_file", "The CSV file's text encoding could not be read. Save it as UTF-8 and try again.")


def _validate_csv(data: bytes) -> None:
    text = decode_csv(data)
    if not text.strip():
        raise AppError("empty_file", "The CSV file has no content.")
    try:
        sample = text[:20_000]
        csv.Sniffer().sniff(sample, delimiters=",;|\t")
    except csv.Error:
        # Single-column CSVs cannot be sniffed; that is fine.
        pass
