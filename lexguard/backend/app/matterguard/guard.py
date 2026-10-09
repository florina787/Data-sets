"""MatterGuard - the deterministic gate every AI request passes before any retrieval or model use.

Inputs : user, client, matter, task, provider, document sensitivity, output destination.
Output : PERMITTED | PERMITTED_WITH_CONTROLS | RESTRICTED | PROHIBITED plus risk, reasons, policy
         evidence, allowed / blocked tools, human-review level and external-distribution permission.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.access.matter_access import check_ethical_wall, check_matter_access
from app.access.rbac import max_sensitivity
from app.models.domain import sensitivity_rank
from app.policy.engine import CONTROL, EXTERNAL_DESTINATIONS, PROHIBIT, RESTRICT, PolicyInput, evaluate_policies
from app.services.data_store import DataStore

TOOL_CATALOG: dict[str, dict] = {
    "matter_document_search": {"ai": False, "external": False, "description": "Permission-aware search over the active matter"},
    "knowledge_search": {"ai": False, "external": False, "description": "Permission-aware search over firm knowledge"},
    "traditional_search": {"ai": False, "external": False, "description": "Keyword search with no generative step"},
    "clause_extraction": {"ai": True, "external": False, "description": "Clause detection and classification"},
    "document_compare": {"ai": True, "external": False, "description": "Clause-level document comparison"},
    "summarize": {"ai": True, "external": False, "description": "Extractive summarisation"},
    "obligation_extract": {"ai": True, "external": False, "description": "Obligation extraction"},
    "timeline_extract": {"ai": True, "external": False, "description": "Date / event extraction"},
    "entity_extract": {"ai": True, "external": False, "description": "Entity extraction"},
    "playbook_compare": {"ai": True, "external": False, "description": "Compare against practice playbook"},
    "citation_verify": {"ai": False, "external": False, "description": "Deterministic citation verification"},
    "privilege_scan": {"ai": False, "external": False, "description": "Potential privilege / confidentiality scan"},
    "draft_generate": {"ai": True, "external": False, "description": "Template-grounded drafting"},
    "external_provider_call": {"ai": True, "external": True, "description": "Send work to an approved external legal-AI provider"},
    "llm_narration": {"ai": True, "external": True, "description": "Optional live-mode LLM narration (never decisions)"},
    "value_calc": {"ai": False, "external": False, "description": "ValueIQ calculations"},
}

INTENT_REVIEW_LEVEL = {
    "knowledge_question": 1, "research": 1, "search": 1, "policy_question": 1, "explain_block": 1, "value_query": 1,
    "summarize": 2, "contract_review": 2, "playbook_compare": 2, "escalation_query": 2, "show_evidence": 2,
    "extract_obligations": 2, "extract_timeline": 2, "extract_entities": 2, "compare_documents": 2,
    "citation_verify": 2, "recommendation_check": 2, "privilege_review": 2,
    "draft_memo": 3, "client_draft": 3, "external_provider_request": 3, "legal_judgment": 3,
}

LEVEL_LABELS = {
    0: "LEVEL 0 - AI prohibited",
    1: "LEVEL 1 - Retrieval / research only",
    2: "LEVEL 2 - AI suggestions (lawyer reviews)",
    3: "LEVEL 3 - Drafting with mandatory lawyer review",
    4: "LEVEL 4 - Approved bounded low-risk workflow",
}


class PolicyEvidence(BaseModel):
    rule_id: str
    effect: str
    description: str
    source_doc_id: str | None = None
    source_section_id: str | None = None


class MatterGuardResult(BaseModel):
    decision: str
    risk: str
    risk_score: int
    reasons: list[str]
    policy_evidence: list[PolicyEvidence]
    allowed_tools: list[str]
    blocked_tools: list[str]
    human_review_level: int
    human_review_label: str
    human_review_required: bool
    external_distribution: str
    access_granted: bool
    ethical_wall_blocked: bool
    ai_allowed_for_matter: bool
    external_ai_allowed_for_matter: bool
    provider_id: str | None
    provider_permitted: bool | None
    destination: str
    excluded_doc_sensitivities: list[str] = []
    alternatives: list[str] = []
    client_policy_summary: str | None = None


def _risk(matter_risk: str, external_provider: bool, external_dest: bool, sens: list[str]) -> tuple[int, str]:
    score = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}.get(matter_risk, 2)
    score += int(external_provider) + int(external_dest)
    score += int("privileged" in sens) + int("highly_confidential" in sens)
    label = "LOW" if score <= 1 else "MEDIUM" if score <= 3 else "HIGH" if score <= 5 else "CRITICAL"
    return score, label


def evaluate(store: DataStore, *, user_id: str, matter_id: str, provider_id: str | None = None,
             destination: str = "internal", intent: str = "general", doc_ids: list[str] | None = None) -> MatterGuardResult:
    user = store.users.get(user_id)
    matter = store.matters.get(matter_id)
    access = check_matter_access(store, user, matter)
    wall = check_ethical_wall(store, user, matter_id) if matter else None
    provider = store.providers.get(provider_id) if provider_id else None

    if not access.allowed or (wall and wall.blocked):
        blocked_reason = wall.reason if (wall and wall.blocked) else access.reason
        rule = "POL-WALL-001" if (wall and wall.blocked) else access.rule_id
        return MatterGuardResult(
            decision="PROHIBITED", risk="HIGH", risk_score=5, reasons=[blocked_reason],
            policy_evidence=[PolicyEvidence(rule_id=rule, effect=PROHIBIT, description=blocked_reason,
                                            source_doc_id="KN-POL-001" if rule == "POL-WALL-001" else "KN-POL-002",
                                            source_section_id="s6" if rule == "POL-WALL-001" else "s1")],
            allowed_tools=[], blocked_tools=sorted(TOOL_CATALOG), human_review_level=0,
            human_review_label=LEVEL_LABELS[0], human_review_required=True, external_distribution="NOT_PERMITTED",
            access_granted=access.allowed and not (wall and wall.blocked), ethical_wall_blocked=bool(wall and wall.blocked),
            ai_allowed_for_matter=False, external_ai_allowed_for_matter=False, provider_id=provider_id,
            provider_permitted=False if provider_id else None, destination=destination,
            alternatives=["Contact the responsible partner or General Counsel if you believe access is required."],
        )

    assert user is not None and matter is not None
    client = store.clients[matter.client_id]
    # Only documents the user's role may see contribute to scope; sensitivity is metadata, not content.
    docs = [store.documents[d] for d in (doc_ids or []) if d in store.documents and store.documents[d].matter_id == matter_id] \
        or store.matter_documents(matter_id)
    role_max = sensitivity_rank(max_sensitivity(user))
    sens = sorted({d.sensitivity for d in docs if d.status == "active" and sensitivity_rank(d.sensitivity) <= role_max},
                  key=sensitivity_rank)
    hits = evaluate_policies(PolicyInput(user=user, client=client, matter=matter, provider=provider,
                                         destination=destination, doc_sensitivities=sens, task_intent=intent))
    if provider_id and provider is None:
        from app.policy.engine import RuleHit
        hits.append(RuleHit(PROHIBIT, "POL-PROV-000", f"Provider '{provider_id}' is not in the provider registry.",
                            {"doc_id": "KN-POL-001", "section_id": "s4"}, "provider"))

    effects = {h.effect for h in hits}
    pol = client.ai_policy
    ai_allowed = pol.ai_allowed
    external_ok = pol.ai_allowed and pol.external_ai_allowed
    if PROHIBIT in effects:
        decision = "PROHIBITED"
    elif RESTRICT in effects:
        decision = "RESTRICTED"
    elif CONTROL in effects:
        decision = "PERMITTED_WITH_CONTROLS"
    else:
        decision = "PERMITTED"

    external_dest = destination in EXTERNAL_DESTINATIONS
    risk_score, risk = _risk(matter.risk_level, bool(provider and provider.external), external_dest, sens)

    blocked: set[str] = set()
    if not ai_allowed:
        blocked |= {t for t, meta in TOOL_CATALOG.items() if meta["ai"]}
    if not external_ok or any(h.rule_id.startswith(("POL-CLIENT-003", "POL-CLIENT-004", "POL-RBAC")) for h in hits):
        blocked.add("external_provider_call")
    provider_prohibited = any(h.effect == PROHIBIT and h.scope == "provider" for h in hits)
    if provider is not None and provider.external and provider_prohibited:
        blocked.add("external_provider_call")
    # Live-mode LLM narration is an external processor: only for clients allowing external AI.
    if not external_ok:
        blocked.add("llm_narration")
    allowed = sorted(set(TOOL_CATALOG) - blocked)

    level = 0 if not ai_allowed else INTENT_REVIEW_LEVEL.get(intent, 2)
    if ai_allowed and external_dest:
        level = max(level, 3)
    if ai_allowed and level == 1 and risk == "LOW" and intent in {"knowledge_question", "policy_question"}:
        level = 4  # approved bounded low-risk workflow
    if decision == "PROHIBITED" and not ai_allowed:
        level = 0

    if not ai_allowed:
        ext = "NOT_PERMITTED"
    elif external_dest:
        ext = "AFTER_ASSURANCE_AND_LAWYER_APPROVAL"
    else:
        ext = "INTERNAL_ONLY"

    alternatives: list[str] = []
    if not ai_allowed:
        alternatives = ["Route to the matter team for manual review.", "Use traditional keyword search (no generative AI)."]
    elif provider is not None and provider_prohibited:
        alternatives = []
        if pol.internal_ai_allowed:
            alternatives.append("Use LexGuard Internal RAG (firm-hosted, permission-aware) - permitted under client instructions.")
        alternatives.append("Route to a lawyer for manual review.")

    return MatterGuardResult(
        decision=decision, risk=risk, risk_score=risk_score,
        reasons=([h.description for h in hits if h.effect == PROHIBIT] or [h.description for h in hits if h.effect == RESTRICT]
                 or [h.description for h in hits][:3]),
        policy_evidence=[PolicyEvidence(rule_id=h.rule_id, effect=h.effect, description=h.description,
                                        source_doc_id=(h.evidence or {}).get("doc_id"),
                                        source_section_id=(h.evidence or {}).get("section_id")) for h in hits],
        allowed_tools=allowed, blocked_tools=sorted(blocked), human_review_level=level,
        human_review_label=LEVEL_LABELS[level], human_review_required=level != 4,
        external_distribution=ext, access_granted=True, ethical_wall_blocked=False,
        ai_allowed_for_matter=ai_allowed, external_ai_allowed_for_matter=external_ok,
        provider_id=provider_id, provider_permitted=(not provider_prohibited) if provider_id else None,
        destination=destination,
        excluded_doc_sensitivities=[s for s in sens if provider is not None and provider.allowed_classifications
                                    and sensitivity_rank(s) > max(sensitivity_rank(c) for c in provider.allowed_classifications)],
        alternatives=alternatives, client_policy_summary=pol.policy_summary,
    )
