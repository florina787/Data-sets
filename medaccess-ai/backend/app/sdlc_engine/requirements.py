"""Requirements Agent: deterministic requirement analysis.

Produces user stories, Gherkin acceptance criteria, dependencies, traceability IDs
and - most importantly - the open questions a human must answer before design.
"""

from __future__ import annotations

import hashlib
import re

from app.services.copilot_nlu import classify_service

AMBIGUITY_RULES = [
    ("VERIFIED_ONLY", lambda t: "appointment" in t and "verified" not in t,
     "Are only verified appointments eligible, or may advertised/unverified openings be presented?"),
    ("REQUISITION_ELIGIBILITY", lambda t: "requisition" not in t and "referral" not in t,
     "Does an earlier slot qualify if the facility cannot accept the patient's requisition?"),
    ("NO_RESULT_BEHAVIOUR", lambda t: not re.search(r"no (result|appointment)s?|none (found|available)", t),
     "What happens if no appointment exists within the radius?"),
    ("RADIUS_EXPANSION", lambda t: re.search(r"\d+\s*km", t) and "expand" not in t,
     "Can users expand the search radius, and who approves it?"),
    ("PRIVATE_PAY", lambda t: "private" not in t and "pay" not in t,
     "Should private-pay facilities be included?"),
    ("BASELINE", lambda t: "earlier" in t and "existing" not in t and "current" not in t,
     "'Earlier' relative to what baseline - the patient's existing appointment date?"),
    ("ACCESSIBILITY", lambda t: "accessib" not in t and "wheelchair" not in t,
     "Must accessibility needs (e.g., wheelchair access) filter results?"),
    ("FRESHNESS", lambda t: "fresh" not in t and "stale" not in t and "minutes" not in t,
     "How recent must availability data be to count as verified?"),
    ("NOTIFICATION_CONSENT", lambda t: re.search(r"notif|remind|alert", t) and "consent" not in t,
     "What consent is required before notifications are sent?"),
]


def trace_id(text: str) -> str:
    return "REQ-" + hashlib.sha256(text.strip().lower().encode()).hexdigest()[:6].upper()


def analyze(text: str) -> dict:
    t = (text or "").lower()
    rid = trace_id(text)
    svc = classify_service(text)
    radius = re.search(r"(\d+)\s*km", t)
    actor = "patient" if "patient" in t else "user"
    service = svc.value if svc else "the requested service"
    rad = f"{radius.group(1)} km" if radius else "a chosen radius"
    ambiguities = [{"id": f"{rid}-Q{i + 1}", "code": code, "question": q, "blocking": code in
                    {"VERIFIED_ONLY", "REQUISITION_ELIGIBILITY"}}
                   for i, (code, rule, q) in enumerate(AMBIGUITY_RULES) if rule(t)]
    stories = [
        {"id": f"{rid}-US1", "story": f"As a {actor}, I want to search for {service} appointments within {rad} "
                                      "so that I can find an earlier option."},
        {"id": f"{rid}-US2", "story": f"As a {actor}, I want to see whether each opening is verified so that I "
                                      "don't rely on unconfirmed availability."},
        {"id": f"{rid}-US3", "story": f"As a {actor}, I want to know if my requisition is accepted so that I only "
                                      "pursue options I can use."},
        {"id": f"{rid}-US4", "story": f"As a {actor}, I want a booking handoff I approve myself so that nothing "
                                      "is submitted without my consent."},
    ]
    criteria = [
        {"id": f"{rid}-AC1", "story": f"{rid}-US1",
         "gherkin": f"Given a {actor} in Toronto\nWhen they search for {service} within {rad}\n"
                    f"Then only facilities within {rad} (straight-line, inclusive) are returned"},
        {"id": f"{rid}-AC2", "story": f"{rid}-US2",
         "gherkin": "Given an advertised but unconfirmed opening\nWhen results are ranked\n"
                    "Then it is listed as an UNVERIFIED_POSSIBILITY and never as a confirmed alternative"},
        {"id": f"{rid}-AC3", "story": f"{rid}-US3",
         "gherkin": "Given a facility that does not accept the patient's requisition format\nWhen eligibility is "
                    "evaluated\nThen the facility is INELIGIBLE and the patient is told to contact their clinician"},
        {"id": f"{rid}-AC4", "story": f"{rid}-US4",
         "gherkin": "Given a selected opening\nWhen the patient requests a booking handoff\nThen the workflow pauses "
                    "for patient approval and no booking is marked confirmed without provider confirmation"},
    ]
    deps = ["Authorized availability source (adapter)", "Facility directory", "Requisition rules",
            "Geolocation (location -> coordinates)", "Human approval service", "Audit trail"]
    return {"id": rid, "requirement": text, "service": svc.value if svc else None,
            "radius_km": int(radius.group(1)) if radius else None, "user_stories": stories,
            "acceptance_criteria": criteria, "dependencies": deps, "ambiguities": ambiguities,
            "status": "NEEDS_CLARIFICATION" if any(a["blocking"] for a in ambiguities) else "READY_FOR_DESIGN",
            "method": "deterministic rule-based analysis"}
