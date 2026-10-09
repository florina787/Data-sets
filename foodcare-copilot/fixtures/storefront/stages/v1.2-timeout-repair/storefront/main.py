"""FreshSip storefront HTTP API. Start with ``uvicorn storefront.main:create_app --factory``."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Iterator

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import storefront
from storefront import cart as carts
from storefront import checkout as checkout_mod
from storefront import db, pricing, promotions, returns, telemetry
from storefront.catalog import PRODUCTS, PROVINCES
from storefront.clock import Clock
from storefront.config import Settings
from storefront.errors import CommerceError
from storefront.inventory_adapter import HttpInventory, InventoryAdapter

FEATURES: dict[str, bool] = {"campaign": True}
EXTRA_SCHEMA = promotions.REDEMPTION_SCHEMA


class QtyBody(BaseModel):
    qty: int = Field(ge=0, le=99)


class ShippingBody(BaseModel):
    province: str | None


class DiscountBody(BaseModel):
    code: str = Field(min_length=1, max_length=32)


class FreeUnitBody(BaseModel):
    sku: str = Field(min_length=1, max_length=40)


class CheckoutBody(BaseModel):
    payment_token: str = Field(min_length=1, max_length=64)
    idempotency_key: str = Field(min_length=8, max_length=80)


class ReturnBody(BaseModel):
    items: dict[str, int]


def create_app(
    settings: Settings | None = None, inventory: InventoryAdapter | None = None
) -> FastAPI:
    settings = settings or Settings.from_env()
    db.init_db(settings.commerce_db, EXTRA_SCHEMA)
    tel = telemetry.configure(settings.telemetry_path, settings.revision, settings.release_id)
    clock = Clock(settings.demo_clock)
    app = FastAPI(title="FreshSip Storefront (demo)")
    app.state.inventory = inventory or HttpInventory(settings.inventory_url)

    @app.middleware("http")
    async def record_request(request: Request, call_next):
        started = time.perf_counter()
        status, error = 500, "unhandled_exception"
        try:
            response = await call_next(request)
            status = response.status_code
            error = getattr(request.state, "error_code", None)
            return response
        finally:
            route = request.scope.get("route")
            if request.url.path.startswith("/api") or request.url.path == "/health":
                tel.emit(
                    "request",
                    method=request.method,
                    route=getattr(route, "path", request.url.path),
                    status=status,
                    error=error,
                    latency_ms=round((time.perf_counter() - started) * 1000, 1),
                )

    @app.exception_handler(CommerceError)
    async def commerce_error(request: Request, exc: CommerceError) -> JSONResponse:
        request.state.error_code = exc.code
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.code, "message": exc.message, "details": exc.details},
        )

    def get_conn() -> Iterator[sqlite3.Connection]:
        conn = db.connect(settings.commerce_db)
        try:
            yield conn
        finally:
            conn.close()

    def get_customer(
        conn: sqlite3.Connection = Depends(get_conn),
        x_demo_customer: str | None = Header(default=None),
    ) -> str | None:
        if not x_demo_customer:
            return None
        row = conn.execute(
            "SELECT id FROM customers WHERE token = ?", (x_demo_customer,)
        ).fetchone()
        if row is None:
            raise CommerceError("Unknown demo customer token")
        return row["id"]

    def open_cart(conn: sqlite3.Connection, cart_id: str, customer: str | None) -> None:
        cart = carts.get_cart(conn, cart_id)
        carts.require_access(cart, customer)
        carts.require_open(cart)

    def cart_payload(conn: sqlite3.Connection, cart_id: str) -> dict:
        cart = carts.get_cart(conn, cart_id)
        quote = pricing.compute_quote(conn, cart_id, clock.now())
        return {"cart_id": cart_id, "status": cart["status"], "quote": quote.to_dict()}

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "revision": settings.revision, "release_id": settings.release_id}

    @app.get("/api/meta")
    def meta() -> dict:
        return {
            "service": "freshsip-storefront",
            "code_version": storefront.CODE_VERSION,
            "revision": settings.revision,
            "release_id": settings.release_id,
            "features": FEATURES,
            "clock": {"now": clock.now().isoformat(), "fixed": clock.is_fixed},
            "demo": True,
        }

    @app.get("/api/catalog")
    def catalog() -> dict:
        return {
            "products": [p.__dict__ for p in PRODUCTS],
            "provinces": list(PROVINCES),
        }

    @app.get("/api/customers")
    def customers(conn: sqlite3.Connection = Depends(get_conn)) -> dict:
        rows = conn.execute("SELECT id, display_name, token FROM customers ORDER BY id").fetchall()
        return {"customers": [dict(r) for r in rows], "note": "Synthetic demo identities"}

    @app.post("/api/carts", status_code=201)
    def new_cart(
        conn: sqlite3.Connection = Depends(get_conn), customer: str | None = Depends(get_customer)
    ) -> dict:
        cart_id = carts.create_cart(conn, customer, clock.now())
        return cart_payload(conn, cart_id)

    @app.get("/api/carts/{cart_id}")
    def read_cart(
        cart_id: str,
        conn: sqlite3.Connection = Depends(get_conn),
        customer: str | None = Depends(get_customer),
    ) -> dict:
        carts.require_access(carts.get_cart(conn, cart_id), customer)
        return cart_payload(conn, cart_id)

    @app.put("/api/carts/{cart_id}/lines/{sku}")
    def put_line(
        cart_id: str,
        sku: str,
        body: QtyBody,
        conn: sqlite3.Connection = Depends(get_conn),
        customer: str | None = Depends(get_customer),
    ) -> dict:
        open_cart(conn, cart_id, customer)
        carts.set_line_qty(conn, cart_id, sku, body.qty)
        return cart_payload(conn, cart_id)

    @app.put("/api/carts/{cart_id}/shipping")
    def put_shipping(
        cart_id: str,
        body: ShippingBody,
        conn: sqlite3.Connection = Depends(get_conn),
        customer: str | None = Depends(get_customer),
    ) -> dict:
        open_cart(conn, cart_id, customer)
        carts.set_province(conn, cart_id, body.province)
        return cart_payload(conn, cart_id)

    @app.put("/api/carts/{cart_id}/discount")
    def put_discount(
        cart_id: str,
        body: DiscountBody,
        conn: sqlite3.Connection = Depends(get_conn),
        customer: str | None = Depends(get_customer),
    ) -> dict:
        open_cart(conn, cart_id, customer)
        pricing.set_discount(conn, cart_id, body.code)
        return cart_payload(conn, cart_id)

    @app.delete("/api/carts/{cart_id}/discount")
    def delete_discount(
        cart_id: str,
        conn: sqlite3.Connection = Depends(get_conn),
        customer: str | None = Depends(get_customer),
    ) -> dict:
        open_cart(conn, cart_id, customer)
        pricing.set_discount(conn, cart_id, None)
        return cart_payload(conn, cart_id)

    register_campaign_routes(app, get_conn, get_customer, open_cart, cart_payload, clock)

    @app.post("/api/carts/{cart_id}/checkout")
    def post_checkout(
        cart_id: str,
        body: CheckoutBody,
        conn: sqlite3.Connection = Depends(get_conn),
        customer: str | None = Depends(get_customer),
    ) -> JSONResponse:
        order, replayed = checkout_mod.checkout(
            conn, app.state.inventory, cart_id, customer,
            body.payment_token, body.idempotency_key, clock.now(),
        )
        return JSONResponse(
            status_code=200 if replayed else 201, content={"order": order, "replayed": replayed}
        )

    @app.get("/api/orders/{order_id}")
    def read_order(
        order_id: str,
        conn: sqlite3.Connection = Depends(get_conn),
        customer: str | None = Depends(get_customer),
    ) -> dict:
        returns._load(conn, order_id, customer)
        return {"order": checkout_mod.order_view(conn, order_id)}

    @app.post("/api/orders/{order_id}/cancel")
    def cancel(
        order_id: str,
        conn: sqlite3.Connection = Depends(get_conn),
        customer: str | None = Depends(get_customer),
    ) -> dict:
        order = returns.cancel_order(conn, app.state.inventory, order_id, customer, clock.now())
        return {"order": order}

    @app.post("/api/orders/{order_id}/returns")
    def partial_return(
        order_id: str,
        body: ReturnBody,
        conn: sqlite3.Connection = Depends(get_conn),
        customer: str | None = Depends(get_customer),
    ) -> dict:
        order = returns.return_units(
            conn, app.state.inventory, order_id, customer, body.items, clock.now()
        )
        return {"order": order}

    if settings.static_dir and Path(settings.static_dir).is_dir():
        app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="static")
    return app


def register_campaign_routes(app, get_conn, get_customer, open_cart, cart_payload, clock) -> None:
    @app.get("/api/campaign")
    def campaign() -> dict:
        start, end = promotions.window_utc()
        c = promotions.CAMPAIGN
        return {
            "id": c.id,
            "name": c.name,
            "eligible_skus": list(c.eligible_skus),
            "province": c.province,
            "timezone": c.timezone,
            "start_local": c.start_local,
            "end_local_exclusive": c.end_local,
            "window_utc": [start.isoformat(), end.isoformat()],
            "active_now": promotions.is_active(clock.now()),
        }

    @app.post("/api/carts/{cart_id}/free-unit")
    def claim_free(
        cart_id: str,
        body: FreeUnitBody,
        conn: sqlite3.Connection = Depends(get_conn),
        customer: str | None = Depends(get_customer),
    ) -> dict:
        open_cart(conn, cart_id, customer)
        promotions.claim_free_unit(conn, cart_id, body.sku, clock.now())
        return cart_payload(conn, cart_id)

    @app.delete("/api/carts/{cart_id}/free-unit")
    def drop_free(
        cart_id: str,
        conn: sqlite3.Connection = Depends(get_conn),
        customer: str | None = Depends(get_customer),
    ) -> dict:
        open_cart(conn, cart_id, customer)
        promotions.remove_free_unit(conn, cart_id)
        return cart_payload(conn, cart_id)
