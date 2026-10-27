"""Registry of approved analytical operations.

The planner (rule-based or Gemini) may only choose operations from this registry,
and arguments are validated against each operation's Pydantic model before
anything touches the database. There is no free-form SQL path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from pydantic import BaseModel, Field, ValidationError

from app.analytics import coaching, metrics, prioritization, sentiment, statements, topics, root_cause, trajectories, xray
from app.analytics.db import AnalyticsDB
from app.schemas.analysis import AnalysisResult, Scope


class RankNegativeTopics(BaseModel):
    top_n: int = Field(5, ge=1, le=20)
    dimension: Literal["topic", "product", "domain"] = "topic"
    rank_by: Literal["count", "rate"] = "count"
    min_conversations: int = Field(20, ge=1, le=1000)


class TopicFrequency(BaseModel):
    dimension: Literal["topic", "product", "domain"] = "topic"


class CompareTopics(BaseModel):
    topics: list[str] = Field(min_length=2, max_length=6)


class SentimentDistribution(BaseModel):
    group_by: Literal["topic", "domain", "month", "language", "product"] | None = None


class NoParams(BaseModel):
    pass


class CoachingReview(BaseModel):
    min_conversations: int = Field(3, ge=1, le=100)
    top_n: int = Field(10, ge=1, le=50)


class AgentProfile(BaseModel):
    agent_id: str = Field(min_length=2, max_length=64)


class ConversationRef(BaseModel):
    conversation_id: str | None = Field(None, max_length=64)


class ConversationRequired(BaseModel):
    conversation_id: str = Field(min_length=2, max_length=64)


class ListConversations(BaseModel):
    limit: int = Field(25, ge=1, le=200)
    order: Literal["most_negative", "most_positive", "recent"] = "most_negative"


class LeadershipPriorities(BaseModel):
    top_n: int = Field(5, ge=1, le=10)
    weights: dict[str, float] | None = None


class TopStatements(BaseModel):
    polarity: Literal["positive", "negative"] = "positive"
    top_n: int = Field(5, ge=1, le=20)
    rank_by: Literal["frequency", "strength"] = "frequency"


class RootCause(BaseModel):
    topic: str | None = Field(None, max_length=40, pattern=r"^[a-z_]+$")
    top_n: int = Field(6, ge=1, le=10)


@dataclass(frozen=True)
class Operation:
    name: str
    description: str
    params: type[BaseModel]
    fn: Callable[..., AnalysisResult]


OPERATIONS: dict[str, Operation] = {
    op.name: op
    for op in [
        Operation("rank_negative_topics", "Rank topics/products/domains by negative customer sentiment.", RankNegativeTopics, topics.rank_negative_topics),
        Operation("topic_frequency", "How often each topic/product/domain occurs.", TopicFrequency, topics.topic_frequency),
        Operation("compare_topics", "Compare two or more topics on sentiment, escalation, empathy and resolution.", CompareTopics, topics.compare_topics),
        Operation("sentiment_distribution", "Conversation and message sentiment mix, optionally grouped.", SentimentDistribution, sentiment.sentiment_distribution),
        Operation("sentiment_trend", "Monthly negative-sentiment trend with confidence intervals.", NoParams, sentiment.sentiment_trend),
        Operation("agent_coaching_review", "Empathy/communication review signals by agent and conversation.", CoachingReview, coaching.agent_coaching_review),
        Operation("agent_profile", "Communication signals for one agent.", AgentProfile, coaching.agent_profile),
        Operation("sentiment_trajectory", "Turn-by-turn customer sentiment for one conversation.", ConversationRef, trajectories.sentiment_trajectory),
        Operation("leadership_priorities", "Transparent priority ranking of recurring concerns with recommendations.", LeadershipPriorities, prioritization.leadership_priorities),
        Operation("dataset_overview", "Dataset coverage, date range and labelling status.", NoParams, metrics.dataset_overview),
        Operation("resolution_quality", "Whether agents' closing actions fit the issue raised.", NoParams, metrics.resolution_quality),
        Operation("list_conversations", "List conversations matching filters, most negative first.", ListConversations, metrics.list_conversations),
        Operation("root_cause_investigation", "Candidate drivers of negative sentiment in a topic: tested associations, precedence, alternatives (never causal).",
                  RootCause, root_cause.root_cause_investigation),
        Operation("conversation_xray", "Message-level X-Ray: escalation signals, repeated concerns and communication gaps, each citing message IDs.",
                  ConversationRequired, xray.conversation_xray),
        Operation("conversation_detail", "Full transcript and labels for one conversation.", ConversationRequired, metrics.conversation_detail),
        Operation("top_statements", "Top-N real customer statements of a sentiment polarity, ranked by frequency or strength, with message evidence.",
                  TopStatements, statements.top_statements),
    ]
}


class OperationError(ValueError):
    pass


def run_operation(db: AnalyticsDB, name: str, scope: Scope, params: dict | None = None) -> AnalysisResult:
    op = OPERATIONS.get(name)
    if op is None:
        raise OperationError(f"Unknown operation '{name}'. Allowed: {sorted(OPERATIONS)}")
    try:
        validated = op.params(**(params or {}))
    except ValidationError as e:
        raise OperationError(f"Invalid arguments for {name}: {e.errors(include_url=False)}") from e
    return op.fn(db, scope, **validated.model_dump())


def catalog() -> list[dict]:
    return [{"name": o.name, "description": o.description, "params": o.params.model_json_schema()} for o in OPERATIONS.values()]
