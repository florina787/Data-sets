"""ClaimForge platform facade — the single shared service layer for API and UI.

Both FastAPI routes and the Streamlit UI call these methods, so business logic is never
duplicated. State (approvals, deployments, defects, traceability) is in-memory for the
demo; adapters for real systems are defined in app/integrations (not connected).
"""

from __future__ import annotations

import json
import threading
from datetime import date
from typing import Any

from app.agents.architecture_agent import ArchitectureAgent
from app.agents.base import AgentContext
from app.agents.developer_agent import DeveloperAgent
from app.agents.governance_agent import GovernanceAgent
from app.agents.impact_agent import ImpactAgent
from app.agents.policy_agent import PolicyAgent
from app.agents.qa_agent import QAAgent
from app.agents.release_agent import ReleaseAgent
from app.agents.remediation_agent import RemediationAgent
from app.agents.requirement_agent import RequirementAgent
from app.agents.root_cause_agent import RootCauseAgent
from app.agents.security_agent import SecurityAgent
from app.agents.supervisor import SupervisorAgent
from app.architecture.analyzer import recommend
from app.catalog.use_cases import USE_CASES
from app.claims.adjudicator import adjudicate_claim
from app.claims.rulesets import RULESET_V2, RULESETS, RuleSet, diff_rulesets, get_ruleset
from app.config.settings import SYNTHETIC_BANNER, SYNTHETIC_DATA_DIR, Settings, get_settings
from app.copilot.narrative import persona_summary
from app.graph.nodes import DeterministicNodes
from app.graph.workflow import build_workflow, workflow_mermaid
from app.impact.analyzer import analyze_impact, impact_tree
from app.llm.client import LLMClient
from app.models.domain import Approval, Claim, ClaimContext
from app.monitoring import metrics as M
from app.monitoring.anomaly import detect_anomalies, primary_anomaly
from app.monitoring.production import RELEASE_DATE, ProductionContext, simulate_production
from app.observability.audit import AuditLog, MetricsRegistry, Tracer, new_request_id
from app.policies.knowledge_base import PolicyKnowledgeBase
from app.policies.retrieval import BM25Retriever
from app.qa.test_generator import generate_test_cases, run_test_cases, summarize
from app.requirements.analyzer import (
    DEMO_CLARIFICATIONS,
    DEMO_REQUIREMENT,
    analyze_requirement_text,
    change_spec_for,
    load_requirement_catalog,
    ruleset_from_requirement,
)
from app.rootcause import tools as rct
from app.security.sanitizer import validate_upload
from app.simulation.generator import ALLOWED_CLAIM_COUNTS
from app.simulation.runner import cached_dataset, run_simulation
from app.tools.registry import ToolRegistry, ToolSpec
from app.traceability.graph import build_base_graph
from app.utils.serialize import to_jsonable


class ClaimForgePlatform:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.audit = AuditLog()
        self.metrics = MetricsRegistry()
        self.tracer = Tracer()
        self.llm = LLMClient(self.settings)
        self.kb = PolicyKnowledgeBase.from_directory()
        self.retriever = BM25Retriever(self.kb)
        self.requirements_catalog = load_requirement_catalog()
        self.releases = json.loads((SYNTHETIC_DATA_DIR / "releases" / "releases.json").read_text(encoding="utf-8"))
        self.trace_graph = build_base_graph(self.requirements_catalog, self.releases, self.kb)
        self.tools = ToolRegistry(self.audit)
        self._register_tools()
        self.ctx = AgentContext(settings=self.settings, llm=self.llm, tools=self.tools, audit=self.audit,
                                metrics=self.metrics, kb=self.kb, retriever=self.retriever,
                                trace_graph=self.trace_graph, releases=self.releases,
                                requirements_catalog=self.requirements_catalog)
        self.agents = {a.name: a for a in (
            SupervisorAgent(self.ctx), RequirementAgent(self.ctx), PolicyAgent(self.ctx), ImpactAgent(self.ctx),
            ArchitectureAgent(self.ctx), DeveloperAgent(self.ctx), QAAgent(self.ctx), SecurityAgent(self.ctx),
            GovernanceAgent(self.ctx), ReleaseAgent(self.ctx), RootCauseAgent(self.ctx), RemediationAgent(self.ctx))}
        self.nodes = DeterministicNodes(self)
        self.graph = build_workflow(self)
        self.approvals: list[dict] = []
        self.deployments: list[dict] = []
        self.defects: dict[str, Any] = {}
        self.current_production: ProductionContext | None = None
        self.last_state: dict | None = None
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ tools
    def _register_tools(self) -> None:
        rc = frozenset({"root_cause"})
        for name, fn, desc in (
            ("segment_metrics", rct.segment_metrics, "Find the anomalous benefit segment"),
            ("denial_reason_shift", rct.denial_reason_shift, "Observed vs expected denial reasons"),
            ("correlate_release", rct.correlate_release, "Change-point vs release + release manifest"),
            ("trace_rule_to_requirement", rct.trace_rule_to_requirement, "Traceability: rule → requirement/policy"),
            ("inspect_affected_claims", rct.inspect_affected_claims, "Claim-level pattern analysis"),
            ("run_regression_suite", rct.run_regression_suite, "Run requirement suite against deployed build"),
            ("check_operational_health", rct.check_operational_health, "Rule exceptions / latency pre vs post"),
        ):
            self.tools.register(ToolSpec(name=name, func=fn, allowed_agents=rc, description=desc))
        # Consequential tool: NOT allow-listed for any agent; requires a human approval token.
        self.tools.register(ToolSpec(name="deploy_release", func=self._deploy, allowed_agents=frozenset(),
                                     consequential=True, description="SIMULATED deployment of an approved release"))

    def deploy_release_tool(self, *, approval_token: str, approver: str, proposed: RuleSet, inject_defect: bool,
                            requirement_id: str) -> dict:
        from app.tools.registry import ToolBudget
        return self.tools.call("release_gate", "deploy_release", ToolBudget(1, 30), approval_token=approval_token,
                               approver=approver, proposed=proposed, inject_defect=inject_defect,
                               requirement_id=requirement_id)

    def _deploy(self, *, approver: str, proposed: RuleSet, inject_defect: bool, requirement_id: str) -> dict:
        prod = simulate_production(self.settings.default_claim_count, self.settings.random_seed + 1000,
                                   inject_defect=inject_defect, approved=proposed)
        with self._lock:
            self.current_production = prod
            record = {"release_id": "REL-2.4", "version": prod.release_version, "status": "DEPLOYED (SIMULATED)",
                      "deployed_on": prod.release_date.isoformat(), "approved_by": approver,
                      "requirement_id": requirement_id, "approved_ruleset": proposed.ruleset_id,
                      "deployed_ruleset": prod.deployed_ruleset.ruleset_id,
                      "controlled_defect_injected": prod.defect_injected and prod.deployed_ruleset.synthetic_defect,
                      "note": ("CONTROLLED SYNTHETIC DEFECT INJECTED at deployment for the ClaimIQ demo "
                               "(visit counter includes CANCELLED visits)." if prod.deployed_ruleset.synthetic_defect
                               else "Deployed exactly as approved."),
                      "label": "SIMULATED DEPLOYMENT — no real system changed"}
            self.deployments.append(record)
        return record

    def seed_demo_production(self, inject_defect: bool = True) -> ProductionContext:
        """Pre-seeded SIMULATED release-2.4 history so ClaimIQ works standalone."""
        with self._lock:
            if self.current_production is None:
                self.current_production = simulate_production(self.settings.default_claim_count,
                                                              self.settings.random_seed + 1000,
                                                              inject_defect=inject_defect, approved=RULESET_V2)
                self.deployments.append({"release_id": "REL-2.4", "version": "2.4", "status": "DEPLOYED (SIMULATED, PRE-SEEDED)",
                                         "deployed_on": RELEASE_DATE.isoformat(), "approved_by": "seeded demo history",
                                         "deployed_ruleset": self.current_production.deployed_ruleset.ruleset_id,
                                         "controlled_defect_injected": inject_defect})
            return self.current_production

    def reset_production(self) -> None:
        with self._lock:
            self.current_production = None

    # ------------------------------------------------------------------ workflow
    def run_workflow(self, request_text: str = DEMO_REQUIREMENT, *, persona: str = "Business Analyst",
                     clarifications: dict | None = None, approval: dict | Approval | None = None,
                     stop_after: str | None = None, inject_defect: bool = True, n_claims: int | None = None,
                     seed: int | None = None, workflow: str | None = None,
                     max_agent_iterations: int | None = None) -> dict:
        if isinstance(approval, Approval):
            approval = approval.model_dump()
        n = n_claims or self.settings.default_claim_count
        if n > self.settings.max_claim_count:
            raise ValueError(f"n_claims exceeds MAX_CLAIM_COUNT={self.settings.max_claim_count}")
        state = {"request_id": new_request_id(), "request_text": request_text, "persona": persona,
                 "clarifications": clarifications or {}, "approval": approval, "stop_after": stop_after,
                 "inject_defect": inject_defect, "n_claims": n, "seed": self.settings.random_seed if seed is None else seed,
                 "workflow": workflow, "max_agent_iterations": max_agent_iterations, "step_count": 0,
                 "agent_calls": {}, "artifacts": {}, "trace": [], "errors": []}
        self.metrics.inc("workflow.runs")
        self.audit.record(f"persona:{persona}", "workflow_start", state["request_id"], workflow=workflow or "auto")
        final = self.graph.invoke(state, {"recursion_limit": self.settings.max_workflow_steps + 10})
        final["summary"] = persona_summary(final, persona, self.llm)
        final["observability"] = {
            "request_id": final["request_id"], "persona": persona, "workflow": final.get("workflow"),
            "agents_invoked": [t["node"] for t in final.get("trace", []) if t["kind"] == "AGENT"],
            "node_order": [t["node"] for t in final.get("trace", [])],
            "total_latency_ms": round(sum(t["latency_ms"] for t in final.get("trace", [])), 1),
            "paid_llm_calls": self.llm.paid_calls, "llm_mode": self.llm.mode,
            "errors": final.get("errors", []),
        }
        self.tracer.export(final["observability"])
        self.audit.record("supervisor", "workflow_end", final["request_id"], status=final.get("status"))
        with self._lock:
            self.last_state = final
        return final

    # ------------------------------------------------------------------ individual capabilities
    def analyze_requirement(self, text: str, clarifications: dict | None = None):
        return analyze_requirement_text(text, clarifications or {})

    def search_policy(self, query: str, top_k: int = 5) -> dict:
        return self.agents["policy"].search(query, top_k)

    def upload_policy(self, filename: str, content: bytes) -> dict:
        text = validate_upload(filename, content, self.settings.max_upload_bytes)
        report = self.kb.add_text(text, filename.rsplit(".", 1)[0], trusted=False)
        self.retriever.reindex()
        self.audit.record("user", "policy_upload", None, doc_id=report["doc_id"],
                          quarantined=len(report["quarantined_lines"]))
        return report

    def analyze_impact(self, text: str, clarifications: dict | None = None) -> dict:
        req = self.analyze_requirement(text, clarifications)
        res = analyze_impact(req)
        res["tree"] = impact_tree(req.requirement_id, res["impacts"])
        return res

    def recommend_architecture(self, text: str) -> dict:
        return recommend(self.analyze_impact(text)["impacts"])

    def generate_tests(self, text: str, clarifications: dict | None = None, ruleset_id: str | None = None) -> dict:
        req = self.analyze_requirement(text, clarifications)
        cases = generate_test_cases(req)
        rs = get_ruleset(ruleset_id) if ruleset_id else ruleset_from_requirement(req)
        results = run_test_cases(cases, rs)
        return {"requirement_id": req.requirement_id, "ruleset": rs.ruleset_id, "cases": cases, "results": results,
                "summary": summarize(results)}

    def generate_claims(self, n_claims: int, seed: int | None = None, sample: int = 20) -> dict:
        if n_claims not in ALLOWED_CLAIM_COUNTS:
            raise ValueError(f"n_claims must be one of {ALLOWED_CLAIM_COUNTS}")
        ds = cached_dataset(n_claims, self.settings.random_seed if seed is None else seed)
        head = ds.claims.head(sample).copy()
        head["service_date"] = head.service_date.astype(str)
        return {"summary": ds.summary(), "sample": head.drop(columns=["service_day"]).to_dict(orient="records"),
                "label": SYNTHETIC_BANNER}

    def adjudicate(self, claim: Claim, context: ClaimContext, ruleset_id: str = "RULESET_V2"):
        return adjudicate_claim(claim, context, get_ruleset(ruleset_id))

    def run_simulation(self, text: str | None = None, clarifications: dict | None = None, *,
                       current_ruleset_id: str = "RULESET_V1", proposed_ruleset_id: str | None = None,
                       n_claims: int | None = None, seed: int | None = None):
        req = self.analyze_requirement(text or DEMO_REQUIREMENT, clarifications if clarifications is not None else DEMO_CLARIFICATIONS)
        proposed = get_ruleset(proposed_ruleset_id) if proposed_ruleset_id else ruleset_from_requirement(req)
        n = n_claims or self.settings.default_claim_count
        if n not in ALLOWED_CLAIM_COUNTS:
            raise ValueError(f"n_claims must be one of {ALLOWED_CLAIM_COUNTS}")
        return run_simulation(get_ruleset(current_ruleset_id), proposed, change_spec_for(req), n_claims=n,
                              seed=self.settings.random_seed if seed is None else seed,
                              annual_claim_volume=self.settings.annual_claim_volume)

    def claimiq_metrics(self, since_release: bool = True) -> dict:
        prod = self.current_production or self.seed_demo_production()
        trend = M.denial_trend(prod)
        trend["week"] = trend.week.astype(str)
        return {"kpis": M.kpis(prod, since_release), "denial_trend_physiotherapy": trend.to_dict(orient="records"),
                "top_denial_reasons": M.top_denial_reasons(prod, since_release),
                "segments": {k: M.segment(prod, k, since_release) for k in M.SEGMENTS},
                "deployments": self.deployments, "label": prod.meta["label"]}

    def detect_anomaly(self, rel_threshold: float | None = None, z_threshold: float | None = None,
                       baseline_mode: str = "RELEASE_PROJECTION") -> dict:
        prod = self.current_production or self.seed_demo_production()
        anomalies = detect_anomalies(prod, rel_threshold=rel_threshold if rel_threshold is not None else self.settings.anomaly_relative_threshold,
                                     z_threshold=z_threshold if z_threshold is not None else self.settings.anomaly_z_threshold,
                                     baseline_mode=baseline_mode)
        return {"anomalies": anomalies, "primary": primary_anomaly(anomalies), "baseline_mode": baseline_mode}

    def investigate(self, max_agent_iterations: int | None = None, persona: str = "Claims Analyst") -> dict:
        return self.run_workflow("Investigate the production anomaly in claim denials (ClaimIQ).", persona=persona,
                                 workflow="CLAIMIQ_INVESTIGATION", max_agent_iterations=max_agent_iterations)

    def traceability(self, node_id: str) -> dict:
        if node_id not in self.trace_graph.nodes:
            raise KeyError(node_id)
        out = self.trace_graph.trace(node_id)
        out["mermaid"] = self.trace_graph.to_mermaid(node_id)
        return out

    def ruleset_info(self) -> dict:
        return {"rulesets": {k: v.to_dict() for k, v in RULESETS.items()},
                "diff_v1_v2": diff_rulesets(RULESETS["RULESET_V1"], RULESETS["RULESET_V2"]),
                "diff_v2_defective": diff_rulesets(RULESETS["RULESET_V2"], RULESETS["RULESET_V2_DEFECTIVE"])}

    def use_cases(self) -> list[dict]:
        return [uc.copy() for uc in USE_CASES]

    def system_metrics(self) -> dict:
        snap = self.metrics.snapshot()
        snap.update({"paid_llm_calls": self.llm.paid_calls, "llm_mode": self.llm.mode, "settings": self.settings.public_dict(),
                     "approvals": len(self.approvals), "deployments": len(self.deployments), "defects": len(self.defects),
                     "trace_nodes": len(self.trace_graph.nodes), "trace_edges": len(self.trace_graph.edges),
                     "tools": self.tools.describe(), "audit_tail": self.audit.entries(25)})
        return snap

    def workflow_diagram(self) -> str:
        return workflow_mermaid(self.graph)

    @staticmethod
    def jsonable(obj: Any) -> Any:
        return to_jsonable(obj)


_PLATFORM: ClaimForgePlatform | None = None
_PLATFORM_LOCK = threading.Lock()


def get_platform() -> ClaimForgePlatform:
    global _PLATFORM
    with _PLATFORM_LOCK:
        if _PLATFORM is None:
            _PLATFORM = ClaimForgePlatform()
        return _PLATFORM


__all__ = ["ClaimForgePlatform", "get_platform", "date"]
