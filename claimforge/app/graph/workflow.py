"""LangGraph workflow: closed-loop SDLC + ClaimIQ production intelligence.

START → supervisor → requirement → policy → ambiguity_check ─(critical)→ human_review → END
      → impact → architecture → developer → qa → simulation → security → governance → release
      ─(BLOCKED / NOT READY)→ return_evidence → END
      → human_approval ─(no approval / rejected)→ END
      → simulated_release → claimiq_monitoring → anomaly_check ─(no)→ healthy → END
      → root_cause → release_correlation → remediation → qa_regression → defect → sdlc_feedback → END

Guards on every node: MAX_WORKFLOW_STEPS (global), MAX_AGENT_ITERATIONS (per node
re-invocation), exception capture, and an optional ``stop_after`` stage.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Callable

from langgraph.graph import END, START, StateGraph

from app.graph.state import TERMINAL_STATUSES, ClaimForgeState

if TYPE_CHECKING:  # pragma: no cover
    from app.services.platform import ClaimForgePlatform

AGENT_NODES = {"supervisor", "requirement", "policy", "impact", "architecture", "developer", "qa", "security",
               "governance", "release", "root_cause", "remediation"}


def _guarded(name: str, fn: Callable[[dict], dict], platform: "ClaimForgePlatform") -> Callable[[dict], dict]:
    settings = platform.settings

    def node(state: dict) -> dict:
        steps = state.get("step_count", 0)
        calls = dict(state.get("agent_calls", {}))
        kind = "AGENT" if name in AGENT_NODES else "DETERMINISTIC"
        if steps >= settings.max_workflow_steps:
            return {"status": "HALTED", "halted_reason": f"MAX_WORKFLOW_STEPS={settings.max_workflow_steps} reached before '{name}'",
                    "trace": [{"node": name, "kind": kind, "status": "SKIPPED_BUDGET", "latency_ms": 0}]}
        if calls.get(name, 0) >= settings.max_agent_iterations:
            return {"status": "HALTED", "halted_reason": f"MAX_AGENT_ITERATIONS={settings.max_agent_iterations} reached for '{name}'",
                    "trace": [{"node": name, "kind": kind, "status": "SKIPPED_BUDGET", "latency_ms": 0}]}
        t0 = time.perf_counter()
        try:
            out = fn(state) or {}
            status = "OK"
        except Exception as exc:  # captured → workflow FAILED with evidence, never silent
            out = {"status": "FAILED", "errors": [f"{name}: {type(exc).__name__}: {exc}"]}
            status = "ERROR"
            platform.audit.record(name, "node_error", state.get("request_id"), error=type(exc).__name__)
        ms = round((time.perf_counter() - t0) * 1000, 1)
        calls[name] = calls.get(name, 0) + 1
        platform.metrics.observe(f"node.{name}", ms)
        out["step_count"] = steps + 1
        out["agent_calls"] = calls
        out["trace"] = [{"node": name, "kind": kind, "status": status, "latency_ms": ms, "order": steps + 1}]
        return out

    return node


def _stop(state: dict, current: str) -> bool:
    return state.get("status") in TERMINAL_STATUSES or state.get("stop_after") == current


def _linear(current: str, nxt: str) -> Callable[[dict], str]:
    def route(state: dict) -> str:
        return "finalize" if _stop(state, current) else nxt
    return route


def build_workflow(platform: "ClaimForgePlatform"):
    a = platform.agents
    n = platform.nodes  # deterministic node implementations
    g = StateGraph(ClaimForgeState)

    nodes: dict[str, Callable[[dict], dict]] = {
        "supervisor": a["supervisor"].invoke,
        "requirement": a["requirement"].invoke,
        "policy": a["policy"].invoke,
        "policy_qa": n.policy_qa,
        "ambiguity_check": n.ambiguity_check,
        "human_review": n.human_review,
        "impact": a["impact"].invoke,
        "architecture": a["architecture"].invoke,
        "developer": a["developer"].invoke,
        "qa": a["qa"].invoke,
        "simulation": n.simulation,
        "security": a["security"].invoke,
        "governance": a["governance"].invoke,
        "release": a["release"].invoke,
        "return_evidence": n.return_evidence,
        "human_approval": n.human_approval,
        "simulated_release": n.simulated_release,
        "claimiq_monitoring": n.claimiq_monitoring,
        "anomaly_check": n.anomaly_check,
        "healthy": n.healthy,
        "root_cause": a["root_cause"].invoke,
        "release_correlation": n.release_correlation,
        "remediation": a["remediation"].invoke,
        "qa_regression": n.qa_regression,
        "defect": n.defect,
        "sdlc_feedback": n.sdlc_feedback,
        "finalize": n.finalize,
    }
    for name, fn in nodes.items():
        g.add_node(name, fn if name == "finalize" else _guarded(name, fn, platform))

    g.add_edge(START, "supervisor")

    def after_supervisor(s: dict) -> str:
        if _stop(s, "supervisor"):
            return "finalize"
        return {"POLICY_QA": "policy_qa", "CLAIMIQ_INVESTIGATION": "claimiq_monitoring"}.get(s.get("workflow"), "requirement")

    g.add_conditional_edges("supervisor", after_supervisor, ["policy_qa", "claimiq_monitoring", "requirement", "finalize"])
    g.add_edge("policy_qa", "finalize")
    g.add_conditional_edges("requirement", _linear("requirement", "policy"), ["policy", "finalize"])
    g.add_conditional_edges("policy", _linear("policy", "ambiguity_check"), ["ambiguity_check", "finalize"])

    def after_ambiguity(s: dict) -> str:
        if s.get("status") in TERMINAL_STATUSES:
            return "finalize"
        if s.get("ambiguity", {}).get("blocking"):
            return "human_review"
        return "finalize" if s.get("stop_after") == "ambiguity_check" else "impact"

    g.add_conditional_edges("ambiguity_check", after_ambiguity, ["human_review", "impact", "finalize"])
    g.add_edge("human_review", "finalize")
    chain = ["impact", "architecture", "developer", "qa", "simulation", "security", "governance", "release"]
    for cur, nxt in zip(chain, chain[1:]):
        g.add_conditional_edges(cur, _linear(cur, nxt), [nxt, "finalize"])

    def after_release(s: dict) -> str:
        if _stop(s, "release"):
            return "finalize"
        decision = s.get("release_assessment", {}).get("decision")
        return "return_evidence" if decision in ("BLOCKED", "NOT READY") else "human_approval"

    g.add_conditional_edges("release", after_release, ["return_evidence", "human_approval", "finalize"])
    g.add_edge("return_evidence", "finalize")

    def after_approval(s: dict) -> str:
        if s.get("status") in TERMINAL_STATUSES or s.get("stop_after") == "human_approval":
            return "finalize"
        appr = s.get("approval") or {}
        return "simulated_release" if appr.get("decision") == "APPROVED" else "finalize"

    g.add_conditional_edges("human_approval", after_approval, ["simulated_release", "finalize"])
    g.add_conditional_edges("simulated_release", _linear("simulated_release", "claimiq_monitoring"), ["claimiq_monitoring", "finalize"])
    g.add_conditional_edges("claimiq_monitoring", _linear("claimiq_monitoring", "anomaly_check"), ["anomaly_check", "finalize"])

    def after_anomaly(s: dict) -> str:
        if _stop(s, "anomaly_check"):
            return "finalize"
        return "root_cause" if s.get("anomaly", {}).get("detected") else "healthy"

    g.add_conditional_edges("anomaly_check", after_anomaly, ["root_cause", "healthy", "finalize"])
    g.add_edge("healthy", "finalize")

    def after_root_cause(s: dict) -> str:
        if _stop(s, "root_cause"):
            return "finalize"
        rc = s.get("root_cause")
        return "release_correlation" if rc is not None and rc.status == "CONCLUDED" else "finalize"

    g.add_conditional_edges("root_cause", after_root_cause, ["release_correlation", "finalize"])
    tail = ["release_correlation", "remediation", "qa_regression", "defect", "sdlc_feedback"]
    for cur, nxt in zip(tail, tail[1:]):
        g.add_conditional_edges(cur, _linear(cur, nxt), [nxt, "finalize"])
    g.add_edge("sdlc_feedback", "finalize")
    g.add_edge("finalize", END)
    return g.compile()


def workflow_mermaid(compiled) -> str:
    try:
        return compiled.get_graph().draw_mermaid()
    except Exception:  # pragma: no cover - drawing is optional
        return ""
