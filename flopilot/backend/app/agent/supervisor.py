"""Supervisor: classifies a request, executes a bounded plan through the harness, composes the
answer and drives the run state machine. Runs execute on a background worker thread."""
from __future__ import annotations

import concurrent.futures
import logging
from typing import Any

from .. import audit, db
from ..auth import Principal
from ..common import AppError, new_id, now_iso
from ..harness import tools as _tools  # noqa: F401  (registers tools)
from ..harness.runtime import BudgetExceeded, Cancelled, RunContext
from ..harness.state import RunState, load_run, transition
from ..llm.providers import get_provider, provider_status
from ..services import workbooks as W
from ..workbook.profile import compact_schema
from . import context as C
from .narrate import narrate
from .planner import Plan, Planner

log = logging.getLogger("flopilot.supervisor")
_runs = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="flopilot-run")

HELP_TEXT = ("I can analyse, clean and add formulas to this workbook. Try:\n"
             "- “Summarize net revenue by region”\n- “Show missing values by column”\n- “Find potential duplicate invoices”\n"
             "- “Compare actual spending with budget”\n- “Add a profit-margin column”\n- “Create a net revenue trend chart”")


def start_run(principal: Principal, workbook_id: str, message: str, conversation_id: str | None,
              selection: dict | None, background: bool = True) -> dict:
    principal.require("read")
    message = (message or "").strip()
    if not message:
        raise AppError("empty_message", "Type a question or request first.")
    if len(message) > 2000:
        raise AppError("message_too_long", "Requests are limited to 2,000 characters.")
    row = W.get_workbook_row(principal, workbook_id)
    conv = C.get_or_create_conversation(principal, workbook_id, conversation_id, message)
    if selection is not None:
        conv["context"]["selection"] = {k: str(v)[:64] for k, v in selection.items() if k in ("sheet", "cell", "range")}
        C.save_context(conv["id"], conv["context"])
    run_id, correlation_id, ts = new_id("run"), new_id("cor"), now_iso()
    status = provider_status()
    db.execute(
        "INSERT INTO runs(id,correlation_id,workbook_id,workbook_version,conversation_id,user_id,workspace_id,state,steps,model,"
        "prompt_version,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (run_id, correlation_id, workbook_id, row["current_version"], conv["id"], principal.user_id, principal.workspace_id,
         RunState.RECEIVED.value, db.dumps([{"type": "state", "state": "RECEIVED", "at": ts, "note": "Received your request…"}]),
         status["model"] or "deterministic-demo", "planner-v1", ts, ts))
    C.add_message(conv["id"], "user", {"text": message, "selection": conv["context"].get("selection")}, run_id)
    audit.record("run_started", run_id=run_id, correlation_id=correlation_id, user_id=principal.user_id,
                 workspace_id=principal.workspace_id, workbook_id=workbook_id, workbook_version=row["current_version"],
                 message=message, mode=status["mode"])
    ctx = RunContext(run_id, correlation_id, principal, workbook_id, row["current_version"], conv["id"], conv["context"])
    if background:
        _runs.submit(_execute, ctx, message)
    else:
        _execute(ctx, message)
    return {"run_id": run_id, "conversation_id": conv["id"], "correlation_id": correlation_id}


def _execute(ctx: RunContext, message: str) -> None:
    try:
        result = handle(ctx, message)
        C.add_message(ctx.conversation_id, "assistant", result, ctx.run_id)
    except Cancelled:
        _finish_safely(ctx, RunState.CANCELLED, "Cancelled by you. Nothing was changed.", {"type": "cancelled", "text": "Cancelled. Nothing was changed."})
    except (BudgetExceeded, AppError) as exc:
        _finish_safely(ctx, RunState.FAILED, exc.message, {"type": "error", "text": exc.message, "code": exc.code, "retryable": exc.retryable})
    except Exception:  # never leak internals to the user
        log.exception("run %s failed", ctx.run_id)
        _finish_safely(ctx, RunState.FAILED, "Something went wrong while handling this request.",
                       {"type": "error", "text": "Something went wrong while handling this request. Please try again.", "code": "internal_error", "retryable": True})
    finally:
        C.save_context(ctx.conversation_id, ctx.context)


def _finish_safely(ctx: RunContext, state: RunState, error: str, result: dict) -> None:
    run = load_run(ctx.run_id)
    if RunState(run["state"]) in (RunState.COMPLETED, RunState.FAILED, RunState.CANCELLED, RunState.ROLLED_BACK):
        return
    result = {**result, "schema_version": "1.0", "run_id": ctx.run_id}
    try:
        transition(ctx.run_id, state, error=error, result=result)
    except AppError:
        db.execute("UPDATE runs SET state = ?, error = ?, result = ?, updated_at = ? WHERE id = ?",
                   (state.value, error, db.dumps(result), now_iso(), ctx.run_id))
    C.add_message(ctx.conversation_id, "assistant", result, ctx.run_id)


def handle(ctx: RunContext, message: str) -> dict:
    ctx.to(RunState.INSPECTING)
    model = W.get_model(ctx.principal, ctx.workbook_id, ctx.version)
    notes = C.refresh_for_version(ctx.context, model)
    ctx.call("inspect_workbook", {})
    ctx.to(RunState.PLANNING)
    planner = Planner(model, ctx.context)
    plan = planner.plan(message)

    if plan is not None and plan.intent == "resolve_clarification":
        rule = plan.steps[0]["args"]
        ctx.context["business_rules"] = [r for r in ctx.context.get("business_rules", []) if r["term"] != rule["term"]] + [
            {**rule, "confirmed_at": now_iso()}]
        ctx.context["pending_clarification"] = None
        ctx.step("business_rule_confirmed", term=rule["term"], column=rule["column"], sheet=rule["sheet"])
        confirmed = plan.assumptions
        message = plan.message or message
        plan = planner.plan(message)
        if plan is not None:
            plan.assumptions = confirmed + plan.assumptions

    if plan is not None and plan.intent == "set_business_rule":
        rule = plan.steps[0]["args"]
        ctx.context["business_rules"] = [r for r in ctx.context.get("business_rules", []) if r["term"] != rule["term"]] + [
            {**rule, "confirmed_at": now_iso()}]
        ctx.step("business_rule_confirmed", term=rule["term"], column=rule["column"], sheet=rule["sheet"])
        return _complete(ctx, {"type": "info", "text": plan.message, "intent": plan.intent, "notes": notes}, plan)

    if plan is None:
        provider = get_provider()
        if provider is not None:
            return _llm_path(ctx, provider, message, compact_schema(W.get_profile(ctx.principal, ctx.workbook_id, ctx.version)), notes)
        return _complete(ctx, {"type": "info", "text": HELP_TEXT, "intent": "help", "notes": notes,
                               "engine": "deterministic-demo"}, Plan("help", "supervisor"))

    db.execute("UPDATE runs SET intent = ?, plan = ? WHERE id = ?", (plan.intent, db.dumps(plan.to_dict()), ctx.run_id))
    ctx.step("plan", intent=plan.intent, role=plan.role, steps=[s["tool"] for s in plan.steps])

    if plan.clarification:
        ctx.context["pending_clarification"] = {k: plan.clarification.get(k) for k in ("term", "sheet", "original")}
        return _complete(ctx, {"type": "clarification", "text": plan.clarification["question"],
                               "clarification": plan.clarification, "intent": plan.intent, "notes": notes}, plan)
    if plan.message and not plan.steps:
        return _complete(ctx, {"type": "info", "text": plan.message, "intent": plan.intent, "notes": notes}, plan)

    ctx.to(RunState.EXECUTING_READS)
    results: list[dict] = []
    operations: list[dict] = []
    chart = None
    infos: list[str] = []
    follow_ups = list(plan.follow_ups)
    for step in plan.steps:
        ctx.check_cancel(force=True)
        tool, args = step["tool"], dict(step.get("args") or {})
        if tool == "_clean_sheet":
            ops_, info = _clean_sheet(ctx, args["sheet"])
            operations += ops_
            infos += info
            continue
        if "from_step" in step:
            if not results:
                continue
            args["result"] = results[step["from_step"]]
        try:
            out = ctx.call(tool, args)
        except AppError as exc:
            handled = _handled_error(ctx, exc, plan, step)
            if handled is None:
                raise
            if handled.get("type") == "clarification":
                return _complete(ctx, {**handled, "intent": plan.intent, "notes": notes}, plan)
            infos.append(handled["text"])
            follow_ups += handled.get("follow_ups", [])
            continue
        if out.get("kind") == "proposal":
            operations.append(out["operation"])
        elif out.get("kind") == "chart":
            chart = out
        else:
            results.append(out)

    primary = results[0] if results else None
    if primary is not None and primary.get("kind") in ("aggregate", "time_series", "variance", "period_change", "missing",
                                                       "histogram", "correlation", "outliers", "duplicates"):
        ctx.context["last_result"] = C.compact_result(primary)
    answer: dict[str, Any] = {
        "type": "proposal" if operations else "answer",
        "intent": plan.intent, "role": plan.role,
        "text": "\n\n".join(filter(None, [narrate(r) for r in results] + infos)),
        "results": results, "chart": chart, "operations": operations,
        "sources": _dedupe([s for r in results for s in r.get("sources", [])]),
        "assumptions": plan.assumptions + _assumption_notes(results),
        "warnings": [w for r in results for w in r.get("warnings", [])],
        "method": next((r.get("method") for r in results if r.get("method")), None),
        "missing_treatment": next((r.get("missing_treatment") for r in results if r.get("missing_treatment")), None),
        "filters": next((r.get("filters") for r in results if r.get("filters")), []),
        "follow_ups": follow_ups, "notes": notes, "engine": "deterministic-demo" if get_provider() is None else "deterministic-planner",
        "grounding": {"checked": True, "ungrounded": [], "note": "All numbers were produced by FloPilot's calculation tools."},
    }
    if operations:
        n = len(operations)
        lead = (f"I prepared {n} change{'s' if n > 1 else ''} for your review. **Nothing has been changed yet** — "
                "check the preview and approve or reject each one.")
        answer["text"] = "\n\n".join(filter(None, [lead, answer["text"]]))
        ctx.context.setdefault("recent_operations", [])
        ctx.context["recent_operations"] = (ctx.context["recent_operations"] + [o["id"] for o in operations])[-20:]
        return _await_approval(ctx, answer)
    if not answer["text"]:
        answer["text"] = "I couldn't produce a result for that request."
    return _complete(ctx, answer, plan)


def run_tool_directly(principal: Principal, workbook_id: str, tool: str, args: dict, label: str,
                      conversation_id: str | None = None) -> dict:
    """Run one proposal tool through the harness for a UI action (e.g. "Prepare again", "Restore v2")."""
    principal.require("propose")
    row = W.get_workbook_row(principal, workbook_id)
    conv = C.get_or_create_conversation(principal, workbook_id, conversation_id, label)
    run_id, correlation_id, ts = new_id("run"), new_id("cor"), now_iso()
    db.execute(
        "INSERT INTO runs(id,correlation_id,workbook_id,workbook_version,conversation_id,user_id,workspace_id,state,steps,model,"
        "prompt_version,intent,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (run_id, correlation_id, workbook_id, row["current_version"], conv["id"], principal.user_id, principal.workspace_id,
         RunState.RECEIVED.value, db.dumps([{"type": "state", "state": "RECEIVED", "at": ts, "note": label}]),
         "none", "direct-action-v1", tool, ts, ts))
    C.add_message(conv["id"], "user", {"text": label, "action": tool}, run_id)
    ctx = RunContext(run_id, correlation_id, principal, workbook_id, row["current_version"], conv["id"], conv["context"])
    try:
        ctx.to(RunState.INSPECTING)
        ctx.to(RunState.PLANNING)
        ctx.step("plan", intent=tool, role="supervisor", steps=[tool])
        ctx.to(RunState.EXECUTING_READS)
        out = ctx.call(tool, args)
    except AppError as exc:
        _finish_safely(ctx, RunState.FAILED, exc.message, {"type": "error", "text": exc.message, "code": exc.code})
        raise
    op = out["operation"]
    answer = {"type": "proposal", "intent": tool, "role": "supervisor", "operations": [op], "results": [], "sources": [],
              "text": f"I prepared “{op['title']}” for your review. **Nothing has been changed yet.**",
              "engine": "direct-action", "assumptions": [], "warnings": [], "follow_ups": []}
    answer = _await_approval(ctx, answer)
    C.add_message(conv["id"], "assistant", answer, run_id)
    return answer | {"conversation_id": conv["id"]}


def _llm_path(ctx: RunContext, provider, message: str, schema: dict, notes: list[str]) -> dict:
    from .llm_agent import PROMPT_VERSION, run_llm

    db.execute("UPDATE runs SET intent = ?, model = ?, prompt_version = ? WHERE id = ?", ("llm", provider.model, PROMPT_VERSION, ctx.run_id))
    out = run_llm(ctx, provider, message, schema)
    results = out["outputs"]
    answer = {
        "type": "proposal" if out["operations"] else "answer", "intent": "llm", "role": "supervisor",
        "text": out["text"], "results": results, "operations": out["operations"], "chart": None,
        "sources": _dedupe([s for r in results for s in r.get("sources", [])]),
        "assumptions": _assumption_notes(results), "warnings": [w for r in results for w in r.get("warnings", [])],
        "method": next((r.get("method") for r in results if r.get("method")), None),
        "filters": [], "follow_ups": [], "notes": notes, "engine": f"llm:{provider.model}", "grounding": out["grounding"],
    }
    if results and results[0].get("kind") in ("aggregate", "time_series", "variance", "period_change"):
        ctx.context["last_result"] = C.compact_result(results[0])
    if out["operations"]:
        return _await_approval(ctx, answer)
    return _complete(ctx, answer, Plan("llm", "supervisor"))


def _await_approval(ctx: RunContext, answer: dict) -> dict:
    answer = {**answer, "schema_version": "1.0", "run_id": ctx.run_id, "usage": _usage(ctx)}
    ctx.to(RunState.PREVIEW_READY)
    transition(ctx.run_id, RunState.AWAITING_APPROVAL, result=answer)
    return answer


def _complete(ctx: RunContext, answer: dict, plan: Plan) -> dict:
    answer = {**answer, "schema_version": "1.0", "run_id": ctx.run_id, "usage": _usage(ctx)}
    answer.setdefault("operations", [])
    answer.setdefault("sources", [])
    transition(ctx.run_id, RunState.COMPLETED, result=answer)
    return answer


def _usage(ctx: RunContext) -> dict:
    return {"steps": ctx.usage.steps, "tokens_in": ctx.usage.tokens_in, "tokens_out": ctx.usage.tokens_out,
            "cost_estimate_usd": round(ctx.usage.cost_usd, 6),
            "cost_note": "Estimate from configured per-token prices; not a bill." if ctx.usage.tokens_in else "No AI model tokens used."}


def _handled_error(ctx: RunContext, exc: AppError, plan: Plan, step: dict) -> dict | None:
    if exc.code == "ambiguous_date_order":
        d = exc.details
        ctx.context["pending_clarification"] = None
        return {"type": "clarification", "text": exc.message, "clarification": {
            "question": exc.message,
            "options": [{"label": "Day-first (DD/MM/YYYY)", "prompt": f"Standardize the dates in {d['column']} on {d['sheet']} as day-first"},
                        {"label": "Month-first (MM/DD/YYYY)", "prompt": f"Standardize the dates in {d['column']} on {d['sheet']} as month-first"}]}}
    if exc.code == "structural_edit_blocked":
        sheet = step.get("args", {}).get("sheet")
        return {"text": exc.message, "follow_ups": [{"label": "Flag duplicates instead", "prompt": f"Flag the duplicates on {sheet}"}]}
    if exc.code in ("nothing_to_change", "not_chartable", "insufficient_data", "insufficient_periods", "column_exists",
                    "unsafe_fill", "no_formula", "column_not_found", "sheet_not_found", "empty_sheet", "invalid_restore"):
        if step["tool"] == "create_chart":
            return {"text": ""}
        return {"text": exc.message}
    if exc.code == "ambiguous_column":
        cands = exc.details.get("candidates", [])
        return {"type": "clarification", "text": exc.message, "clarification": {
            "question": exc.message, "options": [{"label": c, "prompt": f"Use {c}"} for c in cands]}}
    return None


def _clean_sheet(ctx: RunContext, sheet: str) -> tuple[list[dict], list[str]]:
    profile = ctx.call("profile_sheet", {"sheet": sheet})
    issues = profile.get("issues", [])
    variant_cols = [i["column"] for i in issues if i["kind"] == "category_variants"]
    plan: list[dict] = []
    for col in variant_cols:
        plan.append({"sheet": sheet, "action": "normalize_categories", "column": col})
    trim_cols = [i["column"] for i in issues if i["kind"] == "whitespace" and i["column"] not in variant_cols]
    if trim_cols:
        plan.append({"sheet": sheet, "action": "trim_whitespace", "columns": trim_cols})
    for i in issues:
        if i["kind"] == "inconsistent_dates":
            plan.append({"sheet": sheet, "action": "standardize_dates", "column": i["column"]})
    for c in (profile.get("table") or {}).get("columns", []):
        if c["inferred_type"] == "mixed (number)":
            plan.append({"sheet": sheet, "action": "convert_numeric_text", "column": c["name"]})
    operations, infos = [], []
    for args in plan:
        try:
            out = ctx.call("propose_cleaning", args)
            operations.append(out["operation"])
        except AppError as exc:
            if exc.code == "ambiguous_date_order":
                infos.append(exc.message)
            elif exc.code in ("nothing_to_change",):
                continue
            elif exc.code == "budget_exceeded":
                infos.append("More cleaning steps are available; ask again after reviewing these.")
                break
            else:
                infos.append(exc.message)
    others = [i for i in issues if i["kind"] in ("duplicate_candidates", "missing_values", "outlier_candidates", "formula_error")]
    if others:
        infos.append("Also worth reviewing (not changed automatically): " + "; ".join(i["message"] for i in others[:5]))
    if not operations and not infos:
        infos.append(f"I didn't find anything on {sheet} that can be cleaned automatically.")
    return operations, infos


def _assumption_notes(results: list[dict]) -> list[str]:
    notes = []
    for r in results:
        if r.get("kind") in ("aggregate", "time_series") and r.get("excluded"):
            ex = r["excluded"]
            if ex.get("blank"):
                notes.append(f"{ex['blank']} blank cell(s) in the measure were excluded (not treated as zero).")
    return notes


def _dedupe(sources: list[dict]) -> list[dict]:
    seen, out = set(), []
    for s in sources:
        if s["id"] not in seen:
            seen.add(s["id"])
            out.append(s)
    return out


def cancel_run(principal: Principal, run_id: str) -> dict:
    run = load_run(run_id)
    if run["user_id"] != principal.user_id:
        raise AppError("run_not_found", "Run not found.", 404)
    if RunState(run["state"]) in (RunState.COMPLETED, RunState.FAILED, RunState.CANCELLED, RunState.ROLLED_BACK):
        return {"run_id": run_id, "state": run["state"], "cancelled": False}
    db.execute("UPDATE runs SET cancel_requested = 1 WHERE id = ?", (run_id,))
    if run["state"] == RunState.AWAITING_APPROVAL.value:
        # Withdraw pending proposals from this run.
        db.execute("UPDATE operations SET status = 'REJECTED', updated_at = ? WHERE run_id = ? AND status = 'PROPOSED'", (now_iso(), run_id))
        transition(run_id, RunState.CANCELLED, note="Cancelled; pending proposals were withdrawn.")
    audit.record("run_cancel_requested", run_id=run_id, user_id=principal.user_id, workspace_id=principal.workspace_id,
                 workbook_id=run["workbook_id"])
    return {"run_id": run_id, "state": load_run(run_id)["state"], "cancelled": True}


def get_run(principal: Principal, run_id: str) -> dict:
    run = load_run(run_id)
    if run["user_id"] != principal.user_id and principal.role != "admin":
        raise AppError("run_not_found", "Run not found.", 404)
    W.get_workbook_row(principal, run["workbook_id"])
    from ..harness.state import PROGRESS_TEXT
    return {
        "schema_version": "1.0", "id": run["id"], "correlation_id": run["correlation_id"], "state": run["state"],
        "progress": PROGRESS_TEXT[RunState(run["state"])], "workbook_id": run["workbook_id"], "workbook_version": run["workbook_version"],
        "conversation_id": run["conversation_id"], "intent": run["intent"], "plan": run["plan"], "steps": run["steps"],
        "result": run["result"], "error": run["error"], "model": run["model"], "prompt_version": run["prompt_version"],
        "usage": {"tokens_in": run["tokens_in"], "tokens_out": run["tokens_out"], "cost_estimate_usd": run["cost_estimate_usd"]},
        "created_at": run["created_at"], "updated_at": run["updated_at"],
    }


def list_runs(principal: Principal, workbook_id: str) -> list[dict]:
    W.get_workbook_row(principal, workbook_id)
    return db.fetchall("SELECT id, state, intent, model, tokens_in, tokens_out, cost_estimate_usd, created_at, workbook_version "
                       "FROM runs WHERE workbook_id = ? AND user_id = ? ORDER BY created_at DESC LIMIT 50", (workbook_id, principal.user_id))
