"""Requirement analysis engine (DETERMINISTIC parsing + rule templates).

Converts a natural-language benefit change request into a structured requirement:
parameters, business rules, user stories, Given/When/Then acceptance criteria,
assumptions, ambiguities, missing information and dependencies.

It never silently invents business rules: when wording is ambiguous (e.g. "after 10
visits") a CRITICAL ambiguity is raised and the workflow is routed to human review.
In live AI mode an LLM may *rephrase* the narrative; it does not change these outputs.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from app.claims.rulesets import RULESET_V1, RULESET_V2, RuleSet, derive_ruleset
from app.config.settings import SYNTHETIC_DATA_DIR
from app.models.domain import (
    AcceptanceCriterion,
    Ambiguity,
    BenefitType,
    BusinessRule,
    Requirement,
    Severity,
)
from app.simulation.comparison import ChangeSpec

BENEFIT_KEYWORDS = {
    BenefitType.PHYSIOTHERAPY: ("physiotherapy", "physio", "physical therapy"),
    BenefitType.CHIROPRACTIC: ("chiropractic", "chiropractor", "chiro"),
    BenefitType.MASSAGE_THERAPY: ("massage",),
    BenefitType.ACUPUNCTURE: ("acupuncture",),
}
_MONEY = r"\$?\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?"
_FROM_TO_RE = re.compile(rf"from\s+{_MONEY}\s+to\s+{_MONEY}", re.IGNORECASE)
_TO_ONLY_RE = re.compile(rf"(?:maximum|max|limit|coverage)[^.$]*?\bto\s+{_MONEY}", re.IGNORECASE)
_PCT_RE = re.compile(r"(\d{1,3})\s?%", re.IGNORECASE)
_AUTH_WORD_RE = re.compile(r"(?:prior\s+)?(?:authori[sz]ation|pre-?auth\w*|\bauth\b|pre-?approval)", re.IGNORECASE)
_THRESH_RE = re.compile(
    r"\b(after|beyond|over|exceeding|more than|from|starting with|starting at|starting from|beginning with|"
    r"beginning at|on|for)\s+(?:the\s+)?(?:visit\s+(?:number\s+)?)?(\d{1,3})(st|nd|rd|th)?"
    r"(\s+completed)?(\s+(?:physio\w*\s+)?visits?)?(\s+(?:and\s+)?onwards?)?",
    re.IGNORECASE,
)
_DATE_RE = re.compile(r"effective\s+(?:on\s+|from\s+)?(\d{4}-\d{2}-\d{2}|[A-Z][a-z]+\s+\d{1,2},?\s+\d{4})", re.IGNORECASE)

AMB_THRESHOLD = "AMB-AUTH-THRESHOLD"
AMB_VISIT_STATUS = "AMB-VISIT-STATUS"
AMB_EFFECTIVE = "AMB-EFFECTIVE-DATE"
AMB_YTD = "AMB-YTD-ACCUMULATOR"
AMB_PLAN_SCOPE = "AMB-PLAN-SCOPE"
AMB_GRANDFATHER = "AMB-IN-FLIGHT-MEMBERS"
AMB_UNSTRUCTURED = "AMB-UNSTRUCTURED"

THRESHOLD_OPTIONS = {
    "FROM_VISIT_11": "Authorization required from visit 11 onward (the first 10 completed visits are exempt).",
    "ON_VISIT_10": "Authorization required starting on visit 10 (first 9 completed visits exempt).",
}
VISIT_STATUS_OPTIONS = {
    "COMPLETED_ONLY": "Count COMPLETED visits only (cancelled / no-show excluded, per policy P-01.3).",
    "ALL_SCHEDULED": "Count all scheduled appointments including cancelled visits.",
}

# The canonical demo request (used by UI examples, tests and docs).
DEMO_REQUIREMENT = ("Increase physiotherapy annual coverage from $750 to $1,000 and require prior "
                    "authorization after 10 completed visits.")
DEMO_REQUIREMENT_EXPLICIT = ("Increase physiotherapy annual coverage from $750 to $1,000 and require prior "
                             "authorization starting with the 11th completed visit.")
DEMO_CLARIFICATIONS = {AMB_THRESHOLD: "FROM_VISIT_11"}


def _money(whole: str, cents: str | None) -> float:
    return float(whole.replace(",", "")) + (float(f"0.{cents}") if cents else 0.0)


def load_requirement_catalog() -> list[dict]:
    path = SYNTHETIC_DATA_DIR / "requirements" / "requirements.json"
    return json.loads(path.read_text(encoding="utf-8"))["requirements"]


@dataclass
class _Parsed:
    benefit: BenefitType | None
    old_max: float | None
    new_max: float | None
    pct: float | None
    auth_mentioned: bool
    threshold_n: int | None
    threshold_prep: str | None
    threshold_explicit_threshold: int | None  # unambiguous threshold value if wording is explicit
    completed_mentioned: bool
    effective_date: str | None
    plan_mentioned: bool


def _parse(text: str) -> _Parsed:
    low = text.lower()
    benefit = None
    for bt, words in BENEFIT_KEYWORDS.items():
        if any(w in low for w in words):
            benefit = bt
            break
    old_max = new_max = None
    if m := _FROM_TO_RE.search(text):
        old_max, new_max = _money(m.group(1), m.group(2)), _money(m.group(3), m.group(4))
    elif m := _TO_ONLY_RE.search(text):
        new_max = _money(m.group(1), m.group(2))
    pct = None
    if "reimburs" in low and (m := _PCT_RE.search(text)):
        pct = int(m.group(1)) / 100.0
    auth_m = _AUTH_WORD_RE.search(text)
    threshold_n = prep = explicit = None
    completed = "completed" in low
    if auth_m:
        tail = text[auth_m.end():]
        if tm := _THRESH_RE.search(tail):
            prep = tm.group(1).lower()
            threshold_n = int(tm.group(2))
            ordinal = bool(tm.group(3))
            onward = bool(tm.group(6))
            if prep in {"from", "starting with", "starting at", "starting from", "beginning with", "beginning at", "on", "for"} and (ordinal or onward or "visit" in tm.group(0).lower()):
                explicit = threshold_n - 1  # "from the 11th visit" ⇒ 10 prior visits exempt
    effective = m.group(1) if (m := _DATE_RE.search(text)) else None
    plan_mentioned = bool(re.search(r"\b(plan|plans|bronze|silver|gold)\b", low))
    return _Parsed(benefit, old_max, new_max, pct, bool(auth_m), threshold_n, prep, explicit, completed,
                   effective, plan_mentioned)


def analyze_requirement_text(text: str, clarifications: dict[str, str] | None = None,
                             base: RuleSet = RULESET_V1) -> Requirement:
    clarifications = dict(clarifications or {})
    p = _parse(text)
    facets: list[str] = []
    params: dict = {"benefit_type": p.benefit.value if p.benefit else None}
    ambiguities: list[Ambiguity] = []
    assumptions: list[str] = []
    missing: list[str] = []
    rules: list[BusinessRule] = []
    acs: list[AcceptanceCriterion] = []
    stories: list[str] = []
    deps: list[str] = []

    cur_rule = base.benefits.get(p.benefit) if p.benefit else None
    if p.benefit and p.new_max is not None:
        facets.append("BENEFIT_LIMIT_CHANGE")
        params["current_annual_max"] = cur_rule.annual_max
        params["stated_current_annual_max"] = p.old_max
        params["proposed_annual_max"] = p.new_max
    if p.benefit and p.pct is not None:
        facets.append("REIMBURSEMENT_CHANGE")
        params["current_reimbursement_pct"] = cur_rule.reimbursement_pct
        params["proposed_reimbursement_pct"] = p.pct
    if p.benefit and p.auth_mentioned and p.threshold_n is not None:
        facets += ["AUTH_THRESHOLD_ADD", "VISIT_COUNTING"]
        params["auth_threshold_wording"] = f"{p.threshold_prep} {p.threshold_n}"

    if not facets:
        ambiguities.append(Ambiguity(
            ambiguity_id=AMB_UNSTRUCTURED, severity=Severity.CRITICAL, blocking=True,
            question="The request does not specify a recognizable benefit, limit, reimbursement or "
                     "authorization rule change. Which benefit and which rule parameter should change?",
        ))
    # ---------------------------------------------------------------- authorization threshold
    if "AUTH_THRESHOLD_ADD" in facets:
        if p.threshold_explicit_threshold is not None:
            params["auth_threshold"] = p.threshold_explicit_threshold
            assumptions.append(f"Explicit wording: authorization required once {p.threshold_explicit_threshold} "
                               f"completed visits exist (visit {p.threshold_explicit_threshold + 1} onward).")
        else:
            amb = Ambiguity(
                ambiguity_id=AMB_THRESHOLD, severity=Severity.CRITICAL, blocking=True,
                question=f"'{params['auth_threshold_wording']} visits' is ambiguous: does authorization begin on "
                         f"visit {p.threshold_n}, or after visit {p.threshold_n} (i.e. visit {p.threshold_n + 1} onward)?",
                options=THRESHOLD_OPTIONS,
            )
            choice = clarifications.get(AMB_THRESHOLD)
            if choice in THRESHOLD_OPTIONS:
                amb.resolution, amb.resolved_by = THRESHOLD_OPTIONS[choice], "HUMAN"
                params["auth_threshold"] = p.threshold_n if choice == "FROM_VISIT_11" else p.threshold_n - 1
            ambiguities.append(amb)
        if p.completed_mentioned:
            params["count_visit_status"] = "COMPLETED"
            assumptions.append("Only COMPLETED visits count toward the threshold; cancelled and no-show "
                               "appointments are excluded (policy P-01.3).")
        else:
            amb = Ambiguity(
                ambiguity_id=AMB_VISIT_STATUS, severity=Severity.CRITICAL, blocking=True,
                question="Which visit statuses count toward the authorization threshold?",
                options=VISIT_STATUS_OPTIONS,
            )
            choice = clarifications.get(AMB_VISIT_STATUS)
            if choice in VISIT_STATUS_OPTIONS:
                amb.resolution, amb.resolved_by = VISIT_STATUS_OPTIONS[choice], "HUMAN"
                params["count_visit_status"] = "COMPLETED" if choice == "COMPLETED_ONLY" else "ALL_SCHEDULED"
            ambiguities.append(amb)
        ambiguities.append(Ambiguity(
            ambiguity_id=AMB_GRANDFATHER, severity=Severity.MEDIUM, blocking=False,
            question="Members already beyond the threshold at go-live: is there a grace period / grandfathering?",
            default_assumption="No grandfathering; providers receive 30 days notice (P-40.1).",
            resolution="ASSUMPTION: no grandfathering; 30-day provider notice (P-40.1).", resolved_by="ASSUMPTION",
        ))
        missing.append("Authorization validity period confirmation (policy P-20.2 states remainder of benefit year).")
        deps += ["Authorization Service must expose completed-visit counts",
                 "Provider portal authorization request flow (existing, P-20.1)"]

    # ---------------------------------------------------------------- limit change
    if "BENEFIT_LIMIT_CHANGE" in facets:
        ambiguities.append(Ambiguity(
            ambiguity_id=AMB_YTD, severity=Severity.MEDIUM, blocking=False,
            question="Does the new annual maximum apply to amounts already paid earlier in the current benefit year?",
            default_assumption="Yes — the benefit-year accumulator continues; the new maximum applies to the remaining balance.",
            resolution="ASSUMPTION: accumulator continues; new maximum applies to remaining balance (P-01.1).",
            resolved_by="ASSUMPTION",
        ))
        deps.append("Benefits Service effective-dated limits")
    if facets and not p.plan_mentioned:
        ambiguities.append(Ambiguity(
            ambiguity_id=AMB_PLAN_SCOPE, severity=Severity.LOW, blocking=False,
            question="Which plans are in scope?",
            default_assumption="All plans that cover the benefit (P-10.1).",
            resolution="ASSUMPTION: all plans covering the benefit (P-10.1).", resolved_by="ASSUMPTION",
        ))
    if facets and not p.effective_date:
        ambiguities.append(Ambiguity(
            ambiguity_id=AMB_EFFECTIVE, severity=Severity.HIGH, blocking=False,
            question="No effective date given. When does the change take effect?",
            default_assumption="Effective on the deployment date of the release, after the 30-day notice (P-40.1).",
            resolution="ASSUMPTION: effective on release deployment date (to be confirmed by Product Owner).",
            resolved_by="ASSUMPTION",
        ))
        missing.append("Effective date of the change.")
    elif p.effective_date:
        params["effective_date"] = p.effective_date

    # ---------------------------------------------------------------- rules, ACs, stories
    bt_label = p.benefit.value.replace("_", " ").title() if p.benefit else "Benefit"
    if "BENEFIT_LIMIT_CHANGE" in facets:
        old, new = params["current_annual_max"], params["proposed_annual_max"]
        rules.append(BusinessRule(rule_id="BEN_RULE_090", name=f"{bt_label} annual maximum",
                                  description=f"Annual maximum per member per benefit year = ${new:,.0f}.",
                                  benefit_type=p.benefit, policy_section="P-14.2" if p.benefit is BenefitType.PHYSIOTHERAPY else None,
                                  change="MODIFIED", current_value=old, proposed_value=new))
        stories.append(f"As a NorthStar plan member, I want my {bt_label.lower()} annual maximum increased from "
                       f"${old:,.0f} to ${new:,.0f} so that more of my treatment is reimbursed.")
        acs += [
            AcceptanceCriterion(ac_id="AC-1", given=f"a member with ${new - 10:,.2f} {bt_label.lower()} paid this benefit year",
                                when="a claim with allowed amount $100 is adjudicated",
                                then="reimbursement is $10.00 (capped at the remaining maximum) with reason PAID_CAPPED",
                                rule_id="BEN_RULE_090"),
            AcceptanceCriterion(ac_id="AC-2", given=f"a member with ${new:,.2f} paid this benefit year",
                                when="another claim is adjudicated", then="the claim is DENIED with BENEFIT_MAX_REACHED",
                                rule_id="BEN_RULE_090"),
            AcceptanceCriterion(ac_id="AC-3", given=f"a member with exactly ${old:,.2f} paid (the old maximum)",
                                when="a claim is adjudicated under the new ruleset",
                                then="the claim is APPROVED (previously denied)", rule_id="BEN_RULE_090"),
        ]
    if "REIMBURSEMENT_CHANGE" in facets:
        rules.append(BusinessRule(rule_id="REIMB_RULE_050", name=f"{bt_label} reimbursement percentage",
                                  description=f"Reimbursement = {params['proposed_reimbursement_pct']:.0%} of allowed amount.",
                                  benefit_type=p.benefit, change="MODIFIED",
                                  current_value=params["current_reimbursement_pct"],
                                  proposed_value=params["proposed_reimbursement_pct"]))
    if "AUTH_THRESHOLD_ADD" in facets:
        t = params.get("auth_threshold")
        t_txt = f"{t}" if t is not None else f"<UNRESOLVED: {p.threshold_n} or {p.threshold_n - 1}>"
        rules.append(BusinessRule(rule_id="AUTH_RULE_184", name=f"{bt_label} prior-authorization threshold",
                                  description=f"Authorization required once completed visits in the benefit year >= {t_txt}; "
                                              "cancelled/no-show visits excluded.",
                                  benefit_type=p.benefit, policy_section="P-14.3", change="NEW",
                                  current_value=None, proposed_value=t))
        stories.append(f"As NorthStar Utilization Management, I want prior authorization enforced for {bt_label.lower()} "
                       "beyond the completed-visit threshold so that extended treatment is clinically reviewed.")
        if t is not None:
            acs += [
                AcceptanceCriterion(ac_id="AC-4", given=f"{t - 1} completed visits and no authorization",
                                    when=f"the claim for visit {t} is adjudicated", then="no authorization is required; claim APPROVED",
                                    rule_id="AUTH_RULE_184"),
                AcceptanceCriterion(ac_id="AC-5", given=f"{t} completed visits and no authorization",
                                    when=f"the claim for visit {t + 1} is adjudicated", then="claim DENIED with AUTH_REQUIRED",
                                    rule_id="AUTH_RULE_184"),
                AcceptanceCriterion(ac_id="AC-6", given=f"{t} completed visits and an approved authorization",
                                    when=f"the claim for visit {t + 1} is adjudicated", then="claim APPROVED",
                                    rule_id="AUTH_RULE_184"),
                AcceptanceCriterion(ac_id="AC-7", given=f"{t - 1} completed visits and 3 cancelled visits, no authorization",
                                    when=f"the claim for visit {t} is adjudicated",
                                    then="cancelled visits are NOT counted; no authorization required; claim APPROVED",
                                    rule_id="AUTH_RULE_184"),
            ]
    if facets:
        acs.append(AcceptanceCriterion(ac_id="AC-8", given="claims for other paramedical benefits",
                                       when="adjudicated under the new ruleset",
                                       then="outcomes are unchanged (no out-of-scope impact)", rule_id=None))
        assumptions.append("Reimbursement percentage remains unchanged unless explicitly stated (80%, P-14.1).")

    # ---------------------------------------------------------------- identity
    req_id = None
    for item in load_requirement_catalog():
        if item["status"] == "RELEASED":
            continue  # never attach new work to an already-released requirement
        if p.benefit and item["benefit_type"] == p.benefit.value and facets and set(item["facets"]) <= set(facets) | {"VISIT_COUNTING"} and set(facets) <= set(item["facets"]) | {"REIMBURSEMENT_CHANGE"}:
            if "AUTH_THRESHOLD_ADD" in facets or "AUTH_THRESHOLD_ADD" not in item["facets"]:
                req_id = item["requirement_id"]
                break
    if req_id is None:
        req_id = "BR-NEW-" + hashlib.sha256(text.strip().lower().encode()).hexdigest()[:6].upper()
    title = (f"{bt_label}: " + ", ".join(f.replace("_", " ").lower() for f in facets)) if facets else "Unstructured request"
    return Requirement(requirement_id=req_id, title=title, raw_text=text, benefit_type=p.benefit, facets=facets,
                       parameters=params, user_stories=stories, business_rules=rules, acceptance_criteria=acs,
                       assumptions=assumptions, ambiguities=ambiguities, missing_information=missing,
                       dependencies=deps)


class RequirementNotReady(ValueError):
    """Raised when a ruleset is requested for a requirement with unresolved blocking ambiguity."""


def ruleset_from_requirement(req: Requirement, base: RuleSet = RULESET_V1) -> RuleSet:
    """Build the proposed ruleset from the structured requirement (deterministic)."""
    if req.blocking_ambiguities:
        raise RequirementNotReady(f"unresolved blocking ambiguities: {[a.ambiguity_id for a in req.blocking_ambiguities]}")
    if not req.benefit_type:
        raise RequirementNotReady("no benefit identified")
    p = req.parameters
    count_cancelled = p.get("count_visit_status") == "ALL_SCHEDULED"
    candidate = derive_ruleset(
        base, f"RULESET_{req.requirement_id.replace('-', '_')}", "proposed",
        f"Proposed ruleset derived from {req.requirement_id}", req.benefit_type,
        annual_max=p.get("proposed_annual_max"), reimbursement_pct=p.get("proposed_reimbursement_pct"),
        auth_after_completed_visits=p.get("auth_threshold"),
        count_cancelled_visits=count_cancelled if "AUTH_THRESHOLD_ADD" in req.facets else None,
        source_requirements=(req.requirement_id,),
        changed_rules=tuple(r.rule_id for r in req.business_rules),
    )
    # Re-use the canonical id when the derived ruleset equals the specified V2 (traceability).
    if candidate.benefits == RULESET_V2.benefits:
        return RULESET_V2
    return candidate


def change_spec_for(req: Requirement) -> ChangeSpec:
    p = req.parameters
    return ChangeSpec(
        benefit_type=req.benefit_type.value if req.benefit_type else None,
        annual_max_changed="BENEFIT_LIMIT_CHANGE" in req.facets,
        auth_threshold=p.get("auth_threshold"),
        reimbursement_changed="REIMBURSEMENT_CHANGE" in req.facets,
        in_scope_benefits=frozenset({req.benefit_type.value}) if req.benefit_type else frozenset(),
    )
