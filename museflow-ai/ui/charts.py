"""Plotly helpers styled with the validated MuseFlow chart palette.

Single-series bars use slot 1; every bar carries a direct value label (relief for the
pastel slots' sub-3:1 contrast) and every chart has a table view on its page.
"""
from __future__ import annotations

from typing import Sequence

import plotly.graph_objects as go

from ui.session import ctx
from ui.themes import get_theme


def _layout(fig: go.Figure, title: str, height: int) -> go.Figure:
    theme = get_theme(ctx().settings["theme"])
    fig.update_layout(
        title={"text": title, "font": {"size": 15, "color": theme.heading}},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor=theme.chart_surface,
        font={"family": "DM Sans, system-ui, sans-serif", "color": theme.text, "size": 12},
        margin={"l": 10, "r": 30, "t": 46, "b": 10}, height=height, showlegend=False,
        hoverlabel={"bgcolor": theme.surface_solid, "font": {"color": theme.text}}, bargap=0.4,
    )
    fig.update_xaxes(gridcolor=theme.chart_grid, zeroline=False, linecolor=theme.chart_grid)
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)", linecolor=theme.chart_grid, automargin=True)
    return fig


def hbar(labels: Sequence[str], values: Sequence[float], title: str, value_format: str = "{:g}", unit: str = "") -> go.Figure:
    theme = get_theme(ctx().settings["theme"])
    fig = go.Figure(go.Bar(
        x=list(values), y=list(labels), orientation="h", marker={"color": theme.chart_series[0], "cornerradius": 4},
        text=[value_format.format(v) + unit for v in values], textposition="outside", cliponaxis=False,
        textfont={"color": theme.text}, hovertemplate="%{y}: %{x}" + unit + "<extra></extra>",
    ))
    fig.update_yaxes(autorange="reversed")
    return _layout(fig, title, max(150, 44 * len(labels) + 80))


def timeline(rows: list[dict], title: str) -> go.Figure:
    """Per-node execution bars on a shared millisecond axis (rows need node, start_ms, duration_ms, status)."""
    theme = get_theme(ctx().settings["theme"])
    colors = {"completed": theme.chart_series[0], "retrying": theme.chart_series[4], "failed": theme.chart_series[1]}
    fig = go.Figure()
    for status in ("completed", "retrying", "failed"):
        subset = [r for r in rows if r["status"] == status]
        if not subset:
            continue
        fig.add_bar(
            y=[f"{r['seq']}. {r['node']}" for r in subset], x=[max(r["duration_ms"], 0.02) for r in subset],
            base=[r["start_ms"] for r in subset], orientation="h", name=status,
            marker={"color": colors[status], "cornerradius": 4},
            text=[f"{r['duration_ms']:.2f} ms" for r in subset], textposition="outside", cliponaxis=False,
            hovertemplate="%{y}<br>start %{base:.2f} ms · %{x:.2f} ms<extra>" + status + "</extra>",
        )
    fig.update_yaxes(autorange="reversed", categoryorder="array", categoryarray=[f"{r['seq']}. {r['node']}" for r in rows])
    fig.update_xaxes(title_text="ms since run start (measured; gaps include routing and checkpointing)")
    fig = _layout(fig, title, max(220, 34 * len(rows) + 90))
    fig.update_layout(showlegend=len({r["status"] for r in rows}) > 1, legend={"orientation": "h", "y": -0.2})
    return fig
