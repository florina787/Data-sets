"""LangGraph assessment workflow.

    START → Discovery → Current-State Architecture → Data Readiness → Use-Case
    → Deterministic Decision Engine → {Traditional | ML | GenAI | RAG | Agentic}
    → Hybrid composition → Security & Governance → Resilience → Build-vs-Buy
    → Cost / ROI → Target Architecture → Challenger
        ├─(FAIL and revisions < MAX)→ Decision Engine (pattern excluded)
        └─→ Migration Roadmap → ADR → Final Report → END

Every node is deterministic Python. The only optional LLM use is the final
report narration in LIVE mode. The challenger loop is bounded by
``MAX_REVISIONS`` (enforced with :class:`AgentBudget`) *and* LangGraph's
``recursion_limit``.
"""

from __future__ import annotations

import operator
from collections.abc import Callable
from functools import lru_cache
from typing import Annotated, Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.adr.generator import build_adr
from app.agents.challenger import challenge
from app.agents.discovery import discover
from app.agents.explainer import facts_for, template_summary
from app.architecture import patterns as pattern_designs
from app.architecture.build_vs_buy import assess_build_vs_buy
from app.architecture.matrix import build_matrix
from app.architecture.model_deployment import assess_model_deployment
from app.architecture.target import build_target_architecture
from app.cost.engine import calculate_cost
from app.data_readiness.assessment import assess_data_readiness
from app.decision_engine.engine import decide
from app.decision_engine.scoring import compute_scores, finalize, roi_score
from app.decision_engine.use_case import assess_use_case
from app.evaluation.framework import build_evaluation_plan
from app.governance.assessment import assess_security
from app.infrastructure.assessment import assess_infrastructure
from app.llm.provider import Narrator, TemplateNarrator
from app.models.enums import REGULATED_INDUSTRIES, ArchitectureOption
from app.models.inputs import AssessmentRequest
from app.models.outputs import Decision
from app.observability.tracing import Tracer
from app.resilience.assessment import assess_resilience
from app.roadmap.roadmap import build_roadmap
from app.roi.engine import calculate_roi
from app.security.agent_guardrails import AgentBudget, GuardrailConfig, IterationLimitExceeded

A = ArchitectureOption
MAX_REVISIONS = 3
RECURSION_LIMIT = 80
REVISION_GUARDRAILS = GuardrailConfig(max_iterations=MAX_REVISIONS, max_total_tokens=0, timeout_seconds=30.0)


class AssessmentState(TypedDict, total=False):
    request: AssessmentRequest
    discovery: Any
    infrastructure: Any
    data_readiness: Any
    use_case_assessment: Any
    scores: Any
    decision: Decision
    security: Any
    resilience: Any
    build_vs_buy: Any
    model_deployment: Any
    cost: Any
    roi: Any
    matrix: Any
    target_architecture: Any
    challenger: Any
    roadmap: Any
    evaluation: Any
    adr: Any
    executive_summary: str
    explanation_source: str
    excluded: list[ArchitectureOption]
    exclusion_reason: str
    revisions: int
    revision_budget: AgentBudget
    workflow_path: Annotated[list[str], operator.add]


def _tracer(config: RunnableConfig | None) -> Tracer | None:
    return ((config or {}).get("configurable") or {}).get("tracer")


def _node(name: str, agent: str) -> Callable[[Callable[[AssessmentState], dict]], Callable[..., dict]]:
    """Wrap a node with tracing and workflow-path recording."""

    def wrap(fn: Callable[[AssessmentState], dict]) -> Callable[..., dict]:
        def run(state: AssessmentState, config: RunnableConfig) -> dict:
            tracer = _tracer(config)
            if tracer is None:
                out = fn(state)
            else:
                with tracer.span(name, agent):
                    out = fn(state)
            return {**out, "workflow_path": [name]}

        run.__name__ = name
        return run

    return wrap


# ----------------------------------------------------------------- nodes
@_node("discovery", "Discovery Agent")
def discovery_node(state: AssessmentState) -> dict:
    return {"discovery": discover(state["request"])}


@_node("current_state_architecture", "Infrastructure Assessment")
def infrastructure_node(state: AssessmentState) -> dict:
    return {"infrastructure": assess_infrastructure(state["request"].current_architecture)}


@_node("data_readiness", "Data Readiness Assessment")
def data_node(state: AssessmentState) -> dict:
    req = state["request"]
    return {"data_readiness": assess_data_readiness(req.data_profile, req.current_architecture)}


@_node("use_case_assessment", "AI Suitability Assessment")
def use_case_node(state: AssessmentState) -> dict:
    return {"use_case_assessment": assess_use_case(state["request"])}


@_node("decision_engine", "Deterministic Decision Engine")
def decision_node(state: AssessmentState) -> dict:
    req = state["request"]
    scores = compute_scores(req)
    decision = decide(
        req,
        scores,
        rag_data_ready=state["data_readiness"].rag_prerequisites_met,
        excluded=set(state.get("excluded", [])),
        exclusion_reason=state.get("exclusion_reason", ""),
    )
    return {"scores": scores, "decision": decision}


def _pattern_node(name: str, agent: str) -> Callable[..., dict]:
    @_node(name, agent)
    def node(state: AssessmentState) -> dict:
        decision = state["decision"].model_copy(deep=True)
        decision.pattern_design = pattern_designs.design_for(state["request"], decision)
        return {"decision": decision}

    return node


traditional_node = _pattern_node("traditional_pattern", "Traditional Software Designer")
ml_node = _pattern_node("ml_pattern", "ML Pattern Designer")
genai_node = _pattern_node("genai_pattern", "GenAI Pattern Designer")
rag_node = _pattern_node("rag_pattern", "RAG Pattern Designer")
agentic_node = _pattern_node("agentic_pattern", "Agentic Readiness Agent")


def route_pattern(state: AssessmentState) -> str:
    patterns = state["decision"].ai_patterns
    if not patterns:
        return "traditional_pattern"
    return {
        A.AGENTIC_AI: "agentic_pattern",
        A.RAG_GENAI: "rag_pattern",
        A.GENERATIVE_AI: "genai_pattern",
        A.TRADITIONAL_ML: "ml_pattern",
    }[patterns[0]]


@_node("hybrid_composition", "Hybrid Composer")
def hybrid_node(state: AssessmentState) -> dict:
    decision = state["decision"].model_copy(deep=True)
    if decision.pattern_design is not None and decision.ai_recommended and decision.authoritative_systems:
        decision.pattern_design.design_notes.append(
            "Hybrid contract: " + ", ".join(decision.authoritative_systems[:3]) + " remain the source of truth; AI reads via APIs and never writes directly."
        )
    return {"decision": decision}


@_node("security_governance", "Security & Governance Agent")
def security_node(state: AssessmentState) -> dict:
    return {"security": assess_security(state["request"], state["decision"], state["scores"])}


@_node("resilience", "Resilience Assessor")
def resilience_node(state: AssessmentState) -> dict:
    return {"resilience": assess_resilience(state["request"], state["decision"])}


@_node("build_vs_buy", "Build-vs-Buy Assessor")
def build_vs_buy_node(state: AssessmentState) -> dict:
    req, decision = state["request"], state["decision"]
    return {
        "build_vs_buy": assess_build_vs_buy(req, decision, state["scores"]),
        "model_deployment": assess_model_deployment(req, decision),
    }


def _counterfactual_pattern(state: AssessmentState) -> ArchitectureOption:
    """When AI is rejected, evaluate the business case of the most plausible AI option anyway."""
    excluded = state.get("excluded", [])
    if excluded:
        order = [A.AGENTIC_AI, A.RAG_GENAI, A.GENERATIVE_AI, A.TRADITIONAL_ML]
        return next(p for p in order if p in excluded)
    cands = state["decision"].candidate_scores
    return ArchitectureOption(max(cands, key=lambda k: cands[k]))


@_node("cost_roi", "Cost Optimization & ROI")
def cost_roi_node(state: AssessmentState) -> dict:
    req, decision = state["request"], state["decision"]
    regulated = req.organization.industry in REGULATED_INDUSTRIES
    cost = calculate_cost(req.cost_inputs, decision.primary_architecture, decision.ai_patterns, regulated=regulated, review_mandatory=decision.human_review_mandatory)
    if decision.ai_recommended:
        incremental = cost.model_cost_month + cost.infrastructure_cost_month + cost.human_review_cost_month
        roi = calculate_roi(req.roi_inputs, incremental * 12)
    else:
        cf = _counterfactual_pattern(state)
        cf_cost = calculate_cost(req.cost_inputs, cf, [cf], regulated=regulated, include_comparison=False)
        incremental = cf_cost.model_cost_month + cf_cost.infrastructure_cost_month + cf_cost.human_review_cost_month
        roi = calculate_roi(req.roi_inputs, incremental * 12)
        roi.notes.insert(0, f"Counterfactual business case for the rejected '{cf.value}' option (not recommended).")
    scores = state["scores"].model_copy(deep=True)
    scores.roi_business_value = roi_score(roi)
    return {"cost": cost, "roi": roi, "scores": finalize(scores)}


@_node("target_architecture", "Architecture Generator")
def target_node(state: AssessmentState) -> dict:
    req, decision = state["request"], state["decision"]
    matrix = build_matrix(req, decision)
    return {"matrix": matrix, "target_architecture": build_target_architecture(req, decision, matrix)}


@_node("challenger", "Challenger / Validation Agent")
def challenger_node(state: AssessmentState) -> dict:
    result = challenge(state["request"], state["decision"], state["scores"], state["roi"])
    result.revisions_applied = state.get("revisions", 0)
    update: dict[str, Any] = {"challenger": result}
    if result.requires_revision:
        budget = state.get("revision_budget") or AgentBudget(REVISION_GUARDRAILS)
        try:
            budget.step()
        except IterationLimitExceeded:
            result.requires_revision = False
            result.final_verdict = f"Revision limit ({MAX_REVISIONS}) reached — conservative fallback retained."
            return {"challenger": result, "revision_budget": budget}
        excluded = sorted(set(state.get("excluded", [])) | set(result.exclude_patterns), key=lambda o: o.value)
        update.update({"excluded": excluded, "exclusion_reason": result.revision_reason, "revisions": state.get("revisions", 0) + 1, "revision_budget": budget})
    return update


def route_after_challenger(state: AssessmentState) -> str:
    result = state["challenger"]
    if result.requires_revision and state.get("revisions", 0) <= MAX_REVISIONS:
        return "decision_engine"
    return "migration_roadmap"


@_node("migration_roadmap", "Roadmap Planner")
def roadmap_node(state: AssessmentState) -> dict:
    req, decision = state["request"], state["decision"]
    challenger = state["challenger"]
    if state.get("revisions", 0) and not challenger.requires_revision:
        challenger = challenger.model_copy(update={"revisions_applied": state.get("revisions", 0)})
        if challenger.final_verdict == "Recommendation upheld":
            challenger.final_verdict = f"Recommendation upheld after {state['revisions']} revision(s): {state.get('exclusion_reason', '')}"
    return {
        "roadmap": build_roadmap(req, decision, state["roi"]),
        "evaluation": build_evaluation_plan(req, decision),
        "challenger": challenger,
    }


def _adr(state: AssessmentState, request_id: str) -> Any:
    return build_adr(
        state["request"],
        discovery=state["discovery"],
        decision=state["decision"],
        scores=state["scores"],
        security=state["security"],
        cost=state["cost"],
        roi=state["roi"],
        matrix=state["matrix"],
        challenger=state["challenger"],
        roadmap=state["roadmap"],
        evaluation=state["evaluation"],
        build_vs_buy=state["build_vs_buy"],
        model_deployment=state["model_deployment"],
        request_id=request_id,
    )


def build_graph(narrator: Narrator | None = None) -> Any:
    """Compile the assessment graph. ``narrator`` is used only by the final node."""
    narrator = narrator or TemplateNarrator()
    g: StateGraph = StateGraph(AssessmentState)

    def adr_node(state: AssessmentState, config: RunnableConfig) -> dict:
        tracer = _tracer(config)
        rid = tracer.request_id if tracer else ""
        if tracer:
            with tracer.span("adr", "ADR Writer"):
                adr = _adr(state, rid)
        else:
            adr = _adr(state, rid)
        return {"adr": adr, "workflow_path": ["adr"]}

    def report_node(state: AssessmentState, config: RunnableConfig) -> dict:
        tracer = _tracer(config)
        req = state["request"]

        def make() -> dict:
            args = (state["decision"], state["scores"], state["cost"], state["roi"], req.organization.name)
            text = template_summary(*args)
            narrated = narrator.narrate(facts_for(*args), text, tracer)
            source = narrator.source if narrated != text else TemplateNarrator.source
            return {"executive_summary": narrated, "explanation_source": source}

        if tracer:
            with tracer.span("final_report", "Report Narrator"):
                out = make()
        else:
            out = make()
        return {**out, "workflow_path": ["final_report"]}

    for name, fn in [
        ("discovery", discovery_node),
        ("current_state_architecture", infrastructure_node),
        ("data_readiness", data_node),
        ("use_case_assessment", use_case_node),
        ("decision_engine", decision_node),
        ("traditional_pattern", traditional_node),
        ("ml_pattern", ml_node),
        ("genai_pattern", genai_node),
        ("rag_pattern", rag_node),
        ("agentic_pattern", agentic_node),
        ("hybrid_composition", hybrid_node),
        ("security_governance", security_node),
        ("resilience", resilience_node),
        ("build_vs_buy", build_vs_buy_node),
        ("cost_roi", cost_roi_node),
        ("target_architecture", target_node),
        ("challenger", challenger_node),
        ("migration_roadmap", roadmap_node),
        ("adr", adr_node),
        ("final_report", report_node),
    ]:
        g.add_node(name, fn)

    g.add_edge(START, "discovery")
    g.add_edge("discovery", "current_state_architecture")
    g.add_edge("current_state_architecture", "data_readiness")
    g.add_edge("data_readiness", "use_case_assessment")
    g.add_edge("use_case_assessment", "decision_engine")
    g.add_conditional_edges(
        "decision_engine",
        route_pattern,
        ["traditional_pattern", "ml_pattern", "genai_pattern", "rag_pattern", "agentic_pattern"],
    )
    for p in ["traditional_pattern", "ml_pattern", "genai_pattern", "rag_pattern", "agentic_pattern"]:
        g.add_edge(p, "hybrid_composition")
    g.add_edge("hybrid_composition", "security_governance")
    g.add_edge("security_governance", "resilience")
    g.add_edge("resilience", "build_vs_buy")
    g.add_edge("build_vs_buy", "cost_roi")
    g.add_edge("cost_roi", "target_architecture")
    g.add_edge("target_architecture", "challenger")
    g.add_conditional_edges("challenger", route_after_challenger, ["decision_engine", "migration_roadmap"])
    g.add_edge("migration_roadmap", "adr")
    g.add_edge("adr", "final_report")
    g.add_edge("final_report", END)
    return g.compile()


@lru_cache(maxsize=1)
def default_graph() -> Any:
    """Compiled graph with the deterministic template narrator (DEMO mode)."""
    return build_graph(TemplateNarrator())


def graph_mermaid() -> str:
    """Mermaid rendering of the workflow graph itself (for docs/UI)."""
    return default_graph().get_graph().draw_mermaid()


def run_graph(request: AssessmentRequest, tracer: Tracer, narrator: Narrator | None = None) -> AssessmentState:
    graph = default_graph() if narrator is None or isinstance(narrator, TemplateNarrator) else build_graph(narrator)
    state: AssessmentState = {"request": request, "excluded": [], "revisions": 0, "workflow_path": []}
    return graph.invoke(state, config={"configurable": {"tracer": tracer}, "recursion_limit": RECURSION_LIMIT})


__all__ = ["MAX_REVISIONS", "RECURSION_LIMIT", "build_graph", "default_graph", "graph_mermaid", "run_graph"]
