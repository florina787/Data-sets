"""Groundedness score and hallucination risk for an answer, shown next to it in the UI.

Built only from checks the pipeline already runs, so the score is explainable:
  * numbers   - share of figures in the answer text that trace to verified results (weight 0.5)
  * quotes    - share of quoted excerpts that match their source message word for word (weight 0.3)
  * coverage  - share of top-ranked claims with a supporting conversation attached (weight 0.2)
Components that do not apply (no figures, no quotes, no ranking) are left out and the
weights renormalised. The answer's basis matters as much as the score: a model's
general-knowledge answer is never scored, it is labelled as not from the dataset.
"""

from __future__ import annotations

import re

from app.agents.grounding import _NUM, allowed_numbers, ungrounded_numbers

WEIGHTS = {"numbers": 0.5, "quotes": 0.3, "coverage": 0.2}
_RATIO = re.compile(r"(\d+)\s*/\s*(\d+)")
_TRIVIAL = {str(i) for i in range(0, 11)}


def _review_check(review: dict | None, name: str) -> dict | None:
    return next((c for c in (review or {}).get("checks", []) if c.get("check") == name), None)


def _ratio(detail: str) -> tuple[int, int] | None:
    m = _RATIO.search(detail or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def score(explanation: dict, source: str, facts: dict, evidence_review: dict | None, plan: dict) -> dict:
    if source == "general_knowledge":
        return {"basis": "general_knowledge", "score": None, "risk": "high", "label": "Not from dataset · unverified",
                "reasons": ["Written by the language model from its general knowledge.",
                            "Nothing in it was computed from, or checked against, the conversations in the dataset."],
                "components": {}}
    if not plan.get("steps"):
        return {"basis": "no_analysis", "score": None, "risk": "low", "label": "No analysis run",
                "reasons": ["Guidance text only: no figures or findings are claimed."], "components": {}}

    text = " ".join([explanation.get("headline", ""), explanation.get("answer", "")] + explanation.get("key_points", []))
    components: dict[str, float] = {}
    reasons: list[str] = []

    figures = [t for t in _NUM.findall(text) if t.lstrip("+-").replace(",", "") not in _TRIVIAL]
    bad = ungrounded_numbers(" ".join(figures), allowed_numbers(facts)) if figures else []
    if figures:
        components["numbers"] = (len(figures) - len(bad)) / len(figures)
        reasons.append(f"{len(figures) - len(bad)}/{len(figures)} figures in the answer trace to computed results")

    quotes = _review_check(evidence_review, "excerpt_fidelity")
    if quotes and (r := _ratio(quotes.get("detail", ""))) and r[1]:
        components["quotes"] = r[0] / r[1]
        reasons.append(f"{r[0]}/{r[1]} quotes match their source messages word for word")

    cov = _review_check(evidence_review, "evidence_coverage")
    if cov and (r := _ratio(cov.get("detail", ""))) and r[1]:
        components["coverage"] = r[0] / r[1]
        reasons.append(f"{r[0]}/{r[1]} top-ranked claims have a supporting conversation")

    total_w = sum(WEIGHTS[k] for k in components)
    value = round(100 * sum(WEIGHTS[k] * v for k, v in components.items()) / total_w) if total_w else 100
    basis = "model_explained" if source == "llm" else "dataset"
    reasons.append("Wording by the language model, then checked against the computed results" if basis == "model_explained"
                   else "Wording generated from the computed results by templates (no model)")

    if bad:
        risk = "high" if components.get("numbers", 1) < 0.8 else "medium"
    elif value >= 95:
        risk = "low"
    elif value >= 75:
        risk = "medium" if basis == "model_explained" or value < 90 else "low"
    else:
        risk = "high"
    return {"basis": basis, "score": value, "risk": risk, "label": f"Grounded {value}%", "reasons": reasons,
            "components": {k: round(v, 3) for k, v in components.items()}}
