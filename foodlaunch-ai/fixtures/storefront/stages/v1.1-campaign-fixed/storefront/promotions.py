"""FreshSip Ontario weekend campaign: buy two eligible units, get one free.

Rules come from the approved requirement set (brief v1 + recorded clarification
decisions). They are configuration, not inferred at runtime.
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from storefront import cart as carts
from storefront.errors import CommerceError, Conflict


@dataclass(frozen=True)
class Campaign:
    id: str
    name: str
    eligible_skus: tuple[str, ...]
    required_paid_units: int
    free_units: int
    max_free_per_customer: int
    province: str
    timezone: str
    start_local: str  # inclusive, local wall-clock time
    end_local: str  # exclusive, local wall-clock time


CAMPAIGN = Campaign(
    id="FS-ON-WKND-B2G1-2026-10",
    name="FreshSip Ontario Weekend: buy 2, get 1 free",
    eligible_skus=("FS-MANGO-355", "FS-ORANGE-355", "FS-APPLE-355"),
    required_paid_units=2,
    free_units=1,
    max_free_per_customer=1,
    province="ON",
    timezone="America/Toronto",
    start_local="2026-10-31T00:00:00",
    end_local="2026-11-02T00:00:00",
)

REDEMPTION_SCHEMA = """
CREATE TABLE IF NOT EXISTS redemptions (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    order_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_redemption_per_customer
    ON redemptions (customer_id, campaign_id) WHERE status IN ('pending', 'committed');
"""

REASON_TEXT = {
    "campaign_not_active": "The campaign is not running at this time.",
    "sign_in_required": "Sign in as a customer to receive the free unit.",
    "shipping_province_not_eligible": "Free unit is only available for shipping to Ontario.",
    "not_combinable_with_discount_codes": "The offer cannot be combined with discount codes.",
    "already_redeemed": "You have already received your free unit for this campaign.",
    "needs_two_paid_eligible_units": "Add two paid FreshSip mango, orange or apple units.",
}


def to_utc(local_iso: str, tz_name: str) -> datetime:
    """Convert a local wall-clock time to UTC, rejecting DST-ambiguous or skipped times."""
    tz = ZoneInfo(tz_name)
    naive = datetime.fromisoformat(local_iso)
    if naive.tzinfo is not None:
        raise ValueError("Campaign times must be local wall-clock times without an offset")
    first, second = naive.replace(tzinfo=tz, fold=0), naive.replace(tzinfo=tz, fold=1)
    if first.utcoffset() != second.utcoffset():
        raise ValueError(f"{local_iso} is ambiguous in {tz_name} (DST change)")
    converted = first.astimezone(timezone.utc)
    if converted.astimezone(tz).replace(tzinfo=None) != naive:
        raise ValueError(f"{local_iso} does not exist in {tz_name} (DST change)")
    return converted


def window_utc(campaign: Campaign = CAMPAIGN) -> tuple[datetime, datetime]:
    return (
        to_utc(campaign.start_local, campaign.timezone),
        to_utc(campaign.end_local, campaign.timezone),
    )


def is_active(now: datetime, campaign: Campaign = CAMPAIGN) -> bool:
    start, end = window_utc(campaign)
    return start <= now.astimezone(timezone.utc) < end


@dataclass
class Evaluation:
    entitled: bool
    paid_eligible_units: int
    reasons: list[str] = field(default_factory=list)


def has_active_redemption(conn: sqlite3.Connection, customer_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM redemptions WHERE customer_id = ? AND campaign_id = ?"
        " AND status IN ('pending', 'committed')",
        (customer_id, CAMPAIGN.id),
    ).fetchone()
    return row is not None


def evaluate(conn: sqlite3.Connection, cart: sqlite3.Row, now: datetime) -> Evaluation:
    paid = carts.paid_lines(conn, cart["id"])
    paid_eligible = sum(r["qty"] for r in paid if r["sku"] in CAMPAIGN.eligible_skus)
    reasons = []
    if not is_active(now):
        reasons.append("campaign_not_active")
    if not cart["customer_id"]:
        reasons.append("sign_in_required")
    if cart["province"] != CAMPAIGN.province:
        reasons.append("shipping_province_not_eligible")
    if cart["discount_code"]:
        reasons.append("not_combinable_with_discount_codes")
    if cart["customer_id"] and has_active_redemption(conn, cart["customer_id"]):
        reasons.append("already_redeemed")
    if paid_eligible < CAMPAIGN.required_paid_units:
        reasons.append("needs_two_paid_eligible_units")
    return Evaluation(entitled=not reasons, paid_eligible_units=paid_eligible, reasons=reasons)


def summary(evaluation: Evaluation, free_lines: list) -> dict:
    start, end = window_utc()
    return {
        "campaign_id": CAMPAIGN.id,
        "name": CAMPAIGN.name,
        "eligible_skus": list(CAMPAIGN.eligible_skus),
        "window_utc": [start.isoformat(), end.isoformat()],
        "timezone": CAMPAIGN.timezone,
        "entitled": evaluation.entitled,
        "free_unit_in_cart": bool(free_lines),
        "paid_eligible_units": evaluation.paid_eligible_units,
        "reasons": evaluation.reasons,
        "reason_text": [REASON_TEXT[r] for r in evaluation.reasons],
    }


def claim_free_unit(conn: sqlite3.Connection, cart_id: str, sku: str, now: datetime) -> None:
    if sku not in CAMPAIGN.eligible_skus:
        raise CommerceError("This product is not part of the campaign", sku=sku)
    cart = carts.get_cart(conn, cart_id)
    if carts.free_lines(conn, cart_id):
        raise Conflict("A free unit is already in the cart")
    evaluation = evaluate(conn, cart, now)
    if not evaluation.entitled:
        raise Conflict(
            "Cart is not eligible for the free unit",
            reasons=evaluation.reasons,
            reason_text=[REASON_TEXT[r] for r in evaluation.reasons],
        )
    conn.execute(
        "INSERT INTO cart_lines (cart_id, sku, qty, is_free) VALUES (?, ?, 1, 1)", (cart_id, sku)
    )


def remove_free_unit(conn: sqlite3.Connection, cart_id: str) -> None:
    conn.execute("DELETE FROM cart_lines WHERE cart_id = ? AND is_free = 1", (cart_id,))


def insert_pending_redemption(
    conn: sqlite3.Connection, customer_id: str, order_id: str, now: datetime
) -> None:
    """Raises sqlite3.IntegrityError if the customer already holds an active redemption."""
    conn.execute(
        "INSERT INTO redemptions (id, customer_id, campaign_id, order_id, status, created_at)"
        " VALUES (?, ?, ?, ?, 'pending', ?)",
        ("RDM-" + uuid.uuid4().hex[:10], customer_id, CAMPAIGN.id, order_id, now.isoformat()),
    )


def set_redemption_status(conn: sqlite3.Connection, order_id: str, status: str) -> None:
    conn.execute("UPDATE redemptions SET status = ? WHERE order_id = ?", (status, order_id))
