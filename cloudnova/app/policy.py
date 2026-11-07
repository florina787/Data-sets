"""Financial policy + approval-gated decisions (Decisions page).

* The ORIGINAL policy (`policies/financial_policy.yaml`, v1.0) is never modified by the app.
* A change needs an explicit finance-owner approval: approver name, role `finance_owner`, a rationale, the
  operator-configured approval PIN (`FINANCE_APPROVER_PIN`; unset → approvals disabled), and the hash of the impact
  report the approver was shown (proves they approved *these* numbers).
* Approval records the decision; the rebuild is a separate, explicit step. Applying writes a new policy version as a
  runtime override and rebuilds DuckDB from the raw CSV. Reverting to the original is itself a decision.
* Eval expectations are not touched: if a new policy changes an answer, the eval suite reports it.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path

import yaml

from .config import ROOT, get_settings
from .errors import AppError

ORIGINAL_PATH = ROOT / "policies" / "financial_policy.yaml"
DECISION_KEYS = {
    "fx_direction": {
        "record": "docs/decisions/PDR-001-fx-direction.md",
        "options": {
            "documented": "amount_usd = amount_local × rate (as written in the brief)",
            "inverse": "amount_usd = amount_local ÷ rate (the export already applied the rate once)",
        },
        "recommended": "inverse",
    },
    "account_identity": {
        "record": "docs/decisions/PDR-002-account-identity.md",
        "options": {
            "account_id": "one account = one account_id (system key); name is a display attribute",
            "account_name": "one account = one account_name",
        },
        "recommended": "account_id",
        # supported=False → can be recorded, cannot be applied (no mapping exists that makes it coherent)
        "blocked": {"account_name": "Every one of the 200 names spans several regions, plans and signup dates "
                                    "(100% of name groups are inconsistent), so names cannot serve as identity without a "
                                    "master-data mapping from CloudNova. Recordable, not applicable."},
    },
}


def original() -> dict:
    return yaml.safe_load(ORIGINAL_PATH.read_text())


def _override_path() -> Path:
    return get_settings().runtime_dir / "policy_active.json"


def active() -> dict:
    p = _override_path()
    if p.exists():
        return json.loads(p.read_text())
    o = original()
    return {"version": o["version"], "status": o["status"], "rules": o["rules"], "based_on": None, "decision_id": None}


def _db():
    s = get_settings()
    s.runtime_dir.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(s.runtime_dir / "copilot.db")
    con.execute("""CREATE TABLE IF NOT EXISTS policy_decisions (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT, from_value TEXT,
                   to_value TEXT, approver TEXT, role TEXT, rationale TEXT, impact_hash TEXT, status TEXT, at REAL, applied_at REAL,
                   policy_version TEXT)""")
    return con


def decisions() -> list[dict]:
    with closing(_db()) as con:
        cols = [d[1] for d in con.execute("PRAGMA table_info(policy_decisions)")]
        return [dict(zip(cols, r)) for r in con.execute("SELECT * FROM policy_decisions ORDER BY id DESC")]


# ---------------------------------------------------------------- impact (computed from the raw data, not asserted)
def impact(key: str) -> dict:
    from . import db
    q = lambda s: db.connection().execute(s).fetchall()  # noqa: E731
    if key == "fx_direction":
        n, doc_ok, inv_ok = q("""SELECT COUNT(*), COUNT(*) FILTER (WHERE abs(amount_usd - expected_amount_usd) <= 1.00),
            COUNT(*) FILTER (WHERE abs(amount_usd_alt - expected_amount_usd) <= 1.00)
            FROM invoices WHERE currency <> 'USD' AND status <> 'refunded'""")[0]
        cur = active()["rules"]["fx_direction"]
        col = {"documented": "amount_usd" if cur == "documented" else "amount_usd_alt",
               "inverse": "amount_usd_alt" if cur == "documented" else "amount_usd"}
        rows = {}
        for opt, c in col.items():
            q1, allpaid, refunds, exposure = q(f"""SELECT SUM({c}) FILTER (WHERE status='paid' AND invoice_year=2024),
                SUM({c}) FILTER (WHERE status='paid'), SUM({c}) FILTER (WHERE status='refunded'),
                SUM({c}) FILTER (WHERE status IN ('pending','failed')) FROM invoices""")[0]
            rows[opt] = {"q1_paid_2024": round(float(q1), 2), "paid_all_time": round(float(allpaid), 2),
                         "refunds": round(float(refunds), 2), "exposure": round(float(exposure), 2)}
        pb = {"documented": doc_ok if cur == "documented" else inv_ok, "inverse": inv_ok if cur == "documented" else doc_ok}
        rep = {"key": key, "non_usd_invoices_checked": n,
               "price_book_matches": pb,
               "answers": rows,
               "unaffected": ["Q2 avg MRR (list-price based)", "Q4 churn", "Q6 count", "all MRR metrics"],
               "evidence_sql": "abs(amount_usd[_alt] - expected_amount_usd) <= 1.00 over non-USD, non-refund invoices"}
    elif key == "account_identity":
        stats = {}
        for k in ("account_id", "account_name"):
            g, inc = q(f"""WITH x AS (SELECT {k} AS k, COUNT(DISTINCT region) r, COUNT(DISTINCT plan) p, COUNT(DISTINCT churned) c
                          FROM invoices GROUP BY 1) SELECT COUNT(*), AVG(CASE WHEN r>1 OR p>1 OR c>1 THEN 1.0 ELSE 0 END) FROM x""")[0]
            top = [r[0] for r in q(f"""SELECT {k} FROM invoices WHERE status IN ('paid','refunded') GROUP BY 1
                                       ORDER BY SUM(amount_usd) DESC, 1 LIMIT 5""")]
            stats[k] = {"groups": g, "pct_groups_with_conflicting_region_plan_or_churn": round(float(inc) * 100, 1), "top5_by_net_revenue": top}
        rep = {"key": key, "candidates": stats,
               "affected": ["Q2 average MRR per account", "Q4 churn rate", "Q5 top accounts", "account counts"]}
    else:
        raise AppError("unknown_policy", f"Unknown policy key '{key}'.", 404)
    rep["impact_hash"] = hashlib.sha256(json.dumps(rep, sort_keys=True, default=str).encode()).hexdigest()[:16]
    return rep


def overview() -> dict:
    act = active()
    out = []
    for key, meta in DECISION_KEYS.items():
        out.append({"key": key, "current": act["rules"][key], "original": original()["rules"][key], "options": meta["options"],
                    "recommended": meta["recommended"], "blocked": meta.get("blocked", {}), "record": meta["record"],
                    "impact": impact(key)})
    return {"active_policy": act, "original_policy_version": original()["version"], "decisions": decisions(), "proposals": out,
            "approvals_enabled": bool(os.getenv("FINANCE_APPROVER_PIN", "").strip()),
            "note": "Recommendations are not applied until a finance owner approves and a rebuild is run. "
                    "Expected-failure eval cases are left unchanged; a changed policy will show up as eval differences."}


def approve(key: str, option: str, approver: str, role: str, rationale: str, impact_hash: str, pin: str) -> dict:
    expected_pin = os.getenv("FINANCE_APPROVER_PIN", "").strip()
    if not expected_pin:
        raise AppError("approvals_disabled", "Policy approvals are disabled: the operator has not set FINANCE_APPROVER_PIN.", 403)
    if not hmac.compare_digest(pin or "", expected_pin):
        raise AppError("approval_denied", "Approval PIN is incorrect.", 403)
    if role != "finance_owner":
        raise AppError("approval_denied", "Only the finance owner can approve financial-policy changes.", 403)
    if key not in DECISION_KEYS or option not in DECISION_KEYS[key]["options"]:
        raise AppError("invalid_option", f"'{option}' is not an option for '{key}'.", 422)
    if len((approver or "").strip()) < 2 or len((rationale or "").strip()) < 20:
        raise AppError("invalid_decision", "Approver name and a rationale of at least 20 characters are required.", 422)
    if impact_hash != impact(key)["impact_hash"]:
        raise AppError("stale_impact", "The impact report changed since it was shown; review it again before approving.", 409)
    current = active()["rules"][key]
    blocked = DECISION_KEYS[key].get("blocked", {}).get(option)
    status = "confirmed_no_change" if option == current else ("recorded_blocked" if blocked else "approved_pending_rebuild")
    with closing(_db()) as con:
        cur = con.execute("INSERT INTO policy_decisions (key, from_value, to_value, approver, role, rationale, impact_hash, status, at) "
                          "VALUES (?,?,?,?,?,?,?,?,?)", (key, current, option, approver.strip()[:80], role, rationale.strip()[:2000],
                                                          impact_hash, status, time.time()))
        con.commit()
        did = cur.lastrowid
    return {"decision_id": did, "status": status, "blocked_reason": blocked,
            "next": "POST /api/v1/policy/decisions/{id}/apply to rebuild" if status == "approved_pending_rebuild" else None}


def apply(decision_id: int) -> dict:
    from . import db
    from .pipeline.build import build
    with closing(_db()) as con:
        row = con.execute("SELECT key, to_value, status FROM policy_decisions WHERE id=?", (decision_id,)).fetchone()
    if not row:
        raise AppError("not_found", f"No decision {decision_id}.", 404)
    key, value, status = row
    if status != "approved_pending_rebuild":
        raise AppError("not_applicable", f"Decision {decision_id} is '{status}' and cannot be applied.", 409)
    act = active()
    new_rules = {**act["rules"], key: value}
    orig = original()
    is_original = new_rules == orig["rules"]
    ver = orig["version"] if is_original else f"{orig['version'].split('.')[0]}.{int(time.time())}"
    p = _override_path()
    if is_original:
        p.unlink(missing_ok=True)
    else:
        p.write_text(json.dumps({"version": ver, "status": "active-approved", "rules": new_rules, "based_on": orig["version"],
                                 "decision_id": decision_id}, indent=2))
    get_settings.cache_clear()
    db.reset_connections()
    manifest = build(force=True, quiet=True)
    db.reset_connections()
    with closing(_db()) as con:
        con.execute("UPDATE policy_decisions SET status='applied', applied_at=?, policy_version=? WHERE id=?", (time.time(), ver, decision_id))
        con.execute("UPDATE policy_decisions SET status='superseded' WHERE key=? AND status='approved_pending_rebuild' AND id<>?", (key, decision_id))
        con.commit()
    return {"decision_id": decision_id, "applied": {key: value}, "policy_version": ver, "rebuilt": True,
            "fx_direction_in_build": manifest["fx_direction"], "restored_original": is_original}
