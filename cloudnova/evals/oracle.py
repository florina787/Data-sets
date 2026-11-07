"""Independent oracle (specs/evaluation_plan.md). Recomputes expected answers from the RAW CSV with the
standard library only. Deliberately does NOT import from `app/` — its parsers, dedup and aggregation are
written separately from the spec so that a misreading in either implementation shows up as a disagreement.
"""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "raw" / "cloudnova_invoices.csv"
PRICE = {"starter": 49, "pro": 99, "enterprise": 299}
PLAN = {"starter": "starter", "start": "starter", "tier 1": "starter", "pro": "pro", "professional": "pro", "tier 2": "pro",
        "enterprise": "enterprise", "ent": "enterprise", "tier 3": "enterprise"}
STATUS = {**dict.fromkeys(["paid", "complete", "completed", "success"], "paid"),
          **dict.fromkeys(["pending", "in_review", "awaiting"], "pending"),
          **dict.fromkeys(["failed", "declined", "error"], "failed"),
          **dict.fromkeys(["refunded", "refund", "charged_back"], "refunded"),
          **dict.fromkeys(["void", "cancelled", "canceled"], "void")}
RANK = {"refunded": 0, "paid": 1, "failed": 2, "void": 3, "pending": 4}
FX = {"USD": Decimal("1"), "EUR": Decimal("1.08"), "GBP": Decimal("1.27")}
MON = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}


def _date(s: str) -> date:
    s = s.strip()
    parts = re.split(r"[-/ ]+", s)
    if parts[0].isalpha():                      # Jan 5 2024
        return date(int(parts[2]), MON[parts[0][:3].lower()], int(parts[1]))
    if len(parts[0]) == 4:                      # 2024-01-05 / 2024/01/05
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    if "/" in s:                                # 01/05/2024 = MM/DD
        return date(int(parts[2]), int(parts[0]), int(parts[1]))
    return date(int(parts[2]), int(parts[1]), int(parts[0]))   # 05-01-2024 = DD-MM


def _amount(s: str) -> Decimal:
    return Decimal(re.sub(r"[^0-9.\-]", "", s))


def _bool(s: str):
    s = s.strip().lower()
    return True if s in ("true", "yes", "1", "y") else False if s in ("false", "no", "0", "n") else None


@lru_cache
def invoices(inverse_fx: bool = False) -> list[dict]:
    with open(RAW, newline="") as fh:
        raw = list(csv.DictReader(fh))
    seen, uniq = set(), []
    for r in raw:
        key = tuple(v.strip() for v in r.values())
        if key not in seen:
            seen.add(key)
            uniq.append(r)
    by_id = defaultdict(list)
    for r in uniq:
        by_id[r["invoice_id"].strip()].append(r)
    out = []
    for inv_id, rows in by_id.items():
        r = min(rows, key=lambda x: RANK[STATUS[x["status"].strip().lower()]])  # stable: first raw row wins ties
        plan = PLAN[re.sub(r"\s+", " ", r["plan"].strip().lower())]
        cur = r["currency"].strip()
        amt = _amount(r["amount"])
        usd = (amt / FX[cur] if inverse_fx else amt * FX[cur]).quantize(Decimal("0.01"))
        disc = Decimal(r["discount_pct"])
        csat = r["csat_score"].strip()
        out.append({
            "invoice_id": inv_id, "account_id": r["account_id"].strip(), "account_name": r["account_name"].strip(),
            "region": r["region"].strip(), "plan": plan, "seats": int(r["seats"]), "currency": cur, "usd": usd,
            "disc": disc, "status": STATUS[r["status"].strip().lower()], "date": _date(r["invoice_date"]),
            "churned": _bool(r["churned"]), "csat": int(csat) if csat else None, "tickets": int(r["support_tickets"] or 0),
            "months": 10 if r["billing_cycle"].strip().lower() in ("annual", "annually", "yearly") else 1,
            "mrr": (PRICE[plan] * int(r["seats"]) * (1 - disc / 100)).quantize(Decimal("0.01")),
        })
    return out


def raw_stats() -> dict:
    with open(RAW, newline="") as fh:
        raw = list(csv.DictReader(fh))
    keys = [tuple(v.strip() for v in r.values()) for r in raw]
    exact = len(keys) - len(set(keys))
    inv = invoices()
    conflicts = 0
    seen = {}
    for k in dict.fromkeys(keys):
        seen.setdefault(k[0], set()).add(STATUS[k[12].lower()])
    conflicts = sum(1 for s in seen.values() if len(s) > 1)
    return {"raw_rows": len(raw), "exact_duplicates": exact, "clean_invoices": len(inv), "status_conflicts": conflicts}


def accounts() -> dict[str, dict]:
    latest: dict[str, dict] = {}
    totals = defaultdict(lambda: Decimal("0"))
    for r in invoices():
        a = r["account_id"]
        if a not in latest or (r["date"], r["invoice_id"]) > (latest[a]["date"], latest[a]["invoice_id"]):
            latest[a] = r
        if r["status"] in ("paid", "refunded"):
            totals[a] += r["usd"]
    return {a: {**r, "net": totals[a]} for a, r in latest.items()}


def _sum(rows, statuses):
    return sum((r["usd"] for r in rows if r["status"] in statuses), Decimal("0"))


# ------------------------------------------------------------------ expected answers
def expected() -> dict:
    inv = invoices()
    acc = accounts()
    y2024 = [r for r in inv if r["date"].year == 2024]
    exp: dict = {}
    exp["q1_paid_2024"] = float(_sum(y2024, {"paid"}))
    exp["q1_net_2024"] = float(_sum(y2024, {"paid", "refunded"}))
    exp["q1_paid_2024_inverse_fx"] = float(_sum([r for r in invoices(True) if r["date"].year == 2024], {"paid"}))
    by_region = defaultdict(list)
    for a in acc.values():
        if a["churned"] is False:
            by_region[a["region"]].append(a["mrr"])
    avg = {k: float(sum(v) / len(v)) for k, v in by_region.items()}
    exp["q2_region"] = max(avg, key=avg.get)
    exp["q2_avg_mrr"] = avg[exp["q2_region"]]
    exp["q3_refunds"] = float(_sum(inv, {"refunded"}))
    exp["q3_refund_count"] = sum(1 for r in inv if r["status"] == "refunded")
    for plan in ("enterprise", "starter"):
        vals = [a["churned"] for a in acc.values() if a["plan"] == plan and a["churned"] is not None]
        exp[f"q4_churn_{plan}"] = sum(vals) / len(vals)
    top = sorted(acc.values(), key=lambda a: (-a["net"], a["account_id"]))[:5]
    exp["q5_top5_ids"] = [a["account_id"] for a in top]
    exp["q5_low_csat_ids"] = [a["account_id"] for a in top if a["csat"] is not None and a["csat"] <= 2]
    by_name = defaultdict(lambda: Decimal("0"))
    for r in inv:
        if r["status"] in ("paid", "refunded"):
            by_name[r["account_name"]] += r["usd"]
    exp["q5_top5_by_name"] = [n for n, _ in sorted(by_name.items(), key=lambda kv: (-kv[1], kv[0]))[:5]]
    stuck = [r for r in inv if r["status"] in ("pending", "failed")]
    exp["q6_count"] = len(stuck)
    exp["q6_exposure"] = float(_sum(stuck, {"pending", "failed"}))
    # open-ended
    exp["net_2025"] = float(_sum([r for r in inv if r["date"].year == 2025], {"paid", "refunded"}))
    for plan in ("enterprise", "pro", "starter"):
        exp[f"net_by_plan_{plan}"] = float(_sum([r for r in inv if r["plan"] == plan], {"paid", "refunded"}))
    paid = [r for r in inv if r["status"] == "paid"]
    exp["avg_paid_invoice"] = float(sum(r["usd"] for r in paid) / len(paid))
    exp["discount_given"] = float(sum((PRICE[r["plan"]] * r["seats"] * r["months"] * r["disc"] / 100 for r in paid), Decimal("0")))
    exp["emea_enterprise_paid"] = float(_sum([r for r in inv if r["region"] == "EMEA" and r["plan"] == "enterprise"], {"paid"}))
    exp["invoice_count_pending"] = sum(1 for r in inv if r["status"] == "pending")
    ent_region = defaultdict(lambda: Decimal("0"))
    for r in inv:
        if r["plan"] == "enterprise" and r["status"] in ("paid", "refunded"):
            ent_region[r["region"]] += r["usd"]
    exp["followup_enterprise_top_region"] = max(ent_region, key=ent_region.get)
    exp["followup_enterprise_top_value"] = float(ent_region[exp["followup_enterprise_top_region"]])
    tk = defaultdict(list)
    for a in acc.values():
        if a["churned"] is not None:
            tk[a["churned"]].append(a["tickets"])
    exp["tickets_churned_avg"] = sum(tk[True]) / len(tk[True])
    exp.update(raw_stats())
    return exp


if __name__ == "__main__":
    import json
    print(json.dumps(expected(), indent=2, default=str))
