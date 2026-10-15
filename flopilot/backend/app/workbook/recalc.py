"""Optional real recalculation using LibreOffice (headless) - used only to VERIFY formulas.

The recalculated file is never published: LibreOffice rewrites the package and would change
fidelity. We read computed values from its output and discard it. If LibreOffice is not
installed (the default slim Docker image), verification reports `engine_unavailable` and the UI
says the formula was inserted but not verified.
"""
from __future__ import annotations

import io
import shutil
import subprocess
import tempfile
from pathlib import Path

import openpyxl

from ..config import get_settings


def engine_name() -> str | None:
    mode = get_settings().recalc_engine
    if mode == "none":
        return None
    if shutil.which("soffice"):
        return "libreoffice"
    return None


def recalculate(data: bytes) -> bytes | None:
    if engine_name() is None:
        return None
    timeout = get_settings().recalc_timeout_s
    with tempfile.TemporaryDirectory(prefix="flopilot-recalc-") as tmp:
        src = Path(tmp) / "candidate.xlsx"
        out_dir = Path(tmp) / "out"
        src.write_bytes(data)
        profile = Path(tmp) / "profile"
        cmd = [
            "soffice", f"-env:UserInstallation=file://{profile}", "--headless", "--norestore", "--nologo",
            "--nodefault", "--calc", "--convert-to", "xlsx", "--outdir", str(out_dir), str(src),
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=timeout, check=False,
                           env={"HOME": tmp, "PATH": "/usr/bin:/bin:/usr/local/bin"})
        except (subprocess.TimeoutExpired, OSError):
            return None
        result = out_dir / "candidate.xlsx"
        return result.read_bytes() if result.exists() else None


def verify_cells(candidate: bytes, cells: list[tuple[str, str]]) -> dict:
    """Recalculate `candidate` and return computed values for (sheet, coord) pairs."""
    engine = engine_name()
    if engine is None:
        return {"status": "engine_unavailable", "engine": None, "values": {},
                "message": "No recalculation engine is installed; formulas are inserted but their results are not verified by FloPilot. Excel recalculates them on open."}
    recalculated = recalculate(candidate)
    if recalculated is None:
        return {"status": "engine_failed", "engine": engine, "values": {},
                "message": "The recalculation engine did not finish; results are not verified."}
    wb = openpyxl.load_workbook(io.BytesIO(recalculated), data_only=True)
    values = {}
    for sheet, coord in cells:
        if sheet in wb.sheetnames:
            values[f"{sheet}!{coord}"] = wb[sheet][coord].value
    return {"status": "verified", "engine": engine, "values": values,
            "message": "Values recalculated by LibreOffice. Excel may differ for functions LibreOffice does not support (shown as #NAME?)."}
