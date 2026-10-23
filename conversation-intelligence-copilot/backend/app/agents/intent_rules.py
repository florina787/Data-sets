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

# Policy refusals: data the dataset does not contain, or personnel decisions. Always win, whatever else matches.
UNSUPPORTED = re.compile(
    r"revenue|profit|churn|lifetime value|\bltv\b|\bcsat\b|\bnps\b|satisfaction survey|survey (score|result)|handle time|\baht\b|"
    r"salary|salaries|cost per|cost (of|to) (the )?business|cost of .{1,40} to the business|(money|dollars?|\$) (do |did )?we (lose|lost)|lose money|how much money|"
    r"resolution time|time to resolve|how long do (calls|chats|conversations) take|(average|mean) (call|chat) (length|duration)|"
    r"\bgender\b|\bage\b|older (customers|people)|younger (customers|people)|ethnic|\brace\b|religio|nationality|"
    r"weather|stock price|forecast (next|the) (year|quarter)|forecast churn|will (cancel|leave|churn)|"
    r"\bfir(e|ed|ing)\b|terminat|dismiss|disciplin|\bsack(ed)?\b|let (them |him |her )?go\b|punish|demot|"
    r"\blaz(y|iest)\b|\bstupid|worst employee|\bidiot", re.I)
# Requests that are not analysis at all (off-topic, or asking for secrets / to subvert the tools). Refused only
# when no analytical rule matches, so "ignore previous instructions ... show the trend" still answers the trend.
NON_ANALYTICAL = re.compile(r"\bpoem\b|\bjoke\b|\bsong\b|\bstory\b|recipe|api[ _-]?key|system prompt|password|credential|"
                            r"drop table|delete (the )?(table|data)|\bsql\b|reveal your|print your", re.I)


POLICY_REFUSAL = "The question needs data the dataset does not contain or asks for a personnel decision."
NO_MATCH = "The question did not match a supported analysis."


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


# Rule tiers. "strong" rules are specific enough to accept without a second opinion; "weak" rules are broad
# keyword fallbacks whose answer is used only when the semantic router and the model cannot do better.
WEAK_RULES = {"generic_topics_word", "negative_plus_topic_word", "dataset_overview_weak"}

SENTIMENT_WORDS = r"sentiment|mood|feel|felt|happ(y|ier|iness)|unhappy|upset|angr|frustrat|calm|emotion|tone|negative|positive"


def match_rules(question: str, has_previous: bool = False, previous_category: str | None = None,
                previous_top_n: int | None = None) -> tuple[IntentOutput, str]:
    """Deterministic interpretation. Returns (intent, rule_id); rule_id names the rule that fired."""
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
    sentiments = ["negative"] if re.search(r"(only|just|all) negative|negative conversations only|negative ones", ql) else []
    if re.search(r"(only|just) positive|positive ones|the positive (chats|conversations)|list of positive|(only|all) positive", ql):
        sentiments = ["positive"]
    dimension = "product" if re.search(r"\bproducts?\b", ql) else "domain" if re.search(r"\b(domains?|verticals?|industr|business lines?)\b", ql) else "topic"
    rank_by = "rate" if re.search(r"\b(rate|proportion|percentage|share|likelihood)\b", ql) else "count"
    audience = "leadership" if re.search(r"leadership|executive|senior|board|c-suite|vp\b|head of support", ql) else "analyst"
    group_by = None
    m = re.search(r"\b(?:by|per|for each|across|each) (topic|domain|month|language|product)s?\b", ql)
    if m:
        group_by = m.group(1)
    needs_evidence = bool(re.search(r"example|evidence|excerpt|quote|show me (some|the) conversations|support", ql))
    selected = bool(re.search(r"selected conversation|this conversation|the conversation\b|a conversation\b|that conversation", ql))
    sentiment_cue = bool(re.search(SENTIMENT_WORDS, ql))

    def out(category: str, rule: str, **kw) -> tuple[IntentOutput, str]:
        base = dict(category=category, time_window=window, dimension=dimension, rank_by=rank_by, top_n=top_n, topics=topics,
                    products=products, agents=agents, sentiments=sentiments, conversation_ids=conv_ids, group_by=group_by,
                    is_follow_up=is_follow, reference_ranks=refs, audience=audience, needs_evidence=needs_evidence,
                    reasoning="Rule-based interpretation.")
        base.update(kw)
        return IntentOutput(**base), rule

    # 1. policy (always first) -----------------------------------------------------------------
    if UNSUPPORTED.search(q):
        return out("unsupported", "policy_refusal", reasoning=POLICY_REFUSAL)

    # 2. conversation-specific requests (an ID or "the selected conversation") ---------------------------
    if re.search(r"similar|\blike (this|that|these|c\d{7})|(conversations?|chats?|cases?) like\b|more like", ql):
        return out("similar_conversations", "similar_explicit", search_query=q, needs_evidence=True,
                   is_follow_up=is_follow or (has_previous and not (topics or products or conv_ids)))
    if (conv_ids or selected) and re.search(r"x-?ray|what went wrong|went (badly|wrong)|go(es)? (badly|wrong)|diagnos|miss(ed)? (cues|signals)|"
                                            r"communication gaps?|escalation signals?|repeated concerns?|break ?down (this|the|that|the selected)", ql):
        return out("conversation_xray", "xray_explicit")
    if conv_ids and re.search(SENTIMENT_WORDS + r"|trajectory|journey|change|evolve|turn|downhill|end (better|worse)|better or worse|at the end", ql):
        return out("sentiment_trajectory", "trajectory_with_id")
    if selected and re.search(r"sentiment|mood|feel|felt|trajectory|journey|over the course", ql):
        return out("sentiment_trajectory", "trajectory_selected")
    if re.search(r"trajectory|over the course of|sentiment journey|turn[- ]by[- ]turn", ql) and "sentiment" in ql:
        return out("sentiment_trajectory", "trajectory_phrase")
    if conv_ids:
        return out("conversation_detail", "conversation_id_only")

    # 3. session references -------------------------------------------------------------------
    if re.search(r"which findings|uncertain|how (sure|confident)|confidence in|caveat", ql):
        return out("uncertainty_review", "uncertainty_review", is_follow_up=has_previous)
    if re.search(r"why (was|is|did) .*(rank|first|top|priorit)|explain (the|this|that) (ranking|result|answer)|how (was|did you) .*(rank|calculat|scor)", ql):
        return out("explain_previous", "explain_previous", is_follow_up=has_previous)

    # 4. analyses with specific vocabulary ------------------------------------------------------
    if re.search(r"root[- ]?cause|underlying cause|what (causes|is causing|drives|is driving)|what('s| is) behind|drivers? (of|behind)|"
                 r"why (are|is|do|does) .*(negative|unhappy|frustrat|complain|angry|upset|dissatisf)|investigate|"
                 r"explains? .{0,40}(unhappy|negative|frustrat|complain|dissatisf)|factors? .{0,40}(negative|unhappy|dissatisf)", ql):
        return out("root_cause", "root_cause", top_n=None, is_follow_up=is_follow or (has_previous and bool(refs)))
    if re.search(r"summari[sz]e .*(leadership|executive|senior|board)|for (senior )?leadership|executive summary", ql) and has_previous \
            and not re.search(r"concern|priorit|review first", ql):
        return out("leadership_summary", "leadership_summary", is_follow_up=True, audience="leadership")
    if agents and not re.search(r"which agents", ql):
        return out("agent_profile", "agent_id")
    data_cue = re.search(r"\bdataset\b|data set|in the data\b|data cover|date range|what (period|months)|which months|months (are|covered)|"
                         r"how (much|big)|data quality|gaps? (or issues )?in the data|labels? (are|is)? ?(reliab|accura|quality)|reliable are the labels|"
                         r"how many (conversations|agents|products|topics|messages)( and \w+)? (are|is|does|do)", ql)
    per_group = re.search(r"\b(per|by|for each|each|across) (topic|product|domain|issue)", ql)
    if data_cue and not per_group and not re.search(r"negative|positive|sentiment|coach|empath|priorit|trend|compare", ql):
        return out("dataset_overview", "dataset_overview")
    if re.search(r"coach|empath|training|soft[- ]skills|apologi[sz]|acknowledg|communication (skill|quality|issue|training)|"
                 r"agents? (who|that) (need|could|should|may)|team leads? (review|should)", ql) \
            or (re.search(r"which (agents|reps|staff)", ql) and not re.search(r"handled|handle", ql)):
        return out("agent_coaching", "coaching", needs_evidence=True)
    if re.search(r"which agents (handled|handle)|agents (who|that) handled", ql):
        return out("agent_coaching", "coaching_handled", needs_evidence=True,
                   reasoning="Agent listing is served through the coaching review table filtered to the referenced topics.")
    if re.search(r"leadership|review first|prioriti[sz]|priority|recurring (customer )?concern|what should (we|leadership|the head)|biggest (issue|concern|problem|improvement)s?|"
                 r"executive|\bvp\b|head of support|senior attention|fix only|roadmap|invest|pain points|deserve .*attention", ql):
        return out("leadership_priorities", "leadership", audience="leadership" if audience == "leadership" or "leadership" in ql else "analyst")
    if re.search(r"compare|versus|\bvs\.?\b|difference between|stack up|relative to|compared (to|with)", ql) \
            and not re.search(r"(positive|negative|neutral|mixed) (vs\.?|versus|and) (positive|negative|neutral|mixed)", ql):
        return out("compare_topics", "compare")
    if re.search(r"resolution|closing action|resolved|fix rate|right (fix|action|remedy)|correct (fix|remedy|action)|fix appropriate|"
                 r"appropriate (fix|resolution|remedy)|go to the right cases|remed", ql):
        return out("resolution_quality", "resolution")
    if re.search(r"(list|show)( me)?( all| only| the)? (\w+ ){0,3}(conversations|chats)\b|which conversations|list (of|the) (\w+ )?(conversations|chats)|"
                 r"give me the list", ql) and not re.search(r"similar|a few|some|examples?|cases", ql):
        return out("conversation_list", "conversation_list", is_follow_up=has_previous and not (topics or products))
    if re.search(r"example|chats? where|conversations? where|cases\b|find (\w+ ){0,2}(conversations|chats|cases)|search (for|conversations)|look for conversations", ql) \
            and not re.search(r"for example|for instance", ql):
        return out("similar_conversations", "similar_examples", search_query=q, needs_evidence=True,
                   is_follow_up=is_follow or (has_previous and not (topics or products or conv_ids)))
    trend_cue = re.search(r"trend|over time|month[- ]over[- ]month|month (by|to) month|by month|per month|monthly|each month|increas|rising|rise\b|"
                          r"decreas|declin|dropp?(ed)?\b|getting (worse|better)|improv|spike|jump|at its (worst|best)|which month|since (\w+ )?\d{0,4}", ql)
    if trend_cue and (sentiment_cue or re.search(r"angr|negativ|things", ql)):
        return out("sentiment_trend", "trend")
    negative_cue = re.search(r"negative|unhappy|dissatisf|frustrat|angr|upset|complain|worst", ql)
    rank_cue = re.search(r"topic|issue|problem|driver|reason|concern|product|domain|categor|associated|what (makes|made)|where", ql)
    if negative_cue and rank_cue and not re.search(r"what (share|percentage|fraction|proportion) of (conversations|chats)|how many conversations", ql):
        return out("negative_topics", "negative_topics", top_n=top_n or 5)
    if re.search(r"distribution|breakdown|split|mix|how many .*(positive|negative|neutral)|(share|percentage|fraction|proportion) of (conversations|chats)|"
                 r"sentiment (overall|across|by)|overall sentiment|how (do|did|are) customers feel|(customers|people) happy|general mood|overall.{0,20}happy", ql) \
            and sentiment_cue and not re.search(r"topic mix|volume", ql):
        return out("sentiment_distribution", "distribution")
    if re.search(r"most common|frequen|volume|top (topics|issues|products|reasons)|what do customers (contact|call|write|usually)|why do customers|"
                 r"write in about|brings? (people|customers)|contact (us|support)|topic mix|spread across topics|per topic|each topic|"
                 r"distribution of (conversation )?topics|count conversations|most (often|frequently)", ql):
        return out("topic_frequency", "topic_frequency")
    if negative_cue and re.search(r"topic|issue|cause|concern|categor", ql):
        return out("negative_topics", "negative_plus_topic_word", top_n=top_n or 5)
    if data_cue:
        return out("dataset_overview", "dataset_overview_weak")
    if re.search(r"\b(topics|issues|products|domains|categories)\b", ql) and not is_follow:
        return out("topic_frequency", "generic_topics_word")
    if is_follow or (has_previous and (sentiments or topics or products or window.type != "inherit")):
        return out(previous_category or "dataset_overview", "follow_up_inherit", is_follow_up=True,
                   reasoning="Follow-up that changes filters on the previous analysis.")
    if NON_ANALYTICAL.search(q):
        return out("unsupported", "non_analytical", reasoning=POLICY_REFUSAL)
    return out("unsupported", "no_match", reasoning=NO_MATCH)


def parse_intent(question: str, has_previous: bool = False, previous_category: str | None = None, previous_top_n: int | None = None) -> IntentOutput:
    return match_rules(question, has_previous, previous_category, previous_top_n)[0]
