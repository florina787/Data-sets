"""Deterministic investigation tools used by the Root-Cause agent.

Each tool takes structured inputs and returns structured evidence computed from the
(simulated) production data, release manifests, rulesets and the traceability graph.
The agent decides *which* tool to call next; the tools decide *what is true*.
"""

from __future__ import annotations

from datetime import timedelta

from app.models.domain import Anomaly
from app.monitoring.production import ProductionContext
from app.qa.test_generator import generate_test_cases, run_test_cases, summarize
from app.requirements.analyzer import DEMO_CLARIFICATIONS, analyze_requirement_text

REASON_TO_RULE = {"AUTH_REQUIRED": "AUTH_RULE_184", "BENEFIT_MAX_REACHED": "BEN_RULE_090",
                  "PAID_CAPPED": "BEN_RULE_090", "VISIT_LIMIT_EXCEEDED": "VIS_RULE_070",
                  "PROVIDER_INELIGIBLE": "PROV_RULE_020", "MEMBER_INELIGIBLE": "ELIG_RULE_001",
                  "NOT_COVERED": "COV_RULE_010", "DUPLICATE": "DUP_RULE_030"}


def segment_metrics(ctx: ProductionContext, anomalies: list[Anomaly]) -> dict:
    detected = [a for a in anomalies if a.detected and a.segment.get("benefit_type") != "ALL"]
    if not detected:
        return {"segment": None, "statement": "No benefit-level segment exceeds the anomaly threshold."}
    top = max(detected, key=lambda a: a.z_score)
    return {"segment": top.segment["benefit_type"], "metric": top.metric, "z_score": top.z_score,
            "relative_change": top.relative_change,
            "statement": f"Anomaly concentrated in {top.segment['benefit_type']} ({top.summary})."}


def denial_reason_shift(ctx: ProductionContext, benefit: str) -> dict:
    act = ctx.post[(ctx.post.benefit_type == benefit) & (ctx.post.status == "DENIED")].reason_code.value_counts()
    exp_df = ctx.expected[ctx.expected.service_date >= ctx.release_date]
    exp = exp_df[(exp_df.benefit_type == benefit) & (exp_df.status == "DENIED")].reason_code.value_counts()
    reasons = sorted(set(act.index) | set(exp.index))
    rows = [{"reason_code": r, "observed": int(act.get(r, 0)), "expected": int(exp.get(r, 0)),
             "excess": int(act.get(r, 0) - exp.get(r, 0))} for r in reasons]
    rows.sort(key=lambda r: -r["excess"])
    total_excess = sum(max(0, r["excess"]) for r in rows)
    top = rows[0] if rows else None
    share = (top["excess"] / total_excess) if top and total_excess else 0.0
    return {"rows": rows, "top_reason": top["reason_code"] if top else None, "top_excess": top["excess"] if top else 0,
            "excess_share": round(share, 3),
            "statement": (f"{top['reason_code']} accounts for {share:.0%} of excess {benefit} denials "
                          f"({top['observed']} observed vs {top['expected']} expected).") if top else "no denials"}


def correlate_release(ctx: ProductionContext, benefit: str, reason: str, releases: list[dict]) -> dict:
    act = ctx.actual[(ctx.actual.benefit_type == benefit)]
    exp = ctx.expected[(ctx.expected.benefit_type == benefit)]
    a = act[act.reason_code == reason].groupby("week").size()
    e = exp[exp.reason_code == reason].groupby("week").size()
    weeks = sorted(set(a.index) | set(e.index))
    excess = {w: int(a.get(w, 0) - e.get(w, 0)) for w in weeks}
    pre_excess = sum(v for w, v in excess.items() if w < ctx.release_date)
    first = next((w for w in weeks if excess[w] > 0), None)
    aligned = first is not None and pre_excess == 0 and (first - ctx.release_date) <= timedelta(days=14) and first >= ctx.release_date - timedelta(days=6)
    rel = next((r for r in releases if r["version"] == ctx.release_version), None)
    rule = REASON_TO_RULE.get(reason)
    changed = bool(rel and rule in rel.get("changed_rules", []))
    return {"release": ctx.release_version, "release_date": ctx.release_date.isoformat(),
            "first_excess_week": first.isoformat() if first else None, "pre_release_excess": pre_excess,
            "temporally_aligned": aligned, "rule_id": rule, "rule_changed_in_release": changed,
            "release_changed_rules": rel.get("changed_rules", []) if rel else [],
            "change_ids": rel.get("change_ids", []) if rel else [],
            "weekly_excess": [{"week": w.isoformat(), "excess": v} for w, v in excess.items()],
            "statement": (f"Metric shift begins week of {first} (release {ctx.release_version} deployed "
                          f"{ctx.release_date}); {rule} changed in this release.") if aligned and changed
                         else "No clean temporal/rule alignment with the release."}


def trace_rule_to_requirement(rule_id: str, trace_graph) -> dict:
    up = trace_graph.upstream(rule_id)
    reqs = [n for n in up if n["type"] == "requirement"]
    pols = [n for n in up if n["type"] == "policy_section"]
    return {"rule_id": rule_id, "requirements": [r["id"] for r in reqs], "policy_sections": [p["id"] for p in pols],
            "statement": f"{rule_id} implements {', '.join(r['id'] for r in reqs) or 'no requirement'} "
                         f"(policy {', '.join(p['id'] for p in pols) or 'n/a'})."}


def inspect_affected_claims(ctx: ProductionContext, benefit: str, reason: str, threshold: int = 10) -> dict:
    post = ctx.post
    denied = post[(post.benefit_type == benefit) & (post.reason_code == reason)]
    by_spec = denied[(denied.prior_completed_visits >= threshold) & (~denied.authorization_present)]
    wrong = denied[denied.prior_completed_visits < threshold]
    n_wrong = len(wrong)
    with_cancel_reaching = int(((wrong.prior_completed_visits + wrong.prior_cancelled_visits) >= threshold).sum())
    with_cancel = int((wrong.prior_cancelled_visits > 0).sum())
    off_by_one = int(((wrong.prior_completed_visits == threshold - 1) & (wrong.prior_cancelled_visits == 0)).sum())
    exp = ctx.expected.set_index("claim_id")
    wrongly_denied_amount = float(exp.loc[wrong.claim_id, "reimbursement_amount"].sum()) if n_wrong else 0.0
    samples = wrong.head(5)[["claim_id", "member_id", "service_date", "prior_completed_visits",
                             "prior_cancelled_visits", "authorization_present", "reason_code"]].copy()
    samples["service_date"] = samples.service_date.astype(str)
    samples["authorization_present"] = samples.authorization_present.astype(bool)
    return {
        "denied_total": int(len(denied)), "consistent_with_spec": int(len(by_spec)), "inconsistent_with_spec": n_wrong,
        "inconsistent_reaching_threshold_only_with_cancelled": with_cancel_reaching,
        "inconsistent_with_cancelled_visits": with_cancel, "off_by_one_pattern": off_by_one,
        "pattern_match_ratio": round(with_cancel_reaching / n_wrong, 3) if n_wrong else 0.0,
        "wrongly_denied_amount": round(wrongly_denied_amount, 2),
        "samples": samples.to_dict(orient="records"),
        "statement": (f"{n_wrong} of {len(denied)} {reason} denials had fewer than {threshold} COMPLETED visits; "
                      f"{with_cancel_reaching} of them ({(with_cancel_reaching / n_wrong if n_wrong else 0):.0%}) reach "
                      f"{threshold} only when CANCELLED visits are added.") if n_wrong else
                     f"All {len(denied)} {reason} denials are consistent with the specification.",
    }


def run_regression_suite(ctx: ProductionContext) -> dict:
    req = analyze_requirement_text("Increase physiotherapy annual coverage from $750 to $1,000 and require prior "
                                   "authorization after 10 completed visits.", DEMO_CLARIFICATIONS)
    cases = generate_test_cases(req)
    results = run_test_cases(cases, ctx.deployed_ruleset)
    s = summarize(results)
    failed = [{"test_id": r.test_id, "title": r.title, "expected": r.expected, "actual": r.actual}
              for r in results if not r.passed]
    return {"ruleset": ctx.deployed_ruleset.ruleset_id, "summary": s, "failed": failed,
            "cancelled_visit_tests_failed": sum(1 for f in failed if "ancelled" in f["title"]),
            "statement": f"BR-391 suite against deployed build: {s['passed']}/{s['total']} passed; "
                         f"failing: {', '.join(f['title'] for f in failed) or 'none'}."}


def check_operational_health(ctx: ProductionContext) -> dict:
    pre, post = ctx.pre, ctx.post
    exc_pre = float(pre.rule_exception.mean()) if len(pre) else 0.0
    exc_post = float(post.rule_exception.mean()) if len(post) else 0.0
    lat_pre = float(pre.latency_ms.quantile(0.95)) if len(pre) else 0.0
    lat_post = float(post.latency_ms.quantile(0.95)) if len(post) else 0.0
    healthy = exc_post <= max(0.005, exc_pre * 2) and lat_post <= lat_pre * 1.25
    return {"rule_exception_rate_pre": round(exc_pre, 4), "rule_exception_rate_post": round(exc_post, 4),
            "latency_p95_pre_ms": round(lat_pre, 1), "latency_p95_post_ms": round(lat_post, 1),
            "healthy": healthy,
            "statement": ("No rule-exception or latency spike after release — service outage unlikely."
                          if healthy else "Operational degradation detected after release.")}
