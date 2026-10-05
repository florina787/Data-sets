"""Deterministic (non-agent) workflow nodes: gates, simulation, deployment, monitoring.

These nodes deliberately contain no LLM: they are the parts of the system where an LLM
must NOT be used (simulation, HITL gates, deployment, numerical anomaly detection).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.claims.rulesets import RULESET_V1, RULESET_V2
from app.defects.generator import generate_defect, sdlc_feedback
from app.monitoring.anomaly import detect_anomalies, primary_anomaly
from app.monitoring.metrics import kpis, top_denial_reasons
from app.monitoring.production import RELEASE_DATE, simulate_production
from app.qa.test_generator import run_test_cases
from app.requirements.analyzer import change_spec_for, ruleset_from_requirement
from app.simulation.runner import run_simulation

if TYPE_CHECKING:  # pragma: no cover
    from app.services.platform import ClaimForgePlatform


class DeterministicNodes:
    def __init__(self, platform: "ClaimForgePlatform") -> None:
        self.p = platform

    # ------------------------------------------------------------------ SDLC gates
    def policy_qa(self, state: dict) -> dict:
        return {"policy": self.p.agents["policy"].search(state["request_text"]), "status": "COMPLETED"}

    def ambiguity_check(self, state: dict) -> dict:
        req = state["requirement"]
        blocking = req.blocking_ambiguities
        return {"ambiguity": {
            "blocking": bool(blocking),
            "blocking_ids": [a.ambiguity_id for a in blocking],
            "questions": [{"id": a.ambiguity_id, "question": a.question, "options": a.options, "severity": a.severity.value}
                          for a in blocking],
            "resolved": [a.ambiguity_id for a in req.ambiguities if a.resolution],
            "method": "DETERMINISTIC gate: CRITICAL unresolved ambiguity ⇒ human clarification",
        }}

    def human_review(self, state: dict) -> dict:
        self.p.audit.record("human_review_gate", "clarification_requested", state.get("request_id"),
                            ambiguities=state["ambiguity"]["blocking_ids"])
        return {"status": "NEEDS_CLARIFICATION"}

    def simulation(self, state: dict) -> dict:
        req = state["requirement"]
        proposed = ruleset_from_requirement(req)
        run = run_simulation(RULESET_V1, proposed, change_spec_for(req), n_claims=state.get("n_claims") or self.p.settings.default_claim_count,
                             seed=state.get("seed", self.p.settings.random_seed),
                             annual_claim_volume=self.p.settings.annual_claim_volume)
        artifacts = dict(state.get("artifacts") or {})
        artifacts["simulation_merged"] = run.merged
        artifacts["proposed_ruleset"] = proposed
        return {"simulation": run.result, "artifacts": artifacts}

    def return_evidence(self, state: dict) -> dict:
        ra = state["release_assessment"]
        return {"status": f"RELEASE_{ra['decision'].replace(' ', '_')}"}

    def human_approval(self, state: dict) -> dict:
        appr = state.get("approval")
        risk = state["release_risk"]
        if not appr:
            return {"status": "AWAITING_APPROVAL",
                    "release": {"gate": "HUMAN APPROVAL REQUIRED", "required_approvals": risk.required_approvals,
                                "decision": risk.decision.value}}
        self.p.audit.record(f"human:{appr['approver']}", f"release_{appr['decision'].lower()}", state.get("request_id"),
                            role=appr.get("role"))
        self.p.approvals.append({**appr, "request_id": state.get("request_id"),
                                 "requirement_id": state["requirement"].requirement_id,
                                 "ts": datetime.now(timezone.utc).isoformat()})
        if appr["decision"] != "APPROVED":
            return {"status": "RELEASE_REJECTED", "release": {"gate": "REJECTED BY HUMAN", "approval": appr}}
        return {"release": {"gate": "APPROVED BY HUMAN", "approval": appr}}

    def simulated_release(self, state: dict) -> dict:
        appr = state["approval"]
        token = hashlib.sha256(f"{appr['approver']}|{state.get('request_id')}".encode()).hexdigest()[:16]
        proposed = state.get("artifacts", {}).get("proposed_ruleset") or RULESET_V2
        record = self.p.deploy_release_tool(approval_token=token, approver=appr["approver"], proposed=proposed,
                                            inject_defect=state.get("inject_defect", True),
                                            requirement_id=state["requirement"].requirement_id)
        return {"release": {**state.get("release", {}), **record}}

    # ------------------------------------------------------------------ ClaimIQ
    def claimiq_monitoring(self, state: dict) -> dict:
        # Uses the release deployed in this session, else a pre-seeded SIMULATED release-2.4 history.
        prod = self.p.current_production or self.p.seed_demo_production(inject_defect=state.get("inject_defect", True))
        artifacts = dict(state.get("artifacts") or {})
        artifacts["production"] = prod
        return {"artifacts": artifacts, "production": {"kpis": kpis(prod), "top_denial_reasons": top_denial_reasons(prod),
                                                        "label": prod.meta["label"]}}

    def anomaly_check(self, state: dict) -> dict:
        prod = state["artifacts"]["production"]
        s = self.p.settings
        anomalies = detect_anomalies(prod, rel_threshold=s.anomaly_relative_threshold, z_threshold=s.anomaly_z_threshold)
        primary = primary_anomaly(anomalies)
        if primary:
            g = self.p.trace_graph
            g.add_node(primary.anomaly_id, "anomaly", primary.summary)
            metric_node = "METRIC-PHYSIO-AUTH-DENIAL-RATE" if primary.metric == "auth_denial_rate" else "METRIC-PHYSIO-DENIAL-RATE"
            if metric_node in g.nodes and primary.segment.get("benefit_type") == "PHYSIOTHERAPY":
                g.link(metric_node, primary.anomaly_id, "breached")
        return {"anomaly": {"detected": primary is not None, "primary": primary, "anomalies": anomalies,
                            "thresholds": {"relative": s.anomaly_relative_threshold, "z": s.anomaly_z_threshold},
                            "method": "STATISTICAL (no LLM)"}}

    def healthy(self, state: dict) -> dict:
        return {"status": "HEALTHY"}

    def release_correlation(self, state: dict) -> dict:
        rc = state["root_cause"]
        g = self.p.trace_graph
        metric = "METRIC-PHYSIO-AUTH-DENIAL-RATE"
        rel_id = f"REL-{rc.correlated_release}" if rc.correlated_release else None
        upstream = {n["id"] for n in g.upstream(metric)} if metric in g.nodes else set()
        chain = [metric, rel_id, rc.changed_rule, rc.source_requirement, rc.policy_section]
        checks = {
            "release_upstream_of_metric": rel_id in upstream,
            "rule_upstream_of_metric": rc.changed_rule in upstream,
            "requirement_upstream_of_metric": rc.source_requirement in upstream,
            "policy_upstream_of_metric": rc.policy_section in upstream,
            "rule_in_release_manifest": any(r["version"] == rc.correlated_release and rc.changed_rule in r["changed_rules"]
                                            for r in self.p.releases["releases"]),
        }
        return {"release_correlation": {"chain": [c for c in chain if c], "checks": checks, "consistent": all(checks.values()),
                                        "path_requirement_to_metric": self._req_path(g, rc, metric),
                                        "method": "DETERMINISTIC traceability-graph verification"}}

    @staticmethod
    def _req_path(g, rc, metric: str) -> list[str]:
        if rc.source_requirement not in g.nodes or rc.changed_rule not in g.nodes:
            return []
        head = g.path(rc.source_requirement, rc.changed_rule)
        tail = g.path(rc.changed_rule, metric)
        return head + tail[1:] if head and tail else []

    def qa_regression(self, state: dict) -> dict:
        rem = state["remediation"]
        prod = state["artifacts"]["production"]
        from app.claims.rulesets import RULESET_V2_1
        fixed = run_test_cases([rem.regression_test], RULESET_V2_1)[0]
        deployed = run_test_cases([rem.regression_test], prod.deployed_ruleset)[0]
        g = self.p.trace_graph
        tc = rem.regression_test
        if tc.test_id not in g.nodes:
            g.add_node(tc.test_id, "test", tc.title, source="production failure")
        g.link("AUTH_RULE_184", tc.test_id, "verified_by")
        return {"regression": {"test": tc, "passes_on_fix": fixed.passed, "fails_on_deployed_build": not deployed.passed,
                               "code": rem.regression_test_code}}

    def defect(self, state: dict) -> dict:
        rc, rem = state["root_cause"], state["remediation"]
        seq = 1042 + len(self.p.defects)
        d = generate_defect(rc, rem, sequence=seq)
        self.p.defects[d.key] = d
        g = self.p.trace_graph
        primary = state["anomaly"]["primary"]
        g.add_node(d.linked_incident, "incident", "ClaimIQ: physiotherapy authorization denial anomaly")
        g.add_node(d.key, "defect", d.title, severity=d.severity.value)
        if primary and primary.anomaly_id in g.nodes:
            g.link(primary.anomaly_id, d.linked_incident, "raised")
        g.link("METRIC-PHYSIO-AUTH-DENIAL-RATE", d.linked_incident, "triggered")
        g.link(d.linked_incident, d.key, "root_caused_as")
        if d.regression_test_id in g.nodes:
            g.link(d.key, d.regression_test_id, "verified_by")
        return {"defect": d}

    def sdlc_feedback(self, state: dict) -> dict:
        d = state["defect"]
        fb = sdlc_feedback(state["root_cause"], state["remediation"], d)
        g = self.p.trace_graph
        if d.source_requirement in g.nodes:
            g.link(d.key, d.source_requirement, "feeds_back_to")
        return {"feedback": fb, "status": "CLOSED_LOOP_COMPLETE"}

    # ------------------------------------------------------------------ finalize
    def finalize(self, state: dict) -> dict:
        status = state.get("status")
        if not status:
            status = f"STOPPED_AFTER_{state['stop_after'].upper()}" if state.get("stop_after") else "COMPLETED"
        return {"status": status}


__all__ = ["DeterministicNodes", "RELEASE_DATE", "simulate_production"]
