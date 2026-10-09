"""Cart quotes. Quotes are read-only views and never consume stock or entitlements."""

from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime

from storefront import cart as carts
from storefront import promotions
from storefront.catalog import get_product
from storefront.errors import CommerceError, Conflict

DISCOUNT_CODES = {"WELCOME10": 10}  # code -> percent off the subtotal


@dataclass
class QuoteLine:
    sku: str
    name: str
    qty: int
    unit_price_cents: int
    line_total_cents: int
    is_free: bool = False


@dataclass
class Quote:
    cart_id: str
    customer_id: str | None
    province: str | None
    lines: list[QuoteLine]
    subtotal_cents: int
    discount_code: str | None
    discount_cents: int
    total_cents: int
    promotion: dict | None = None
    messages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def allocate(total_cents: int, weights: list[int]) -> list[int]:
    """Split ``total_cents`` across ``weights`` exactly (largest-remainder method)."""
    if not weights:
        return []
    weight_sum = sum(weights)
    if weight_sum == 0:
        base = [total_cents // len(weights)] * len(weights)
        for i in range(total_cents - sum(base)):
            base[i] += 1
        return base
    raw = [total_cents * w / weight_sum for w in weights]
    shares = [int(x) for x in raw]
    order = sorted(range(len(weights)), key=lambda i: (-(raw[i] - shares[i]), i))
    for i in order[: total_cents - sum(shares)]:
        shares[i] += 1
    return shares


def set_discount(conn: sqlite3.Connection, cart_id: str, code: str | None) -> None:
    if code is not None:
        code = code.strip().upper()
        if code not in DISCOUNT_CODES:
            raise CommerceError("Unknown discount code", code=code)
        if carts.free_lines(conn, cart_id):
            raise Conflict(
                "Discount codes cannot be combined with the FreshSip free unit."
                " Remove the free unit first.",
                reason="not_combinable_with_discount_codes",
            )
    conn.execute("UPDATE carts SET discount_code = ? WHERE id = ?", (code, cart_id))


def compute_quote(conn: sqlite3.Connection, cart_id: str, now: datetime) -> Quote:
    cart = carts.get_cart(conn, cart_id)
    lines: list[QuoteLine] = []
    for row in carts.paid_lines(conn, cart_id):
        product = get_product(row["sku"])
        lines.append(
            QuoteLine(
                sku=product.sku,
                name=product.name,
                qty=row["qty"],
                unit_price_cents=product.price_cents,
                line_total_cents=product.price_cents * row["qty"],
            )
        )
    evaluation = promotions.evaluate(conn, cart, now)
    free = carts.free_lines(conn, cart_id)
    messages: list[str] = []
    if free and not evaluation.entitled and cart["status"] == "open":
        # Entitlement is re-derived on every recompute: removing qualifying paid
        # units (or any other rule change) removes the free unit from the cart.
        promotions.remove_free_unit(conn, cart_id)
        free = []
        messages.append(
            "Free unit removed: "
            + " ".join(promotions.REASON_TEXT[r] for r in evaluation.reasons)
        )
    for row in free:
        product = get_product(row["sku"])
        lines.append(
            QuoteLine(
                sku=product.sku,
                name=product.name,
                qty=row["qty"],
                unit_price_cents=0,
                line_total_cents=0,
                is_free=True,
            )
        )
    subtotal = sum(line.line_total_cents for line in lines)
    code = cart["discount_code"]
    discount = subtotal * DISCOUNT_CODES[code] // 100 if code else 0
    return Quote(
        cart_id=cart_id,
        customer_id=cart["customer_id"],
        province=cart["province"],
        lines=lines,
        subtotal_cents=subtotal,
        discount_code=code,
        discount_cents=discount,
        total_cents=subtotal - discount,
        promotion=promotions.summary(evaluation, free),
        messages=messages,
    )
