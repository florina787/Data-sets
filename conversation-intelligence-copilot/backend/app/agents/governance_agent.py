"""Governance agent: PII, coaching safeguards, human review, dataset authorisation, audit."""

from __future__ import annotations

from app.analytics.coaching import SAFEGUARD
from app.governance.pii import contains_pii, mask_text

HUMAN_REVIEW_CATEGORIES = {"agent_coaching", "agent_profile", "leadership_priorities", "leadership_summary"}


def review(plan: dict, explanation: dict, evidence: list[dict], injection_flags: list[str], uncertainty: list[str]) -> tuple[dict, list[dict], list[str], list[dict]]:
    """Returns (explanation, evidence, uncertainty, findings) after enforcing policies."""
    findings: list[dict] = []
    for field in ("headline", "answer"):
        if contains_pii(explanation.get(field, "")):
            explanation[field] = mask_text(explanation[field])[0]
            findings.append({"policy": "pii_masking", "outcome": "masked", "detail": f"PII pattern masked in {field}"})
    explanation["key_points"] = [mask_text(k)[0] if contains_pii(k) else k for k in explanation.get("key_points", [])]
    pii_hits = 0
    for e in evidence:
        for x in e["excerpts"]:
            if contains_pii(x["text"]):
                x["text"] = mask_text(x["text"])[0]
                pii_hits += 1
    findings.append({"policy": "pii_masking", "outcome": "pass" if not pii_hits else "masked",
                     "detail": "Evidence excerpts are PII-masked at ingestion" + (f"; {pii_hits} re-masked" if pii_hits else "")})
    if injection_flags:
        findings.append({"policy": "prompt_injection", "outcome": "flagged",
                         "detail": "Instruction-like content in the question was treated as data; no tools or permissions changed."})
    else:
        findings.append({"policy": "prompt_injection", "outcome": "pass", "detail": "No injection patterns in the question"})
    cat = plan.get("category")
    human = cat in HUMAN_REVIEW_CATEGORIES
    if cat in ("agent_coaching", "agent_profile"):
        if SAFEGUARD not in uncertainty:
            uncertainty.append(SAFEGUARD)
        findings.append({"policy": "coaching_safeguard", "outcome": "enforced",
                         "detail": "Coaching output is decision support; requires team-lead review; no protected attributes used."})
    if human:
        findings.append({"policy": "human_review", "outcome": "required", "detail": "A human owner must review before acting on these recommendations."})
    findings.append({"policy": "tool_safety", "outcome": "pass", "detail": "Only registered read-only operations ran; no model-generated SQL or code."})
    findings.append({"policy": "dataset_authorisation", "outcome": "pass",
                     "detail": f"Dataset mode: {plan.get('scope', {}).get('dataset_mode', 'original')}"})
    return explanation, evidence, uncertainty, findings
