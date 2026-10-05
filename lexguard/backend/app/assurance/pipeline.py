"""WorkProduct Assurance pipeline.

AI WORK PRODUCT -> PROPOSITION EXTRACTION -> SOURCE MAPPING -> CITATION VERIFICATION -> GROUNDEDNESS
-> PLAYBOOK CHECK -> MATTER POLICY CHECK -> CONFIDENTIALITY / PRIVILEGE -> ASSURANCE RESULT -> HUMAN REVIEW

The assurance score measures how completely an AI work product is TRACEABLE to and VERIFIED against
permitted sources and firm controls. It is NOT a probability that the legal analysis is correct.
"""

from __future__ import annotations

from pydantic import BaseModel

WEIGHTS = {
    "citation_coverage": 0.20, "citation_support": 0.30, "source_coverage": 0.10,
    "playbook_adherence": 0.15, "matter_policy_compliance": 0.10, "verification_completion": 0.15,
}
UNSUPPORTED_PENALTY = 0.5
PASS_THRESHOLD = 0.90
FAIL_THRESHOLD = 0.75

SCORE_MEANING = (
    "The assurance score measures traceability and verification completeness: the share of material propositions "
    "that are cited, whether citations are supported by permitted sources, source coverage, playbook adherence, "
    "matter-policy compliance and verification completion, minus a penalty for unsupported claims. "
    "It is NOT a measure of legal correctness and does not replace lawyer review."
)


class AssuranceResult(BaseModel):
    score: float
    score_pct: int
    status: str  # PASS | REVIEW_REQUIRED | FAIL
    components: dict[str, float]
    weights: dict[str, float]
    unsupported_claim_rate: float
    citation_summary: dict
    blocking_issues: list[str]
    stages: list[dict]
    meaning: str = SCORE_MEANING
    external_delivery_allowed: bool


def evaluate(*, propositions: list[dict], verifications: list[dict], playbook_results: list[dict],
             policy_decision: str, privilege_flags: list[dict], documents_in_scope: int | None = None,
             documents_processed: int | None = None, destination: str = "internal",
             recommendations_checked: bool = False) -> AssuranceResult:
    material = [p for p in propositions if p.get("material", True)]
    mids = {p["pid"] for p in material}
    vmat = [v for v in verifications if v["pid"] in mids]
    n = max(1, len(material))
    cited = sum(1 for p in material if p.get("citation"))
    sup = sum(1 for v in vmat if v["status"] == "SUPPORTED")
    part = sum(1 for v in vmat if v["status"] == "PARTIALLY_SUPPORTED")
    uns = sum(1 for v in vmat if v["status"] in ("UNSUPPORTED", "SOURCE_NOT_FOUND"))
    nf = sum(1 for v in vmat if v["status"] == "SOURCE_NOT_FOUND")
    if recommendations_checked and playbook_results:
        adherence = sum(1 for r in playbook_results if r["result"] == "ALIGNED") / len(playbook_results)
    else:
        adherence = 1.0  # clause classifications come from the playbook itself; deviations are flagged, not adopted
    no_props = not material  # e.g. a recommendation-only work product: citation components not applicable
    components = {
        "citation_coverage": 1.0 if no_props else round(cited / n, 4),
        "citation_support": 1.0 if no_props else round((sup + 0.5 * part) / n, 4),
        "source_coverage": round((documents_processed / documents_in_scope) if documents_in_scope else 1.0, 4),
        "playbook_adherence": round(adherence, 4),
        "matter_policy_compliance": 1.0 if policy_decision in ("PERMITTED", "PERMITTED_WITH_CONTROLS", "RESTRICTED") else 0.0,
        "verification_completion": 1.0 if no_props else round(len(vmat) / n, 4),
    }
    unsupported_rate = round(uns / n, 4)
    score = sum(components[k] * w for k, w in WEIGHTS.items()) - UNSUPPORTED_PENALTY * unsupported_rate
    score = max(0.0, min(1.0, round(score, 4)))

    blocking: list[str] = []
    if uns:
        blocking.append(f"{uns} material proposition(s) unsupported or with source not found ({nf} source not found).")
    if part:
        blocking.append(f"{part} material proposition(s) only partially supported.")
    esc = [r for r in playbook_results if r["result"] == "ESCALATION_REQUIRED"]
    if esc:
        blocking.append(f"{len(esc)} playbook escalation(s) require partner review.")
    if recommendations_checked:
        dev = [r for r in playbook_results if r["result"] == "DEVIATION"]
        if dev:
            blocking.append(f"{len(dev)} AI recommendation(s) deviate from the playbook.")
    crit = [f for f in privilege_flags if f.get("severity") == "CRITICAL"]
    if crit:
        blocking.append(f"{len(crit)} critical confidentiality issue(s).")
    if components["matter_policy_compliance"] < 1:
        blocking.append("Matter policy not satisfied.")

    if score < FAIL_THRESHOLD or components["matter_policy_compliance"] < 1 or crit:
        status = "FAIL"
    elif score >= PASS_THRESHOLD and not uns and not part and not (recommendations_checked and adherence < 1):
        status = "PASS"
    else:
        status = "REVIEW_REQUIRED"

    stages = [
        {"stage": "Proposition extraction", "status": "COMPLETE" if material else "NOT_APPLICABLE",
         "detail": f"{len(material)} material propositions"},
        {"stage": "Source mapping", "status": "COMPLETE", "detail": f"{cited} of {len(material)} propositions mapped to a source"},
        {"stage": "Citation verification", "status": "COMPLETE" if len(vmat) == len(material) else "INCOMPLETE",
         "detail": f"{sup} supported, {part} partial, {uns - nf} unsupported, {nf} source not found"},
        {"stage": "Groundedness", "status": "COMPLETE", "detail": f"{sup / n:.0%} of propositions fully grounded"},
        {"stage": "Playbook check", "status": "COMPLETE" if playbook_results else "NOT_APPLICABLE",
         "detail": f"{len(playbook_results)} items checked"},
        {"stage": "Matter policy check", "status": "COMPLETE", "detail": f"MatterGuard decision: {policy_decision}"},
        {"stage": "Confidentiality / privilege", "status": "COMPLETE", "detail": f"{len(privilege_flags)} potential risk flag(s)"},
        {"stage": "Assurance result", "status": status, "detail": f"Score {score:.0%}"},
        {"stage": "Human review", "status": "PENDING", "detail": "Lawyer approval required before use"},
    ]
    return AssuranceResult(
        score=score, score_pct=round(score * 100), status=status, components=components, weights=WEIGHTS,
        unsupported_claim_rate=unsupported_rate,
        citation_summary={"total": len(vmat), "SUPPORTED": sup, "PARTIALLY_SUPPORTED": part,
                          "UNSUPPORTED": uns - nf, "SOURCE_NOT_FOUND": nf},
        blocking_issues=blocking, stages=stages,
        external_delivery_allowed=(status == "PASS") or not destination.startswith("external"),
    )
