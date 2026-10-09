"""Server-side carts."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime

from storefront.catalog import PROVINCES, get_product
from storefront.errors import CommerceError, Conflict, Forbidden, NotFound

MAX_QTY_PER_LINE = 24


def create_cart(conn: sqlite3.Connection, customer_id: str | None, now: datetime) -> str:
    cart_id = "CART-" + uuid.uuid4().hex[:12]
    conn.execute(
        "INSERT INTO carts (id, customer_id, created_at) VALUES (?, ?, ?)",
        (cart_id, customer_id, now.isoformat()),
    )
    return cart_id


def get_cart(conn: sqlite3.Connection, cart_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM carts WHERE id = ?", (cart_id,)).fetchone()
    if row is None:
        raise NotFound("Cart not found", cart_id=cart_id)
    return row


def require_access(cart: sqlite3.Row, customer_id: str | None) -> None:
    if cart["customer_id"] and cart["customer_id"] != customer_id:
        raise Forbidden("This cart belongs to another customer")


def require_open(cart: sqlite3.Row) -> None:
    if cart["status"] != "open":
        raise Conflict("Cart is no longer open", status=cart["status"])


def set_line_qty(conn: sqlite3.Connection, cart_id: str, sku: str, qty: int) -> None:
    try:
        get_product(sku)
    except KeyError:
        raise NotFound("Unknown product", sku=sku) from None
    if qty < 0 or qty > MAX_QTY_PER_LINE:
        raise CommerceError(f"Quantity must be between 0 and {MAX_QTY_PER_LINE}")
    if qty == 0:
        conn.execute(
            "DELETE FROM cart_lines WHERE cart_id = ? AND sku = ? AND is_free = 0", (cart_id, sku)
        )
        return
    conn.execute(
        "INSERT INTO cart_lines (cart_id, sku, qty, is_free) VALUES (?, ?, ?, 0) "
        "ON CONFLICT (cart_id, sku, is_free) DO UPDATE SET qty = excluded.qty",
        (cart_id, sku, qty),
    )


def set_province(conn: sqlite3.Connection, cart_id: str, province: str | None) -> None:
    if province is not None and province not in PROVINCES:
        raise CommerceError("Unknown shipping province", province=province)
    conn.execute("UPDATE carts SET province = ? WHERE id = ?", (province, cart_id))


def paid_lines(conn: sqlite3.Connection, cart_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT sku, qty FROM cart_lines WHERE cart_id = ? AND is_free = 0 ORDER BY sku",
        (cart_id,),
    ).fetchall()


def free_lines(conn: sqlite3.Connection, cart_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT sku, qty FROM cart_lines WHERE cart_id = ? AND is_free = 1 ORDER BY sku",
        (cart_id,),
    ).fetchall()


def snapshot(conn: sqlite3.Connection, cart_id: str) -> list[tuple[str, int, int]]:
    """Stable representation of cart contents, used to prove carts are preserved."""
    rows = conn.execute(
        "SELECT sku, qty, is_free FROM cart_lines WHERE cart_id = ? ORDER BY sku, is_free",
        (cart_id,),
    ).fetchall()
    return [(r["sku"], r["qty"], r["is_free"]) for r in rows]
