"""Deterministic architecture decision engine.

The engine applies explicit rules over the scorecard. Order of precedence:

1. Hard rules (deterministic workload, deterministic-only actions, replacement
   of working deterministic components) — these can reject AI outright.
2. Suitability thresholds and gates per pattern (ML, GenAI, RAG, Agentic).
3. Simplicity: when agents are not required, the simplest qualifying pattern wins.
4. Hybrid composition when existing deterministic systems must stay authoritative.
5. Autonomy caps (human-in-the-loop) from risk.

LLMs never participate in this module.
"""

from __future__ import annotations

from app.config.logging_config import get_logger
from app.decision_engine import weights as W
from app.decision_engine.scoring import agentic_gate, is_deterministic_workload
from app.governance.autonomy import action_policies, determine_autonomy
from app.models.enums import (
    AGENTIC_VERDICT_LABELS,
    ARCHITECTURE_LABELS,
    AUTONOMY_LABELS,
    DETERMINISTIC_ONLY_ACTIONS,
    HIGH_RISK_WRITE_ACTIONS,
    REGULATED_INDUSTRIES,
    AgenticVerdict,
    ArchitectureOption,
    ArchitectureStyle,
    AutonomyLevel,
    DataStore,
    Industry,
    TaskType,
)
from app.models.inputs import AssessmentRequest
from app.models.outputs import Decision, RejectedAlternative, ScoreCard

logger = get_logger("decision_engine")

A = ArchitectureOption
_RECORD_STORES = {
    DataStore.ORACLE: "Oracle",
    DataStore.POSTGRESQL: "PostgreSQL",
    DataStore.SQL_SERVER: "SQL Server",
    DataStore.MYSQL: "MySQL",
    DataStore.MONGODB: "MongoDB",
}
_SHORT = {A.TRADITIONAL_ML: "ML", A.GENERATIVE_AI: "GenAI", A.RAG_GENAI: "RAG", A.AGENTIC_AI: "Constrained Agents"}


def authoritative_systems(req: AssessmentRequest) -> list[str]:
    """Existing systems of record that must remain the source of truth."""
    arch = req.current_architecture
    systems = list(arch.existing_systems)
    if ArchitectureStyle.MICROSERVICES in arch.styles:
        systems.append("Existing microservices")
    elif ArchitectureStyle.MONOLITH in arch.styles:
        systems.append("Existing core application (monolith)")
    systems += [f"{name} (system of record)" for ds, name in _RECORD_STORES.items() if ds in arch.data_stores]
    return systems


def _qualifying_patterns(
    req: AssessmentRequest, scores: ScoreCard, rag_data_ready: bool, notes: list[str]
) -> dict[ArchitectureOption, float]:
    uc = req.use_case
    q: dict[ArchitectureOption, float] = {}
    if scores.ml_suitability.value >= W.ML_MIN:
        q[A.TRADITIONAL_ML] = scores.ml_suitability.value
    if scores.genai_suitability.value >= W.GENAI_MIN:
        q[A.GENERATIVE_AI] = scores.genai_suitability.value
    rag_needs_generation = uc.generation_requirement >= 2 or TaskType.KNOWLEDGE_SEARCH in uc.primary_tasks
    if scores.rag_suitability.value >= W.RAG_MIN and rag_needs_generation:
        if rag_data_ready:
            q[A.RAG_GENAI] = scores.rag_suitability.value
        else:
            notes.append(
                "R-RAG-DATA: RAG need exists but data readiness prerequisites are unmet — remediate content "
                "quality/permissions first; RAG deferred."
            )
    gate_met, _ = agentic_gate(req)
    if scores.agentic_readiness.value >= W.AGENTIC_MIN and gate_met and not is_deterministic_workload(req):
        q[A.AGENTIC_AI] = scores.agentic_readiness.value
    return q


def decide(
    req: AssessmentRequest,
    scores: ScoreCard,
    *,
    rag_data_ready: bool = True,
    excluded: set[ArchitectureOption] | frozenset[ArchitectureOption] = frozenset(),
    exclusion_reason: str = "",
) -> Decision:
    """Produce the architecture decision for a request and its scorecard."""
    uc, org = req.use_case, req.organization
    actions = set(uc.action_types)
    rules: list[str] = []
    rationale: list[str] = []
    deterministic = is_deterministic_workload(req)
    forbidden = actions & DETERMINISTIC_ONLY_ACTIONS
    gate_met, signals = agentic_gate(req)
    authoritative = authoritative_systems(req)

    qualifying = _qualifying_patterns(req, scores, rag_data_ready, rules)
    for option in list(qualifying):
        if option in excluded:
            del qualifying[option]
            rules.append(f"R-CHAL-01: {option.value} excluded on challenger revision — {exclusion_reason or 'see challenger'}.")

    # ------------------------------------------------------------ hard rules
    no_ai_reason = ""
    if deterministic:
        no_ai_reason = (
            "The workload is deterministic and governed by explicit rules; AI adds nondeterminism, "
            "hallucination risk, latency, cost and governance burden without incremental value."
        )
        rules.append("R-DET-01: deterministic, rules-governed workload → no AI component.")
    elif scores.ai_suitability.value < W.AI_SUITABILITY_MIN:
        no_ai_reason = f"AI suitability {scores.ai_suitability.value:.0f} is below the {W.AI_SUITABILITY_MIN:.0f} threshold."
        rules.append("R-AI-01: AI suitability below threshold → no AI component.")
    elif not qualifying:
        no_ai_reason = "No AI pattern met its suitability threshold and gates."
        if excluded:
            no_ai_reason += f" Remaining patterns were excluded: {exclusion_reason}."
        rules.append("R-AI-02: no qualifying AI pattern → no AI component.")
    if forbidden:
        rules.append(
            "R-FORBID-01: deterministic-only actions ("
            + ", ".join(sorted(a.value for a in forbidden))
            + ") remain with existing deterministic systems."
        )
    if uc.replaces_existing_component and (deterministic or forbidden):
        rules.append(f"R-REPL-01: request to replace '{uc.replaces_existing_component}' with AI rejected.")

    # ------------------------------------------------------------ patterns
    patterns: list[ArchitectureOption] = []
    if not no_ai_reason:
        if A.AGENTIC_AI in qualifying:
            patterns.append(A.AGENTIC_AI)
            if A.RAG_GENAI in qualifying:
                patterns.append(A.RAG_GENAI)
        elif A.RAG_GENAI in qualifying:
            patterns.append(A.RAG_GENAI)
        elif A.GENERATIVE_AI in qualifying:
            patterns.append(A.GENERATIVE_AI)
        if A.TRADITIONAL_ML in qualifying:
            if patterns and qualifying[A.TRADITIONAL_ML] >= max(qualifying[p] for p in patterns):
                patterns.insert(0, A.TRADITIONAL_ML)
            else:
                patterns.append(A.TRADITIONAL_ML)
        rules.append("R-SIMPLE-01: simplest qualifying pattern(s) selected: " + ", ".join(p.value for p in patterns))

    # ------------------------------------------------------------ primary
    if not patterns:
        has_existing = bool(uc.replaces_existing_component or uc.current_solution or req.current_architecture.existing_systems)
        primary = A.KEEP_EXISTING if has_existing else A.TRADITIONAL_SOFTWARE
        rationale.append(no_ai_reason)
        if primary is A.KEEP_EXISTING:
            target = uc.replaces_existing_component or (req.current_architecture.existing_systems or ["current solution"])[0]
            rationale.append(f"Keep the existing {target}: it is working, deterministic and auditable.")
            label = f"Keep Existing {target}"
        else:
            rationale.append("Implement with deterministic software (rules/workflow engine, APIs, reporting).")
            label = "Traditional deterministic software (rules / workflow engine)"
    else:
        families = {A.TRADITIONAL_ML} & set(patterns), set(patterns) - {A.TRADITIONAL_ML}
        multi_family = all(families)
        deterministic_core = uc.deterministic_requirement >= 3 and bool(authoritative)
        cross_system_lookup = (
            uc.cross_system_interaction >= 3 and A.AGENTIC_AI not in patterns and bool(req.current_architecture.existing_systems)
        )
        hybrid = multi_family or deterministic_core or bool(forbidden) or cross_system_lookup
        if hybrid:
            primary = A.HYBRID
            why = []
            if deterministic_core:
                why.append("a deterministic core must remain authoritative")
            if forbidden:
                why.append("deterministic-only actions stay with existing systems")
            if cross_system_lookup:
                why.append("authoritative facts come from existing system APIs, AI adds knowledge on top")
            if multi_family:
                why.append("both predictive ML and generative capabilities are needed")
            rules.append("R-HYB-01: hybrid deterministic + AI — " + "; ".join(why) + ".")
        else:
            primary = patterns[0]
        label = _label(req, primary, patterns, authoritative, scores)
        for p in patterns:
            rationale.append(_pattern_reason(p, scores))
        rationale.append(
            "Existing deterministic systems remain authoritative; AI is added around them through existing APIs."
            if authoritative
            else "AI is introduced as a bounded capability with clear ownership."
        )

    # ------------------------------------------------------------ agentic verdict
    verdict, agentic_rationale, answer = _agentic_verdict(req, scores, patterns, deterministic, forbidden, gate_met, signals, excluded)
    if verdict is AgenticVerdict.RECOMMENDED:
        label = label.replace("Constrained Agents", "Bounded Agents")  # low-risk: bounded rather than approval-gated

    # ------------------------------------------------------------ autonomy
    level, autonomy_rationale, review = determine_autonomy(req, primary, patterns, scores)
    policies = action_policies(req, level, ai_present=bool(patterns))
    approval = bool(patterns) and (
        bool(actions & HIGH_RISK_WRITE_ACTIONS)
        or review
        or level == AutonomyLevel.APPROVAL_REQUIRED
    )
    if not patterns and actions & HIGH_RISK_WRITE_ACTIONS:
        approval = True  # existing human approval processes stay in place
    citations = A.RAG_GENAI in patterns and (uc.citation_requirement >= 4 or org.industry == Industry.LEGAL)
    if citations:
        rules.append("R-CITE-01: citations mandatory for grounded answers.")

    decision = Decision(
        primary_architecture=primary,
        primary_architecture_label=ARCHITECTURE_LABELS[primary],
        architecture_label=label,
        ai_recommended=bool(patterns),
        ai_verdict_label="AI RECOMMENDED (SCOPED)" if patterns else "DO NOT USE AI",
        ai_patterns=patterns,
        agentic_verdict=verdict,
        agentic_verdict_label=AGENTIC_VERDICT_LABELS[verdict],
        agentic_answer=answer,
        agentic_rationale=agentic_rationale,
        autonomy_level=level,
        autonomy_label=AUTONOMY_LABELS[level],
        autonomy_rationale=autonomy_rationale,
        requires_human_approval=approval,
        human_review_mandatory=review,
        citations_mandatory=citations,
        authoritative_systems=authoritative,
        action_policies=policies,
        rationale=[r for r in rationale if r],
        rejected_alternatives=_rejected(req, scores, primary, patterns, qualifying, no_ai_reason, verdict, agentic_rationale, rag_data_ready, excluded),
        triggered_rules=rules,
        candidate_scores={
            "traditional_ml": scores.ml_suitability.value,
            "generative_ai": scores.genai_suitability.value,
            "rag_genai": scores.rag_suitability.value,
            "agentic_ai": scores.agentic_readiness.value,
        },
        excluded_patterns=sorted(excluded, key=lambda o: o.value),
    )
    logger.debug(
        "decision",
        extra={"extra_fields": {"primary": primary.value, "patterns": [p.value for p in patterns], "agentic": verdict.value, "autonomy": int(level)}},
    )
    return decision


def _label(
    req: AssessmentRequest,
    primary: ArchitectureOption,
    patterns: list[ArchitectureOption],
    authoritative: list[str],
    scores: ScoreCard,
) -> str:
    ai = " + ".join(_SHORT[p] for p in patterns)
    if primary is A.HYBRID:
        anchor = "Microservices" if ArchitectureStyle.MICROSERVICES in req.current_architecture.styles else (
            req.current_architecture.existing_systems[0] if req.current_architecture.existing_systems else "Systems"
        )
        return f"Existing {anchor} (authoritative) + {ai}"
    if primary is A.AGENTIC_AI:
        extra = " + RAG" if A.RAG_GENAI in patterns else ""
        return f"Constrained Agents (LangGraph) around Existing APIs{extra}"
    if primary is A.RAG_GENAI:
        secure = "Secure " if scores.security_risk.value >= 50 else ""
        return f"{secure}RAG + GenAI on Existing Platform"
    if primary is A.GENERATIVE_AI:
        return "Generative AI assistant (bounded, reviewed)"
    if primary is A.TRADITIONAL_ML:
        return "Traditional ML on existing data platform"
    return ARCHITECTURE_LABELS[primary]


def _pattern_reason(p: ArchitectureOption, s: ScoreCard) -> str:
    return {
        A.TRADITIONAL_ML: f"Prediction/classification is central (ML suitability {s.ml_suitability.value:.0f}) — a classical model is cheaper and more explainable than an LLM.",
        A.GENERATIVE_AI: f"Generation/summarization is central (GenAI suitability {s.genai_suitability.value:.0f}).",
        A.RAG_GENAI: f"Answers must be grounded in proprietary, changing documents (RAG suitability {s.rag_suitability.value:.0f}).",
        A.AGENTIC_AI: f"Variable multi-step, cross-system, tool-using workflow (agentic readiness {s.agentic_readiness.value:.0f}).",
    }[p]


def _agentic_verdict(
    req: AssessmentRequest,
    scores: ScoreCard,
    patterns: list[ArchitectureOption],
    deterministic: bool,
    forbidden: set,
    gate_met: bool,
    signals: dict[str, int],
    excluded: set[ArchitectureOption] | frozenset[ArchitectureOption],
) -> tuple[AgenticVerdict, list[str], str]:
    org, uc = req.organization, req.use_case
    reasons: list[str] = []
    if A.AGENTIC_AI in patterns:
        constrained_by = []
        if org.industry in REGULATED_INDUSTRIES:
            constrained_by.append(f"regulated industry ({org.industry.value})")
        if set(uc.action_types) & HIGH_RISK_WRITE_ACTIONS:
            constrained_by.append("high-risk write actions require approval")
        if scores.security_risk.value >= 45:
            constrained_by.append(f"security risk {scores.security_risk.value:.0f}")
        if scores.overall_risk.value >= 50:
            constrained_by.append(f"overall risk {scores.overall_risk.value:.0f}")
        reasons.append(
            f"Agentic need gate met ({sum(v >= W.AGENTIC_GATE_MIN_RATING for v in signals.values())}/{len(signals)} dimensions) "
            f"and readiness {scores.agentic_readiness.value:.0f} ≥ {W.AGENTIC_MIN:.0f}."
        )
        reasons.append("Agents orchestrate existing APIs as tools; they do not replace existing services.")
        if constrained_by:
            reasons.append("Constrained because: " + "; ".join(constrained_by) + ".")
            return (
                AgenticVerdict.CONSTRAINED,
                reasons,
                "Partially. Agents add value for read-only investigation and evidence gathering across systems; "
                "any write/remediation step is prepared by the agent and executed only after human approval.",
            )
        return AgenticVerdict.RECOMMENDED, reasons, "Yes, within a bounded, allow-listed, low-risk workflow."

    if deterministic:
        reasons.append("Workload is deterministic: explicit rules are exact, auditable and cheaper than an agent.")
    if forbidden:
        reasons.append(
            "Deterministic-only actions (" + ", ".join(sorted(a.value for a in forbidden)) + ") must never be decided by an autonomous agent."
        )
    if not gate_met:
        weak = [k for k, v in signals.items() if v < W.AGENTIC_GATE_MIN_RATING]
        reasons.append(f"Agentic need gate unmet — insufficient {', '.join(weak)}. A workflow engine or simple API call suffices.")
    elif scores.agentic_readiness.value < W.AGENTIC_MIN:
        reasons.append(f"Agentic readiness {scores.agentic_readiness.value:.0f} < {W.AGENTIC_MIN:.0f} threshold.")
    if A.AGENTIC_AI in excluded:
        reasons.append("Agentic pattern excluded by challenger validation (complexity not justified).")
    reasons.append("Agents would add nondeterminism, hallucination risk, latency, operational complexity, governance burden and cost.")
    return AgenticVerdict.NOT_RECOMMENDED, reasons, "No. This workload does not require agents."


def _rejected(
    req: AssessmentRequest,
    s: ScoreCard,
    primary: ArchitectureOption,
    patterns: list[ArchitectureOption],
    qualifying: dict[ArchitectureOption, float],
    no_ai_reason: str,
    verdict: AgenticVerdict,
    agentic_rationale: list[str],
    rag_data_ready: bool,
    excluded: set[ArchitectureOption] | frozenset[ArchitectureOption],
) -> list[RejectedAlternative]:
    chosen = set(patterns) | {primary}
    out: list[RejectedAlternative] = []
    for option in A:
        if option in chosen:
            continue
        if option is A.KEEP_EXISTING:
            reason = f"AI adds material value (AI suitability {s.ai_suitability.value:.0f}); existing systems are kept but extended."
        elif option is A.TRADITIONAL_SOFTWARE:
            reason = (
                "Existing solution already provides deterministic processing — keep it rather than rebuild."
                if primary is A.KEEP_EXISTING
                else "Rules alone cannot provide the required generation/prediction/knowledge capability; deterministic components are retained alongside AI."
            )
        elif option is A.TRADITIONAL_ML:
            reason = f"ML suitability {s.ml_suitability.value:.0f} < {W.ML_MIN:.0f}: no primary prediction/classification need."
        elif option is A.GENERATIVE_AI:
            reason = (
                "Ungrounded GenAI is insufficient: answers must be grounded in proprietary documents (RAG chosen)."
                if A.RAG_GENAI in patterns
                else f"GenAI suitability {s.genai_suitability.value:.0f} < {W.GENAI_MIN:.0f}."
            )
        elif option is A.RAG_GENAI:
            if s.rag_suitability.value >= W.RAG_MIN and not rag_data_ready:
                reason = "RAG need exists but data readiness prerequisites are unmet — remediate data first."
            else:
                reason = f"RAG suitability {s.rag_suitability.value:.0f} < {W.RAG_MIN:.0f}: no proprietary-document grounding need (existing tooling is not a reason)."
        elif option is A.AGENTIC_AI:
            reason = " ".join(agentic_rationale[:2])
        else:  # HYBRID
            reason = (
                "No AI component is justified, so there is nothing to hybridize."
                if not patterns
                else "No separate deterministic core needs to run alongside the AI capability for this workflow."
            )
        if option in excluded:
            reason = "Excluded by challenger validation. " + reason
        out.append(RejectedAlternative(option=option, reason=reason))
    return out
