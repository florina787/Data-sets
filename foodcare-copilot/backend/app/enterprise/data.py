"""Deterministic synthetic enterprise data (fixed seed, generated from fixtures/enterprise).

The generator is the only place where "true" effects (such as a campaign's
uplift) exist. Everything the copilot and the screens report is measured back
from the generated rows, exactly as it would be from real data.
"""

from __future__ import annotations

import json
import math
import random
from datetime import date, timedelta
from functools import lru_cache

from app.config import FIXTURES
from app.db import session

SCHEMA = """
CREATE TABLE IF NOT EXISTS ent_products (
    sku TEXT PRIMARY KEY, name TEXT NOT NULL, brand TEXT NOT NULL, category TEXT NOT NULL,
    price_cents INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS ent_sales_weekly (
    week_start TEXT NOT NULL, sku TEXT NOT NULL, province TEXT NOT NULL, channel TEXT NOT NULL,
    units INTEGER NOT NULL, revenue_cents INTEGER NOT NULL, campaign_id TEXT,
    PRIMARY KEY (week_start, sku, province, channel)
);
CREATE TABLE IF NOT EXISTS ent_campaigns (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, mechanic TEXT NOT NULL, region TEXT NOT NULL,
    skus_json TEXT NOT NULL, start TEXT NOT NULL, end TEXT NOT NULL, status TEXT NOT NULL, source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ent_warehouses (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, serves_json TEXT NOT NULL, lead_time_days INTEGER NOT NULL,
    safety_days INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS ent_stock (
    warehouse TEXT NOT NULL, sku TEXT NOT NULL, on_hand INTEGER NOT NULL, as_of TEXT NOT NULL,
    PRIMARY KEY (warehouse, sku)
);
CREATE TABLE IF NOT EXISTS ent_inbound (
    po TEXT PRIMARY KEY, warehouse TEXT NOT NULL, sku TEXT NOT NULL, units INTEGER NOT NULL, eta TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ent_product_records (
    sku TEXT NOT NULL, version TEXT NOT NULL, approved_by TEXT NOT NULL, approved_at TEXT NOT NULL,
    ingredients_json TEXT NOT NULL, allergens_json TEXT NOT NULL, current INTEGER NOT NULL,
    PRIMARY KEY (sku, version)
);
CREATE TABLE IF NOT EXISTS ent_listings (
    sku TEXT NOT NULL, channel TEXT NOT NULL, record_version TEXT NOT NULL, ingredients_json TEXT NOT NULL,
    allergens_json TEXT NOT NULL, updated_at TEXT NOT NULL, note TEXT,
    PRIMARY KEY (sku, channel)
);
CREATE TABLE IF NOT EXISTS copilot_messages (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL, ts TEXT NOT NULL, role TEXT NOT NULL,
    username TEXT, content TEXT NOT NULL, answer_json TEXT
);
"""

AS_OF = "2026-10-26"  # stock snapshot date (start of the demo week)


@lru_cache(maxsize=1)
def company() -> dict:
    return json.loads((FIXTURES / "enterprise" / "company.json").read_text())


def weeks() -> list[str]:
    cfg = company()["history"]
    first = date.fromisoformat(cfg["first_week"])
    return [(first + timedelta(weeks=i)).isoformat() for i in range(cfg["weeks"])]


def _season(kind: str, index: int, total: int) -> float:
    position = index / max(total - 1, 1)  # 0 = early July, 1 = late October
    if kind == "summer":
        return 1.15 - 0.30 * position
    if kind == "autumn":
        return 0.90 + 0.25 * position
    return 1.0


def _campaign_for(sku: str, province: str, week: str) -> dict | None:
    for c in company()["campaigns"]:
        if sku in c["skus"] and province == c["region"] and c["start"] <= week <= c["end"]:
            return c
    return None


def generate_sales() -> list[tuple]:
    cfg = company()
    rng = random.Random(cfg["seed"])
    all_weeks = weeks()
    rows = []
    for wi, week in enumerate(all_weeks):
        for product in cfg["products"]:
            season = _season(product["seasonality"], wi, len(all_weeks))
            for province, region in cfg["regions"].items():
                campaign = _campaign_for(product["sku"], province, week)
                for channel, ch in cfg["channels"].items():
                    noise = rng.uniform(0.88, 1.12)
                    units = product["base_weekly_units"] * region["weight"] * ch["weight"] * season * noise
                    discount = 0.0
                    if campaign:
                        units *= campaign["true_uplift"]
                        discount = campaign["discount_share"]
                    units = max(0, round(units))
                    revenue = round(units * product["price_cents"] * ch["net_price_factor"] * (1 - discount))
                    rows.append((week, product["sku"], province, channel, units, revenue,
                                 campaign["id"] if campaign else None))
    return rows


def seed() -> None:
    cfg = company()
    sales = generate_sales()
    with session() as conn:
        conn.executescript(SCHEMA)
        conn.execute("BEGIN")
        for table in ("ent_products", "ent_sales_weekly", "ent_campaigns", "ent_warehouses", "ent_stock",
                      "ent_inbound", "ent_product_records", "ent_listings", "copilot_messages"):
            conn.execute(f"DELETE FROM {table}")
        conn.executemany("INSERT INTO ent_products VALUES (?, ?, ?, ?, ?)",
                         [(p["sku"], p["name"], p["brand"], p["category"], p["price_cents"]) for p in cfg["products"]])
        conn.executemany("INSERT INTO ent_sales_weekly VALUES (?, ?, ?, ?, ?, ?, ?)", sales)
        for c in cfg["campaigns"]:
            conn.execute("INSERT INTO ent_campaigns VALUES (?, ?, ?, ?, ?, ?, ?, 'completed', 'synthetic history')",
                         (c["id"], c["name"], c["mechanic"], c["region"], json.dumps(c["skus"]), c["start"], c["end"]))
        up = cfg["upcoming_campaign"]
        conn.execute("INSERT INTO ent_campaigns VALUES (?, ?, ?, ?, ?, ?, ?, 'scheduled', ?)",
                     (up["id"], up["name"], up["mechanic"], up["region"], json.dumps(up["skus"]), up["start"],
                      up["end"], up["source"]))
        for w in cfg["warehouses"]:
            conn.execute("INSERT INTO ent_warehouses VALUES (?, ?, ?, ?, ?)",
                         (w["id"], w["name"], json.dumps(w["serves"]), w["lead_time_days"], w["safety_days"]))
        recent = weeks()[-4:]
        for w in cfg["warehouses"]:
            for sku, days in cfg["stock_days_of_cover"][w["id"]].items():
                weekly = sum(r[4] for r in sales if r[0] in recent and r[1] == sku and r[2] in w["serves"]) / 4
                conn.execute("INSERT INTO ent_stock VALUES (?, ?, ?, ?)",
                             (w["id"], sku, math.floor(weekly / 7 * days), AS_OF))
        conn.executemany("INSERT INTO ent_inbound VALUES (?, ?, ?, ?, ?)",
                         [(i["po"], i["warehouse"], i["sku"], i["units"], i["eta"]) for i in cfg["inbound"]])
        overrides = {(o["sku"], o["channel"]): o for o in cfg["listing_overrides"]}
        for rec in cfg["product_records"]:
            conn.execute("INSERT INTO ent_product_records VALUES (?, ?, ?, ?, ?, ?, 1)",
                         (rec["sku"], rec["version"], rec["approved_by"], rec["approved_at"],
                          json.dumps(rec["ingredients"]), json.dumps(rec["allergens"])))
            for channel in cfg["channels"]:
                o = overrides.get((rec["sku"], channel), {})
                conn.execute("INSERT INTO ent_listings VALUES (?, ?, ?, ?, ?, ?, ?)",
                             (rec["sku"], channel, o.get("record_version", rec["version"]),
                              json.dumps(o.get("ingredients", rec["ingredients"])),
                              json.dumps(o.get("allergens", rec["allergens"])), "2026-10-20", o.get("note")))
        conn.execute("COMMIT")


def ensure_seeded() -> None:
    with session() as conn:
        conn.executescript(SCHEMA)
        if conn.execute("SELECT COUNT(*) FROM ent_products").fetchone()[0] == 0:
            seeded = False
        else:
            seeded = True
    if not seeded:
        seed()
