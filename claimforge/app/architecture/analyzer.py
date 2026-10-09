"""Architecture analysis & recommendations (DETERMINISTIC guardrailed templates).

Principles enforced in code:
* Prefer preserving working enterprise systems (KEEP/ENHANCE before REPLACE).
* NEVER recommend replacing a deterministic claims engine with an LLM agent.
* ClaimForge is ADDITIVE: it sits beside the platform behind read-only adapters.
"""

from __future__ import annotations

from app.impact.analyzer import load_architecture
from app.models.domain import Impact, ImpactAction

CURRENT_ARCHITECTURE_MERMAID = """flowchart TB
    U[Members / Providers / Staff] --> GW[API Gateway]
    GW --> K8S{{Kubernetes cluster}}
    K8S --> CS[Claims Service<br/>deterministic adjudication]
    K8S --> BS[Benefits Service]
    K8S --> AS[Authorization Service]
    K8S --> MS[Member Service]
    CS --> KAFKA[(Kafka: claims.adjudicated)]
    BS --> KAFKA
    AS --> KAFKA
    MS --> KAFKA
    KAFKA --> DB[(PostgreSQL / Oracle)]
    KAFKA --> MON[Monitoring]
"""

TARGET_ARCHITECTURE_MERMAID = """flowchart TB
    CF[ClaimForge Copilot UI<br/>Streamlit] --> API[FastAPI]
    API --> LG[LangGraph orchestration<br/>Supervisor + specialist agents]
    LG --> AG[Agents<br/>reasoning / explanation]
    LG --> RAG[Policy RAG<br/>BM25 + citations]
    LG --> TOOLS[Allow-listed tools<br/>deterministic engines]
    TOOLS --> ENG[Rules engine / simulator /<br/>risk / anomaly detection]
    TOOLS --> ADP[API / MCP adapter layer<br/>read-only by default]
    ADP --> PLAT[EXISTING INSURANCE PLATFORM]
    PLAT --> CS[Claims Service]
    PLAT --> BS[Benefits Service]
    PLAT --> AS[Authorization Service]
    PLAT --> MS[Member Service]
    CS & BS & AS & MS --> DATA[(Data / Kafka)]
    DATA -. claims.adjudicated events .-> CIQ[ClaimIQ monitoring]
    CIQ --> LG
    HITL[Human approval gates] --- LG
"""


class ArchitectureGuardrailViolation(RuntimeError):
    pass


def recommend(impacts: list[Impact]) -> dict:
    arch = load_architecture()
    deterministic = {c["component_id"] for c in arch["components"] if c.get("deterministic_engine")}
    recs: list[dict] = [
        {"action": "KEEP", "target": "Claims Service deterministic adjudication pipeline",
         "reason": "Adjudication must remain deterministic, versioned and auditable (O-01.1, S-04.1). "
                   "Agents never adjudicate claims."},
        {"action": "KEEP", "target": "Kafka event backbone & existing data stores",
         "reason": "ClaimIQ consumes existing claims.adjudicated events; no new transactional store needed."},
    ]
    for imp in impacts:
        if imp.action is ImpactAction.KEEP:
            continue
        recs.append({"action": imp.action.value, "target": imp.component_name, "component_id": imp.component_id,
                     "reason": imp.reason})
    recs += [
        {"action": "ADD", "target": "ClaimForge layer (FastAPI + LangGraph) beside the platform",
         "reason": "Additive SDLC/decision-support layer; read-only adapters; consequential actions gated by humans."},
        {"action": "ADD", "target": "Shadow adjudication replay (simulation lab)",
         "reason": "Run proposed rulesets against synthetic/replayed claims before release; compare expected vs actual."},
        {"action": "ADD", "target": "ClaimIQ release-aware monitoring",
         "reason": "Compare post-release metrics to the approved simulation projection; trigger investigation on anomalies."},
    ]
    # Guardrail: never replace a deterministic engine with an agent/LLM.
    for r in recs:
        if r["action"] == "REPLACE" and r.get("component_id") in deterministic:
            raise ArchitectureGuardrailViolation(f"Refusing to REPLACE deterministic engine {r['component_id']}")
        if "llm" in r["reason"].lower() and "replace" in r["action"].lower():
            raise ArchitectureGuardrailViolation("LLM replacement of deterministic logic is not allowed")
    return {
        "recommendations": recs,
        "principles": [
            "Agents orchestrate, retrieve, investigate and explain.",
            "Deterministic engines adjudicate, calculate, simulate and score.",
            "Statistics detect numerical anomalies; agents investigate them.",
            "Humans approve consequential actions (release, remediation, reprocessing).",
        ],
        "current_architecture_mermaid": CURRENT_ARCHITECTURE_MERMAID,
        "target_architecture_mermaid": TARGET_ARCHITECTURE_MERMAID,
        "fhir_mapping": FHIR_MAPPING,
        "method": "DETERMINISTIC TEMPLATE with guardrail checks",
    }


FHIR_MAPPING = [
    {"claimforge": "Member", "fhir_r4": "Patient + Coverage.beneficiary", "status": "MAPPING ONLY (not implemented)"},
    {"claimforge": "Plan / Benefit", "fhir_r4": "Coverage / InsurancePlan", "status": "MAPPING ONLY (not implemented)"},
    {"claimforge": "Claim / ClaimLine", "fhir_r4": "Claim / Claim.item", "status": "MAPPING ONLY (not implemented)"},
    {"claimforge": "AdjudicationResult", "fhir_r4": "ClaimResponse / ExplanationOfBenefit", "status": "MAPPING ONLY (not implemented)"},
    {"claimforge": "Provider", "fhir_r4": "Practitioner / Organization", "status": "MAPPING ONLY (not implemented)"},
    {"claimforge": "Authorization", "fhir_r4": "ClaimResponse (preAuthRef) / CoverageEligibilityResponse", "status": "MAPPING ONLY (not implemented)"},
]
