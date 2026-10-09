"""Inventory dependency resilience (REQ-9, added after incident INC-001).

The inventory system is replaced by a real local HTTP server whose reserve
endpoint can be made slow, reproducing the timeout observed in production
telemetry. The storefront must fail fast, keep the cart, and create no order.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from conftest import free_lines

from storefront.inventory_adapter import HttpInventory

pytestmark = pytest.mark.critical

SLOW_SECONDS = 4.0
CHECKOUT_BUDGET_SECONDS = 3.0


class FakeInventory:
    def __init__(self) -> None:
        self.slow = False
        self.reservations = 0
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:  # keep test output clean
                pass

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", 0))
                json.loads(self.rfile.read(length) or b"{}")
                if outer.slow:
                    time.sleep(SLOW_SECONDS)
                    self._send(504, {"error": "upstream_timeout"})
                    return
                if self.path.endswith("/reserve"):
                    outer.reservations += 1
                    self._send(200, {"reservation_id": f"RSV-{outer.reservations}"})
                else:
                    self._send(200, {"ok": True})

            def _send(self, status: int, body: dict) -> None:
                data = json.dumps(body).encode()
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass  # the client gave up, which is what a bounded timeout does

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def fake_inventory():
    inventory = FakeInventory()
    yield inventory
    inventory.close()


def orders_count(shop) -> int:
    with sqlite3.connect(shop.db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]


@pytest.mark.ac("AC-9.1")
@pytest.mark.regression("REG-002")
def test_inventory_timeout_fails_fast_preserves_cart_and_creates_no_order(
    make_shop, fake_inventory
):
    shop = make_shop(inventory=HttpInventory(fake_inventory.url))
    cart = shop.qualifying_cart()
    before = shop.quote(cart)
    fake_inventory.slow = True

    started = time.perf_counter()
    response = shop.checkout(cart, "key-timeout-1")
    elapsed = time.perf_counter() - started

    assert response.status_code == 503, response.text
    assert response.json()["error"] == "checkout_temporarily_unavailable"
    assert elapsed < CHECKOUT_BUDGET_SECONDS, f"checkout took {elapsed:.1f}s"
    assert orders_count(shop) == 0
    after = shop.quote(cart)
    assert after["lines"] == before["lines"]
    assert len(free_lines(after)) == 1


@pytest.mark.ac("AC-9.2")
@pytest.mark.regression("REG-002")
def test_checkout_recovers_when_inventory_responds_again(make_shop, fake_inventory):
    shop = make_shop(inventory=HttpInventory(fake_inventory.url))
    cart = shop.qualifying_cart()
    fake_inventory.slow = True
    assert shop.checkout(cart, "key-recover-1").status_code == 503
    fake_inventory.slow = False
    response = shop.checkout(cart, "key-recover-2")
    assert response.status_code == 201, response.text
    assert response.json()["order"]["status"] == "paid"
