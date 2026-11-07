"""Logical agents as harness tools (specs/agent_contracts.md)."""
from __future__ import annotations

import re

from .. import db
from ..errors import AppError
from ..governance.guards import ungrounded_numbers
from ..llm.provider import get_provider
from ..semantic.catalog import METRICS, SCHEMA_DOC
from ..semantic.planner import QueryPlan, compile_sql
from .harness import tool


# ---------------------------------------------------------------- financial analytics (deterministic)
@tool("run_metric_query", "Compile an approved-metric QueryPlan to SQL and run it read-only.", agent="financial_analytics")
def run_metric_query(plan: dict) -> dict:
    p = QueryPlan.from_dict(plan)
    sql = compile_sql(p)
    res = db.run_query(sql)
    res["_trace"] = f"semantic plan → {len(res['rows'])} rows in {res['ms']} ms"
    return res


@tool("scope_caveats", "Data-quality facts for the rows a plan touches (dedup conflicts, ambiguous dates, FX).",
      agent="data_quality")
def scope_caveats(plan: dict) -> dict:
    p = QueryPlan.from_dict(plan)
    out: list[str] = []
    ctx: dict = {}
    if p.grain == "invoice":
        base = compile_sql(QueryPlan(metrics=["invoice_count"], filters=p.filters))
        where = base.split("WHERE", 1)[1] if "WHERE" in base else "TRUE"
        frm = base.split("FROM", 1)[1].split("WHERE")[0]
        r = db.run_query(f"SELECT COUNT(*) FILTER (WHERE i.dq_flags LIKE '%dedup_conflict%') AS conflicts, "
                         f"SUM(ABS(i.amount_usd)) FILTER (WHERE i.dq_flags LIKE '%dedup_conflict%') AS at_stake, "
                         f"COUNT(*) FILTER (WHERE i.date_was_ambiguous) AS ambiguous_dates, "
                         f"COUNT(*) FILTER (WHERE i.currency <> 'USD' AND i.status IN ('paid','refunded')) AS non_usd, "
                         f"SUM(i.amount_usd) FILTER (WHERE i.status = 'paid') AS paid_doc, "
                         f"SUM(i.amount_usd_alt) FILTER (WHERE i.status = 'paid') AS paid_alt, "
                         f"COUNT(*) FILTER (WHERE i.invoice_date > current_date) AS future_dated "
                         f"FROM {frm} WHERE {where}")["rows"][0]
        conflicts, at_stake, amb, non_usd, paid_doc, paid_alt, future = r
        if conflicts:
            out.append(f"{conflicts} invoice(s) in scope came from conflicting duplicate records resolved by status precedence "
                       f"(refunded > paid > failed > void > pending); ${at_stake:,.2f} depends on that rule.")
        if amb and ("invoice_year" in p.filters or p.group_by in ("invoice_month", "invoice_year")):
            out.append(f"{amb} invoice date(s) in scope were ambiguous DD-MM-YYYY values, parsed day-first per the evidence rule.")
        if future:
            out.append(f"{future} invoice(s) in scope are dated after today; they are included as issued.")
        if non_usd and p.primary in ("paid_revenue", "net_revenue", "avg_invoice_value") and paid_doc is not None:
            out.append(f"FX: {non_usd} non-USD invoices converted with the documented rule (amount × 1.08 EUR / × 1.27 GBP). "
                       f"Open question: the EUR/GBP amounts already look like USD × rate; under the inverse rule paid revenue "
                       f"here would be ${paid_alt:,.2f} instead of ${paid_doc:,.2f}.")
        if p.primary in ("exposure", "exposure_count") and not p.group_by:
            by = db.run_query(compile_sql(QueryPlan(metrics=["exposure_count", "exposure"], group_by="status",
                                                    filters={**p.filters, "status": p.filters.get("status", ["pending", "failed"])})))
            ctx["by_status"] = [[r[0], r[1], r[2]] for r in by["rows"]]
    else:
        r = db.run_query("SELECT COUNT(*) FILTER (WHERE attr_conflicts > 0), COUNT(*) FILTER (WHERE churned IS NULL) FROM accounts")["rows"][0]
        out.append(f"Account metrics use each account's latest invoice as its current state; {r[0]:,} of 3,815 accounts "
                   f"have attributes (plan/region/churn/CSAT) that differ across invoices.")
        if p.primary in ("avg_mrr", "total_mrr"):
            out.append("MRR = list price × seats × (1 − discount); annual invoices map to the same MRR (not amount ÷ 12). "
                       "Only active (not churned) accounts are included.")
        if p.primary in ("churn_rate", "churned_accounts"):
            out.append("Churn is a snapshot flag with no churn date, so this is a share of accounts, not a period churn rate.")
    out += p.notes
    return {"caveats": out, "context": ctx, "_trace": f"{len(out)} caveat(s)"}


# ---------------------------------------------------------------- data quality
DQ_TOPICS = {
    "duplicates": r"dup|conflict|disagree",
    "dates": r"date|ambiguous|format",
    "fx": r"fx|currenc|exchange",
    "emails": r"email",
    "rejected": r"reject|quarantin|drop|remov",
}


@tool("data_quality_report", "Summarise cleaning decisions and audit tables.", agent="data_quality")
def data_quality_report(question: str) -> dict:
    q = question.lower()
    topic = next((t for t, pat in DQ_TOPICS.items() if re.search(pat, q)), "overview")
    if topic == "duplicates":
        sql = ("SELECT invoice_id, raw_statuses, winner_status, usd_at_stake FROM dedup_conflicts ORDER BY usd_at_stake DESC")
        res = db.run_query(sql)
        n = len(res["rows"])
        total = sum(r[3] for r in res["rows"])
        text = (f"82 exact-duplicate rows and 27 synonym duplicates (same invoice, status spelled differently) were collapsed. "
                f"**{n}** invoice_ids had genuinely conflicting statuses across source systems; the winner was chosen by "
                f"precedence refunded > paid > failed > void > pending (evidence of money movement beats a stale state). "
                f"**${total:,.2f}** of invoice value depends on that rule; every losing record is kept in `rejected_rows`.")
    elif topic == "dates":
        sql = ("SELECT issue_code, n_rows, action FROM dq_issues WHERE issue_code IN "
               "('ambiguous_invoice_date','ambiguous_signup_date','future_invoice_date','invoice_before_signup')")
        res = db.run_query(sql)
        text = ("Dates came in five formats. `NN/NN/YYYY` is read as MM/DD (the first part is never > 12 in 1,320 rows; the "
                "second part is > 12 in 786). `NN-NN-YYYY` is read as DD-MM (first part > 12 in 151 rows, second never). "
                "Rows where both readings are valid are flagged `date_was_ambiguous`.")
    elif topic == "fx":
        sql = ("SELECT currency, COUNT(*) AS invoices, SUM(amount_local) AS amount_local, SUM(amount_usd) AS usd_documented, "
               "SUM(amount_usd_alt) AS usd_inverse FROM invoices WHERE status = 'paid' GROUP BY currency ORDER BY currency")
        res = db.run_query(sql)
        text = ("FX uses the fixed rates from the business context (EUR→USD 1.08, GBP→USD 1.27; no live rates). Open question for "
                "finance: every EUR/GBP amount equals the USD list price × the rate, which suggests amounts were already "
                "converted once. The table shows paid revenue under the documented rule and under the inverse rule.")
    elif topic == "emails":
        sql = "SELECT issue_code, n_rows, action FROM dq_issues WHERE issue_code LIKE 'email%'"
        res = db.run_query(sql)
        text = "Emails with `_at_` were repaired to `@`; blank emails stay NULL. Emails are masked in query results."
    elif topic == "rejected":
        sql = "SELECT replace(issue_code, 'rejected:', '') AS reason, n_rows AS rows_moved FROM dq_issues WHERE issue_code LIKE 'rejected:%' ORDER BY n_rows DESC"
        res = db.run_query(sql)
        parts = ", ".join(f"{r[1]:,} {r[0].replace('_', ' ')}" for r in res["rows"])
        text = (f"{sum(r[1] for r in res['rows']):,} raw rows were moved to `rejected_rows` ({parts}). No raw row is silently "
                f"dropped: every row is either in `invoices` or in `rejected_rows` with its reason and full raw record.")
    else:
        sql = "SELECT issue_code, \"column\", n_rows, action FROM dq_issues ORDER BY n_rows DESC"
        res = db.run_query(sql)
        text = ("5,125 raw rows → 5,000 clean invoices + 125 rows in `rejected_rows` (82 exact duplicates, 27 synonym "
                "duplicates, 16 lost status conflicts). Categories normalised by explicit lookup maps; nulls are never imputed.")
    res["_trace"] = f"data quality topic={topic}"
    return {"text": text, "result": res, "topic": topic, "_trace": f"data quality topic={topic}"}


# ---------------------------------------------------------------- LLM tools (local Qwen)
SQL_SYSTEM = f"""You translate questions about CloudNova's invoice data into ONE DuckDB SQL SELECT statement.
Schema:
{SCHEMA_DOC}
Business rules (must follow):
- Revenue uses amount_usd (already USD). Paid revenue: status = 'paid'. Net revenue: status IN ('paid','refunded').
- Refunds: status = 'refunded' (amounts are negative). Exposure: status IN ('pending','failed').
- MRR per account: accounts.current_mrr_usd for accounts where is_active. Never derive MRR from amount.
- Use invoice_year for years. Use accounts for account-level questions.
Return only the SQL in a ```sql block. No explanations. Read-only: never modify data.
Examples:
Q: paid revenue by currency in 2023
```sql
SELECT currency, SUM(amount_usd) AS paid_revenue FROM invoices WHERE status = 'paid' AND invoice_year = 2023 GROUP BY currency ORDER BY paid_revenue DESC
```
Q: which industry has the most churned accounts
```sql
SELECT industry, COUNT(*) AS churned_accounts FROM accounts WHERE churned GROUP BY industry ORDER BY churned_accounts DESC
```
Q: average seats per invoice for annual billing
```sql
SELECT AVG(seats) AS avg_seats FROM invoices WHERE billing_cycle = 'annual'
```"""

_SQL_BLOCK = re.compile(r"```(?:sql)?\s*(.+?)```", re.S | re.I)


def _extract_sql(text: str) -> str:
    m = _SQL_BLOCK.search(text)
    sql = (m.group(1) if m else text).strip()
    return sql.split(";")[0].strip() if sql.count(";") <= 1 else sql


@tool("run_llm_sql", "Ask local Qwen to write SQL for a question the semantic layer cannot express; run it through the guard.",
      agent="financial_analytics", timeout_s=240)
def run_llm_sql(question: str) -> dict:
    provider = get_provider()
    if provider is None:
        raise AppError("llm_unavailable", "No local model is configured.", 503)
    msgs = [{"role": "user", "content": f"<question>\n{question}\n</question>"}]
    llm_ms, attempts, last_err = 0.0, [], None
    for _ in range(2):  # one controlled retry with the error fed back
        resp = provider.complete(SQL_SYSTEM, msgs, max_tokens=300)
        llm_ms += resp.latency_ms
        sql = _extract_sql(resp.text)
        try:
            res = db.run_query(sql)
            res.update(llm_ms=llm_ms, attempts=attempts + [{"sql": sql, "status": "ok"}], model=resp.model,
                       _trace=f"Qwen SQL ok after {len(attempts) + 1} attempt(s), {round(llm_ms)} ms")
            return res
        except AppError as exc:
            last_err = exc
            attempts.append({"sql": sql, "status": exc.code, "message": exc.message})
            msgs += [{"role": "assistant", "content": resp.text},
                     {"role": "user", "content": f"That query failed: {exc.message} Return a corrected single SELECT."}]
    assert last_err is not None
    last_err.details["attempts"] = attempts
    raise last_err


@tool("narrate", "Ask Qwen for a 1–2 sentence summary of result rows; reject it if it contains ungrounded numbers.",
      agent="governance", timeout_s=180)
def narrate(question: str, columns: list, rows: list) -> dict:
    provider = get_provider()
    table = "\n".join([" | ".join(map(str, columns))] + [" | ".join(map(str, r)) for r in rows[:15]])
    resp = provider.complete("Summarise the query result for a finance stakeholder in at most 2 sentences. Use only numbers "
                             "that appear in the table, formatted with thousands separators. Do not speculate.",
                             [{"role": "user", "content": f"Question: {question}\nResult:\n{table}"}], max_tokens=120)
    bad = ungrounded_numbers(resp.text, rows)
    return {"text": None if bad else resp.text, "rejected_numbers": sorted(bad), "llm_ms": resp.latency_ms,
            "_trace": ("narrative rejected: ungrounded " + ", ".join(map(str, sorted(bad)[:5]))) if bad else "narrative grounded"}


GENERAL_SYSTEM = ("You are CloudNova Copilot, a concise assistant for a SaaS finance team. You can chat, explain SaaS and finance "
                  "concepts, and brainstorm. You do NOT have internet access or live data. Never state CloudNova-specific numbers "
                  "in this mode: if the user asks about CloudNova's figures, tell them to ask a data question (e.g. 'paid revenue in "
                  "2024') which is answered from the database. Keep answers under 120 words.")


@tool("general_chat", "General conversation and concepts via local Qwen (no CloudNova numbers).", agent="general_knowledge", timeout_s=180)
def general_chat(question: str, history: list[dict]) -> dict:
    provider = get_provider()
    if provider is None:
        raise AppError("llm_unavailable", "No local model is configured for general conversation.", 503)
    msgs = []
    for t in history[-4:]:
        msgs += [{"role": "user", "content": t["question"]}, {"role": "assistant", "content": (t["answer"] or "")[:600]}]
    msgs.append({"role": "user", "content": question})
    resp = provider.complete(GENERAL_SYSTEM, msgs, max_tokens=220, temperature=0.3)
    return {"text": resp.text, "llm_ms": resp.latency_ms, "model": resp.model, "_trace": f"Qwen chat {round(resp.latency_ms)} ms"}


def metric_definitions(plan: QueryPlan) -> list[dict]:
    return [{"id": m, "label": METRICS[m].label, "definition": METRICS[m].definition, "sql": METRICS[m].sql} for m in plan.metrics]
