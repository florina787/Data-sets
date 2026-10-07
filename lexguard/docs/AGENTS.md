# Agents

Agents are backend intelligence. Users never pick or chat with an agent; the Supervisor plans the minimal set for each
request and the trace makes the orchestration visible ("How LexGuard analyzed this").

## Catalogue

| # | Agent | Module | Responsibility | Tool allowlist |
|---|---|---|---|---|
| 1 | Supervisor | `agents/core.py::supervisor` | Plan by intent; prerequisites; max steps | — |
| 2 | Matter Intake | `agents/core.py::matter_intake` | User/client/matter context; intent; injection screen | — |
| 3 | AI Policy | `agents/core.py::ai_policy`, `agents/legal.py::policy_explainer` | MatterGuard; policy Q&A; "why blocked" | `knowledge_search` |
| 4 | AI Routing | `agents/core.py::assess_suitability`, `route` | Suitability + router | — |
| 5 | Legal Knowledge | `agents/legal.py::legal_knowledge` | Firm knowledge retrieval | `knowledge_search` |
| 6 | Document Analysis | `agents/legal.py::document_analysis` | CoC review, summary, obligations, timeline, entities, comparison; external provider path | `matter_document_search`, `clause_extraction`, `summarize`, `obligation_extract`, `timeline_extract`, `entity_extract`, `document_compare`, `external_provider_call`, `traditional_search` |
| 7 | Legal Research | `agents/legal.py::legal_research` | Research summaries; legal-judgment decision support | `knowledge_search`, `matter_document_search`, `external_provider_call` |
| 8 | Playbook | `agents/assurance.py::playbook_check` | PlaybookGuard on clauses / recommendations | `playbook_compare`, `knowledge_search` |
| 9 | Citation Verification | `agents/assurance.py::citation_check` | Verify all material propositions | `citation_verify` |
| 10 | WorkProduct Assurance | `agents/assurance.py::assurance`, `agents/legal.py::load_work_product` | Assurance pipeline; load AI work product for verification | `citation_verify` |
| 11 | Privilege / Confidentiality | `agents/assurance.py::privilege_check`, `agents/legal.py::privilege_scan` | PrivilegeGuard | `privilege_scan` |
| 12 | Drafting | `agents/legal.py::drafting` | DD report / memo from verified findings | `draft_generate`, `knowledge_search`, `citation_verify`, `playbook_compare` |
| 13 | Value Analysis | `agents/legal.py::value_analysis` | ValueIQ | `value_calc` |
| 14 | Change Impact | `changeops/service.py` | Policy-change impact | — |
| 15 | Evaluation | `evaluation/lab.py` | Baseline vs candidate | — |

## Supervisor plans (deterministic)

| Intent | Plan | Assurance chain? |
|---|---|---|
| contract_review, escalation_query, show_evidence | document_analysis | yes |
| playbook_compare | legal_knowledge → document_analysis | yes |
| draft_memo, client_draft | document_analysis → drafting | yes (on the draft) |
| research | legal_research | yes |
| legal_judgment | legal_research (decision-support mode) | yes; route HUMAN_LAWYER |
| knowledge_question | legal_knowledge | yes |
| summarize / extract_* / compare_documents | document_analysis | yes (extractive points) |
| citation_verify, recommendation_check | load_work_product | yes |
| policy_question, explain_block, cross_matter_request | policy_explainer | no |
| privilege_review | privilege_scan | no |
| value_query | value_analysis | no |
| search | traditional_search | no |

## Limits enforced by the graph (not by agents)

* **Iteration limit** - `MAX_AGENT_STEPS` (default 12); exceeded → `HALTED` + `AGENT_ITERATION_LIMIT` audit.
* **Tool budget** - `MAX_TOOL_CALLS` (default 40) per request; batch tools count once.
* **Time budget** - `REQUEST_TIMEOUT_S` (default 20 s) checked before every node.
* **Tool allowlists** - a tool runs only if it is in the agent's allowlist **and** MatterGuard's allowed tools.
* **Providers** - only via `ProviderGateway`, which re-checks MatterGuard's provider decision.

## Intent classification

`copilot/intent.py` uses ordered regular-expression rules (legal judgment and cross-matter checks first). Intent
only selects a workflow; it cannot grant access. References to another matter's name/number produce
`cross_matter_request`, which is refused without retrieval and logged as a security event.
