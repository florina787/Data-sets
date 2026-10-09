"""Checkout, inventory reservation and redemption integrity (REQ-6, REQ-7)."""

from __future__ import annotations

import sqlite3
import threading

import pytest
from conftest import AMARA, DECLINED_CARD, free_lines

from storefront.inventory_adapter import InMemoryInventory

pytestmark = pytest.mark.critical


def redemptions(shop) -> list[tuple[str, str]]:
    with sqlite3.connect(shop.db_path) as conn:
        return conn.execute(
            "SELECT customer_id, status FROM redemptions ORDER BY created_at"
        ).fetchall()


@pytest.mark.ac("AC-7.1")
def test_successful_checkout_reserves_paid_and_free_units(shop):
    cart = shop.qualifying_cart()
    response = shop.checkout(cart, "key-success-1")
    assert response.status_code == 201, response.text
    order = response.json()["order"]
    assert order["status"] == "paid"
    assert order["total_cents"] == 498
    assert sorted((u["sku"], u["is_free"]) for u in order["units"]) == [
        ("FS-MANGO-355", 0), ("FS-MANGO-355", 0), ("FS-ORANGE-355", 1)
    ]
    assert shop.inventory.stock["FS-MANGO-355"] == 48
    assert shop.inventory.stock["FS-ORANGE-355"] == 49
    assert redemptions(shop) == [("CUST-1001", "committed")]


@pytest.mark.ac("AC-7.1")
def test_exhausted_inventory_rejects_checkout_without_side_effects(make_shop):
    shop = make_shop(stock={"FS-MANGO-355": 5, "FS-ORANGE-355": 0, "FS-APPLE-355": 5})
    cart = shop.qualifying_cart()  # free orange is claimable; stock is checked at order time
    response = shop.checkout(cart, "key-oos-1")
    assert response.status_code == 409
    assert response.json()["details"]["sku"] == "FS-ORANGE-355"
    assert shop.inventory.stock["FS-MANGO-355"] == 5
    assert redemptions(shop) == []
    assert len(free_lines(shop.quote(cart))) == 1  # cart is preserved for the customer


@pytest.mark.ac("AC-7.2")
def test_quotes_do_not_consume_redemption_or_stock(shop):
    cart = shop.qualifying_cart()
    for _ in range(3):
        shop.quote(cart)
    assert redemptions(shop) == []
    assert shop.inventory.stock["FS-ORANGE-355"] == 50
    # The same customer can still hold an entitlement in a second open cart.
    other = shop.new_cart()
    shop.set_qty(other, "FS-APPLE-355", 2)
    assert shop.claim_free(other, "FS-MANGO-355").status_code == 200


@pytest.mark.ac("AC-7.3")
def test_payment_failure_releases_reservation_and_entitlement(shop):
    cart = shop.qualifying_cart()
    declined = shop.checkout(cart, "key-declined-1", card=DECLINED_CARD)
    assert declined.status_code == 402
    assert shop.inventory.stock["FS-MANGO-355"] == 50
    assert shop.inventory.stock["FS-ORANGE-355"] == 50
    assert redemptions(shop) == [("CUST-1001", "released")]
    retry = shop.checkout(cart, "key-declined-2")
    assert retry.status_code == 201, retry.text
    assert redemptions(shop)[-1] == ("CUST-1001", "committed")


@pytest.mark.ac("AC-7.4")
def test_repeated_checkout_request_is_idempotent(shop):
    cart = shop.qualifying_cart()
    first = shop.checkout(cart, "key-idem-1")
    second = shop.checkout(cart, "key-idem-1")
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["replayed"] is True
    assert first.json()["order"]["id"] == second.json()["order"]["id"]
    assert shop.inventory.stock["FS-MANGO-355"] == 48
    assert redemptions(shop) == [("CUST-1001", "committed")]


@pytest.mark.ac("AC-6.2")
def test_concurrent_checkouts_redeem_at_most_once(make_shop):
    inventory = InMemoryInventory(
        {"FS-MANGO-355": 50, "FS-ORANGE-355": 50, "FS-APPLE-355": 50}, delay_seconds=0.05
    )
    shop = make_shop(inventory=inventory)
    carts = [shop.qualifying_cart(AMARA) for _ in range(4)]
    results: list[int] = []
    barrier = threading.Barrier(len(carts))

    def run(index: int, cart_id: str) -> None:
        barrier.wait()
        results.append(shop.checkout(cart_id, f"key-race-{index}").status_code)

    threads = [threading.Thread(target=run, args=(i, c)) for i, c in enumerate(carts)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert redemptions(shop).count(("CUST-1001", "committed")) == 1
    assert [r for r in results if r not in (201, 409)] == []
    total_free_units_sold = 50 - inventory.stock["FS-ORANGE-355"]
    assert total_free_units_sold == 1
