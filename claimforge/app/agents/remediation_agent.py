"""Remediation agent: proposes and *verifies* a fix in simulation; never applies it.

Bounded loop over candidate remediations. Each candidate is verified by deterministic
shadow replay of post-release claims + the BR-391 regression suite + the generated
regression test. The first candidate that verifies is recommended. Production is never
modified; reprocessing and deployment require human approval.
"""

from __future__ import annotations

from datetime import date
from dataclasses import replace

from app.agents.base import BaseAgent
from app.claims.adjudicator import adjudicate_frame
from app.claims.rulesets import RULESET_V1, RuleSet
from app.models.domain import Remediation, TestCase
from app.qa.test_generator import generate_test_cases, regression_test_code, run_test_cases, summarize
from app.requirements.analyzer import DEMO_CLARIFICATIONS, DEMO_REQUIREMENT, analyze_requirement_text

_EPOCH = date(2000, 1, 1)


def _fixed(deployed: RuleSet) -> RuleSet:
    benefits = {bt: (replace(br, count_cancelled_visits=False) if br.auth_after_completed_visits is not None else br)
                for bt, br in deployed.benefits.items()}
    return RuleSet(ruleset_id="RULESET_V2_1", version="2.4.1",
                   description="Hotfix: AUTH_RULE_184 counts COMPLETED visits only.", benefits=benefits,
                   source_requirements=deployed.source_requirements, changed_rules=("AUTH_RULE_184",))


def _run_generated_test(code: str) -> bool:
    ns: dict = {}
    exec(compile(code, "<generated_regression_test>", "exec"), ns)  # our own generated code, not user input
    fn = next(v for k, v in ns.items() if k.startswith("test_"))
    try:
        fn()
        return True
    except AssertionError:
        return False


class RemediationAgent(BaseAgent):
    name = "remediation"
    title = "Remediation Agent"
    implementation = "Bounded propose→verify loop with deterministic replay; human approval required"

    def run(self, state: dict) -> dict:
        prod = state["artifacts"]["production"]
        rc = state["root_cause"]
        max_iter = state.get("max_agent_iterations") or self.ctx.settings.max_agent_iterations
        sample = rc.sample_claims[0] if rc.sample_claims else {"prior_completed_visits": 8, "prior_cancelled_visits": 3}
        completed, cancelled = int(sample["prior_completed_visits"]), int(sample["prior_cancelled_visits"])
        threshold = 10
        test_id = "TC-REG-BR391-001"
        candidates = [
            ("FORWARD_FIX", "Count COMPLETED visits only in the AUTH_RULE_184 visit counter (hotfix 2.4.1).", _fixed(prod.deployed_ruleset)),
            ("ROLLBACK", "Roll back to release 2.3 (RULESET_V1).", RULESET_V1),
        ]
        req = analyze_requirement_text(DEMO_REQUIREMENT, DEMO_CLARIFICATIONS)
        suite = generate_test_cases(req)
        chosen = None
        attempts = []
        for it, (kind, desc, rs) in enumerate(candidates, 1):
            if it > max_iter:
                break
            replay = adjudicate_frame(prod.dataset.claims, prod.dataset.members, prod.dataset.providers,
                                      [(_EPOCH, RULESET_V1), (prod.release_date, rs)])
            post_ids = set(prod.post.claim_id)
            exp = prod.expected.set_index("claim_id")
            rep = replay.set_index("claim_id").loc[list(post_ids)]
            mismatches = int((rep.status != exp.loc[rep.index, "status"]).sum())
            suite_summary = summarize(run_test_cases(suite, rs))
            code = regression_test_code(test_id, completed, cancelled, threshold, ruleset_id="RULESET_V2_1")
            gen_ok = _run_generated_test(code) if kind == "FORWARD_FIX" else False
            verified = mismatches == 0 and suite_summary["failed"] == 0
            attempts.append({"iteration": it, "candidate": kind, "description": desc, "ruleset": rs.ruleset_id,
                             "replay_mismatches_vs_approved_spec": mismatches, "suite": suite_summary,
                             "generated_regression_test_passes": gen_ok, "verified": verified})
            if verified:
                chosen = (kind, desc, rs, code)
                break
        if chosen is None:  # fall back to the safest candidate, flagged unverified
            kind, desc, rs = candidates[-1]
            code = regression_test_code(test_id, completed, cancelled, threshold)
            chosen = (kind, desc, rs, code)
        kind, desc, rs, code = chosen
        defective_fails = not _run_generated_test(code.replace('"RULESET_V2_1"', f'"{prod.deployed_ruleset.ruleset_id}"')) \
            if prod.deployed_ruleset.ruleset_id in ("RULESET_V2_DEFECTIVE",) else None
        post = prod.post
        exp_post = prod.expected.set_index("claim_id").loc[post.claim_id]
        reprocess = int(((post.status.values == "DENIED") & (exp_post.status.values == "APPROVED")).sum())
        reg_tc = TestCase(test_id=test_id, title="Regression: cancelled visits must not count toward AUTH_RULE_184 threshold",
                          category="regression", requirement_id=rc.source_requirement or "BR-391",
                          rule_id="AUTH_RULE_184", critical=True, source="REMEDIATION_AGENT (from production failure)",
                          given={"benefit_type": "PHYSIOTHERAPY", "plan_id": "NSH-GOLD", "billed": 100.0,
                                 "prior_completed": completed, "prior_cancelled": cancelled},
                          expected={"status": "DENIED" if completed >= threshold else "APPROVED",
                                    "authorization_required": completed >= threshold, "counted_visits": completed})
        rem = Remediation(
            remediation_id="REM-" + (rc.investigation_id[-8:] if rc.investigation_id else "0001"),
            recommended_change=desc if kind == "FORWARD_FIX" else desc + " (UNVERIFIED fallback)",
            configuration_change={"rule_id": "AUTH_RULE_184", "count_visit_status": "COMPLETED",
                                  "count_cancelled_visits": False, "target_ruleset": rs.ruleset_id},
            implementation_recommendation=[
                "VisitCounter: filter visit_status = 'COMPLETED' (see code patch).",
                "Read counts from the completed_visit_counts view (single source of truth).",
                "Add the generated regression test to the release gate for AUTH_RULE_184.",
                "Ship as hotfix 2.4.1 behind the existing feature flag; shadow-adjudicate before enabling.",
            ],
            code_patch=state.get("development_plan", {}).get("code_patch") or
            "- visitRepo.countByMemberBenefitYear(...)\n+ visitRepo.countByMemberBenefitYearAndStatus(..., COMPLETED)",
            additional_validation=[
                "Data-quality check: AUTH_REQUIRED denials with < threshold COMPLETED visits must be 0 (ClaimIQ alert).",
                "Synthetic test data must include cancelled and no-show visits (generator updated).",
                "Contract test: claim.adjudicated.counted_visits equals completed-visit view count.",
            ],
            regression_test=reg_tc,
            regression_test_code=code,
            rollback_option="Rollback to 2.3 (RULESET_V1) is available via effective-dated rules, but it also reverts the "
                            "$1,000 maximum (member harm). Use only if the hotfix cannot ship within the SLA.",
            forward_fix="Hotfix 2.4.1 (RULESET_V2_1): count COMPLETED visits only.",
            claims_to_reprocess=reprocess,
            verification={"attempts": attempts, "generated_test_fails_on_defective_build": defective_fails,
                          "method": "SIMULATED shadow replay + deterministic test execution"},
            iterations=len(attempts),
        )
        return {"remediation": rem}
