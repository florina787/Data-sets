"""Financial Investigation Studio: Revenue Constellation · Investigation Replay · Decision Butterfly.

Every node and edge is derived from a database fact; nothing is inferred or invented:
  account —billed→ invoice                      invoices.account_id
  invoice —flagged_by→ discrepancy              the leakage check's own WHERE clause (app/enhancements/leakage.py)
  invoice —governed_by→ PDR-001 (FX)            currency <> 'USD'
  invoice —resolved_by→ status precedence       dq_flags contains dedup_conflict
  account —identity_question→ PDR-002           the account's invoices carry more than one account_name
Proposed policy interpretations are always labelled "proposed — not approved" unless the active policy says otherwise.
"""
from __future__ import annotations

import csv
import hashlib
import json
from decimal import Decimal

from . import db
from .config import get_settings
from .errors import AppError
from .pipeline import rules as R

DISCREPANCIES = {  # id → (label, WHERE over invoices aliased as i) — reuses the leakage checks' definitions
    "status_conflict": ("Status conflict between source systems", "i.dq_flags LIKE '%dedup_conflict%'"),
    "refund_without_payment": ("Refund with no recorded payment", "i.status='refunded' AND NOT EXISTS (SELECT 1 FROM invoices p WHERE p.account_id=i.account_id AND p.status='paid')"),
    "refund_before_first_payment": ("Refund before first payment", "i.status='refunded' AND i.invoice_date < (SELECT MIN(p.invoice_date) FROM invoices p WHERE p.account_id=i.account_id AND p.status='paid')"),
    "future_dated_paid": ("Paid invoice dated in the future", "i.status='paid' AND i.invoice_date > current_date"),
    "aged_receivable": ("Pending/failed > 90 days", "i.status IN ('pending','failed') AND i.invoice_date < current_date - INTERVAL 90 DAY"),
    "ambiguous_date": ("Ambiguous DD-MM date", "i.date_was_ambiguous"),
}
POLICIES = {
    "PDR-001": {"label": "PDR-001 · FX direction", "key": "fx_direction"},
    "PDR-002": {"label": "PDR-002 · Account identity", "key": "account_identity"},
    "PRECEDENCE": {"label": "Dedup status precedence", "key": None},
}


def _q(sql, params=None):
    return db.connection().execute(sql, params or []).fetchall()


def _f(v):
    return float(v) if isinstance(v, Decimal) else v


# ---------------------------------------------------------------- 1. Revenue Constellation
def graph(q: str = "", region: str = "", plan: str = "", flag: str = "", accounts: int = 12) -> dict:
    accounts = max(1, min(int(accounts), 40))
    where, params = ["1=1"], []
    if region:
        where.append("a.region = ?"); params.append(region)
    if plan:
        where.append("a.plan = ?"); params.append(plan)
    if q:
        where.append("(a.account_id ILIKE ? OR a.account_name ILIKE ? OR a.account_id IN (SELECT account_id FROM invoices WHERE invoice_id ILIKE ?))")
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    if flag:
        if flag not in DISCREPANCIES:
            raise AppError("invalid_filter", f"Unknown discrepancy filter '{flag}'.", 422)
        where.append(f"a.account_id IN (SELECT i.account_id FROM invoices i WHERE {DISCREPANCIES[flag][1]})")
    accs = _q(f"""SELECT a.account_id, a.account_name, a.region, a.plan, a.net_revenue_usd, a.current_mrr_usd, a.churned, a.csat_score, a.invoice_count
                  FROM accounts a WHERE {' AND '.join(where)} ORDER BY a.net_revenue_usd DESC, a.account_id LIMIT {accounts}""", params)
    ids = [a[0] for a in accs]
    if not ids:
        return {"nodes": [], "edges": [], "filters": {"q": q, "region": region, "plan": plan, "flag": flag}, "legend": _legend()}
    ph = ",".join("?" * len(ids))
    invs = _q(f"""SELECT invoice_id, account_id, status, amount_usd, currency, invoice_date, plan, dq_flags FROM invoices
                  WHERE account_id IN ({ph}) ORDER BY account_id, invoice_date""", ids)
    inv_ids = [r[0] for r in invs]
    iph = ",".join("?" * len(inv_ids))
    nodes, edges = [], []
    for a in accs:
        nodes.append({"id": f"acc:{a[0]}", "type": "account", "label": a[1], "ref": a[0], "region": a[2], "plan": a[3],
                      "net_revenue_usd": _f(a[4]), "mrr_usd": _f(a[5]), "churned": a[6], "csat": a[7], "invoices": a[8]})
    for inv in invs:
        nodes.append({"id": f"inv:{inv[0]}", "type": "invoice", "label": inv[0], "ref": inv[0], "status": inv[2], "amount_usd": _f(inv[3]),
                      "currency": inv[4], "invoice_date": inv[5].isoformat(), "plan": inv[6]})
        edges.append({"from": f"acc:{inv[1]}", "to": f"inv:{inv[0]}", "type": "billed", "evidence": "invoices.account_id"})
    used_disc, used_pol = set(), set()
    for did, (label, cond) in DISCREPANCIES.items():
        for (iid,) in _q(f"SELECT i.invoice_id FROM invoices i WHERE i.invoice_id IN ({iph}) AND {cond}", inv_ids):
            edges.append({"from": f"inv:{iid}", "to": f"disc:{did}", "type": "flagged_by", "evidence": cond}); used_disc.add(did)
    for (iid,) in _q(f"SELECT invoice_id FROM invoices WHERE invoice_id IN ({iph}) AND currency <> 'USD'", inv_ids):
        edges.append({"from": f"inv:{iid}", "to": "pol:PDR-001", "type": "governed_by", "evidence": "currency <> 'USD'"}); used_pol.add("PDR-001")
    for (iid,) in _q(f"SELECT invoice_id FROM invoices WHERE invoice_id IN ({iph}) AND dq_flags LIKE '%dedup_conflict%'", inv_ids):
        edges.append({"from": f"inv:{iid}", "to": "pol:PRECEDENCE", "type": "resolved_by", "evidence": "dq_flags contains dedup_conflict"}); used_pol.add("PRECEDENCE")
    for (aid,) in _q(f"SELECT account_id FROM invoices WHERE account_id IN ({ph}) GROUP BY 1 HAVING COUNT(DISTINCT account_name) > 1", ids):
        edges.append({"from": f"acc:{aid}", "to": "pol:PDR-002", "type": "identity_question", "evidence": "more than one account_name on this account_id"}); used_pol.add("PDR-002")
    totals = {did: n for did, n in ((d, _q(f"SELECT COUNT(*) FROM invoices i WHERE {c}")[0][0]) for d, (_, c) in DISCREPANCIES.items())}
    for did in used_disc:
        nodes.append({"id": f"disc:{did}", "type": "discrepancy", "label": DISCREPANCIES[did][0], "ref": did, "ledger_total": totals[did]})
    from .policy import active
    act = active()
    for pid in used_pol:
        k = POLICIES[pid]["key"]
        nodes.append({"id": f"pol:{pid}", "type": "policy", "label": POLICIES[pid]["label"], "ref": pid, "policy_key": k,
                      "active_value": act["rules"].get(k) if k else "refunded > paid > failed > void > pending",
                      "status": f"active v{act['version']}" + ("" if k is None else " — alternative proposed, not approved")})
    return {"nodes": nodes, "edges": edges, "filters": {"q": q, "region": region, "plan": plan, "flag": flag},
            "counts": {"accounts": len(accs), "invoices": len(invs), "edges": len(edges)}, "legend": _legend()}


def _legend():
    return {"account": "customer account (account_id)", "invoice": "clean invoice", "discrepancy": "deterministic check that flagged an invoice",
            "policy": "financial policy / open decision", "edges": {"billed": "invoices.account_id", "flagged_by": "check WHERE clause",
                                                                     "governed_by": "non-USD → FX rule", "resolved_by": "dedup conflict → precedence",
                                                                     "identity_question": "account carries >1 name"}}


# ---------------------------------------------------------------- 2. Investigation Replay
def replay(invoice_id: str) -> dict:
    if not invoice_id or len(invoice_id) > 40 or not invoice_id.replace("-", "").isalnum():
        raise AppError("invalid_invoice_id", "Invoice ids look like INV-100010.", 422)
    s = get_settings()
    cols = [c[0] for c in db.connection().execute("SELECT * FROM invoices LIMIT 0").description]
    row = _q("SELECT * FROM invoices WHERE invoice_id = ?", [invoice_id])
    if not row:
        raise AppError("not_found", f"No invoice {invoice_id} in the clean ledger.", 404)
    inv = dict(zip(cols, row[0]))
    raw_all = []
    with open(s.raw_csv, newline="") as fh:
        for n, r in enumerate(csv.DictReader(fh), start=2):
            if r["invoice_id"].strip() == invoice_id:
                raw_all.append({"raw_row_number": n, **r})
    kept_raw = next(r for r in raw_all if r["raw_row_number"] == inv["raw_row_number"])
    rejected = [{"raw_row_number": r[0], "reason": r[1], "status": r[2]} for r in
                _q("SELECT raw_row_number, reason, status FROM rejected_rows WHERE invoice_id = ? ORDER BY raw_row_number", [invoice_id])]
    conflict = _q("SELECT candidate_statuses, raw_statuses, winner_status, usd_at_stake FROM dedup_conflicts WHERE invoice_id = ?", [invoice_id])
    man = json.loads((s.data_dir / "manifest.json").read_text())

    # normalization, re-run now with the same rule functions (reproducibility check)
    plan = R.norm_plan(kept_raw["plan"]); cyc = R.norm_cycle(kept_raw["billing_cycle"]); st = R.norm_status(kept_raw["status"])
    amt, emb = R.parse_amount(kept_raw["amount"]); d, amb = R.parse_date(kept_raw["invoice_date"]); em, rep = R.norm_email(kept_raw["contact_email"])
    norm = [
        {"field": "plan", "raw": kept_raw["plan"], "clean": inv["plan"], "rule": f"PLAN_MAP['{kept_raw['plan'].strip().lower()}']", "reproduced": plan == inv["plan"]},
        {"field": "billing_cycle", "raw": kept_raw["billing_cycle"], "clean": inv["billing_cycle"], "rule": "CYCLE_MAP (annual bills 10 months)", "reproduced": cyc == inv["billing_cycle"]},
        {"field": "status", "raw": kept_raw["status"], "clean": inv["status"], "rule": "STATUS_MAP (BUSINESS_CONTEXT table)", "reproduced": st == inv["status"]},
        {"field": "amount", "raw": kept_raw["amount"], "clean": f"{_f(inv['amount_local']):,.2f} {inv['currency']}", "rule": "strip symbol/suffix/commas" + (f"; embedded {emb}" if emb else ""), "reproduced": amt == inv["amount_local"]},
        {"field": "invoice_date", "raw": kept_raw["invoice_date"], "clean": inv["invoice_date"].isoformat(),
         "rule": "DD-MM-YYYY (ambiguous — flagged)" if amb else "evidence-based date rule (spec §5.2)", "reproduced": d == inv["invoice_date"]},
        {"field": "contact_email", "raw": kept_raw["contact_email"], "clean": inv["contact_email"] or "NULL", "rule": "'_at_' → '@'" if rep else "lower-case; invalid/blank → NULL", "reproduced": em == inv["contact_email"]},
    ]
    rate = Decimal(str(s.fx_to_usd[inv["currency"]]))
    list_price = R.LIST_PRICE_USD[inv["plan"]]
    months = R.BILLED_MONTHS[inv["billing_cycle"]]
    expected_usd = (Decimal(list_price) * inv["seats"] * months * (1 - inv["discount_pct"] / 100)).quantize(Decimal("0.01"))
    doc_usd, inv_usd = (inv["amount_local"] * rate).quantize(Decimal("0.01")), (inv["amount_local"] / rate).quantize(Decimal("0.01"))
    calc = {
        "price_book": f"{list_price} × {inv['seats']} seats × {months} month(s) × (1 − {_f(inv['discount_pct'])}%) = ${_f(expected_usd):,.2f}",
        "expected_usd": _f(expected_usd),
        "mrr": f"{list_price} × {inv['seats']} × (1 − {_f(inv['discount_pct'])}%) = ${_f(inv['mrr_usd']):,.2f} per month",
        "fx": {"rate": _f(rate), "documented": _f(doc_usd), "inverse": _f(inv_usd), "active_rule": man.get("fx_direction"),
               "stored_amount_usd": _f(inv["amount_usd"])},
        "matches_price_book": {"documented": abs(abs(doc_usd) - expected_usd) <= 1, "inverse": abs(abs(inv_usd) - expected_usd) <= 1},
        "counts_toward": [m for m, ok in (("paid_revenue", inv["status"] == "paid"), ("net_revenue", inv["status"] in ("paid", "refunded")),
                                          ("refunds", inv["status"] == "refunded"), ("exposure", inv["status"] in ("pending", "failed"))) if ok] or ["no revenue metric (void)"],
    }
    flags = [f for f in (inv["dq_flags"] or "").split(";") if f]
    findings = [did for did, (_, cond) in DISCREPANCIES.items() if _q(f"SELECT 1 FROM invoices i WHERE i.invoice_id = ? AND {cond}", [invoice_id])]
    try:  # independent check: the stdlib oracle re-derives this invoice from the raw CSV without app code
        from evals.oracle import invoices as oracle_invoices
        o = next((x for x in oracle_invoices() if x["invoice_id"] == invoice_id), None)
        oracle = {"status": o["status"], "amount_usd_documented": float(o["usd"]), "agrees": o["status"] == inv["status"] and
                  abs(float(o["usd"]) - float(doc_usd)) < 0.01} if o else None
    except Exception:  # pragma: no cover - evals package absent
        oracle = None
    snapshot = _q("""SELECT invoice_id FROM invoices WHERE account_id = ? ORDER BY invoice_date DESC, invoice_id DESC LIMIT 1""", [inv["account_id"]])[0][0]
    steps = [
        {"step": "Imported", "summary": f"{len(raw_all)} raw row(s) in {man['raw_csv']} carry this invoice id",
         "evidence": {"file": man["raw_csv"], "sha256": man["raw_sha256"], "raw_rows": [{k: v for k, v in r.items()} for r in raw_all]}},
        {"step": "Normalized", "summary": f"{sum(n['reproduced'] for n in norm)}/{len(norm)} fields reproduced now by app/pipeline/rules.py", "evidence": norm},
        {"step": "Reconciled", "summary": {"unique": "only one record — nothing to reconcile", "synonym_collapsed": "duplicates agreed after normalization; one kept",
                                           "conflict_precedence": "systems disagreed; status precedence chose the winner"}[inv["dedup_rule"]],
         "evidence": {"dedup_rule": inv["dedup_rule"], "kept_raw_row": inv["raw_row_number"], "rejected": rejected,
                      "conflict": dict(zip(["candidate_statuses", "raw_statuses", "winner", "usd_at_stake"], [_f(x) for x in conflict[0]])) if conflict else None}},
        {"step": "Calculated", "summary": calc["price_book"], "evidence": calc},
        {"step": "Evaluated", "summary": f"{len(flags)} data-quality flag(s), {len(findings)} discrepancy check(s); oracle {'agrees' if oracle and oracle['agrees'] else 'n/a' if not oracle else 'DISAGREES'}",
         "evidence": {"dq_flags": flags, "discrepancies": findings, "oracle": oracle, "is_account_snapshot_invoice": snapshot == invoice_id,
                      "policy_version": man.get("policy_version", "1.0")}},
    ]
    bundle = {"invoice_id": invoice_id, "account_id": inv["account_id"], "steps": steps}
    bundle["evidence_hash"] = hashlib.sha256(json.dumps(bundle, sort_keys=True, default=str).encode()).hexdigest()
    return bundle


# ---------------------------------------------------------------- 3. Decision Butterfly
def butterfly(key: str) -> dict:
    from .policy import DECISION_KEYS, active
    if key not in DECISION_KEYS:
        raise AppError("unknown_policy", f"Unknown policy '{key}'.", 404)
    act = active()
    current = act["rules"][key]
    out = {"key": key, "active_value": current, "policy_version": act["version"], "record": DECISION_KEYS[key]["record"],
           "interpretations": []}
    if key == "fx_direction":
        cur_col = "amount_usd"
        alt_col = "amount_usd_alt"
        cols = {current: cur_col, ("inverse" if current == "documented" else "documented"): alt_col}
        metric_sql = {
            "Paid revenue (all time)": "SUM({c}) FILTER (WHERE status='paid')",
            "Q1 · paid revenue 2024": "SUM({c}) FILTER (WHERE status='paid' AND invoice_year=2024)",
            "Net revenue": "SUM({c}) FILTER (WHERE status IN ('paid','refunded'))",
            "Q3 · refunds": "SUM({c}) FILTER (WHERE status='refunded')",
            "Q6 · pending/failed exposure": "SUM({c}) FILTER (WHERE status IN ('pending','failed'))",
            "Average paid invoice": "AVG({c}) FILTER (WHERE status='paid')",
        }
        vals = {opt: {m: float(_q(f"SELECT {sql.format(c=c)} FROM invoices")[0][0]) for m, sql in metric_sql.items()} for opt, c in cols.items()}
        top5 = {opt: [r[0] for r in _q(f"SELECT account_id FROM invoices WHERE status IN ('paid','refunded') GROUP BY 1 ORDER BY SUM({c}) DESC, 1 LIMIT 5")]
                for opt, c in cols.items()}
        unaffected = ["MRR & Q2 average MRR (list-price based)", "Q4 churn rate", "Q6 invoice count", "Discounts given (list-price based)", "Account counts"]
    else:
        def by_key(k):
            snap = f"""WITH l AS (SELECT {k} AS ak, region, plan, churned, mrr_usd, ROW_NUMBER() OVER (PARTITION BY {k} ORDER BY invoice_date DESC, invoice_id DESC) rn FROM invoices)
                       SELECT * FROM l WHERE rn = 1"""
            top_region, avg_mrr = _q(f"SELECT region, AVG(mrr_usd) m FROM ({snap}) WHERE NOT churned GROUP BY 1 ORDER BY m DESC LIMIT 1")[0]
            ent, sta = [float(_q(f"SELECT AVG(CASE WHEN churned THEN 1.0 ELSE 0 END) FROM ({snap}) WHERE plan = '{p}'")[0][0]) for p in ("Enterprise", "Starter")]
            return {"Accounts": float(_q(f"SELECT COUNT(DISTINCT {k}) FROM invoices")[0][0]), "Q2 · top region avg MRR": float(avg_mrr),
                    "Q4 · Enterprise churn": ent, "Q4 · Starter churn": sta, "_top_region": top_region}
        cols = {"account_id": "account_id", "account_name": "account_name"}
        vals = {opt: by_key(c) for opt, c in cols.items()}
        top5 = {opt: [r[0] for r in _q(f"SELECT {c} FROM invoices WHERE status IN ('paid','refunded') GROUP BY 1 ORDER BY SUM(amount_usd) DESC, 1 LIMIT 5")]
                for opt, c in cols.items()}
        unaffected = ["Paid / net revenue totals", "Refunds", "Exposure", "MRR total"]
    base = vals[current]
    for opt in DECISION_KEYS[key]["options"]:
        v = vals[opt]
        metrics = [{"metric": m, "value": v[m], "baseline": base[m], "delta": v[m] - base[m]} for m in v if not m.startswith("_")]
        out["interpretations"].append({
            "value": opt, "description": DECISION_KEYS[key]["options"][opt],
            "status": "active (approved)" if opt == current and act["version"] != "1.0" else "active (original rules v1.0)" if opt == current else
                      ("proposed — blocked: " + DECISION_KEYS[key]["blocked"][opt]) if opt in DECISION_KEYS[key].get("blocked", {}) else "proposed — not approved",
            "metrics": metrics, "top5": top5[opt], "top5_changed": top5[opt] != top5[current],
            "top_region": v.get("_top_region")})
    out["unaffected"] = unaffected
    return out
