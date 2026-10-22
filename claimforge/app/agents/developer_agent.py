"""Developer agent: implementation plan, pseudocode, code/API/schema proposals.

DEMO TEMPLATE: proposals target the *synthetic* NorthStar repositories. Nothing is ever
committed, merged or deployed automatically.
"""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.impact.analyzer import load_architecture
from app.models.domain import ImpactAction, Requirement

_PATCH = '''--- a/authorization-service/src/main/java/com/northstar/auth/visits/VisitCounter.java
+++ b/authorization-service/src/main/java/com/northstar/auth/visits/VisitCounter.java
@@ public int countedVisits(String memberId, Benefit benefit, BenefitYear year) {
-    return visitRepo.countByMemberBenefitYear(memberId, benefit, year);
+    // BR-391 / AUTH_RULE_184 / policy P-01.3: only COMPLETED visits count toward the threshold.
+    return visitRepo.countByMemberBenefitYearAndStatus(memberId, benefit, year, VisitStatus.COMPLETED);
 }
'''


class DeveloperAgent(BaseAgent):
    name = "developer"
    title = "Developer Agent"
    implementation = "DETERMINISTIC TEMPLATE (synthetic repos) — no auto-merge / deploy"

    def run(self, state: dict) -> dict:
        req: Requirement = state["requirement"]
        impacts = [i for i in state["impact"]["impacts"] if i.action is not ImpactAction.KEEP]
        paths = {c["component_id"]: c.get("repo_paths", []) for c in load_architecture()["components"]}
        p = req.parameters
        steps = []
        for n, imp in enumerate(sorted(impacts, key=lambda i: ({"database_table": 0, "rule": 1, "service": 2, "api": 3,
                                                                  "event": 4}.get(i.component_type, 5), i.component_id)), 1):
            steps.append({"step": n, "component": imp.component_name, "action": imp.action.value,
                          "work": imp.reason, "files": paths.get(imp.component_id, [])})
        t = p.get("auth_threshold")
        pseudocode = [
            "def adjudicate(claim, member_history, ruleset):",
            "    ... eligibility / effective date / provider / coverage / duplicate checks (unchanged)",
        ]
        if "AUTH_THRESHOLD_ADD" in req.facets:
            pseudocode += [
                "    completed = count(v for v in member_history.visits(benefit, year) if v.status == 'COMPLETED')",
                f"    if completed >= {t if t is not None else '<THRESHOLD>'} and not has_approved_authorization(member, benefit):",
                "        return DENIED(AUTH_REQUIRED, rule='AUTH_RULE_184')",
            ]
        if "BENEFIT_LIMIT_CHANGE" in req.facets:
            pseudocode += [
                f"    annual_max = benefits_api.annual_max(benefit, effective=claim.service_date)  # ${p['proposed_annual_max']:,.0f}",
                "    paid = min(pct * allowed, annual_max - ytd_paid)",
            ]
        api_changes = []
        schema = []
        if "BENEFIT_LIMIT_CHANGE" in req.facets:
            api_changes.append("GET /v2/benefits/limits?benefit=PHYSIOTHERAPY&date=YYYY-MM-DD → {annual_max, remaining, effective_from}")
            schema.append(f"INSERT INTO benefit_limits (benefit, annual_max, effective_from, ruleset) VALUES "
                          f"('PHYSIOTHERAPY', {p['proposed_annual_max']:.2f}, :release_date, 'RULESET_V2');")
        if "AUTH_THRESHOLD_ADD" in req.facets:
            api_changes.append("GET /v1/authorizations/requirement?member=&benefit= → {required, counted_completed_visits, threshold}")
            schema += [
                f"INSERT INTO authorization_rules (rule_id, benefit, threshold, count_status) VALUES "
                f"('AUTH_RULE_184', 'PHYSIOTHERAPY', {t if t is not None else 'NULL'}, 'COMPLETED');",
                "CREATE VIEW completed_visit_counts AS SELECT member_id, benefit, benefit_year, COUNT(*) AS completed "
                "FROM visit_history WHERE visit_status = 'COMPLETED' GROUP BY 1,2,3;",
            ]
        plan = {
            "requirement_id": req.requirement_id,
            "steps": steps,
            "pseudocode": "\n".join(pseudocode),
            "code_patch": _PATCH if "AUTH_THRESHOLD_ADD" in req.facets else "",
            "api_changes": api_changes,
            "schema_changes": schema,
            "migration_considerations": [
                "Effective-dated rows: keep RULESET_V1 rows for audit and claims with earlier service dates.",
                "Backward-compatible Avro change (optional fields) for claim.adjudicated.",
                "Feature flag per benefit for staged rollout; shadow-adjudicate before enabling.",
                "No in-place update of historical claims; reprocessing requires approval (O-05.2).",
            ],
            "technical_documentation": f"Docs to update: benefit booklet (P-14), provider manual, runbook for {req.requirement_id}.",
            "label": "DETERMINISTIC TEMPLATE — proposal only; not merged, not deployed",
        }
        plan["narrative"] = self.narrate("Explain the implementation plan", plan["pseudocode"],
                                         f"{len(steps)} implementation steps across {len(impacts)} changed components.")
        return {"development_plan": plan}
