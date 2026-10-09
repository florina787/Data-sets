"""Seeded returns policy (REQ-8)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.critical


def place_promo_order(shop, key: str, extra_mango: int = 0) -> dict:
    cart = shop.new_cart()
    shop.set_qty(cart, "FS-MANGO-355", 2 + extra_mango)
    assert shop.claim_free(cart, "FS-ORANGE-355").status_code == 200
    response = shop.checkout(cart, key)
    assert response.status_code == 201, response.text
    return response.json()["order"]


@pytest.mark.ac("AC-8.1")
def test_full_cancellation_refunds_everything_and_restores_entitlement(shop):
    order = place_promo_order(shop, "key-cancel-1")
    response = shop.client.post(
        f"/api/orders/{order['id']}/cancel", headers=shop.headers("cust-amara-demo")
    )
    assert response.status_code == 200, response.text
    cancelled = response.json()["order"]
    assert cancelled["status"] == "cancelled"
    assert cancelled["refunded_cents"] == order["total_cents"] == 498
    assert shop.inventory.stock["FS-ORANGE-355"] == 50

    again = shop.new_cart()
    shop.set_qty(again, "FS-APPLE-355", 2)
    assert shop.claim_free(again, "FS-MANGO-355").status_code == 200


@pytest.mark.ac("AC-8.2")
def test_partial_return_refunds_allocated_promotion_amount(shop):
    order = place_promo_order(shop, "key-return-1")
    group = [u for u in order["units"] if u["in_promo_group"]]
    assert sorted(u["paid_cents"] for u in group) == [166, 166, 166]  # 498 spread over 3 units
    assert sum(u["paid_cents"] for u in order["units"]) == order["total_cents"]

    response = shop.client.post(
        f"/api/orders/{order['id']}/returns",
        json={"items": {"FS-ORANGE-355": 1}},
        headers=shop.headers("cust-amara-demo"),
    )
    assert response.status_code == 200, response.text
    returned = response.json()["order"]
    assert returned["refunded_cents"] == 166
    assert returned["status"] == "partially_returned"

    # A partial return does not restore the entitlement.
    again = shop.new_cart()
    shop.set_qty(again, "FS-APPLE-355", 2)
    assert shop.claim_free(again, "FS-MANGO-355").status_code == 409


@pytest.mark.ac("AC-8.2")
def test_units_outside_promotion_group_refund_at_full_price_first(shop):
    order = place_promo_order(shop, "key-return-2", extra_mango=1)
    assert order["total_cents"] == 3 * 249
    response = shop.client.post(
        f"/api/orders/{order['id']}/returns",
        json={"items": {"FS-MANGO-355": 2}},
        headers=shop.headers("cust-amara-demo"),
    )
    assert response.status_code == 200, response.text
    assert response.json()["order"]["refunded_cents"] == 249 + 166
    over = shop.client.post(
        f"/api/orders/{order['id']}/returns",
        json={"items": {"FS-MANGO-355": 2}},
        headers=shop.headers("cust-amara-demo"),
    )
    assert over.status_code == 400
