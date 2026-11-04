"""Stripe Checkout, Billing, Customer Portal and webhook processing.

Entitlements are derived only from webhook-synchronised subscription state (never from a
redirect). Events are processed idempotently (``stripe_events`` primary key) and tolerate
out-of-order delivery: subscription events re-fetch the subscription from Stripe when possible,
and otherwise an event older than the last applied one is ignored.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import stripe
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import get_settings
from ..features import PLANS
from ..models import BillingAuditLog, Invoice, StripeCustomer, StripeEvent, Subscription, User


def _client() -> stripe.StripeClient:
    s = get_settings()
    if not s.stripe_secret_key:
        raise HTTPException(503, "Payments are not configured yet (STRIPE_SECRET_KEY).")
    if s.stripe_secret_key.startswith("sk_live") and not s.stripe_allow_live:
        raise HTTPException(503, "Live Stripe keys are blocked until STRIPE_ALLOW_LIVE=true is explicitly set.")
    return stripe.StripeClient(s.stripe_secret_key)


def price_to_plan(price_id: str | None) -> str | None:
    s = get_settings()
    return {s.stripe_price_pro: "pro", s.stripe_price_premium: "premium"}.get(price_id or "") if price_id else None


def plan_price(plan_id: str) -> str:
    s = get_settings()
    price = {"pro": s.stripe_price_pro, "premium": s.stripe_price_premium}.get(plan_id)
    if not price:
        raise HTTPException(503, f"No Stripe price configured for plan '{plan_id}' (STRIPE_PRICE_{plan_id.upper()}).")
    return price


def _ts(v: Any) -> datetime | None:
    return datetime.fromtimestamp(int(v), tz=timezone.utc) if v else None


def get_or_create_customer(db: Session, user: User) -> str:
    row = db.get(StripeCustomer, user.id)
    if row:
        return row.stripe_customer_id
    cust = _client().customers.create(params={"email": user.email, "metadata": {"careerflo_user_id": str(user.id)}})
    db.add(StripeCustomer(user_id=user.id, stripe_customer_id=cust.id, livemode=bool(cust.livemode)))
    db.commit()
    return cust.id


def create_checkout(db: Session, user: User, plan_id: str) -> str:
    if plan_id not in ("pro", "premium"):
        raise HTTPException(422, "Unknown plan")
    active = db.scalar(select(Subscription).where(Subscription.user_id == user.id, Subscription.status.in_(["active", "trialing", "past_due"])))
    if active:
        raise HTTPException(409, "You already have a subscription. Use 'Change plan' to switch.")
    s = get_settings()
    session = _client().checkout.sessions.create(params={
        "mode": "subscription", "customer": get_or_create_customer(db, user),
        "line_items": [{"price": plan_price(plan_id), "quantity": 1}],
        "client_reference_id": str(user.id),
        "subscription_data": {"metadata": {"careerflo_user_id": str(user.id), "plan": plan_id}},
        "metadata": {"careerflo_user_id": str(user.id), "plan": plan_id},
        "automatic_tax": {"enabled": True}, "customer_update": {"address": "auto"},
        "allow_promotion_codes": True,
        "success_url": f"{s.public_app_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{s.public_app_url}/billing/cancel",
    })
    db.add(BillingAuditLog(user_id=user.id, action="checkout.created", detail={"plan": plan_id, "session": session.id}))
    db.commit()
    return session.url


def portal_url(db: Session, user: User) -> str:
    row = db.get(StripeCustomer, user.id)
    if not row:
        raise HTTPException(404, "No billing account yet.")
    sess = _client().billing_portal.sessions.create(params={"customer": row.stripe_customer_id,
                                                             "return_url": f"{get_settings().public_app_url}/billing"})
    return sess.url


def _user_sub(db: Session, user: User) -> Subscription:
    sub = db.scalar(select(Subscription).where(Subscription.user_id == user.id, Subscription.status.in_(["active", "trialing", "past_due"])))
    if not sub:
        raise HTTPException(404, "No active subscription")
    return sub


def change_plan(db: Session, user: User, plan_id: str) -> dict[str, Any]:
    sub = _user_sub(db, user)
    c = _client()
    remote = c.subscriptions.retrieve(sub.stripe_subscription_id)
    item = remote["items"]["data"][0]
    c.subscriptions.update(sub.stripe_subscription_id, params={
        "items": [{"id": item["id"], "price": plan_price(plan_id)}], "proration_behavior": "create_prorations",
        "metadata": {"careerflo_user_id": str(user.id), "plan": plan_id}})
    db.add(BillingAuditLog(user_id=user.id, action="subscription.change_requested", detail={"to": plan_id}))
    db.commit()
    return {"requested": plan_id, "note": "Your plan updates as soon as Stripe confirms the change (usually seconds). Proration applies."}


def set_cancel(db: Session, user: User, cancel: bool) -> dict[str, Any]:
    sub = _user_sub(db, user)
    _client().subscriptions.update(sub.stripe_subscription_id, params={"cancel_at_period_end": cancel})
    db.add(BillingAuditLog(user_id=user.id, action="subscription.cancel_requested" if cancel else "subscription.resume_requested"))
    db.commit()
    return {"cancel_at_period_end": cancel, "access_until": sub.current_period_end}


# ---------------------------------------------------------------- webhooks
def verify_event(payload: bytes, sig_header: str | None) -> dict[str, Any]:
    secret = get_settings().stripe_webhook_secret
    if not secret:
        raise HTTPException(503, "STRIPE_WEBHOOK_SECRET not configured")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header or "", secret)
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise HTTPException(400, "Invalid Stripe signature") from exc
    return event.to_dict() if hasattr(event, "to_dict") else dict(event)


def _user_for_customer(db: Session, customer_id: str | None, meta: dict | None = None) -> uuid.UUID | None:
    if meta and meta.get("careerflo_user_id"):
        try:
            return uuid.UUID(meta["careerflo_user_id"])
        except ValueError:
            pass
    if not customer_id:
        return None
    row = db.scalar(select(StripeCustomer).where(StripeCustomer.stripe_customer_id == customer_id))
    return row.user_id if row else None


def _fetch_subscription(sub_id: str) -> dict[str, Any] | None:
    try:
        return _client().subscriptions.retrieve(sub_id).to_dict()
    except Exception:  # noqa: BLE001 - offline / tests: fall back to the event payload
        return None


def _sync_subscription(db: Session, obj: dict[str, Any], event_created: int) -> str:
    sub_id = obj["id"]
    fresh = _fetch_subscription(sub_id)
    authoritative = fresh is not None
    data = fresh or obj
    row = db.scalar(select(Subscription).where(Subscription.stripe_subscription_id == sub_id))
    if row and not authoritative and event_created < row.last_event_at:
        return "ignored_out_of_order"
    items = (data.get("items") or {}).get("data") or []
    price = (items[0].get("price") or {}).get("id") if items else None
    plan = price_to_plan(price) or (data.get("metadata") or {}).get("plan") or (row.plan_id if row else None)
    if plan not in PLANS:
        return "ignored_unknown_price"
    user_id = _user_for_customer(db, data.get("customer"), data.get("metadata"))
    if user_id is None or db.get(User, user_id) is None:
        return "ignored_unknown_customer"
    period_start = data.get("current_period_start") or (items[0].get("current_period_start") if items else None)
    period_end = data.get("current_period_end") or (items[0].get("current_period_end") if items else None)
    if row is None:
        row = Subscription(user_id=user_id, stripe_subscription_id=sub_id, stripe_customer_id=data.get("customer") or "", plan_id=plan,
                           status=data.get("status", "incomplete"))
        db.add(row)
    row.plan_id, row.status = plan, data.get("status", row.status)
    row.current_period_start, row.current_period_end = _ts(period_start), _ts(period_end)
    row.cancel_at_period_end = bool(data.get("cancel_at_period_end"))
    row.canceled_at = _ts(data.get("canceled_at"))
    row.livemode = bool(data.get("livemode"))
    row.last_event_at = max(row.last_event_at or 0, event_created)
    if not db.get(StripeCustomer, user_id) and data.get("customer"):
        db.add(StripeCustomer(user_id=user_id, stripe_customer_id=data["customer"], livemode=row.livemode))
    db.add(BillingAuditLog(user_id=user_id, action="subscription.synced", detail={"status": row.status, "plan": plan,
                                                                                    "authoritative": authoritative}))
    return "processed"


def _record_invoice(db: Session, inv: dict[str, Any], status: str) -> str:
    customer = inv.get("customer")
    user_id = _user_for_customer(db, customer, (inv.get("subscription_details") or {}).get("metadata"))
    lines = ((inv.get("lines") or {}).get("data") or [])
    price = None
    if lines:
        price = (lines[0].get("price") or {}).get("id") or (((lines[0].get("pricing") or {}).get("price_details") or {}).get("price"))
    row = db.get(Invoice, inv["id"]) or Invoice(id=inv["id"], stripe_customer_id=customer or "", status=status, amount_cents=0, currency="cad")
    row.user_id, row.status = user_id, status
    row.amount_cents = int(inv.get("amount_paid") if status == "paid" else inv.get("amount_due") or 0)
    row.currency = (inv.get("currency") or "cad").upper()
    row.hosted_invoice_url = inv.get("hosted_invoice_url")
    row.plan_id = price_to_plan(price)
    row.paid_at = _ts((inv.get("status_transitions") or {}).get("paid_at")) if status == "paid" else row.paid_at
    row.livemode = bool(inv.get("livemode"))
    db.merge(row)
    db.add(BillingAuditLog(user_id=user_id, action=f"invoice.{status}", detail={"invoice": inv["id"], "amount": row.amount_cents}))
    return "processed"


def process_event(db: Session, event: dict[str, Any]) -> str:
    """Idempotent: the event id is inserted first; a replay hits the primary key and is skipped."""
    eid, etype, created = event["id"], event["type"], int(event.get("created") or 0)
    obj = event["data"]["object"]
    try:
        db.add(StripeEvent(id=eid, type=etype, stripe_created=created, status="processing"))
        db.flush()
    except IntegrityError:
        db.rollback()
        return "duplicate"
    try:
        if etype in ("customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"):
            outcome = _sync_subscription(db, obj, created)
        elif etype == "checkout.session.completed":
            user_id = _user_for_customer(db, obj.get("customer"), obj.get("metadata"))
            if user_id and obj.get("customer") and not db.get(StripeCustomer, user_id):
                db.add(StripeCustomer(user_id=user_id, stripe_customer_id=obj["customer"], livemode=bool(obj.get("livemode"))))
            outcome = "processed"
            if obj.get("subscription"):
                fresh = _fetch_subscription(obj["subscription"])
                if fresh:
                    outcome = _sync_subscription(db, fresh, created)
        elif etype == "invoice.paid":
            outcome = _record_invoice(db, obj, "paid")
        elif etype == "invoice.payment_failed":
            outcome = _record_invoice(db, obj, "failed")
        elif etype == "charge.refunded":
            inv_id = obj.get("invoice")
            row = db.get(Invoice, inv_id) if inv_id else None
            if row:
                row.amount_refunded_cents = int(obj.get("amount_refunded") or 0)
                row.status = "refunded" if obj.get("refunded") else row.status
            outcome = "processed" if row else "ignored_no_invoice"
        else:
            outcome = "ignored_type"
        ev = db.get(StripeEvent, eid)
        ev.status = "processed" if outcome == "processed" else "ignored"
        ev.detail = {"outcome": outcome}
        db.commit()
        return outcome
    except Exception:
        db.rollback()  # leaves no event row: Stripe will retry delivery
        raise
