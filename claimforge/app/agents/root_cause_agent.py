"""Root-cause agent (ClaimIQ): bounded, tool-using investigation loop.

Each iteration the planner chooses the next investigation tool whose prerequisites are
satisfied, calls it through the allow-listed registry, records evidence and re-scores
hypotheses. The loop stops when every investigation step is done or when
MAX_AGENT_ITERATIONS / MAX_TOOL_CALLS / timeout is hit (→ INCONCLUSIVE).

In DEMO_MODE the planner is deterministic; confidence comes from deterministic evidence
weights, not from an LLM's self-assessment.
"""

from __future__ import annotations

import hashlib

from app.agents.base import BaseAgent
from app.models.domain import BenefitType, Evidence, RootCause
from app.tools.registry import ToolError

# step name -> (prerequisite fact keys, evidence weight)
PLAN: list[tuple[str, tuple[str, ...]]] = [
    ("segment_metrics", ()),
    ("denial_reason_shift", ("segment",)),
    ("correlate_release", ("segment", "reason")),
    ("trace_rule_to_requirement", ("rule_id",)),
    ("inspect_affected_claims", ("segment", "reason")),
    ("run_regression_suite", ()),
    ("check_operational_health", ()),
]
WEIGHTS = {"temporal_alignment": 0.15, "reason_concentration": 0.15, "rule_changed_in_release": 0.15,
           "requirement_traced": 0.05, "claim_pattern_match": 0.30, "failing_regression_test": 0.15,
           "operational_cause_ruled_out": 0.05}


class RootCauseAgent(BaseAgent):
    name = "root_cause"
    title = "Root-Cause Agent (ClaimIQ)"
    implementation = "Bounded agent loop over deterministic investigation tools; LLM narrative optional"

    def run(self, state: dict) -> dict:
        prod = state["artifacts"]["production"]
        anomalies = state["anomaly"]["anomalies"]
        max_iter = state.get("max_agent_iterations") or self.ctx.settings.max_agent_iterations
        budget = self.budget()
        facts: dict = {}
        evidence: list[Evidence] = []
        done: list[str] = []
        stop_reason = None
        rid = state.get("request_id")
        iterations = 0

        def tool(name: str, **kw):
            return self.ctx.tools.call(self.name, name, budget, request_id=rid, **kw)

        while len(done) < len(PLAN):
            if iterations >= max_iter:
                stop_reason = f"MAX_AGENT_ITERATIONS={max_iter} reached"
                break
            step = next((s for s, pre in PLAN if s not in done and all(k in facts for k in pre)), None)
            if step is None:
                stop_reason = "no runnable investigation step (prerequisites unmet)"
                break
            iterations += 1
            try:
                if step == "segment_metrics":
                    out = tool(step, ctx=prod, anomalies=anomalies)
                    if out["segment"] is None:
                        done.append(step)
                        stop_reason = "no anomalous segment"
                        evidence.append(self._ev(step, out["statement"], None, 0.0, out))
                        break
                    facts["segment"] = out["segment"]
                elif step == "denial_reason_shift":
                    out = tool(step, ctx=prod, benefit=facts["segment"])
                    facts["reason"] = out["top_reason"]
                    facts["reason_share"] = out["excess_share"]
                elif step == "correlate_release":
                    out = tool(step, ctx=prod, benefit=facts["segment"], reason=facts["reason"],
                               releases=self.ctx.releases["releases"])
                    facts.update(rule_id=out["rule_id"], aligned=out["temporally_aligned"],
                                 rule_changed=out["rule_changed_in_release"], release=out["release"])
                elif step == "trace_rule_to_requirement":
                    out = tool(step, rule_id=facts["rule_id"], trace_graph=self.ctx.trace_graph)
                    facts["requirement"] = out["requirements"][0] if out["requirements"] else None
                    facts["policy"] = out["policy_sections"][0] if out["policy_sections"] else None
                    facts["policy_all"] = out["policy_sections"]
                elif step == "inspect_affected_claims":
                    rule = prod.approved_ruleset.benefits.get(BenefitType(facts["segment"]))
                    out = tool(step, ctx=prod, benefit=facts["segment"], reason=facts["reason"],
                               threshold=(rule.auth_after_completed_visits if rule else None) or 10)
                    facts["claims"] = out
                elif step == "run_regression_suite":
                    out = tool(step, ctx=prod)
                    facts["regression"] = out
                else:
                    out = tool(step, ctx=prod)
                    facts["ops"] = out
            except ToolError as exc:
                stop_reason = f"tool error: {exc}"
                break
            done.append(step)
            evidence.append(self._ev(step, out["statement"], None, 0.0,
                                     {k: v for k, v in out.items() if k not in ("rows", "samples", "weekly_excess", "failed")}))

        hypotheses, scored = self._score(facts)
        score = round(sum(WEIGHTS[k] for k, ok in scored.items() if ok), 2)
        concluded = len(done) == len(PLAN) and stop_reason is None
        confidence = "HIGH" if score >= 0.8 else ("MEDIUM" if score >= 0.5 else "LOW")
        supported = [h for h in hypotheses if h["status"] == "SUPPORTED"]
        claims = facts.get("claims", {})
        primary = state["anomaly"].get("primary")
        rc = RootCause(
            investigation_id="INV-" + hashlib.sha256(str(sorted(facts.keys())).encode() + (rid or "").encode()).hexdigest()[:8].upper(),
            status="CONCLUDED" if concluded else "INCONCLUSIVE",
            anomaly_summary=primary.summary if primary else "no anomaly",
            correlated_release=facts.get("release") if facts.get("aligned") else None,
            changed_rule=facts.get("rule_id"),
            source_requirement=facts.get("requirement"),
            policy_section="P-14.3" if "P-14.3" in facts.get("policy_all", []) else facts.get("policy"),
            likely_defect=supported[0]["statement"] if supported and concluded else None,
            confidence=confidence if concluded else "LOW",
            confidence_score=score if concluded else min(score, 0.49),
            evidence=self._weight(evidence, scored),
            hypotheses=hypotheses,
            affected_claims=claims.get("inconsistent_with_spec", 0),
            wrongly_denied_amount=claims.get("wrongly_denied_amount", 0.0),
            sample_claims=claims.get("samples", []),
            iterations=iterations,
            tool_calls=budget.calls,
            trace_path=[x for x in [primary.metric if primary else None, f"Release {facts.get('release')}" if facts.get("release") else None,
                                    facts.get("rule_id"), facts.get("requirement"), facts.get("policy")] if x],
        )
        fallback = (f"{rc.status}: {rc.likely_defect or stop_reason or 'no supported hypothesis'} "
                    f"(confidence {rc.confidence}, score {rc.confidence_score}).")
        return {"root_cause": rc, "root_cause_narrative": self.narrate("Summarize the root-cause investigation",
                                                                       str([e.statement for e in rc.evidence]), fallback),
                "root_cause_stop_reason": stop_reason}

    @staticmethod
    def _ev(step, statement, supports, weight, data) -> Evidence:
        return Evidence(evidence_id=f"EV-{step}", kind=step, statement=statement, supports=supports, weight=weight, data=data)

    @staticmethod
    def _weight(evidence: list[Evidence], scored: dict) -> list[Evidence]:
        mapping = {"correlate_release": ["temporal_alignment", "rule_changed_in_release"],
                   "denial_reason_shift": ["reason_concentration"], "trace_rule_to_requirement": ["requirement_traced"],
                   "inspect_affected_claims": ["claim_pattern_match"], "run_regression_suite": ["failing_regression_test"],
                   "check_operational_health": ["operational_cause_ruled_out"]}
        out = []
        for e in evidence:
            keys = mapping.get(e.kind, [])
            w = round(sum(WEIGHTS[k] for k in keys if scored.get(k)), 2)
            out.append(e.model_copy(update={"weight": w, "supports": "H1" if w else None}))
        return out

    @staticmethod
    def _score(f: dict) -> tuple[list[dict], dict]:
        claims = f.get("claims", {})
        reg = f.get("regression", {})
        ops = f.get("ops", {})
        n_wrong = claims.get("inconsistent_with_spec", 0)
        scored = {
            "temporal_alignment": bool(f.get("aligned")),
            "reason_concentration": f.get("reason_share", 0) >= 0.6,
            "rule_changed_in_release": bool(f.get("rule_changed")),
            "requirement_traced": bool(f.get("requirement")),
            "claim_pattern_match": n_wrong > 0 and claims.get("pattern_match_ratio", 0) >= 0.9,
            "failing_regression_test": reg.get("cancelled_visit_tests_failed", 0) > 0,
            "operational_cause_ruled_out": bool(ops.get("healthy")),
        }

        def status(cond_support: bool | None) -> str:
            return "UNTESTED" if cond_support is None else ("SUPPORTED" if cond_support else "REFUTED")

        h1 = None if not claims else (scored["claim_pattern_match"] and (not reg or scored["failing_regression_test"]))
        h2 = None if not claims else (n_wrong > 0 and claims.get("off_by_one_pattern", 0) / n_wrong >= 0.5)
        h3 = None if not ops else (not ops.get("healthy"))
        h4 = None if not claims else (n_wrong == 0)
        hypotheses = [
            {"id": "H1", "status": status(h1),
             "statement": f"{f.get('rule_id', 'AUTH_RULE_184')} counts CANCELLED visits toward the COMPLETED-visit "
                          "authorization threshold (violates P-01.3)."},
            {"id": "H2", "status": status(h2), "statement": "Off-by-one: authorization enforced from visit 10 instead of 11."},
            {"id": "H3", "status": status(h3), "statement": "Authorization Service outage / lookup failures."},
            {"id": "H4", "status": status(h4), "statement": "Intended effect of BR-391 (no defect)."},
            {"id": "H5", "status": "REFUTED" if claims else "UNTESTED",
             "statement": "Member-mix / volume shift (baseline is a shadow replay of the identical claims)."},
        ]
        return hypotheses, scored
