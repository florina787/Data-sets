from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..billing import stripe_service as S
from ..billing.metering import active_plan
from ..config import get_settings
from ..db import SessionLocal
from ..models import Invoice
from ..security.auth import CurrentUser, DB

router = APIRouter(prefix="/api/billing", tags=["billing"])


class PlanIn(BaseModel):
    plan: str = Field(pattern="^(pro|premium)$")


@router.get("/subscription")
def subscription(user: CurrentUser, db: DB) -> dict:
    plan, sub = active_plan(db, user.id)
    key = get_settings().stripe_secret_key
    return {"plan": {"id": plan.id, "name": plan.name, "price_cents": plan.price_cents, "currency": plan.currency},
            "subscription": None if not sub else {
                "status": sub.status, "current_period_end": sub.current_period_end, "cancel_at_period_end": sub.cancel_at_period_end,
                "livemode": sub.livemode},
            "stripe_mode": "live" if key.startswith("sk_live") else "test" if key else "not_configured",
            "terms": {"renewal": "Subscriptions renew monthly until cancelled. Cancel any time; access continues to the end of the paid period.",
                      "refunds": "Payments are non-refundable except where required by law or at our discretion for billing errors.",
                      "trial": "Free trials never convert into a paid subscription automatically.",
                      "tax": "Applicable sales tax (e.g. GST/HST) is calculated by Stripe at checkout."}}


@router.post("/checkout")
def checkout(body: PlanIn, user: CurrentUser, db: DB) -> dict:
    return {"url": S.create_checkout(db, user, body.plan)}


@router.post("/portal")
def portal(user: CurrentUser, db: DB) -> dict:
    return {"url": S.portal_url(db, user)}


@router.post("/change-plan")
def change(body: PlanIn, user: CurrentUser, db: DB) -> dict:
    return S.change_plan(db, user, body.plan)


@router.post("/cancel")
def cancel(user: CurrentUser, db: DB) -> dict:
    return S.set_cancel(db, user, True)


@router.post("/resume")
def resume(user: CurrentUser, db: DB) -> dict:
    return S.set_cancel(db, user, False)


@router.get("/invoices")
def invoices(user: CurrentUser, db: DB) -> dict:
    rows = db.scalars(select(Invoice).where(Invoice.user_id == user.id).order_by(Invoice.created_at.desc()).limit(50))
    return {"invoices": [{"id": i.id, "status": i.status, "amount_cents": i.amount_cents, "refunded_cents": i.amount_refunded_cents,
                          "currency": i.currency, "plan": i.plan_id, "url": i.hosted_invoice_url,
                          "paid_at": _utc(i.paid_at), "created_at": _utc(i.created_at)} for i in rows]}


def _utc(d):
    """ISO-8601 with an explicit UTC offset (SQLite drops tzinfo; browsers would otherwise read local time)."""
    if d is None:
        return None
    from datetime import timezone

    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).isoformat()


webhook_router = APIRouter(tags=["billing"])


@webhook_router.post("/api/webhooks/stripe")
async def stripe_webhook(request: Request) -> dict:
    payload = await request.body()
    event = S.verify_event(payload, request.headers.get("stripe-signature"))
    with SessionLocal() as db:
        outcome = S.process_event(db, event)
    return {"received": True, "outcome": outcome}
