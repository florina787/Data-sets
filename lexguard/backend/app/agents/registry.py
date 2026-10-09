"""Agent catalogue (backend intelligence only - users never talk to an agent directly)."""

from __future__ import annotations

from app.security.tool_gateway import AGENT_TOOL_ALLOWLIST

AGENTS = [
    ("supervisor", "Supervisor Agent", "Understands intent and matter context, plans the minimal set of agents, enforces iteration and tool limits, surfaces approval gates.", "1.4"),
    ("matter_intake", "Matter Intake Agent", "Resolves user, client and matter context; classifies the request deterministically; screens user text for injection.", "1.2"),
    ("ai_policy", "AI Policy Agent", "Invokes MatterGuard (deterministic) and explains policy decisions with evidence.", "1.3"),
    ("ai_routing", "AI Routing Agent", "Computes deterministic AI-suitability scores and selects the execution route.", "1.1"),
    ("legal_knowledge", "Legal Knowledge Agent", "Permission-aware retrieval of firm policies, playbooks, precedents and institutional knowledge.", "2.4"),
    ("document_analysis", "Document Analysis Agent", "Clause extraction, due diligence, comparison, obligations, timelines, entities and summaries.", "1.3"),
    ("legal_research", "Legal Research Agent", "Grounded research summaries and decision-support packs with citations.", "2.1"),
    ("playbook", "Playbook Agent", "PlaybookGuard: compares clauses and AI recommendations with practice playbooks.", "1.1"),
    ("citation_verification", "Citation Verification Agent", "Verifies every material proposition against permitted sources.", "1.6"),
    ("workproduct_assurance", "WorkProduct Assurance Agent", "Runs the assurance pipeline and computes the assurance score.", "1.2"),
    ("privilege", "Privilege / Confidentiality Agent", "PrivilegeGuard: flags POTENTIAL privilege and confidentiality risks for lawyer review.", "1.0"),
    ("drafting", "Drafting Agent", "Template-grounded drafting from verified, permitted context only.", "1.5"),
    ("value_analysis", "Value Analysis Agent", "ValueIQ estimates for the request, matter, practice, workflow and provider.", "1.0"),
    ("change_impact", "Change Impact Agent", "ChangeOps: impact analysis of policy changes on workflows, providers, prompts and gates.", "1.0"),
    ("evaluation", "Evaluation Agent", "Evaluation Lab: baseline vs candidate regression evaluation.", "1.0"),
]


def catalogue() -> list[dict]:
    return [{"agent_id": a, "name": n, "description": d, "version": v, "tools": sorted(AGENT_TOOL_ALLOWLIST.get(a, set()))}
            for a, n, d, v in AGENTS]
