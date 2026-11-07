"""Supervisor: route → tools → validated response (specs/agent_contracts.md, query_interface.md).

Routing is deterministic first (so financial answers never depend on the model), local Qwen second.
"""
from __future__ import annotations

import re
import secrets
import time

from .. import db
from ..errors import AppError
from ..governance.guards import MAX_QUESTION_CHARS, instruction_like, write_intent
from ..llm.provider import provider_status
from ..semantic.catalog import METRICS
from ..semantic.planner import CONCEPT, UNMODELED, QueryPlan, apply_followup, describe_filters, detect_metrics, plan_question
from . import memory
from . import tools as T
from .harness import RunContext
from .render import chart_for, render

OUT_OF_SCOPE = [
    (re.compile(r"\bwhy\b.{0,40}\bchurn|reason.{0,30}churn|churn(ed)? because", re.I),
     "The ledger records *whether* an account churned, not *why*: there are no cancellation reasons, support transcripts or "
     "notes. I can show observable correlates (plan, CSAT, support tickets, region) for churned accounts, but any 'reason' "
     "would be speculation."),
    (re.compile(r"forecast|predict|projection|next (year|quarter|month)|will .{0,40}\b(be|grow|look|reach)\b", re.I),
     "Forecasting is out of scope: the data has no subscription start/end history to model future revenue honestly. "
     "I can show the historical monthly trend instead."),
    (re.compile(r"(live|current|today'?s|real.?time).{0,20}(exchange|fx|rate|price|stock)", re.I),
     "I don't have internet access or live rates; CloudNova uses fixed FX (EUR→USD 1.08, GBP→USD 1.27)."),
]
DQ_PAT = re.compile(r"reconcil|5,?125|double.?count|duplicate|data quality|dirty|cleaning|cleaned|ambiguous|date format|conflict|reject|quarantin|malformed|"
                    r"\bfx\b.{0,20}(issue|question|direction|rule)|how (did|do) you (handle|treat|parse|clean)|emails?", re.I)
EXPLAIN_PAT = re.compile(r"^\s*(explain|how (was|is|did you) (that|this|it) (calculated|computed|derived)|show (me )?the (sql|query)|"
                         r"how did you (get|calculate|compute)|where did (that|this) (number|come)|what does .{1,30} mean|"
                         r"how (is|are) .{1,40} (calculated|computed|defined|derived|measured)|"
                         r"how (is|do you) (define|calculate|compute)|definition of|define\b)", re.I)
GREETING = re.compile(r"^\s*(hi|hello|hey|yo|thanks|thank you|good (morning|afternoon|evening)|how are you|who are you|what can you do)\b", re.I)
DATA_WORDS = re.compile(r"invoice|account|customer|client|revenue|region|plan|seat|csat|status|currency|discount|industr|payment|"
                        r"billing|churn|refund|mrr|how many|top \d|which|list|average|total|sum|count|percent|share", re.I)


def new_session() -> str:
    return "s_" + secrets.token_hex(6)


def _base(session_id: str, run_id: str) -> dict:
    return {"schema_version": "1.0", "session_id": session_id, "run_id": run_id, "intent": None, "answer": "", "sql": None,
            "planner": "none", "metric_definitions": [], "filters": {}, "result": None, "chart": None, "caveats": [],
            "sources": [], "trace": [], "llm": {"provider": "qwen", "used": False, "latency_ms": 0.0}, "suggestions": []}


def ask(question: str, session_id: str | None = None) -> dict:
    question = (question or "").strip()
    if not question:
        raise AppError("invalid_question", "Please type a question.", 400)
    if len(question) > MAX_QUESTION_CHARS:
        raise AppError("invalid_question", f"Questions are limited to {MAX_QUESTION_CHARS} characters.", 400)
    session_id = session_id or new_session()
    run_id = "r_" + secrets.token_hex(6)
    ctx = RunContext(run_id, session_id)
    out = _base(session_id, run_id)
    status = "ok"
    try:
        _dispatch(question, ctx, out)
    except AppError as exc:
        status = exc.code
        ctx.note("error", exc.message, status="error", code=exc.code)
        out["trace"] = ctx.trace
        _finish(ctx, out, question, status)
        raise
    out["trace"] = ctx.trace
    _finish(ctx, out, question, status)
    return out


def _finish(ctx: RunContext, out: dict, question: str, status: str) -> None:
    total = (time.perf_counter() - ctx.t0) * 1000
    out["latency_ms"] = round(total, 1)
    sql_ms = sum(t["ms"] for t in ctx.trace if t.get("tool") in ("run_metric_query", "scope_caveats", "data_quality_report"))
    memory.record_run({"run_id": ctx.run_id, "session_id": ctx.session_id, "question": question, "intent": out["intent"] or "error",
                       "planner": out["planner"], "status": status, "total_ms": round(total, 1),
                       "llm_ms": out["llm"]["latency_ms"], "sql_ms": round(sql_ms, 1), "trace": ctx.trace})
    if status == "ok":
        memory.append(ctx.session_id, question, out["intent"], out.get("_plan"), out["answer"], out["sql"])
    out.pop("_plan", None)


def _dispatch(q: str, ctx: RunContext, out: dict) -> None:
    t = time.perf_counter()
    if instruction_like(q):
        ctx.note("guard", "instruction-like text detected; treated as data, not instructions", status="flagged")
    if write_intent(q):
        ctx.note("route", "write/modify request", (time.perf_counter() - t) * 1000)
        out.update(intent="out_of_scope", answer="I can only read CloudNova's data — the analytics database is opened read-only, "
                   "so nothing can be deleted, updated or changed from the chat. Changes to source data go through the finance "
                   "team's billing systems.")
        return
    for pat, msg in OUT_OF_SCOPE:
        if pat.search(q):
            ctx.note("route", "out_of_scope (no evidence in data)", (time.perf_counter() - t) * 1000)
            out.update(intent="out_of_scope", answer=msg,
                       suggestions=["Show churn rate by plan", "Average CSAT for churned vs active accounts", "Monthly revenue trend"])
            return
    prev_plan, prev_sql = memory.last_plan(ctx.session_id)

    if EXPLAIN_PAT.search(q):
        ms = detect_metrics(q)
        if prev_plan and (not ms or re.search(r"\b(that|this|it)\b", q, re.I)):
            p = QueryPlan.from_dict(prev_plan)
            ctx.note("route", "explain previous answer", (time.perf_counter() - t) * 1000)
            defs = T.metric_definitions(p)
            out.update(intent="explain", sql=prev_sql, planner="semantic", metric_definitions=defs, filters=describe_filters(p),
                       answer="Here is how the previous answer was computed:\n" + "\n".join(f"- **{d['label']}** = {d['definition']} "
                              f"SQL: `{d['sql']}`" for d in defs) + f"\n- Filters: {', '.join(f'{k} = {v}' for k, v in describe_filters(p).items()) or 'none'}. "
                              "The full SQL that ran is shown below; it executed read-only on the cleaned `invoices`/`accounts` tables.",
                       sources=["invoices", "accounts"])
            out["_plan"] = prev_plan
            return
        if ms:
            ctx.note("route", "explain metric definition", (time.perf_counter() - t) * 1000)
            defs = [{"id": m, "label": METRICS[m].label, "definition": METRICS[m].definition, "sql": METRICS[m].sql} for m in ms[:2]]
            out.update(intent="explain", metric_definitions=defs,
                       answer="\n".join(f"**{d['label']}** — {d['definition']}\n`{d['sql']}`" for d in defs))
            return

    if DQ_PAT.search(q) and not detect_metrics(q):
        ctx.note("route", "data_quality", (time.perf_counter() - t) * 1000)
        r = ctx.call("data_quality_report", question=q)
        out.update(intent="data_quality", answer=r["text"], sql=r["result"]["sql"], result=_result(r["result"]),
                   sources=r["result"]["tables"], planner="semantic", chart=chart_for(None, r["result"]))
        return

    if CONCEPT.search(q) and not re.search(r"invoices?|accounts?|customers?|clients?|churned|\bactive\b", q, re.I):
        ms = [] if UNMODELED.search(q) else detect_metrics(q)
        if ms:  # a term we define: answer from the approved catalog, not from model memory
            ctx.note("route", "concept question about a catalog metric → explain definition", (time.perf_counter() - t) * 1000)
            defs = [{"id": m, "label": METRICS[m].label, "definition": METRICS[m].definition, "sql": METRICS[m].sql} for m in ms[:2]]
            out.update(intent="explain", metric_definitions=defs,
                       answer="At CloudNova (per the business rules):\n" + "\n".join(f"**{d['label']}** — {d['definition']}\n`{d['sql']}`" for d in defs))
            return
        ctx.note("route", "concept question (no CloudNova scope) → general", (time.perf_counter() - t) * 1000)
        _general(q, ctx, out)
        return

    from ..config import get_settings
    if get_settings().query_mode == "llm" and not GREETING.search(q):  # comparison mode: no semantic layer at all
        if not provider_status()["reachable"]:
            raise AppError("llm_unavailable", "QUERY_MODE=llm needs the local Qwen model, which is not reachable.", 503, retryable=True)
        ctx.note("route", "analytics (QUERY_MODE=llm: Qwen text-to-SQL for every data question)", (time.perf_counter() - t) * 1000)
        _llm_sql(q, ctx, out)
        return

    plan = None
    if prev_plan:
        plan = apply_followup(QueryPlan.from_dict(prev_plan), q)
        if plan:
            ctx.note("route", "analytics (follow-up patches previous plan)", (time.perf_counter() - t) * 1000)
    if plan is None and not GREETING.search(q):
        plan = plan_question(q)
        if plan:
            ctx.note("route", f"analytics (semantic plan, confidence {plan.confidence})", (time.perf_counter() - t) * 1000)
    if plan is not None and plan.confidence >= 0.6:
        _analytics(plan, q, ctx, out)
        return

    llm = provider_status()
    if GREETING.search(q) or not DATA_WORDS.search(q):
        ctx.note("route", "general conversation", (time.perf_counter() - t) * 1000)
        _general(q, ctx, out)
        return

    if not llm["reachable"]:
        ctx.note("route", "clarify (no semantic plan, Qwen offline)", (time.perf_counter() - t) * 1000)
        out.update(intent="clarify", answer="I couldn't map that to an approved metric, and the local Qwen model (used for "
                   "free-form SQL) is offline. Try naming a metric and a breakdown, e.g. 'net revenue by industry in 2025'.",
                   suggestions=["Net revenue by industry", "Churn rate by region", "Refunds by month in 2024"])
        return
    ctx.note("route", "analytics (Qwen text-to-SQL; semantic planner had no confident plan)", (time.perf_counter() - t) * 1000)
    _llm_sql(q, ctx, out)


def _llm_sql(q: str, ctx: RunContext, out: dict) -> None:
    res = ctx.call("run_llm_sql", question=q)
    llm_ms = res["llm_ms"]
    answer = None
    if res["rows"]:
        try:
            n = ctx.call("narrate", question=q, columns=res["columns"], rows=res["rows"])
            llm_ms += n["llm_ms"]
            answer = n["text"]
        except AppError:
            answer = None
    if not answer:
        answer = _table_text(res)
    out.update(intent="analytics", planner="llm_sql", sql=res["sql"], result=_result(res), sources=res["tables"],
               answer=answer, chart=chart_for(None, res),
               llm={"provider": "qwen", "model": res["model"], "used": True, "latency_ms": round(llm_ms, 1)},
               caveats=["SQL written by the local Qwen model (not an approved metric). It passed the read-only SQL guard; "
                        "check the query before relying on it."])


def _general(q: str, ctx: RunContext, out: dict) -> None:
    if not provider_status()["reachable"]:
        raise AppError("llm_unavailable", "General conversation needs the local Qwen model, which is not reachable. "
                       "Data questions (e.g. 'paid revenue in 2024') still work without it.", 503, retryable=True)
    r = ctx.call("general_chat", question=q, history=memory.history(ctx.session_id))
    out.update(intent="general", answer=r["text"], llm={"provider": "qwen", "model": r["model"], "used": True,
                                                          "latency_ms": r["llm_ms"]})
    out["caveats"] = ["General-knowledge answer from the local model — not computed from CloudNova data."]


def _analytics(plan: QueryPlan, q: str, ctx: RunContext, out: dict) -> None:
    res = ctx.call("run_metric_query", plan=plan.to_dict())
    cav = ctx.call("scope_caveats", plan=plan.to_dict())
    out.update(intent="analytics", planner="semantic", sql=res["sql"], result=_result(res), sources=res["tables"],
               metric_definitions=T.metric_definitions(plan), filters=describe_filters(plan),
               answer=render(plan, res, cav["context"]), caveats=cav["caveats"], chart=chart_for(plan, res))
    out["_plan"] = plan.to_dict()
    out["suggestions"] = _suggest(plan)


def _suggest(plan: QueryPlan) -> list[str]:
    s = []
    if plan.group_by != "plan":
        s.append("Now by plan")
    if "plan" not in plan.filters:
        s.append("Only Enterprise")
    s.append("Turn it into a chart" if plan.group_by else "Break it down by region")
    s.append("Explain the calculation")
    return s[:4]


def _result(res: dict) -> dict:
    return {k: res[k] for k in ("columns", "rows", "row_count", "truncated")}


def _table_text(res: dict) -> str:
    if not res["rows"]:
        return "The query ran but returned no rows."
    head = " | ".join(res["columns"])
    lines = [" | ".join(f"{v:,.2f}" if isinstance(v, float) else str(v) for v in r) for r in res["rows"][:10]]
    return f"Result ({res['row_count']} row(s)):\n{head}\n" + "\n".join(lines)


def health() -> dict:
    try:
        n = db.run_query("SELECT COUNT(*) FROM invoices")["rows"][0][0]
        data = {"ok": True, "invoices": n}
    except AppError as exc:
        data = {"ok": False, "error": exc.code}
    return {"status": "ok" if data["ok"] else "degraded", "data": data, "llm": provider_status()}
