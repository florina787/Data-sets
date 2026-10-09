"""Order creation: reserve stock, persist the order, take mock payment, commit."""

from __future__ import annotations

import sqlite3
import uuid
from collections import Counter
from datetime import datetime

from storefront import cart as carts
from storefront import payments
from storefront.db import tx
from storefront.errors import CheckoutUnavailable, CommerceError, Conflict, PaymentFailed
from storefront.inventory_adapter import InventoryAdapter, InventoryUnavailable, OutOfStock
from storefront.pricing import Quote, allocate, compute_quote


def build_units(quote: Quote) -> list[dict]:
    """Expand quote lines into units and allocate the order discount across them."""
    units = []
    for line in quote.lines:
        for _ in range(line.qty):
            units.append(
                {
                    "sku": line.sku,
                    "list_price_cents": line.unit_price_cents,
                    "paid_cents": line.unit_price_cents,
                    "is_free": 0,
                    "in_promo_group": 0,
                }
            )
    if quote.discount_cents:
        shares = allocate(quote.discount_cents, [u["list_price_cents"] for u in units])
        for unit, share in zip(units, shares, strict=True):
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

    try:
        reservation_id = inventory.reserve(dict(Counter(u["sku"] for u in units)), idempotency_key)
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
                " subtotal_cents, discount_cents, total_cents, reservation_id, created_at)"
                " VALUES (?, ?, ?, ?, 'pending_payment', ?, ?, ?, ?, ?, ?)",
                (
                    order_id, cart_id, customer_id, idempotency_key, quote.province,
                    quote.subtotal_cents, quote.discount_cents, quote.total_cents,
                    reservation_id, now.isoformat(),
                ),
            )
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
        if replay is None:
            raise
        return order_view(conn, replay["id"]), True

    try:
        payment_ref = payments.charge(payment_token, quote.total_cents, idempotency_key)
    except payments.PaymentDeclined as exc:
        with tx(conn):
            conn.execute("UPDATE orders SET status = 'payment_failed' WHERE id = ?", (order_id,))
        _release_quietly(inventory, reservation_id)
        raise PaymentFailed(str(exc), order_id=order_id) from exc

    with tx(conn):
        conn.execute(
            "UPDATE orders SET status = 'paid', payment_ref = ? WHERE id = ?",
            (payment_ref, order_id),
        )
        conn.execute("UPDATE carts SET status = 'checked_out' WHERE id = ?", (cart_id,))
    try:
        inventory.commit(reservation_id)
    except InventoryUnavailable:
        pass  # stock stays held; the reservation is reconciled by the inventory system
    return order_view(conn, order_id), False
