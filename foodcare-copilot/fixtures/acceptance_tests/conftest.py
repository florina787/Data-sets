"""Acceptance-test harness owned by the QA agent.

These tests are specified from the approved acceptance criteria, not from the
candidate implementation. They are copied from the control room's fixture
store into every test run; candidate patches cannot modify them. Each test is
tagged with the acceptance criteria it verifies via ``@pytest.mark.ac(...)``.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from storefront.config import Settings
from storefront.inventory_adapter import InMemoryInventory
from storefront.main import create_app

DEMO_NOW = "2026-10-31T12:00:00-04:00"  # inside the campaign window
DEFAULT_STOCK = {
    "FS-MANGO-355": 50,
    "FS-ORANGE-355": 50,
    "FS-APPLE-355": 50,
    "FS-SPARKLIME-355": 50,
    "BH-COLDBREW-300": 50,
    "NT-OATMILK-1L": 50,
}
AMARA = "cust-amara-demo"
LUC = "cust-luc-demo"
OK_CARD = "tok_demo_ok"
DECLINED_CARD = "tok_demo_decline"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "ac(*ids): acceptance criteria verified by the test")
    config.addinivalue_line("markers", "critical: must pass before release")
    config.addinivalue_line("markers", "regression(id): preserved regression test")


@dataclass
class Shop:
    client: TestClient
    inventory: object
    db_path: Path

    def headers(self, customer: str | None) -> dict:
        return {"X-Demo-Customer": customer} if customer else {}

    def new_cart(self, customer: str | None = AMARA, province: str | None = "ON") -> str:
        response = self.client.post("/api/carts", headers=self.headers(customer))
        assert response.status_code == 201, response.text
        cart_id = response.json()["cart_id"]
        if province:
            self.ship_to(cart_id, province, customer)
        return cart_id

    def set_qty(self, cart_id: str, sku: str, qty: int, customer: str | None = AMARA):
        return self.client.put(
            f"/api/carts/{cart_id}/lines/{sku}", json={"qty": qty}, headers=self.headers(customer)
        )

    def ship_to(self, cart_id: str, province: str | None, customer: str | None = AMARA):
        return self.client.put(
            f"/api/carts/{cart_id}/shipping",
            json={"province": province},
            headers=self.headers(customer),
        )

    def claim_free(self, cart_id: str, sku: str, customer: str | None = AMARA):
        return self.client.post(
            f"/api/carts/{cart_id}/free-unit", json={"sku": sku}, headers=self.headers(customer)
        )

    def apply_code(self, cart_id: str, code: str, customer: str | None = AMARA):
        return self.client.put(
            f"/api/carts/{cart_id}/discount", json={"code": code}, headers=self.headers(customer)
        )

    def quote(self, cart_id: str, customer: str | None = AMARA) -> dict:
        response = self.client.get(f"/api/carts/{cart_id}", headers=self.headers(customer))
        assert response.status_code == 200, response.text
        return response.json()["quote"]

    def checkout(
        self, cart_id: str, key: str, customer: str | None = AMARA, card: str = OK_CARD
    ):
        return self.client.post(
            f"/api/carts/{cart_id}/checkout",
            json={"payment_token": card, "idempotency_key": key},
            headers=self.headers(customer),
        )

    def qualifying_cart(self, customer: str = AMARA) -> str:
        cart_id = self.new_cart(customer)
        assert self.set_qty(cart_id, "FS-MANGO-355", 2, customer).status_code == 200
        response = self.claim_free(cart_id, "FS-ORANGE-355", customer)
        assert response.status_code == 200, response.text
        return cart_id


@pytest.fixture
def make_shop(tmp_path: Path):
    created: list[Shop] = []

    def factory(stock: dict | None = None, clock: str = DEMO_NOW, inventory=None) -> Shop:
        db_path = tmp_path / f"commerce-{len(created)}.db"
        inv = inventory or InMemoryInventory(stock or DEFAULT_STOCK)
        app = create_app(Settings(commerce_db=str(db_path), demo_clock=clock), inv)
        shop = Shop(TestClient(app, raise_server_exceptions=False), inv, db_path)
        created.append(shop)
        return shop

    return factory


@pytest.fixture
def shop(make_shop) -> Shop:
    return make_shop()


def free_lines(quote: dict) -> list[dict]:
    return [line for line in quote["lines"] if line["is_free"]]


# --- JSON evidence report -------------------------------------------------

_RESULTS: dict[str, dict] = {}


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call):
    outcome = yield
    report = outcome.get_result()
    entry = _RESULTS.setdefault(
        item.nodeid,
        {
            "nodeid": item.nodeid,
            "acceptance_criteria": [a for m in item.iter_markers("ac") for a in m.args],
            "regression_ids": [a for m in item.iter_markers("regression") for a in m.args],
            "critical": item.get_closest_marker("critical") is not None,
            "outcome": "passed",
            "duration_s": 0.0,
            "message": None,
        },
    )
    entry["duration_s"] = round(entry["duration_s"] + report.duration, 4)
    if report.failed:
        entry["outcome"] = "failed" if report.when == "call" else "error"
        entry["message"] = str(report.longrepr)[-2500:]
    elif report.skipped and report.when != "teardown":
        entry["outcome"] = "skipped"


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    target = os.environ.get("ACCEPTANCE_REPORT")
    if target:
        Path(target).write_text(
            json.dumps(
                {"exit_status": int(exitstatus), "finished_at": time.time(),
                 "tests": list(_RESULTS.values())},
                indent=2,
            )
        )
