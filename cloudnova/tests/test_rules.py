from datetime import date
from decimal import Decimal

import pytest

from app.pipeline import rules as R


@pytest.mark.parametrize("raw,exp", [(" Starter ", "Starter"), ("Tier 1", "Starter"), ("Start", "Starter"), ("PRO", "Pro"),
                                     ("Professional", "Pro"), ("Tier 2", "Pro"), ("ENT", "Enterprise"), ("enterprise ", "Enterprise"),
                                     ("Platinum", None), ("", None)])
def test_plan_aliases_and_unknown_never_defaulted(raw, exp):
    assert R.norm_plan(raw) == exp


@pytest.mark.parametrize("raw,exp", [("Complete", "paid"), ("success", "paid"), ("in_review", "pending"), ("awaiting", "pending"),
                                     ("declined", "failed"), ("error", "failed"), ("charged_back", "refunded"), ("REFUND", "refunded"),
                                     ("canceled", "void"), ("cancelled", "void"), ("lost", None)])
def test_status_aliases(raw, exp):
    assert R.norm_status(raw) == exp


@pytest.mark.parametrize("raw,exp", [("yearly", "annual"), ("annually", "annual"), ("Annual", "annual"), ("Monthly", "monthly"), ("weekly", None)])
def test_billing_cycle(raw, exp):
    assert R.norm_cycle(raw) == exp


@pytest.mark.parametrize("raw,exp", [("true", True), ("Y", True), ("1", True), ("Yes", True), ("N", False), ("FALSE", False), ("0", False), ("", None), ("maybe", None)])
def test_booleans(raw, exp):
    assert R.norm_bool(raw) is exp


@pytest.mark.parametrize("raw,amt,ccy", [("$4,900.00", "4900.00", "USD"), ("$-4,900.00", "-4900.00", "USD"), ("€1,270.08", "1270.08", "EUR"),
                                         ("£565.78", "565.78", "GBP"), ("31432", "31432", None), ("1,200.00 EUR", "1200.00", "EUR"),
                                         ("-9,999.99 USD", "-9999.99", "USD"), ("abc", None, None), ("", None, None)])
def test_amount_parsing(raw, amt, ccy):
    got, embedded = R.parse_amount(raw)
    assert got == (Decimal(amt) if amt else None)
    if amt:
        assert embedded == ccy


@pytest.mark.parametrize("raw,exp,amb", [("2024-01-05", date(2024, 1, 5), False), ("2024/01/05", date(2024, 1, 5), False),
                                         ("01/05/2024", date(2024, 1, 5), False),       # MM/DD (evidence rule)
                                         ("31-05-2024", date(2024, 5, 31), False),      # DD-MM, unambiguous
                                         ("05-01-2024", date(2024, 1, 5), True),        # DD-MM, ambiguous → flagged
                                         ("07-07-2024", date(2024, 7, 7), False),       # day == month: same either way
                                         ("Jan 5 2024", date(2024, 1, 5), False), ("Aug 10 2023", date(2023, 8, 10), False),
                                         ("13/45/2024", None, False), ("yesterday", None, False)])
def test_dates(raw, exp, amb):
    assert R.parse_date(raw) == (exp, amb)


def test_email_repair_and_validation():
    assert R.norm_email("billing_at_acme.com") == ("billing@acme.com", True)
    assert R.norm_email("Billing@Acme.com") == ("billing@acme.com", False)
    assert R.norm_email("") == (None, False)
    assert R.norm_email("not-an-email") == (None, False)


def test_mrr_is_independent_of_cycle_and_currency():
    # Enterprise 10 seats 20% off = 299*10*0.8
    assert R.mrr_usd("Enterprise", 10, Decimal("20")) == Decimal("2392.00")
    assert R.BILLED_MONTHS == {"monthly": 1, "annual": 10}


def test_fx_conversion_documented_and_inverse():
    assert R.to_usd(Decimal("52920.00"), 1.08) == Decimal("57153.60")
    assert R.to_usd(Decimal("52920.00"), 1.08, "inverse") == Decimal("49000.00")
    assert R.to_usd(Decimal("100"), 1.0) == Decimal("100.00")


def test_conflict_precedence():
    assert sorted(["pending", "paid", "void", "refunded", "failed"], key=R.status_rank) == ["refunded", "paid", "failed", "void", "pending"]
