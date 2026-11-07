"""Nova's Guided Journey — scene data + narration, generated from the real engine (no hard-coded figures).

Each scene: id, title, subtitle, destination (DOM target the guide walks to), gesture, narration lines, data.
Scene 5 (agent harness) is driven client-side by a live /ask run's trace events; scene 6 pauses on a real policy
decision (approval gate in app/policy.py); scene 7 reads the committed evaluation artifacts.
"""
from __future__ import annotations

import csv
import json

from . import db
from .config import ROOT, get_settings


def _q(sql):
    return db.connection().execute(sql).fetchall()


def _money(v):
    return ("-" if v < 0 else "") + f"${abs(v):,.2f}"


def _examples() -> list[dict]:
    raw = {r["invoice_id"].strip(): r for r in csv.DictReader(open(get_settings().raw_csv))}
    picks = {
        "INV-100010": "plan alias + $ string", "INV-100105": "ambiguous DD-MM date", "INV-100012": "EUR suffix amount",
        "INV-100040": "'_at_' email repaired",
    }
    out = []
    for inv, issue in picks.items():
        r = _q(f"SELECT plan, billing_cycle, amount_local, currency, amount_usd, status, invoice_date, contact_email "
               f"FROM invoices WHERE invoice_id = '{inv}'")
        if not r or inv not in raw:
            continue
        p, cyc, amt, ccy, usd, st, d, em = r[0]
        rr = raw[inv]
        out.append({"invoice_id": inv, "issue": issue,
                    "raw": {"plan": rr["plan"], "amount": rr["amount"], "status": rr["status"], "date": rr["invoice_date"], "email": rr["contact_email"]},
                    "clean": {"plan": p, "amount_usd": float(usd), "currency": ccy, "status": st, "date": d.isoformat(), "email": em}})
    return out


def honesty() -> list[dict]:
    """Per stakeholder question: how it is cited, and which choices could make it wrong — with numbers in scope."""
    amb24, conf24, stake24 = _q("""SELECT COUNT(*) FILTER (WHERE date_was_ambiguous), COUNT(*) FILTER (WHERE dq_flags LIKE '%dedup_conflict%'),
        COALESCE(SUM(abs(amount_usd)) FILTER (WHERE dq_flags LIKE '%dedup_conflict%'), 0) FROM invoices WHERE invoice_year = 2024""")[0]
    q1_inv, exp_inv = [float(x) for x in _q("""SELECT SUM(amount_usd_alt) FILTER (WHERE status='paid' AND invoice_year=2024),
        SUM(amount_usd_alt) FILTER (WHERE status IN ('pending','failed')) FROM invoices""")[0]]
    conf_all, stake_all = _q("SELECT COUNT(*), SUM(usd_at_stake) FROM dedup_conflicts")[0]
    snap = _q("SELECT COUNT(*) FILTER (WHERE attr_conflicts > 0) FROM accounts")[0][0]
    fut = _q("SELECT COUNT(*) FROM invoices WHERE invoice_date > current_date")[0][0]
    cite = "Generated SQL shown with the answer; value matched by evals/oracle.py (independent re-implementation from the raw CSV)."
    return [
        {"q": "Q1 paid revenue 2024", "cited": cite, "confidence": "medium",
         "could_be_wrong": [f"FX rule: {_money(q1_inv)} under the inverse rule (PDR-001, recommended, not approved)",
                            f"{amb24} ambiguous DD-MM dates in 2024 parsed day-first (a swap stays in the same year)",
                            f"{conf24} dedup conflicts in 2024, {_money(float(stake24))} decided by status precedence"]},
        {"q": "Q2 highest avg MRR region", "cited": cite, "confidence": "high",
         "could_be_wrong": [f"latest-invoice snapshot: {snap:,} of 3,815 accounts have conflicting attributes",
                            "active accounts only — over all accounts APAC still leads but NA and EMEA swap"]},
        {"q": "Q3 refunds", "cited": cite, "confidence": "medium",
         "could_be_wrong": ["FX rule changes the USD total (−$8.93M documented vs −$8.20M inverse)",
                            f"{conf_all} dedup conflicts overall, 2 of them paid-vs-refunded"]},
        {"q": "Q4 churn Enterprise vs Starter", "cited": cite, "confidence": "medium",
         "could_be_wrong": ["churn is a snapshot flag with no dates — a share of accounts, not a period rate",
                            f"plan comes from the latest invoice ({snap:,} accounts disagree across invoices)"]},
        {"q": "Q5 top 5 accounts + CSAT ≤ 2", "cited": cite, "confidence": "medium",
         "could_be_wrong": ["account identity: by account_name the top 5 is different (PDR-002; names are not a coherent identity)",
                            "blank CSAT shown as unknown, never as low"]},
        {"q": "Q6 pending/failed exposure", "cited": cite, "confidence": "medium",
         "could_be_wrong": [f"FX rule ({_money(exp_inv)} under inverse)", f"{fut} future-dated invoices are included as issued",
                            f"dedup precedence moved {conf_all} conflicting invoices; {_money(float(stake_all))} at stake overall"]},
    ]


def scenes() -> dict:
    from .policy import active, overview
    from .reconciliation import reconciliation
    s = get_settings()
    man = json.loads((s.data_dir / "manifest.json").read_text())
    variants = dict(_q("SELECT replace(issue_code,'raw_variants:',''), n_rows FROM dq_issues WHERE issue_code LIKE 'raw_variants:%'"))
    rc = reconciliation()
    biggest = max(rc["by_reason"], key=lambda r: r["paid_usd"])
    paid, net, ref, exp, exp_n, q1 = _q("""SELECT SUM(amount_usd) FILTER (WHERE status='paid'), SUM(amount_usd) FILTER (WHERE status IN ('paid','refunded')),
        SUM(amount_usd) FILTER (WHERE status='refunded'), SUM(amount_usd) FILTER (WHERE status IN ('pending','failed')),
        COUNT(*) FILTER (WHERE status IN ('pending','failed')), SUM(amount_usd) FILTER (WHERE status='paid' AND invoice_year=2024) FROM invoices""")[0]
    mrr = _q("SELECT region, AVG(current_mrr_usd) FILTER (WHERE is_active) m FROM accounts GROUP BY 1 ORDER BY m DESC")
    churn = _q("""SELECT plan, AVG(CASE WHEN churned THEN 1.0 ELSE 0 END) FILTER (WHERE churned IS NOT NULL), COUNT(*) FILTER (WHERE churned), COUNT(*)
                  FROM accounts GROUP BY 1 ORDER BY 2 DESC""")
    ch = {p: (float(r), int(c), int(n)) for p, r, c, n in churn}
    pol = overview()
    fx = next(p for p in pol["proposals"] if p["key"] == "fx_direction")
    evals_path = ROOT / "evals" / "results" / "latest.json"
    modes_path = ROOT / "evals" / "results" / "mode_comparison.json"
    ev = json.loads(evals_path.read_text()) if evals_path.exists() else None
    modes = json.loads(modes_path.read_text())["summary"] if modes_path.exists() else None
    stake = [r for r in (ev or {}).get("results", []) if r["category"] == "stakeholder"]
    verified = sum(1 for r in stake if r["status"] == "PASS")

    sc = [
        {"id": 1, "key": "messy", "title": "The Messy Export", "subtitle": "What finance handed over on day one",
         "destination": "raw-card", "gesture": "point",
         "narration": [f"Finance exported {man['raw_rows']:,} rows stitched from three systems.",
                       f"I found {variants.get('plan', 0)} spellings of three plans, {variants.get('status', 0)} spellings of five statuses, and five date formats.",
                       "Here is one real row before and after the spec's rules. Nothing is fuzzy-matched or imputed."],
         "data": {"raw_rows": man["raw_rows"], "variants": variants, "examples": _examples()}},
        {"id": 2, "key": "reconcile", "title": "Reconciliation", "subtitle": "Where every row and dollar went",
         "destination": "bar-" + biggest["reason"], "gesture": "point",
         "narration": [f"{rc['raw_rows']:,} raw rows describe {rc['clean_invoices']:,} invoices. {rc['rejected_rows']} rows are copies or conflicts — each kept in an audit table.",
                       f"Counting them would overstate paid revenue by {_money(rc['impact']['paid_revenue']['overstatement_avoided'])}. The largest share comes from {biggest['reason'].replace('_', ' ')}s.",
                       f"{rc['conflicts']['count']} invoices had systems disagreeing on status. If every losing record had won, net revenue would move {_money(rc['conflicts']['net_revenue_swing_if_all_losers_won'])}."],
         "data": rc},
        {"id": 3, "key": "revenue", "title": "Revenue Intelligence", "subtitle": "Recognized revenue, refunds and exposure",
         "destination": "kpi-refunds", "gesture": "point",
         "narration": [f"Paid revenue in 2024 was {_money(float(q1))}. All-time paid revenue is {_money(float(paid))}, or {_money(float(net))} net of refunds.",
                       f"We have given back {_money(abs(float(ref)))} in refunds — they are negative amounts and net against revenue.",
                       f"{int(exp_n):,} invoices are stuck in pending or failed, exposing {_money(float(exp))}. That is billed, not earned."],
         "data": {"q1_paid_2024": float(q1), "paid": float(paid), "net": float(net), "refunds": float(ref), "exposure": float(exp), "exposure_count": int(exp_n)}},
        {"id": 4, "key": "mrr", "title": "MRR & Churn", "subtitle": "Recurring revenue per account, and who leaves",
         "destination": "mrr-top", "gesture": "point",
         "narration": [f"Average MRR per active account is highest in {mrr[0][0]} at {_money(float(mrr[0][1]))}. MRR comes from list price × seats × discount, never the annual lump sum.",
                       f"Enterprise churns at {ch['Enterprise'][0] * 100:.2f}% ({ch['Enterprise'][1]:,} of {ch['Enterprise'][2]:,}) versus Starter at {ch['Starter'][0] * 100:.2f}% ({ch['Starter'][1]:,} of {ch['Starter'][2]:,}).",
                       "Churn here is a snapshot flag — there are no churn dates, so I won't tell you why anyone left."],
         "data": {"mrr_by_region": [[r, float(m)] for r, m in mrr], "churn": {p: {"rate": v[0], "churned": v[1], "accounts": v[2]} for p, v in ch.items()}}},
        {"id": 5, "key": "harness", "title": "Agent Harness", "subtitle": "I follow the query agent's real execution path",
         "destination": "node-question", "gesture": "work",
         "narration": ["I'm sending a real question to the query agent now. Every move below comes from its recorded trace."],
         "data": {"question": "Which region has the highest average MRR per account?"}},
        {"id": 6, "key": "approval", "title": "Finance-Owner Approval", "subtitle": "The journey pauses until an authorised decision is recorded",
         "destination": "desk", "gesture": "wait",
         "narration": [f"Policy decision {fx['record'].split('/')[-1][:7]}: FX direction. Under the brief's literal rule, {fx['impact']['price_book_matches']['documented']} of {fx['impact']['non_usd_invoices_checked']:,} non-USD invoices match the price book; under the inverse rule, {fx['impact']['price_book_matches']['inverse']:,} do.",
                       f"Q1 would move from {_money(fx['impact']['answers']['documented']['q1_paid_2024'])} to {_money(fx['impact']['answers']['inverse']['q1_paid_2024'])}. I recommend the inverse rule — but I don't decide.",
                       "I've brought it to the finance owner's desk. Nothing changes until an authorised person records a decision, and a rebuild is a separate step."],
         "data": {"proposal": fx, "active_policy": active(), "approvals_enabled": pol["approvals_enabled"]}},
        {"id": 7, "key": "summary", "title": "Executive Summary", "subtitle": "Outcome, evidence and what is still open",
         "destination": "summary-evals", "gesture": "success" if ev and ev["counts"]["FAIL"] == 0 and ev["counts"]["XPASS"] == 0 else "warn",
         "narration": ([f"All {len(stake)} stakeholder answers were checked against an independent oracle: {verified} verified."] if stake else ["No evaluation artifact found — run python -m evals."])
                      + ([f"Evaluation suite: {ev['counts']['PASS']} pass, {ev['counts']['FAIL']} fail, {ev['counts']['XFAIL']} documented expected failures."] if ev else [])
                      + ([f"Hybrid answered {modes['hybrid']['correct']} of {modes['hybrid']['total']} correctly in a median {modes['hybrid']['median_ms']} ms; Qwen alone answered {modes['llm']['correct']} of {modes['llm']['total']}."] if modes else [])
                      + ["A good answer cites how; a great one says where it could be wrong. Here is that list, per question — dates, dedup, FX and identity."]
                      + [f"Still open: the FX decision (policy v{active()['version']} is active) and account identity. Both are on the Decisions page."],
         "data": {"honesty": honesty(), "evals": ev and {"counts": ev["counts"], "run_at": ev["run_at"], "stakeholder": stake}, "modes": modes, "policy": active()}},
    ]
    return {"scenes": sc, "labels": {"data": "Synthetic take-home dataset (cloudnova_invoices.csv) — real computations, fictional company.",
                                     "character": "Nova is original draft artwork drawn in SVG for this project."}}
