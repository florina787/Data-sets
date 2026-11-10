"""Dataset-informed taxonomy (version-controlled).

Every definition here was derived by inspecting the supplied Syncora sample
(see docs/dataset/DATA_PROFILE.md): each conversation opens with one of nine
customer issue templates applied to one of 51 product names, followed by turns
drawn from a small pool of customer and agent phrases. The taxonomy maps those
observed patterns to analyst-facing labels. Anything that does not match a known
pattern falls back to a lexicon heuristic and is flagged as lower confidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

TAXONOMY_VERSION = "tax-1.0"


@dataclass(frozen=True)
class Topic:
    id: str
    label: str
    description: str


TOPICS: dict[str, Topic] = {
    t.id: t
    for t in [
        Topic("duplicate_charge", "Duplicate charge", "Customer reports being charged twice."),
        Topic("payment_not_reflected", "Paid but service not delivered", "UPI payment shows successful but the service was not provided."),
        Topic("coupon_not_applied", "Coupon not applying", "A coupon or promo code fails at checkout."),
        Topic("not_received", "Item or service not received", "Something the customer expected has not arrived."),
        Topic("app_crash", "App crash", "The app crashes while the customer uses a feature."),
        Topic("account_locked", "Login / account locked", "Customer cannot log in because the account is locked."),
        Topic("service_malfunction", "Feature not working", "A product or feature is not working as expected."),
        Topic("general_help", "General help request", "Customer asks for help without describing a specific fault."),
        Topic("other", "Other / unclassified", "Opening message did not match a known issue pattern."),
    ]
}

# Opening-message templates -> (topic, language). Group 1 captures the product.
OPENING_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    ("duplicate_charge", "english", re.compile(r"I was charged twice for my (.+)\.")),
    ("service_malfunction", "english", re.compile(r"Hello, my (.+) is not working as expected\.")),
    ("payment_not_reflected", "english", re.compile(r"UPI shows successful but I didn't get the service for (.+)\.")),
    ("coupon_not_applied", "english", re.compile(r"Coupon isn[’']t applying on checkout for the (.+)\.")),
    ("general_help", "english", re.compile(r"Hi, I need help with my (.+)\.")),
    ("app_crash", "hinglish", re.compile(r"App crash ho rahi hai while using (.+)\.")),
    ("account_locked", "english", re.compile(r"I can[’']t log in\. It says account locked\.")),
    ("not_received", "english", re.compile(r"The (.+) hasn[’']t arrived yet\. Can you check\?")),
    ("general_help", "hinglish", re.compile(r"Mujhe (.+) ke baare mein help chahiye\.")),
]

# Product -> business domain. Assumption: inferred from product names only;
# a few names (Billing, Subscription, Membership) are plausible in several domains.
PRODUCT_DOMAINS: dict[str, str] = {
    **{p: "Telecom" for p in ["4G Pack", "5G Upgrade", "Broadband", "eSIM", "International Pack", "Porting", "Roaming"]},
    **{p: "E-commerce" for p in ["Order", "Return", "Exchange", "Refund", "Prime Delivery", "Priority Delivery", "Coupon", "Gift Card", "Voucher", "Promo", "Partner Offer", "Membership", "Subscription"]},
    **{p: "Financial services" for p in ["UPI", "Wallet", "Credit Card", "Loan", "Savings", "Mutual Fund", "Insurance", "Insurance Claim", "FASTag", "Billing"]},
    **{p: "Travel" for p in ["Bus", "Cab", "Flight", "Hotel"]},
    **{p: "Healthcare" for p in ["Appointment", "Lab Test", "Prescription", "Teleconsult", "Report"]},
    **{p: "Education" for p in ["Assignment", "Career Track", "Certificate", "Course", "Exam", "Mock Test"]},
    **{p: "SaaS / developer" for p in ["API", "Analytics", "Audit Logs", "SSO", "Webhooks", "Workspace"]},
}


@dataclass(frozen=True)
class Act:
    """A communication act: what a known message template does in the conversation."""

    id: str
    role: str
    sentiment: str  # positive | neutral | negative
    score: float  # -1 .. 1
    language: str = "english"
    empathy: bool = False  # acknowledges feelings or apologises
    courtesy: bool = False
    resolution: str | None = None  # action the agent says it took


FOLLOWUP_ACTS: dict[str, Act] = {
    # customer
    "Still not fixed. Can you escalate?": Act("escalation_request", "customer", "negative", -1.0),
    "It’s urgent. Please expedite.": Act("urgency", "customer", "negative", -0.6),
    "Thoda jaldi please, flight in 2 hours.": Act("urgency", "customer", "negative", -0.6, language="hinglish"),
    "Okay, waiting for an update.": Act("waiting", "customer", "neutral", 0.0),
    "Got it. I’ve retried, and it works now.": Act("confirms_fixed", "customer", "positive", 1.0),
    "Thanks, that helps.": Act("gratitude", "customer", "positive", 0.8),
    # agent: engagement
    "I understand this is frustrating. I'm investigating now.": Act("empathy_acknowledgement", "agent", "neutral", 0.0, empathy=True),
    "I'm sorry about the trouble. Let me check your account.": Act("apology", "agent", "neutral", 0.0, empathy=True),
    "Thanks for reaching out! I’m pulling up the details.": Act("courtesy_greeting", "agent", "neutral", 0.0, courtesy=True),
    "I can help with that. May I have the registered email or phone?": Act("verification_request", "agent", "neutral", 0.0),
    "Please allow me a moment while I run some checks.": Act("hold_notice", "agent", "neutral", 0.0),
    "Main abhi verify kar rahi/raha hoon, kindly wait.": Act("hold_notice", "agent", "neutral", 0.0, language="hinglish"),
    # agent: resolution statements
    "Service activated. Please restart the app and confirm.": Act("resolution", "agent", "neutral", 0.0, resolution="service_activated"),
    "We escalated the case to our specialist team. You'll get an update soon.": Act("resolution", "agent", "neutral", 0.0, resolution="escalated"),
    "The order is out for delivery. Expected by tomorrow evening.": Act("resolution", "agent", "neutral", 0.0, resolution="out_for_delivery"),
    "I have issued a refund. You’ll see it in 3-5 business days.": Act("resolution", "agent", "neutral", 0.0, resolution="refund_issued"),
    "I have applied the coupon manually and adjusted your invoice.": Act("resolution", "agent", "neutral", 0.0, resolution="coupon_applied"),
    "I’ve reset your account. Please try logging in again.": Act("resolution", "agent", "neutral", 0.0, resolution="account_reset"),
}

# Opening complaint sentiment: a fault report is negative; a plain help request is neutral.
OPENING_SENTIMENT: dict[str, tuple[str, float]] = {
    "general_help": ("neutral", 0.0),
    "other": ("neutral", 0.0),
}
DEFAULT_OPENING_SENTIMENT = ("negative", -0.6)

# Which agent resolution statements plausibly address which issue (assumption, documented
# in ASSUMPTIONS.md). Escalation is always acceptable. general_help is not assessable.
RELEVANT_RESOLUTIONS: dict[str, set[str]] = {
    "duplicate_charge": {"refund_issued", "escalated"},
    "payment_not_reflected": {"service_activated", "refund_issued", "escalated"},
    "coupon_not_applied": {"coupon_applied", "escalated"},
    "not_received": {"out_for_delivery", "refund_issued", "escalated"},
    "app_crash": {"service_activated", "account_reset", "escalated"},
    "account_locked": {"account_reset", "escalated"},
    "service_malfunction": {"service_activated", "account_reset", "escalated"},
}

HINGLISH_MARKERS = re.compile(r"\b(mujhe|baare|mein|chahiye|ho rahi|thoda|jaldi|kar rahi|raha hoon|hai)\b", re.I)

# Lexicon fallback for text outside the known templates (e.g. appended data).
NEGATIVE_WORDS = re.compile(r"\b(not|never|can[’']?t|cannot|still|urgent|escalate|crash\w*|fail\w*|charged twice|angry|worst|terrible|locked|broken|refund)\b", re.I)
POSITIVE_WORDS = re.compile(r"\b(thanks?|thank you|works|working now|great|resolved|perfect|appreciate|helps?)\b", re.I)
EMPATHY_WORDS = re.compile(r"\b(sorry|understand|apolog\w+|frustrat\w+|appreciate your patience)\b", re.I)

SENTIMENTS = ["positive", "neutral", "negative", "mixed", "uncertain"]
