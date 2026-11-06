"""Action-planning node: apply policy and select one permitted next step.

Tools: none beyond the evidence bundle and the policy engine. The model (in
LIVE mode) may only choose among actions the policy engine already allows and
write purpose/uncertainty text; it cannot change payloads, approvals or roles.
"""
from __future__ import annotations

import json

from ..policies import engine
from .contracts import (
    ActionPlanLLM, DiagnosisOutput, EvidenceBundle, PriorIntervention, RecommendationDraft,
    RefusedRequest, TriageOutput,
)
from .providers import Provider

SYSTEM_PROMPT = """You are the action-planning step of a telecom support workflow.
Choose exactly one action_type from the 'permitted_actions' list you are given; never invent
actions. Write a one-paragraph purpose and an honest uncertainty statement that names what the
evidence does not establish. Do not promise restoration times, credits or appointment slots.
Return JSON matching the schema."""

TOOLS: tuple[str, ...] = ()


def _kb(bundle: EvidenceBundle, doc_id: str, heading: str | None = None) -> str | None:
    for i in bundle.items:
        if i.source_type == "knowledge" and i.data.get("document_id") == doc_id and (
                heading is None or i.data.get("heading") == heading):
            return i.ref_id
    return None


def _prior_actions(bundle: EvidenceBundle) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for p in bundle.prior_actions:
        for a in p["actions"]:
            out.setdefault(a, []).append(p)
    return out


def _candidates(conclusion: str, prior: dict) -> list[str]:
    if conclusion == "AREA_INCIDENT":
        return ["associate_case_with_incident", "draft_customer_update"]
    if conclusion == "LINE_IMPAIRMENT":
        return ["create_technician_dispatch", "draft_customer_update"]
    if conclusion == "EQUIPMENT_FAULT":
        first = ("create_technician_dispatch" if "power_adapter_check" in prior
                 else "suggest_customer_troubleshooting")
        rest = [a for a in ("suggest_customer_troubleshooting", "create_technician_dispatch",
                            "reset_equipment") if a != first]
        return [first, *rest]
    return []


def plan(case_id: str, service_id: str, triage: TriageOutput, bundle: EvidenceBundle,
         diagnosis: DiagnosisOutput, provider: Provider, budget_used: int,
         forced_action: str | None = None):
    """Return (draft | None, policy_decision | None, facts, usage, notes, refused)."""
    facts = set(bundle.facts)
    prior = _prior_actions(bundle)
    by_ref = {i.ref_id: i for i in bundle.items}
    top = next((h for h in diagnosis.hypotheses if h.category == diagnosis.conclusion), None)
    notes: list[str] = []

    guide_step2 = _kb(bundle, "KB-TS-001", "Step 2 - Power adapter and ventilation check")
    if guide_step2:
        facts.add("approved_guide_steps")
    if "power_adapter_check" in prior:
        facts.add("guide_steps_already_failed")
    facts.add("cited_facts_only")  # drafts are generated only from cited bundle items

    # ---- Refusals: requests the workflow will not fulfil ----
    refused: list[RefusedRequest] = []
    incident_refs = [i for i in bundle.items if i.source_type == "incident" and "mapped_path" in i.flags]
    if "restoration_guarantee" in triage.special_requests:
        etr = next((i.data.get("estimated_restoration_at") for i in incident_refs
                    if i.data.get("active") and i.data.get("estimated_restoration_at")), None)
        cites = [r for r in (_kb(bundle, "KB-RB-003", "Restoration estimates"),
                             _kb(bundle, "KB-COMM-005", "Content rules")) if r]
        cites += [i.ref_id for i in incident_refs if i.data.get("active")]
        refused.append(RefusedRequest(
            request="Guaranteed restoration time",
            reason=("Restoration times are never guaranteed. " +
                    (f"The only figure that may be quoted is the published estimate ({etr})."
                     if etr else "No restoration estimate is published on the incident record, so none "
                                 "can be given.")),
            citations=cites))
    if {"bill_credit", "compensation"} & set(triage.special_requests):
        cites = [r for r in (_kb(bundle, "KB-COMM-005", "Credits and compensation"),
                             _kb(bundle, "KB-POL-006", "Roles")) if r]
        decision = engine.evaluate("apply_bill_credit", facts)
        refused.append(RefusedRequest(
            request="Bill credit / compensation",
            reason="Bill credits are disabled in this prototype and eligibility is never inferred by the "
                   "assistant. Note the request for review under billing rules. " + " ".join(decision.reasons),
            citations=cites))
    for i in bundle.items:
        if "prompt_injection" in i.flags:
            refused.append(RefusedRequest(
                request=f"Instructions embedded in {i.source_id}",
                reason="Instruction-like text inside a retrieved record was quarantined and ignored. "
                       "Records are evidence, not instructions; actions and approvals follow policy only.",
                citations=[i.ref_id]))

    candidates = _candidates(diagnosis.conclusion, prior)
    if forced_action is not None and candidates:
        candidates = [forced_action] + [a for a in candidates if a != forced_action]
    if not candidates or top is None:
        return None, None, sorted(facts), None, notes, refused

    evaluations = {a: engine.evaluate(a, facts) for a in candidates}
    permitted = [a for a in candidates if evaluations[a].allowed]
    alternatives = [{"action_type": a, "allowed": evaluations[a].allowed,
                     "executable": evaluations[a].executable, "mvp_behavior": evaluations[a].mvp_behavior,
                     "reasons": evaluations[a].reasons} for a in candidates]
    # Show why commonly-expected actions are not recommended.
    for extra in ("create_technician_dispatch", "suggest_customer_troubleshooting",
                  "associate_case_with_incident", "apply_bill_credit"):
        if extra not in evaluations:
            d = engine.evaluate(extra, facts)
            alternatives.append({"action_type": extra, "allowed": d.allowed, "executable": d.executable,
                                 "mvp_behavior": d.mvp_behavior, "reasons": d.reasons})
    if not permitted:
        notes.append("No candidate action satisfies policy; escalation required.")
        return None, None, sorted(facts), None, notes, refused

    chosen = permitted[0]
    usage = None
    llm_text: ActionPlanLLM | None = None
    if forced_action is not None:
        chosen = forced_action if forced_action in permitted else None
        if chosen is None:
            return None, evaluations[forced_action], sorted(facts), None, notes, refused
    elif provider.is_live:
        ctx = {"conclusion": diagnosis.conclusion, "summary": diagnosis.summary,
               "permitted_actions": permitted, "special_requests": triage.special_requests}
        llm_text, usage = provider.generate(system=SYSTEM_PROMPT, user=json.dumps(ctx),
                                            schema=ActionPlanLLM, budget_used=budget_used)
        if llm_text.action_type in permitted:
            chosen = llm_text.action_type
        else:
            notes.append(f"LIVE planner proposed non-permitted action '{llm_text.action_type}'; rejected.")
            llm_text = None

    evidence_refs = list(top.supporting_refs)
    prerequisites: list[str] = []
    payload: dict
    if chosen == "associate_case_with_incident":
        inc = next(i for i in incident_refs if "AREA_INCIDENT" in i.supports)
        payload = {"case_id": case_id, "incident_id": inc.data["incident_id"]}
        evidence_refs += [r for r in ("MAPPING", _kb(bundle, "KB-RB-003", "Linking a case to an incident")) if r]
        purpose = (f"Link this case to {inc.data['incident_id']} so the customer is covered by the incident's "
                   "restoration and communications, and avoid individual troubleshooting or dispatch during "
                   "an active incident on the mapped path.")
        prerequisites = ["Incident is on the service's mapped path (verified via service mapping)",
                         "Incident interval overlaps the reported symptom window",
                         "Specialist confirms the association"]
    elif chosen == "create_technician_dispatch":
        reason = "line impairment" if diagnosis.conclusion == "LINE_IMPAIRMENT" else "suspected equipment fault"
        payload = {"case_id": case_id, "service_id": service_id, "dispatch_type": "repair_visit",
                   "reason": reason, "evidence_refs": sorted(top.supporting_refs),
                   "appointment": "not scheduled - availability to be confirmed with the customer"}
        evidence_refs += [r for r in (_kb(bundle, "KB-DSP-004", "Evidence prerequisites"),
                                      _kb(bundle, "KB-DSP-004", "Line impairment indicators"), "PEERS") if r]
        purpose = (f"Send a technician to locate and repair the {reason} indicated by fresh measurements. "
                   "Customer-side troubleshooting already tried is not repeated.")
        prerequisites = ["Fresh diagnostics within 24 hours", "No active incident on the mapped path",
                         "Supervisor approval by someone other than the proposer",
                         "Appointment slot confirmed with the customer (not inferred)"]
    elif chosen == "suggest_customer_troubleshooting":
        payload = {"case_id": case_id, "guide_ref": guide_step2,
                   "steps": by_ref[guide_step2].excerpt if guide_step2 else "",
                   "delivery": "read to customer by specialist; nothing is sent automatically"}
        evidence_refs += [r for r in (guide_step2, _kb(bundle, "KB-MODEM-002", "Unexpected reboots"),
                                      _kb(bundle, "KB-MODEM-002", "Known firmware note")) if r]
        purpose = ("Ask the customer to check the modem's power adapter and ventilation, the approved first "
                   "step when unexpected reboots occur with healthy line metrics. A modem restart is not "
                   "requested again.")
        prerequisites = ["Step not already attempted for this symptom", "No active incident on the mapped path"]
    else:  # draft_customer_update
        facts_lines = [by_ref[r].excerpt for r in top.supporting_refs if by_ref[r].kind != "note"][:3]
        payload = {"case_id": case_id, "channel": "draft_only",
                   "body": "Update on your internet service: " + " ".join(facts_lines),
                   "citations": top.supporting_refs[:3]}
        purpose = "Prepare a cited customer update. It is a draft and is never sent by this prototype."
        prerequisites = ["Specialist reviews the draft", "Only cited facts included"]

    prior_out: list[PriorIntervention] = []
    for action, entries in prior.items():
        repeated = (chosen == "suggest_customer_troubleshooting" and action == "power_adapter_check")
        n = len(entries)
        prior_out.append(PriorIntervention(
            source_ref=entries[-1]["source_ref"], action=action, outcome=entries[-1]["outcome"],
            repeated_in_recommendation=repeated,
            justification=(f"Recorded as already tried in {n} source(s) "
                           f"({', '.join(e['source_ref'] for e in entries)}) without resolving the symptom; not repeated."
                           if not repeated else "Repeated because new evidence justifies it.")))

    oppose = [r for r in top.opposing_refs]
    uncertainty = (f"Evidence sufficiency: {top.sufficiency}. "
                   + (f"Opposing evidence: {', '.join(oppose)}. " if oppose else "No measured evidence opposes this. ")
                   + {"associate_case_with_incident": "Restoration time is unknown; association does not prove "
                                                      "every symptom is caused by the incident.",
                      "create_technician_dispatch": "The exact fault location is not established remotely; "
                                                    "appointment availability is unknown.",
                      "suggest_customer_troubleshooting": "The power check may not resolve the reboots; if it "
                                                          "does not, equipment replacement may be needed.",
                      "draft_customer_update": "The draft has not been reviewed or sent."}[chosen])
    purpose_text = llm_text.purpose if llm_text else purpose
    uncertainty_text = (llm_text.uncertainty + " " + uncertainty) if llm_text else uncertainty
    draft = RecommendationDraft(
        action_type=chosen, payload=payload, purpose=purpose_text, prerequisites=prerequisites,
        evidence_refs=list(dict.fromkeys(evidence_refs)), uncertainty=uncertainty_text,
        prior_interventions=prior_out, refused_requests=refused,
        alternatives=[a for a in alternatives if a["action_type"] != chosen])
    return draft, evaluations[chosen], sorted(facts), usage, notes, refused


def build_for_action(action_type: str, case_id: str, service_id: str, triage: TriageOutput,
                     bundle: EvidenceBundle, diagnosis: DiagnosisOutput):
    """Deterministic plan for a specialist-selected alternative action."""
    from .providers import DemoProvider

    draft, decision, facts, _, _, _ = plan(case_id, service_id, triage, bundle, diagnosis,
                                           DemoProvider(), 0, forced_action=action_type)
    return draft, decision, facts
