"""Stripe flows. Unit level: our code against a recording fake of the Stripe client (no network, no Stripe validation).
Spec-level validation runs in CI against the official stripe-mock container (see .github/workflows/careerflo-ci.yml)."""
import hashlib
import hmac
import json
import os
import time
import uuid

import pytest

from app.billing import stripe_service as S
from app.config import get_settings

from .conftest import register


class _Obj(dict):
    def __getattr__(self, k):
        return self[k]

    def to_dict(self):
        return dict(self)


class FakeStripe:
    def __init__(self):
        self.calls = []
        fake = self

        class _NS:
            def __init__(self, name):
                self.name = name

            def create(self, params=None):
                fake.calls.append((self.name, "create", params))
                ids = {"customers": "cus_fake", "checkout.sessions": "cs_fake", "billing_portal.sessions": "bps_fake"}
                return _Obj(id=ids.get(self.name, "x_fake"), url=f"https://checkout.stripe.test/{self.name}", livemode=False)

            def retrieve(self, sid):
                fake.calls.append((self.name, "retrieve", sid))
                return _Obj({"id": sid, "items": {"data": [{"id": "si_fake", "price": {"id": "price_pro_test"}}]}})

            def update(self, sid, params=None):
                fake.calls.append((self.name, "update", (sid, params)))
                return _Obj(id=sid)

        self.customers = _NS("customers")
        self.subscriptions = _NS("subscriptions")
        self.checkout = type("C", (), {"sessions": _NS("checkout.sessions")})()
        self.billing_portal = type("B", (), {"sessions": _NS("billing_portal.sessions")})()
        self.v1 = self  # stripe-python v16+: resources live under client.v1


@pytest.fixture
def fake_stripe(monkeypatch):
    fake = FakeStripe()
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake")
    get_settings.cache_clear()
    monkeypatch.setattr(S, "_client", lambda: fake)
    monkeypatch.setattr(S, "_fetch_subscription", lambda sid: None)
    yield fake
    monkeypatch.undo()
    get_settings.cache_clear()


def test_checkout_portal_change_cancel(client, user, fake_stripe):
    h, u = user
    r = client.post("/api/billing/checkout", headers=h, json={"plan": "pro"})
    assert r.status_code == 200 and r.json()["url"].startswith("https://checkout.stripe.test/")
    _, _, params = next(c for c in fake_stripe.calls if c[0] == "checkout.sessions")
    assert params["mode"] == "subscription" and params["line_items"] == [{"price": "price_pro_test", "quantity": 1}]
    assert params["client_reference_id"] == u["id"] and params["automatic_tax"] == {"enabled": True}
    assert params["success_url"].endswith("/billing/success?session_id={CHECKOUT_SESSION_ID}")
    assert client.get("/api/usage", headers=h).json()["plan"]["id"] == "free"   # redirect alone unlocks nothing
    assert client.post("/api/billing/portal", headers=h).json()["url"]
    # activate via verified webhook, then change plan / cancel / resume
    assert signed(client, sub_event("evt_a" + u["id"][:6], u["id"], "active", 100)).json()["outcome"] == "processed"
    assert client.post("/api/billing/checkout", headers=h, json={"plan": "premium"}).status_code == 409
    assert client.post("/api/billing/change-plan", headers=h, json={"plan": "premium"}).status_code == 200
    _, _, (sid, upd) = [c for c in fake_stripe.calls if c[0] == "subscriptions" and c[1] == "update"][-1]
    assert upd["proration_behavior"] == "create_prorations" and upd["items"][0]["price"] == "price_premium_test"
    assert client.post("/api/billing/cancel", headers=h).json()["cancel_at_period_end"] is True
    assert client.post("/api/billing/resume", headers=h).json()["cancel_at_period_end"] is False


def test_live_keys_refused_without_explicit_flag(client, user, monkeypatch):
    h, _ = user
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_live_should_not_be_used")
    get_settings.cache_clear()
    try:
        r = client.post("/api/billing/checkout", headers=h, json={"plan": "pro"})
        assert r.status_code == 503 and "STRIPE_ALLOW_LIVE" in r.json()["detail"]
    finally:
        monkeypatch.undo(); get_settings.cache_clear()


# ---------------------------------------------------------------- webhook scenarios
def signed(client, event):
    payload = json.dumps(event)
    t = int(time.time())
    sig = hmac.new(b"whsec_test_secret", f"{t}.{payload}".encode(), hashlib.sha256).hexdigest()
    return client.post("/api/webhooks/stripe", content=payload, headers={"Stripe-Signature": f"t={t},v1={sig}", "Content-Type": "application/json"})


def sub_event(eid, uid, status, created, price="price_pro_test", cancel=False):
    now = int(time.time())
    return {"id": eid, "type": "customer.subscription.updated", "created": created, "data": {"object": {
        "id": f"sub_{uid[:8]}", "customer": f"cus_{uid[:8]}", "status": status, "cancel_at_period_end": cancel, "livemode": False,
        "metadata": {"careerflo_user_id": uid}, "items": {"data": [{"price": {"id": price}, "current_period_start": now,
                                                                     "current_period_end": now + 30 * 86400}]}}}}


def invoice(eid, uid, typ, amount=999, created=50):
    return {"id": eid, "type": typ, "created": created, "data": {"object": {
        "id": "in_" + eid, "customer": f"cus_{uid[:8]}", "amount_paid": amount if typ == "invoice.paid" else 0, "amount_due": amount,
        "currency": "cad", "livemode": False, "status_transitions": {"paid_at": int(time.time())},
        "subscription_details": {"metadata": {"careerflo_user_id": uid}}, "lines": {"data": [{"price": {"id": "price_pro_test"}}]}}}}


def test_webhook_lifecycle_upgrade_downgrade_failure_refund(client):
    h, u = register(client)
    uid = u["id"]
    co = {"id": "evt_co" + uid[:6], "type": "checkout.session.completed", "created": 5, "data": {"object": {
        "id": "cs_1", "customer": f"cus_{uid[:8]}", "subscription": None, "metadata": {"careerflo_user_id": uid}, "livemode": False}}}
    assert signed(client, co).json()["outcome"] == "processed"
    assert client.get("/api/usage", headers=h).json()["plan"]["id"] == "free"   # checkout alone: no subscription yet
    signed(client, sub_event("evt_s1" + uid[:6], uid, "active", 10, price="price_premium_test"))
    assert client.get("/api/usage", headers=h).json()["plan"]["id"] == "premium"
    signed(client, sub_event("evt_s2" + uid[:6], uid, "active", 20, price="price_pro_test"))                  # downgrade
    assert client.get("/api/usage", headers=h).json()["plan"]["id"] == "pro"
    assert signed(client, invoice("pf" + uid[:6], uid, "invoice.payment_failed")).json()["outcome"] == "processed"
    signed(client, sub_event("evt_s3" + uid[:6], uid, "past_due", 30))
    assert client.get("/api/usage", headers=h).json()["plan"]["id"] == "pro"        # grace during Stripe retries
    signed(client, sub_event("evt_s4" + uid[:6], uid, "unpaid", 40))
    assert client.get("/api/usage", headers=h).json()["plan"]["id"] == "free"       # access removed once unpaid
    assert signed(client, invoice("pd" + uid[:6], uid, "invoice.paid")).json()["outcome"] == "processed"
    ref = {"id": "evt_rf" + uid[:6], "type": "charge.refunded", "created": 60, "data": {"object": {
        "id": "ch_1", "invoice": "in_pd" + uid[:6], "amount_refunded": 999, "refunded": True}}}
    assert signed(client, ref).json()["outcome"] == "processed"
    inv = {i["id"]: i for i in client.get("/api/billing/invoices", headers=h).json()["invoices"]}
    assert inv["in_pd" + uid[:6]]["status"] == "refunded" and inv["in_pd" + uid[:6]]["refunded_cents"] == 999
    assert inv["in_pf" + uid[:6]]["status"] == "failed"
    signed(client, sub_event("evt_s5" + uid[:6], uid, "active", 70, cancel=True))
    assert client.get("/api/billing/subscription", headers=h).json()["subscription"]["cancel_at_period_end"] is True
    assert client.get("/api/usage", headers=h).json()["plan"]["id"] == "pro"        # access until the period ends


def test_unknown_price_and_customer_ignored(client):
    _, u = register(client)
    assert signed(client, sub_event("evt_up" + u["id"][:6], u["id"], "active", 5, price="price_unknown")).json()["outcome"] == "ignored_unknown_price"
    ghost = sub_event("evt_gh", str(uuid.uuid4()), "active", 5)
    assert signed(client, ghost).json()["outcome"] == "ignored_unknown_customer"
