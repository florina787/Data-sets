"""Deterministic intent parser.

Used when Gemini is unavailable, and as a validator/fallback when it is. It
produces the same typed `IntentOutput` as the model so the rest of the graph is
identical in both modes.
"""

from __future__ import annotations

import re

from app.labeling.taxonomy import PRODUCT_DOMAINS
from app.llm.structured_output import IntentOutput, TimeWindowSpec

CONV_ID = re.compile(r"\bC\d{7}\b", re.I)
AGENT_ID = re.compile(r"\bAgent[A-Za-z]{4}\b")
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september",
                                      "october", "november", "december"], start=1)}
# "may" is only a month when followed by a year or preceded by "in" (otherwise it is the verb).
MONTH_RE = re.compile(r"\b(" + "|".join([m for m in MONTHS if m != "may"] + [m[:3] for m in MONTHS if m != "may"] + ["sept"]) + r")\b\.?\s*(\d{4})?"
                      r"|\b(may)\s+(\d{4})\b|\bin (may)\b()", re.I)
NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "top one": 1, "#1": 1, "#2": 2, "#3": 3}

TOPIC_SYNONYMS: list[tuple[str, re.Pattern[str]]] = [
    ("duplicate_charge", re.compile(r"duplicate charge|charged twice|double[- ]charg|billed twice", re.I)),
    ("payment_not_reflected", re.compile(r"\bupi\b|paid but|payment (succeeded|successful|went through)|service not delivered|not reflected", re.I)),
    ("coupon_not_applied", re.compile(r"coupon|promo code|discount code", re.I)),
    ("not_received", re.compile(r"not received|hasn.?t arrived|not arrived|didn.?t arrive|delivery|not delivered(?! service)", re.I)),
    ("app_crash", re.compile(r"crash", re.I)),
    ("account_locked", re.compile(r"log ?in|locked|account lock|sign ?in", re.I)),
    ("service_malfunction", re.compile(r"not working|malfunction|broken|feature (issue|problem)", re.I)),
    ("general_help", re.compile(r"general help|help request", re.I)),
]
PRODUCT_RE = re.compile(r"\b(" + "|".join(re.escape(p) for p in sorted(PRODUCT_DOMAINS, key=len, reverse=True)) + r")\b")

UNSUPPORTED = re.compile(
    r"revenue|profit|churn|lifetime value|\bltv\b|\bcsat\b|\bnps\b|survey score|handle time|\baht\b|salary|salaries|cost per|"
    r"\bgender\b|\bage\b|ethnic|\brace\b|religio|nationality|weather|stock price|forecast (next|the) (year|quarter)|"
    r"\bfire\b|terminate|dismiss|disciplin", re.I)


def _top_n(q: str) -> int | None:
    m = re.search(r"\btop\s+(\d+|" + "|".join(NUM_WORDS) + r")\b", q, re.I)
    if not m:
        return None
    v = m.group(1).lower()
    return int(v) if v.isdigit() else NUM_WORDS[v]


def _window(q: str) -> TimeWindowSpec:
    ql = q.lower()
    if re.search(r"previous month|month before|prior month|preceding month", ql):
        return TimeWindowSpec(type="previous_month")
    if re.search(r"next month|following month|month after", ql):
        return TimeWindowSpec(type="next_month")
    m = re.search(r"last\s+(\d+|" + "|".join(NUM_WORDS) + r")\s+months", ql)
    if m:
        v = m.group(1)
        return TimeWindowSpec(type="last_n_months", n=int(v) if v.isdigit() else NUM_WORDS[v])
    if re.search(r"last month|latest month|most recent month|this month|past month|recent month", ql):
        return TimeWindowSpec(type="last_month")
    m = MONTH_RE.search(q)
    if m:
        groups = [g for g in m.groups()]
        name = next(g for g in (groups[0], groups[2], groups[4]) if g).lower().rstrip(".")
        month = next(i for k, i in MONTHS.items() if k.startswith(name))
        year = groups[1] or groups[3] or "2025"
        return TimeWindowSpec(type="month", month=f"{year}-{month:02d}")
    if re.search(r"all time|overall|entire dataset|whole dataset|all months|all conversations|across the dataset", ql):
        return TimeWindowSpec(type="all")
    return TimeWindowSpec(type="inherit")


def _reference_ranks(q: str, n_hint: int | None) -> list[int]:
    ql = q.lower()
    m = re.search(r"\btop (two|three|2|3|four|4|five|5)\b", ql)
    if m and re.search(r"compare|those|these|the top (two|three|2|3)\b", ql):
        n = NUM_WORDS.get(m.group(1), None) or int(m.group(1))
        return list(range(1, n + 1))
    ranks = sorted({v for k, v in ORDINALS.items() if re.search(r"(?<!\w)" + re.escape(k) + r"(?!\w)", ql)})
    if ranks and re.search(r"\b(one|topic|concern|issue|item|ranked|result)\b|#\d", ql):
        return ranks
    if re.search(r"\b(those|these|them)\b", ql) and n_hint:
        return list(range(1, n_hint + 1))
    return []


def parse_intent(question: str, has_previous: bool = False, previous_category: str | None = None, previous_top_n: int | None = None) -> IntentOutput:
    q = question.strip()
    ql = q.lower()
    conv_ids = [c.upper() for c in CONV_ID.findall(q)]
    agents = AGENT_ID.findall(q)
    topics = [t for t, p in TOPIC_SYNONYMS if p.search(q)]
    products = [p for p in PRODUCT_RE.findall(q)]
    window = _window(q)
    top_n = _top_n(q)
    refs = _reference_ranks(q, previous_top_n) if has_previous else []
    follow_cue = bool(re.search(r"^(and|now|what about|how about|same|also|then|only|show only|just)\b|\b(those|these|them|that one|the first one|this conversation|previous answer|that analysis|above)\b", ql))
    is_follow = has_previous and (bool(refs) or follow_cue or window.type in ("previous_month", "next_month"))
    sentiments = ["negative"] if re.search(r"(only|just) negative|negative conversations only|negative ones", ql) else []
    if re.search(r"(only|just) positive|positive ones", ql):
        sentiments = ["positive"]
    dimension = "product" if re.search(r"\bproducts?\b", ql) else "domain" if re.search(r"\b(domains?|verticals?|industr|business lines?)\b", ql) else "topic"
    rank_by = "rate" if re.search(r"\b(rate|proportion|percentage|share|likelihood)\b", ql) else "count"
    audience = "leadership" if re.search(r"leadership|executive|senior|board|c-suite|vp\b", ql) else "analyst"
    group_by = None
    m = re.search(r"\bby (topic|domain|month|language|product)\b", ql)
    if m:
        group_by = m.group(1)
    needs_evidence = bool(re.search(r"example|evidence|excerpt|quote|show me (some|the) conversations|support", ql))

    def out(category: str, **kw) -> IntentOutput:
        base = dict(category=category, time_window=window, dimension=dimension, rank_by=rank_by, top_n=top_n, topics=topics,
                    products=products, agents=agents, sentiments=sentiments, conversation_ids=conv_ids, group_by=group_by,
                    is_follow_up=is_follow, reference_ranks=refs, audience=audience, needs_evidence=needs_evidence,
                    reasoning="Rule-based interpretation.")
        base.update(kw)
        return IntentOutput(**base)

    if UNSUPPORTED.search(q):
        return out("unsupported", reasoning="The question needs data the dataset does not contain or asks for a personnel decision.")
    if re.search(r"similar|like (this|that|these)|find (conversations|cases|examples)|search (for|conversations)|look for conversations|(show|give|find).*\bexamples?\b|supporting examples|more examples", ql):
        return out("similar_conversations", search_query=q, needs_evidence=True,
                   is_follow_up=is_follow or (has_previous and not (topics or products or conv_ids)))
    if conv_ids and re.search(r"sentiment|trajectory|journey|change|evolve|turn", ql):
        return out("sentiment_trajectory")
    if re.search(r"trajectory|over the course of|sentiment journey|turn[- ]by[- ]turn|selected conversation|a conversation", ql) and "sentiment" in ql:
        return out("sentiment_trajectory")
    if conv_ids:
        return out("conversation_detail")
    if re.search(r"(show|list|give)( me)?( only| just| all| the)? ?(negative|positive|mixed|neutral)? conversations\b|which conversations|list (of )?conversations", ql) \
            and not re.search(r"similar", ql):
        return out("conversation_list", is_follow_up=has_previous and not (topics or products))
    if re.search(r"which findings|uncertain|how (sure|confident)|reliab|confidence in|caveat", ql):
        return out("uncertainty_review", is_follow_up=has_previous)
    if re.search(r"why (was|is|did) .*(rank|first|top|priorit)|explain (the|this|that) (ranking|result|answer)|how (was|did you) .*(rank|calculat|scor)", ql):
        return out("explain_previous", is_follow_up=has_previous)
    if re.search(r"summari[sz]e .*(leadership|executive|senior|board)|for (senior )?leadership|executive summary", ql) and has_previous \
            and not re.search(r"concern|priorit|review first", ql):
        return out("leadership_summary", is_follow_up=True, audience="leadership")
    if agents and not re.search(r"which agents", ql):
        return out("agent_profile")
    if re.search(r"coach|empathy|empathetic|communication (skill|quality|issue)|training need|agents? (who|that) (need|could|should|may)", ql) \
            or (re.search(r"which agents", ql) and not re.search(r"handled|handle", ql)):
        return out("agent_coaching", needs_evidence=True)
    if re.search(r"which agents (handled|handle)|agents (who|that) handled", ql):
        return out("agent_coaching", needs_evidence=True, reasoning="Agent listing is served through the coaching review table filtered to the referenced topics.")
    if re.search(r"leadership|review first|prioriti[sz]|priority|recurring (customer )?concern|what should (we|leadership) (look|review|focus)|biggest (issue|concern|problem)s?", ql):
        return out("leadership_priorities", audience="leadership" if "leadership" in ql or audience == "leadership" else "analyst")
    if re.search(r"compare|versus|\bvs\.?\b|difference between", ql):
        return out("compare_topics")
    if re.search(r"trend|over time|month[- ]over[- ]month|month by month|increas|rising|decreas|declin|getting worse|getting better", ql):
        return out("sentiment_trend")
    if re.search(r"resolution|closing action|resolved|fix rate|right (fix|action)", ql):
        return out("resolution_quality")
    if re.search(r"negative", ql) and re.search(r"topic|issue|driver|reason|cause|concern|product|domain|categor|associated|what (makes|made)", ql):
        return out("negative_topics", top_n=top_n or 5)
    if re.search(r"distribution|breakdown|split|mix|how many .*(positive|negative|neutral)|sentiment (overall|across)|overall sentiment|how (do|did|are) customers feel", ql):
        return out("sentiment_distribution")
    if re.search(r"most common|frequen|volume|top (topics|issues|products|reasons)|what do customers (contact|call|write)|why do customers", ql):
        return out("topic_frequency")
    if re.search(r"dataset|data set|coverage|how many conversations|date range|data quality|how much data|what data", ql):
        return out("dataset_overview")
    if re.search(r"\b(topics|issues|products|domains|categories)\b", ql) and not is_follow:
        return out("topic_frequency")
    if is_follow or (has_previous and (sentiments or topics or products or window.type != "inherit")):
        return out(previous_category or "dataset_overview", is_follow_up=True, reasoning="Follow-up that changes filters on the previous analysis.")
    return out("unsupported", reasoning="The question did not match a supported analysis.")
