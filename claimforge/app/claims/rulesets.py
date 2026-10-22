"""Versioned, immutable rulesets (DETERMINISTIC configuration).

* ``RULESET_V1``            — current production policy (release 2.3): physio max $750, no auth.
* ``RULESET_V2``            — BR-391 as specified: physio max $1,000, auth required once
                              10 COMPLETED visits exist (i.e. from visit 11 onward).
* ``RULESET_V2_DEFECTIVE``  — CONTROLLED SYNTHETIC DEFECT used by the ClaimIQ demo: the
                              visit counter counts COMPLETED + CANCELLED visits.
* ``RULESET_V2_1``          — hotfix proposed by the Remediation agent (same as V2 spec).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date

from app.models.domain import BenefitType

POLICY_EFFECTIVE_DATE = date(2026, 1, 1)


@dataclass(frozen=True)
class BenefitRule:
    benefit_type: BenefitType
    reimbursement_pct: float
    annual_max: float
    per_visit_allowed_max: float
    max_visits: int | None = None
    # Authorization required when counted prior visits >= this value.
    # 10 => visits 1..10 exempt, visit 11 onward requires authorization.
    auth_after_completed_visits: int | None = None
    count_cancelled_visits: bool = False


@dataclass(frozen=True)
class RuleSet:
    ruleset_id: str
    version: str
    description: str
    benefits: dict[BenefitType, BenefitRule]
    policy_effective_date: date = POLICY_EFFECTIVE_DATE
    source_requirements: tuple[str, ...] = ()
    changed_rules: tuple[str, ...] = ()
    synthetic_defect: bool = False
    tags: tuple[str, ...] = field(default_factory=tuple)

    def benefit(self, benefit_type: BenefitType) -> BenefitRule:
        return self.benefits[benefit_type]

    def to_dict(self) -> dict:
        return {
            "ruleset_id": self.ruleset_id,
            "version": self.version,
            "description": self.description,
            "policy_effective_date": self.policy_effective_date.isoformat(),
            "source_requirements": list(self.source_requirements),
            "changed_rules": list(self.changed_rules),
            "synthetic_defect": self.synthetic_defect,
            "benefits": {
                bt.value: {
                    "reimbursement_pct": br.reimbursement_pct,
                    "annual_max": br.annual_max,
                    "per_visit_allowed_max": br.per_visit_allowed_max,
                    "max_visits": br.max_visits,
                    "auth_after_completed_visits": br.auth_after_completed_visits,
                    "count_cancelled_visits": br.count_cancelled_visits,
                }
                for bt, br in self.benefits.items()
            },
        }


_BASE_BENEFITS = {
    BenefitType.PHYSIOTHERAPY: BenefitRule(BenefitType.PHYSIOTHERAPY, 0.80, 750.0, 120.0),
    BenefitType.CHIROPRACTIC: BenefitRule(BenefitType.CHIROPRACTIC, 0.80, 500.0, 90.0),
    BenefitType.MASSAGE_THERAPY: BenefitRule(BenefitType.MASSAGE_THERAPY, 0.80, 500.0, 100.0, max_visits=20),
    BenefitType.ACUPUNCTURE: BenefitRule(BenefitType.ACUPUNCTURE, 0.80, 400.0, 90.0),
}

RULESET_V1 = RuleSet(
    ruleset_id="RULESET_V1",
    version="2.3",
    description="Current production policy: physiotherapy 80%, $750 annual max, no authorization.",
    benefits=dict(_BASE_BENEFITS),
    source_requirements=("BR-377",),
)


def derive_ruleset(
    base: RuleSet,
    ruleset_id: str,
    version: str,
    description: str,
    benefit_type: BenefitType,
    *,
    annual_max: float | None = None,
    reimbursement_pct: float | None = None,
    auth_after_completed_visits: int | None = None,
    count_cancelled_visits: bool | None = None,
    max_visits: int | None = None,
    source_requirements: tuple[str, ...] = (),
    changed_rules: tuple[str, ...] = (),
    synthetic_defect: bool = False,
) -> RuleSet:
    """Create a new immutable ruleset by changing parameters for one benefit."""
    current = base.benefits[benefit_type]
    changes = {}
    if annual_max is not None:
        changes["annual_max"] = float(annual_max)
    if reimbursement_pct is not None:
        changes["reimbursement_pct"] = float(reimbursement_pct)
    if auth_after_completed_visits is not None:
        changes["auth_after_completed_visits"] = int(auth_after_completed_visits)
    if count_cancelled_visits is not None:
        changes["count_cancelled_visits"] = bool(count_cancelled_visits)
    if max_visits is not None:
        changes["max_visits"] = int(max_visits)
    benefits = dict(base.benefits)
    benefits[benefit_type] = replace(current, **changes)
    return RuleSet(
        ruleset_id=ruleset_id,
        version=version,
        description=description,
        benefits=benefits,
        policy_effective_date=base.policy_effective_date,
        source_requirements=source_requirements,
        changed_rules=changed_rules,
        synthetic_defect=synthetic_defect,
    )


RULESET_V2 = derive_ruleset(
    RULESET_V1, "RULESET_V2", "2.4",
    "BR-391 as specified: physiotherapy $1,000 max; authorization from the 11th completed visit.",
    BenefitType.PHYSIOTHERAPY,
    annual_max=1000.0, auth_after_completed_visits=10, count_cancelled_visits=False,
    source_requirements=("BR-391",), changed_rules=("BEN_RULE_090", "AUTH_RULE_184"),
)

RULESET_V2_DEFECTIVE = derive_ruleset(
    RULESET_V1, "RULESET_V2_DEFECTIVE", "2.4",
    "CONTROLLED SYNTHETIC DEFECT: release 2.4 build counts COMPLETED + CANCELLED visits.",
    BenefitType.PHYSIOTHERAPY,
    annual_max=1000.0, auth_after_completed_visits=10, count_cancelled_visits=True,
    source_requirements=("BR-391",), changed_rules=("BEN_RULE_090", "AUTH_RULE_184"),
    synthetic_defect=True,
)

RULESET_V2_1 = derive_ruleset(
    RULESET_V1, "RULESET_V2_1", "2.4.1",
    "Proposed hotfix: AUTH_RULE_184 counts COMPLETED visits only.",
    BenefitType.PHYSIOTHERAPY,
    annual_max=1000.0, auth_after_completed_visits=10, count_cancelled_visits=False,
    source_requirements=("BR-391",), changed_rules=("AUTH_RULE_184",),
)

RULESETS: dict[str, RuleSet] = {
    rs.ruleset_id: rs for rs in (RULESET_V1, RULESET_V2, RULESET_V2_DEFECTIVE, RULESET_V2_1)
}


def get_ruleset(ruleset_id: str) -> RuleSet:
    try:
        return RULESETS[ruleset_id]
    except KeyError as exc:
        raise ValueError(f"Unknown ruleset '{ruleset_id}'. Known: {sorted(RULESETS)}") from exc


def diff_rulesets(a: RuleSet, b: RuleSet) -> list[dict]:
    """Parameter-level diff between two rulesets (used by release correlation)."""
    out: list[dict] = []
    for bt in a.benefits:
        ra, rb = a.benefits[bt], b.benefits[bt]
        for param in ("reimbursement_pct", "annual_max", "per_visit_allowed_max", "max_visits",
                      "auth_after_completed_visits", "count_cancelled_visits"):
            va, vb = getattr(ra, param), getattr(rb, param)
            if va != vb:
                rule = "AUTH_RULE_184" if param.startswith(("auth", "count")) else (
                    "BEN_RULE_090" if param == "annual_max" else
                    "VIS_RULE_070" if param == "max_visits" else "REIMB_RULE_050")
                out.append({"benefit_type": bt.value, "parameter": param, "from": va, "to": vb, "rule_id": rule})
    return out
