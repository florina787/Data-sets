"""Zero-LLM Intelligence Router.

Decides, before any model call, whether a question needs an LLM at all. Facts always
come from registered DuckDB operations and evidence from FAISS; a model can only add
interpretation (or parse a question the rules cannot). So:

  ANALYTICS ONLY  never call a model; rules intent + deterministic narrative.
  HYBRID AI       use the model for intent (per INTENT_STRATEGY) and explanation.
  AUTO            analytics only when the rules recognise the question and it asks for
                  facts; hybrid when it asks for interpretation or the rules cannot parse it.

The decision and its reason are recorded on every response.
"""

from __future__ import annotations

import re

from app.agents.intent_rules import ALWAYS_REFUSE, NO_MATCH, POLICY_REFUSAL
from app.llm.structured_output import IntentOutput

MODES = ("auto", "analytics_only", "hybrid_ai")
INTERPRETIVE = re.compile(r"\bwhy\b|\bexplain|interpret|recommend|what should|suggest|advice|advise|summari[sz]e|root cause|"
                          r"\bdrivers?\b|what is (causing|driving)|insight|implication|narrative|in plain (english|language)", re.I)
# Categories whose answer *is* an interpretation of other results.
INTERPRETIVE_CATEGORIES = {"explain_previous", "leadership_summary", "root_cause"}


def decide(question: str, requested: str, rules_intent: IntentOutput, llm_available: bool, llm_reason: str | None = None,
           unresolved: bool | None = None) -> dict:
    """`unresolved`: the deterministic stages (rules + semantic) could not route the question with high precision."""
    requested = requested if requested in MODES else "auto"
    if unresolved is None:
        unresolved = rules_intent.reasoning == NO_MATCH
    cue = INTERPRETIVE.search(question)

    def out(route: str, reason: str, llm_steps: list[str]) -> dict:
        return {"requested_mode": requested, "route": route, "reason": reason, "llm_available": llm_available,
                "llm_steps": llm_steps if route == "hybrid_ai" else [], "rules_category": rules_intent.category,
                "interpretive_cue": cue.group(0) if cue else None}

    if requested == "analytics_only":
        return out("analytics_only", "ANALYTICS ONLY selected: answered from registered operations without any model call.", [])
    if not llm_available:
        prefix = "HYBRID AI requested, but no" if requested == "hybrid_ai" else "No"
        return out("analytics_only", f"{prefix} LLM is available ({(llm_reason or 'not configured')[:120]}); deterministic analytics answer the question.", [])
    if requested == "hybrid_ai":
        return out("hybrid_ai", "HYBRID AI selected: the model interprets the question and explains the verified results.", ["intent", "explanation"])
    # AUTO
    if rules_intent.reasoning == POLICY_REFUSAL:
        if ALWAYS_REFUSE.search(question):
            return out("analytics_only", "Policy refusal is deterministic; no model is needed to decline.", [])
        return out("hybrid_ai", "The dataset does not contain what this asks for; the model writes a general-knowledge answer, "
                                "labelled as not from the dataset.", ["explanation"])
    if unresolved:
        return out("hybrid_ai", "Rules and semantic matching could not route the question with high precision, so the model interprets it.",
                   ["intent", "explanation"])
    if rules_intent.category in INTERPRETIVE_CATEGORIES or cue:
        why = f"asks for interpretation ('{cue.group(0)}')" if cue else f"'{rules_intent.category}' is an interpretive analysis"
        return out("hybrid_ai", f"The question {why}; registered operations compute the facts and the model explains them.", ["explanation"])
    return out("analytics_only", f"Rules recognised '{rules_intent.category}' and registered operations compute the full answer; "
                                 "a model would add cost without adding facts.", [])
