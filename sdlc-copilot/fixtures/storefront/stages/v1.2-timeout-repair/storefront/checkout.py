"""Order creation: reserve stock, persist the order, take mock payment, commit."""

from __future__ import annotations

import sqlite3
import uuid
from collections import Counter
from datetime import datetime

from storefront import cart as carts
from storefront import payments, promotions
from storefront.catalog import get_product
from storefront.db import tx
from storefront.errors import CheckoutUnavailable, CommerceError, Conflict, PaymentFailed
from storefront.inventory_adapter import InventoryAdapter, InventoryUnavailable, OutOfStock
from storefront.pricing import Quote, allocate, compute_quote


def build_units(quote: Quote) -> list[dict]:
    """Expand quote lines into units and allocate discounts across them.

    With a free campaign unit, the two qualifying paid units and the free unit
    form a promotion group: the group's paid amount is allocated across all
    three units by list price, so partial returns refund the allocated amount.
    """
    units = []
    for line in quote.lines:
        product = get_product(line.sku)
        for _ in range(line.qty):
            units.append(
                {
                    "sku": line.sku,
                    "list_price_cents": product.price_cents,
                    "paid_cents": 0 if line.is_free else line.unit_price_cents,
                    "is_free": int(line.is_free),
                    "in_promo_group": int(line.is_free),
                }
            )
    free_units = [u for u in units if u["is_free"]]
    if free_units:
        qualifying = [
            u for u in units
            if not u["is_free"] and u["sku"] in promotions.CAMPAIGN.eligible_skus
        ][: promotions.CAMPAIGN.required_paid_units]
        group = qualifying + free_units
        group_paid = sum(u["paid_cents"] for u in qualifying)
        shares = allocate(group_paid, [u["list_price_cents"] for u in group])
        for unit, share in zip(group, shares, strict=True):
            unit["paid_cents"] = share
            unit["in_promo_group"] = 1
    if quote.discount_cents:
        paid_units = [u for u in units if not u["is_free"]]
        shares = allocate(quote.discount_cents, [u["list_price_cents"] for u in paid_units])
        for unit, share in zip(paid_units, shares, strict=True):
            unit["paid_cents"] -= share
    return units


def order_view(conn: sqlite3.Connection, order_id: str) -> dict:
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    units = conn.execute(
        "SELECT * FROM order_units WHERE order_id = ? ORDER BY unit_index", (order_id,)
    ).fetchall()
    refunds = conn.execute(
        "SELECT * FROM refunds WHERE order_id = ? ORDER BY created_at", (order_id,)
    ).fetchall()
    return {
        **dict(order),
        "units": [dict(u) for u in units],
        "refunds": [dict(r) for r in refunds],
    }


def _release_quietly(inventory: InventoryAdapter, reservation_id: str) -> None:
    try:
        inventory.release(reservation_id)
    except InventoryUnavailable:
        pass  # the inventory system expires held reservations on its own


def checkout(
    conn: sqlite3.Connection,
    inventory: InventoryAdapter,
    cart_id: str,
    customer_id: str | None,
    payment_token: str,
    idempotency_key: str,
    now: datetime,
) -> tuple[dict, bool]:
    """Return ``(order, replayed)``. Replays of an idempotency key never charge twice."""
    existing = conn.execute(
        "SELECT id, cart_id FROM orders WHERE idempotency_key = ?", (idempotency_key,)
    ).fetchone()
    if existing:
        if existing["cart_id"] != cart_id:
            raise Conflict("Idempotency key already used for another cart")
        return order_view(conn, existing["id"]), True

    cart = carts.get_cart(conn, cart_id)
    carts.require_access(cart, customer_id)
    carts.require_open(cart)
    quote = compute_quote(conn, cart_id, now)
    if not quote.lines:
        raise CommerceError("Cart is empty")
    if not quote.province:
        raise CommerceError("Shipping province is required")
    units = build_units(quote)
    has_free_unit = any(u["is_free"] for u in units)
    if has_free_unit and not customer_id:
        raise CommerceError("Sign in to receive the free unit")
    campaign_id = promotions.CAMPAIGN.id if has_free_unit else None

    try:
        reservation_id = inventory.reserve_order(
            dict(Counter(u["sku"] for u in units)), idempotency_key, campaign_id
        )
    except OutOfStock as exc:
        raise Conflict("Not enough stock", sku=exc.sku) from exc
    except InventoryUnavailable as exc:
        raise CheckoutUnavailable(
            "Checkout is temporarily unavailable. Your cart has been saved."
        ) from exc

    order_id = "ORD-" + uuid.uuid4().hex[:12]
    try:
        with tx(conn):
            conn.execute(
                "INSERT INTO orders (id, cart_id, customer_id, idempotency_key, status, province,"
                " subtotal_cents, discount_cents, total_cents, reservation_id, campaign_id,"
                " created_at) VALUES (?, ?, ?, ?, 'pending_payment', ?, ?, ?, ?, ?, ?, ?)",
                (
                    order_id, cart_id, customer_id, idempotency_key, quote.province,
                    quote.subtotal_cents, quote.discount_cents, quote.total_cents,
                    reservation_id, campaign_id, now.isoformat(),
                ),
            )
            if has_free_unit:
                promotions.insert_pending_redemption(conn, customer_id, order_id, now)
            conn.executemany(
                "INSERT INTO order_units (order_id, unit_index, sku, list_price_cents, paid_cents,"
                " is_free, in_promo_group) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (order_id, i, u["sku"], u["list_price_cents"], u["paid_cents"],
                     u["is_free"], u["in_promo_group"])
                    for i, u in enumerate(units)
                ],
            )
    except sqlite3.IntegrityError:
        replay = conn.execute(
            "SELECT id FROM orders WHERE idempotency_key = ?", (idempotency_key,)
        ).fetchone()
        if replay is not None:
            return order_view(conn, replay["id"]), True
        _release_quietly(inventory, reservation_id)
        if has_free_unit:
            raise Conflict(
                "The free unit has already been redeemed by this customer",
                reason="already_redeemed",
            ) from None
        raise

    try:
        payment_ref = payments.charge(payment_token, quote.total_cents, idempotency_key)
    except payments.PaymentDeclined as exc:
        with tx(conn):
            conn.execute("UPDATE orders SET status = 'payment_failed' WHERE id = ?", (order_id,))
            promotions.set_redemption_status(conn, order_id, "released")
        _release_quietly(inventory, reservation_id)
        raise PaymentFailed(str(exc), order_id=order_id) from exc

    with tx(conn):
        conn.execute(
            "UPDATE orders SET status = 'paid', payment_ref = ? WHERE id = ?",
            (payment_ref, order_id),
        )
        conn.execute("UPDATE carts SET status = 'checked_out' WHERE id = ?", (cart_id,))
        promotions.set_redemption_status(conn, order_id, "committed")
    try:
        inventory.commit(reservation_id)
    except InventoryUnavailable:
        pass  # stock stays held; the reservation is reconciled by the inventory system
    return order_view(conn, order_id), False
