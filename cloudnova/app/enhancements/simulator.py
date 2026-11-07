"""Financial Digital Twin — what-if simulator (enhancement 2).

Baseline = OBSERVED state of active accounts from the cleaned ledger (latest-invoice snapshot, same MRR rule as the
core metrics). Scenario = the same accounts with user-supplied assumptions applied. Everything is computed in memory
from a read-only query; the ledger is never modified. Every scenario output is labelled hypothetical.

MRR   = list_price[plan] × seats × (1 − discount/100)             (BUSINESS_CONTEXT)
ARR   = MRR × 12
Expected 12-month billings = monthly accounts MRR × 12 + annual accounts MRR × 10   (annual = 10 billed months)
Assumed churn is applied as an expected value: each account's MRR × (1 − churn%) — not a prediction.
"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from .. import db
from ..pipeline.rules import BILLED_MONTHS, LIST_PRICE_USD

PLANS = tuple(LIST_PRICE_USD)


class Scenario(BaseModel):
    list_price_usd: dict[str, float] = Field(default_factory=dict, description="override per plan, e.g. {'Pro': 109}")
    seat_change_pct: dict[str, float] = Field(default_factory=dict, description="per plan or 'all', e.g. {'all': 10}")
    discount_pct: dict[str, float] = Field(default_factory=dict, description="set discount per plan or 'all' (absolute %)")
    assumed_churn_pct: float = Field(0.0, ge=0, le=100, description="share of active MRR assumed lost (expected value)")
    plan_filter: list[str] | None = Field(None, description="limit the scenario to these plans")

    @field_validator("list_price_usd")
    @classmethod
    def _prices(cls, v):
        for k, p in v.items():
            if k not in PLANS:
                raise ValueError(f"unknown plan '{k}' (expected one of {', '.join(PLANS)})")
            if not 0 <= p <= 100000:
                raise ValueError("list price must be between 0 and 100000")
        return v

    @field_validator("seat_change_pct")
    @classmethod
    def _seats(cls, v):
        for k, p in v.items():
            if k not in PLANS + ("all",):
                raise ValueError(f"unknown plan '{k}'")
            if not -100 <= p <= 500:
                raise ValueError("seat change must be between -100% and +500%")
        return v

    @field_validator("discount_pct")
    @classmethod
    def _disc(cls, v):
        for k, p in v.items():
            if k not in PLANS + ("all",):
                raise ValueError(f"unknown plan '{k}'")
            if not 0 <= p < 100:
                raise ValueError("discount must be in [0, 100)")
        return v

    @field_validator("plan_filter")
    @classmethod
    def _plans(cls, v):
        if v is not None and any(p not in PLANS for p in v):
            raise ValueError(f"plan_filter must contain only {', '.join(PLANS)}")
        return v


BASE_SQL = """
SELECT a.account_id, a.plan, a.seats, CAST(a.discount_pct AS DOUBLE) AS discount_pct, l.billing_cycle,
       CAST(a.current_mrr_usd AS DOUBLE) AS observed_mrr
FROM accounts a
JOIN (SELECT account_id, billing_cycle,
             ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY invoice_date DESC, invoice_id DESC) AS rn
      FROM invoices) l ON l.account_id = a.account_id AND l.rn = 1
WHERE a.is_active
"""


def _pick(d: dict, plan: str):
    return d.get(plan, d.get("all"))


def simulate(sc: Scenario) -> dict:
    rows = db.connection().execute(BASE_SQL).fetchall()
    if sc.plan_filter:
        rows = [r for r in rows if r[1] in sc.plan_filter]
    keep = 1 - sc.assumed_churn_pct / 100

    def agg():
        return {p: {"accounts": 0, "seats": 0, "mrr": 0.0, "billings_12m": 0.0} for p in PLANS}

    base, sim = agg(), agg()
    for _acc, plan, seats, disc, cycle, observed in rows:
        months = 12 if cycle == "monthly" else BILLED_MONTHS["annual"]
        b = base[plan]
        b["accounts"] += 1
        b["seats"] += seats
        b["mrr"] += observed
        b["billings_12m"] += observed * months
        price = _pick(sc.list_price_usd, plan) if _pick(sc.list_price_usd, plan) is not None else LIST_PRICE_USD[plan]
        chg = _pick(sc.seat_change_pct, plan) or 0.0
        new_seats = max(0, round(seats * (1 + chg / 100)))
        d = _pick(sc.discount_pct, plan)
        d = disc if d is None else d
        mrr = price * new_seats * (1 - d / 100) * keep
        s = sim[plan]
        s["accounts"] += keep
        s["seats"] += new_seats * keep
        s["mrr"] += mrr
        s["billings_12m"] += mrr * months

    def total(t):
        tot = {k: sum(t[p][k] for p in PLANS) for k in ("accounts", "seats", "mrr", "billings_12m")}
        return tot

    def fmt(t):
        return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in {**t, "arr": t["mrr"] * 12}.items()}

    by_plan = []
    for p in PLANS:
        if base[p]["accounts"] == 0:
            continue
        b, s = fmt(base[p]), fmt(sim[p])
        by_plan.append({"plan": p, "observed": b, "hypothetical": s,
                        "delta_mrr": round(s["mrr"] - b["mrr"], 2),
                        "delta_mrr_pct": round((s["mrr"] - b["mrr"]) / b["mrr"] * 100, 2) if b["mrr"] else None})
    tb, ts = fmt(total(base)), fmt(total(sim))
    return {
        "label": "HYPOTHETICAL scenario vs OBSERVED baseline — not a forecast; the ledger is unchanged.",
        "scenario": sc.model_dump(),
        "observed": tb, "hypothetical": ts,
        "delta": {k: round(ts[k] - tb[k], 2) for k in ("mrr", "arr", "billings_12m", "accounts", "seats")},
        "by_plan": by_plan,
        "method": {
            "baseline": "active accounts (latest-invoice snapshot); MRR = list price × seats × (1 − discount); matches the core 'mrr' metric",
            "arr": "MRR × 12",
            "billings_12m": "monthly accounts: MRR × 12; annual accounts: MRR × 10 (2 months free)",
            "churn": "applied as expected value: MRR × (1 − assumed churn %); accounts shown fractional for that reason",
            "assumptions_not_modelled": "price elasticity, upgrades/downgrades, new logos, timing within the year, FX",
        },
    }


def observed_mrr_check() -> float:
    """Baseline must reconcile to the core metric (used by tests)."""
    return float(db.connection().execute("SELECT SUM(current_mrr_usd) FROM accounts WHERE is_active").fetchone()[0] or Decimal(0))
