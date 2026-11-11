"""Administrator-only subscription analytics from real records (synthetic/demo accounts excluded)."""
from __future__ import annotations

from collections import Counter, defaultdict

from fastapi import APIRouter
from sqlalchemy import func, select

from ..config import get_settings
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


@router.get("/ops")
async def ops(admin: AdminUser, db: DB) -> dict:
    """Operational dashboard. Every block states whether it is MEASURED, ESTIMATED or contains DEMO records."""
    import os
    from datetime import timedelta

    import psutil

    from ..llm.qwen import get_llm
    from ..models import AgentRun, Conversation, InferenceMetric, McpToolCall, utcnow
    from ..opsmetrics import metrics as reqm

    since = utcnow() - timedelta(days=30)
    demo_ids = {u.id for u in db.scalars(select(User).where(User.is_demo.is_(True)))}
    inf = [m for m in db.scalars(select(InferenceMetric).where(InferenceMetric.created_at >= since)) if m.user_id not in demo_ids]
    ok_inf = [m for m in inf if m.ok]
    runs = [r for r in db.scalars(select(AgentRun).where(AgentRun.created_at >= since)) if not r.is_synthetic and r.user_id not in demo_ids]
    calls = [c for c in db.scalars(select(McpToolCall).where(McpToolCall.created_at >= since)) if c.user_id not in demo_ids]
    consumed = [e for e in db.scalars(select(UsageEvent).where(UsageEvent.outcome == "consumed", UsageEvent.created_at >= since))
                if e.user_id not in demo_ids]
    open_convs = db.scalar(select(func.count()).select_from(Conversation).where(Conversation.status == "open"))

    def avg(xs):
        xs = [x for x in xs if x is not None]
        return round(sum(xs) / len(xs), 1) if xs else None

    llm = get_llm()
    vm = psutil.virtual_memory()
    req = reqm.snapshot()
    active_30d = len({e.user_id for e in consumed})
    variable_cost_cents = sum(FEATURES[e.feature_id].est_cost_cents for e in consumed if e.feature_id in FEATURES)
    fixed_monthly_usd = float(os.environ.get("INFRA_MONTHLY_COST_USD", "0") or 0)
    revenue = metrics(admin, db)
    return {
        "measured": {
            "note": f"Request counters are in-process and cover the last {req['since_seconds']} s (reset on restart). Database figures cover 30 days and exclude demo accounts.",
            "api": req,
            "open_conversations": open_convs,
            "inference": {"requests": len(inf), "errors": len(inf) - len(ok_inf), "avg_ttft_ms": avg([m.ttft_ms for m in ok_inf]),
                          "avg_tokens_per_second": avg([m.tokens_per_second for m in ok_inf]), "avg_total_ms": avg([m.total_ms for m in ok_inf]),
                          "queue_depth_now": llm.queue_depth, "max_concurrency": get_settings().llm_max_concurrency,
                          "provider": llm.provider, "model": llm.model},
            "agents": {"runs": len(runs), "completed": sum(r.status == "completed" for r in runs),
                       "failed": sum(r.status == "failed" for r in runs),
                       "success_rate": round(sum(r.status == "completed" for r in runs) / len(runs), 3) if runs else None},
            "mcp": {"calls": len(calls), "failures": sum(c.status in ("error", "timeout") for c in calls),
                    "denied": sum(c.status == "denied" for c in calls)},
            "feature_usage_30d": dict(Counter(e.feature_id for e in consumed)),
            "trial_vs_plan_30d": dict(Counter(e.source for e in consumed)),
            "resources": {"cpu_percent": psutil.cpu_percent(interval=0.1), "memory_percent": vm.percent,
                          "memory_used_gb": round(vm.used / 1e9, 2), "memory_total_gb": round(vm.total / 1e9, 2),
                          "disk_percent": psutil.disk_usage("/").percent},
        },
        "estimated": {
            "note": "Variable cost uses per-feature unit-cost assumptions in app/features.py (CAD cents); fixed cost comes from INFRA_MONTHLY_COST_USD. These are estimates, not invoices.",
            "active_users_30d": active_30d,
            "variable_cost_cad_30d": round(variable_cost_cents / 100, 2),
            "fixed_infra_usd_month": fixed_monthly_usd,
            "cost_per_active_user_usd": round(fixed_monthly_usd / active_30d, 2) if active_30d and fixed_monthly_usd else None,
        },
        "revenue": {"note": "From Stripe-synchronised records only. Null when there is no real revenue yet.",
                    "mrr_cents": revenue["mrr_cents"] if revenue["mrr_cents"] else None,
                    "estimated_gross_margin": revenue["estimated_gross_margin"], "livemode_records": revenue["livemode_records"]},
    }
