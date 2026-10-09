"""Inventory adapter: reservation-based stock control against the inventory system."""

from __future__ import annotations

import threading
import time
import uuid
from typing import Protocol

import httpx

from storefront import telemetry

INVENTORY_TIMEOUT_SECONDS = 1.5


class OutOfStock(Exception):
    def __init__(self, sku: str) -> None:
        super().__init__(f"Insufficient stock for {sku}")
        self.sku = sku


class InventoryUnavailable(Exception):
    """The inventory system did not answer in time or failed."""


class InventoryAdapter(Protocol):
    def reserve(self, units: dict[str, int], key: str) -> str: ...

    def commit(self, reservation_id: str) -> None: ...

    def release(self, reservation_id: str) -> None: ...

    def restock(self, units: dict[str, int], key: str) -> None: ...


class InMemoryInventory:
    """Thread-safe in-process inventory used by tests."""

    def __init__(self, stock: dict[str, int], delay_seconds: float = 0.0) -> None:
        self.stock = dict(stock)
        self.delay_seconds = delay_seconds
        self.reservations: dict[str, dict] = {}
        self._by_key: dict[str, str] = {}
        self._restocked: set[str] = set()
        self._lock = threading.Lock()

    def reserve(self, units: dict[str, int], key: str) -> str:
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        with self._lock:
            if key in self._by_key:
                return self._by_key[key]
            for sku, qty in units.items():
                if self.stock.get(sku, 0) < qty:
                    raise OutOfStock(sku)
            for sku, qty in units.items():
                self.stock[sku] -= qty
            reservation_id = "RSV-" + uuid.uuid4().hex[:10]
            self.reservations[reservation_id] = {"units": dict(units), "state": "held"}
            self._by_key[key] = reservation_id
            return reservation_id

    def commit(self, reservation_id: str) -> None:
        with self._lock:
            self.reservations[reservation_id]["state"] = "committed"

    def release(self, reservation_id: str) -> None:
        with self._lock:
            reservation = self.reservations[reservation_id]
            if reservation["state"] == "held":
                for sku, qty in reservation["units"].items():
                    self.stock[sku] += qty
                reservation["state"] = "released"

    def restock(self, units: dict[str, int], key: str) -> None:
        with self._lock:
            if key in self._restocked:
                return
            for sku, qty in units.items():
                self.stock[sku] = self.stock.get(sku, 0) + qty
            self._restocked.add(key)


class HttpInventory:
    """Client for the inventory system HTTP API (simulated by the control room)."""

    def __init__(self, base_url: str, timeout_seconds: float = INVENTORY_TIMEOUT_SECONDS) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=httpx.Timeout(timeout_seconds))

    def _post(self, operation: str, path: str, payload: dict) -> dict:
        with telemetry.get().timed("inventory", operation):
            try:
                response = self._client.post(f"{self.base_url}{path}", json=payload)
            except httpx.HTTPError as exc:
                raise InventoryUnavailable(str(exc)) from exc
            if response.status_code == 409:
                raise OutOfStock(response.json().get("sku", "unknown"))
            if response.status_code >= 400:
                raise InventoryUnavailable(f"inventory returned HTTP {response.status_code}")
            return response.json()

    def reserve(self, units: dict[str, int], key: str) -> str:
        return self._post("reserve", "/reserve", {"key": key, "units": units})["reservation_id"]

    def commit(self, reservation_id: str) -> None:
        self._post("commit", "/commit", {"reservation_id": reservation_id})

    def release(self, reservation_id: str) -> None:
        self._post("release", "/release", {"reservation_id": reservation_id})

    def restock(self, units: dict[str, int], key: str) -> None:
        self._post("restock", "/restock", {"key": key, "units": units})
