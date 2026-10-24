"""Intake & Intent Agent: deterministic routing and input normalization.

No language model is involved. Each workflow has weighted patterns; the best
score wins. Security-relevant intents (data export) are matched first and
cannot be outscored. Ambiguous or empty queries produce a clarifying question.
"""

from __future__ import annotations

import re
from typing import Any

MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
          "november", "december"]

PATTERNS: dict[str, list[tuple[str, float]]] = {
    "maintenance_investigation": [
        (r"\bvibration\b", 3), (r"\binvestigat", 2), (r"\banomal", 2), (r"maintenance (plan|evidence)", 2),
        (r"\btechnician", 1), (r"\bdiagnos", 2), (r"\bAC-\d{3}\b", 1.5), (r"recovery options", 0.5)],
    "scenario_compare": [
        (r"\b\d{2,3}[- ]?(hour|hr|h)\b", 2.5), (r"\bscenario", 2.5), (r"\bdelay", 1.5), (r"\bcompare\b", 1),
        (r"what[- ]if", 2.5), (r"lead[- ]time", 1.5)],
    "downtime_analysis": [
        (r"\bdowntime\b", 3), (r"\bwhy\b", 1), (r"\b(rise|rose|increase|spike|jump)", 2),
        (r"\b(" + "|".join(MONTHS) + r")\b", 1.5), (r"\btrend", 1), (r"confidence", 1)],
    "legacy_assessment": [
        (r"\blegacy\b", 3), (r"\bschema\b", 2), (r"\boracle\b", 2), (r"moderni[sz]", 2), (r"\bcobol\b", 2),
        (r"rewrit", 1.5), (r"non-invasive", 2), (r"\bmonolith", 1.5)],
    "bridge_generation": [
        (r"\badapter\b", 3), (r"\bmcp\b", 2), (r"generate (a )?(read-only )?api", 3), (r"\bbridge\b", 2),
        (r"inventory view", 1.5), (r"\bread-only\b", 1)],
    "governance_review": [
        (r"blocked", 3), (r"\bdenied\b|\bdenials?\b", 2.5), (r"\bpolic(y|ies)\b", 2), (r"governing", 1.5),
        (r"agent actions", 2), (r"audit", 1)],
    "executive_pitch": [
        (r"\bpitch\b", 3), (r"\bexecutive\b", 2), (r"\broi\b", 2), (r"90[- ]day", 2.5), (r"roadmap", 1.5),
        (r"\bcosts?\b", 1), (r"\bpilot\b", 1.5)],
    "document_freshness": [
        (r"\bstale\b", 3), (r"provenance", 3), (r"\bdocuments?\b", 1.5), (r"\brevision", 1.5), (r"missing", 1),
        (r"\boutdated|expired\b", 2)],
    "recovery_options": [
        (r"recovery options?", 3), (r"verified inventory", 3), (r"\bcompare\b.*\brecovery", 2), (r"\baog\b", 2),
        (r"\balternat", 1.5)],
    "parts_status": [
        (r"\bparts?\b", 1.5), (r"\binventory\b", 1.5), (r"\bsupplier", 2), (r"critical stock", 3),
        (r"\bP-\d{4}[A-Z]?\b", 2), (r"lead[- ]time", 1)],
    "fleet_overview": [
        (r"\bfleet\b", 2.5), (r"\bhealth\b", 2), (r"\bavailability\b", 1.5), (r"overview", 2), (r"status of", 1)],
    "quality_investigation": [
        (r"nonconform|\bncr\b", 3), (r"corrective action|\bcapa\b", 3), (r"\bquality\b", 2), (r"supplier documentation", 2)],
}

EXPORT_VERB = re.compile(r"(?i)\b(export|send|e-?mail|forward|upload|share|copy|transfer|leak|dump)\b")
EXPORT_DEST = re.compile(r"(?i)(personal|private|my own|external|gmail|yahoo|hotmail|outlook\.com|dropbox|google drive|"
                         r"usb|[\w.+-]+@[\w-]+\.[\w.]+|\be-?mail\b|home)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
AIRCRAFT = re.compile(r"\bAC-\d{3}\b", re.I)
PART = re.compile(r"\bP-\d{4}[A-Z]?\b", re.I)
HOURS = re.compile(r"\b(\d{1,3})[- ]?(?:hour|hr|h)s?\b", re.I)

SUGGESTIONS = [
    "Investigate abnormal vibration on AC-204, retrieve maintenance evidence, check parts and draft a maintenance plan.",
    "Compare 24-hour and 48-hour delay scenarios for a replacement part.",
    "Why did aircraft downtime rise in October? Show causes, trend and confidence limits.",
    "Assess this legacy Oracle schema and recommend a non-invasive modernization path.",
    "Generate a read-only API and MCP adapter for the approved parts inventory view.",
    "Show me all blocked agent actions and explain the governing policy.",
    "Create an executive modernization pitch with costs, risks and a 90-day pilot roadmap.",
    "Show which maintenance documents are stale or missing provenance.",
    "Compare aircraft maintenance recovery options using verified inventory availability.",
    "Export restricted maintenance records to my personal email.",
]


def classify(query: str) -> dict[str, Any]:
    q = (query or "").strip()
    entities = {
        "aircraft": sorted({m.upper() for m in AIRCRAFT.findall(q)}),
        "parts": sorted({m.upper() for m in PART.findall(q)}),
        "hours": sorted({int(h) for h in HOURS.findall(q)}),
        "months": [m for m in MONTHS if re.search(rf"\b{m}\b", q, re.I)],
        "emails": EMAIL.findall(q),
    }
    if len(q) < 3:
        return {"workflow": "clarify", "confidence": 0.0, "scores": {}, "entities": entities,
                "reason": "Empty or very short query.", "suggestions": SUGGESTIONS}

    # Security first: an export/exfiltration request is routed to the governance
    # graph regardless of anything else in the sentence.
    if EXPORT_VERB.search(q) and EXPORT_DEST.search(q) and not re.search(r"(?i)\breport\b|\bpdf\b|\bbrief\b|download", q):
        dest = "personal_email" if re.search(r"(?i)personal|private|my own|gmail|yahoo|hotmail|home", q) else "external_email"
        return {"workflow": "data_export", "confidence": 1.0, "scores": {"data_export": 99}, "entities": entities,
                "destination": dest, "reason": "Export verb with an external or personal destination."}

    scores: dict[str, float] = {}
    for wf, pats in PATTERNS.items():
        s = sum(w for p, w in pats if re.search(p, q, re.I))
        if s:
            scores[wf] = round(s, 2)
    if not scores:
        return {"workflow": "clarify", "confidence": 0.0, "scores": {}, "entities": entities,
                "reason": "No workflow matched. Please pick one of the suggestions or rephrase.", "suggestions": SUGGESTIONS}
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], list(PATTERNS).index(kv[0])))
    best, top = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0.0
    confidence = round(min(1.0, top / 6.0) * (1.0 if top - second >= 1 else 0.8), 2)
    if top < 2:
        return {"workflow": "clarify", "confidence": confidence, "scores": scores, "entities": entities,
                "reason": f"Low-confidence match ('{best}'). Clarification needed.", "suggestions": SUGGESTIONS,
                "candidate": best}
    return {"workflow": best, "confidence": confidence, "scores": scores, "entities": entities,
            "reason": f"Highest pattern score {top} (runner-up {second})."}
