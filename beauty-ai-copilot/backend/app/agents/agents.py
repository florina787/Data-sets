"""Eight bounded agents. Each has a declared contract (inputs, allowed tools, output schema,
evidence requirement, error strategy). Agents read facts prepared by the workflow and may call only
their allowed read-only tools through the ToolGateway. They cannot evaluate gates, grant
permissions or approve anything; their outputs are recommendations and summaries."""
from __future__ import annotations

import re
import time
from typing import Any, Callable

from pydantic import BaseModel, Field

from app.errors import Forbidden
from app.retrieval.knowledge import get_kb

# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------

CONTRACTS: dict[str, dict] = {
    "requirements": {
        "responsibility": "Extract scope and resolve ambiguity",
        "inputs": ["change statement", "answered clarifications", "demo clarification config"],
        "allowed_tools": ["kb.search"],
        "output": "RequirementsOutput: scope, ambiguities[], acceptance_criteria[]",
        "evidence": "Each ambiguity links related guidance excerpts when found; acceptance criteria cite clarification IDs",
        "error_strategy": "Fail the node; checkpoint keeps prior nodes; resume re-runs only this node",
    },
    "evidence": {
        "responsibility": "Retrieve approved specifications and dataset documentation",
        "inputs": ["requirement scope", "user roles (for authorization filtering)"],
        "allowed_tools": ["kb.search", "kb.validate", "kb.conflicts"],
        "output": "EvidenceOutput: citations[], conflicts[], unsupported_claims[], injection_flags[]",
        "evidence": "Every citation carries source ID, version, section, excerpt and retrieval time and is validated",
        "error_strategy": "Unresolvable citations are marked UNRESOLVED, never dropped; claims without support are UNKNOWN",
    },
    "impact": {
        "responsibility": "Map affected services, data, models, tests and owners",
        "inputs": ["requirement scope", "system map", "evidence bundle"],
        "allowed_tools": ["system_map.read", "dataset.describe"],
        "output": "ImpactOutput: components[], tests[], owners[], risks[]",
        "evidence": "Each component lists the matched requirement terms; risks cite dataset card or specs",
        "error_strategy": "Fail node; impact cannot be accepted until a successful assessment exists",
    },
    "development": {
        "responsibility": "Propose an implementation and reviewed patch",
        "inputs": ["candidate code revision (diff)", "acceptance criteria", "dataset coverage"],
        "allowed_tools": ["revision.read", "dataset.describe"],
        "output": "DevelopmentOutput: plan[], files_changed[], traceability[], risks[]",
        "evidence": "Traceability maps each changed file to requirement and test IDs",
        "error_strategy": "Diff is analysed as text only; nothing is executed in the application runtime",
    },
    "evaluation": {
        "responsibility": "Select required tests and interpret computed results",
        "inputs": ["computed metric results", "computed gate decisions"],
        "allowed_tools": ["evaluation.read"],
        "output": "EvaluationOutput: outcome (copied, read-only), findings[], limitations[]",
        "evidence": "Findings reference metric records (cell IDs) and gate IDs",
        "error_strategy": "A summary that contradicts the computed outcome is rejected and recorded",
    },
    "governance": {
        "responsibility": "Assemble privacy, permissions and model-risk findings",
        "inputs": ["control test results", "eligibility exclusions", "review status"],
        "allowed_tools": ["evaluation.read", "reviews.read"],
        "output": "GovernanceOutput: packet",
        "evidence": "References control test IDs and consent policy sections",
        "error_strategy": "Fail node; reviews can still proceed on the raw records",
    },
    "release": {
        "responsibility": "Summarize readiness and blockers",
        "inputs": ["release gate decisions", "approval status"],
        "allowed_tools": ["gates.read"],
        "output": "ReleaseOutput: recommendation, blockers[] (recommendation is not authorization)",
        "evidence": "Each blocker names its gate ID and owner",
        "error_strategy": "A summary claiming readiness while gates block is rejected",
    },
    "monitoring": {
        "responsibility": "Summarize observed changes and supporting evidence",
        "inputs": ["alert", "monitoring windows", "released and previous model configurations"],
        "allowed_tools": ["monitoring.read", "model_registry.read"],
        "output": "MonitoringOutput: findings[], suspected_cause, proposed_response, caveats[]",
        "evidence": "Cites cohort metrics and the configuration entry implicated",
        "error_strategy": "States that a statistical alert alone does not prove root cause",
    },
}


class ToolGateway:
    """Per-agent allow-list. Every call is timed and recorded."""

    def __init__(self, agent: str, roles: list[str], tools: dict[str, Callable[..., Any]]):
        self.agent, self.roles, self._tools = agent, roles, tools
        self.calls: list[dict] = []

    def call(self, name: str, **kwargs):
        if name not in CONTRACTS[self.agent]["allowed_tools"]:
            raise Forbidden("tool_not_allowed", f"Agent '{self.agent}' may not call tool '{name}'")
        t0 = time.perf_counter()
        try:
            return self._tools[name](**kwargs)
        finally:
            self.calls.append({"tool": name, "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
                               "args": {k: v for k, v in kwargs.items() if k != "roles"}})


def default_tools(roles: list[str], extra: dict | None = None) -> dict:
    kb = get_kb()
    t = {
        "kb.search": lambda query, k=3, include_unapproved=False: kb.search(query, roles, k=k, include_unapproved=include_unapproved),
        "kb.validate": lambda ref: kb.validate_citation(ref),
        "kb.conflicts": lambda: kb.conflicts(),
    }
    t.update(extra or {})
    return t


class AgentResult(BaseModel):
    agent: str
    summary: str
    data: dict = Field(default_factory=dict)
    refs: list[dict] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Requirements
# ---------------------------------------------------------------------------

AMBIGUITY_RULES = [
    ("correct_match", r"\b(improv\w*|recommend\w*|match\w*|accura\w*|performance)\b",
     "What counts as a correct shade match, and which metric is primary vs secondary?", "domain_reviewer", "top-1 match correct reference shade"),
    ("group_definitions", r"(skin[- ]tones?|deeper|darker|lighter|groups?)",
     "How are skin-tone groups defined, under which approved grouping protocol, and which cell is the target?", "domain_reviewer", "grouping protocol strata synthetic"),
    ("lighting_protocol", r"(lighting|light\b|indoor|outdoor|daylight)",
     "Which lighting categories and capture protocol define 'warm indoor lighting'?", "qa_engineer", "lighting categories capture protocol"),
    ("reference_labels", r"\b(improv\w*|correct|match\w*|performance)\b",
     "Where do reference shade labels come from, and who establishes that they are valid?", "domain_reviewer", "reference labels label protocol"),
    ("acceptable_regression", r"(preserv\w*|without (hurting|degrading)|other tested groups|other groups)",
     "How much may any other tested group regress, and how much must the target improve?", "product_owner", "regression percentage points release gates"),
    ("supported_devices", None,
     "Which devices are supported and covered by evaluation data?", "qa_engineer", "supported devices cohort validated"),
    ("recapture", r"(recommend\w*|image|photo|lighting)",
     "When should the system request another image instead of recommending a shade?", "domain_reviewer", "request another image quality"),
    ("release_evidence", None,
     "What evidence is required for release (sample sizes, control tests, freshness)?", "release_manager", "release gates evidence samples"),
]


def requirements_agent(gw: ToolGateway, facts: dict) -> AgentResult:
    stmt: str = facts["statement"]
    low = stmt.lower()
    demo = facts.get("demo_clarifications", {})
    ambiguities, refs = [], []
    for key, pattern, question, owner, query in AMBIGUITY_RULES:
        if pattern is None:
            triggered = key == "release_evidence" or "device" not in low
            trigger = "always required" if key == "release_evidence" else "no device scope stated"
        else:
            m = re.search(pattern, low)
            triggered, trigger = bool(m), (f"term '{m.group(0)}'" if m else "")
        if not triggered:
            continue
        hits = gw.call("kb.search", query=query, k=1)
        rel = [{k: h[k] for k in ("source_id", "source_version", "section", "excerpt", "retrieved_at")} for h in hits]
        refs += rel
        ambiguities.append({"key": key, "question": question, "owner_role": owner, "required": True, "trigger": trigger,
                            "suggested_answer": demo.get(key, {}).get("answer"),
                            "suggested_structured": demo.get(key, {}).get("structured"), "related_guidance": rel})
    answered = facts.get("answered", {})
    criteria = build_acceptance_criteria(answered) if answered and all(a["key"] in answered for a in ambiguities) else []
    open_n = sum(1 for a in ambiguities if a["key"] not in answered)
    summary = (f"Found {len(ambiguities)} ambiguities in the change statement; {open_n} unresolved. "
               + ("All required clarifications answered; acceptance criteria derived from structured answers."
                  if not open_n else "Requirement cannot be approved until required clarifications are answered."))
    return AgentResult(agent="requirements", summary=summary, refs=refs,
                       data={"scope": scope_from(answered), "ambiguities": ambiguities, "acceptance_criteria": criteria})


def scope_from(answered: dict) -> dict:
    s: dict = {}
    for v in answered.values():
        s.update(v.get("structured") or {})
    return s


def build_acceptance_criteria(answered: dict) -> list[dict]:
    s = scope_from(answered)
    out = []
    if "target_cell" in s and "target_min_improvement_pp" in s:
        out.append({"code": "AC-1", "text": f"Target cell {s['target_cell']} top-1 accuracy improves by at least {s['target_min_improvement_pp']} percentage points vs baseline on matched samples.",
                    "metric": "top1_delta_pp", "gate_id": "G-TARGET", "value": s["target_min_improvement_pp"]})
    if "max_regression_pp" in s:
        out.append({"code": "AC-2", "text": f"No required evaluation cell loses more than {s['max_regression_pp']} percentage points of top-1 accuracy vs baseline.",
                    "metric": "top1_delta_pp", "gate_id": "G-NO-REGRESSION", "value": s["max_regression_pp"]})
    if "min_samples_per_cell" in s:
        out.append({"code": "AC-3", "text": f"Every required cell has at least {s['min_samples_per_cell']} eligible paired samples; otherwise the result is INCONCLUSIVE.",
                    "metric": "n_eligible", "gate_id": "G-SAMPLES", "value": s["min_samples_per_cell"]})
    if "secondary_metric" in s:
        out.append({"code": "AC-4", "text": "Top-3 accuracy is reported for every cell as a secondary metric (not gated).",
                    "metric": "top3_accuracy_pct", "gate_id": None, "value": None})
    if s.get("privacy_tests") == "all_pass":
        out.append({"code": "AC-5", "text": "All privacy and authorization control tests pass.", "metric": "control_tests", "gate_id": "G-CONTROLS", "value": None})
    if s.get("abstention") == "counts_as_incorrect":
        out.append({"code": "AC-6", "text": "Abstentions remain in the denominator and count as incorrect.", "metric": "denominator", "gate_id": "G-ABSTENTION-DENOMINATOR", "value": None})
    if s.get("unvalidated"):
        out.append({"code": "AC-7", "text": f"Unvalidated device cohorts {s['unvalidated']} are watched in post-release monitoring.", "metric": "monitoring", "gate_id": None, "value": None})
    return out


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

EVIDENCE_TOPICS = [
    ("Definition of a correct match", "top-1 match correct reference shade abstention denominator", "SPEC-SHADE-001"),
    ("Release gates", "release gates samples regression target percentage points", "POL-REL-005"),
    ("Evaluation protocol", "paired comparison bootstrap evaluation cells strata lighting", "PROT-EVAL-008"),
    ("Lighting protocol", "lighting categories capture protocol grey reference card", "SPEC-LIGHT-003"),
    ("Supported devices", "supported devices cohort validated DEV-T3", "SPEC-LIGHT-003"),
    ("Dataset composition and limitations", "dataset composition devices covered limitations grouping protocol", "DS-CARD-010"),
    ("Consent for evaluation", "consent permitted use evaluation retention", "POL-CONSENT-006"),
    ("Image recapture", "request another image quality re-capture triggers", "SPEC-IQ-002"),
    ("Calibration guidance", "warm indoor compensation curve deeper shade families", None),
    ("Third-party calibration notes", "vendor calibration note operator instructions", None),
]
REQUIRED_EVIDENCE = ["POL-REL-005", "PROT-EVAL-008", "DS-CARD-010", "SPEC-SHADE-001"]

CLAIMS_TO_CHECK = [
    ("Shade predictions for device cohort DEV-T3 have been evaluated", "DEV-T3 evaluated devices covered"),
    ("Reference labels are validated by measured colour references", "measured colour references label validity"),
    ("Equal subgroup accuracy demonstrates fairness", "fairness parity subgroup"),
]


def evidence_agent(gw: ToolGateway, facts: dict) -> AgentResult:
    citations, injection, seen = [], [], set()
    for purpose, query, expected in EVIDENCE_TOPICS:
        for hit in gw.call("kb.search", query=query, k=2, include_unapproved=True):
            key = (hit["source_id"], hit["source_version"], hit["section"])
            if key in seen:
                continue
            seen.add(key)
            v = gw.call("kb.validate", ref=hit)
            usable = v["status"] == "VALID" and not hit["injection_patterns"]
            c = {**{k: hit[k] for k in ("source_id", "source_version", "title", "section", "heading", "excerpt", "retrieved_at", "status", "effective_date")},
                 "purpose": purpose, "validation_status": v["status"], "flags": hit["flags"], "usable_as_authority": usable}
            citations.append(c)
            if hit["injection_patterns"]:
                injection.append({"source_id": hit["source_id"], "section": hit["section"], "patterns": hit["injection_patterns"],
                                  "action": "excerpt kept as data; instructions ignored; not usable as authority"})
    conflicts = gw.call("kb.conflicts")
    cited_ids = {c["source_id"] for c in citations if c["usable_as_authority"]}
    missing = [d for d in REQUIRED_EVIDENCE if d not in cited_ids]
    unsupported = []
    for claim, q in CLAIMS_TO_CHECK:
        hits = gw.call("kb.search", query=q, k=1)
        unsupported.append({"claim": claim, "status": "UNKNOWN",
                            "note": "No approved source supports this claim; it must not be asserted.",
                            "nearest": {k: hits[0][k] for k in ("source_id", "source_version", "section", "excerpt")} if hits else None})
    summary = (f"Retrieved {len(citations)} cited excerpts ({sum(c['usable_as_authority'] for c in citations)} usable as authority). "
               f"{len(conflicts)} outdated-version conflicts flagged; {len(injection)} instruction-like passages ignored. "
               + (f"Missing required evidence: {', '.join(missing)}." if missing else "All required evidence sources are cited."))
    return AgentResult(agent="evidence", summary=summary, refs=[c for c in citations if c["usable_as_authority"]],
                       data={"citations": citations, "conflicts": conflicts, "unsupported_claims": unsupported,
                             "injection_flags": injection, "missing_required": missing})


# ---------------------------------------------------------------------------
# Impact
# ---------------------------------------------------------------------------

def impact_agent(gw: ToolGateway, facts: dict) -> AgentResult:
    smap = gw.call("system_map.read")
    ds = gw.call("dataset.describe")
    words = set(re.findall(r"[a-z\-]+", facts["statement"].lower()))
    for k, v in (facts.get("scope") or {}).items():
        words |= set(re.findall(r"[a-z\-]+", f"{k} {v}".lower()))
    comps = []
    for c in smap["components"]:
        hit = sorted(set(c["tags"]) & words)
        if hit:
            comps.append({**c, "matched_terms": hit})
    tests = [{**t, "matched_terms": sorted(set(t["tags"]) & words)} for t in smap["tests"] if set(t["tags"]) & words]
    owners = sorted({c["owner_role"] for c in comps} | {t["owner_role"] for t in tests})
    risks = []
    scope_devices = set((facts.get("scope") or {}).get("devices", []))
    unvalidated = (facts.get("scope") or {}).get("unvalidated", [])
    if unvalidated:
        risks.append({"risk": f"Device cohorts {unvalidated} have no evaluation samples (dataset covers {ds['devices_covered']}). "
                              "Offline evaluation cannot detect device-specific defects there; plan monitoring.",
                      "severity": "high", "ref": {"source_id": "DS-CARD-010", "source_version": "1.0", "section": "§4"}})
    if scope_devices and not scope_devices <= set(ds["devices_covered"]):
        risks.append({"risk": "Declared supported devices exceed evaluation coverage.", "severity": "high",
                      "ref": {"source_id": "SPEC-LIGHT-003", "source_version": "1.1", "section": "§3"}})
    risks.append({"risk": "Lighting-specific preprocessing can shift results in non-target cells; every required cell must be compared.",
                  "severity": "medium", "ref": {"source_id": "PROT-EVAL-008", "source_version": "2.0", "section": "§1"}})
    risks.append({"risk": "Tone strata are synthetic attributes; results do not validate any real-world grouping method.",
                  "severity": "medium", "ref": {"source_id": "DS-CARD-010", "source_version": "1.0", "section": "§2"}})
    summary = (f"{len(comps)} components, {len(tests)} tests and {len(owners)} owner roles affected. "
               f"{sum(r['severity'] == 'high' for r in risks)} high-severity risks flagged.")
    return AgentResult(agent="impact", summary=summary, refs=[r["ref"] for r in risks],
                       data={"components": comps, "tests": tests, "owners": owners, "risks": risks})


# ---------------------------------------------------------------------------
# Development
# ---------------------------------------------------------------------------

def development_agent(gw: ToolGateway, facts: dict) -> AgentResult:
    rev = gw.call("revision.read")
    ds = gw.call("dataset.describe")
    files = re.findall(r"^diff --git a/(\S+)", rev["diff"], flags=re.M)
    risks = []
    removed_or_added = [l for l in rev["diff"].splitlines() if l[:1] in "+-" and not l.startswith(("+++", "---"))]
    device_changes = []
    for i, line in enumerate(rev["diff"].splitlines()):
        m = re.match(r'^\s+"(DEV-T\d)": \{', line)
        if m:
            device_changes.append(m.group(1))
    for d in sorted(set(device_changes)):
        if any(l.startswith(("+", "-")) for l in removed_or_added) and d not in ds["devices_covered"]:
            risks.append({"risk": f"Diff changes the lighting-profile map for {d}, which has no evaluation samples. "
                                  "Offline evaluation cannot verify this entry; add a device test or monitoring watch.",
                          "severity": "high", "file": "config/lighting_profile_map.json"})
    trace = [{"file": f, "requirement_refs": rev["requirement_refs"], "test_refs": rev["test_refs"]} for f in files]
    plan = [
        "Apply the revision in an isolated build workspace (not the application runtime).",
        "Rebuild the model artifact and register its digest.",
        f"Run evaluation config {facts.get('evaluation_config_id')} on held-out split; compare all required cells.",
        "Request code review from someone other than the author.",
    ]
    summary = f"Revision {rev['revision_id']} changes {len(files)} files; mapped to {', '.join(rev['requirement_refs'])}. {len(risks)} risks flagged."
    return AgentResult(agent="development", summary=summary,
                       data={"revision_id": rev["revision_id"], "plan": plan, "files_changed": files, "traceability": trace,
                             "risks": risks, "executed_code": False})


# ---------------------------------------------------------------------------
# Evaluation interpretation
# ---------------------------------------------------------------------------

def evaluation_agent(gw: ToolGateway, facts: dict) -> AgentResult:
    ev = gw.call("evaluation.read")
    outcome = ev["outcome"]
    cells = ev["cells"]
    worst = min(cells.items(), key=lambda kv: kv[1]["delta"]["top1_delta_pp"])
    ov = ev["overall"]["delta"]["top1_delta_pp"]
    findings = [f"Overall top-1 accuracy changed by {ov:+.2f} pp ({ev['overall']['baseline']['top1_accuracy_pct']}% → {ev['overall']['candidate']['top1_accuracy_pct']}%, n={ev['overall']['baseline']['n_eligible']})."]
    t = ev["target_cell"]
    findings.append(f"Target cell {t}: {cells[t]['delta']['top1_delta_pp']:+.2f} pp (n={cells[t]['baseline']['n_eligible']}).")
    findings.append(f"Worst cell {worst[0]}: {worst[1]['delta']['top1_delta_pp']:+.2f} pp (CI {worst[1]['delta_ci95_pp'][0]:+.2f} to {worst[1]['delta_ci95_pp'][1]:+.2f}).")
    if ov > 0 and worst[1]["delta"]["top1_delta_pp"] < -ev["thresholds"]["max_regression_pp"]:
        findings.append(f"Aggregate improvement hides a subgroup regression in {worst[0]} beyond the {ev['thresholds']['max_regression_pp']} pp limit.")
    failed = [g["gate_id"] for g in ev["gates"] if g["status"] != "PASS"]
    if failed:
        findings.append("Blocking gates: " + ", ".join(failed) + ".")
    crosses = [c for c, v in cells.items() if v["delta_ci95_pp"][0] < 0 < v["delta_ci95_pp"][1]]
    limitations = [
        "Data and predictions are synthetic fixtures; no computer-vision inference or training occurred.",
        "Reference label validity is not established and requires expert review.",
        f"{len(cells)} cells are compared; some intervals will exclude zero by chance (no multiplicity correction applied).",
        f"{len(crosses)} cell deltas have 95% intervals spanning zero.",
        "Deterministic demo gates are illustrative and do not replace a production statistical review.",
        "Subgroup parity on synthetic strata does not demonstrate fairness.",
    ]
    summary = f"Computed outcome: {outcome}. " + " ".join(findings[:3])
    return AgentResult(agent="evaluation", summary=summary, refs=[{"record": f"evaluation:{ev['run_id']}"}],
                       data={"outcome": outcome, "findings": findings, "limitations": limitations, "note": "Outcome copied from the policy engine; read-only."})


# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------

def governance_agent(gw: ToolGateway, facts: dict) -> AgentResult:
    ev = gw.call("evaluation.read")
    reviews = gw.call("reviews.read")
    controls = ev.get("controls", [])
    failed = [c for c in controls if c["status"] != "PASS"]
    packet = {
        "controls": controls,
        "eligibility_exclusions": ev.get("exclusions", {}),
        "required_reviews": reviews["required"],
        "review_status": reviews["status"],
        "model_risk": [
            "Seeded synthetic strata; real grouping requires domain, privacy and evaluation review (DPIA-007 §1, restricted).",
            "Unvalidated device cohorts are not covered by offline evaluation.",
        ],
        "references": [{"source_id": "POL-CONSENT-006", "source_version": "1.3", "section": "§1"},
                       {"source_id": "POL-CONSENT-006", "source_version": "1.3", "section": "§2"}],
    }
    summary = (f"{len(controls) - len(failed)}/{len(controls)} privacy and authorization control tests passed. "
               f"Reviews outstanding: {', '.join(k for k, v in reviews['status'].items() if v != 'APPROVE') or 'none'}.")
    return AgentResult(agent="governance", summary=summary, refs=packet["references"], data={"packet": packet})


# ---------------------------------------------------------------------------
# Release
# ---------------------------------------------------------------------------

def release_agent(gw: ToolGateway, facts: dict) -> AgentResult:
    r = gw.call("gates.read")
    blockers = [{"gate_id": g["gate_id"], "owner_role": g["owner_role"], "observed": g["observed"], "status": g["status"]}
                for g in r["gates"] if g["status"] != "PASS"]
    rec = "READY_FOR_AUTHORIZATION" if not blockers else "BLOCKED"
    summary = (f"Recommendation: {rec}. " + ("No blocking gates; a distinct authorized approver must still decide."
               if not blockers else f"{len(blockers)} blockers: " + ", ".join(b["gate_id"] for b in blockers) + "."))
    return AgentResult(agent="release", summary=summary, data={"recommendation": rec, "blockers": blockers,
                       "note": "Recommendation is not authorization."})


# ---------------------------------------------------------------------------
# Monitoring
# ---------------------------------------------------------------------------

def monitoring_agent(gw: ToolGateway, facts: dict) -> AgentResult:
    m = gw.call("monitoring.read")
    reg = gw.call("model_registry.read")
    alert = m["alert"]
    device, lighting = alert["scope"].split("|")
    rel_map, prev_map = reg["released_lpm"], reg["previous_lpm"]
    findings = [f"{alert['scope']}: observed top-1 {alert['observed']['accuracy_pct']}% on {alert['observed']['labelled']} labelled sessions "
                f"vs reference {alert['observed']['reference_pct']}% (Wilson 95% upper {alert['observed']['wilson95'][1]}%)."]
    other = [f"{k}: {v['accuracy_pct']}% (n={v['labelled']})" for k, v in m["cohort_cells"].items()
             if k.startswith(device) and k != alert["scope"]]
    if other:
        findings.append(f"Other {device} cells: " + "; ".join(other))
    same_light = [f"{k}: {v['accuracy_pct']}% (n={v['labelled']})" for k, v in m["cohort_cells"].items()
                  if k.endswith("|" + lighting) and not k.startswith(device)]
    if same_light:
        findings.append(f"Same lighting on other devices: " + "; ".join(same_light))
    cause = None
    mapped = rel_map.get(device, {}).get(lighting)
    if mapped and mapped != lighting:
        cause = {"hypothesis": f"Released lighting-profile map {reg['released_lpm_id']} maps {device}/{lighting} to '{mapped}' "
                               f"(previous {reg['previous_lpm_id']}: '{prev_map.get(device, {}).get(lighting)}').",
                 "evidence": [f"config:{reg['released_lpm_id']}:{device}.{lighting}", f"alert:{alert['id']}"],
                 "confidence": "supported by configuration diff and cohort pattern; confirm with a targeted test"}
    caveats = ["A statistical alert alone does not prove root cause.",
               "Observations are simulated; reference labels are synthetic and arrive with delay.",
               "Confirm the hypothesis with a targeted device test before closing the incident."]
    proposal = {"action": "rollback", "target_model_id": reg["previous_model_id"],
                "requires": "authorized release-manager approval (prototype policy POL-REL-005 §5)"} if cause else \
               {"action": "investigate_further", "requires": "more labelled sessions"}
    summary = ("Monitoring alert investigated. " + (cause["hypothesis"] + " Proposed response: rollback pending authorized review."
               if cause else "No configuration cause found; further investigation proposed."))
    return AgentResult(agent="monitoring", summary=summary, refs=[{"record": f"alert:{alert['id']}"}],
                       data={"findings": findings, "suspected_cause": cause, "proposed_response": proposal, "caveats": caveats})


AGENTS: dict[str, Callable[[ToolGateway, dict], AgentResult]] = {
    "requirements": requirements_agent, "evidence": evidence_agent, "impact": impact_agent,
    "development": development_agent, "evaluation": evaluation_agent, "governance": governance_agent,
    "release": release_agent, "monitoring": monitoring_agent,
}

CONTRADICTION = re.compile(r"(all gates pass|ready (for|to) release|release (is )?approved|approved for release|passed all)", re.I)


def summary_contradicts(agent: str, computed: str | None, text: str) -> bool:
    """Reject LLM summaries that claim a favourable result the deterministic engine did not produce."""
    return agent in {"evaluation", "release"} and computed not in {"PASS", "READY_FOR_AUTHORIZATION"} and bool(CONTRADICTION.search(text))
