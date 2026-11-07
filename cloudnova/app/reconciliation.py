"""Raw → clean reconciliation with financial impact (fixed, trusted SQL; no user input reaches it).

Answers the finance lead's first question: "you started with 5,125 rows and kept 5,000 — what did you drop, and
what would it have done to my numbers?"
"""
from __future__ import annotations

from . import db

_REV = "('paid','refunded')"


def _rows(sql: str) -> list[tuple]:
    return db.connection().execute(sql).fetchall()


def reconciliation() -> dict:
    raw = db.internal_scalar("SELECT COUNT(*) FROM invoices") + db.internal_scalar("SELECT COUNT(*) FROM rejected_rows")
    clean = db.internal_scalar("SELECT COUNT(*) FROM invoices")
    by_reason = _rows(f"""
        SELECT reason, COUNT(*) AS rows,
               COALESCE(SUM(amount_usd) FILTER (WHERE status = 'paid'), 0)            AS paid_usd,
               COALESCE(SUM(amount_usd) FILTER (WHERE status = 'refunded'), 0)        AS refunded_usd,
               COALESCE(SUM(amount_usd) FILTER (WHERE status IN ('pending','failed')), 0) AS exposure_usd,
               COUNT(DISTINCT invoice_id) AS invoice_ids
        FROM rejected_rows GROUP BY reason
        ORDER BY CASE reason WHEN 'exact_duplicate' THEN 1 WHEN 'synonym_duplicate' THEN 2 WHEN 'lost_conflict' THEN 3 ELSE 4 END""")
    explain = {
        "exact_duplicate": "Byte-identical rows (after trimming) exported twice. Keeping them double-counts the invoice.",
        "synonym_duplicate": "Same invoice from two systems, same facts, status spelled differently (e.g. 'completed' vs 'PAID').",
        "lost_conflict": "Same invoice, systems disagree on status. Precedence refunded > paid > failed > void > pending; "
                         "the losing record is kept here for audit.",
    }
    steps = [{"label": "Raw export rows", "rows": raw, "kind": "total"}]
    remaining = raw
    for reason, n, *_ in by_reason:
        remaining -= n
        steps.append({"label": reason.replace("_", " "), "rows": -n, "kind": "delta"})
    steps.append({"label": "Clean invoices", "rows": clean, "kind": "total"})
    assert remaining == clean, "row accounting broken"  # the invariant the tests also enforce

    clean_paid, clean_net, clean_exp = _rows(f"""SELECT SUM(amount_usd) FILTER (WHERE status='paid'),
        SUM(amount_usd) FILTER (WHERE status IN {_REV}), SUM(amount_usd) FILTER (WHERE status IN ('pending','failed')) FROM invoices""")[0]
    rej_paid, rej_net, rej_exp = _rows(f"""SELECT COALESCE(SUM(amount_usd) FILTER (WHERE status='paid'),0),
        COALESCE(SUM(amount_usd) FILTER (WHERE status IN {_REV}),0),
        COALESCE(SUM(amount_usd) FILTER (WHERE status IN ('pending','failed')),0) FROM rejected_rows""")[0]
    conflicts = _rows(f"""
        SELECT c.invoice_id, c.raw_statuses, c.winner_status, r.status AS loser_status, i.amount_usd,
               (CASE WHEN r.status IN {_REV} THEN r.amount_usd ELSE 0 END) -
               (CASE WHEN i.status IN {_REV} THEN i.amount_usd ELSE 0 END) AS net_revenue_delta_if_loser_won
        FROM dedup_conflicts c
        JOIN invoices i USING (invoice_id)
        JOIN rejected_rows r ON r.invoice_id = c.invoice_id AND r.reason = 'lost_conflict'
        ORDER BY ABS(net_revenue_delta_if_loser_won) DESC, c.invoice_id""")
    swing = sum(float(c[5]) for c in conflicts)
    f = float
    return {
        "raw_rows": raw, "clean_invoices": clean, "rejected_rows": raw - clean, "waterfall": steps,
        "by_reason": [{"reason": r, "rows": n, "invoice_ids": ids, "paid_usd": f(p), "refunded_usd": f(rf), "exposure_usd": f(e),
                       "explanation": explain.get(r, "")} for r, n, p, rf, e, ids in by_reason],
        "impact": {
            "paid_revenue": {"clean": f(clean_paid), "naive_no_dedup": f(clean_paid) + f(rej_paid), "overstatement_avoided": f(rej_paid)},
            "net_revenue": {"clean": f(clean_net), "naive_no_dedup": f(clean_net) + f(rej_net), "overstatement_avoided": f(rej_net)},
            "exposure": {"clean": f(clean_exp), "naive_no_dedup": f(clean_exp) + f(rej_exp), "overstatement_avoided": f(rej_exp)},
        },
        "conflicts": {
            "count": len(conflicts),
            "net_revenue_swing_if_all_losers_won": swing,
            "rows": [{"invoice_id": c[0], "raw_statuses": c[1], "winner": c[2], "loser": c[3], "amount_usd": f(c[4]),
                      "net_revenue_delta_if_loser_won": f(c[5])} for c in conflicts],
        },
        "method": "Naive = the same normalized rows summed without deduplication. Clean = one row per invoice_id per the data "
                  "contract §3. Conflict swing = change in net revenue if every losing record had been chosen instead.",
    }
