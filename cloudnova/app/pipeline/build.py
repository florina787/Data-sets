"""Build data/processed/cloudnova.duckdb from the raw CSV (typed tables + metric views + manifest)."""
from __future__ import annotations

import hashlib
import json
import time
from datetime import date, datetime, timezone
from pathlib import Path

import duckdb

from ..config import get_settings
from .clean import clean, load_raw

INVOICE_TYPES = {
    "invoice_id": "VARCHAR", "account_id": "VARCHAR", "account_name": "VARCHAR", "contact_email": "VARCHAR",
    "email_was_repaired": "BOOLEAN", "region": "VARCHAR", "industry": "VARCHAR", "plan": "VARCHAR",
    "billing_cycle": "VARCHAR", "billed_months": "INTEGER", "seats": "INTEGER", "currency": "VARCHAR",
    "amount_local": "DECIMAL(14,2)", "fx_rate_to_usd": "DECIMAL(6,4)", "amount_usd": "DECIMAL(14,2)",
    "amount_usd_alt": "DECIMAL(14,2)", "discount_pct": "DECIMAL(5,2)", "list_price_usd": "DECIMAL(8,2)",
    "mrr_usd": "DECIMAL(14,2)", "expected_amount_usd": "DECIMAL(14,2)", "status_raw": "VARCHAR", "status": "VARCHAR",
    "is_revenue": "BOOLEAN", "payment_method": "VARCHAR", "signup_date": "DATE", "invoice_date": "DATE",
    "invoice_year": "INTEGER", "invoice_month": "VARCHAR", "date_was_ambiguous": "BOOLEAN", "churned": "BOOLEAN",
    "csat_score": "INTEGER", "support_tickets": "INTEGER", "dedup_rule": "VARCHAR", "dq_flags": "VARCHAR",
    "raw_row_number": "INTEGER",
}
ACCOUNT_TYPES = {
    "account_id": "VARCHAR", "account_name": "VARCHAR", "region": "VARCHAR", "industry": "VARCHAR", "plan": "VARCHAR",
    "seats": "INTEGER", "discount_pct": "DECIMAL(5,2)", "churned": "BOOLEAN", "csat_score": "INTEGER",
    "current_mrr_usd": "DECIMAL(14,2)", "is_active": "BOOLEAN", "first_invoice_date": "DATE",
    "last_invoice_date": "DATE", "invoice_count": "INTEGER", "paid_revenue_usd": "DECIMAL(14,2)",
    "refunds_usd": "DECIMAL(14,2)", "net_revenue_usd": "DECIMAL(14,2)", "attr_conflicts": "INTEGER",
}

VIEWS = """
CREATE OR REPLACE VIEW monthly_revenue AS
SELECT invoice_month,
       SUM(amount_usd) FILTER (WHERE status = 'paid')                   AS paid_revenue_usd,
       SUM(amount_usd) FILTER (WHERE status = 'refunded')               AS refunds_usd,
       SUM(amount_usd) FILTER (WHERE status IN ('paid','refunded'))     AS net_revenue_usd,
       SUM(amount_usd) FILTER (WHERE status IN ('pending','failed'))    AS exposure_usd,
       COUNT(*)                                                         AS invoice_count
FROM invoices GROUP BY invoice_month ORDER BY invoice_month;
"""


def _typed_insert(con: duckdb.DuckDBPyConnection, name: str, df, types: dict) -> None:
    con.register("_df", df[list(types)].astype(object).where(df[list(types)].notna(), None))
    cols = ", ".join(f"CAST({c} AS {t}) AS {c}" for c, t in types.items())
    con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT {cols} FROM _df")
    con.unregister("_df")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(force: bool = False, quiet: bool = False) -> dict:
    s = get_settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = s.data_dir / "manifest.json"
    digest = sha256(s.raw_csv)
    if not force and s.db_path.exists() and manifest_path.exists():
        m = json.loads(manifest_path.read_text())
        if m.get("raw_sha256") == digest and m.get("fx_direction") == s.fx_direction:
            return {**m, "reused": True}
    t0 = time.perf_counter()
    result = clean(load_raw(s.raw_csv), s.fx_to_usd, s.fx_direction, today=date.today())
    tmp = s.db_path.with_suffix(".tmp.duckdb")
    tmp.unlink(missing_ok=True)
    con = duckdb.connect(str(tmp))
    try:
        _typed_insert(con, "invoices", result.invoices, INVOICE_TYPES)
        _typed_insert(con, "accounts", result.accounts, ACCOUNT_TYPES)
        for name, df in (("rejected_rows", result.rejected_rows), ("dedup_conflicts", result.dedup_conflicts),
                         ("dq_issues", result.dq_issues)):
            con.register("_df", df)
            con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM _df")
            con.unregister("_df")
        con.execute("ALTER TABLE invoices ADD PRIMARY KEY (invoice_id)")
        con.execute("ALTER TABLE accounts ADD PRIMARY KEY (account_id)")
        con.execute(VIEWS)
        for name in ("invoices", "accounts"):
            con.execute(f"COPY {name} TO '{s.data_dir / (name + '.parquet')}' (FORMAT parquet)")
    finally:
        con.close()
    tmp.replace(s.db_path)
    from ..policy import active as _active_policy
    pol = _active_policy()
    manifest = {
        "policy_version": pol["version"], "policy_decision_id": pol.get("decision_id"),
        "raw_csv": str(s.raw_csv.name), "raw_sha256": digest, "fx_direction": s.fx_direction,
        "fx_to_usd": s.fx_to_usd, "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "build_seconds": round(time.perf_counter() - t0, 2), **result.stats,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2))
    if not quiet:
        print(f"built {s.db_path.name}: {result.stats['clean_invoices']} invoices, {result.stats['accounts']} accounts, "
              f"{result.stats['rejected_rows']} rejected rows ({manifest['build_seconds']}s)")
    return {**manifest, "reused": False}
