"""AI Router - chooses the execution route deterministically. It never defaults to agentic AI."""

from __future__ import annotations

from pydantic import BaseModel

ROUTES = ["NO_AI", "HUMAN_LAWYER", "TRADITIONAL_SEARCH", "LEGAL_RESEARCH_PLATFORM", "DETERMINISTIC_WORKFLOW",
          "INTERNAL_RAG", "ENTERPRISE_COPILOT", "EXTERNAL_LEGAL_AI", "DOCUMENT_REVIEW_WORKFLOW", "AGENTIC_WORKFLOW", "HYBRID"]

INTENT_WORKFLOW = {
    "contract_review": "WF-DD-COC", "playbook_compare": "WF-DD-COC", "escalation_query": "WF-DD-COC",
    "show_evidence": "WF-DD-COC", "draft_memo": "WF-DD-COC", "client_draft": "WF-DD-COC",
    "research": "WF-RESEARCH-INT", "knowledge_question": "WF-KNOWLEDGE-QA", "summarize": "WF-CONTRACT-SUMMARY",
    "recommendation_check": "WF-PLAYBOOK-CHECK", "extract_timeline": "WF-INCIDENT-TIMELINE",
}


class RouteOption(BaseModel):
    route: str
    selected: bool
    reason: str


class RoutingDecision(BaseModel):
    route: str
    provider_id: str | None
    workflow_id: str | None
    reasons: list[str]
    ai_support_permitted: list[str] = []
    options: list[RouteOption]


def recommend(*, intent: str, mg, suit, doc_count: int, requested_provider: str | None) -> RoutingDecision:
    opts: dict[str, str] = {}
    reasons: list[str] = []
    support: list[str] = []
    provider: str | None = "P-INTERNAL-RAG"

    agentic_ok = suit.agentic_suitability >= 70 and suit.autonomy_risk < 40 and mg.ai_allowed_for_matter
    opts["AGENTIC_WORKFLOW"] = ("Eligible but not selected: a bounded workflow is sufficient." if agentic_ok else
                                f"Rejected: agentic suitability {suit.agentic_suitability}, autonomy risk {suit.autonomy_risk}. "
                                "LexGuard never defaults to agentic AI.")

    if not mg.access_granted:
        route, provider = "NO_AI", None
        reasons.append("Access denied by deterministic controls; no route permitted.")
    elif not mg.ai_allowed_for_matter:
        route, provider = "HUMAN_LAWYER", None
        reasons.append("Client prohibits all AI use (Level 0). Work routed to the matter team.")
        support = ["Traditional keyword search (non-generative)"]
    elif intent == "legal_judgment":
        route, provider = "HUMAN_LAWYER", None
        reasons.append(f"Legal-judgment risk {suit.legal_judgment_risk}/100: consequential decisions are reserved to lawyers.")
        support = ["Research on relevant factors", "Evidence synthesis from matter documents", "Scenario analysis (non-decisional)"]
    elif intent in ("cross_matter_request", "policy_question", "explain_block", "value_query", "citation_verify",
                    "recommendation_check", "privilege_review"):
        route, provider = "DETERMINISTIC_WORKFLOW", None
        reasons.append("Answerable by deterministic controls and verification engines; no generative step required.")
    elif intent == "external_provider_request":
        if requested_provider and mg.provider_permitted:
            route, provider = "EXTERNAL_LEGAL_AI", requested_provider
            reasons.append("Requested external provider is approved for this client, practice and data classification.")
        else:
            route, provider = "INTERNAL_RAG", "P-INTERNAL-RAG"
            reasons.append("Requested external provider is not permitted; internal alternative offered.")
    elif intent in ("contract_review", "playbook_compare", "escalation_query", "show_evidence"):
        if doc_count > 50 and suit.ai_suitability >= 60:
            route = "DOCUMENT_REVIEW_WORKFLOW"
            reasons.append(f"High-volume repeatable review ({doc_count} documents, AI suitability {suit.ai_suitability}).")
        else:
            route = "INTERNAL_RAG"
            reasons.append("Low document volume; permission-aware retrieval is sufficient.")
    elif intent in ("draft_memo", "client_draft"):
        route = "HYBRID"
        reasons.append("Drafting combines verified review findings, grounded drafting and mandatory lawyer review.")
    elif intent == "search":
        route, provider = "TRADITIONAL_SEARCH", None
        reasons.append("Locating documents does not require generative AI.")
    else:
        route = "INTERNAL_RAG"
        reasons.append("Knowledge retrieval with citations from permitted sources.")

    candidates = {
        "NO_AI": "Not required: access and AI policy permit assisted work." if route != "NO_AI" else "",
        "HUMAN_LAWYER": "Lawyer review remains mandatory downstream." if route != "HUMAN_LAWYER" else "",
        "TRADITIONAL_SEARCH": "Insufficient for analysis tasks." if route != "TRADITIONAL_SEARCH" else "",
        "LEGAL_RESEARCH_PLATFORM": "Public-law research platform not needed for matter-document tasks.",
        "DETERMINISTIC_WORKFLOW": "Task requires analysis beyond deterministic rules." if route != "DETERMINISTIC_WORKFLOW" else "",
        "INTERNAL_RAG": "" if route == "INTERNAL_RAG" else "Available as fallback.",
        "ENTERPRISE_COPILOT": "General copilot is not approved for privileged material or playbook comparison.",
        "EXTERNAL_LEGAL_AI": ("Client prohibits external AI." if not mg.external_ai_allowed_for_matter else
                              "Not requested; internal processing preferred when sufficient.") if route != "EXTERNAL_LEGAL_AI" else "",
        "DOCUMENT_REVIEW_WORKFLOW": "Not a high-volume document review task." if route != "DOCUMENT_REVIEW_WORKFLOW" else "",
        "HYBRID": "Not a drafting task." if route != "HYBRID" else "",
    }
    options = [RouteOption(route=r, selected=(r == route),
                           reason=(reasons[0] if r == route else opts.get(r) or candidates.get(r, "")))
               for r in ROUTES]
    return RoutingDecision(route=route, provider_id=provider if route not in ("HUMAN_LAWYER", "NO_AI") else None,
                           workflow_id=INTENT_WORKFLOW.get(intent), reasons=reasons, ai_support_permitted=support,
                           options=options)
