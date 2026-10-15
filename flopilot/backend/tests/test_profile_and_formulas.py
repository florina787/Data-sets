"""Profiling of the seeded demo workbook, formula intelligence and the preview evaluator."""
from __future__ import annotations

import pytest

from app.common import AppError
from app.workbook import formulas
from app.workbook.evaluator import evaluate_formula
from app.workbook.model import load_model
from app.workbook.profile import profile_workbook
from tests.conftest import DEMO


@pytest.fixture(scope="module")
def demo():
    return load_model(DEMO.read_bytes(), "wb_demo", 1)


@pytest.fixture(scope="module")
def profile(demo):
    return profile_workbook(demo)


def kinds(profile, sheet=None):
    return {(i["sheet"], i["column"], i["kind"]) for i in profile["issues"] if sheet in (None, i["sheet"])}


def test_seeded_issues_are_detected(profile):
    k = kinds(profile)
    assert ("Expenses", None, "formula_error") in k
    assert ("Sales", "Region", "category_variants") in k
    assert ("Sales", "Category", "category_variants") in k
    assert ("Expenses", "Department", "category_variants") in k
    assert ("Sales", "Order Date", "inconsistent_dates") in k
    assert ("Sales", None, "duplicate_candidates") in k
    assert ("Customers", None, "duplicate_candidates") in k
    assert ("Sales", "Customer ID", "missing_values") in k
    assert ("Sales", "Units", "outlier_candidates") in k
    assert ("Notes", None, "hidden_sheets") in k
    assert ("Notes", None, "instruction_like_text") in k


def test_outlier_is_the_seeded_transaction(profile):
    issue = next(i for i in profile["issues"] if i["kind"] == "outlier_candidates" and i["column"] == "Gross Revenue")
    assert issue["rows"] == [75]


def test_types_formulas_and_structure(profile):
    sales = next(s for s in profile["sheets"] if s["name"] == "Sales")
    cols = {c["name"]: c for c in sales["table"]["columns"]}
    assert cols["Net Revenue"]["semantic"] == "currency"
    assert cols["Discount"]["semantic"] == "percentage"
    assert cols["Order Date"]["semantic"] == "date"
    assert cols["Order Date"]["inferred_type"].startswith("mixed")
    assert cols["Order ID"]["semantic"] == "identifier"
    assert sales["formula_cells"] == 119 and sales["formulas_without_cached_value"] == 0
    summary = next(s for s in profile["sheets"] if s["name"] == "Summary")
    assert summary["merged_ranges"] == ["A1:D1"]
    assert summary["table"]["header_row"] == 3 and summary["table"]["header_confidence"] < 0.9
    inv = next(s for s in profile["sheets"] if s["name"] == "Inventory")
    assert inv["excel_tables"] == ["InventoryTable"] and inv["data_validations"] == 1 and inv["conditional_formats"] == 1
    notes = next(s for s in profile["sheets"] if s["name"] == "Notes")
    assert notes["state"] == "hidden"


def test_explain_formula_with_references(demo):
    e = formulas.explain_formula("=(F23-G23)/G23", demo, "Expenses", "H23")
    assert "Amount (F23) minus Budget (G23) divided by Budget (G23)" in e["plain_english"]
    assert all(r["anchoring"].startswith("relative") for r in e["references"])
    x = formulas.explain_formula("=XLOOKUP(A2,Customers!$A$2:$A$41,Customers!$C$2:$C$41)", demo, "Sales")
    assert any("Microsoft 365" in c for c in x["compatibility"])
    assert any(r["cross_sheet"] and r["anchoring"].startswith("absolute") for r in x["references"])


def test_diagnose_div0(demo):
    d = formulas.diagnose_cell(demo, "Expenses", "H23")
    assert d["error"] == "#DIV/0!"
    assert "The divisor G23 is zero." in d["findings"]
    assert d["suggested_formula"] == '=IF(OR(G23=0,G23=""),"",(F23-G23)/G23)'


def test_consistency_check_finds_typed_value(demo):
    c = formulas.consistency_check(demo, "Sales", "Profit")
    assert c["dominant_pattern"] == "=K2-L2"
    assert c["hardcoded_rows"] == [40]
    assert c["inconsistent"] == []


def test_formula_policy(demo):
    for bad in ('=WEBSERVICE("http://x")', '=HYPERLINK("http://x","click")', "=[Other.xlsx]Sheet1!A1"):
        with pytest.raises(AppError) as e:
            formulas.validate_formula(bad, demo)
        assert e.value.code in ("formula_not_allowed", "invalid_formula")
    with pytest.raises(AppError):
        formulas.validate_formula("=SUM(Missing!A1:A3)", demo)
    assert formulas.validate_formula("=TODAY()", demo)  # volatile note


def test_margin_proposal_placement(demo):
    p = formulas.build_formula_proposal(demo, "Sales", {"kind": "margin", "profit": "Profit", "revenue": "Net Revenue"})
    assert p["target_column"] == "N" and p["header_cell"] == "N1"
    assert p["first_formula"] == '=IFERROR(M2/K2,"")'
    assert p["target_range"] == "N2:N121" and len(p["rows"]) == 120
    assert p["number_format"] == "0.0%"
    with pytest.raises(AppError) as e:
        formulas.build_formula_proposal(demo, "Sales", {"kind": "ratio", "numerator": "Cost", "denominator": "Units", "new_column": "Profit"})
    assert e.value.code == "column_exists"


def test_cross_sheet_lookup_proposal(demo):
    p = formulas.build_formula_proposal(demo, "Sales", {"kind": "lookup", "key": "Customer ID", "lookup_sheet": "Customers",
                                                         "lookup_key": "Customer ID", "return_column": "Segment"})
    assert p["first_formula"] == '=XLOOKUP(F2,Customers!$A$2:$A$42,Customers!$C$2:$C$42,"Not found")'
    legacy = formulas.build_formula_proposal(demo, "Sales", {"kind": "lookup", "key": "Customer ID", "lookup_sheet": "Customers",
                                                              "lookup_key": "Customer ID", "return_column": "Segment"}, excel_version="2016")
    assert legacy["first_formula"].startswith("=IFERROR(INDEX(Customers!$C$2:$C$42,MATCH(F2,")

    def resolver(sheet, row, col):
        return demo.ws_v(sheet).cell(row, col).value
    value, reason = evaluate_formula(legacy["first_formula"], "Sales", resolver)
    customer = demo.ws_v("Sales")["F2"].value
    expected = next(demo.ws_v("Customers").cell(r, 3).value for r in range(2, 43) if demo.ws_v("Customers").cell(r, 1).value == customer)
    assert reason is None and value == expected


def test_custom_template_with_column_names(demo):
    p = formulas.build_formula_proposal(demo, "Sales", {"kind": "custom", "template": "={Net Revenue}-{Cost}", "new_column": "Check"})
    assert p["first_formula"] == "=K2-L2"


@pytest.mark.parametrize("formula,expected", [
    ("=1+2*3", 7.0), ("=(1+2)*3", 9.0), ("=2^3^2", 64.0), ("=-2^2", 4.0), ("=10%", 0.1), ('="a"&1', "a1"),
    ("=IF(1>2,\"x\",\"y\")", "y"), ("=IFERROR(1/0,\"safe\")", "safe"), ("=ROUND(2.345,2)", 2.35), ("=1/0", "#DIV/0!"),
    ('=1+"x"', "#VALUE!"), ("=AND(1,0)", False),
])
def test_evaluator(formula, expected):
    value, reason = evaluate_formula(formula, "S", lambda s, r, c: None)
    assert reason is None and value == expected


def test_evaluator_refuses_unsupported():
    value, reason = evaluate_formula("=XLOOKUP(1,A1:A2,B1:B2)", "S", lambda s, r, c: None)
    assert value is None and "not supported" in reason
