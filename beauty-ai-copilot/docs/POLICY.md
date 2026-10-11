# Lifecycle and policy configuration

## States

`DRAFT, NEEDS_CLARIFICATION, REQUIREMENTS_APPROVED, IMPACT_REVIEW, DEVELOPMENT, EVALUATING, EVALUATION_FAILED,
EVALUATION_INCONCLUSIVE, REVIEW_REQUIRED, RELEASE_APPROVED, CANARY, MONITORING, RELEASED, ROLLBACK_RECOMMENDED,
ROLLED_BACK, CANCELLED, FAILED`. Terminal: `ROLLED_BACK`, `CANCELLED`, `FAILED`.

## Permitted transitions (generated from `app/lifecycle/state_machine.py`)

Every non-terminal state except `RELEASED` can also move to `CANCELLED` (authorized cancellation) or `FAILED`
(unrecoverable workflow error). Any other transition returns HTTP 409 `illegal_transition`.

| From | To | Backend prerequisite |
|---|---|---|
| DRAFT | NEEDS_CLARIFICATION | Requirements agent found unresolved ambiguities |
| DRAFT | REQUIREMENTS_APPROVED | No ambiguities and product owner approved the requirement version |
| NEEDS_CLARIFICATION | NEEDS_CLARIFICATION | Clarification answered; others remain |
| NEEDS_CLARIFICATION | REQUIREMENTS_APPROVED | All required clarifications answered and product owner approved the new requirement version |
| REQUIREMENTS_APPROVED | NEEDS_CLARIFICATION | Requirement re-opened |
| REQUIREMENTS_APPROVED | IMPACT_REVIEW | Evidence and impact agents completed with resolvable citations |
| IMPACT_REVIEW | DEVELOPMENT | Impact assessment accepted by an authorized owner |
| DEVELOPMENT | EVALUATING | Candidate registered with digest-verified artifact and code revision; evaluation config present |
| EVALUATING | EVALUATION_FAILED | Computed gates: at least one FAIL |
| EVALUATING | EVALUATION_INCONCLUSIVE | Computed gates: no FAIL but at least one INCONCLUSIVE |
| EVALUATING | REVIEW_REQUIRED | Computed gates: all PASS |
| EVALUATING | DEVELOPMENT | Evaluation job failed or was cancelled (computation, not policy) |
| EVALUATION_FAILED | DEVELOPMENT | New candidate registered |
| EVALUATION_INCONCLUSIVE | DEVELOPMENT | New candidate or configuration registered |
| EVALUATION_FAILED | EVALUATING | Re-evaluation requested after new candidate |
| EVALUATION_INCONCLUSIVE | EVALUATING | Re-evaluation requested |
| REVIEW_REQUIRED | DEVELOPMENT | Review rejected or new candidate registered |
| REVIEW_REQUIRED | EVALUATING | Re-evaluation requested (prior approvals invalidated) |
| REVIEW_REQUIRED | RELEASE_APPROVED | Required reviews approved; distinct release approver approved bound artifacts |
| RELEASE_APPROVED | REVIEW_REQUIRED | Approval invalidated, expired or rejected |
| RELEASE_APPROVED | CANARY | Approval revalidated immediately before simulated deployment |
| CANARY | MONITORING | Canary window observed with no open alert |
| MONITORING | RELEASED | All rollout stages completed with no open alert |
| CANARY | ROLLBACK_RECOMMENDED | Alert investigated; monitoring agent proposed rollback |
| MONITORING | ROLLBACK_RECOMMENDED | Alert investigated; monitoring agent proposed rollback |
| RELEASED | ROLLBACK_RECOMMENDED | Alert investigated; monitoring agent proposed rollback |
| ROLLBACK_RECOMMENDED | ROLLED_BACK | Authorized rollback approval and compatibility check passed |
| ROLLBACK_RECOMMENDED | MONITORING | Rollback rejected by authorized reviewer; monitoring continues |

The services check each prerequisite server-side before calling `transition()`, which re-checks the table and writes
an audit event naming the prerequisite.

## Release policy (`policies/release-policy-v2.1.json`, version `2.1-demo`)

> Illustrative demo rules for an independent prototype. They are **not** L’Oréal standards or scientifically
> established thresholds.

| Setting | Value |
|---|---|
| Minimum eligible paired samples per required cell | 100 |
| Maximum top-1 regression in any required cell | 2.0 pp |
| Minimum top-1 improvement in the target cell | 5.0 pp |
| Maximum coverage drop in any required cell | 3.0 pp |
| Threshold resolution | Stricter of policy and approved acceptance criteria (e.g. AC-3 = 150 samples → INCONCLUSIVE, tested) |
| Required reviews | code (non-author), domain, privacy |
| Separation of duties | Release approver ≠ revision author; code reviewer ≠ author; rollback approver ≠ requester |
| Approval TTL / use | 72 h, single use (nonce, `consumed_at`) |
| Evaluation max age | 14 days |
| Rollout stages | 5 % → 25 % → 100 % of simulated sessions (prototype settings); ≥ 1 window per stage, no open alert |
| Monitoring alert | ≥ 40 labels in a cohort cell, accuracy < reference − 10 pp, Wilson 95 % upper < reference |

## Gates

| Gate | Context | PASS when | Otherwise | Owner |
|---|---|---|---|---|
| G-CONFIG | evaluation | Evaluation config and policy present | INCONCLUSIVE | ml_engineer |
| G-ARTIFACT | evaluation | Registered digests = digests recomputed from files (baseline, candidate, dataset) | FAIL | ml_engineer |
| G-AMBIGUITY | evaluation | No open required clarification; requirement approved | INCONCLUSIVE | product_owner |
| G-EVIDENCE | evaluation | Required sources cited, current and resolvable | INCONCLUSIVE if missing; FAIL if a citation no longer resolves | domain_reviewer |
| G-SAMPLES | evaluation | Every required cell n ≥ minimum | INCONCLUSIVE | qa_engineer |
| G-TARGET | evaluation | Target Δ ≥ minimum | FAIL (INCONCLUSIVE if data insufficient) | product_owner |
| G-NO-REGRESSION | evaluation | Every sufficient cell Δ ≥ −max | FAIL (INCONCLUSIVE if any cell insufficient) | domain_reviewer |
| G-COVERAGE | evaluation | No cell coverage drop > max | FAIL | qa_engineer |
| G-ABSTENTION-DENOMINATOR | evaluation | Every eligible sample has a prediction record for both models; abstentions counted | FAIL | qa_engineer |
| G-CONTROLS | evaluation | All control tests PASS | FAIL | privacy_reviewer |
| G-EVALUATION | release | Latest run SUCCEEDED with PASS | FAIL / INCONCLUSIVE | release_manager |
| G-FRESHNESS | release | Run matches current candidate digest, requirement version, config, dataset, policy; age ≤ max | FAIL (stale) | release_manager |
| G-CODE-REVIEW | release | Approved non-author code review bound to the current diff digest | INCONCLUSIVE / FAIL | qa_engineer |
| G-REVIEWS | release | Domain and privacy APPROVE bound to the current binding | INCONCLUSIVE / FAIL | release_manager |
| G-APPROVAL | deploy | Approved, unexpired, unused, not invalidated, binding digest matches, approver ≠ author | FAIL → approval invalidated, back to REVIEW_REQUIRED | release_manager |

Overall = FAIL if any FAIL, else INCONCLUSIVE if any INCONCLUSIVE (or no gates), else PASS. Insufficient data can never
yield PASS. Recommendation (release agent) is separate from authorization (release manager).

## Approval binding

Reviews and release approvals are bound to: requirement version, candidate model ID and **artifact digest**, code
revision and diff digest, dataset snapshot and digest, evaluation config and digest, latest evaluation run, policy
version and digest, and deployment target. The binding is recomputed at check time. Registering a new candidate or
re-evaluating invalidates prior reviews and approvals, with an audited reason. Changing any bound file (tested:
predictions, policy) blocks deployment at revalidation.
