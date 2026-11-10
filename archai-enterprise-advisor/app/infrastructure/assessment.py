"""Current-state infrastructure assessment.

Produces a deterministic 0–100 Infrastructure Readiness score from what the
enterprise *already has*. A high score means AI services can be hosted on the
existing platform (container orchestration, gateway, identity, CI/CD,
observability) instead of standing up a parallel stack.
"""

from __future__ import annotations

from app.models.enums import (
    CI_CD_TOOLS,
    OBSERVABILITY_TOOLS,
    PUBLIC_CLOUDS,
    ArchitectureStyle,
    Compute,
    Deployment,
    IdentitySecurity,
    Integration,
)
from app.models.inputs import CurrentArchitecture
from app.models.outputs import InfrastructureAssessment, Score, ScoreFactor

#: Maximum points per capability (sums to 100).
INFRA_WEIGHTS: dict[str, float] = {
    "container_platform": 20,
    "service_architecture": 15,
    "api_gateway": 10,
    "identity_and_access": 15,
    "secrets_management": 10,
    "ci_cd": 10,
    "observability": 10,
    "private_networking": 5,
    "integration_fabric": 5,
}

_COMPUTE_CREDIT = {
    Compute.KUBERNETES: 1.0,
    Compute.OPENSHIFT: 1.0,
    Compute.SERVERLESS: 0.6,
    Compute.DOCKER: 0.5,
    Compute.VIRTUAL_MACHINES: 0.3,
    Compute.BARE_METAL: 0.2,
}
_STYLE_CREDIT = {
    ArchitectureStyle.MICROSERVICES: 1.0,
    ArchitectureStyle.EVENT_DRIVEN: 1.0,
    ArchitectureStyle.API_BASED: 0.9,
    ArchitectureStyle.SOA: 0.7,
    ArchitectureStyle.BATCH: 0.3,
    ArchitectureStyle.MONOLITH: 0.3,
}


def _identity_credit(arch: CurrentArchitecture) -> float:
    ids = set(arch.identity_security)
    modern = ids & {IdentitySecurity.OIDC, IdentitySecurity.OAUTH2, IdentitySecurity.ENTRA_ID, IdentitySecurity.JWT}
    credit = 0.55 if modern else (0.35 if IdentitySecurity.ACTIVE_DIRECTORY in ids else 0.0)
    if ids & {IdentitySecurity.RBAC, IdentitySecurity.ABAC}:
        credit += 0.45
    return min(credit, 1.0)


def _integration_credit(arch: CurrentArchitecture) -> float:
    integ = set(arch.integration)
    if integ & {Integration.KAFKA, Integration.EVENT_BUS, Integration.MESSAGE_QUEUE} and integ & {
        Integration.REST,
        Integration.GRPC,
        Integration.GRAPHQL,
    }:
        return 1.0
    if integ & {Integration.REST, Integration.GRPC, Integration.GRAPHQL, Integration.KAFKA, Integration.EVENT_BUS}:
        return 0.8
    if integ:
        return 0.4
    return 0.0


def infrastructure_score(arch: CurrentArchitecture) -> Score:
    """Deterministic Infrastructure Readiness score with factor breakdown."""
    ids = set(arch.identity_security)
    devops = set(arch.devops)
    raw = {
        "container_platform": max((_COMPUTE_CREDIT[c] for c in arch.compute), default=0.0),
        "service_architecture": max((_STYLE_CREDIT[s] for s in arch.styles), default=0.0),
        "api_gateway": 1.0 if IdentitySecurity.API_GATEWAY in ids else 0.0,
        "identity_and_access": _identity_credit(arch),
        "secrets_management": 1.0 if IdentitySecurity.SECRETS_MANAGEMENT in ids else 0.0,
        "ci_cd": 1.0 if devops & CI_CD_TOOLS else 0.0,
        "observability": min(len(devops & OBSERVABILITY_TOOLS) / 2, 1.0),
        "private_networking": 1.0 if IdentitySecurity.PRIVATE_NETWORKING in ids else 0.0,
        "integration_fabric": _integration_credit(arch),
    }
    factors = [
        ScoreFactor(name=k, raw=round(v, 3), weight=INFRA_WEIGHTS[k], contribution=round(v * INFRA_WEIGHTS[k], 2))
        for k, v in raw.items()
    ]
    value = round(sum(f.contribution for f in factors), 1)
    return Score(key="infrastructure_readiness", label="Infrastructure Readiness", value=value, factors=factors)


def _maturity_label(score: float) -> str:
    if score >= 75:
        return "Mature platform — AI services can reuse it"
    if score >= 50:
        return "Capable platform with gaps"
    if score >= 30:
        return "Developing platform"
    return "Limited platform — address foundations before AI"


def assess_infrastructure(arch: CurrentArchitecture) -> InfrastructureAssessment:
    """Narrative + score for the current-state platform."""
    score = infrastructure_score(arch)
    raw = {f.name: f.raw for f in score.factors}
    strengths: list[str] = []
    gaps: list[str] = []
    reusable: list[str] = []

    if raw["container_platform"] >= 1.0:
        names = [c.value for c in arch.compute if c in (Compute.KUBERNETES, Compute.OPENSHIFT)]
        strengths.append(f"Container orchestration in place ({', '.join(names)}) — AI services deploy as ordinary workloads.")
        reusable.append("Existing container platform for AI service hosting")
    elif raw["container_platform"] > 0:
        gaps.append("No container orchestration; AI services would run on VMs/serverless with more manual operations.")
    else:
        gaps.append("No compute platform described.")

    if raw["service_architecture"] >= 0.9:
        strengths.append("Service-oriented/API architecture lets AI integrate through existing APIs instead of databases.")
        reusable.append("Existing service APIs as governed integration points")
    elif ArchitectureStyle.MONOLITH in arch.styles:
        gaps.append("Monolith: integrate AI at the edge via an adapter API rather than modifying core logic.")

    if raw["api_gateway"]:
        strengths.append("API Gateway provides an existing security and rate-limiting boundary for AI traffic.")
        reusable.append("API Gateway for authN/Z, quotas and AI route policies")
    else:
        gaps.append("No API gateway — introduce a governed entry point before exposing AI endpoints.")

    if raw["identity_and_access"] >= 0.9:
        strengths.append("Federated identity with role/attribute-based access control can be propagated to AI retrieval and tools.")
        reusable.append("Enterprise identity (RBAC/ABAC) for permission-aware retrieval")
    else:
        gaps.append("Identity/authorization model is incomplete — AI must not bypass entitlements.")

    if not raw["secrets_management"]:
        gaps.append("No secrets management — required before storing model/API credentials.")
    else:
        reusable.append("Secrets manager for model credentials")
    if not raw["ci_cd"]:
        gaps.append("No CI/CD — prompts, retrieval configs and evaluations need versioned pipelines.")
    else:
        reusable.append("CI/CD pipelines for prompts, configs and evaluation gates")
    if raw["observability"] < 0.5:
        gaps.append("Limited observability — AI telemetry (tokens, latency, groundedness) needs a home.")
    else:
        reusable.append("Observability stack — extend with AI telemetry")

    deploy = set(arch.deployment)
    if deploy == {Deployment.ON_PREMISES}:
        location = "on-premises only"
    elif deploy & {Deployment.HYBRID_CLOUD, Deployment.MULTI_CLOUD} or (
        Deployment.ON_PREMISES in deploy and deploy & PUBLIC_CLOUDS
    ):
        location = "hybrid / multi-environment"
    else:
        location = ", ".join(d.value for d in arch.deployment) or "unspecified"

    summary = (
        f"Deployment: {location}. Compute: {', '.join(c.value for c in arch.compute) or 'n/a'}. "
        f"Styles: {', '.join(s.value for s in arch.styles) or 'n/a'}. Readiness {score.value:.0f}/100."
    )
    return InfrastructureAssessment(
        score=score.value,
        maturity_label=_maturity_label(score.value),
        platform_summary=summary,
        strengths=strengths,
        gaps=gaps,
        reusable_platform_capabilities=reusable,
    )
