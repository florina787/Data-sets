"""Model deployment strategy (where the model runs)."""

from __future__ import annotations

from app.models.enums import PUBLIC_CLOUDS, ArchitectureOption, Deployment, Industry
from app.models.inputs import AssessmentRequest
from app.models.outputs import Decision, ModelDeploymentOption, ModelDeploymentStrategy

A = ArchitectureOption


def assess_model_deployment(req: AssessmentRequest, decision: Decision) -> ModelDeploymentStrategy:
    org, dp = req.organization, req.data_profile
    patterns = set(decision.ai_patterns)
    deploy = set(req.current_architecture.deployment)
    cloud = bool(deploy & (PUBLIC_CLOUDS | {Deployment.HYBRID_CLOUD, Deployment.MULTI_CLOUD}))
    on_prem_only = not cloud
    llm = bool(patterns & {A.GENERATIVE_AI, A.RAG_GENAI, A.AGENTIC_AI})
    strict = dp.privileged or (dp.data_residency_required and org.industry in {Industry.BANKING, Industry.LEGAL})

    if not patterns:
        return ModelDeploymentStrategy(recommended="Not applicable — no model required", rationale=["No AI component recommended."], options=[])
    if not llm:
        return ModelDeploymentStrategy(
            recommended="Classical ML served on the existing platform",
            rationale=["Traditional ML models are small; serve them as containers on the existing platform or a managed ML endpoint."],
            options=[ModelDeploymentOption(option="Existing platform model serving", suitable=True, rationale="No LLM required.")],
        )

    options = [
        ModelDeploymentOption(option="Commercial LLM API", suitable=not strict and not dp.data_residency_required,
                              rationale="Best quality/time-to-value; requires acceptable data-processing terms and egress."),
        ModelDeploymentOption(option="Managed cloud model (in your cloud tenancy)", suitable=cloud and not dp.privileged,
                              rationale="Inference inside existing cloud contracts, identity and private networking."),
        ModelDeploymentOption(option="Self-hosted open-weight model", suitable=org.gpu_available,
                              rationale="Full control; requires GPUs and MLOps; quality may trail frontier models."),
        ModelDeploymentOption(option="On-prem inference", suitable=org.gpu_available and (on_prem_only or strict),
                              rationale="Strongest residency/confidentiality; highest operational burden."),
        ModelDeploymentOption(option="Hybrid model strategy", suitable=True,
                              rationale="Route sensitive or high-volume calls to private/self-hosted models; others to managed models."),
    ]
    rationale: list[str] = []
    if strict and org.gpu_available:
        rec = "On-prem / self-hosted open-weight inference (hybrid fallback only after legal approval)"
        rationale.append("Privileged or residency-restricted data with GPU capacity available → keep inference on-premises.")
    elif strict and cloud:
        rec = "Managed cloud model in an approved region within your tenancy"
        rationale.append("Residency requirements met through regional, private-networked managed inference.")
    elif strict:
        rec = "Hybrid: start with a private, region-pinned managed endpoint under strict contractual terms, or procure on-prem GPUs"
        rationale.append("Data is highly sensitive but no GPU capacity exists — a decision for legal/security; do not default to a public API.")
    elif cloud:
        rec = "Managed cloud model (in your tenancy) with smaller-model routing"
        rationale.append("Existing cloud footprint provides identity, networking and contracts.")
    else:
        rec = "Commercial LLM API via the existing API gateway, or self-hosted if GPUs are available"
        rationale.append("No cloud footprint; choose based on data terms and GPU availability.")
    if req.cost_inputs.requests_per_month > 1_000_000:
        rationale.append("High volume: evaluate self-hosted models for high-volume routes to control cost.")
    rationale.append("Abstract the provider behind an AI gateway so models can be swapped or routed without code changes.")
    return ModelDeploymentStrategy(recommended=rec, rationale=rationale, options=options)
