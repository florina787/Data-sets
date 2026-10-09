"""Simulated inventory system (the storefront's external dependency).

It lives in the control-room process only so the demo needs no extra service.
Fault injection is demo-only and clearly labelled: an active fault makes every
inventory call wait ``fault_delay_s`` and then answer 504.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import get_settings
from app.db import kv_get, kv_set, new_id, now_iso, rows, tx
from app.records import audit, evidence

SEED_STOCK = {
    "FS-MANGO-355": 40, "FS-ORANGE-355": 40, "FS-APPLE-355": 6,
    "FS-SPARKLIME-355": 25, "BH-COLDBREW-300": 30, "NT-OATMILK-1L": 20,
}
FAULT_KEY = "fault.inventory_timeout"

router = APIRouter(prefix="/sim/inventory", tags=["inventory simulator (demo)"])


class ReserveBody(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    units: dict[str, int]
    campaign_id: str | None = None


class ReservationBody(BaseModel):
    reservation_id: str


class RestockBody(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    units: dict[str, int]


def seed() -> None:
    with tx() as conn:
        conn.execute("DELETE FROM sim_stock")
        conn.execute("DELETE FROM sim_reservations")
        conn.execute("DELETE FROM sim_restocks")
        conn.executemany("INSERT INTO sim_stock (sku, stock) VALUES (?, ?)", SEED_STOCK.items())
    kv_set(FAULT_KEY, {"active": False})


def fault_state() -> dict:
    return kv_get(FAULT_KEY, {"active": False})


def set_fault(active: bool, actor: str) -> dict:
    state = {"active": active, "delay_s": get_settings().fault_delay_s, "changed_by": actor,
             "changed_at": now_iso(), "kind": "inventory_timeout",
             "label": "Injected fault (demo only)"}
    kv_set(FAULT_KEY, state)
    audit(actor, "fault.inject" if active else "fault.clear", entity_type="fault",
          entity_id="inventory_timeout", delay_s=state["delay_s"])
    evidence("fault_injection", "demo fault control",
             f"Inventory timeout fault {'injected' if active else 'cleared'} by {actor}",
             "injected_fault", ref_table="kv", ref_id=FAULT_KEY)
    return state


async def _maybe_fault() -> JSONResponse | None:
    state = fault_state()
    if state.get("active"):
        await asyncio.sleep(float(state.get("delay_s", 4)))
        return JSONResponse(status_code=504, content={"error": "upstream_timeout", "injected": True})
    return None


@router.get("/stock")
def stock() -> dict:
    return {"stock": {r["sku"]: r["stock"] for r in rows("SELECT * FROM sim_stock ORDER BY sku")},
            "fault": fault_state()}


@router.post("/reserve")
async def reserve(body: ReserveBody):
    if (faulted := await _maybe_fault()) is not None:
        return faulted
    if any(q <= 0 for q in body.units.values()):
        return JSONResponse(status_code=400, content={"error": "invalid_quantity"})
    with tx() as conn:
        existing = conn.execute("SELECT id FROM sim_reservations WHERE key = ?", (body.key,)).fetchone()
        if existing:
            return {"reservation_id": existing["id"], "replayed": True}
        for sku, qty in sorted(body.units.items()):
            found = conn.execute("SELECT stock FROM sim_stock WHERE sku = ?", (sku,)).fetchone()
            if found is None or found["stock"] < qty:
                return JSONResponse(status_code=409, content={"error": "out_of_stock", "sku": sku})
        for sku, qty in body.units.items():
            conn.execute("UPDATE sim_stock SET stock = stock - ? WHERE sku = ?", (qty, sku))
        reservation_id = new_id("RSV")
        conn.execute(
            "INSERT INTO sim_reservations (id, key, units_json, state, campaign_id, created_at)"
            " VALUES (?, ?, ?, 'held', ?, ?)",
            (reservation_id, body.key, json.dumps(body.units), body.campaign_id, now_iso()),
        )
    return {"reservation_id": reservation_id, "replayed": False}


@router.post("/commit")
async def commit(body: ReservationBody):
    if (faulted := await _maybe_fault()) is not None:
        return faulted
    with tx() as conn:
        conn.execute("UPDATE sim_reservations SET state = 'committed' WHERE id = ? AND state = 'held'",
                     (body.reservation_id,))
    return {"ok": True}


@router.post("/release")
async def release(body: ReservationBody):
    if (faulted := await _maybe_fault()) is not None:
        return faulted
    with tx() as conn:
        found = conn.execute("SELECT * FROM sim_reservations WHERE id = ?", (body.reservation_id,)).fetchone()
        if found and found["state"] == "held":
            for sku, qty in json.loads(found["units_json"]).items():
                conn.execute("UPDATE sim_stock SET stock = stock + ? WHERE sku = ?", (qty, sku))
            conn.execute("UPDATE sim_reservations SET state = 'released' WHERE id = ?", (body.reservation_id,))
    return {"ok": True}


@router.post("/restock")
async def restock(body: RestockBody):
    if (faulted := await _maybe_fault()) is not None:
        return faulted
    with tx() as conn:
        if conn.execute("SELECT 1 FROM sim_restocks WHERE key = ?", (body.key,)).fetchone():
            return {"ok": True, "replayed": True}
        for sku, qty in body.units.items():
            conn.execute("UPDATE sim_stock SET stock = stock + ? WHERE sku = ?", (qty, sku))
        conn.execute("INSERT INTO sim_restocks (key, created_at) VALUES (?, ?)", (body.key, now_iso()))
    return {"ok": True, "replayed": False}
