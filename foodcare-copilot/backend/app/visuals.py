"""Visual response contract (schema version 1.0): typed, validated visuals and safe UI actions.

Jerry never returns code to execute. Each answer may carry ``visuals`` (data for a fixed set of
frontend components) and ``ui_actions`` (a fixed set of navigation/download/open actions). Every
item is validated here; anything that fails validation is dropped and reported, never rendered.
All visuals carry ``provenance`` so the UI can label synthetic, modelled and operational data.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

SCHEMA_VERSION = "1.0"
# Only in-app pages (optionally one ?key=value) or this app's export/motion files: no external URLs.
URL_PATTERN = (r"^/[a-z-]*(\?[a-z_]+=[A-Za-z0-9_-]+)?$"
               r"|^/api/(exports|motion)/[a-z_]+\.(pdf|gif)(\?ref=[A-Za-z0-9-]+)?$")
Prov = Literal["verified", "operational_record", "modeled", "synthetic", "mixed"]
Label = Annotated[str, Field(max_length=120)]


class Kpi(BaseModel):
    label: Label
    value: Annotated[str, Field(max_length=60)]
    delta: Annotated[str, Field(max_length=40)] | None = None
    status: Literal["good", "watch", "attention", "unknown"] = "unknown"


class KpiCards(BaseModel):
    kind: Literal["kpis"] = "kpis"
    title: Label
    items: list[Kpi] = Field(max_length=8)
    provenance: Prov


class Point(BaseModel):
    label: Label
    value: float
    note: Annotated[str, Field(max_length=120)] | None = None


class BarChart(BaseModel):
    kind: Literal["bar"] = "bar"
    title: Label
    unit: Annotated[str, Field(max_length=20)]
    items: list[Point] = Field(max_length=30)
    provenance: Prov
    highlight: list[Label] = []


class LineChart(BaseModel):
    kind: Literal["line"] = "line"
    title: Label
    unit: Annotated[str, Field(max_length=20)]
    points: list[Point] = Field(max_length=60)
    provenance: Prov


class Waterfall(BaseModel):
    kind: Literal["waterfall"] = "waterfall"
    title: Label
    unit: Annotated[str, Field(max_length=20)]
    steps: list[Point] = Field(max_length=12)
    provenance: Prov
    missing: list[Label] = []  # components with no data (shown as gaps, never as zero)


class Band(BaseModel):
    label: Label
    p10: float
    p50: float
    p90: float


class ForecastBand(BaseModel):
    kind: Literal["forecast_band"] = "forecast_band"
    title: Label
    unit: Annotated[str, Field(max_length=20)]
    bands: list[Band] = Field(max_length=6)
    provenance: Literal["modeled"] = "modeled"
    method: Annotated[str, Field(max_length=400)]


class TableVisual(BaseModel):
    kind: Literal["table"] = "table"
    title: Label
    columns: list[Label] = Field(max_length=8)
    rows: list[list[str | float | int | None]] = Field(max_length=50)
    provenance: Prov


class Node(BaseModel):
    id: Annotated[str, Field(max_length=60)]
    label: Label
    group: Annotated[str, Field(max_length=30)]
    state: Annotated[str, Field(max_length=40)] | None = None
    detail: Annotated[str, Field(max_length=300)] | None = None


class Edge(BaseModel):
    source: Annotated[str, Field(max_length=60)]
    target: Annotated[str, Field(max_length=60)]
    label: Annotated[str, Field(max_length=60)] | None = None


class StoryStep(BaseModel):
    title: Label
    text: Annotated[str, Field(max_length=400)]
    nodes: list[Annotated[str, Field(max_length=60)]] = []  # nodes highlighted in this step


class FlowGraph(BaseModel):
    kind: Literal["flow"] = "flow"
    title: Label
    nodes: list[Node] = Field(max_length=40)
    edges: list[Edge] = Field(max_length=80)
    provenance: Prov
    caption: Annotated[str, Field(max_length=400)] | None = None


class MotionStory(BaseModel):
    kind: Literal["motion_story"] = "motion_story"
    story: Literal["architecture", "supplier_disruption", "farm_to_market"]
    title: Label
    nodes: list[Node] = Field(max_length=40)
    edges: list[Edge] = Field(max_length=80)
    steps: list[StoryStep] = Field(max_length=12)
    provenance: Prov
    disclaimer: Annotated[str, Field(max_length=300)]


class TimelineEvent(BaseModel):
    date: Annotated[str, Field(max_length=25)]
    label: Label
    provenance: Prov


class Timeline(BaseModel):
    kind: Literal["timeline"] = "timeline"
    title: Label
    events: list[TimelineEvent] = Field(max_length=30)


class PlanStep(BaseModel):
    step: Annotated[str, Field(max_length=300)]
    owner: Annotated[str, Field(max_length=120)]
    approval: Annotated[str, Field(max_length=120)]
    evidence: Annotated[str, Field(max_length=200)]


class ActionPlan(BaseModel):
    kind: Literal["plan"] = "plan"
    title: Label
    steps: list[PlanStep] = Field(max_length=10)
    assumptions: list[Annotated[str, Field(max_length=300)]] = []
    provenance: Prov


class Axis(BaseModel):
    label: Label
    value: Annotated[float, Field(ge=0, le=100)]
    detail: Annotated[str, Field(max_length=160)] | None = None


class Radar(BaseModel):
    kind: Literal["radar"] = "radar"
    title: Label
    axes: list[Axis] = Field(min_length=3, max_length=10)
    provenance: Prov
    caption: Annotated[str, Field(max_length=300)] | None = None


class Heatmap(BaseModel):
    kind: Literal["heatmap"] = "heatmap"
    title: Label
    rows: list[Label] = Field(max_length=20)
    columns: list[Label] = Field(max_length=10)
    values: list[list[Annotated[int, Field(ge=0, le=4)]]]  # 0 none · 1 low · 2 medium · 3 high · 4 critical
    provenance: Prov


class GanttMilestone(BaseModel):
    name: Label
    date: Annotated[str, Field(max_length=10)]
    state: Literal["done", "overdue", "upcoming"]


class GanttRow(BaseModel):
    label: Label
    group: Annotated[str, Field(max_length=40)]
    start: Annotated[str, Field(max_length=10)]
    end: Annotated[str, Field(max_length=10)]
    status: Literal["on_track", "at_risk", "delayed", "blocked", "done"]
    milestones: list[GanttMilestone] = Field(max_length=8)


class Gantt(BaseModel):
    kind: Literal["gantt"] = "gantt"
    title: Label
    today: Annotated[str, Field(max_length=10)]
    rows: list[GanttRow] = Field(max_length=20)
    provenance: Prov


Visual = Annotated[
    KpiCards
    | BarChart
    | LineChart
    | Waterfall
    | ForecastBand
    | TableVisual
    | FlowGraph
    | MotionStory
    | Timeline
    | ActionPlan
    | Radar
    | Heatmap
    | Gantt,
    Field(discriminator="kind"),
]


class UiAction(BaseModel):
    type: Literal["open_globe", "download", "open_xray", "open_page", "open_motion", "open_containment"]
    label: Label
    geo: dict[str, str] | None = None  # {country?, node?, incident?}
    sites: list[Annotated[str, Field(max_length=20)]] = Field(default=[], max_length=40)
    url: Annotated[str, Field(max_length=200, pattern=URL_PATTERN)] | None = None
    agent_run_id: Annotated[str, Field(max_length=40)] | None = None


_VISUALS = TypeAdapter(list[Visual])
_ACTIONS = TypeAdapter(list[UiAction])


def validate(visuals: list[dict], actions: list[dict]) -> tuple[list[dict], list[dict], list[str]]:
    """Validate each item separately; invalid items are dropped and reported (never rendered)."""
    ok_v, ok_a, errors = [], [], []
    for v in visuals:
        try:
            ok_v.append(_VISUALS.validate_python([v])[0].model_dump())
        except ValidationError as exc:
            errors.append(f"visual dropped: {exc.errors()[0]['msg']}")
    for a in actions:
        try:
            ok_a.append(_ACTIONS.validate_python([a])[0].model_dump(exclude_none=True))
        except ValidationError as exc:
            errors.append(f"action dropped: {exc.errors()[0]['msg']}")
    return ok_v, ok_a, errors
