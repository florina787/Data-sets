"""Deterministic intent classification for Copilot requests (DEMO_MODE and live mode alike).

Intent only selects a workflow; it can never grant access. Unknown text falls back to a knowledge question.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from app.services.data_store import DataStore

RULES: list[tuple[str, list[str]]] = [
    ("legal_judgment", [r"\bshould (our|the|my|we)\b.*\b(accept|reject|settle|appeal|sign|sue|agree|proceed)\b",
                        r"\bdecide (whether|if)\b", r"\bwhat should (we|our client) do\b", r"\bin (our|the) client'?s best interest\b"]),
    ("explain_block", [r"\bwhy (was|were|is|did)\b.*\b(block|denied|prohibit|restrict|stop)", r"\bwhy blocked\b"]),
    ("external_provider_request", [r"\b(send|upload|submit|run|process|forward|share)\b.*\b(external|harvey|third[- ]party|provider)\b"]),
    ("policy_question", [r"\bcan (i|we) use\b", r"\b(is|are) (external |generative )?ai (allowed|permitted)\b",
                         r"\bai (policy|restrictions?|usage)\b", r"\ballowed to use\b", r"\bpermitted (ai|providers?)\b"]),
    ("citation_verify", [r"\bverify\b.*\b(citation|memo|draft|claims?)\b", r"\bcheck\b.*\bcitations?\b", r"\bhallucinat",
                         r"\bunsupported claims?\b"]),
    ("recommendation_check", [r"\brecommendation\b", r"\bnegotiation position\b"]),
    ("client_draft", [r"\bclient[- ]ready\b", r"\bdraft\b.*\bclient\b", r"\bclient (communication|email|letter)\b"]),
    ("show_evidence", [r"\b(show|see|view)\b.*\bevidence\b", r"\bevidence for\b", r"\bsource for\b", r"\bwhere does it say\b"]),
    ("escalation_query", [r"\bescalat"]),
    ("compare_documents", [r"\bcompare\b.*\b[A-Z]+-[A-Z]*-?\d{3,4}\b.*\b[A-Z]+-[A-Z]*-?\d{3,4}\b"]),
    ("playbook_compare", [r"\bplaybook\b", r"\bdeviation"]),
    ("research", [r"\bresearch\b", r"\bcase law\b", r"\benforceab", r"\bauthorit(y|ies)\b", r"\blegal position\b"]),
    ("draft_memo", [r"\bdraft\b", r"\bmemo\b", r"\bbriefing\b", r"\bwrite (a|an|the)\b", r"\bprepare (a|an|the)\b.*\breport\b"]),
    ("contract_review", [r"\breview\b.*\b(contracts?|agreements?)\b", r"\bchange[- ](of|in)[- ]control\b", r"\bdue diligence\b",
                         r"\bclauses?\b"]),
    ("extract_obligations", [r"\bobligations?\b"]),
    ("extract_timeline", [r"\btimeline\b", r"\bchronolog", r"\bkey dates\b"]),
    ("extract_entities", [r"\bentit(y|ies)\b", r"\bwho are the parties\b"]),
    ("summarize", [r"\bsummar"]),
    ("privilege_review", [r"\bprivilege", r"\bconfidentiality review\b"]),
    ("value_query", [r"\bvalue\b", r"\bhours saved\b", r"\broi\b", r"\bproductivity\b"]),
    ("search", [r"\b(find|locate|list) (the |all )?(documents?|contracts?|files?)\b"]),
]
_COMPILED = [(intent, [re.compile(p, re.IGNORECASE) for p in pats]) for intent, pats in RULES]
DOC_ID_RE = re.compile(r"\b(?:MAPLE-C-\d{4}|MAPLE-EMP-\d{3}|AURORA-\d{3}|BETA-\d{3}|ORION-\d{3}|GRANITE-\d{3}|BELL-\d{3}|KESTREL-\d{3}|ARDEN-\d{3})\b",
                       re.IGNORECASE)


class IntentResult(BaseModel):
    intent: str
    matched_rule: str | None
    destination: str
    requested_provider: str | None
    doc_ids: list[str]
    referenced_other_matters: list[str]


def classify(store: DataStore, message: str, active_matter_id: str | None) -> IntentResult:
    intent, matched = "knowledge_question", None
    for name, pats in _COMPILED:
        for p in pats:
            if p.search(message):
                intent, matched = name, p.pattern
                break
        if matched:
            break
    low = message.lower()
    destination = "internal"
    if intent == "client_draft" or re.search(r"\b(client[- ]ready|send to (the )?client|for the client)\b", low):
        destination = "external_client"
    requested_provider = None
    if intent == "external_provider_request":
        requested_provider = "P-HARVEY" if "harvey" in low else "P-MOCK-LEGAL-AI"
    others = []
    for m in store.matters.values():
        if m.matter_id == active_matter_id:
            continue
        if m.name.lower() in low or m.matter_number.lower() in low or m.matter_id.lower() in low:
            others.append(m.matter_id)
    if others and intent not in ("legal_judgment",):
        intent, matched = "cross_matter_request", "reference to another matter"
    return IntentResult(intent=intent, matched_rule=matched, destination=destination, requested_provider=requested_provider,
                        doc_ids=[d.upper() for d in DOC_ID_RE.findall(message)], referenced_other_matters=others)
