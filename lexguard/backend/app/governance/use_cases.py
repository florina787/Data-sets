"""Use-case catalogue. Status reflects what is actually implemented in this repository."""

from __future__ import annotations

I, P, PL = "IMPLEMENTED", "PARTIAL", "PLANNED"

USE_CASES = [
    ("UC01", "Matter / Governance", "Matter classification", I, "Matter risk, confidentiality and AI status derived deterministically (MatterGuard, Control Tower).", "app/matterguard/guard.py"),
    ("UC02", "Matter / Governance", "Client AI restriction", I, "Client AI instructions enforced as policy rules POL-CLIENT-001..005.", "app/policy/engine.py"),
    ("UC03", "Matter / Governance", "Matter AI eligibility", I, "MatterGuard returns PERMITTED / WITH CONTROLS / RESTRICTED / PROHIBITED.", "app/matterguard/guard.py"),
    ("UC04", "Matter / Governance", "Ethical-wall enforcement", I, "Walls checked before any retrieval; denial is audited as a security event.", "app/access/matter_access.py"),
    ("UC05", "Matter / Governance", "Data sensitivity", I, "Sensitivity labels with role clearances applied before scoring.", "app/rag/retriever.py"),
    ("UC06", "Matter / Governance", "RBAC", I, "Role permissions for content, approvals, external providers and governance.", "app/access/rbac.py"),
    ("UC07", "Matter / Governance", "Provider permission", I, "Provider registry rules POL-PROV-001..004 and ProviderGateway enforcement.", "app/providers/registry.py"),
    ("UC08", "Routing", "AI suitability", I, "Deterministic weighted scoring of task and matter factors.", "app/routing/suitability.py"),
    ("UC09", "Routing", "Agentic suitability", I, "Agentic score and autonomy risk; router never defaults to agentic.", "app/routing/router.py"),
    ("UC10", "Routing", "Human-vs-AI routing", I, "Legal-judgment and Level 0 matters routed to a lawyer.", "app/routing/router.py"),
    ("UC11", "Routing", "Provider routing", I, "Router selects internal/external provider subject to MatterGuard.", "app/routing/router.py"),
    ("UC12", "Routing", "Workflow recommendation", I, "Router maps intent to a registered workflow.", "app/routing/router.py"),
    ("UC13", "Routing", "Human-review determination", I, "HITL levels 0-4 determined by MatterGuard.", "app/matterguard/guard.py"),
    ("UC14", "Knowledge", "Policy retrieval", I, "Firm policies and client instructions retrievable with citations.", "app/agents/legal.py"),
    ("UC15", "Knowledge", "Matter retrieval", I, "Matter-partitioned retrieval limited to the active matter.", "app/rag/retriever.py"),
    ("UC16", "Knowledge", "Precedent retrieval", I, "Precedents and templates in the practice partition.", "app/rag/retriever.py"),
    ("UC17", "Knowledge", "Playbook retrieval", I, "Playbook sections retrieved and shown as comparison evidence.", "app/agents/legal.py"),
    ("UC18", "Knowledge", "Institutional knowledge", I, "Lessons-learned notes retrievable by practice.", "synthetic_data/policies"),
    ("UC19", "Knowledge", "Permission-aware RAG", I, "Sealed AccessScope; unauthorised partitions never read or scored.", "app/rag/index.py"),
    ("UC20", "Legal work", "Document review", I, "487-contract change-of-control review with exclusions.", "app/documents/analysis.py"),
    ("UC21", "Legal work", "Due diligence", I, "DD findings, deviations, escalations and verified DD report.", "app/agents/legal.py"),
    ("UC22", "Legal work", "Contract analysis", I, "Clause-level analysis with playbook classification.", "app/documents/analysis.py"),
    ("UC23", "Legal work", "Clause extraction", I, "Change-of-control clause and definition extraction.", "app/documents/analysis.py"),
    ("UC24", "Legal work", "Document comparison", I, "Section-aligned comparison with similarity ratio.", "app/documents/analysis.py"),
    ("UC25", "Legal work", "Research assistance", P, "Extractive research over the synthetic internal knowledge base; no external case-law database is connected.", "app/agents/legal.py"),
    ("UC26", "Legal work", "Drafting", P, "Template-grounded DD report / memo from verified findings; no free-form generative drafting in DEMO_MODE.", "app/drafting/drafter.py"),
    ("UC27", "Legal work", "Summarization", I, "Extractive per-section summaries with citations.", "app/documents/analysis.py"),
    ("UC28", "Legal work", "Obligation extraction", I, "Sentence-level obligation extraction with citations.", "app/documents/analysis.py"),
    ("UC29", "Assurance", "Citation verification", I, "SUPPORTED / PARTIAL / UNSUPPORTED / SOURCE NOT FOUND per proposition.", "app/citations/verifier.py"),
    ("UC30", "Assurance", "Groundedness", P, "Lexical groundedness (quote, term overlap, figures); no semantic entailment model.", "app/citations/verifier.py"),
    ("UC31", "Assurance", "Unsupported-claim detection", I, "Unsupported and missing-source claims detected and penalised.", "app/assurance/pipeline.py"),
    ("UC32", "Assurance", "Playbook validation", I, "Clauses and AI recommendations vs playbook rules.", "app/playbooks/guard.py"),
    ("UC33", "Assurance", "Matter-policy validation", I, "MatterGuard decision feeds assurance.", "app/assurance/pipeline.py"),
    ("UC34", "Assurance", "Confidentiality review", I, "Cross-matter, cross-client and external-sharing checks.", "app/privilege/guard.py"),
    ("UC35", "Assurance", "Potential privilege risk", I, "Pattern-based POTENTIAL PRIVILEGE RISK flags; never a determination.", "app/privilege/guard.py"),
    ("UC36", "Assurance", "Work-product assurance", I, "Full pipeline with explained score and delivery gate.", "app/assurance/pipeline.py"),
    ("UC37", "Operations", "Adoption analytics", I, "Practice/provider adoption on synthetic history + live runs.", "app/governance/control_tower.py"),
    ("UC38", "Operations", "Matter AI value", I, "Per-matter ValueIQ (synthetic estimates).", "app/valueiq/service.py"),
    ("UC39", "Operations", "Time-savings analysis", I, "Net hours saved formula (synthetic estimates).", "app/valueiq/service.py"),
    ("UC40", "Operations", "Rework analysis", P, "Rework hours from synthetic history only; no live rework capture from reviewers.", "app/valueiq/service.py"),
    ("UC41", "Operations", "Provider utilization", I, "Usage by provider.", "app/governance/control_tower.py"),
    ("UC42", "Governance SDLC", "Policy change impact", I, "ChangeOps impact analysis, tests, pilot, approval, simulated deploy.", "app/changeops/service.py"),
    ("UC43", "Governance SDLC", "Prompt regression", P, "Prompt versions are evaluated as configuration changes; prompts are not sent to an LLM in DEMO_MODE.", "app/evaluation/lab.py"),
    ("UC44", "Governance SDLC", "Agent/workflow evaluation", I, "Baseline vs candidate with safety and quality gates.", "app/evaluation/lab.py"),
    ("UC45", "Governance SDLC", "AI inventory", I, "Applications, agents, models, providers, prompts, RAG, workflows.", "app/inventory/service.py"),
]


def catalogue() -> list[dict]:
    return [{"id": i, "category": c, "name": n, "status": s, "evidence": e, "module": m} for i, c, n, s, e, m in USE_CASES]
