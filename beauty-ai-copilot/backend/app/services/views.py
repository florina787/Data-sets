"""Read models for the API: change detail, next steps, traceability, report export, copilot Q&A,
telemetry and process metrics. Everything here derives from persisted records."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.lifecycle.state_machine import S, allowed_from
from app.models.orm import (AcceptanceCriterion, AgentInvocation, Alert, Approval, AuditEvent, ChangeRequest, Clarification,
                            CodeRevision, CopilotMessage, EvaluationRun, EvidenceReference, GateDecision, ImpactAssessment,
                            ModelVersion, MonitoringWindow, Release, RequirementVersion, Review, RollbackRecord, User)
from app.security.rbac import has_permission
from app.services import binding, fixtures
from app.services.gates import release_gates, review_status
from app.services.repo import get_change
from app.workflows.graph import latest_interrupt


def iso(dt):
    if dt is None:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).isoformat()


def change_summary(ch: ChangeRequest) -> dict:
    return {"id": ch.id, "title": ch.title, "status": ch.status, "scenario": ch.scenario, "created_at": iso(ch.created_at),
            "updated_at": iso(ch.updated_at), "candidate_model_id": ch.candidate_model_id}


NEXT_STEPS = {
    "DRAFT": [("Requirements agent review", "investigate.run")],
    "NEEDS_CLARIFICATION": [("Answer required clarifications", "clarification.answer"), ("Approve requirement version", "requirements.approve")],
    "REQUIREMENTS_APPROVED": [("Run evidence and impact investigation", "investigate.run")],
    "IMPACT_REVIEW": [("Review cited evidence and accept impact", "impact.accept")],
    "DEVELOPMENT": [("Register candidate revision", "candidate.register"), ("Review code diff (not the author)", "review.code"), ("Run evaluation", "evaluation.run")],
    "EVALUATING": [("Wait for evaluation job", "change.read")],
    "EVALUATION_FAILED": [("Inspect failed gates; register a corrected candidate", "candidate.register")],
    "EVALUATION_INCONCLUSIVE": [("Add data/config or register a new candidate", "candidate.register")],
    "REVIEW_REQUIRED": [("Code review", "review.code"), ("Domain review", "review.domain"), ("Privacy review", "review.privacy"), ("Release approval (distinct approver)", "release.approve")],
    "RELEASE_APPROVED": [("Start simulated canary (revalidates approval)", "release.execute")],
    "CANARY": [("Advance simulated monitoring window", "monitoring.advance"), ("Promote to next stage", "release.execute")],
    "MONITORING": [("Advance simulated monitoring window", "monitoring.advance"), ("Investigate alerts", "alert.investigate"), ("Promote to next stage", "release.execute")],
    "RELEASED": [("Advance simulated monitoring window", "monitoring.advance"), ("Investigate alerts", "alert.investigate")],
    "ROLLBACK_RECOMMENDED": [("Request rollback", "rollback.request"), ("Approve or reject rollback (release manager)", "rollback.approve")],
}


def next_steps(ch: ChangeRequest, user: User) -> list[dict]:
    return [{"label": l, "permission": p, "you_can": has_permission(user.roles, p)} for l, p in NEXT_STEPS.get(ch.status, [])]


def run_dict(run: EvaluationRun, full: bool = True) -> dict:
    d = {"id": run.id, "status": run.status, "outcome": run.outcome, "candidate_model_id": run.candidate_model_id,
         "baseline_model_id": run.baseline_model_id, "candidate_artifact_digest": run.candidate_artifact_digest,
         "dataset_snapshot_id": run.dataset_snapshot_id, "dataset_digest": run.dataset_digest,
         "evaluation_config_id": run.evaluation_config_id, "evaluation_config_digest": run.evaluation_config_digest,
         "policy_version": run.policy_version, "requirement_version_id": run.requirement_version_id, "requested_by": run.requested_by,
         "created_at": iso(run.created_at), "started_at": iso(run.started_at), "finished_at": iso(run.finished_at),
         "duration_ms": run.duration_ms, "attempts": run.attempts, "error": run.error, "cancel_requested": run.cancel_requested,
         "test_set_evaluation_index": run.test_set_evaluation_index}
    if full:
        d["summary"] = run.summary
    return d


def change_detail(db: Session, user: User, change_id: str) -> dict:
    ch = get_change(db, user.tenant_id, change_id)
    rvs = db.execute(select(RequirementVersion).where(RequirementVersion.change_id == ch.id).order_by(RequirementVersion.version)).scalars().all()
    crit = defaultdict(list)
    for c in db.execute(select(AcceptanceCriterion).where(AcceptanceCriterion.requirement_version_id.in_([r.id for r in rvs]))).scalars():
        crit[c.requirement_version_id].append({"code": c.code, "text": c.text, "metric": c.metric, "gate_id": c.gate_id})
    clar = db.execute(select(Clarification).where(Clarification.change_id == ch.id)).scalars().all()
    ev = db.execute(select(EvidenceReference).where(EvidenceReference.change_id == ch.id)).scalars().all()
    ia = db.execute(select(ImpactAssessment).where(ImpactAssessment.change_id == ch.id).order_by(ImpactAssessment.created_at.desc())).scalars().first()
    runs = db.execute(select(EvaluationRun).where(EvaluationRun.change_id == ch.id).order_by(EvaluationRun.created_at)).scalars().all()
    reviews = db.execute(select(Review).where(Review.change_id == ch.id).order_by(Review.created_at)).scalars().all()
    approvals = db.execute(select(Approval).where(Approval.change_id == ch.id).order_by(Approval.created_at)).scalars().all()
    releases = db.execute(select(Release).where(Release.change_id == ch.id).order_by(Release.created_at)).scalars().all()
    alerts = db.execute(select(Alert).where(Alert.change_id == ch.id).order_by(Alert.created_at)).scalars().all()
    msgs = db.execute(select(CopilotMessage).where(CopilotMessage.change_id == ch.id).order_by(CopilotMessage.id)).scalars().all()
    inv = db.execute(select(AgentInvocation).where(AgentInvocation.change_id == ch.id).order_by(AgentInvocation.created_at)).scalars().all()
    models = db.execute(select(ModelVersion)).scalars().all()
    revisions = db.execute(select(CodeRevision)).scalars().all()
    latest_out = {}
    for i in inv:
        if i.status != "ERROR":
            latest_out[i.agent] = i.output
    gates_live = [g.dict() for g in release_gates(db, ch)] if ch.candidate_model_id else []
    return {
        "change": {**change_summary(ch), "description": ch.description, "created_by": ch.created_by, "trace_id": ch.trace_id,
                   "baseline_model_id": ch.baseline_model_id, "code_revision_id": ch.code_revision_id,
                   "dataset_snapshot_id": ch.dataset_snapshot_id, "evaluation_config_id": ch.evaluation_config_id,
                   "latest_evaluation_run_id": ch.latest_evaluation_run_id, "current_requirement_version_id": ch.current_requirement_version_id,
                   "deployment_target": ch.deployment_target, "impact_accepted": ch.impact_accepted, "version_no": ch.version_no},
        "allowed_transitions": allowed_from(ch.status),
        "next_steps": next_steps(ch, user),
        "interrupt": latest_interrupt(db, ch.id),
        "requirement_versions": [{"id": r.id, "version": r.version, "statement": r.statement, "scope": r.scope, "status": r.status,
                                  "approved_by": r.approved_by, "approved_at": iso(r.approved_at), "acceptance_criteria": crit[r.id]} for r in rvs],
        "clarifications": [{"id": c.id, "key": c.key, "question": c.question, "required": c.required, "owner_role": c.owner_role,
                            "suggested_answer": c.suggested_answer, "answer": c.answer, "structured_answer": c.structured_answer,
                            "answered_by": c.answered_by, "answered_at": iso(c.answered_at), "cycle": c.cycle,
                            "related_guidance": c.evidence_refs} for c in clar],
        "evidence": [{"id": e.id, "source_id": e.source_id, "source_version": e.source_version, "section": e.section,
                      "excerpt": e.excerpt, "purpose": e.purpose, "retrieved_at": iso(e.retrieved_at), "retrieved_by": e.retrieved_by,
                      "validation_status": e.validation_status, "flags": e.flags} for e in ev],
        "evidence_analysis": latest_out.get("evidence", {}).get("data"),
        "impact": {"id": ia.id, "content": ia.content, "accepted_by": ia.accepted_by, "accepted_at": iso(ia.accepted_at),
                   "requirement_version_id": ia.requirement_version_id} if ia else None,
        "development": latest_out.get("development", {}).get("data"),
        "models": [{"id": m.id, "version": m.version, "role": m.role, "artifact_digest": m.artifact_digest, "preprocessing": m.preprocessing,
                    "catalogue_version": m.catalogue_version, "code_revision_id": m.code_revision_id,
                    "lighting_profile_map_id": m.lighting_profile_map_id, "provenance": m.provenance, "is_fixture": m.is_fixture} for m in models],
        "revisions": [{"id": r.id, "author": r.author_user_id, "summary": r.summary, "diff": r.diff, "diff_digest": r.diff_digest,
                       "requirement_refs": r.requirement_refs, "test_refs": r.test_refs} for r in revisions if r.diff],
        "evaluation_runs": [run_dict(r, full=False) for r in runs],
        "evaluation_interpretation": latest_out.get("evaluation"),
        "governance": latest_out.get("governance"),
        "release_readiness": {"gates": gates_live, "overall": _overall(gates_live), "recommendation": latest_out.get("release")},
        "reviews": [{"id": r.id, "kind": r.kind, "decision": r.decision, "reviewer_id": r.reviewer_id, "comment": r.comment,
                     "binding": r.binding, "created_at": iso(r.created_at), "invalidated_at": iso(r.invalidated_at),
                     "invalidated_reason": r.invalidated_reason} for r in reviews],
        "review_status": review_status(db, ch) if ch.candidate_model_id else None,
        "approvals": [{"id": a.id, "kind": a.kind, "decision": a.decision, "approver_id": a.approver_id, "comment": a.comment,
                       "binding": a.binding, "created_at": iso(a.created_at), "expires_at": iso(a.expires_at),
                       "consumed_at": iso(a.consumed_at), "consumed_by": a.consumed_by, "invalidated_at": iso(a.invalidated_at),
                       "invalidated_reason": a.invalidated_reason} for a in approvals],
        "current_binding": binding.current_binding(db, ch) if ch.candidate_model_id else None,
        "releases": [{"id": r.id, "status": r.status, "model_id": r.model_id, "stages": r.stages, "stage_index": r.stage_index,
                      "allocation_pct": r.stages[r.stage_index], "previous_model_id": r.previous_model_id, "history": r.history,
                      "mode": r.mode} for r in releases],
        "alerts": [{"id": a.id, "release_id": a.release_id, "scope": a.scope, "status": a.status, "observed": a.observed,
                    "investigation": a.investigation} for a in alerts],
        "messages": [{"id": m.id, "role": m.role, "author": m.author, "text": m.text, "refs": m.refs, "created_at": iso(m.created_at)} for m in msgs],
        "agent_invocations": [{"id": i.id, "agent": i.agent, "status": i.status, "language_mode": i.language_mode, "provider": i.provider,
                               "model": i.model, "latency_ms": i.latency_ms, "tool_calls": i.tool_calls, "input_tokens": i.input_tokens,
                               "output_tokens": i.output_tokens, "cost_usd": i.cost_usd, "summary": i.output.get("summary") if i.output else None,
                               "llm_summary": i.output.get("llm_summary") if i.output else None, "llm_error": i.output.get("llm_error") if i.output else None,
                               "error": i.error, "created_at": iso(i.created_at), "thread_id": i.thread_id} for i in inv],
    }


def _overall(gates: list[dict]) -> str:
    st = {g["status"] for g in gates}
    return "FAIL" if "FAIL" in st else ("INCONCLUSIVE" if "INCONCLUSIVE" in st or not gates else "PASS")


# ---------------------------------------------------------------------------
# Traceability and report
# ---------------------------------------------------------------------------

def traceability(db: Session, user: User, change_id: str) -> dict:
    d = change_detail(db, user, change_id)
    chain = []
    for rv in d["requirement_versions"]:
        chain.append({"type": "requirement", "id": rv["id"], "label": f"Requirement v{rv['version']} ({rv['status']})",
                      "links": [c["code"] for c in rv["acceptance_criteria"]]})
    for c in d["clarifications"]:
        chain.append({"type": "clarification", "id": c["id"], "label": f"{c['key']}: {'answered' if c['answer'] else 'OPEN'} (cycle {c['cycle']})"})
    for r in d["revisions"]:
        if r["id"] == d["change"]["code_revision_id"] or any(run["candidate_model_id"].endswith(r["id"].split("REV-")[-1]) for run in d["evaluation_runs"]):
            chain.append({"type": "revision", "id": r["id"], "label": f"{r['id']} by {r['author']} → {', '.join(r['requirement_refs'])}",
                          "links": r["test_refs"]})
    if d["change"]["dataset_snapshot_id"]:
        chain.append({"type": "dataset", "id": d["change"]["dataset_snapshot_id"], "label": "Synthetic dataset snapshot"})
    for run in d["evaluation_runs"]:
        chain.append({"type": "evaluation", "id": run["id"], "label": f"{run['candidate_model_id']}: {run['status']} / {run['outcome']}"})
        for g in db.execute(select(GateDecision).where(GateDecision.run_id == run["id"])).scalars():
            if g.status != "PASS":
                chain.append({"type": "policy_decision", "id": f"{run['id']}:{g.gate_id}", "label": f"{g.gate_id} {g.status}: {g.observed[:120]}"})
    for r in d["reviews"]:
        chain.append({"type": "review", "id": r["id"], "label": f"{r['kind']} {r['decision']} by {r['reviewer_id']}" + (" (invalidated)" if r["invalidated_at"] else "")})
    for a in d["approvals"]:
        chain.append({"type": "approval", "id": a["id"], "label": f"{a['kind']} {a['decision']} by {a['approver_id']}" +
                      (" (used)" if a["consumed_at"] else "") + (" (invalidated)" if a["invalidated_at"] else "")})
    for r in d["releases"]:
        chain.append({"type": "release", "id": r["id"], "label": f"{r['model_id']} {r['status']} (simulated, stages {r['stages']})"})
        for w in db.execute(select(MonitoringWindow).where(MonitoringWindow.release_id == r["id"]).order_by(MonitoringWindow.index)).scalars():
            chain.append({"type": "monitoring", "id": w.id, "label": f"window {w.index} @ {w.allocation_pct}%: {w.labelled} labelled (simulated)"})
        for rb in db.execute(select(RollbackRecord).where(RollbackRecord.release_id == r["id"])).scalars():
            chain.append({"type": "rollback", "id": rb.id, "label": f"rollback {rb.status} → {rb.target_model_id}"})
    for a in d["alerts"]:
        chain.append({"type": "alert", "id": a["id"], "label": f"{a['scope']} {a['status']}"})
    return {"change_id": change_id, "chain": chain}


def report_markdown(db: Session, user: User, change_id: str) -> str:
    d = change_detail(db, user, change_id)
    ch = d["change"]
    L = [f"# Change report — {ch['id']}", "", "> Independent beauty AI prototype — synthetic evaluation data. Fixture predictions, not computer-vision inference. Simulated deployment.", "",
         f"**Title:** {ch['title']}  ", f"**Status:** {ch['status']}  ", f"**Generated:** {datetime.now(timezone.utc).isoformat()}", "",
         "## Requirement", ""]
    for rv in d["requirement_versions"]:
        L.append(f"- v{rv['version']} — {rv['status']}" + (f" (approved by {rv['approved_by']})" if rv["approved_by"] else ""))
        for c in rv["acceptance_criteria"]:
            L.append(f"  - **{c['code']}** {c['text']}" + (f" → `{c['gate_id']}`" if c["gate_id"] else ""))
    L += ["", "## Clarifications", "", "| Key | Answer | By | Cycle |", "|---|---|---|---|"]
    for c in d["clarifications"]:
        L.append(f"| {c['key']} | {(c['answer'] or 'OPEN').replace('|', '/')} | {c['answered_by'] or ''} | {c['cycle']} |")
    L += ["", "## Evidence", "", "| Source | Version | Section | Status | Purpose |", "|---|---|---|---|---|"]
    for e in d["evidence"]:
        L.append(f"| {e['source_id']} | {e['source_version']} | {e['section']} | {e['validation_status']} | {e['purpose']} |")
    for run_s in d["evaluation_runs"]:
        run = db.get(EvaluationRun, run_s["id"])
        L += ["", f"## Evaluation {run.id} — {run.candidate_model_id} vs {run.baseline_model_id}", "",
              f"Status **{run.status}**, outcome **{run.outcome}**, policy {run.policy_version}, config {run.evaluation_config_id}, dataset {run.dataset_snapshot_id}.  ",
              f"Candidate digest `{run.candidate_artifact_digest}`"]
        if run.summary:
            s = run.summary
            o = s["overall"]
            L += ["", f"Eligible held-out samples: {s['eligible_total']} of {s['split_total']} (exclusions: {s['exclusions']}).", "",
                  "| Scope | n | Baseline top-1 | Candidate top-1 | Δ pp (95% CI) | Rel. change | Baseline top-3 | Candidate top-3 | Coverage b→c |",
                  "|---|---|---|---|---|---|---|---|---|"]
            def row(name, b):
                ci = b["delta_ci95_pp"]
                return (f"| {name} | {b['baseline']['n_eligible']} | {b['baseline']['top1_correct']} ({b['baseline']['top1_accuracy_pct']}%) | "
                        f"{b['candidate']['top1_correct']} ({b['candidate']['top1_accuracy_pct']}%) | {b['delta']['top1_delta_pp']:+.2f} ({ci[0]:+.2f} to {ci[1]:+.2f}) | "
                        f"{b['delta']['top1_relative_change_pct']:+.2f}% | {b['baseline']['top3_accuracy_pct']}% | {b['candidate']['top3_accuracy_pct']}% | "
                        f"{b['baseline']['coverage_pct']}% → {b['candidate']['coverage_pct']}% |")
            L.append(row("**Overall**", o))
            for c in s["required_cells"]:
                if c in s["cells"]:
                    L.append(row(c + (" (target)" if c == s["target_cell"] else ""), s["cells"][c]))
            L += ["", "| Gate | Rule | Observed | Status | Owner |", "|---|---|---|---|---|"]
            for g in s["gates"]:
                L.append(f"| {g['gate_id']} | {g['rule']} | {g['observed']} | **{g['status']}** | {g['owner_role']} |")
            L += ["", f"Uncertainty: {s['uncertainty_method']}. Δ is in percentage points; relative change is reported separately."]
    L += ["", "## Reviews and approvals", ""]
    for r in d["reviews"]:
        L.append(f"- Review {r['kind']}: {r['decision']} by {r['reviewer_id']}" + (f" — invalidated: {r['invalidated_reason']}" if r["invalidated_at"] else ""))
    for a in d["approvals"]:
        L.append(f"- Approval {a['kind']}: {a['decision']} by {a['approver_id']}, expires {a['expires_at']}" +
                 (f", used by {a['consumed_by']}" if a["consumed_at"] else "") + (f" — invalidated: {a['invalidated_reason']}" if a["invalidated_at"] else ""))
    for r in d["releases"]:
        L += ["", f"## Release {r['id']} (simulated)", "", f"Model {r['model_id']}, status {r['status']}, stages {r['stages']} (prototype settings)."]
        for h in r["history"]:
            L.append(f"- {h['at']}: {h['event']} {h.get('stage_pct', '')}% by {h['by']}")
    for a in d["alerts"]:
        L += ["", f"### Alert {a['id']} — {a['scope']} ({a['status']})", "", f"Observed: {a['observed']}"]
        if a["investigation"]:
            inv = a["investigation"]
            L += [f"- {f}" for f in inv["findings"]]
            if inv.get("suspected_cause"):
                L.append(f"- Suspected cause: {inv['suspected_cause']['hypothesis']}")
            L += [f"- Caveat: {c}" for c in inv["caveats"]]
    L += ["", "## Limitations", "", "- Synthetic data, fictional brand/policies; tone strata are not an endorsed classification method.",
          "- Gates are illustrative demo rules; label validity and statistical uncertainty require expert review.",
          "- Simulated deployment and monitoring; no customer traffic.", ""]
    return "\n".join(L)


# ---------------------------------------------------------------------------
# Copilot Q&A (deterministic intent routing over persisted state)
# ---------------------------------------------------------------------------

def copilot_answer(db: Session, user: User, change_id: str, text: str) -> dict:
    d = change_detail(db, user, change_id)
    q = text.lower()
    refs: list = []
    if re.search(r"block|why|gate|fail", q):
        runs = [r for r in d["evaluation_runs"] if r["status"] == "SUCCEEDED"]
        gates = d["release_readiness"]["gates"]
        bad = [g for g in gates if g["status"] != "PASS"]
        lines = [f"{g['gate_id']} {g['status']}: {g['observed']}" for g in bad]
        if runs:
            run = db.get(EvaluationRun, runs[-1]["id"])
            lines = [f"{g['gate_id']} {g['status']}: {g['observed']}" for g in run.summary["gates"] if g["status"] != "PASS"] + lines
            refs.append({"record": f"evaluation:{run.id}"})
        ans = ("Current blockers (computed by the policy engine):\n- " + "\n- ".join(dict.fromkeys(lines))) if lines else "No blocking gates are currently computed."
    elif re.search(r"next|what now|todo", q):
        ans = "Next steps: " + "; ".join(f"{s['label']}{'' if s['you_can'] else ' (needs another role)'}" for s in d["next_steps"])
    elif re.search(r"regress|worst|subgroup|cell", q):
        runs = [r for r in d["evaluation_runs"] if r["status"] == "SUCCEEDED"]
        if not runs:
            ans = "No completed evaluation yet."
        else:
            s = db.get(EvaluationRun, runs[-1]["id"]).summary
            worst = sorted(s["cells"].items(), key=lambda kv: kv[1]["delta"]["top1_delta_pp"])[:3]
            ans = "Lowest cell deltas (top-1, pp): " + "; ".join(f"{c} {v['delta']['top1_delta_pp']:+.2f} (n={v['baseline']['n_eligible']})" for c, v in worst) + \
                  f". Overall {s['overall']['delta']['top1_delta_pp']:+.2f} pp."
            refs.append({"record": f"evaluation:{runs[-1]['id']}"})
    elif re.search(r"evidence|source|cite|policy|spec", q):
        terms = re.sub(r"(evidence|source|cite|for|about|what|does|say|the|policy|spec)", " ", q)
        from app.retrieval.knowledge import get_kb
        hits = get_kb().search(terms if terms.strip() else q, user.roles, k=3)
        refs = [{k: h[k] for k in ("source_id", "source_version", "section", "excerpt")} for h in hits]
        ans = "Relevant approved excerpts:\n" + "\n".join(f"- {h['source_id']} v{h['source_version']} {h['section']}: {h['excerpt'][:180]}" for h in hits) if hits else "No approved source found — unknown."
    elif re.search(r"status|state|where", q):
        ans = f"{d['change']['id']} is {d['change']['status']}. Permitted next states: {', '.join(d['allowed_transitions'])}."
    else:
        ans = "I can answer: status, next steps, blockers/gates, worst cells/regressions, and evidence lookups. Actions are taken with the buttons, which enforce permissions server-side."
    from app.models.orm import CopilotMessage
    db.add(CopilotMessage(change_id=change_id, role="user", author=user.id, text=text[:2000]))
    db.add(CopilotMessage(change_id=change_id, role="agent", author="copilot", text=ans + "  [deterministic answer from persisted state]", refs=refs))
    return {"answer": ans, "refs": refs, "mode": "deterministic"}


# ---------------------------------------------------------------------------
# Telemetry and process metrics
# ---------------------------------------------------------------------------

def telemetry(db: Session, user: User, change_id: str | None = None) -> dict:
    q = select(AgentInvocation)
    if change_id:
        get_change(db, user.tenant_id, change_id)
        q = q.where(AgentInvocation.change_id == change_id)
    else:
        ids = db.execute(select(ChangeRequest.id).where(ChangeRequest.tenant_id == user.tenant_id)).scalars().all()
        q = q.where(AgentInvocation.change_id.in_(ids))
    agg: dict = defaultdict(lambda: {"invocations": 0, "errors": 0, "latency_ms": [], "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "tool_calls": 0})
    for i in db.execute(q).scalars():
        a = agg[i.agent]
        a["invocations"] += 1
        a["errors"] += i.status == "ERROR"
        a["latency_ms"].append(i.latency_ms)
        a["input_tokens"] += i.input_tokens or 0
        a["output_tokens"] += i.output_tokens or 0
        a["cost_usd"] += i.cost_usd or 0
        a["tool_calls"] += len(i.tool_calls or [])
    out = {}
    for k, a in agg.items():
        lat = sorted(a.pop("latency_ms"))
        out[k] = {**a, "latency_ms_p50": lat[len(lat) // 2] if lat else None, "latency_ms_max": lat[-1] if lat else None,
                  "cost_usd": round(a["cost_usd"], 6)}
    return {"by_agent": out, "note": "Measured latencies of this deployment. Tokens/cost are zero in deterministic mode (no model calls)."}


def process_metrics(db: Session, user: User) -> dict:
    changes = db.execute(select(ChangeRequest).where(ChangeRequest.tenant_id == user.tenant_id)).scalars().all()
    ids = [c.id for c in changes]
    ev = db.execute(select(AuditEvent).where(AuditEvent.change_id.in_(ids)).order_by(AuditEvent.id)).scalars().all()
    by = defaultdict(list)
    for e in ev:
        by[e.change_id].append(e)
    runs = db.execute(select(EvaluationRun).where(EvaluationRun.change_id.in_(ids))).scalars().all()
    rbs = db.execute(select(RollbackRecord).where(RollbackRecord.change_id.in_(ids))).scalars().all()
    clar = db.execute(select(Clarification).where(Clarification.change_id.in_(ids))).scalars().all()
    appr = db.execute(select(Approval).where(Approval.change_id.in_(ids), Approval.kind == "release")).scalars().all()

    def secs(a, b):
        return round((b - a).total_seconds(), 1)

    to_review = []
    for cid, es in by.items():
        start = es[0].created_at
        hit = next((e for e in es if e.action == "state.transition" and "-> REVIEW_REQUIRED" in e.reason), None)
        if hit:
            to_review.append(secs(start, hit.created_at))
    m = {
        "time_requirement_to_review_s": {"value": to_review, "numerator": "time from change creation to first REVIEW_REQUIRED transition",
                                         "denominator": "per change", "window": "all time", "exclusions": "changes never reaching review", "source": "audit_events"},
        "clarification_cycles": {"value": round(sum(c.cycle for c in clar if c.answer) / max(1, sum(1 for c in clar if c.answer)), 2),
                                 "numerator": "sum of answer cycles", "denominator": "answered clarifications", "window": "all time", "exclusions": "unanswered", "source": "clarifications"},
        "evaluation_time_ms": {"value": [r.duration_ms for r in runs if r.duration_ms], "numerator": "job duration", "denominator": "per succeeded run",
                               "window": "all time", "exclusions": "failed/cancelled", "source": "evaluation_runs"},
        "regressions_caught_before_release": {"value": sum(1 for r in runs if r.outcome == "FAIL" and r.summary and any(g["gate_id"] == "G-NO-REGRESSION" and g["status"] == "FAIL" for g in r.summary["gates"])),
                                              "numerator": "runs failing G-NO-REGRESSION", "denominator": "count", "window": "all time", "exclusions": "none", "source": "evaluation_runs"},
        "rejected_or_inconclusive_releases": {"value": sum(1 for r in runs if r.outcome in ("FAIL", "INCONCLUSIVE")) + sum(1 for a in appr if a.decision == "REJECTED"),
                                              "numerator": "FAIL/INCONCLUSIVE evaluations + rejected release approvals", "denominator": "count", "window": "all time", "exclusions": "none", "source": "evaluation_runs, approvals"},
        "approval_turnaround_s": {"value": [], "numerator": "REVIEW_REQUIRED → release approval", "denominator": "per approval", "window": "all time", "exclusions": "rejected", "source": "audit_events"},
        "rollback_time_ms": {"value": [r.duration_ms for r in rbs if r.duration_ms], "numerator": "approval → simulated rollback completion",
                             "denominator": "per executed rollback", "window": "all time", "exclusions": "failed", "source": "rollback_records"},
        "cost_per_change_usd": {"value": round(sum(i.cost_usd or 0 for i in db.execute(select(AgentInvocation).where(AgentInvocation.change_id.in_(ids))).scalars()) / max(1, len(ids)), 6),
                                "numerator": "sum of recorded LLM cost (dated price config)", "denominator": "changes", "window": "all time",
                                "exclusions": "infrastructure cost not tracked", "source": "agent_invocations"},
    }
    for cid, es in by.items():
        rr = next((e for e in es if "-> REVIEW_REQUIRED" in e.reason), None)
        ap = next((e for e in es if e.action == "release.approve" and e.status == "APPROVED"), None)
        if rr and ap:
            m["approval_turnaround_s"]["value"].append(secs(rr.created_at, ap.created_at))
    return {"metrics": m, "evidence_class": "synthetic demo records",
            "note": "These measure this prototype's own records. Faster simulated execution does not prove engineering time savings; value estimates need validated change volume, effort and costs."}
