# Use Case Catalog

> Generated from `app/catalog/use_cases.py` (the same catalog the UI and `GET /use-cases` serve).
> SYNTHETIC DEMO — statuses are deliberately conservative.

| Status | Meaning |
|---|---|
| **IMPLEMENTED** | Runs end-to-end in this repository (DEMO_MODE, synthetic data). |
| **PARTIAL** | Real but limited implementation (limits stated in the Note column). |
| **PLANNED** | Not implemented. Interface or mapping only. |

**Totals:** 30 implemented · 8 partial · 2 planned.


## Plan / Requirements

| ID | Use case | Agent / engine | Status | Demo available | Where | Note |
|---|---|---|---|---|---|---|
| UC01 | Requirement understanding | Requirement Agent (deterministic parser) | **IMPLEMENTED** | Yes | Copilot, Requirements |  |
| UC02 | Ambiguity detection | Requirement Agent + ambiguity gate | **IMPLEMENTED** | Yes | Requirements | CRITICAL ambiguity blocks workflow → human clarification |
| UC03 | User-story generation | Requirement Agent (template) | **IMPLEMENTED** | Yes | Requirements |  |
| UC04 | Acceptance-criteria generation | Requirement Agent (template) | **IMPLEMENTED** | Yes | Requirements | Given/When/Then |
| UC05 | Policy-to-requirement validation | Policy Agent (BM25 RAG + checks) | **IMPLEMENTED** | Yes | Policy Evidence | consistency / amendment / dependency findings |

## Architecture / Impact

| ID | Use case | Agent / engine | Status | Demo available | Where | Note |
|---|---|---|---|---|---|---|
| UC06 | Application impact analysis | Impact Agent | **IMPLEMENTED** | Yes | Impact Analysis |  |
| UC07 | Microservice dependency analysis | Impact Agent (dependency propagation) | **PARTIAL** | Yes | Impact Analysis | one-hop propagation over synthetic catalog |
| UC08 | API impact analysis | Impact Agent | **IMPLEMENTED** | Yes | Impact Analysis |  |
| UC09 | Database/schema impact analysis | Impact Agent | **IMPLEMENTED** | Yes | Impact Analysis |  |
| UC10 | Architecture recommendation | Architecture Agent (guardrailed) | **IMPLEMENTED** | Yes | Architecture | KEEP/ENHANCE/ADD/REPLACE |

## Development

| ID | Use case | Agent / engine | Status | Demo available | Where | Note |
|---|---|---|---|---|---|---|
| UC11 | Implementation-plan generation | Developer Agent (template) | **IMPLEMENTED** | Yes | Development Plan |  |
| UC12 | Code-change proposal | Developer Agent (template) | **PARTIAL** | Yes | Development Plan | template patch for a synthetic repo; never merged |
| UC13 | API/schema proposal | Developer Agent (template) | **IMPLEMENTED** | Yes | Development Plan |  |
| UC14 | Technical documentation generation | Developer/Release Agents (template) | **PARTIAL** | Yes | Development Plan, Release Center | doc-update list + release notes only |

## QA / Claim Simulation

| ID | Use case | Agent / engine | Status | Demo available | Where | Note |
|---|---|---|---|---|---|---|
| UC15 | Unit-test generation | QA Agent | **IMPLEMENTED** | Yes | QA & Tests | executed against the rules engine |
| UC16 | API-test generation | QA Agent | **PARTIAL** | Yes | QA & Tests | API test specs generated; not auto-executed |
| UC17 | Regression-test selection | Impact + QA Agents | **PARTIAL** | Yes | Impact Analysis, QA & Tests | indirect components flagged for regression scope; no optimisation |
| UC18 | Boundary-test generation | QA Agent | **IMPLEMENTED** | Yes | QA & Tests | visit 10/11, annual max, effective date |
| UC19 | Synthetic claim generation | Seeded generator (deterministic) | **IMPLEMENTED** | Yes | Claims Simulation | 1k–100k claims |
| UC20 | Historical/synthetic claims replay | Simulator (shadow replay) | **IMPLEMENTED** | Yes | Claims Simulation, ClaimIQ | synthetic replay only — no real history |
| UC21 | Expected-vs-actual adjudication comparison | Comparison engine | **IMPLEMENTED** | Yes | Claims Simulation | expected vs UNEXPECTED change classification |

## Security / Governance

| ID | Use case | Agent / engine | Status | Demo available | Where | Note |
|---|---|---|---|---|---|---|
| UC22 | PHI/privacy review | Security Agent (rule-based) | **PARTIAL** | Yes | Security & Governance | advisory; not a compliance assessment |
| UC23 | Security review | Security Agent (rule-based) | **PARTIAL** | Yes | Security & Governance | advisory; no SAST/DAST |
| UC24 | Governance evidence generation | Governance Agent | **IMPLEMENTED** | Yes | Security & Governance |  |
| UC25 | Audit/traceability review | Audit log + traceability graph | **IMPLEMENTED** | Yes | Traceability, System Metrics |  |

## Release

| ID | Use case | Agent / engine | Status | Demo available | Where | Note |
|---|---|---|---|---|---|---|
| UC26 | Release-risk scoring | Release Agent (deterministic risk engine) | **IMPLEMENTED** | Yes | Release Center |  |
| UC27 | Deployment-readiness assessment | Release Agent | **IMPLEMENTED** | Yes | Release Center | READY / READY WITH APPROVAL / NOT READY / BLOCKED |
| UC28 | Release-note generation | Release Agent (template) | **IMPLEMENTED** | Yes | Release Center |  |
| UC29 | Rollback-plan generation | Release Agent (template) | **IMPLEMENTED** | Yes | Release Center |  |

## ClaimIQ / Production

| ID | Use case | Agent / engine | Status | Demo available | Where | Note |
|---|---|---|---|---|---|---|
| UC30 | Claim-denial monitoring | ClaimIQ metrics | **IMPLEMENTED** | Yes | ClaimIQ | SIMULATED production |
| UC31 | Denial anomaly detection | Statistical detector | **IMPLEMENTED** | Yes | ClaimIQ | relative change + z-score |
| UC32 | Claims anomaly detection | Statistical detector | **PARTIAL** | Yes | ClaimIQ | denial & auth metrics alerted; latency/exceptions monitored only |
| UC33 | Production incident investigation | Root-Cause Agent | **IMPLEMENTED** | Yes | Root Cause |  |
| UC34 | Root-cause analysis | Root-Cause Agent (bounded loop) | **IMPLEMENTED** | Yes | Root Cause |  |
| UC35 | Release-to-incident correlation | Root-Cause Agent + correlation node | **IMPLEMENTED** | Yes | Root Cause |  |
| UC36 | Requirement-to-defect traceability | Traceability graph | **IMPLEMENTED** | Yes | Traceability |  |
| UC37 | Remediation recommendation | Remediation Agent (verified in simulation) | **IMPLEMENTED** | Yes | Root Cause | never applied automatically |
| UC38 | Regression-test generation from production failure | Remediation + QA | **IMPLEMENTED** | Yes | Root Cause | runnable pytest code |

## Integrations

| ID | Use case | Agent / engine | Status | Demo available | Where | Note |
|---|---|---|---|---|---|---|
| UC39 | Defect sync to Jira / Azure DevOps | Tracker adapter | **PLANNED** | No | - | adapter interface only; not connected |
| UC40 | FHIR Claim / ExplanationOfBenefit ingestion | FHIR adapter | **PLANNED** | No | - | mapping documented; not implemented |
