from app.labeling import rules


def lab(text, role="customer", turn=1):
    return rules.label_message(text, role, turn)


def test_opening_templates_parse_topic_product_language():
    m = lab("App crash ho rahi hai while using Wallet.", turn=0)
    assert (m.topic, m.product, m.language, m.sentiment) == ("app_crash", "Wallet", "hinglish", "negative")
    m = lab("Hi, I need help with my Insurance Claim.", turn=0)
    assert (m.topic, m.product, m.sentiment) == ("general_help", "Insurance Claim", "neutral")
    assert lab("I can’t log in. It says account locked.", turn=0).topic == "account_locked"


def test_followups_and_agent_acts():
    assert lab("Still not fixed. Can you escalate?").act == "escalation_request"
    assert lab("Thanks, that helps.").sentiment == "positive"
    a = lab("I'm sorry about the trouble. Let me check your account.", role="agent")
    assert a.empathy and a.method == "template"
    r = lab("I have issued a refund. You’ll see it in 3-5 business days.", role="agent")
    assert r.resolution == "refund_issued"


def test_template_text_from_wrong_role_is_not_trusted():
    assert lab("Thanks, that helps.", role="agent").method == "lexicon"


def test_lexicon_fallback_is_flagged_low_confidence():
    m = lab("This is terrible, it still doesn't work")
    assert m.method == "lexicon" and m.confidence < 0.5 and m.sentiment == "negative"
    assert lab("Totally new phrasing", turn=0).topic == "other"


def test_conversation_sentiment_thresholds():
    assert rules.conversation_sentiment([-1, -0.6], ["negative", "negative"]) == "negative"
    assert rules.conversation_sentiment([1, 0.8], ["positive", "positive"]) == "positive"
    assert rules.conversation_sentiment([-1, 1, 0], ["negative", "positive", "neutral"]) == "mixed"
    assert rules.conversation_sentiment([0, 0], ["neutral", "neutral"]) == "neutral"
    assert rules.conversation_sentiment([], []) == "uncertain"


def test_aggregate_empathy_response_and_resolution_fit():
    def t(role, text, i):
        return {"speaker_role": role, "turn_index": i, "clean_text": text, **rules.label_message(text, role, i).to_dict()}

    turns = [t("customer", "I was charged twice for my Wallet.", 0),
             t("agent", "I understand this is frustrating. I'm investigating now.", 1),
             t("customer", "Still not fixed. Can you escalate?", 2),
             t("agent", "Please allow me a moment while I run some checks.", 3),
             t("customer", "Thanks, that helps.", 4),
             t("agent", "I have applied the coupon manually and adjusted your invoice.", 5)]
    a = rules.aggregate_conversation(turns)
    assert a["topic"] == "duplicate_charge" and a["domain"] == "Financial services"
    assert a["negative_turns_with_reply"] == 2 and a["empathic_replies"] == 1 and a["empathy_response_rate"] == 0.5
    assert a["final_resolution"] == "coupon_applied" and a["resolution_relevant"] is False
    assert a["escalation_requests"] == 1 and a["ends_negative"] is False


def test_threshold_mean_is_classified_consistently():
    from app.labeling.rules import conversation_sentiment

    # Customer scores of C0014957: the exact mean is -0.25, but naive float summation gives -0.24999999999999997,
    # which used to label it "mixed" while other conversations at -0.25 were "negative".
    scores = [-0.6, 0.8, -0.6, 0.8, -0.6, -0.6, -0.6, -0.6]
    assert sum(scores) / len(scores) > -0.25  # the float artefact this guards against
    assert conversation_sentiment(scores, ["negative", "positive"]) == "negative"
