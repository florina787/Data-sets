import json
from datetime import date

import pandas as pd

from app import db
from app.pipeline.clean import RAW_COLUMNS, clean


def _row(**kw):
    base = dict(invoice_id="INV-1", account_id="ACC-1", account_name="Acme", contact_email="a@acme.com", region="NA",
                industry="Retail", plan="Pro", billing_cycle="monthly", seats="10", currency="USD", amount="990.00",
                discount_pct="0", status="paid", payment_method="ach", signup_date="2023-01-01", invoice_date="2024-01-05",
                churned="N", csat_score="4", support_tickets="0")
    base.update(kw)
    return base


def _clean(rows):
    df = pd.DataFrame(rows)[RAW_COLUMNS]
    df.insert(0, "raw_row_number", range(2, len(df) + 2))
    return clean(df, {"USD": 1.0, "EUR": 1.08, "GBP": 1.27}, today=date(2026, 11, 7))


def test_every_raw_row_is_accounted_for():
    r = _clean([_row(), _row(), _row(invoice_id="INV-2", plan="Platinum"), _row(invoice_id="INV-3", status="Complete"),
                _row(invoice_id="INV-3", status="PAID")])
    assert len(r.invoices) + len(r.rejected_rows) == 5
    assert set(r.rejected_rows["reason"]) == {"exact_duplicate", "unknown_plan", "synonym_duplicate"}


def test_conflict_precedence_and_audit():
    r = _clean([_row(invoice_id="INV-9", status="Pending"), _row(invoice_id="INV-9", status="Complete")])
    assert r.invoices.loc[0, "status"] == "paid"
    assert r.invoices.loc[0, "dedup_rule"] == "conflict_precedence"
    assert r.dedup_conflicts.loc[0, "usd_at_stake"] == 990.0
    lost = r.rejected_rows.iloc[0]
    assert lost["reason"] == "lost_conflict" and json.loads(lost["raw_record"])["status"] == "Pending"


def test_annual_and_mrr_and_fx():
    r = _clean([_row(billing_cycle="yearly", currency="EUR", amount="10,692.00 EUR", plan="Tier 2")])
    inv = r.invoices.iloc[0]
    assert inv["billed_months"] == 10 and float(inv["mrr_usd"]) == 990.0
    assert float(inv["expected_amount_usd"]) == 9900.0
    assert float(inv["amount_usd"]) == round(10692 * 1.08, 2)
    assert "pricing_violation" not in inv["dq_flags"]


def test_nulls_not_imputed_and_flags():
    r = _clean([_row(csat_score="", industry="", contact_email="x_at_acme.com", invoice_date="05-01-2024")])
    inv = r.invoices.iloc[0]
    assert pd.isna(inv["csat_score"]) and inv["industry"] is None
    assert inv["contact_email"] == "x@acme.com"
    assert inv["date_was_ambiguous"] and inv["invoice_date"] == date(2024, 1, 5)
    for f in ("csat_missing", "industry_missing", "email_repaired", "ambiguous_invoice_date"):
        assert f in inv["dq_flags"]


def test_account_snapshot_uses_latest_invoice():
    r = _clean([_row(invoice_id="INV-1", plan="Starter", invoice_date="2023-01-01", churned="N"),
                _row(invoice_id="INV-2", plan="Enterprise", invoice_date="2024-06-01", churned="Y")])
    a = r.accounts.iloc[0]
    assert a["plan"] == "Enterprise" and a["churned"] is True or a["churned"] == True  # noqa: E712
    assert not a["is_active"] and a["attr_conflicts"] >= 2


def test_built_database_invariants():
    assert db.internal_scalar("SELECT COUNT(*) FROM invoices") == 5000
    assert db.internal_scalar("SELECT COUNT(*) FROM invoices") + db.internal_scalar("SELECT COUNT(*) FROM rejected_rows") == 5125
    assert db.internal_scalar("SELECT COUNT(DISTINCT invoice_id) FROM invoices") == 5000
    assert db.internal_scalar("SELECT COUNT(*) FROM invoices WHERE status NOT IN ('paid','pending','failed','refunded','void')") == 0
    assert db.internal_scalar("SELECT COUNT(*) FROM invoices WHERE status='refunded' AND amount_usd >= 0") == 0
    assert db.internal_scalar("SELECT COUNT(*) FROM invoices WHERE dq_flags LIKE '%pricing_violation%'") == 0
