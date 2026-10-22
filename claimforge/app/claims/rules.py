"""Business-rule catalog (DETERMINISTIC).

Each rule has a stable identifier that appears on every adjudication result, in the
traceability graph and in ClaimIQ evidence. Rule logic itself lives in
:mod:`app.claims.adjudicator`; rule *parameters* live in :mod:`app.claims.rulesets`.
"""

from __future__ import annotations

from app.models.domain import BusinessRule, ReasonCode

ELIG_RULE = "ELIG_RULE_001"
EFF_RULE = "EFF_RULE_005"
COV_RULE = "COV_RULE_010"
PROV_RULE = "PROV_RULE_020"
DUP_RULE = "DUP_RULE_030"
REIMB_RULE = "REIMB_RULE_050"
VIS_RULE = "VIS_RULE_070"
BEN_RULE = "BEN_RULE_090"
AUTH_RULE = "AUTH_RULE_184"

RULE_CATALOG: dict[str, BusinessRule] = {
    ELIG_RULE: BusinessRule(rule_id=ELIG_RULE, name="Member eligibility",
                            description="Member coverage must be active on the date of service.",
                            policy_section="P-01.2"),
    EFF_RULE: BusinessRule(rule_id=EFF_RULE, name="Policy effective date",
                           description="Date of service must be on/after the policy effective date.",
                           policy_section="P-02.2"),
    PROV_RULE: BusinessRule(rule_id=PROV_RULE, name="Provider eligibility",
                            description="Provider must be registered and not suspended.",
                            policy_section="P-12.1"),
    COV_RULE: BusinessRule(rule_id=COV_RULE, name="Benefit coverage",
                           description="Benefit must be covered by the member's plan.",
                           policy_section="P-10.1"),
    DUP_RULE: BusinessRule(rule_id=DUP_RULE, name="Duplicate claim",
                           description="Same member/provider/benefit/procedure/date is a duplicate.",
                           policy_section="P-30.1"),
    VIS_RULE: BusinessRule(rule_id=VIS_RULE, name="Visit limit",
                           description="Completed visits per benefit year must not exceed the limit.",
                           policy_section="P-16.2"),
    AUTH_RULE: BusinessRule(rule_id=AUTH_RULE, name="Physiotherapy prior-authorization threshold",
                            description="Authorization required once the counted completed visits in the "
                                        "benefit year reach the threshold.",
                            policy_section="P-14.3"),
    REIMB_RULE: BusinessRule(rule_id=REIMB_RULE, name="Reimbursement calculation",
                             description="Reimbursement = pct x min(billed, fee schedule max).",
                             policy_section="P-01.4"),
    BEN_RULE: BusinessRule(rule_id=BEN_RULE, name="Annual benefit maximum",
                           description="Reimbursement capped by remaining annual maximum.",
                           policy_section="P-14.2"),
}

REASON_TO_RULE: dict[ReasonCode, str] = {
    ReasonCode.MEMBER_INELIGIBLE: ELIG_RULE,
    ReasonCode.POLICY_NOT_EFFECTIVE: EFF_RULE,
    ReasonCode.PROVIDER_INELIGIBLE: PROV_RULE,
    ReasonCode.NOT_COVERED: COV_RULE,
    ReasonCode.DUPLICATE: DUP_RULE,
    ReasonCode.VISIT_LIMIT_EXCEEDED: VIS_RULE,
    ReasonCode.AUTH_REQUIRED: AUTH_RULE,
    ReasonCode.BENEFIT_MAX_REACHED: BEN_RULE,
    ReasonCode.PAID_CAPPED: BEN_RULE,
    ReasonCode.PAID: REIMB_RULE,
}
