"""Typed contracts for deterministic analytical results."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class DateWindow(BaseModel):
    start: str | None = None  # inclusive ISO date
    end: str | None = None  # exclusive ISO date
    label: str = "All dates"
    rule: str = "all"
    explanation: str = ""


class Scope(BaseModel):
    dataset_mode: Literal["original", "synthetic", "combined"] = "original"
    window: DateWindow = Field(default_factory=DateWindow)
    topics: list[str] = []
    products: list[str] = []
    domains: list[str] = []
    agents: list[str] = []
    sentiments: list[str] = []
    conversation_ids: list[str] = []


class Metric(BaseModel):
    id: str
    label: str
    value: float | int | str | None
    unit: str | None = None  # count | percent | score | ratio
    numerator: float | int | None = None
    denominator: float | int | None = None
    description: str = ""


class Table(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]


class AnalysisResult(BaseModel):
    operation: str
    params: dict[str, Any] = {}
    scope: Scope = Field(default_factory=Scope)
    metrics: list[Metric] = []
    table: Table | None = None
    series: dict[str, Table] = {}
    evidence_refs: list[str] = []  # conversation or message ids
    method_notes: list[str] = []
    uncertainty_notes: list[str] = []
    coverage: dict[str, Any] = {}
    status: Literal["ok", "insufficient_data", "unsupported", "error"] = "ok"

    def metric(self, metric_id: str) -> Metric | None:
        return next((m for m in self.metrics if m.id == metric_id), None)
