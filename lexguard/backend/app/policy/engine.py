"""Deterministic AI policy engine.

Every rule is plain Python over typed inputs. No rule consults an LLM, an agent, or document text.
Rules return (effect, rule_id, description, evidence). Effects are aggregated by MatterGuard.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.access.rbac import has_permission
from app.models.domain import Client, Matter, Provider, User, sensitivity_rank

PROHIBIT, RESTRICT, CONTROL = "PROHIBIT", "RESTRICT", "CONTROL"

EXTERNAL_DESTINATIONS = {"external_client", "external_court", "external_public", "external_counterparty"}


@dataclass
class RuleHit:
    effect: str
    rule_id: str
    description: str
    evidence: dict | None = None
    scope: str = "request"  # request | provider | delivery


@dataclass
class PolicyInput:
    user: User
    client: Client
    matter: Matter
    provider: Provider | None
    destination: str
    doc_sensitivities: list[str]
    task_intent: str = "general"
    hits: list[RuleHit] = field(default_factory=list)


FIRM_POLICY = {"doc_id": "KN-POL-001"}


def evaluate_policies(p: PolicyInput) -> list[RuleHit]:
    hits: list[RuleHit] = []
    pol = p.client.ai_policy
    client_ev = pol.evidence
    max_doc = max((sensitivity_rank(s) for s in p.doc_sensitivities), default=-1)

    # --- client AI instructions -------------------------------------------------
    if not pol.ai_allowed:
        hits.append(RuleHit(PROHIBIT, "POL-CLIENT-001", f"{p.client.name} prohibits all AI use on its matters.", client_ev))
    if p.provider is not None:
        if not p.provider.external and not pol.internal_ai_allowed:
            hits.append(RuleHit(PROHIBIT, "POL-CLIENT-002", f"{p.client.name} prohibits internal AI processing.", client_ev, "provider"))
        if p.provider.external and not pol.external_ai_allowed:
            hits.append(RuleHit(PROHIBIT, "POL-CLIENT-003",
                                f"{p.client.name} prohibits external generative AI. Provider '{p.provider.name}' is external.",
                                client_ev, "provider"))
        elif p.provider.external and p.provider.provider_id not in pol.allowed_external_providers:
            hits.append(RuleHit(PROHIBIT, "POL-CLIENT-004",
                                f"Provider '{p.provider.name}' is not on {p.client.name}'s approved external provider list.",
                                client_ev, "provider"))
        elif p.provider.external and pol.max_external_classification is not None and \
                max_doc > sensitivity_rank(pol.max_external_classification):
            hits.append(RuleHit(RESTRICT, "POL-CLIENT-005",
                                f"Some matter documents exceed the client's maximum classification for external processing "
                                f"({pol.max_external_classification}); those documents are excluded.", client_ev, "provider"))

        # --- provider register ----------------------------------------------------
        prov = p.provider
        prov_ev = {"doc_id": "KN-POL-001", "section_id": "s4"}
        if prov.approval_status != "APPROVED" or prov.status != "ACTIVE":
            hits.append(RuleHit(PROHIBIT, "POL-PROV-001",
                                f"Provider '{prov.name}' is not approved for use (approval: {prov.approval_status}, status: {prov.status}).",
                                prov_ev, "provider"))
        if prov.practice_restrictions and p.matter.practice_id not in prov.practice_restrictions:
            hits.append(RuleHit(PROHIBIT, "POL-PROV-002",
                                f"Provider '{prov.name}' is not approved for this practice group.", prov_ev, "provider"))
        if p.matter.matter_id in prov.matter_restrictions:
            hits.append(RuleHit(PROHIBIT, "POL-PROV-003", f"Provider '{prov.name}' is restricted on this matter.", prov_ev, "provider"))
        if prov.allowed_classifications and max_doc > max(sensitivity_rank(c) for c in prov.allowed_classifications):
            hits.append(RuleHit(RESTRICT, "POL-PROV-004",
                                f"Provider '{prov.name}' is not approved for the most sensitive documents in this matter; "
                                "those documents are excluded from processing.", prov_ev, "provider"))
        if prov.external and not has_permission(p.user, "request_external_provider"):
            hits.append(RuleHit(PROHIBIT, "POL-RBAC-001",
                                f"Role {p.user.role.value} may not send matter data to external providers.",
                                {"doc_id": "KN-POL-001", "section_id": "s4"}, "provider"))

    # --- delivery / human review ------------------------------------------------
    if p.destination in EXTERNAL_DESTINATIONS:
        hits.append(RuleHit(CONTROL, "POL-DEST-001",
                            "External delivery requires assurance to pass and Senior Associate or Partner approval.",
                            {"doc_id": "KN-POL-003", "section_id": "s2"}, "delivery"))
        if "privileged" in p.doc_sensitivities:
            hits.append(RuleHit(CONTROL, "POL-DEST-002",
                                "Matter contains privileged material: potential privilege risk must be reviewed before external delivery.",
                                {"doc_id": "KN-POL-002", "section_id": "s2"}, "delivery"))
    if pol.human_review_required:
        hits.append(RuleHit(CONTROL, "POL-HR-001", "Client instructions require lawyer review of AI-assisted work.", client_ev))
    if p.matter.risk_level == "HIGH":
        hits.append(RuleHit(CONTROL, "POL-RISK-001", "High-risk matter: additional review controls apply.",
                            {"doc_id": "KN-POL-003", "section_id": "s1"}))
    hits.append(RuleHit(CONTROL, "POL-FIRM-002", "AI output is not legal advice until adopted by a responsible lawyer.",
                        {"doc_id": "KN-POL-001", "section_id": "s2"}))
    return hits
