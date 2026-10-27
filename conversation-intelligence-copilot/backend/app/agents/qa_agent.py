"""QA agent: deterministic verification of the assembled answer before it is shown."""

from __future__ import annotations

from app.agents.grounding import allowed_numbers, ungrounded_numbers
from app.analytics.query_registry import OPERATIONS

CRITICAL = {"registered_operations", "denominators", "ranking_consistency", "chart_consistency", "explanation_grounded", "proportions_valid",
            "excerpt_fidelity"}


def _check(name: str, passed: bool, detail: str) -> dict:
    return {"check": name, "passed": bool(passed), "critical": name in CRITICAL, "detail": detail}


def run_qa(plan: dict, tool_results: dict, charts: list[dict], evidence: list[dict], evidence_report: dict, explanation: dict, facts: dict,
           evidence_review: dict | None = None, basis: str = "") -> dict:
    checks: list[dict] = []
    ops = [s["op"] for s in plan.get("steps", [])]
    checks.append(_check("registered_operations", all(o in OPERATIONS for o in ops), f"Operations: {ops or 'none'}"))

    scope = plan.get("scope", {})
    mismatched = []
    for name, r in tool_results.items():
        rs = r.get("scope", {})
        if rs.get("dataset_mode") != scope.get("dataset_mode"):
            mismatched.append(f"{name}: dataset mode")
        if name != "sentiment_trend" and plan.get("category") not in ("explain_previous", "uncertainty_review", "leadership_summary"):
            if rs.get("window", {}).get("start") != scope.get("window", {}).get("start"):
                mismatched.append(f"{name}: window")
    checks.append(_check("filters_applied", not mismatched, "All results use the planned scope" if not mismatched else "; ".join(mismatched)))

    if (r := tool_results.get("rank_negative_topics")) and r["status"] == "ok":
        groups = r["series"]["all_groups"]["rows"]
        total = next(m["value"] for m in r["metrics"] if m["id"] == "conversations_in_scope")
        neg = next(m["value"] for m in r["metrics"] if m["id"] == "negative_conversations")
        s_total = int(sum(g["conversations"] for g in groups))
        s_neg = int(sum(g["negative"] for g in groups))
        checks.append(_check("denominators", s_total == total and s_neg == neg,
                             f"Group totals {s_total}/{s_neg} vs scope {total}/{neg} conversations/negative"))
        rows = r["table"]["rows"]
        key = "negative" if r["params"]["rank_by"] == "count" else "negative_rate"
        ordered = all(rows[i][key] >= rows[i + 1][key] for i in range(len(rows) - 1))
        consecutive = [row["rank"] for row in rows] == list(range(1, len(rows) + 1))
        checks.append(_check("ranking_consistency", ordered and consecutive, f"Ranks 1..{len(rows)} ordered by {key}"))
    if (r := tool_results.get("leadership_priorities")) and r["status"] == "ok":
        rows = r["table"]["rows"]
        ordered = all(rows[i]["priority_score"] >= rows[i + 1]["priority_score"] for i in range(len(rows) - 1))
        total = next(m["value"] for m in r["metrics"] if m["id"] == "conversations_in_scope")
        checks.append(_check("ranking_consistency", ordered, "Priority scores in descending order"))
        checks.append(_check("denominators", int(sum(x["conversations"] for x in rows)) == total, "Concern volumes sum to conversations in scope"))

    bad_props = []
    for name, r in tool_results.items():
        for m in r.get("metrics", []):
            if m.get("unit") == "percent" and m.get("value") is not None and not (0 <= float(m["value"]) <= 1):
                bad_props.append(f"{name}.{m['id']}={m['value']}")
    checks.append(_check("proportions_valid", not bad_props, "All proportions within [0, 1]" if not bad_props else ", ".join(bad_props)))

    chart_issues = []
    tables = {
        "negative_topics": ("rank_negative_topics", "table", "name", "negative"),
        "sentiment_trend": ("sentiment_trend", "table", "month", "negative_rate"),
        "priority_scores": ("leadership_priorities", "table", "name", "priority_score"),
        "topic_frequency": ("topic_frequency", "table", "name", "conversations"),
    }
    for c in charts:
        spec = tables.get(c["chart_id"])
        if not spec or spec[0] not in tool_results:
            continue
        src = {row[spec[2]]: row[spec[3]] for row in tool_results[spec[0]]["table"]["rows"]}
        for row in c["data"]:
            if src.get(row[spec[2]]) != row.get(spec[3]):
                chart_issues.append(f"{c['chart_id']}:{row[spec[2]]}")
    checks.append(_check("chart_consistency", not chart_issues, f"{len(charts)} charts match their source tables" if not chart_issues else ", ".join(chart_issues)))

    invalid = evidence_report.get("invalid", []) + evidence_report.get("out_of_scope", [])
    checks.append(_check("evidence_valid", not invalid, f"{evidence_report.get('resolved', 0)} evidence items resolved to source messages"
                         if not invalid else f"Dropped unresolved or out-of-scope references: {invalid}"))
    if plan.get("steps") and not plan.get("unsupported_reason"):
        needs = any(r.get("evidence_refs") for r in tool_results.values())
        checks.append(_check("evidence_present", bool(evidence) or not needs, f"{len(evidence)} evidence items attached"))

    text = " ".join([explanation.get("headline", ""), explanation.get("answer", "")] + explanation.get("key_points", []))
    if basis == "general_knowledge":
        # Not from the dataset by design: the check is that it says so, not that its numbers trace to results.
        labelled = explanation.get("answer", "").startswith("Model's own answer, not from the dataset.")
        checks.append(_check("general_answer_labelled", labelled, "Answer is labelled as the model's own, not from the dataset"
                             if labelled else "General-knowledge answer is missing its label"))
    elif not plan.get("steps") and plan.get("unsupported_reason"):
        checks.append(_check("explanation_grounded", True, "No analysis was run; the reply is guidance text and claims no figures"))
    else:
        bad = ungrounded_numbers(text, allowed_numbers(facts))
        checks.append(_check("explanation_grounded", not bad, "All numbers in the answer trace to verified results" if not bad else f"Ungrounded numbers: {bad[:8]}"))

    unc = [n for r in tool_results.values() for n in r.get("uncertainty_notes", [])]
    checks.append(_check("uncertainty_disclosed", True, f"{len(unc)} uncertainty notes attached to the response"))
    if "agent_coaching_review" in tool_results:
        r = tool_results["agent_coaching_review"]
        checks.append(_check("coaching_sample_size_gate", r["params"]["min_conversations"] >= 1 and any("Decision support" in n for n in r["uncertainty_notes"]),
                             f"Minimum {r['params']['min_conversations']} conversations per agent enforced; safeguard attached"))
    # Evidence Challenger results count as QA checks (a qualified causal claim is a warning, a mismatched quote is critical).
    for c in (evidence_review or {}).get("checks", []):
        if c["check"] == "counter_evidence":
            continue
        checks.append(_check(c["check"], c["status"] == "pass", c["detail"]))
    failed_critical = [c for c in checks if not c["passed"] and c["critical"]]
    failed = [c for c in checks if not c["passed"]]
    status = "fail" if failed_critical else "warn" if failed else "pass"
    return {"status": status, "checks": checks, "passed": sum(c["passed"] for c in checks), "total": len(checks)}
