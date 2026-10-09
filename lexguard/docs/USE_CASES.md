# Use Case Catalog

Status is honest: **IMPLEMENTED** means working code exercised by the demo and/or tests; **PARTIAL** means a real but
limited implementation (the limitation is stated); **PLANNED** would mean not implemented. The same catalogue is served
by `GET /use-cases` and shown on the **Use Cases** page.

Totals: **40 implemented · 5 partial · 0 planned** (45 total).


## Matter / Governance

| ID | Use case | Status | Evidence | Module |
|---|---|---|---|---|
| UC01 | Matter classification | IMPLEMENTED | Matter risk, confidentiality and AI status derived deterministically (MatterGuard, Control Tower). | `app/matterguard/guard.py` |
| UC02 | Client AI restriction | IMPLEMENTED | Client AI instructions enforced as policy rules POL-CLIENT-001..005. | `app/policy/engine.py` |
| UC03 | Matter AI eligibility | IMPLEMENTED | MatterGuard returns PERMITTED / WITH CONTROLS / RESTRICTED / PROHIBITED. | `app/matterguard/guard.py` |
| UC04 | Ethical-wall enforcement | IMPLEMENTED | Walls checked before any retrieval; denial is audited as a security event. | `app/access/matter_access.py` |
| UC05 | Data sensitivity | IMPLEMENTED | Sensitivity labels with role clearances applied before scoring. | `app/rag/retriever.py` |
| UC06 | RBAC | IMPLEMENTED | Role permissions for content, approvals, external providers and governance. | `app/access/rbac.py` |
| UC07 | Provider permission | IMPLEMENTED | Provider registry rules POL-PROV-001..004 and ProviderGateway enforcement. | `app/providers/registry.py` |

## Routing

| ID | Use case | Status | Evidence | Module |
|---|---|---|---|---|
| UC08 | AI suitability | IMPLEMENTED | Deterministic weighted scoring of task and matter factors. | `app/routing/suitability.py` |
| UC09 | Agentic suitability | IMPLEMENTED | Agentic score and autonomy risk; router never defaults to agentic. | `app/routing/router.py` |
| UC10 | Human-vs-AI routing | IMPLEMENTED | Legal-judgment and Level 0 matters routed to a lawyer. | `app/routing/router.py` |
| UC11 | Provider routing | IMPLEMENTED | Router selects internal/external provider subject to MatterGuard. | `app/routing/router.py` |
| UC12 | Workflow recommendation | IMPLEMENTED | Router maps intent to a registered workflow. | `app/routing/router.py` |
| UC13 | Human-review determination | IMPLEMENTED | HITL levels 0-4 determined by MatterGuard. | `app/matterguard/guard.py` |

## Knowledge

| ID | Use case | Status | Evidence | Module |
|---|---|---|---|---|
| UC14 | Policy retrieval | IMPLEMENTED | Firm policies and client instructions retrievable with citations. | `app/agents/legal.py` |
| UC15 | Matter retrieval | IMPLEMENTED | Matter-partitioned retrieval limited to the active matter. | `app/rag/retriever.py` |
| UC16 | Precedent retrieval | IMPLEMENTED | Precedents and templates in the practice partition. | `app/rag/retriever.py` |
| UC17 | Playbook retrieval | IMPLEMENTED | Playbook sections retrieved and shown as comparison evidence. | `app/agents/legal.py` |
| UC18 | Institutional knowledge | IMPLEMENTED | Lessons-learned notes retrievable by practice. | `synthetic_data/policies` |
| UC19 | Permission-aware RAG | IMPLEMENTED | Sealed AccessScope; unauthorised partitions never read or scored. | `app/rag/index.py` |

## Legal work

| ID | Use case | Status | Evidence | Module |
|---|---|---|---|---|
| UC20 | Document review | IMPLEMENTED | 487-contract change-of-control review with exclusions. | `app/documents/analysis.py` |
| UC21 | Due diligence | IMPLEMENTED | DD findings, deviations, escalations and verified DD report. | `app/agents/legal.py` |
| UC22 | Contract analysis | IMPLEMENTED | Clause-level analysis with playbook classification. | `app/documents/analysis.py` |
| UC23 | Clause extraction | IMPLEMENTED | Change-of-control clause and definition extraction. | `app/documents/analysis.py` |
| UC24 | Document comparison | IMPLEMENTED | Section-aligned comparison with similarity ratio. | `app/documents/analysis.py` |
| UC25 | Research assistance | PARTIAL | Extractive research over the synthetic internal knowledge base; no external case-law database is connected. | `app/agents/legal.py` |
| UC26 | Drafting | PARTIAL | Template-grounded DD report / memo from verified findings; no free-form generative drafting in DEMO_MODE. | `app/drafting/drafter.py` |
| UC27 | Summarization | IMPLEMENTED | Extractive per-section summaries with citations. | `app/documents/analysis.py` |
| UC28 | Obligation extraction | IMPLEMENTED | Sentence-level obligation extraction with citations. | `app/documents/analysis.py` |

## Assurance

| ID | Use case | Status | Evidence | Module |
|---|---|---|---|---|
| UC29 | Citation verification | IMPLEMENTED | SUPPORTED / PARTIAL / UNSUPPORTED / SOURCE NOT FOUND per proposition. | `app/citations/verifier.py` |
| UC30 | Groundedness | PARTIAL | Lexical groundedness (quote, term overlap, figures); no semantic entailment model. | `app/citations/verifier.py` |
| UC31 | Unsupported-claim detection | IMPLEMENTED | Unsupported and missing-source claims detected and penalised. | `app/assurance/pipeline.py` |
| UC32 | Playbook validation | IMPLEMENTED | Clauses and AI recommendations vs playbook rules. | `app/playbooks/guard.py` |
| UC33 | Matter-policy validation | IMPLEMENTED | MatterGuard decision feeds assurance. | `app/assurance/pipeline.py` |
| UC34 | Confidentiality review | IMPLEMENTED | Cross-matter, cross-client and external-sharing checks. | `app/privilege/guard.py` |
| UC35 | Potential privilege risk | IMPLEMENTED | Pattern-based POTENTIAL PRIVILEGE RISK flags; never a determination. | `app/privilege/guard.py` |
| UC36 | Work-product assurance | IMPLEMENTED | Full pipeline with explained score and delivery gate. | `app/assurance/pipeline.py` |

## Operations

| ID | Use case | Status | Evidence | Module |
|---|---|---|---|---|
| UC37 | Adoption analytics | IMPLEMENTED | Practice/provider adoption on synthetic history + live runs. | `app/governance/control_tower.py` |
| UC38 | Matter AI value | IMPLEMENTED | Per-matter ValueIQ (synthetic estimates). | `app/valueiq/service.py` |
| UC39 | Time-savings analysis | IMPLEMENTED | Net hours saved formula (synthetic estimates). | `app/valueiq/service.py` |
| UC40 | Rework analysis | PARTIAL | Rework hours from synthetic history only; no live rework capture from reviewers. | `app/valueiq/service.py` |
| UC41 | Provider utilization | IMPLEMENTED | Usage by provider. | `app/governance/control_tower.py` |

## Governance SDLC

| ID | Use case | Status | Evidence | Module |
|---|---|---|---|---|
| UC42 | Policy change impact | IMPLEMENTED | ChangeOps impact analysis, tests, pilot, approval, simulated deploy. | `app/changeops/service.py` |
| UC43 | Prompt regression | PARTIAL | Prompt versions are evaluated as configuration changes; prompts are not sent to an LLM in DEMO_MODE. | `app/evaluation/lab.py` |
| UC44 | Agent/workflow evaluation | IMPLEMENTED | Baseline vs candidate with safety and quality gates. | `app/evaluation/lab.py` |
| UC45 | AI inventory | IMPLEMENTED | Applications, agents, models, providers, prompts, RAG, workflows. | `app/inventory/service.py` |

## Where to see each one

* UC01-07, UC13: Copilot left panel, **MatterGuard** page, Project Aurora / Matter Beta / Granite scenarios.
* UC08-12: **MatterGuard** page (AI Router section) and the Policy tab of any Copilot answer.
* UC14-19: **Knowledge** page and the Sources tab.
* UC20-28: Copilot on Project Maple (review, draft, summarise `MAPLE-C-0042`, compare `MAPLE-C-0059` with `MAPLE-C-0060`) and Orion (timeline).
* UC29-36: **WorkProduct Assurance** page, Evidence/Approval tabs, "Verify the citations in the draft memo".
* UC37-41: **Control Tower** and **ValueIQ**.
* UC42-45: **ChangeOps**, **Evaluation Lab**, **AI Inventory**.
