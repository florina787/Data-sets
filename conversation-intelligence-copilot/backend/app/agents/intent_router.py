"""Confidence-aware intent routing.

Order of precedence (each stage records its method and reason for AI Decision Replay):

  1. policy      authorisation and policy refusals (missing data, personnel decisions, non-analytical requests)
  2. rules       high-precision deterministic matches (any rule outside WEAK_RULES)
  3. semantic    nearest labelled examples (MiniLM); accepted only above validation-calibrated
                 similarity and margin thresholds; similarities are not probabilities
  4. vague guard a question with almost no content words and no entity is clarified without guessing
  5. llm         the configured model picks a category from a closed set (constrained JSON);
                 the result is validated against the extracted entities
  6. rules_weak  a broad keyword rule, used only when nothing above produced an answer
  7. clarify     otherwise ask the user to rephrase, naming the closest analyses

Entities (conversation and agent IDs, topics, products, time windows, follow-up references)
always come from the deterministic extractors, whichever stage chose the category. No stage
produces a numeric confidence; uncalibrated models are not given one.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from app.agents.intent_rules import TOPIC_SYNONYMS, WEAK_RULES, match_rules
from app.agents.semantic_intent import semantic_match
from app.llm.structured_output import IntentOutput

ACTIVE_PROMPT = ("intent_classification", "2.1")
CLARIFY_PREFIX = "Clarification needed:"
POLICY_RULES = {"policy_refusal", "non_analytical"}
# Words that carry no analytical content; a question with fewer than MIN_CONTENT_WORDS other words and no
# entity ("And?", "What about it?") is too vague for any stage, including the model, to route.
FILLER = set("a an the and or but so what about it this that these those me my we our us you your tell show give more please "
             "is are was were be do does did can could would should anything something some any else now then ok okay also how".split())
MIN_CONTENT_WORDS = 2

# Relevance gate: a question no rule recognises is treated as off-topic, without asking any model, when it is far from
# every labelled example, or moderately far and mentions nothing the dataset contains. Calibrated on the benchmark's
# validation/test questions and tests/evaluation/datasets/off_domain_questions.jsonl (no in-domain question is gated).
OFF_TOPIC_MAX_SIM = 0.30
OFF_TOPIC_MAX_SIM_NO_TERMS = 0.50
DATASET_TERMS = re.compile(
    r"sentiment|negativ|positiv|complain|angr|unhappy|upset|frustrat|happ(y|ier|iest)|mood|topic|issue|problem|concern|"
    r"conversation|chat|transcript|message|escalat|empath|coach|apolog|agent|refund|charg|coupon|voucher|deliver|payment|"
    r"log ?in|crash|account|product|domain|month|week|trend|over time|january|february|march|april|june|july|august|"
    r"september|october|november|december|dataset|\bdata\b|\bC\d{7}\b|resolution|closing|priorit|leadership|example|"
    r"similar|compare|worst|best|hinglish|language", re.I)
FOLLOW_UP_CUES = re.compile(r"\b(it|that|this|those|these|them|more|previous|same|again|why|first|second|top)\b", re.I)
OFF_TOPIC_TEXT = ("This question isn't about the customer-support conversations in this dataset, so no analysis here can answer it.")


def is_off_topic(question: str, similarity: float) -> bool:
    return similarity < OFF_TOPIC_MAX_SIM or (similarity < OFF_TOPIC_MAX_SIM_NO_TERMS and not DATASET_TERMS.search(question))
LABELS = {
    "negative_topics": "the most negative topics", "topic_frequency": "topic volumes", "sentiment_distribution": "the sentiment mix",
    "sentiment_trend": "the sentiment trend", "compare_topics": "a topic comparison", "root_cause": "a root-cause investigation",
    "leadership_priorities": "leadership priorities", "agent_coaching": "agent coaching signals", "agent_profile": "one agent's profile",
    "resolution_quality": "resolution fit", "sentiment_trajectory": "a conversation's sentiment journey",
    "conversation_xray": "a conversation X-Ray", "conversation_detail": "a transcript", "similar_conversations": "similar conversations",
    "conversation_list": "a list of conversations", "dataset_overview": "the dataset overview",
}


@dataclass
class RouteDecision:
    label: str  # an IntentCategory, or "clarify"
    intent: IntentOutput
    method: str  # policy | rules | semantic | llm | rules_weak | clarify
    reason: str
    rule_id: str
    llm_calls: int = 0
    semantic: dict | None = None
    llm: dict | None = None
    latency_ms: float = 0.0
    stages: list[str] = field(default_factory=list)

    def meta(self) -> dict:
        return {"method": self.method, "reason": self.reason, "rule": self.rule_id, "label": self.label, "llm_calls": self.llm_calls,
                "semantic": self.semantic, "llm": self.llm, "stages": self.stages, "latency_ms": self.latency_ms}


def _entities_ok(category: str, intent: IntentOutput, selected_conversation_id: str | None) -> bool:
    if category == "agent_profile":
        return bool(intent.agents)
    if category == "conversation_detail":
        return bool(intent.conversation_ids or selected_conversation_id)
    return True


def _clarify_text(candidates: list[str]) -> str:
    near = [LABELS[c] for c in candidates if c in LABELS][:2]
    hint = f" It could be about {' or '.join(near)}." if near else ""
    return (f"{CLARIFY_PREFIX} I couldn't tell which analysis you want.{hint} Try naming it, e.g. 'top negative topics last month', "
            "'which agents need empathy coaching', or 'how did sentiment change in C0000479'.")


def route_intent(question: str, previous: dict | None = None, allow_llm: bool = True, request_id: str = "",
                 selected_conversation_id: str | None = None) -> RouteDecision:
    t0 = time.perf_counter()
    prev_cat = previous.get("intent", {}).get("category") if previous else None
    prev_n = len(previous.get("refs", {}).get("ranking", [])[:10]) if previous else None
    rules_intent, rule = match_rules(question, has_previous=previous is not None, previous_category=prev_cat, previous_top_n=prev_n)
    stages = ["policy", "rules"]

    def done(label: str, intent: IntentOutput, method: str, reason: str, **kw) -> RouteDecision:
        return RouteDecision(label, intent, method, reason, rule, stages=stages, latency_ms=round((time.perf_counter() - t0) * 1000, 1), **kw)

    def as_category(cat: str, reason: str) -> IntentOutput:
        return rules_intent.model_copy(update={"category": cat, "reasoning": reason})

    if rule in POLICY_RULES:
        return done("unsupported", rules_intent, "policy", f"Policy rule '{rule}': {rules_intent.reasoning}")
    if rule != "no_match" and rule not in WEAK_RULES:
        return done(rules_intent.category, rules_intent, "rules", f"High-precision rule '{rule}'.")

    stages.append("semantic")
    sem = semantic_match(question)
    sem_meta = {"available": sem.available, "candidates": sem.candidates, "margin": sem.margin, "accepted": sem.accepted,
                "thresholds": sem.thresholds, "nearest_example": sem.nearest_example} if sem.available else {"available": False, "note": sem.note}
    if sem.accepted and sem.top and _entities_ok(sem.top, rules_intent, selected_conversation_id):
        why = (f"Semantic match '{sem.top}' (similarity {sem.similarity:.2f}, margin {sem.margin:.2f} ≥ calibrated "
               f"{sem.thresholds['min_similarity']:.2f}/{sem.thresholds['min_margin']:.2f}).")
        return done(sem.top, as_category(sem.top, why), "semantic", why, semantic=sem_meta)

    # A bare topic name ("app crashes", "coupons?") names *what* but not *which analysis*, so topic words are not counted.
    stripped = question
    for _, pat in TOPIC_SYNONYMS:  # remove whole words touched by a topic phrase ("crashes", not just "crash")
        stripped = re.sub(rf"\w*(?:{pat.pattern})\w*", " ", stripped, flags=re.I)
    stripped = re.sub(r"\b(app|account|order|payment)s?\b", " ", stripped, flags=re.I)  # topic heads left behind
    content = [w for w in re.findall(r"[a-z0-9]+", stripped.lower()) if w not in FILLER]
    if len(content) < MIN_CONTENT_WORDS and not (rules_intent.conversation_ids or rules_intent.agents or previous):
        return done("clarify", as_category("unsupported", _clarify_text([c for c, _ in sem.candidates])), "clarify",
                    f"Too vague to route ({len(content)} content word(s)); asking instead of guessing.", semantic=sem_meta)

    referential = previous is not None and FOLLOW_UP_CUES.search(question)
    if sem.available and rule not in WEAK_RULES and not referential and is_off_topic(question, sem.similarity):
        return done("clarify", as_category("unsupported", OFF_TOPIC_TEXT), "off_topic",
                    f"Not about the conversation data (nearest example similarity {sem.similarity:.2f}); no model was asked to classify it.",
                    semantic=sem_meta)

    llm_meta = None
    calls = 0
    if allow_llm:
        from app.llm.gemini_client import LLMUnavailable, get_llm
        from app.llm.structured_output import IntentClassification
        from app.prompts.registry import get_prompt

        llm = get_llm()
        if llm.available():
            stages.append("llm")
            prompt = get_prompt(*ACTIVE_PROMPT)
            calls = 1
            try:
                res = llm.generate_json(prompt, prompt.render(question=question), IntentClassification, request_id=request_id, purpose="intent")
                cat = res.parsed.category  # type: ignore[union-attr]
                llm_meta = {"category": cat, "prompt": f"{prompt.id}@{prompt.version}", "model": res.model, "cache_hit": res.cache_hit,
                            "tokens": res.usage.total_tokens if res.usage.reported else None}
                if cat == "clarify":
                    return done("clarify", as_category("unsupported", _clarify_text([c for c, _ in sem.candidates])), "clarify",
                                "The model judged the question too vague to route.", llm_calls=calls, semantic=sem_meta, llm=llm_meta)
                if cat == "unsupported":
                    return done("unsupported", as_category("unsupported", "The model judged the request out of scope for this dataset."), "llm",
                                "The model classified the request as unsupported.", llm_calls=calls, semantic=sem_meta, llm=llm_meta)
                if _entities_ok(cat, rules_intent, selected_conversation_id):
                    why = f"Model ({prompt.id}@{prompt.version}) chose '{cat}'; entities validated by the deterministic extractors."
                    return done(cat, as_category(cat, why), "llm", why, llm_calls=calls, semantic=sem_meta, llm=llm_meta)
                llm_meta["rejected"] = f"'{cat}' needs an entity the question does not contain"
            except LLMUnavailable as e:
                llm_meta = {"error": str(e)[:200]}

    if rule in WEAK_RULES:
        why = f"Broad keyword rule '{rule}' (used only because no higher-precision stage answered)."
        return done(rules_intent.category, rules_intent.model_copy(update={"reasoning": why}), "rules_weak", why,
                    llm_calls=calls, semantic=sem_meta, llm=llm_meta)
    return done("clarify", as_category("unsupported", _clarify_text([c for c, _ in sem.candidates])), "clarify",
                "No stage could route the question with enough precision.", llm_calls=calls, semantic=sem_meta, llm=llm_meta)
