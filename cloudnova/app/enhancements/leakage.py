"""Revenue Leakage Investigator (enhancement 1).

Runs fixed, read-only checks over the cleaned DuckDB tables using the existing business rules, and returns findings
with evidence (the SQL + sample invoice ids), dollar exposure and an investigation status.

Vocabulary is deliberately strict — nothing here is a "recovered" or "confirmed lost" dollar:
* control_passed      — the check ran and found nothing (shown, because a passed control is evidence too)
* rule_violation      — contradicts a documented business rule (deterministic)
* needs_investigation — irregular pattern that *may* be leakage or may be a data artefact; a person must decide
* decision_required   — the number depends on a business decision CloudNova has not made yet
* needs_policy        — cannot be judged without a policy CloudNova has not provided
Exposure is "dollars at stake", never "dollars lost".
"""
from __future__ import annotations

import os
import sqlite3
import time
from contextlib import closing

from .. import db
from ..config import get_settings
from ..errors import AppError

STATUSES = ("open", "investigating", "resolved", "dismissed")


def _q(sql: str) -> list[tuple]:
    return db.connection().execute(sql).fetchall()


def _sample(sql: str, n: int = 8) -> list[str]:
    return [r[0] for r in _q(sql + f" LIMIT {n}")]


CHECKS = [
    {
        "id": "pricing_discrepancy", "title": "Invoice amount ≠ list price × seats × months × (1 − discount)",
        "rule": "BUSINESS_CONTEXT pricing rules; annual = 10 months; FX at fixed rates",
        "kind": "rule_violation",
        "where": "status <> 'refunded' AND abs(abs(amount_local) - expected_amount_usd * fx_rate_to_usd) > 1.00",
        "table": "invoices", "amount": "amount_usd",
        "why": "Under- or over-billing against the price book is the most direct form of revenue leakage.",
    },
    {
        "id": "status_conflict", "title": "Source systems disagree on an invoice's status",
        "rule": "Data contract §3 precedence refunded > paid > failed > void > pending",
        "kind": "decision_required",
        "where": "dq_flags LIKE '%dedup_conflict%'", "table": "invoices", "amount": "abs(amount_usd)",
        "why": "If the precedence rule picked the wrong record, revenue is mis-stated by the invoice amount.",
    },
    {
        "id": "refund_without_payment", "title": "Refund on an account with no paid invoice in the ledger",
        "rule": "A refund should reverse a recorded payment",
        "kind": "needs_investigation",
        "where": "status = 'refunded' AND NOT EXISTS (SELECT 1 FROM invoices p WHERE p.account_id = invoices.account_id AND p.status = 'paid')",
        "table": "invoices", "amount": "abs(amount_usd)",
        "why": "Money returned with no matching receipt. May be real leakage, or the payment sits under another account_id "
               "(account identity is ambiguous: 200 names over 3,815 ids).",
    },
    {
        "id": "refund_before_first_payment", "title": "Refund dated before the account's first paid invoice",
        "rule": "A refund cannot precede the payment it reverses",
        "kind": "needs_investigation",
        "where": "status = 'refunded' AND invoice_date < (SELECT MIN(p.invoice_date) FROM invoices p WHERE p.account_id = invoices.account_id AND p.status = 'paid')",
        "table": "invoices", "amount": "abs(amount_usd)",
        "why": "Timeline impossibility: either a date was mis-parsed/mis-keyed or the refund is not tied to this account's payments.",
    },
    {
        "id": "aged_receivables", "title": "Pending/failed invoices older than 90 days",
        "rule": "Pending/failed are not revenue; long-unresolved ones are at risk of never being collected",
        "kind": "needs_investigation",
        "where": "status IN ('pending','failed') AND invoice_date < current_date - INTERVAL 90 DAY",
        "table": "invoices", "amount": "amount_usd",
        "why": "Billed but uncollected. Not a loss until written off — a collections queue.",
    },
    {
        "id": "future_dated_paid", "title": "Paid invoices dated after today",
        "rule": "Recognized revenue should not include invoices not yet issued",
        "kind": "needs_investigation",
        "where": "status = 'paid' AND invoice_date > current_date",
        "table": "invoices", "amount": "amount_usd",
        "why": "Counted in all-time paid revenue today; likely a date-entry or export issue (or pre-billing).",
    },
]


def _discount_check() -> dict:
    policy = os.getenv("DISCOUNT_POLICY_MAX_PCT", "").strip()
    sql_tiers = "SELECT CAST(discount_pct AS INTEGER) AS tier, COUNT(*) FROM invoices WHERE status='paid' GROUP BY 1 ORDER BY 1"
    tiers = _q(sql_tiers)
    given = float(_q("SELECT SUM(list_price_usd*seats*billed_months*discount_pct/100) FROM invoices WHERE status='paid'")[0][0])
    base = {"id": "discount_policy", "title": "Discounts above policy", "rule": "Discount policy (not provided in the brief)",
            "why": "Unapproved discounting is classic leakage, but only a policy can say what is 'unapproved'.",
            "sql": sql_tiers, "evidence_extra": {"discount_tiers_on_paid_invoices": {str(t): n for t, n in tiers},
                                                   "total_discount_given_usd": round(given, 2)}}
    if not policy:
        return {**base, "kind": "needs_policy", "count": 0, "exposure_usd": 0.0, "sample_invoice_ids": [],
                "summary": f"All paid-invoice discounts sit on standard tiers {sorted(t for t, _ in tiers)}%. ${given:,.2f} of list-price "
                           "discount was given; without CloudNova's discount policy none of it can be called leakage. "
                           "Set DISCOUNT_POLICY_MAX_PCT to evaluate."}
    try:
        cap = float(policy)
    except ValueError as exc:
        raise AppError("invalid_config", "DISCOUNT_POLICY_MAX_PCT must be a number", 500) from exc
    where = f"status = 'paid' AND discount_pct > {cap}"
    n, amt = _q(f"SELECT COUNT(*), COALESCE(SUM(list_price_usd*seats*billed_months*(discount_pct-{cap})/100),0) FROM invoices WHERE {where}")[0]
    return {**base, "kind": "rule_violation" if n else "control_passed", "count": n, "exposure_usd": round(float(amt), 2),
            "sql": f"SELECT invoice_id FROM invoices WHERE {where}", "sample_invoice_ids": _sample(f"SELECT invoice_id FROM invoices WHERE {where} ORDER BY invoice_id"),
            "summary": f"{n} paid invoices exceed the {cap:g}% policy; discount above policy = ${float(amt):,.2f} (list-price basis)."}


def run_checks() -> list[dict]:
    out = []
    for c in CHECKS:
        sql = f"SELECT invoice_id FROM {c['table']} WHERE {c['where']}"
        n, amt = _q(f"SELECT COUNT(*), COALESCE(SUM({c['amount']}), 0) FROM {c['table']} WHERE {c['where']}")[0]
        kind = c["kind"] if n else "control_passed"
        out.append({"id": c["id"], "title": c["title"], "rule": c["rule"], "why": c["why"], "kind": kind, "count": int(n),
                    "exposure_usd": round(float(amt), 2), "sql": sql,
                    "sample_invoice_ids": _sample(sql + " ORDER BY invoice_id") if n else [],
                    "summary": (f"{n:,} invoice(s), ${float(amt):,.2f} at stake (not a confirmed loss)." if n else
                                "Check ran on all 5,000 invoices and found nothing.")})
    out.append(_discount_check())
    fx = _q("SELECT COUNT(*), SUM(amount_usd) - SUM(amount_usd_alt) FROM invoices WHERE status='paid' AND currency <> 'USD'")[0]
    out.append({"id": "fx_direction", "title": "FX conversion may be applied twice", "rule": "Data contract §6 open question",
                "kind": "decision_required", "count": int(fx[0]), "exposure_usd": round(float(fx[1]), 2),
                "sql": "SELECT SUM(amount_usd) - SUM(amount_usd_alt) FROM invoices WHERE status='paid' AND currency <> 'USD'",
                "sample_invoice_ids": _sample("SELECT invoice_id FROM invoices WHERE status='paid' AND currency <> 'USD' ORDER BY invoice_id"),
                "why": "Every EUR/GBP amount equals USD list × rate, so × rate again may overstate non-USD revenue.",
                "summary": f"Paid non-USD revenue differs by ${float(fx[1]):,.2f} between the documented and inverse FX rule."})
    status = _statuses()
    for f in out:
        st = status.get(f["id"], {})
        f["investigation"] = {"status": st.get("status", "resolved" if f["kind"] == "control_passed" else "open"),
                              "note": st.get("note", ""), "updated_at": st.get("updated_at")}
    order = {"rule_violation": 0, "decision_required": 1, "needs_investigation": 2, "needs_policy": 3, "control_passed": 4}
    return sorted(out, key=lambda f: (order[f["kind"]], -f["exposure_usd"]))


# ---------------------------------------------------------------- investigation status (runtime store, never the ledger)
def _db():
    s = get_settings()
    s.runtime_dir.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(s.runtime_dir / "copilot.db")
    con.execute("CREATE TABLE IF NOT EXISTS investigations (finding_id TEXT PRIMARY KEY, status TEXT, note TEXT, updated_at REAL)")
    return con


def _statuses() -> dict:
    with closing(_db()) as con:
        return {r[0]: {"status": r[1], "note": r[2], "updated_at": r[3]} for r in con.execute("SELECT * FROM investigations")}


def set_status(finding_id: str, status: str, note: str = "") -> dict:
    valid_ids = {c["id"] for c in CHECKS} | {"discount_policy", "fx_direction"}
    if finding_id not in valid_ids:
        raise AppError("not_found", f"No finding '{finding_id}'.", 404)
    if status not in STATUSES:
        raise AppError("invalid_status", f"status must be one of {', '.join(STATUSES)}", 422)
    with closing(_db()) as con:
        con.execute("INSERT OR REPLACE INTO investigations VALUES (?,?,?,?)", (finding_id, status, note[:500], time.time()))
        con.commit()
    return {"finding_id": finding_id, "status": status, "note": note[:500]}


def summary(findings: list[dict]) -> dict:
    by_kind: dict = {}
    for f in findings:
        by_kind[f["kind"]] = by_kind.get(f["kind"], 0) + 1
    return {"findings_by_kind": by_kind, "note": "Exposure is dollars at stake pending investigation — not recovered or confirmed-lost revenue. "
                                        "Findings overlap (one invoice can appear in several), so do not add them up."}
