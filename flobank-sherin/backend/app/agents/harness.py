"""Enterprise agent harness on LangGraph.

  plan_task -> execute_step (loop, one agent per step) -> verify -> approval_gate (interrupt) -> finalize

* Planning: deterministic keyword/attachment router validated against the agent registry.
* Tool permissions: a step may only call tools on its agent's allow-list; violations are denied and audited.
* Retry and recovery: each tool call is retried up to MAX_RETRIES times; failures are recorded, not hidden.
* Checkpointing: LangGraph SqliteSaver keyed by run id, so a run paused for approval survives restarts.
* Human approval: state-changing actions (apply a diff, open a PR, deploy, trade) pause the graph with interrupt().
* Accounting: one AgentTask per run (data_class="measured") with measured wall time, measured Ollama tokens if the
  local model was used, allocated compute, and human review minutes measured from the approval decision.
"""
from __future__ import annotations

import datetime as dt
import logging
import operator
import re
import sqlite3
import threading
import time
import uuid
from decimal import Decimal
from typing import Annotated, Any, TypedDict

import yaml
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from sqlalchemy import select

from app import catalog as C
from app import models as M
from app.agents import llm
from app.agents import tools as T
from app.approvals import service as approvals
from app.audit import audit
from app.config import get_settings
from app.data.seed import local_inference_cost, q
from app.db import session_scope
from app.guardian import engine as guardian

log = logging.getLogger("sherin.harness")
MAX_RETRIES = 2
CONTAINER_HOURLY_USD = Decimal("0.20")  # allocated agent runtime cost (Azure Container Apps equivalent)


class HarnessState(TypedDict, total=False):
    run_id: str
    request: str
    requested_by: str
    attachments: list[dict]
    context: dict
    plan: list[dict]
    cursor: int
    results: Annotated[list[dict], operator.add]
    trace: Annotated[list[dict], operator.add]
    actions: list[dict]
    approval_id: str | None
    approval: dict | None
    status: str


NODES = ["plan_task", "execute_step", "verify", "approval_gate", "finalize"]
EDGES = [("__start__", "plan_task", ""), ("plan_task", "execute_step", "plan ready"), ("plan_task", "finalize", "nothing to do"),
         ("execute_step", "execute_step", "next step"), ("execute_step", "verify", "all steps done"),
         ("verify", "approval_gate", "action proposed"), ("verify", "finalize", "no action"),
         ("approval_gate", "finalize", "decision recorded"), ("finalize", "__end__", "")]


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat(timespec="milliseconds")


# Typed execution events (stored in the run trace, streamed to the UI):
# RUN_PLANNED, AGENT_STARTED, TOOL_RUNNING, TOOL_RETRY, TOOL_COMPLETED, TOOL_FAILED, TOOL_DENIED,
# VALIDATION_STARTED, VALIDATION_PASSED, VALIDATION_FAILED, APPROVAL_REQUIRED, APPROVAL_DECIDED, TASK_COMPLETED, TASK_FAILED
TERMINAL_EVENTS = {"TASK_COMPLETED", "TASK_FAILED"}


def _ev(node: str, msg: str, **kw) -> dict:
    return {"at": _now(), "node": node, "message": msg, **kw}


# ---------------------------------------------------------------------------------------------- planning
def _att(state, *exts) -> dict | None:
    for a in state.get("attachments") or []:
        if a.get("name", "").lower().endswith(exts):
            return a
    return None


def make_plan(request: str, attachments: list[dict], context: dict) -> list[dict]:
    r = request.lower()
    names = " ".join(a.get("name", "").lower() for a in attachments)
    steps: list[tuple[str, str, str]] = []
    if re.search(r"\.ya?ml\b", names) or re.search(r"pipeline|ci/cd|yaml|build fail", r):
        steps += [("cicd", "pipeline.yaml_lint", "Analyse pipeline YAML and propose a fix"),
                  ("azure_devops", "ado.pull_request.draft", "Draft a pull request for the fix")]
        if "deploy" in r:
            steps.append(("cicd", "deploy.request_approval", "Request human-approved production deployment"))
    if ".py" in names or re.search(r"python|debug|traceback|bug", r):
        steps += [("python_coding", "python.ast_debug", "Debug the Python code and propose a patch"),
                  ("qa", "python.test_gen", "Generate regression test scaffolds"),
                  ("python_coding", "diff.propose", "Propose the patch for human approval")]
    elif re.search(r"\btests?\b", r):
        steps.append(("qa", "python.test_gen", "Generate test scaffolds"))
    for kw, tool in [("data factory", "adf.diagnose"), ("adf", "adf.diagnose"), ("function", "functions.diagnose"), ("aks", "aks.describe"),
                     ("kubernetes", "aks.describe"), ("app insights", "appinsights.query"), ("application insights", "appinsights.query"),
                     ("monitor", "monitor.query"), ("incident", "monitor.query"), (".log", "monitor.query")]:
        if kw in r or kw in names:
            steps.append(("sre", tool, f"Diagnose using {tool}"))
            break
    if re.search(r"bicep|terraform|infra|configuration review|\.bicep|\.tf\b", r + " " + names):
        steps += [("azure_devops", "infra.config_review", "Review infrastructure configuration"), ("security", "secrets.scan", "Scan for secrets")]
    elif re.search(r"secret|security", r):
        steps.append(("security", "secrets.scan", "Scan for secrets"))
    if "reconcil" in r:
        steps.append(("portfolio_management", "portfolio.reconcile", "Reconcile book vs custodian"))
    if context.get("proposal_id") or re.search(r"\bTP-\d+|trade|invest", request, re.I):
        steps += [("investment_judgment", "guardian.evaluate", "Run Sherin Guardian pre-trade controls"),
                  ("risk_analytics", "risk.var", "Compute portfolio risk"), ("esg", "esg.scores", "Validate ESG exposure")]
    elif re.search(r"\bvar\b|risk", r):
        steps.append(("risk_analytics", "risk.var", "Compute portfolio risk"))
    if "esg" in r and not any(s[0] == "esg" for s in steps):
        steps.append(("esg", "esg.scores", "Validate ESG exposure"))
    if "compliance" in r:
        steps.append(("compliance", "compliance.events", "Summarise compliance events"))
    if re.search(r"cost|finops|token|spend", r):
        steps += [("finops", "finance.read", "Read AI cost position"), ("finops", "tokens.read", "Read token consumption")]
    if re.search(r"report|board|summary", r):
        steps.append(("reporting", "report.generate", "Compile executive report"))
    if not steps:
        steps.append(("reporting", "finance.read", "Summarise the financial position"))
    seen, out = set(), []
    for a, t, o in steps:
        if (a, t) not in seen:
            seen.add((a, t))
            out.append({"step": len(out) + 1, "agent": a, "tool": t, "objective": o})
    return out


# ---------------------------------------------------------------------------------------------- tools
def _text(state, *exts) -> tuple[str, str]:
    a = _att(state, *exts)
    if a:
        return a["content"], a["name"]
    return state.get("request", ""), "request.txt"


def _finance_summary(db) -> dict:
    from app.finance import engine as E
    p = E.resolve_period("month", get_settings().demo_end_month)
    e = E.economics(db, p, "synthetic")
    return {"period": p.label, "data_class": "synthetic", "bank_revenue_usd": float(e["bank"]["revenue"]), "ai_cost_usd": float(e["ai"]["total"]),
            "cost_avoidance_usd": float(e["cost_avoidance"]), "net_benefit_usd": float(e["net_benefit"]),
            "roi_pct": float(e["roi_pct"]) if e["roi_pct"] is not None else None}


def run_tool(tool: str, state: HarnessState, db, prior: list[dict]) -> dict:
    ctx = state.get("context") or {}
    if tool == "python.ast_debug":
        code, name = _text(state, ".py")
        return T.python_ast_debug(code, name)
    if tool == "python.test_gen":
        code, name = _text(state, ".py")
        return T.python_test_gen(code, name.rsplit(".", 1)[0])
    if tool == "diff.propose":
        dbg = next((r["output"] for r in prior if r["tool"] == "python.ast_debug"), None)
        if not dbg or not dbg.get("diff"):
            return {"ok": True, "action": None, "note": "No automatic patch available; findings require a human fix."}
        return {"ok": True, "action": {"kind": "code_change", "title": "Apply Python patch", "diff": dbg["diff"]}}
    if tool == "pipeline.yaml_lint":
        text, name = _text(state, ".yml", ".yaml")
        return T.pipeline_yaml_lint(text, name)
    if tool == "ado.pull_request.draft":
        lint = next((r["output"] for r in prior if r["tool"] in ("pipeline.yaml_lint", "python.ast_debug")), {})
        if not lint.get("diff"):
            return {"ok": True, "action": None, "note": "Nothing to put in a pull request."}
        pr = T.pr_draft("Fix pipeline configuration" if "pipeline" in str(prior) else "Fix code issues", lint["diff"], lint.get("findings", []))
        return {"ok": True, "pull_request": pr, "action": {"kind": "code_change", "title": pr["title"], "diff": pr["diff"]},
                "note": "PR drafted locally. Opening it in Azure DevOps requires approval and a configured ADO connection (pending)."}
    if tool == "deploy.request_approval":
        return {"ok": True, "action": {"kind": "deployment", "title": "Production deployment of the pipeline fix", "environment": "production"}}
    if tool in ("adf.diagnose", "functions.diagnose", "aks.describe", "appinsights.query", "monitor.query"):
        text, _ = _text(state, ".log", ".txt", ".json")
        hint = {"adf.diagnose": "adf", "functions.diagnose": "functions", "aks.describe": "aks", "appinsights.query": "appinsights"}.get(tool)
        out = T.azure_diagnose(text, None)
        out["incidents"] = T.incidents_summary(db, {"adf": "Data Factory", "functions": "Functions", "aks": "AKS", "appinsights": "App Insights"}.get(hint or "", None))
        return out
    if tool == "infra.config_review":
        text, _ = _text(state, ".bicep", ".tf", ".json", ".yml", ".yaml")
        return T.infra_config_review(text)
    if tool == "secrets.scan":
        text, _ = _text(state, ".py", ".yml", ".yaml", ".bicep", ".tf", ".json", ".txt", ".env")
        return T.secrets_scan(text)
    if tool == "portfolio.reconcile":
        return T.portfolio_reconcile(db, ctx.get("portfolio_id", "PF-BAL"))
    if tool == "guardian.evaluate":
        pid = ctx.get("proposal_id") or (re.search(r"TP-\d+", state.get("request", "")) or [None])[0]
        if not pid:
            return {"ok": False, "error": "No trade proposal id supplied (e.g. TP-1001)."}
        prop = db.get(M.TradeProposal, pid)
        if prop is None:
            return {"ok": False, "error": f"Unknown proposal {pid}"}
        res = guardian.evaluate(db, prop)
        prop.decision, prop.guardian_result = res["decision"], res
        action = None
        if res["decision"] in ("PASS", "REVIEW", "BLOCK", "INSUFFICIENT_DATA"):
            action = {"kind": "investment", "proposal_id": pid, "title": f"{prop.side} {prop.issuer}", "guardian_decision": res["decision"]}
        return {"ok": True, "guardian": res, "action": action}
    if tool == "risk.var":
        pid = ctx.get("portfolio_id")
        if not pid and ctx.get("proposal_id"):
            pr = db.get(M.TradeProposal, ctx["proposal_id"])
            pid = pr.portfolio_id if pr else None
        m = re.search(r"TP-\d+", state.get("request", ""))
        if not pid and m:
            pr = db.get(M.TradeProposal, m.group(0))
            pid = pr.portfolio_id if pr else None
        return T.portfolio_risk(db, pid or "PF-BAL")
    if tool == "esg.scores":
        out = T.portfolio_risk(db, ctx.get("portfolio_id", "PF-GRN"))
        return {"ok": True, "low_esg_positions": out["low_esg_positions"], "portfolio_id": out["portfolio_id"]}
    if tool == "compliance.events":
        return T.compliance_summary(db)
    if tool == "finance.read":
        return {"ok": True, **_finance_summary(db)}
    if tool == "tokens.read":
        from app.finance import engine as E
        p = E.resolve_period("month", get_settings().demo_end_month)
        ta = E.token_analytics(db, p, "month", E.fx_for(db, "USD"), "synthetic")
        return {"ok": True, "totals": ta["totals"], "top_agents": ta["per_agent"][:3]}
    if tool == "report.generate":
        fs = _finance_summary(db)
        return {"ok": True, "report_markdown": f"# Sherin executive summary ({fs['period']}, synthetic)\n\n" +
                "\n".join(f"- **{k.replace('_', ' ')}**: {v:,.2f}" if isinstance(v, float) else f"- **{k.replace('_', ' ')}**: {v}" for k, v in fs.items())}
    raise ValueError(f"no implementation for tool {tool}")


# ---------------------------------------------------------------------------------------------- nodes
def plan_task(state: HarnessState) -> dict:
    plan = make_plan(state["request"], state.get("attachments") or [], state.get("context") or {})
    _persist(state["run_id"], status="running", plan=plan, trace_add=[_ev("plan_task", f"Planned {len(plan)} step(s)", plan=plan, event="RUN_PLANNED")])
    return {"plan": plan, "cursor": 0, "status": "running", "trace": [_ev("plan_task", f"Planned {len(plan)} step(s)")]}


def execute_step(state: HarnessState) -> dict:
    step = state["plan"][state["cursor"]]
    agent, tool = step["agent"], step["tool"]
    allowed = C.AGENTS[agent]["tools"]
    t0 = time.perf_counter()
    # Persisted before the tool runs so observers see the agent start in real time.
    started = [_ev("execute_step", f"{C.AGENTS[agent]['label']} started: {step['objective']}", agent=agent, tool=tool, step=step["step"], status="running", event="AGENT_STARTED")]
    if tool in allowed:
        started.append(_ev("execute_step", f"{agent} running {tool}", agent=agent, tool=tool, step=step["step"], status="running", event="TOOL_RUNNING"))
    _persist(state["run_id"], trace_add=started)
    events: list[dict] = []
    if tool not in allowed:
        res = {"step": step["step"], "agent": agent, "tool": tool, "ok": False, "denied": True, "retries": 0, "duration_ms": 0,
               "output": {"error": f"Tool {tool} is not permitted for {agent}"}, "tokens": None}
        with session_scope() as db:
            audit(db, f"agent.{agent}", "AGENT", "tool.denied", "harness_run", state["run_id"], tool=tool)
        events.append(_ev("execute_step", f"Permission denied: {agent} cannot call {tool}", agent=agent, tool=tool, step=step["step"], status="denied", event="TOOL_DENIED"))
    else:
        out, retries, err = None, 0, None
        while True:
            try:
                with session_scope() as db:
                    out = run_tool(tool, state, db, state.get("results") or [])
                break
            except Exception as e:  # noqa: BLE001 - recorded and retried
                err = f"{type(e).__name__}: {e}"
                if retries >= MAX_RETRIES:
                    out = {"ok": False, "error": err}
                    break
                retries += 1
                events.append(_ev("execute_step", f"Retry {retries}/{MAX_RETRIES} after error: {err}", agent=agent, tool=tool, step=step["step"], status="retry", event="TOOL_RETRY"))
                time.sleep(0.05 * 2 ** retries)
        tokens = None
        if out.get("ok") is not False and llm.status()["available"]:
            g = llm.generate(f"Summarise these {tool} results for a banking engineering manager in 3 bullet points:\n{str(out)[:4000]}",
                             system="You are Sherin, FLO Bank's agent. Be factual; do not invent numbers.", max_tokens=200)
            if g:
                tokens = {k: g[k] for k in ("input_tokens", "output_tokens", "latency_ms", "model")}
                out["llm_summary"] = g["text"]
        res = {"step": step["step"], "agent": agent, "tool": tool, "ok": out.get("ok", True) is not False, "retries": retries,
               "duration_ms": int((time.perf_counter() - t0) * 1000), "output": out, "tokens": tokens}
        events.append(_ev("execute_step", f"{'Completed' if res['ok'] else 'Failed'} in {res['duration_ms']} ms", agent=agent, tool=tool,
                          status="ok" if res["ok"] else "failed", retries=retries, tokens=tokens, step=step["step"],
                          event="TOOL_COMPLETED" if res["ok"] else "TOOL_FAILED", error=None if res["ok"] else out.get("error")))
    _persist(state["run_id"], trace_add=events, result_add=res)
    return {"results": [res], "cursor": state["cursor"] + 1, "trace": started + events}


def route_after_execute(state: HarnessState) -> str:
    return "execute_step" if state["cursor"] < len(state["plan"]) else "verify"


def _verify_one(r: dict) -> tuple[bool, str]:
    o = r["output"]
    if not r["ok"]:
        return False, o.get("error", "step failed")
    if r["tool"] == "python.ast_debug" and o.get("fixed_code"):
        try:
            compile(o["fixed_code"], "patched.py", "exec")
        except SyntaxError as e:
            return False, f"patched code does not compile: {e}"
        again = T.python_ast_debug(o["fixed_code"])
        fixed_rules = {"bare-except", "none-comparison"}
        if any(f["rule"] in fixed_rules for f in again["findings"]):
            return False, "patch did not remove the findings it claims to fix"
        return True, "patched code compiles and auto-fixable findings are gone"
    if r["tool"] == "python.test_gen" and o.get("ok"):
        compile(o["tests"], "test_generated.py", "exec")
        return True, "generated tests compile"
    if r["tool"] == "pipeline.yaml_lint" and o.get("diff"):
        new = _apply_unified(o["diff"])
        try:
            yaml.safe_load(new) if new is not None else None
        except yaml.YAMLError as e:
            return False, f"patched YAML invalid: {e}"
        return True, "patched YAML parses"
    if r["tool"] == "guardian.evaluate" and o.get("guardian"):
        g = o["guardian"]
        return guardian.decide(g["checks"]) == g["decision"], "guardian decision recomputed from checks"
    if r["tool"] == "portfolio.reconcile":
        return o["matched"] + len(o["breaks"]) == o["positions"], "break count reconciles to position count"
    return o.get("ok", True) is not False, "output present"


def _apply_unified(diff: str) -> str | None:
    """Rebuild the 'after' text of a single-file unified diff (context + added lines)."""
    out, in_hunk = [], False
    for ln in diff.splitlines():
        if ln.startswith("@@"):
            in_hunk = True
            continue
        if not in_hunk or ln.startswith(("---", "+++")):
            continue
        if ln.startswith("+"):
            out.append(ln[1:])
        elif ln.startswith(" "):
            out.append(ln[1:])
    return "\n".join(out) if out else None


def verify(state: HarnessState) -> dict:
    _persist(state["run_id"], trace_add=[_ev("verify", "Independent Verification Agent is checking every step", agent="verification", status="running", event="VALIDATION_STARTED")])
    checks = []
    for r in state.get("results") or []:
        ok, why = _verify_one(r)
        checks.append({"step": r["step"], "agent": r["agent"], "tool": r["tool"], "verified": ok, "reason": why})
    actions = [dict(r["output"]["action"], step=r["step"], agent=r["agent"]) for r in state.get("results") or []
               if r["ok"] and isinstance(r["output"], dict) and r["output"].get("action")]
    all_ok = all(c["verified"] for c in checks) and bool(checks)
    ev = [_ev("verify", f"Independent Verification Agent: {sum(c['verified'] for c in checks)}/{len(checks)} steps verified", agent="verification",
              status="ok" if all_ok else "failed", checks=checks, event="VALIDATION_PASSED" if all_ok else "VALIDATION_FAILED")]
    _persist(state["run_id"], trace_add=ev, verification=checks)
    return {"trace": ev, "actions": actions if all_ok else [],
            "status": "verified" if all_ok else "verification_failed"}


def route_after_verify(state: HarnessState) -> str:
    return "approval_gate" if state.get("actions") else "finalize"


def approval_gate(state: HarnessState) -> dict:
    approval_id = state.get("approval_id")
    if not approval_id:
        with session_scope() as db:
            acts = state["actions"]
            inv = next((a for a in acts if a["kind"] == "investment"), None)
            if inv:
                prop = db.get(M.TradeProposal, inv["proposal_id"])
                ap = approvals.for_guardian(db, prop, prop.guardian_result, requested_by=state["requested_by"])
                ap.related_run_id = state["run_id"]
                ap.data_class = "measured"
            else:
                kinds = {a["kind"] for a in acts}
                kind = "deployment" if "deployment" in kinds else "code_change"
                ap = approvals.create(db, kind=kind,
                                      title="; ".join(a["title"] for a in acts)[:200],
                                      summary=f"Sherin harness run {state['run_id']} proposes {len(acts)} state-changing action(s). Verified by the Independent Verification Agent.",
                                      requested_by=f"agent.{acts[0]['agent']}", required_roles=approvals.required_roles_for(kind),
                                      risk_evidence=[f"Step {a['step']} ({a['agent']}): {a['title']}" for a in acts], related_run_id=state["run_id"])
            approval_id = ap.id
            status = ap.status
        ev = [_ev("approval_gate", f"Waiting for human approval {approval_id} ({status})", status="waiting", approval_id=approval_id, approval_status=status,
                  event="APPROVAL_REQUIRED")]
        _persist(state["run_id"], status="awaiting_approval" if status not in ("blocked", "insufficient_data") else status, trace_add=ev,
                 approval_id=approval_id)
        if status in ("blocked", "insufficient_data"):
            return {"approval_id": approval_id, "approval": {"status": status}, "trace": ev}
    decision = interrupt({"approval_id": approval_id})
    ev = [_ev("approval_gate", f"Approval {approval_id}: {decision.get('status')}", status=decision.get("status"), approval_id=approval_id, event="APPROVAL_DECIDED")]
    _persist(state["run_id"], trace_add=ev)
    return {"approval_id": approval_id, "approval": decision, "trace": ev}


def finalize(state: HarnessState) -> dict:
    results = state.get("results") or []
    run_id = state["run_id"]
    appr = state.get("approval") or {}
    with session_scope() as db:
        run = db.get(M.HarnessRun, run_id)
        primary = results[0]["agent"] if results else "reporting"
        wf = C.AGENTS[primary]["workflow"] or "executive_reporting"
        base = db.get(M.HumanBaseline, wf)
        duration_s = max(1, round(sum(r["duration_ms"] for r in results) / 1000))
        verified = state.get("status") == "verified"
        review_min = Decimal(str(appr.get("review_minutes", 0)))
        review_basis = "measured" if appr.get("review_minutes") is not None else "estimated"
        if not appr.get("review_minutes"):
            review_min = Decimal("5")  # estimated time for a human to read the run output
        model_cost = Decimal(0)
        task_id = f"R{uuid.uuid4().hex[:9].upper()}"
        token_rows = []
        for r in results:
            if r.get("tokens"):
                lc, le = local_inference_cost(r["tokens"]["latency_ms"])
                model_cost += lc + le
                token_rows.append(M.TokenUsage(ts=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None), agent=r["agent"], task_id=task_id, provider="local_qwen",
                                               model=r["tokens"]["model"], input_tokens=r["tokens"]["input_tokens"], output_tokens=r["tokens"]["output_tokens"],
                                               cached_tokens=0, api_cost_usd=Decimal(0), local_compute_usd=lc, local_energy_usd=le,
                                               latency_ms=r["tokens"]["latency_ms"], success=r["ok"], data_class="measured"))
        compute = q(Decimal(duration_s) / 3600 * CONTAINER_HOURLY_USD)
        review_cost = q(review_min / 60 * Decimal(base.hourly_rate_usd))
        approved = appr.get("status") == "approved"
        rejected = appr.get("status") in ("rejected", "changes_requested")  # a human declined the agent's output
        task = M.AgentTask(id=task_id, run_id=run_id, agent=primary, department=C.WORKFLOW_BASELINES[wf][0], workflow_type=wf,
                           title=state["request"][:200], created_at=dt.datetime.now(dt.timezone.utc).replace(tzinfo=None), duration_s=duration_s,
                           status="succeeded" if all(r["ok"] for r in results) else "failed", quality_pass=verified,
                           verified=verified and not rejected, retries=sum(r["retries"] for r in results), tool_calls=len(results),
                           human_review_min=review_min, rework_min=Decimal(0), cost_model=q(model_cost), cost_compute=compute, cost_infra=Decimal(0),
                           cost_tooling=Decimal(0), cost_human_review=review_cost, cost_rework=Decimal(0), baseline_hours=base.hours_per_task,
                           baseline_rate_usd=base.hourly_rate_usd, summary=f"Harness run {run_id}", data_class="measured")
        db.add(task)
        db.flush()
        for tr in token_rows:
            db.add(tr)
        today = dt.date.today()
        for cat, amt, sub in [("llm_inference", q(model_cost), "local qwen (measured latency)"), ("compute", compute, "agent runtime (measured)"),
                              ("human_review", review_cost, f"review ({review_basis})")]:
            if amt > 0:
                db.add(M.AiCostRecord(date=today, category=cat, subcategory=sub, agent=primary, task_id=task_id, amount_usd=amt,
                                      description=f"{task_id} {state['request'][:150]}", vendor="internal", basis="actual" if review_basis == "measured" or cat != "human_review" else "estimated",
                                      data_class="measured"))
        baseline_cost = q(Decimal(base.hours_per_task) * Decimal(base.hourly_rate_usd))
        ai_cost = q(model_cost) + compute + review_cost
        outcome = ("applied (simulated - no live Azure DevOps connection configured)" if approved else
                   appr.get("status") or ("no action required" if not state.get("actions") else "pending"))
        summary = {"task_id": task_id, "verified": bool(task.verified), "agent_minutes": round(duration_s / 60, 2), "human_review_minutes": float(review_min),
                   "human_review_basis": review_basis, "allocated_cost_usd": float(ai_cost), "model_cost_usd": float(q(model_cost)),
                   "compute_cost_usd": float(compute), "human_baseline_usd": float(baseline_cost), "human_baseline_hours": float(base.hours_per_task),
                   "baseline_source": base.source, "estimated_saving_usd": float(baseline_cost - ai_cost) if task.verified else 0.0,
                   "llm_used": any(r.get("tokens") for r in results), "tokens": sum((r["tokens"] or {}).get("input_tokens", 0) + (r["tokens"] or {}).get("output_tokens", 0) for r in results),
                   "action_outcome": outcome, "approval_id": state.get("approval_id"),
                   "sentence": (f"This run required {round(duration_s / 60, 1)} minutes of agent execution, {float(review_min):g} minutes of human review "
                                f"({review_basis}), and ${float(ai_cost):,.2f} of allocated compute, model and review cost, against a configured human baseline of "
                                f"{float(base.hours_per_task):g} hours (${float(baseline_cost):,.2f}).")}
        run.status = "completed" if appr.get("status") in (None, "approved") else f"completed_{appr.get('status')}"
        run.result = {**(run.result or {}), **summary}
        run.finished_at = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
        run.trace = [*run.trace, _ev("finalize", summary["sentence"], status="done", event="TASK_COMPLETED", verified=summary["verified"],
                                     action_outcome=summary["action_outcome"], task_id=task_id)]
        audit(db, state["requested_by"], "USER", "harness.completed", "harness_run", run_id, task_id=task_id, verified=bool(task.verified))
    return {"status": "completed", "trace": [_ev("finalize", "Run complete")]}


def _persist(run_id: str, *, status: str | None = None, plan=None, trace_add=None, result_add=None, verification=None, approval_id=None):
    with session_scope() as db:
        run = db.get(M.HarnessRun, run_id)
        if run is None:
            return
        if status:
            run.status = status
        if plan is not None:
            run.plan = plan
        if trace_add:
            run.trace = [*run.trace, *trace_add]
        res = dict(run.result or {})
        if result_add is not None:
            res["steps"] = [*res.get("steps", []), result_add]
        if verification is not None:
            res["verification"] = verification
        if approval_id:
            res["approval_id"] = approval_id
        run.result = res


# ---------------------------------------------------------------------------------------------- graph + service
def build_graph(checkpointer):
    g = StateGraph(HarnessState)
    for n in NODES:
        g.add_node(n, globals()[n])
    g.add_edge(START, "plan_task")
    g.add_conditional_edges("plan_task", lambda s: "execute_step" if s.get("plan") else "finalize", ["execute_step", "finalize"])
    g.add_conditional_edges("execute_step", route_after_execute, ["execute_step", "verify"])
    g.add_conditional_edges("verify", route_after_verify, ["approval_gate", "finalize"])
    g.add_edge("approval_gate", "finalize")
    g.add_edge("finalize", END)
    return g.compile(checkpointer=checkpointer)


class Harness:
    def __init__(self, checkpoint_path: str | None = None, sync_mode: bool = False):
        self.sync_mode = sync_mode  # tests run graph invocations inline instead of on a worker thread
        path = checkpoint_path or get_settings().checkpoint_path
        if path != ":memory:":
            from pathlib import Path
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self.saver = SqliteSaver(self._conn)
        self.saver.setup()
        self.graph = build_graph(self.saver)
        self._lock = threading.Lock()

    def _invoke(self, payload, run_id: str):
        cfg = {"configurable": {"thread_id": run_id}, "recursion_limit": 60}
        try:
            with self._lock:
                self.graph.invoke(payload, cfg)
        except Exception as e:  # noqa: BLE001
            log.exception("harness run failed")
            _persist(run_id, status="failed", trace_add=[_ev("error", f"{type(e).__name__}: {e}", status="failed", event="TASK_FAILED")])

    def start(self, request: str, requested_by: str, attachments: list[dict] | None = None, context: dict | None = None, sync: bool | None = None) -> str:
        sync = self.sync_mode if sync is None else sync
        run_id = f"RUN-{uuid.uuid4().hex[:10].upper()}"
        with session_scope() as db:
            db.add(M.HarnessRun(id=run_id, request=request, requested_by=requested_by, status="queued", plan=[], trace=[], result={}))
            audit(db, requested_by, "USER", "harness.started", "harness_run", run_id, request=request[:200])
        payload = {"run_id": run_id, "request": request, "requested_by": requested_by, "attachments": attachments or [], "context": context or {},
                   "results": [], "trace": []}
        if sync:
            self._invoke(payload, run_id)
        else:
            threading.Thread(target=self._invoke, args=(payload, run_id), daemon=True).start()
        return run_id

    def resume(self, run_id: str, decision: dict, sync: bool | None = None):
        sync = self.sync_mode if sync is None else sync
        if sync:
            self._invoke(Command(resume=decision), run_id)
        else:
            threading.Thread(target=self._invoke, args=(Command(resume=decision), run_id), daemon=True).start()

    def state(self, run_id: str) -> dict[str, Any]:
        snap = self.graph.get_state({"configurable": {"thread_id": run_id}})
        return {"next": list(snap.next), "values_keys": list(snap.values.keys())}


_harness: Harness | None = None


def get_harness() -> Harness:
    global _harness
    if _harness is None:
        _harness = Harness()
    return _harness


def set_harness(h: Harness | None):
    global _harness
    _harness = h


def run_to_dict(run: M.HarnessRun) -> dict:
    return {"id": run.id, "request": run.request, "requested_by": run.requested_by, "status": run.status, "plan": run.plan, "trace": run.trace,
            "result": run.result, "created_at": run.created_at.isoformat(timespec="seconds") if run.created_at else None,
            "finished_at": run.finished_at.isoformat(timespec="seconds") if run.finished_at else None}


def on_approval_decided(db, approval: M.Approval):
    """Called by the approvals API. Resumes a paused harness run once the approval reaches a final state."""
    if not approval.related_run_id or approval.status not in ("approved", "rejected", "changes_requested"):
        return
    req = approval.requested_at or dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    last = dt.datetime.fromisoformat(approval.decisions[-1]["at"]) if approval.decisions else dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    minutes = max(0.1, min(120.0, (last - req).total_seconds() / 60))
    get_harness().resume(approval.related_run_id, {"status": approval.status, "review_minutes": round(minutes, 1)})


def list_runs(db, limit: int = 30) -> list[dict]:
    return [run_to_dict(r) for r in db.scalars(select(M.HarnessRun).order_by(M.HarnessRun.created_at.desc()).limit(limit))]
