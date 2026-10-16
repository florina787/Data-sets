"""LangGraph workflow for the AI-SDLC "90-Day MRI Wait-Time Challenge".

Separate from the patient workflow. Two human checkpoints use ``interrupt()``:
requirement clarification (stage 3) and release approval (stage 13). Every stage
writes an auditable artifact with a traceability reference.
"""

from __future__ import annotations

import operator
import time
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

from langgraph.errors import GraphBubbleUp
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from app.database.session import session_scope
from app.governance import approvals, audit, builds
from app.harness.core import new_id
from app.models import db as m
from app.sdlc_engine import architecture, monitoring, qa, rca, release, requirements, security_scan, simulation
from app.telemetry import metrics as tm

DEMO_REQUIREMENT = ("A patient has an MRI appointment 90 days away. Patients should be able to find potentially "
                    "earlier MRI appointments within 25 km.")

STAGES = [
    ("business_requirement", "Business requirement", "sdlc_requirements"),
    ("requirements_analysis", "Requirement ambiguity detection", "sdlc_requirements"),
    ("human_clarification", "Human decision", "human"),
    ("architecture", "Architecture", "sdlc_architecture"),
    ("development", "Development", "sdlc_development"),
    ("qa", "QA test generation & execution", "sdlc_qa"),
    ("simulation", "Synthetic simulation", "sdlc_qa"),
    ("defect_injection", "Injected defect (controlled)", "sdlc_release"),
    ("monitoring", "Production monitoring", "sdlc_monitoring"),
    ("root_cause", "Root cause analysis", "sdlc_rca"),
    ("fix", "Fix proposal", "sdlc_development"),
    ("regression", "Regression testing + security validation", "sdlc_qa"),
    ("release_approval", "Release approval", "sdlc_release"),
    ("deployment", "Deployment", "sdlc_release"),
    ("post_release", "Post-release monitoring", "sdlc_monitoring"),
]
STAGE_INDEX = {s[0]: i + 1 for i, s in enumerate(STAGES)}


class SdlcState(BaseModel):
    run_id: str
    requested_by: str
    requirement: str = DEMO_REQUIREMENT
    simulation_volume: int = 200
    target_env: str = "demo-production"
    status: str = "RUNNING"
    analysis: dict = Field(default_factory=dict)
    clarification: dict = Field(default_factory=dict)
    qa_report: dict = Field(default_factory=dict)
    baseline_sim: dict = Field(default_factory=dict)
    production_sim: dict = Field(default_factory=dict)
    anomalies: list[dict] = Field(default_factory=list)
    rca: dict = Field(default_factory=dict)
    fix: dict = Field(default_factory=dict)
    regression: dict = Field(default_factory=dict)
    security: dict = Field(default_factory=dict)
    release: dict = Field(default_factory=dict)
    approval_id: str | None = None
    pending_question: dict | None = None
    deployment: list[dict] = Field(default_factory=list)
    post_release: dict = Field(default_factory=dict)
    monitor_since: float | None = None
    artifacts: Annotated[list[dict], operator.add] = Field(default_factory=list)
    stage_log: Annotated[list[dict], operator.add] = Field(default_factory=list)


def _artifact(st: SdlcState, stage: str, agent: str, prefix: str, content: dict) -> dict:
    ref = f"{prefix}-{st.run_id[-6:].upper()}-{STAGE_INDEX[stage]:02d}"
    aid = new_id("ART")
    with session_scope() as s:
        s.add(m.SdlcArtifact(id=aid, run_id=st.run_id, stage=stage, agent=agent, trace_ref=ref, content=content))
    audit.record("SDLC_ARTIFACT", agent, {"stage": stage, "trace_ref": ref}, st.run_id)
    return {"id": aid, "stage": stage, "agent": agent, "trace_ref": ref, "summary": content.get("summary", "")}


def stage(name: str):
    title, agent = next((t, a) for s, t, a in STAGES if s == name)

    def deco(fn):
        def run(state: SdlcState) -> dict:
            t0 = time.perf_counter()
            try:
                out = fn(state) or {}
                status = out.pop("_status", "completed")
            except GraphBubbleUp:
                raise
            except Exception as e:  # noqa: BLE001
                out, status = {"status": "FAILED", "_summary": f"{type(e).__name__}: {e}"}, "failed"
            summary = out.pop("_summary", "")
            out["stage_log"] = [{"stage": name, "index": STAGE_INDEX[name], "title": title, "agent": agent,
                                 "status": status, "summary": summary,
                                 "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
                                 "at": datetime.now(UTC).isoformat()}]
            tm.AGENT_RUNS.labels(agent=agent, status=status).inc()
            return out
        run.__name__ = name
        return run
    return deco


@stage("business_requirement")
def business_requirement(st: SdlcState):
    rid = requirements.trace_id(st.requirement)
    art = _artifact(st, "business_requirement", "sdlc_requirements", "REQ",
                    {"summary": "Business requirement captured", "requirement": st.requirement, "requirement_id": rid})
    return {"artifacts": [art], "_summary": f"{rid}: {st.requirement}"}


@stage("requirements_analysis")
def requirements_analysis(st: SdlcState):
    a = requirements.analyze(st.requirement)
    art = _artifact(st, "requirements_analysis", "sdlc_requirements", "REQ",
                    {"summary": f"{len(a['user_stories'])} stories, {len(a['ambiguities'])} open questions", **a})
    blocking = [q for q in a["ambiguities"] if q["blocking"]]
    key_q = next((q for q in blocking if q["code"] == "REQUISITION_ELIGIBILITY"), blocking[0] if blocking else None)
    upd = {"analysis": a, "artifacts": [art],
           "_summary": f"Ambiguity detected: {key_q['question']}" if key_q else "No blocking ambiguity"}
    if key_q:
        ap = approvals.create("REQUIREMENT_CLARIFICATION", "sdlc_requirements", key_q["question"],
                              evidence=[{"requirement_id": a["id"], "open_questions": [q["question"] for q in blocking]}],
                              consequences=["Design is blocked until the product owner answers"],
                              payload={"question": key_q["question"], "questions": blocking}, workflow_id=st.run_id,
                              workflow_type="sdlc")
        upd.update(approval_id=ap["id"], status="AWAITING_CLARIFICATION",
                   pending_question={"type": "REQUIREMENT_CLARIFICATION", "approval_id": ap["id"],
                                     "question": key_q["question"], "all_questions": [q["question"] for q in blocking]})
    return upd


@stage("human_clarification")
def human_clarification(st: SdlcState):
    if not st.pending_question:
        return {"_status": "skipped", "_summary": "No clarification needed"}
    ans = interrupt({"type": "REQUIREMENT_CLARIFICATION", "approval_id": st.approval_id})
    text = (ans.get("answer") or "").strip() or ("Only verified appointments from providers meeting the documented "
                                                 "eligibility requirements may be presented as confirmed alternatives.")
    art = _artifact(st, "human_clarification", "human", "REQ",
                    {"summary": "Product owner decision recorded", "question": st.pending_question["question"],
                     "decision": text, "decided_by": ans.get("decided_by")})
    return {"clarification": {"question": st.pending_question["question"], "answer": text,
                              "decided_by": ans.get("decided_by")}, "pending_question": None, "approval_id": None,
            "status": "RUNNING", "artifacts": [art], "_summary": f"Decision: {text}"}


@stage("architecture")
def architecture_stage(st: SdlcState):
    diagrams = architecture.all_diagrams()
    art = _artifact(st, "architecture", "sdlc_architecture", "ARCH",
                    {"summary": f"{len(diagrams)} Mermaid diagrams generated", "diagrams": list(diagrams)})
    return {"artifacts": [art], "_summary": "Component, sequence, data-flow, agent, deployment, security diagrams"}


@stage("development")
def development(st: SdlcState):
    plan = [
        {"component": "Availability adapter", "module": "backend/app/integrations/availability.py", "status": "implemented"},
        {"component": "Eligibility validation", "module": "backend/app/services/eligibility.py", "status": "implemented"},
        {"component": "Distance filtering", "module": "backend/app/services/geo.py", "status": "implemented"},
        {"component": "Verification + ranking", "module": "backend/app/services/verification.py, ranking.py",
         "status": "implemented"},
        {"component": "Recommendation API", "module": "backend/app/api/routes/search.py", "status": "implemented"},
    ]
    art = _artifact(st, "development", "sdlc_development", "CODE",
                    {"summary": "Build 1.4.0 implements the requirement", "build": "1.4.0", "plan": plan,
                     "clarification_applied": st.clarification.get("answer")})
    return {"artifacts": [art], "_summary": "Build 1.4.0: adapter, eligibility, distance, ranking, recommendation API"}


@stage("qa")
def qa_stage(st: SdlcState):
    rep = qa.run_suite("1.4.0")
    art = _artifact(st, "qa", "sdlc_qa", "TEST", {"summary": f"{rep['passed']}/{rep['executed']} passed on 1.4.0",
                                                   "report": rep})
    return {"qa_report": rep, "artifacts": [art],
            "_summary": f"{rep['executed']} scenarios executed on 1.4.0: {rep['passed']} passed, {rep['failed']} failed"}


@stage("simulation")
def simulation_stage(st: SdlcState):
    sim = simulation.simulate(st.simulation_volume, "1.4.0", env="demo-staging", seed=11, emit_telemetry=True)
    art = _artifact(st, "simulation", "sdlc_qa", "TEST", {"summary": "Baseline simulation", "simulation": sim})
    return {"baseline_sim": sim, "artifacts": [art],
            "_summary": f"{sim['searches']} synthetic searches; accuracy {sim['recommendation_accuracy']:.2%}; "
                        f"avg potential days saved {sim['avg_potential_days_saved']}"}


@stage("defect_injection")
def defect_injection(st: SdlcState):
    d = builds.deploy("1.5.0", "demo-production", "sdlc_release(controlled-defect-injection)",
                      approval_id="DEMO-CONTROLLED-DEFECT-INJECTION")
    art = _artifact(st, "defect_injection", "sdlc_release", "CODE",
                    {"summary": "Build 1.5.0 with CONTROLLED DEMONSTRATION DEFECT deployed to demo-production",
                     "deployment": d, "defect": "ADVERTISED -> VERIFIED_AVAILABLE"})
    return {"deployment": [d], "monitor_since": time.time(), "artifacts": [art],
            "_summary": "Controlled defect: recommendation engine marks unverified slots as confirmed (build 1.5.0)"}


@stage("monitoring")
def monitoring_stage(st: SdlcState):
    sim = simulation.simulate(st.simulation_volume, env="demo-production", seed=23, emit_telemetry=True)
    found = monitoring.detect(since=st.monitor_since, labels_filter={"build": sim["build_version"]})
    art = _artifact(st, "monitoring", "sdlc_monitoring", "MON",
                    {"summary": f"{len(found)} anomaly(ies) detected", "anomalies": found, "simulation": sim})
    return {"production_sim": sim, "anomalies": found, "artifacts": [art],
            "_summary": (f"Detected {', '.join(a['rule'] for a in found)}; {sim['unverified_presented_as_confirmed']} "
                         f"unverified slots presented as confirmed") if found else "No anomalies"}


@stage("root_cause")
def root_cause(st: SdlcState):
    an = next((a for a in st.anomalies if a["rule"] == "VERIFICATION_MISCLASSIFICATION"), None)
    res = rca.analyze(an, builds.active_build("demo-production").version, "1.4.0",
                      st.production_sim.get("samples"))
    art = _artifact(st, "root_cause", "sdlc_rca", "MON", {"summary": res["root_cause"] or "Inconclusive", **res})
    return {"rca": res, "artifacts": [art],
            "_summary": ("CONFIRMED: " + res["root_cause"]) if res["confirmed"] else "Root cause not confirmed"}


@stage("fix")
def fix_stage(st: SdlcState):
    f = rca.propose_fix(st.rca.get("suspect_build", "1.5.0"))
    art = _artifact(st, "fix", "sdlc_development", "CODE", {"summary": f["change"], **f})
    return {"fix": f, "artifacts": [art], "_summary": f"Build {f['fixed_build']}: {f['change']}"}


@stage("regression")
def regression(st: SdlcState):
    fixed = st.fix.get("fixed_build", "1.5.1")
    reg_fixed = qa.run_suite(fixed, qa.REGRESSION_IDS)
    reg_bad = qa.run_suite(st.rca.get("suspect_build", "1.5.0"), qa.REGRESSION_IDS)
    full = qa.run_suite(fixed)
    sec = security_scan.run_all()
    sec_brief = {k: sec[k] for k in ("executed_at", "open_findings", "prompt_injection", "authorization")}
    sec_brief["secret_findings"] = len(sec["secret_scan"]["findings"])
    art = _artifact(st, "regression", "sdlc_qa", "TEST",
                    {"summary": f"Regression {reg_fixed['passed']}/{reg_fixed['executed']} on {fixed}; "
                                f"{reg_bad['failed']} fail on {reg_bad['build_version']}",
                     "fixed": reg_fixed, "defective": reg_bad, "full_suite": full, "security": sec_brief})
    return {"regression": {"fixed": reg_fixed, "defective": reg_bad, "full_suite": full}, "security": sec,
            "artifacts": [art],
            "_summary": f"{fixed}: {full['passed']}/{full['executed']} pass; regression {reg_fixed['passed']}/"
                        f"{reg_fixed['executed']}; security open findings {sec['open_findings']}"}


@stage("release_approval")
def release_approval(st: SdlcState):
    fixed = st.fix.get("fixed_build", "1.5.1")
    if not st.release:
        rel = release.prepare(fixed, st.regression["full_suite"], st.regression["fixed"], st.security, st.rca)
    else:
        rel = st.release
    if not rel["ready"]:
        return {"release": rel, "status": "RELEASE_BLOCKED", "_status": "failed",
                "_summary": "Release checklist failed: " + ", ".join(c["item"] for c in rel["checklist"]
                                                                    if not c["passed"])}
    aid = st.approval_id
    if not aid:
        return {"release": rel, "_status": "awaiting_approval", "_summary": "Approval requested"}
    decision = interrupt({"type": "PRODUCTION_DEPLOYMENT", "approval_id": aid})
    ok = decision.get("decision") == "APPROVED"
    art = _artifact(st, "release_approval", "sdlc_release", "REL",
                    {"summary": f"Release {fixed} {decision.get('decision')}", "release": rel,
                     "decided_by": decision.get("decided_by"), "approval_id": aid})
    return {"release": {**rel, "decision": decision.get("decision"), "decided_by": decision.get("decided_by")},
            "pending_question": None, "status": "RUNNING" if ok else "RELEASE_REJECTED", "artifacts": [art],
            "_summary": f"{decision.get('decision')} by {decision.get('decided_by')}"}


@stage("deployment")
def deployment(st: SdlcState):
    fixed = st.release["version"]
    d1 = builds.deploy(fixed, "demo-staging", "sdlc_release", st.approval_id)
    d2 = builds.deploy(fixed, st.target_env, "sdlc_release", st.approval_id)
    release.mark_deployed(fixed, st.target_env, st.release.get("decided_by"))
    art = _artifact(st, "deployment", "sdlc_release", "REL",
                    {"summary": f"{fixed} deployed to demo-staging and {st.target_env} (simulated)", "deployments": [d1, d2]})
    return {"deployment": st.deployment + [d1, d2], "monitor_since": time.time(), "artifacts": [art],
            "_summary": f"{fixed} -> demo-staging, {st.target_env} (simulated in-process deployment)"}


@stage("post_release")
def post_release(st: SdlcState):
    sim = simulation.simulate(st.simulation_volume, env=st.target_env, seed=23, emit_telemetry=True)
    found = monitoring.detect(since=st.monitor_since, labels_filter={"build": sim["build_version"]})
    reg = qa.run_suite(None, qa.REGRESSION_IDS)
    resolved = 0
    if not found and reg["failed"] == 0:
        resolved = monitoring.resolve("VERIFICATION_MISCLASSIFICATION", f"Fixed by {sim['build_version']}") + \
            monitoring.resolve("UNVERIFIED_AS_CONFIRMED", f"Fixed by {sim['build_version']}")
    res = {"simulation": sim, "new_anomalies": found, "regression": reg, "anomalies_resolved": resolved,
           "defect_absent": sim["unverified_presented_as_confirmed"] == 0 and reg["failed"] == 0}
    art = _artifact(st, "post_release", "sdlc_monitoring", "MON",
                    {"summary": "Defect absent in regression dataset" if res["defect_absent"] else "Defect persists",
                     **res})
    return {"post_release": res, "status": "COMPLETED" if res["defect_absent"] else "FAILED", "artifacts": [art],
            "_summary": f"Accuracy {sim['recommendation_accuracy']:.2%}; unverified-as-confirmed "
                        f"{sim['unverified_presented_as_confirmed']}; anomalies resolved {resolved}"}


def _route_release(st: SdlcState):
    if st.status in {"RELEASE_BLOCKED", "RELEASE_REJECTED", "FAILED"}:
        return END
    return "deployment"


def _route_clar(st: SdlcState):
    return END if st.status == "FAILED" else "architecture"


def _request_release_approval(st: SdlcState) -> dict:
    """Create the approval request once, before the interrupting node (keeps resume idempotent)."""
    if st.status == "FAILED" or st.approval_id:
        return {}
    fixed = st.fix.get("fixed_build", "1.5.1")
    rel = release.prepare(fixed, st.regression["full_suite"], st.regression["fixed"], st.security, st.rca)
    if not rel["ready"]:
        return {"release": rel}
    ap = approvals.create(
        "PRODUCTION_DEPLOYMENT", "sdlc_release", f"Deploy build {fixed} (hotfix) to {st.target_env}.",
        evidence=[{"checklist": rel["checklist"]}, {"root_cause": st.rca.get("root_cause")},
                  {"diff": st.fix.get("diff")}],
        consequences=["Patient workflow will use the corrected status mapping",
                      f"Rollback: redeploy {rel['manifest']['previous_production']}"],
        payload={"version": fixed, "environment": st.target_env, "requested_by": st.requested_by},
        workflow_id=st.run_id, workflow_type="sdlc")
    return {"release": rel, "approval_id": ap["id"], "status": "AWAITING_RELEASE_APPROVAL",
            "pending_question": {"type": "PRODUCTION_DEPLOYMENT", "approval_id": ap["id"],
                                 "question": f"Approve deployment of {fixed} to {st.target_env}?"}}


def build_graph() -> StateGraph:
    g = StateGraph(SdlcState)
    nodes = [business_requirement, requirements_analysis, human_clarification, architecture_stage, development,
             qa_stage, simulation_stage, defect_injection, monitoring_stage, root_cause, fix_stage, regression]
    names = [s[0] for s in STAGES]
    for name, fn in zip(names, nodes):
        g.add_node(name, fn)  # type: ignore[call-overload]
    g.add_node("request_release_approval", _request_release_approval)  # type: ignore[call-overload]
    g.add_node("release_approval", release_approval)
    g.add_node("deployment", deployment)
    g.add_node("post_release", post_release)
    g.add_edge(START, "business_requirement")
    g.add_edge("business_requirement", "requirements_analysis")
    g.add_edge("requirements_analysis", "human_clarification")
    g.add_conditional_edges("human_clarification", _route_clar, ["architecture", END])
    chain = ["architecture", "development", "qa", "simulation", "defect_injection", "monitoring", "root_cause",
             "fix", "regression", "request_release_approval", "release_approval"]
    for a, b in zip(chain, chain[1:]):
        g.add_edge(a, b)
    g.add_conditional_edges("release_approval", _route_release, ["deployment", END])
    g.add_edge("deployment", "post_release")
    g.add_edge("post_release", END)
    return g


@lru_cache
def compiled():
    from app.graphs.patient_graph import checkpointer

    return build_graph().compile(checkpointer=checkpointer())


def mermaid() -> str:
    return build_graph().compile().get_graph().draw_mermaid()


def _cfg(run_id: str) -> dict:
    return {"configurable": {"thread_id": f"sdlc:{run_id}"}, "recursion_limit": 50}


def start(requested_by: str, requirement: str | None = None, volume: int = 200) -> dict:
    run_id = new_id("SDLC")
    with session_scope() as s:
        s.add(m.WorkflowExecution(id=run_id, workflow_type="sdlc_demo", user_id=requested_by, status="RUNNING",
                                  build_version=builds.active_build().version, summary={}))
    audit.record("SDLC_RUN_STARTED", requested_by, {"run_id": run_id}, run_id)
    compiled().invoke(SdlcState(run_id=run_id, requested_by=requested_by, requirement=requirement or DEMO_REQUIREMENT,
                                simulation_volume=max(10, min(volume, 2000))), _cfg(run_id))
    return _require(run_id)


def resume(run_id: str, value: dict) -> dict:
    from langgraph.types import Command

    compiled().invoke(Command(resume=value), _cfg(run_id))
    return _require(run_id)


def _require(run_id: str) -> dict:
    r = get(run_id)
    if r is None:
        raise LookupError(run_id)
    return r


def get(run_id: str) -> dict | None:
    snap = compiled().get_state(_cfg(run_id))
    if not snap or not snap.values:
        return None
    v = {**SdlcState(run_id=run_id, requested_by="").model_dump(), **dict(snap.values)}
    v["paused_at"] = list(snap.next) if snap.next else []
    v["stages"] = [{"stage": s, "index": i + 1, "title": t, "agent": a} for i, (s, t, a) in enumerate(STAGES)]
    if not snap.next and v["status"] in {"RUNNING"}:
        v["status"] = "COMPLETED"
    with session_scope() as s:
        row = s.get(m.WorkflowExecution, run_id)
        if row:
            row.status = v["status"]
    return v


def traceability(run_id: str) -> list[dict]:
    with session_scope() as s:
        rows = s.query(m.SdlcArtifact).filter(m.SdlcArtifact.run_id == run_id).order_by(m.SdlcArtifact.created_at).all()
        return [{"trace_ref": r.trace_ref, "stage": r.stage, "agent": r.agent,
                 "summary": (r.content or {}).get("summary"), "created_at": r.created_at.isoformat()} for r in rows]


def artifact(run_id: str, stage_name: str) -> dict | None:
    with session_scope() as s:
        r = s.query(m.SdlcArtifact).filter(m.SdlcArtifact.run_id == run_id, m.SdlcArtifact.stage == stage_name) \
            .order_by(m.SdlcArtifact.created_at.desc()).first()
        return None if r is None else {"trace_ref": r.trace_ref, "stage": r.stage, "agent": r.agent,
                                       "content": r.content, "created_at": r.created_at.isoformat()}
