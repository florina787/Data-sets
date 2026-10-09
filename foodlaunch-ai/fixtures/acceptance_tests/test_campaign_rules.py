"""Campaign eligibility rules (REQ-1 .. REQ-6)."""

from __future__ import annotations

import pytest
from conftest import LUC, free_lines

from storefront import promotions

pytestmark = pytest.mark.critical


@pytest.mark.ac("AC-1.1")
def test_two_paid_eligible_units_earn_exactly_one_free_unit(shop):
    cart = shop.new_cart()
    shop.set_qty(cart, "FS-MANGO-355", 1)
    shop.set_qty(cart, "FS-APPLE-355", 1)
    response = shop.claim_free(cart, "FS-ORANGE-355")
    assert response.status_code == 200, response.text
    quote = response.json()["quote"]
    assert [(f["sku"], f["qty"], f["line_total_cents"]) for f in free_lines(quote)] == [
        ("FS-ORANGE-355", 1, 0)
    ]
    assert quote["total_cents"] == 2 * 249
    second = shop.claim_free(cart, "FS-MANGO-355")
    assert second.status_code == 409
    assert len(free_lines(shop.quote(cart))) == 1


@pytest.mark.ac("AC-1.2")
def test_unrelated_products_neither_qualify_nor_can_be_free(shop):
    cart = shop.new_cart()
    shop.set_qty(cart, "FS-SPARKLIME-355", 2)  # FreshSip brand, but not an eligible SKU
    shop.set_qty(cart, "BH-COLDBREW-300", 3)
    assert shop.claim_free(cart, "FS-MANGO-355").status_code == 409
    shop.set_qty(cart, "FS-MANGO-355", 2)
    not_eligible = shop.claim_free(cart, "FS-SPARKLIME-355")
    assert not_eligible.status_code == 400
    assert free_lines(shop.quote(cart)) == []


@pytest.mark.ac("AC-1.3")
def test_one_paid_eligible_unit_is_not_enough(shop):
    cart = shop.new_cart()
    shop.set_qty(cart, "FS-MANGO-355", 1)
    response = shop.claim_free(cart, "FS-ORANGE-355")
    assert response.status_code == 409
    assert "needs_two_paid_eligible_units" in response.json()["details"]["reasons"]


@pytest.mark.ac("AC-2.1")
@pytest.mark.regression("REG-001")
def test_removing_qualifying_paid_units_removes_the_free_unit(shop):
    """REG-001: the free unit must not survive removal of qualifying paid units."""
    cart = shop.qualifying_cart()
    assert len(free_lines(shop.quote(cart))) == 1

    after_reduce = shop.set_qty(cart, "FS-MANGO-355", 1).json()["quote"]
    assert free_lines(after_reduce) == [], "free unit kept after paid units were reduced"
    assert after_reduce["total_cents"] == 249
    assert after_reduce["promotion"]["entitled"] is False

    # Adding the paid unit back does not silently re-add a free unit.
    restored = shop.set_qty(cart, "FS-MANGO-355", 2).json()["quote"]
    assert free_lines(restored) == []


@pytest.mark.ac("AC-2.1")
@pytest.mark.regression("REG-001")
def test_checkout_after_removal_charges_for_every_unit(shop):
    cart = shop.qualifying_cart()
    shop.set_qty(cart, "FS-MANGO-355", 0)
    shop.set_qty(cart, "FS-APPLE-355", 1)
    response = shop.checkout(cart, "key-reg001-checkout")
    assert response.status_code == 201, response.text
    order = response.json()["order"]
    assert [u["is_free"] for u in order["units"]] == [0]
    assert order["total_cents"] == 249


@pytest.mark.ac("AC-3.1")
def test_shipping_province_must_be_ontario(shop):
    cart = shop.new_cart(province="QC")
    shop.set_qty(cart, "FS-MANGO-355", 2)
    response = shop.claim_free(cart, "FS-ORANGE-355")
    assert response.status_code == 409
    assert "shipping_province_not_eligible" in response.json()["details"]["reasons"]

    no_province = shop.new_cart(province=None)
    shop.set_qty(no_province, "FS-MANGO-355", 2)
    assert shop.claim_free(no_province, "FS-ORANGE-355").status_code == 409


@pytest.mark.ac("AC-3.1", "AC-2.1")
@pytest.mark.regression("REG-001")
def test_changing_province_away_from_ontario_removes_free_unit(shop):
    cart = shop.qualifying_cart()
    quote = shop.ship_to(cart, "MB").json()["quote"]
    assert free_lines(quote) == []
    assert "shipping_province_not_eligible" in quote["promotion"]["reasons"]


@pytest.mark.ac("AC-4.1")
def test_campaign_window_is_converted_from_toronto_time_across_dst(shop):
    campaign = shop.client.get("/api/campaign").json()
    # Starts Saturday 00:00 EDT (UTC-4); ends Monday 00:00 EST (UTC-5) after DST ends.
    assert campaign["timezone"] == "America/Toronto"
    assert campaign["window_utc"] == ["2026-10-31T04:00:00+00:00", "2026-11-02T05:00:00+00:00"]


@pytest.mark.ac("AC-4.1")
@pytest.mark.parametrize(
    ("instant", "active"),
    [
        ("2026-10-30T23:59:59-04:00", False),
        ("2026-10-31T00:00:00-04:00", True),
        ("2026-11-01T01:30:00-05:00", True),  # repeated hour, second occurrence (EST)
        ("2026-11-01T23:30:00-05:00", True),  # wrong if the end used the EDT offset
        ("2026-11-02T00:00:00-05:00", False),
    ],
)
def test_campaign_boundaries(make_shop, instant, active):
    shop = make_shop(clock=instant)
    cart = shop.new_cart()
    shop.set_qty(cart, "FS-MANGO-355", 2)
    response = shop.claim_free(cart, "FS-ORANGE-355")
    assert (response.status_code == 200) is active, response.text


@pytest.mark.ac("AC-4.2")
@pytest.mark.parametrize("local", ["2026-11-01T01:30:00", "2026-03-08T02:30:00"])
def test_ambiguous_or_missing_local_times_are_rejected(local):
    with pytest.raises(ValueError):
        promotions.to_utc(local, "America/Toronto")


@pytest.mark.ac("AC-5.1")
def test_discount_codes_do_not_stack_with_free_unit(shop):
    cart = shop.qualifying_cart()
    blocked = shop.apply_code(cart, "WELCOME10")
    assert blocked.status_code == 409
    assert shop.quote(cart)["discount_code"] is None

    other = shop.new_cart(customer=LUC)
    shop.set_qty(other, "FS-MANGO-355", 2, customer=LUC)
    assert shop.apply_code(other, "WELCOME10", customer=LUC).status_code == 200
    refused = shop.claim_free(other, "FS-ORANGE-355", customer=LUC)
    assert refused.status_code == 409
    assert "not_combinable_with_discount_codes" in refused.json()["details"]["reasons"]


@pytest.mark.ac("AC-6.1")
def test_anonymous_carts_cannot_claim_free_unit(shop):
    cart = shop.new_cart(customer=None)
    shop.set_qty(cart, "FS-MANGO-355", 2, customer=None)
    response = shop.claim_free(cart, "FS-ORANGE-355", customer=None)
    assert response.status_code == 409
    assert "sign_in_required" in response.json()["details"]["reasons"]


@pytest.mark.ac("AC-6.1")
def test_one_free_unit_per_customer_per_campaign(shop):
    first = shop.qualifying_cart()
    assert shop.checkout(first, "key-once-1").status_code == 201

    second = shop.new_cart()
    shop.set_qty(second, "FS-MANGO-355", 4)
    response = shop.claim_free(second, "FS-APPLE-355")
    assert response.status_code == 409
    assert "already_redeemed" in response.json()["details"]["reasons"]

    # Another customer is unaffected.
    luc_cart = shop.new_cart(customer=LUC)
    shop.set_qty(luc_cart, "FS-MANGO-355", 2, customer=LUC)
    assert shop.claim_free(luc_cart, "FS-APPLE-355", customer=LUC).status_code == 200
