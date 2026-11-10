"""Resilience & disaster-recovery assessment.

Core principle: AI failure must not bring down an existing deterministic
business process. AI is kept off the critical path wherever possible.
"""

from __future__ import annotations

from app.models.enums import ArchitectureOption, Compute, DataStore
from app.models.inputs import AssessmentRequest
from app.models.outputs import Decision, FailureScenario, ResilienceAssessment

A = ArchitectureOption
PRINCIPLE = "AI failure must not unnecessarily bring down an existing deterministic business process."


def assess_resilience(req: AssessmentRequest, decision: Decision) -> ResilienceAssessment:
    patterns = set(decision.ai_patterns)
    uc = req.use_case
    if not patterns:
        return ResilienceAssessment(
            principle=PRINCIPLE,
            ai_on_critical_path=False,
            degradation_chain=["No AI introduced", "Existing deterministic system continues with its current HA/DR posture"],
            failure_scenarios=[],
            patterns={"existing_ha": "Unchanged — no new failure modes introduced."},
            recommendations=["Keep current HA/DR; no AI-specific resilience work required."],
        )

    authoritative = decision.authoritative_systems[0] if decision.authoritative_systems else "existing process"
    on_critical_path = uc.latency_sensitivity >= 5 and uc.transaction_criticality >= 4
    llm = bool(patterns & {A.GENERATIVE_AI, A.RAG_GENAI, A.AGENTIC_AI})
    rag = A.RAG_GENAI in patterns
    agent = A.AGENTIC_AI in patterns

    scenarios: list[FailureScenario] = []
    if llm:
        scenarios.append(FailureScenario(
            failure="LLM provider outage / throttling",
            impact="AI assistance unavailable",
            response="Circuit breaker opens → route to fallback model; if unavailable, disable AI assistance. "
            f"{authoritative} continues operating.",
        ))
    if rag:
        scenarios.append(FailureScenario(
            failure="Vector store / retrieval outage",
            impact="Grounded answers unavailable",
            response="Fall back to existing keyword/enterprise search; never answer ungrounded.",
        ))
    if agent:
        scenarios.append(FailureScenario(
            failure="Tool/API outage during agent run",
            impact="Partial evidence",
            response="Per-tool timeout + circuit breaker; agent reports which evidence is missing; no write attempted.",
        ))
        scenarios.append(FailureScenario(
            failure="Agent exceeds iteration/token budget",
            impact="Incomplete investigation",
            response="Halt, return partial findings with explicit 'incomplete' status, hand off to human.",
        ))
    if A.TRADITIONAL_ML in patterns:
        scenarios.append(FailureScenario(
            failure="Model serving outage or drift",
            impact="Predictions unavailable/degraded",
            response="Serve last good model or rules-based baseline; drift alert triggers retraining review.",
        ))
    scenarios.append(FailureScenario(
        failure="Network partition between AI services and core systems",
        impact="AI cannot reach systems of record",
        response="AI returns 'unavailable'; core systems unaffected because AI is not in their request path.",
    ))

    chain = ["AI fully available"]
    if llm:
        chain += ["Primary model unavailable → fallback model", "All models unavailable → disable AI assistance"]
    if rag:
        chain.insert(1, "Vector store unavailable → keyword search fallback")
    chain.append(f"{authoritative} continues operating (deterministic path unaffected)")

    replicas = "≥2 replicas across zones (Kubernetes/OpenShift HPA + PodDisruptionBudget)" if set(req.current_architecture.compute) & {Compute.KUBERNETES, Compute.OPENSHIFT} else "≥2 instances behind a load balancer"
    recs = [
        "Keep AI off the synchronous critical path of deterministic transactions; integrate asynchronously or as advisory side-calls.",
        f"High availability: {replicas}.",
        "Timeouts on every model/tool call; retries (max 3) with exponential backoff 1s → 2s → 4s.",
        "Circuit breakers per dependency (model provider, vector store, each tool).",
        "Feature flag to disable AI assistance instantly without redeploying core services.",
    ]
    if rag and DataStore.SEARCH_ENGINE in req.current_architecture.data_stores:
        recs.append("Reuse the existing search engine as the retrieval fallback.")
    if on_critical_path:
        recs.append("WARNING: workload is latency- and transaction-critical — AI must remain advisory only.")
    return ResilienceAssessment(
        principle=PRINCIPLE,
        ai_on_critical_path=on_critical_path,
        degradation_chain=chain,
        failure_scenarios=scenarios,
        patterns={
            "timeout": "LLM 30s, tools 10s, retrieval 3s",
            "retries": "max 3, exponential backoff 1s/2s/4s, idempotent operations only",
            "circuit_breaker": "open after 3 consecutive failures, half-open after 60s",
            "fallback_model": "secondary model/provider or smaller model" if llm else "n/a",
            "graceful_degradation": "disable AI assistance; existing process continues",
        },
        recommendations=recs,
    )
