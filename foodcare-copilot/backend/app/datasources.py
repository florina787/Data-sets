"""Potato data sources: what feeds Flo & Jerry, with live record counts and honest status.

``connected`` = records exist and are used now; ``synthetic`` = connected but generated demo
data; ``not_connected`` = a planned source with no integration yet (nothing is simulated).
"""

from __future__ import annotations

from app.db import row
from app.memory.store import get_store


def _count(sql: str, params: tuple = ()) -> int:
    found = get_store().query(sql, params)
    return int(found[0]["n"]) if found else 0


def sources(username: str) -> list[dict]:
    q = _count
    batches = q("SELECT COUNT(*) AS n FROM inspection_batches WHERE username = ?", (username,))
    images = q("SELECT COUNT(*) AS n FROM inspection_items i JOIN inspection_batches b ON b.id = i.batch_id"
               " WHERE b.username = ?", (username,))
    potatoes = q("SELECT COUNT(*) AS n FROM inspection_potatoes p JOIN inspection_batches b ON b.id = p.batch_id"
                 " WHERE b.username = ?", (username,))
    corrections = q("SELECT COUNT(*) AS n FROM inspection_corrections c JOIN inspection_batches b"
                    " ON b.id = c.batch_id WHERE b.username = ?", (username,))
    suppliers = q("SELECT COUNT(DISTINCT supplier) AS n FROM inspection_batches WHERE username = ? AND supplier"
                  " IS NOT NULL AND supplier != ''", (username,))
    evaluations = q("SELECT COUNT(*) AS n FROM ml_evaluations")
    real_datasets = q("SELECT COUNT(*) AS n FROM ml_datasets WHERE synthetic = 0")
    conversations = q("SELECT COUNT(*) AS n FROM conversations WHERE username = ?", (username,))
    sales = (row("SELECT COUNT(*) AS n FROM ent_sales_weekly") or {"n": 0})["n"]
    stock = (row("SELECT COUNT(*) AS n FROM ent_stock") or {"n": 0})["n"]

    def src(key, name, kind, status, records, unit, detail, to=None, needs=None):
        return {"key": key, "name": name, "kind": kind, "status": status, "records": records, "unit": unit,
                "detail": detail, "to": to, "needs": needs}

    return [
        src("photos", "Inspection photos", "vision", "connected" if images else "empty", images, "images",
            f"{batches} batch(es), {potatoes} potatoes measured", "/inspection",
            None if images else "Upload a photo in Potato Inspection"),
        src("corrections", "Inspector corrections", "human review", "connected" if corrections else "empty",
            corrections, "corrections", "Human grade overrides with reasons (future training labels)", "/inspection"),
        src("suppliers", "Supplier & lot records", "traceability", "connected" if suppliers else "empty", suppliers,
            "suppliers", "Entered with each inspection batch; not verified against a supplier system", "/inspection"),
        src("evaluations", "Model evaluations", "ML governance", "connected" if evaluations else "empty",
            evaluations, "reports", f"{real_datasets} real labelled dataset(s) registered", "/evaluation"),
        src("sales", "Sales history", "commercial", "synthetic", sales, "weekly rows",
            "16 weeks × 6 products × 6 regions × 3 channels (generated)", "/sales"),
        src("stock", "Warehouse stock", "supply", "synthetic", stock, "stock lines",
            "Days of cover and purchase orders (generated)", "/inventory"),
        src("conversations", "Jerry conversations", "memory", "connected" if conversations else "empty",
            conversations, "conversations", "Saved questions and answers (SQLite)", "/copilot"),
        src("storage", "Storage sensors", "IoT", "not_connected", 0, "readings",
            "Temperature and humidity of potato stores", None, "A sensor export or API (e.g. CSV, MQTT, OPC UA)"),
        src("weather", "Weather & field data", "agriculture", "not_connected", 0, "records",
            "Growing-season weather and harvest dates", None, "A weather data source and field/lot mapping"),
        src("erp", "ERP / purchasing", "enterprise", "not_connected", 0, "records",
            "Purchase orders, costs and receipts", None, "Read-only ERP export or API with unit costs"),
        src("scales", "Weighing scales", "operations", "not_connected", 0, "weighings",
            "Measured input and waste weights", None, "Scale export; needed for any weight or waste-cost figure"),
        src("video", "Conveyor video", "vision", "not_connected", 0, "videos",
            "Moving-line counting and tracking", None, "Video files or a camera stream"),
    ]
