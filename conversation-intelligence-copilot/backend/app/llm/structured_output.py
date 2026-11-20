"""Pydantic schemas for every structured model output, with controlled enums."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

IntentCategory = Literal[
    "negative_topics", "agent_coaching", "sentiment_trajectory", "leadership_priorities", "sentiment_distribution",
    "sentiment_trend", "topic_frequency", "compare_topics", "agent_profile", "conversation_detail", "similar_conversations",
    "dataset_overview", "resolution_quality", "conversation_list", "explain_previous", "uncertainty_review", "leadership_summary",
    "conversation_xray", "root_cause", "top_statements", "unsupported",
]
TopicId = Literal["duplicate_charge", "payment_not_reflected", "coupon_not_applied", "not_received", "app_crash",
                  "account_locked", "service_malfunction", "general_help", "other"]
WindowType = Literal["all", "last_month", "month", "previous_month", "next_month", "last_n_months", "inherit"]
SentimentLabel = Literal["positive", "neutral", "negative", "mixed", "uncertain"]


ClassifiableIntent = Literal[
    "negative_topics", "topic_frequency", "sentiment_distribution", "sentiment_trend", "compare_topics", "root_cause",
    "leadership_priorities", "agent_coaching", "agent_profile", "resolution_quality", "sentiment_trajectory", "conversation_xray",
    "conversation_detail", "similar_conversations", "conversation_list", "dataset_overview", "unsupported", "clarify",
]


class IntentClassification(BaseModel):
    """Category-only output for the small local model; entities come from deterministic extractors."""

    category: ClassifiableIntent


class TimeWindowSpec(BaseModel):
    type: WindowType = "inherit"
    month: str | None = Field(None, description="YYYY-MM when type is 'month'")
    n: int | None = Field(None, description="Number of months when type is 'last_n_months'")


class IntentOutput(BaseModel):
    category: IntentCategory
    time_window: TimeWindowSpec = Field(default_factory=TimeWindowSpec)
    dimension: Literal["topic", "product", "domain"] = "topic"
    rank_by: Literal["count", "rate"] = "count"
    top_n: int | None = None
    topics: list[TopicId] = []
    products: list[str] = []
    agents: list[str] = []
    sentiments: list[SentimentLabel] = []
    conversation_ids: list[str] = []
    search_query: str | None = None
    group_by: Literal["topic", "domain", "month", "language", "product"] | None = None
    is_follow_up: bool = False
    reference_ranks: list[int] = Field(default_factory=list, description="1-based ranks from the previous ranking the user refers to")
    audience: Literal["analyst", "leadership"] = "analyst"
    needs_evidence: bool = False
    polarity: Literal["positive", "negative"] | None = None  # top_statements: which statements
    statement_rank: Literal["frequency", "strength"] = "frequency"  # top_statements: most common, or strongest sentiment
    reasoning: str = Field("", description="One short sentence explaining the interpretation")


class MessageClassification(BaseModel):
    index: int
    act: Literal["issue_report", "escalation_request", "urgency", "waiting", "confirms_fixed", "gratitude", "empathy_acknowledgement",
                 "apology", "courtesy_greeting", "verification_request", "hold_notice", "resolution", "unknown"]
    sentiment: Literal["positive", "neutral", "negative", "mixed"]
    sentiment_score: float = Field(ge=-1, le=1)
    empathy: bool
    courtesy: bool
    resolution: Literal["service_activated", "escalated", "out_for_delivery", "refund_issued", "coupon_applied", "account_reset", "none"]
    language: Literal["english", "hinglish", "other"]
    topic: TopicId | None = None
    product: str | None = None
    confidence: Literal["high", "medium", "low"]


class ClassificationBatch(BaseModel):
    items: list[MessageClassification]


class ExplanationOutput(BaseModel):
    headline: str = Field(description="One-sentence direct answer")
    answer: str = Field(description="2-5 sentences, using only numbers from VERIFIED_FACTS")
    key_points: list[str] = Field(default_factory=list, max_length=5)
    follow_up_questions: list[str] = Field(default_factory=list, max_length=4)
