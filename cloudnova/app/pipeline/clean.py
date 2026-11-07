"""Raw CSV → clean tables, implementing specs/cloudnova_data_contract.md.

Invariant (tested): every raw row lands in exactly one of `invoices` or `rejected_rows`.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pandas as pd

from . import rules as R

RAW_COLUMNS = ["invoice_id", "account_id", "account_name", "contact_email", "region", "industry", "plan",
               "billing_cycle", "seats", "currency", "amount", "discount_pct", "status", "payment_method",
               "signup_date", "invoice_date", "churned", "csat_score", "support_tickets"]
# columns compared to decide "synonym duplicate" vs "conflict" (normalized values)
_COMPARE = ["account_id", "plan", "billing_cycle", "seats", "currency", "amount_local", "discount_pct", "status",
            "invoice_date", "region", "churned", "csat_score"]


@dataclass
class CleanResult:
    invoices: pd.DataFrame
    accounts: pd.DataFrame
    rejected_rows: pd.DataFrame
    dedup_conflicts: pd.DataFrame
    dq_issues: pd.DataFrame
    stats: dict


def load_raw(path) -> pd.DataFrame:
    """Read the ledger through the source-adapter seam (app/sources) so other systems can feed the same contract."""
    from ..sources.base import CsvLedgerAdapter
    df = CsvLedgerAdapter(path).extract().rows
    df.insert(0, "raw_row_number", range(2, len(df) + 2))  # 1-based incl. header, as seen in a spreadsheet
    return df


def _normalize_row(r: dict, fx: dict, direction: str, today: date) -> tuple[dict | None, str | None, list[str]]:
    """Returns (clean_row, reject_reason, dq_flags)."""
    flags: list[str] = []
    plan = R.norm_plan(r["plan"])
    if plan is None:
        return None, "unknown_plan", flags
    cycle = R.norm_cycle(r["billing_cycle"])
    if cycle is None:
        return None, "unknown_billing_cycle", flags
    status = R.norm_status(r["status"])
    if status is None:
        return None, "unknown_status", flags
    currency = r["currency"].strip().upper()
    if currency not in R.CURRENCIES:
        return None, "unknown_currency", flags
    amount, embedded = R.parse_amount(r["amount"])
    if amount is None:
        return None, "unparseable_amount", flags
    if embedded and embedded != currency:
        flags.append("currency_mismatch")
    seats = R.parse_int(r["seats"])
    if not seats or seats <= 0:
        return None, "invalid_seats", flags
    try:
        discount = Decimal(r["discount_pct"].strip() or "0")
    except Exception:
        return None, "unparseable_discount", flags
    if not (0 <= discount < 100):
        return None, "invalid_discount", flags
    inv_date, ambiguous = R.parse_date(r["invoice_date"])
    if inv_date is None:
        return None, "unparseable_invoice_date", flags
    signup, signup_amb = R.parse_date(r["signup_date"])
    if r["signup_date"].strip() and signup is None:
        flags.append("unparseable_signup_date")
    if ambiguous:
        flags.append("ambiguous_invoice_date")
    if signup_amb:
        flags.append("ambiguous_signup_date")
    if signup and inv_date < signup:
        flags.append("invoice_before_signup")
    if inv_date > today:
        flags.append("future_invoice_date")
    email, repaired = R.norm_email(r["contact_email"])
    if repaired:
        flags.append("email_repaired")
    if r["contact_email"].strip() and email is None:
        flags.append("email_invalid")
    if not r["contact_email"].strip():
        flags.append("email_missing")
    region = r["region"].strip().upper() or None
    if region not in R.REGIONS:
        flags.append("region_invalid")
        region = None
    csat = R.parse_int(r["csat_score"])
    if csat is not None and not 1 <= csat <= 5:
        flags.append("csat_out_of_range")
        csat = None
    if csat is None:
        flags.append("csat_missing")
    industry = R.norm_text(r["industry"])
    if industry is None:
        flags.append("industry_missing")
    churned = R.norm_bool(r["churned"])
    if churned is None:
        flags.append("churned_unknown")
    pm = R.norm_payment(r["payment_method"])
    if pm is None:
        flags.append("payment_method_missing")
    if status == "refunded" and amount >= 0:
        flags.append("refund_not_negative")
    if status != "refunded" and amount < 0:
        flags.append(f"negative_amount_on_{status}")
    rate = fx[currency]
    mrr = R.mrr_usd(plan, seats, discount)
    months = R.BILLED_MONTHS[cycle]
    expected_local = (mrr * months * Decimal(str(rate))).quantize(Decimal("0.01"))
    if status != "refunded" and abs(abs(amount) - expected_local) > Decimal("1.00"):
        flags.append("pricing_violation")
    tickets = R.parse_int(r["support_tickets"])
    return {
        "invoice_id": r["invoice_id"].strip(),
        "account_id": r["account_id"].strip(),
        "account_name": R.norm_text(r["account_name"]),
        "contact_email": email,
        "email_was_repaired": repaired,
        "region": region,
        "industry": industry,
        "plan": plan,
        "billing_cycle": cycle,
        "billed_months": months,
        "seats": seats,
        "currency": currency,
        "amount_local": amount,
        "fx_rate_to_usd": rate,
        "amount_usd": R.to_usd(amount, rate, direction),
        "amount_usd_alt": R.to_usd(amount, rate, "inverse" if direction == "documented" else "documented"),
        "discount_pct": discount,
        "list_price_usd": R.LIST_PRICE_USD[plan],
        "mrr_usd": mrr,
        "expected_amount_usd": (mrr * months).quantize(Decimal("0.01")),
        "status_raw": r["status"],
        "status": status,
        "is_revenue": status in R.REVENUE_STATUSES,
        "payment_method": pm,
        "signup_date": signup,
        "invoice_date": inv_date,
        "invoice_year": inv_date.year,
        "invoice_month": inv_date.strftime("%Y-%m"),
        "date_was_ambiguous": ambiguous,
        "churned": churned,
        "csat_score": csat,
        "support_tickets": tickets if tickets is not None and tickets >= 0 else None,
        "raw_row_number": r["raw_row_number"],
    }, None, flags


def clean(raw: pd.DataFrame, fx: dict, direction: str = "documented", today: date | None = None) -> CleanResult:
    today = today or date.today()
    rejected: list[dict] = []
    conflicts: list[dict] = []

    def reject(row: dict, reason: str, **extra) -> None:
        raw_rec = {c: row[c] for c in RAW_COLUMNS}
        # best-effort financial view of the rejected row, so reconciliation can show what keeping it would have cost
        st = R.norm_status(row["status"])
        amt, _ = R.parse_amount(row["amount"])
        ccy = row["currency"].strip().upper()
        usd = float(R.to_usd(amt, fx[ccy], direction)) if amt is not None and ccy in fx else None
        rejected.append({"raw_row_number": row["raw_row_number"], "invoice_id": row["invoice_id"].strip(),
                         "reason": reason, "status": st, "amount_usd": usd, "raw_record": json.dumps(raw_rec), **extra})

    # 1. exact duplicates (all 19 raw columns identical after trimming)
    key = raw[RAW_COLUMNS].apply(lambda s: s.str.strip())
    dup_mask = key.duplicated(keep="first")
    records = raw.to_dict("records")
    survivors = []
    for rec, is_dup in zip(records, dup_mask):
        (reject(rec, "exact_duplicate") if is_dup else survivors.append(rec))

    # 2. normalize; quarantine unparseable rows
    normalized: list[tuple[dict, list[str]]] = []
    for rec in survivors:
        row, reason, flags = _normalize_row(rec, fx, direction, today)
        if reason:
            reject(rec, reason)
        else:
            normalized.append((row, flags))

    # 3. group by invoice_id: synonym duplicates vs conflicts
    groups: dict[str, list[tuple[dict, list[str]]]] = defaultdict(list)
    for item in normalized:
        groups[item[0]["invoice_id"]].append(item)
    raw_by_row = {r["raw_row_number"]: r for r in survivors}
    out = []
    for inv_id, items in groups.items():
        if len(items) == 1:
            row, flags = items[0]
            row["dedup_rule"] = "unique"
        else:
            sigs = {tuple(str(it[0][c]) for c in _COMPARE) for it in items}
            if len(sigs) == 1:
                row, flags = items[0]
                row["dedup_rule"] = "synonym_collapsed"
                for other, _ in items[1:]:
                    reject(raw_by_row[other["raw_row_number"]], "synonym_duplicate", kept_raw_row=row["raw_row_number"])
            else:
                ranked = sorted(items, key=lambda it: (R.status_rank(it[0]["status"]), it[0]["raw_row_number"]))
                row, flags = ranked[0]
                row["dedup_rule"] = "conflict_precedence"
                flags = flags + ["dedup_conflict"]
                diff_cols = [c for c in _COMPARE if len({str(it[0][c]) for it in items}) > 1]
                conflicts.append({
                    "invoice_id": inv_id,
                    "candidate_statuses": ",".join(it[0]["status"] for it in ranked),
                    "raw_statuses": ",".join(it[0]["status_raw"] for it in ranked),
                    "differing_columns": ",".join(diff_cols),
                    "winner_status": row["status"],
                    "winner_raw_row": row["raw_row_number"],
                    "rule": "precedence refunded>paid>failed>void>pending",
                    "usd_at_stake": float(abs(row["amount_usd"])),
                })
                for other, _ in ranked[1:]:
                    reject(raw_by_row[other["raw_row_number"]], "lost_conflict", kept_raw_row=row["raw_row_number"])
        row["dq_flags"] = ";".join(sorted(set(flags)))
        out.append(row)

    invoices = pd.DataFrame(out).sort_values("invoice_id").reset_index(drop=True)
    rejected_df = pd.DataFrame(rejected, columns=["raw_row_number", "invoice_id", "reason", "status", "amount_usd", "raw_record",
                                                  "kept_raw_row"])
    rejected_df = rejected_df.sort_values("raw_row_number").reset_index(drop=True)
    conflicts_df = pd.DataFrame(conflicts, columns=["invoice_id", "candidate_statuses", "raw_statuses", "differing_columns",
                                                    "winner_status", "winner_raw_row", "rule", "usd_at_stake"])
    accounts = build_accounts(invoices)
    dq = build_dq_issues(raw, invoices, rejected_df, conflicts_df)
    stats = {
        "raw_rows": int(len(raw)),
        "clean_invoices": int(len(invoices)),
        "rejected_rows": int(len(rejected_df)),
        "rejected_by_reason": {k: int(v) for k, v in Counter(rejected_df["reason"]).items()},
        "dedup_conflicts": int(len(conflicts_df)),
        "accounts": int(len(accounts)),
        "fx_direction": direction,
    }
    return CleanResult(invoices, accounts, rejected_df, conflicts_df, dq, stats)


SNAPSHOT_ATTRS = ["account_name", "region", "industry", "plan", "seats", "discount_pct", "churned", "csat_score"]


def build_accounts(inv: pd.DataFrame) -> pd.DataFrame:
    """One row per account_id; attributes from the latest invoice (date, then invoice_id)."""
    srt = inv.sort_values(["account_id", "invoice_date", "invoice_id"])
    latest = srt.groupby("account_id", sort=True).tail(1).set_index("account_id")
    g = inv.groupby("account_id")
    acc = latest[SNAPSHOT_ATTRS + ["mrr_usd"]].rename(columns={"mrr_usd": "current_mrr_usd"}).copy()
    acc["is_active"] = acc["churned"].map(lambda c: c is False or c == False)  # noqa: E712 - NULL churned → not active
    acc["first_invoice_date"] = g["invoice_date"].min()
    acc["last_invoice_date"] = g["invoice_date"].max()
    acc["invoice_count"] = g.size()

    def _sum(status_set):
        sub = inv[inv["status"].isin(status_set)]
        return sub.groupby("account_id")["amount_usd"].apply(lambda s: sum(s, Decimal(0)))

    zero = Decimal("0.00")
    acc["paid_revenue_usd"] = _sum({"paid"}).reindex(acc.index).apply(lambda v: zero if pd.isna(v) else v)
    acc["refunds_usd"] = _sum({"refunded"}).reindex(acc.index).apply(lambda v: zero if pd.isna(v) else v)
    acc["net_revenue_usd"] = acc["paid_revenue_usd"] + acc["refunds_usd"]
    acc["attr_conflicts"] = g[["account_name", "region", "plan", "churned", "csat_score", "industry"]].nunique(dropna=False).gt(1).sum(axis=1)
    return acc.reset_index()


def build_dq_issues(raw: pd.DataFrame, inv: pd.DataFrame, rejected: pd.DataFrame, conflicts: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for reason, n in Counter(rejected["reason"]).items():
        ex = rejected[rejected["reason"] == reason]["invoice_id"].iloc[0]
        rows.append({"issue_code": f"rejected:{reason}", "column": "*", "n_rows": n, "example": ex, "action": "moved to rejected_rows"})
    flag_counts: Counter = Counter()
    examples: dict = {}
    for inv_id, f in zip(inv["invoice_id"], inv["dq_flags"]):
        for code in filter(None, f.split(";")):
            flag_counts[code] += 1
            examples.setdefault(code, inv_id)
    col_of = {"email": "contact_email", "csat": "csat_score", "industry": "industry", "churned": "churned",
              "payment": "payment_method", "ambiguous_invoice": "invoice_date", "ambiguous_signup": "signup_date",
              "invoice_before": "invoice_date", "future": "invoice_date", "region": "region", "pricing": "amount",
              "negative": "amount", "refund": "amount", "currency": "amount", "dedup": "status", "unparseable_signup": "signup_date"}
    action = {"email_repaired": "'_at_' replaced with '@'", "csat_missing": "kept NULL (not imputed)",
              "industry_missing": "kept NULL (not imputed)", "ambiguous_invoice_date": "parsed as DD-MM-YYYY (spec §5.2)",
              "dedup_conflict": "status precedence; loser in rejected_rows", "future_invoice_date": "kept; flagged",
              "negative_amount_on_paid": "kept as-is (nets revenue); flagged for finance"}
    for code, n in sorted(flag_counts.items()):
        col = next((v for k, v in col_of.items() if code.startswith(k)), "*")
        rows.append({"issue_code": code, "column": col, "n_rows": n, "example": examples[code], "action": action.get(code, "flagged")})
    raw_variants = {c: int(raw[c].nunique()) for c in ["plan", "status", "billing_cycle", "payment_method", "churned"]}
    for c, n in raw_variants.items():
        rows.append({"issue_code": f"raw_variants:{c}", "column": c, "n_rows": n, "example": "", "action": "normalized via lookup map"})
    return pd.DataFrame(rows)
