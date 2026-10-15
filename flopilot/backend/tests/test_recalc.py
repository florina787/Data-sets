"""Real recalculation with LibreOffice (skipped when it is not installed)."""
from __future__ import annotations

import shutil

import pytest

from app.workbook import formulas, recalc
from app.workbook.changes import apply_change_set, build_formula_column
from app.workbook.model import load_model
from tests.conftest import DEMO

pytestmark = pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice not installed")


def test_margin_formulas_verified_by_libreoffice(settings_override):
    settings_override(recalc_engine="auto")
    base = DEMO.read_bytes()
    model = load_model(base, "wb", 1)
    p = formulas.build_formula_proposal(model, "Sales", {"kind": "margin", "profit": "Profit", "revenue": "Net Revenue"})
    candidate = apply_change_set(base, build_formula_column(model, p, {}))
    result = recalc.verify_cells(candidate, [("Sales", "N2"), ("Sales", "N40"), ("Expenses", "H23")])
    assert result["status"] == "verified" and result["engine"] == "libreoffice"
    k2, m2 = model.ws_v("Sales")["K2"].value, model.ws_v("Sales")["M2"].value
    assert result["values"]["Sales!N2"] == pytest.approx(m2 / k2)
    assert result["values"]["Sales!N40"] == pytest.approx(1234.56 / model.ws_v("Sales")["K40"].value)
    assert result["values"]["Expenses!H23"] == "#DIV/0!"


def test_engine_unavailable_is_reported_honestly(settings_override):
    settings_override(recalc_engine="none")
    result = recalc.verify_cells(DEMO.read_bytes(), [("Sales", "M2")])
    assert result["status"] == "engine_unavailable" and "not verified" in result["message"]
