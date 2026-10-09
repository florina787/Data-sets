"""Commerce persistence (SQLite). Schema is shared by every storefront revision."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    token TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS carts (
    id TEXT PRIMARY KEY,
    customer_id TEXT,
    province TEXT,
    discount_code TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cart_lines (
    cart_id TEXT NOT NULL,
    sku TEXT NOT NULL,
    qty INTEGER NOT NULL CHECK (qty > 0),
    is_free INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (cart_id, sku, is_free)
);
CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    cart_id TEXT NOT NULL,
    customer_id TEXT,
    idempotency_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    province TEXT,
    subtotal_cents INTEGER NOT NULL,
    discount_cents INTEGER NOT NULL,
    total_cents INTEGER NOT NULL,
    refunded_cents INTEGER NOT NULL DEFAULT 0,
    reservation_id TEXT,
    payment_ref TEXT,
    campaign_id TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS order_units (
    order_id TEXT NOT NULL,
    unit_index INTEGER NOT NULL,
    sku TEXT NOT NULL,
    list_price_cents INTEGER NOT NULL,
    paid_cents INTEGER NOT NULL,
    is_free INTEGER NOT NULL DEFAULT 0,
    in_promo_group INTEGER NOT NULL DEFAULT 0,
    returned INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (order_id, unit_index)
);
CREATE TABLE IF NOT EXISTS refunds (
    id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
"""

SEED_CUSTOMERS = (
    ("CUST-1001", "Amara Okafor (demo)", "cust-amara-demo"),
    ("CUST-1002", "Luc Tremblay (demo)", "cust-luc-demo"),
    ("CUST-1003", "Priya Raman (demo)", "cust-priya-demo"),
)


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=10, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def init_db(path: str, extra_schema: str = "") -> None:
    conn = connect(path)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA + extra_schema)
        conn.executemany(
            "INSERT OR IGNORE INTO customers (id, display_name, token) VALUES (?, ?, ?)",
            SEED_CUSTOMERS,
        )
    finally:
        conn.close()


@contextmanager
def tx(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Serialised write transaction (BEGIN IMMEDIATE)."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
