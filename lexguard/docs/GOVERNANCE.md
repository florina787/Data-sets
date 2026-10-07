# Governance

## Human-in-the-loop levels

| Level | Name | Applied when |
|---|---|---|
| 0 | AI prohibited | Client prohibits all AI (`POL-CLIENT-001`), or access denied |
| 1 | Retrieval / research only | Knowledge questions, research, policy questions, search |
| 2 | AI suggestions | Contract review, playbook comparison, extraction, verification |
| 3 | Drafting with mandatory lawyer review | Drafts, client drafts, legal-judgment support, any external destination |
| 4 | Approved bounded low-risk workflow | Level-1 knowledge/policy questions on LOW-risk matters |

No level permits autonomous legal judgment. Legal-judgment requests are routed to `HUMAN_LAWYER`.

## Approval rules (enforced in `governance/review.py`)

* Reviewer must have matter access and not be screened.
* Internal approval: Partner, Senior Associate or Associate. External approval: Partner or Senior Associate.
* Work product with any `ESCALATION_REQUIRED` playbook result: Partner only.
* External delivery: assurance status must be `PASS`, otherwise `409 ASSURANCE_GATE` and a `DELIVERY_BLOCKED` audit event.
* Decisions are final (`409 ALREADY_DECIDED`) and audited (`HUMAN_REVIEW_APPROVED/REJECTED`, `FINAL_STATUS`).

## Policy rules

| Rule | Effect | Meaning |
|---|---|---|
| ACC-002..005 | deny | Role lacks matter-content permission / not on named team / practice-group access |
| POL-WALL-001 | deny | Ethical wall screens the user |
| POL-CLIENT-001 | PROHIBIT | Client prohibits all AI |
| POL-CLIENT-002 | PROHIBIT | Client prohibits internal AI |
| POL-CLIENT-003 | PROHIBIT | Client prohibits external GenAI and provider is external |
| POL-CLIENT-004 | PROHIBIT | External provider not on client's approved list |
| POL-CLIENT-005 | RESTRICT | Documents above client's max external classification excluded |
| POL-PROV-000 | PROHIBIT | Provider not in registry |
| POL-PROV-001 | PROHIBIT | Provider not approved / not active |
| POL-PROV-002 | PROHIBIT | Provider not approved for the practice |
| POL-PROV-003 | PROHIBIT | Provider restricted on the matter |
| POL-PROV-004 | RESTRICT | Provider not cleared for the most sensitive documents |
| POL-RBAC-001 | PROHIBIT | Role may not send data to external providers |
| POL-DEST-001 | CONTROL | External delivery needs assurance PASS + senior approval |
| POL-DEST-002 | CONTROL | Privileged material in scope of an external delivery |
| POL-HR-001 | CONTROL | Client requires lawyer review |
| POL-RISK-001 | CONTROL | High-risk matter |
| POL-FIRM-002 | CONTROL | AI output is not advice until adopted by a lawyer |

## AI suitability formulas (`routing/suitability.py`)

Factors per task profile in [0, 1]: repeatability, legal judgment, knowledge retrieval, cross-system reasoning,
consequence, hallucination tolerance, source availability; plus volume (= min(1, docs/200)), external distribution
and client restriction.

```
ai_suitability     = 100·(.25 repeat + .20 volume + .20 retrieval + .15 sources + .20 (1-judgment)) − 15·restriction  (0 if AI prohibited)
agentic            = min(ai_suitability, 100·(.35 cross_system + .25 repeat + .20 (1-judgment) + .20 (1-consequence)))
legal_judgment_risk= 100·(.7 judgment + .3 consequence)
autonomy_risk      = 100·(.5 consequence + .3 judgment + .2 (1-hallucination_tolerance))
evidence_req       = 100·(.6 (1-hallucination_tolerance) + .4 external_distribution)
confidentiality    = 70·max_sensitivity/4 + 15·external_provider + 15·external_destination
privilege_risk     = min(100, 200·privileged_share + 40·[any privileged])
human_review_req   = max(25·review_level, .5 evidence + .5 legal_judgment_risk)
```

Bands: HIGH ≥ 70, MEDIUM ≥ 40, LOW < 40. Agentic routing would require agentic ≥ 70 *and* autonomy risk < 40.

## Assurance score

See README → Assurance. Weights are in `assurance/pipeline.py::WEIGHTS`. PASS ≥ 0.90 with zero partial,
unsupported or missing-source material propositions; FAIL < 0.75, policy non-compliance, or critical
confidentiality issue; otherwise REVIEW_REQUIRED.

## Evaluation gates

* Safety metrics (policy adherence, cross-matter isolation, refusal correctness, confidentiality behaviour): must be
  100 % and must not regress.
* Quality metrics: no regression greater than 2 points.
* Promotion: AI Governance role, only for runs whose gates passed; recorded in governance state (simulated deploy).

## ChangeOps

Deterministic parser maps policy text to `{output_types, destinations, requirements}`. Supported requirements:
citation verification, lawyer review, assurance, privilege review. Affected workflows are those whose outputs and
destinations intersect the change and whose gates lack the requirement. Regression checks run the real assurance
pipeline against an AI memo destined for external use. Approval (AI Governance) writes a gate overlay that the AI
Inventory reflects immediately.

## AI inventory

Applications, 15 agents, models (deterministic engines; optional Claude narration disabled in DEMO_MODE),
6 providers, 12 prompts, the RAG pipeline and 12 workflows — each with owner, version, risk, approval status,
last evaluation and deployment status (`GET /inventory`).
