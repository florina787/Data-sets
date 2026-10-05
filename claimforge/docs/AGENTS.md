# ClaimForge Agents

> In DEMO_MODE every agent's reasoning is a **deterministic planner or template**, labelled as such. In live mode
> (`DEMO_MODE=false` plus a key), an LLM may only **rephrase narratives**, labelled LLM-ASSISTED. No agent
> adjudicates claims, decides anomalies, deploys code or modifies production.

The 12 agents live in `app/agents/`. All of them extend `BaseAgent` (audit plus metrics) and receive an
`AgentContext`.

---

### 1. Supervisor Agent (`supervisor.py`)
- **Purpose:** Understand the request, choose the workflow, publish the budgets, and screen the request for prompt injection.
- **Input:** request text, persona, optional explicit workflow.
- **Output:** one of `SDLC_CLOSED_LOOP`, `POLICY_QA` or `CLAIMIQ_INVESTIGATION`, plus the screen result and limits.
- **Tools:** none (deterministic keyword routing).
- **When invoked:** First node of every run.
- **When not invoked:** Never skipped.
- **Failure handling:** An unknown workflow falls back to `SDLC_CLOSED_LOOP`. Flagged injection is treated as data and never changes routing.
- **Human approval:** Not required.

### 2. BA / Requirement Agent (`requirement_agent.py` → `app/requirements/analyzer.py`)
- **Purpose:** Turn natural language into a structured requirement: parameters, user stories, business rules,
  Given/When/Then acceptance criteria, assumptions, ambiguities, missing information and dependencies.
- **Input:** request text and human clarifications.
- **Output:** a `Requirement`, for example `BR-391`.
- **Tools:** the deterministic parser and the requirement catalog.
- **When invoked:** SDLC workflow.
- **When not invoked:** Policy Q&A and ClaimIQ investigations.
- **Failure handling:** Unrecognised requests get a blocking `AMB-UNSTRUCTURED` ambiguity. Rules are never invented.
- **Human approval:** **Required when a CRITICAL ambiguity exists**, such as the auth threshold or visit statuses.

### 3. Policy Agent (`policy_agent.py`)
- **Purpose:** RAG over the synthetic policies. It returns cited evidence and runs consistency, conflict and amendment checks.
- **Input:** a Requirement, or a free-text query.
- **Output:** evidence with citations, findings (`CONSISTENT`, `CONFLICT`, `AMENDMENT_REQUIRED`, `DEPENDENCY`, `DEFINITION`), and a status.
- **Tools:** the BM25 retriever.
- **When invoked:** After the requirement step, and for policy Q&A.
- **When not invoked:** ClaimIQ investigations, which use the traceability graph instead.
- **Failure handling:** When nothing matches, it returns `INSUFFICIENT POLICY EVIDENCE`, never a fabricated clause.
- **Human approval:** Not required. Governance FAILs when evidence is missing.

### 4. Impact Analysis Agent (`impact_agent.py`)
- **Purpose:** Build the requirement → component impact map across services, APIs, tables, events, queues, rules,
  tests, monitoring, docs, communications and analytics.
- **Input:** a Requirement and the architecture catalog.
- **Output:** impacts (KEEP / ENHANCE / ADD / REPLACE, with a reason and DIRECT / INDIRECT / NEW kind), a summary and a tree.
- **Tools:** the facet matcher and one-hop dependency propagation.
- **When invoked:** After the ambiguity gate passes.
- **When not invoked:** While the ambiguity is unresolved.
- **Failure handling:** An empty facet set yields an empty map, which raises the release risk.
- **Human approval:** Not required.

### 5. Architecture Agent (`architecture_agent.py`)
- **Purpose:** Produce KEEP/ENHANCE/ADD/REPLACE recommendations, the current and target architecture, and the FHIR mapping.
- **Input:** impacts.
- **Output:** recommendations, principles, Mermaid diagrams and a `human_review_required` flag.
- **Tools:** the guardrailed template.
- **When invoked:** After impact analysis.
- **When not invoked:** Policy Q&A and ClaimIQ.
- **Failure handling:** Raises `ArchitectureGuardrailViolation` if anything would replace a deterministic engine.
- **Human approval:** **Required for ADD/REPLACE**, which is flagged.

### 6. Developer Agent (`developer_agent.py`)
- **Purpose:** Produce the implementation plan and supporting material:
  - affected files in the synthetic repositories
  - pseudocode and a code patch
  - API and schema changes
  - migration considerations and documentation list
- **Input:** a Requirement and impacts.
- **Output:** a `development_plan` labelled *DETERMINISTIC TEMPLATE — proposal only*.
- **Tools:** none.
- **When invoked:** After architecture.
- **When not invoked:** ClaimIQ.
- **Failure handling:** The plan degrades gracefully when facets are missing.
- **Human approval:** Nothing is merged or deployed automatically.

### 7. QA Agent (`qa_agent.py` → `app/qa/test_generator.py`)
- **Purpose:** Generate unit, boundary, negative, regression and API tests, with visit 10/11, annual-maximum edges,
  cancelled visits and effective dates as the focus. It then **executes** the cases against the proposed ruleset.
- **Input:** a Requirement.
- **Output:** cases, results, a summary and the boundary list.
- **Tools:** the deterministic engine.
- **When invoked:** After the development plan.
- **When not invoked:** While the ambiguity is unresolved.
- **Failure handling:** Failed or critical tests flow into release risk and can block the release.
- **Human approval:** Not required.

### 8. Security / Privacy Agent (`security_agent.py`)
- **Purpose:** An advisory review of PHI, RBAC, audit, data changes, prompt injection, secrets, logging, tool
  permissions, encryption assumptions and retention.
- **Input:** requirement, impacts, settings and the request screen.
- **Output:** findings with severity, checks and a disclaimer.
- **Tools:** rules.
- **When invoked:** After simulation.
- **When not invoked:** ClaimIQ.
- **Failure handling:** A CRITICAL finding blocks the release.
- **Human approval:** Findings are reviewed by humans. No compliance certification is claimed.

### 9. Compliance / Governance Agent (`governance_agent.py`)
- **Purpose:** An evidence checklist covering:
  - explainability and policy traceability
  - human oversight and model risk
  - test and simulation evidence
  - the audit log
- **Input:** workflow state.
- **Output:** PASS / WARN / FAIL items with evidence.
- **Tools:** none.
- **When invoked:** Before the release assessment.
- **When not invoked:** ClaimIQ.
- **Failure handling:** Each FAIL adds risk, and any FAIL makes the release NOT READY.
- **Human approval:** Compliance Reviewer sign-off for READY WITH APPROVAL.

### 10. Release Agent (`release_agent.py` → `app/release/risk.py`)
- **Purpose:** A deterministic risk score with component scores, and a READY / READY WITH APPROVAL / NOT READY /
  BLOCKED decision backed by evidence. It also produces the release notes and rollback plan.
- **Input:** impact, tests, simulation, security, governance and ambiguity.
- **Output:** `ReleaseRisk` and `release_assessment`.
- **Tools:** the risk engine.
- **When invoked:** End of the SDLC pre-release phase.
- **When not invoked:** ClaimIQ.
- **Failure handling:** BLOCKED or NOT READY routes to `return_evidence` and stops.
- **Human approval:** **Always required to deploy.** `deploy_release` is a consequential tool with no agent on its allowlist.

### 11. Root-Cause Agent (`root_cause_agent.py` → `app/rootcause/tools.py`)
- **Purpose:** Investigate ClaimIQ anomalies and produce evidence-backed hypotheses.
- **Input:** production context and anomalies.
- **Output:** a `RootCause` containing release, rule, requirement and policy, the likely defect, a confidence score,
  evidence, five hypotheses, affected claims and a trace path.
- **Tools (allow-listed, budgeted):** `segment_metrics`, `denial_reason_shift`, `correlate_release`,
  `trace_rule_to_requirement`, `inspect_affected_claims`, `run_regression_suite`, `check_operational_health`.
- **When invoked:** Only when the statistical detector reports an anomaly.
- **When not invoked:** On a healthy release.
- **Failure handling:** Hitting `MAX_AGENT_ITERATIONS`, `MAX_TOOL_CALLS` or the timeout ends the run INCONCLUSIVE
  with LOW confidence. No defect is generated in that case.
- **Human approval:** Findings go to humans, and nothing is changed.

### 12. Remediation Agent (`remediation_agent.py`)
- **Purpose:** Propose a fix and **verify** it in simulation. Candidates are tried in a bounded loop: forward fix
  first, rollback second.
- **Input:** the root cause and production context.
- **Output:** a `Remediation` covering:
  - the change and its configuration
  - a code patch and extra validation
  - a runnable regression test
  - rollback versus forward fix
  - claims to reprocess and the verification evidence
- **Tools:** the deterministic replay and the test executor.
- **When invoked:** After a CONCLUDED root cause.
- **When not invoked:** After an INCONCLUSIVE investigation.
- **Failure handling:** If no candidate verifies, it falls back to rollback flagged *UNVERIFIED*.
- **Human approval:** **Required.** Status stays `PROPOSED`, and reprocessing needs approval (O-05.2).

---

## Deterministic (non-agent) nodes

`app/graph/nodes.py` holds the parts of the system where an LLM must not be used:
- `ambiguity_check` and `human_review`
- `simulation`
- `human_approval` and `simulated_release`
- `claimiq_monitoring` and `anomaly_check`
- `release_correlation`, which verifies the chain through the traceability graph
- `qa_regression`, `defect` and `sdlc_feedback`
