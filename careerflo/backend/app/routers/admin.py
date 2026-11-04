"""Administrator-only subscription analytics from real records (synthetic/demo accounts excluded)."""
from __future__ import annotations

from collections import Counter, defaultdict

from fastapi import APIRouter
from sqlalchemy import select

from ..features import FEATURES, PLANS
from ..models import Invoice, Subscription, TrialUsage, UsageEvent, User
from ..security.auth import AdminUser, DB

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/metrics")
def metrics(admin: AdminUser, db: DB) -> dict:
    users = [u for u in db.scalars(select(User)) if not u.is_demo]
    real_ids = {u.id for u in users}
    subs = [s for s in db.scalars(select(Subscription)) if s.user_id in real_ids]
    active = [s for s in subs if s.status in ("active", "trialing", "past_due")]
    paying_ids = {s.user_id for s in subs if s.status in ("active", "trialing", "past_due", "canceled")}
    trials = [t for t in db.scalars(select(TrialUsage)) if t.user_id in real_ids]
    trial_users = {t.user_id for t in trials if t.used > 0}
    invoices = [i for i in db.scalars(select(Invoice)) if i.user_id in real_ids]
    paid = [i for i in invoices if i.status in ("paid", "refunded")]
    revenue_by_month: dict[str, int] = defaultdict(int)
    for i in paid:
        if i.paid_at:
            revenue_by_month[i.paid_at.strftime("%Y-%m")] += i.amount_cents - i.amount_refunded_cents
    events = [e for e in db.scalars(select(UsageEvent).where(UsageEvent.outcome == "consumed")) if e.user_id in real_ids]
    cost_cents = sum(FEATURES[e.feature_id].est_cost_cents for e in events if e.feature_id in FEATURES)
    mrr = sum(PLANS[s.plan_id].price_cents for s in active if s.status != "past_due" and not s.cancel_at_period_end)
    net_rev = sum(revenue_by_month.values())
    return {
        "registered_users": len(users), "trial_users": len(trial_users),
        "trial_usage_by_feature": dict(Counter(t.feature_id for t in trials for _ in range(t.used))),
        "trial_to_paid_conversion": round(len(paying_ids & trial_users) / len(trial_users), 3) if trial_users else None,
        "active_pro": sum(1 for s in active if s.plan_id == "pro"), "active_premium": sum(1 for s in active if s.plan_id == "premium"),
        "mrr_cents": mrr, "currency": "CAD",
        "cancellations": sum(1 for s in subs if s.status == "canceled" or s.cancel_at_period_end),
        "failed_payments": sum(1 for i in invoices if i.status == "failed"),
        "revenue_trend": [{"month": k, "net_cents": v} for k, v in sorted(revenue_by_month.items())],
        "estimated_usage_cost_cents": round(cost_cents, 1),
        "estimated_gross_margin": round((net_rev - cost_cents) / net_rev, 3) if net_rev else None,
        "livemode_records": any(s.livemode for s in subs),
        "note": "All figures come from Stripe-synchronised records and server-side usage events; demo accounts are excluded. "
                "Usage cost is an estimate from per-feature unit costs in app/features.py.",
    }
