"""Synthetic shopper traffic against the locally deployed storefront.

Journeys are real HTTP calls; the results (status codes, latencies, whether
the cart survived a failed checkout) are measured, not scripted.
"""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx

from app.config import get_settings
from app.records import evidence

CUSTOMERS = ["cust-luc-demo", "cust-priya-demo", "cust-amara-demo"]


def _journey(index: int, claim_free: bool) -> dict:
    base = get_settings().storefront_url
    headers = {"X-Demo-Customer": CUSTOMERS[index % len(CUSTOMERS)]}
    steps: list[dict] = []
    with httpx.Client(base_url=base, headers=headers, timeout=15) as client:
        def call(name: str, method: str, path: str, **kwargs) -> httpx.Response | None:
            started = time.perf_counter()
            try:
                try:
                    response = client.request(method, path, **kwargs)
                except (httpx.ReadError, httpx.RemoteProtocolError):
                    if method != "GET":
                        raise
                    # The server closes keep-alive connections after an unhandled 500;
                    # retry an idempotent read once on a fresh connection.
                    response = client.request(method, path, **kwargs)
                steps.append({"step": name, "status": response.status_code,
                              "latency_ms": round((time.perf_counter() - started) * 1000, 1)})
                return response
            except httpx.HTTPError as exc:
                steps.append({"step": name, "status": None, "error": type(exc).__name__,
                              "latency_ms": round((time.perf_counter() - started) * 1000, 1)})
                return None

        created = call("create_cart", "POST", "/api/carts")
        if created is None or created.status_code != 201:
            return {"journey": index, "steps": steps, "outcome": "cart_failed"}
        cart_id = created.json()["cart_id"]
        call("add_items", "PUT", f"/api/carts/{cart_id}/lines/FS-MANGO-355", json={"qty": 2})
        call("shipping", "PUT", f"/api/carts/{cart_id}/shipping", json={"province": "ON"})
        if claim_free:
            call("claim_free", "POST", f"/api/carts/{cart_id}/free-unit", json={"sku": "FS-ORANGE-355"})
        before = call("quote_before", "GET", f"/api/carts/{cart_id}")
        checkout = call("checkout", "POST", f"/api/carts/{cart_id}/checkout",
                        json={"payment_token": "tok_demo_ok", "idempotency_key": f"synthetic-{uuid.uuid4().hex}"})
        result = {"journey": index, "cart_id": cart_id, "steps": steps}
        if checkout is None:
            result["outcome"] = "checkout_transport_error"
        elif checkout.status_code == 201:
            result["outcome"] = "order_created"
            result["order_id"] = checkout.json()["order"]["id"]
        else:
            result["outcome"] = f"checkout_{checkout.status_code}"
            after = call("quote_after", "GET", f"/api/carts/{cart_id}")
            if before is not None and after is not None and after.status_code == 200:
                result["cart_preserved"] = (
                    before.json()["quote"]["lines"] == after.json()["quote"]["lines"]
                    and after.json()["status"] == "open"
                )
            try:
                result["error_body"] = checkout.json()
            except ValueError:
                result["error_body"] = {"raw": checkout.text[:200]}
        return result


def generate(journeys: int = 3, run_id: str | None = None, revision: str | None = None) -> dict:
    journeys = max(1, min(journeys, 10))
    meta = {}
    try:
        meta = httpx.get(f"{get_settings().storefront_url}/api/meta", timeout=3).json()
    except (httpx.HTTPError, ValueError):
        pass
    claim = bool(meta.get("features", {}).get("campaign"))
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=journeys) as pool:
        results = list(pool.map(lambda i: _journey(i, claim), range(journeys)))
    checkout_latencies = [s["latency_ms"] for r in results for s in r["steps"] if s["step"] == "checkout"]
    outcomes: dict[str, int] = {}
    for r in results:
        outcomes[r["outcome"]] = outcomes.get(r["outcome"], 0) + 1
    report = {
        "journeys": results,
        "outcomes": outcomes,
        "revision": meta.get("revision"),
        "release_id": meta.get("release_id"),
        "max_checkout_ms": max(checkout_latencies) if checkout_latencies else None,
        "carts_preserved_after_failure": [r.get("cart_preserved") for r in results if "cart_preserved" in r],
        "elapsed_s": round(time.perf_counter() - started, 2),
    }
    evidence("synthetic_traffic", "traffic generator",
             f"{journeys} journeys on {str(meta.get('revision'))[:10]}: {outcomes}", "tool",
             revision=meta.get("revision") or revision, run_id=run_id)
    return report
