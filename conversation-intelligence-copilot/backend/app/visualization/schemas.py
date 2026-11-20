"""Declarative chart / graph contract rendered by the frontend. No executable code."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

ChartType = Literal["bar", "horizontal_bar", "line", "area", "stacked_bar", "donut", "heatmap", "timeline", "priority_matrix",
                    "scatter", "kpi", "table", "error_bar"]


class Series(BaseModel):
    key: str
    label: str
    color: Literal["indigo", "cyan", "violet", "negative", "positive", "neutral", "mixed", "warning", "muted"] = "indigo"


class Drilldown(BaseModel):
    kind: Literal["topic", "product", "conversation", "agent", "month", "message"]
    field: str


class ChartSpec(BaseModel):
    chart_id: str
    chart_type: ChartType
    title: str
    description: str = ""
    x_field: str | None = None
    y_field: str | None = None
    series: list[Series] = []
    data: list[dict[str, Any]] = []
    value_format: Literal["count", "percent", "score", "number"] = "count"
    filters: dict[str, Any] = {}
    dataset_scope: str = "original"
    source_analysis_id: str = ""
    evidence_ids: list[str] = []
    uncertainty_note: str | None = None
    drilldown: Drilldown | None = None
    error_low_field: str | None = None
    error_high_field: str | None = None
    accessibility_summary: str = Field("", description="Plain-text summary for screen readers")

    @model_validator(mode="after")
    def _fields_exist(self):
        if self.chart_type in ("kpi", "table", "heatmap", "timeline", "priority_matrix"):
            return self
        needed = [f for f in [self.x_field, *(s.key for s in self.series)] if f]
        for row in self.data:
            missing = [f for f in needed if f not in row]
            if missing:
                raise ValueError(f"{self.chart_id}: data row missing fields {missing}")
        return self


class GraphNode(BaseModel):
    id: str
    label: str
    kind: Literal["issue", "resolution", "topic", "recommendation", "agent", "product"]
    value: float | None = None


class GraphEdge(BaseModel):
    source: str
    target: str
    weight: float
    label: str = ""
    relation: Literal["observed", "inferred"] = "observed"


class GraphSpec(BaseModel):
    graph_id: str
    title: str
    description: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    source_analysis_id: str = ""
