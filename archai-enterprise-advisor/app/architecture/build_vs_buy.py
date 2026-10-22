"""Build vs buy assessment. Custom LangGraph systems are never the default."""

from __future__ import annotations

from app.models.enums import PUBLIC_CLOUDS, ArchitectureOption, Deployment, SourcingDecision
from app.models.inputs import AssessmentRequest
from app.models.outputs import BuildVsBuyAssessment, Decision, ScoreCard, SourcingOption

A = ArchitectureOption


def assess_build_vs_buy(req: AssessmentRequest, decision: Decision, scores: ScoreCard) -> BuildVsBuyAssessment:
    org, dp = req.organization, req.data_profile
    patterns = set(decision.ai_patterns)
    infra = scores.infrastructure_readiness.value
    cloud = bool(set(req.current_architecture.deployment) & (PUBLIC_CLOUDS | {Deployment.HYBRID_CLOUD, Deployment.MULTI_CLOUD}))
    sensitive = dp.privileged or dp.data_residency_required or dp.contains_financial_data
    mature = org.ai_maturity >= 3 and infra >= 60

    if not patterns:
        return BuildVsBuyAssessment(
            decision=SourcingDecision.KEEP,
            summary="KEEP the existing solution — no AI procurement or build is justified.",
            options=[
                SourcingOption(option="Keep existing solution", fit_score=95, rationale="Meets requirements deterministically."),
                SourcingOption(option="Build internally (AI)", fit_score=5, rationale="Adds cost and risk without benefit."),
                SourcingOption(option="Commercial SaaS (AI)", fit_score=5, rationale="No AI capability needed."),
            ],
            reasoning=["The recommended architecture contains no AI component."],
        )

    integration_heavy = A.AGENTIC_AI in patterns or req.use_case.cross_system_interaction >= 4
    commodity = patterns <= {A.GENERATIVE_AI, A.RAG_GENAI} and req.use_case.cross_system_interaction <= 2

    def score(base: float, *adj: tuple[bool, float]) -> float:
        return max(0.0, min(100.0, base + sum(v for cond, v in adj if cond)))

    options = [
        SourcingOption(option="Keep existing solution", fit_score=score(20, (scores.ai_suitability.value < 50, 20)),
                       rationale="Existing systems are retained as authoritative regardless; alone they do not meet the new need."),
        SourcingOption(option="Build internally", fit_score=score(35, (mature, 25), (integration_heavy, 20), (not mature, -20), (commodity, -10)),
                       rationale="Custom orchestration fits proprietary integrations but needs AI engineering maturity."),
        SourcingOption(option="Managed AI platform", fit_score=score(45, (cloud, 15), (not mature, 10), (sensitive and not cloud, -20)),
                       rationale="Managed retrieval/orchestration reduces operational burden."),
        SourcingOption(option="Cloud-managed AI (models in your tenancy)", fit_score=score(45, (cloud, 25), (dp.privileged and not cloud, -30)),
                       rationale="Keeps data within existing cloud contracts, identity and networking."),
        SourcingOption(option="Open-source platform (self-operated)", fit_score=score(30, (org.gpu_available, 20), (mature, 15), (sensitive, 10), (not mature, -15)),
                       rationale="Maximum control and residency; highest operational burden."),
        SourcingOption(option="Commercial SaaS", fit_score=score(40, (commodity, 20), (sensitive, -25), (integration_heavy, -20)),
                       rationale="Fastest for commodity use cases; limited control over data and integration."),
        SourcingOption(option="Hybrid (buy platform/model, build thin integration)", fit_score=score(55, (integration_heavy, 15), (sensitive, 10), (mature, 5)),
                       rationale="Buy undifferentiated capabilities; build only the integration with existing systems."),
    ]
    options.sort(key=lambda o: o.fit_score, reverse=True)
    top = options[0].option
    if top.startswith("Hybrid"):
        decision_value = SourcingDecision.HYBRID
    elif top.startswith("Build") or top.startswith("Open-source"):
        decision_value = SourcingDecision.BUILD
    elif top.startswith("Keep"):
        decision_value = SourcingDecision.KEEP
    else:
        decision_value = SourcingDecision.BUY

    reasoning = [f"Highest fit: {top} ({options[0].fit_score:.0f}/100)."]
    if A.AGENTIC_AI in patterns:
        reasoning.append("Build only a thin LangGraph orchestration layer around existing APIs; buy model access and observability.")
    if A.TRADITIONAL_ML in patterns:
        reasoning.append("Use the existing data platform / managed ML services before building bespoke ML infrastructure.")
    if sensitive:
        reasoning.append("Data sensitivity favours options that keep data in your tenancy or on-premises.")
    if not mature:
        reasoning.append(f"AI maturity {org.ai_maturity}/5 and platform readiness {infra:.0f}/100 argue against large custom builds.")
    return BuildVsBuyAssessment(
        decision=decision_value,
        summary=f"{decision_value.value}: {top}.",
        options=options,
        reasoning=reasoning,
    )
