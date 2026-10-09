"""Cancellations and partial returns. Refunds use the amounts allocated at order time."""

from __future__ import annotations

import sqlite3
import uuid
from collections import Counter
from datetime import datetime

from storefront.checkout import order_view
from storefront.db import tx
from storefront.errors import CommerceError, Conflict, Forbidden, NotFound
from storefront.inventory_adapter import InventoryAdapter, InventoryUnavailable


def _load(conn: sqlite3.Connection, order_id: str, customer_id: str | None) -> sqlite3.Row:
    order = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order is None:
        raise NotFound("Order not found", order_id=order_id)
    if order["customer_id"] and order["customer_id"] != customer_id:
        raise Forbidden("This order belongs to another customer")
    return order


def _restock_quietly(inventory: InventoryAdapter, units: dict[str, int], key: str) -> None:
    try:
        inventory.restock(units, key)
    except InventoryUnavailable:
        pass  # restock is reconciled later; the refund is already recorded


def _on_cancel(conn: sqlite3.Connection, order: sqlite3.Row) -> None:
    """Hook for revision-specific cancellation effects (runs inside the transaction)."""


def cancel_order(
    conn: sqlite3.Connection,
    inventory: InventoryAdapter,
    order_id: str,
    customer_id: str | None,
    now: datetime,
) -> dict:
    order = _load(conn, order_id, customer_id)
    if order["status"] != "paid":
        raise Conflict("Only paid orders without returns can be cancelled", status=order["status"])
    units = conn.execute(
        "SELECT sku FROM order_units WHERE order_id = ?", (order_id,)
    ).fetchall()
    with tx(conn):
        conn.execute(
            "UPDATE orders SET status = 'cancelled', refunded_cents = total_cents WHERE id = ?",
            (order_id,),
        )
        conn.execute(
            "INSERT INTO refunds (id, order_id, kind, amount_cents, created_at)"
            " VALUES (?, ?, 'cancellation', ?, ?)",
            ("RFD-" + uuid.uuid4().hex[:10], order_id, order["total_cents"], now.isoformat()),
        )
        _on_cancel(conn, order)
    _restock_quietly(inventory, dict(Counter(u["sku"] for u in units)), f"cancel:{order_id}")
    return order_view(conn, order_id)


def return_units(
    conn: sqlite3.Connection,
    inventory: InventoryAdapter,
    order_id: str,
    customer_id: str | None,
    items: dict[str, int],
    now: datetime,
) -> dict:
    """Return units; the refund is the sum of each unit's allocated paid amount.

    Seeded policy: within a SKU, units outside the promotion group are returned
    first, then the most recently purchased units.
    """
    order = _load(conn, order_id, customer_id)
    if order["status"] not in ("paid", "partially_returned"):
        raise Conflict("Order is not eligible for returns", status=order["status"])
    if not items or any(qty <= 0 for qty in items.values()):
        raise CommerceError("Return quantities must be positive")
    chosen: list[sqlite3.Row] = []
    for sku, qty in items.items():
        candidates = conn.execute(
            "SELECT * FROM order_units WHERE order_id = ? AND sku = ? AND returned = 0"
            " ORDER BY in_promo_group ASC, unit_index DESC",
            (order_id, sku),
        ).fetchall()
        if len(candidates) < qty:
            raise CommerceError("Cannot return more units than were purchased", sku=sku)
        chosen.extend(candidates[:qty])
    refund = sum(u["paid_cents"] for u in chosen)
    refund_id = "RFD-" + uuid.uuid4().hex[:10]
    with tx(conn):
        conn.executemany(
            "UPDATE order_units SET returned = 1 WHERE order_id = ? AND unit_index = ?",
            [(order_id, u["unit_index"]) for u in chosen],
        )
        remaining = conn.execute(
            "SELECT COUNT(*) FROM order_units WHERE order_id = ? AND returned = 0", (order_id,)
        ).fetchone()[0]
        conn.execute(
            "UPDATE orders SET refunded_cents = refunded_cents + ?, status = ? WHERE id = ?",
            (refund, "returned" if remaining == 0 else "partially_returned", order_id),
        )
        conn.execute(
            "INSERT INTO refunds (id, order_id, kind, amount_cents, created_at)"
            " VALUES (?, ?, 'partial_return', ?, ?)",
            (refund_id, order_id, refund, now.isoformat()),
        )
    _restock_quietly(inventory, dict(Counter(u["sku"] for u in chosen)), f"return:{refund_id}")
    return order_view(conn, order_id)
