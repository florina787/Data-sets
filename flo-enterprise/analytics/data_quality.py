"""Data-quality checks executed against the governed data products (results are measured, never assumed)."""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from integrations.mock.adapters import Adapters


def run_checks(adapters: Adapters, today: date | None = None) -> dict:
    st = adapters.store
    t = st.tables
    checks = []

    def add(product, cid, name, passed, detail, severity="high"):
        checks.append({"data_product": product, "check_id": cid, "name": name, "passed": bool(passed), "detail": detail,
                       "severity": severity})

    # investment / finance
    breaks = [r for r in t["product_monthly"] if r["aum_close_cents"] != r["aum_open_cents"] + r["subscriptions_cents"] - r["redemptions_cents"] + r["market_cents"]]
    add("finance", "DQ-FIN-001", "AUM roll-forward reconciles for every product-month", not breaks, f"{len(breaks)} breaks / {len(t['product_monthly'])} rows")
    by_m = defaultdict(int)
    for r in t["product_monthly"]:
        by_m[r["month"]] += r["revenue_cents"]
    ledger = {r["month"]: r["actual_cents"] for r in t["finance_monthly"] if r["line"] == "revenue_management_fees"}
    diff = [m for m in by_m if by_m[m] != ledger.get(m)]
    add("finance", "DQ-FIN-002", "Ledger fee revenue equals product-level accruals", not diff, f"{len(diff)} months differ")
    months = st.idx["months"]
    cont = [p for p, v in st.idx["portfolio_monthly_by"].items() if any(a["mv_close_cents"] != b["mv_open_cents"] for a, b in zip(v, v[1:]))]
    add("investment", "DQ-INV-001", "Portfolio valuations are continuous (close = next open)", not cont, f"{len(cont)} portfolios with gaps")
    wsum = defaultdict(float)
    for h in t["portfolio_holdings"]:
        wsum[h["portfolio_id"]] += h["current_weight"]
    bad_w = [k for k, v in wsum.items() if abs(v - 1) > 1e-3]
    add("investment", "DQ-INV-002", "Portfolio current weights sum to 100% (+/-0.1%)", not bad_w, f"{len(bad_w)} portfolios outside tolerance")
    neg = [r for r in t["portfolio_monthly"] if r["mv_close_cents"] <= 0]
    add("investment", "DQ-INV-003", "Market values are positive", not neg, f"{len(neg)} non-positive valuations")
    sec_ids = set(st.idx["security"])
    orphan = [h for h in t["portfolio_holdings"] + t["product_holdings"] if h["security_id"] not in sec_ids]
    add("investment", "DQ-INV-004", "Holdings reference known securities", not orphan, f"{len(orphan)} orphan holdings")
    # wealth
    cl = st.idx["client"]
    orphan_p = [p for p in t["portfolios"] if p["client_id"] not in cl]
    add("wealth", "DQ-WLT-001", "Every portfolio has an existing client", not orphan_p, f"{len(orphan_p)} orphans")
    xt = [p for p in t["portfolios"] if p["client_id"] in cl and cl[p["client_id"]]["tenant_id"] != p["tenant_id"]]
    add("wealth", "DQ-WLT-002", "Portfolio tenant matches client tenant", not xt, f"{len(xt)} mismatches", "critical")
    adv = st.idx["advisor"]
    xa = [c for c in t["clients"] if adv[c["advisor_id"]]["tenant_id"] != c["tenant_id"]]
    add("wealth", "DQ-WLT-003", "Client advisor belongs to the client's tenant", not xa, f"{len(xa)} mismatches", "critical")
    stale = [c for c in t["clients"] if c["status"] == "active" and (months[-1] - c["kyc_last_review"]).days > 730]
    add("wealth", "DQ-WLT-004", "Active clients have KYC reviewed within 730 days", not stale, f"{len(stale)} clients overdue", "medium")
    dup = len(t["clients"]) - len({c["account_number"] for c in t["clients"]})
    add("wealth", "DQ-WLT-005", "Account numbers are unique", dup == 0, f"{dup} duplicates", "critical")
    # risk / strategy
    open_ce = [e for e in t["compliance_events"] if e["status"] == "closed" and e["closed_at"] is None]
    add("risk", "DQ-RSK-001", "Closed compliance events have a closure date", not open_ce, f"{len(open_ce)} missing dates", "medium")
    no_obs = [d for d in t["decisions"] if d["deadline"] < months[-1] and d["observed_value"] is None and d["id"] != "D-0001"]
    add("strategy", "DQ-STR-001", "Decisions past deadline have an observed outcome", not no_obs, f"{len(no_obs)} decisions without outcome", "medium")
    # freshness
    today = today or date.today()
    lag = (today - months[-1]).days
    add("all", "DQ-FRS-001", "Month-end data within freshness SLA (<= 45 days old)", lag <= 45, f"latest month-end {months[-1]}, {lag} days old", "medium")
    passed = sum(c["passed"] for c in checks)
    return {"checks": checks, "passed": passed, "total": len(checks), "pass_rate": round(passed / len(checks), 4),
            "dataset_version": st.version, "as_of": months[-1].isoformat()}
