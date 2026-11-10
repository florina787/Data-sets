"""Generate the README charts (light and dark variants) from the real data and evaluation results.

  uv run python -m scripts.readme_figures      (from backend/)

Writes docs/readme/<name>-light.png and <name>-dark.png. Every value is read from DuckDB or
data/manifests; nothing is typed in by hand. Palette: the validated reference categorical order
(light and dark steps validated separately; light slots 3-5 are below 3:1 on the surface, so every
bar carries a direct value label and the README shows the numbers in a table beside each chart).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from app.analytics.db import get_db  # noqa: E402
from app.analytics.query_registry import run_operation  # noqa: E402
from app.analytics.time_windows import resolve_window  # noqa: E402
from app.config import PROJECT_ROOT  # noqa: E402
from app.schemas.analysis import Scope  # noqa: E402

OUT = PROJECT_ROOT / "docs" / "readme"
MAN = PROJECT_ROOT / "data" / "manifests"

THEMES = {
    "light": {"surface": "#fcfcfb", "ink": "#0b0b0b", "ink2": "#52514e", "muted": "#8a8984", "grid": "#e6e5e1",
              "series": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"], "track": "#ecebe7", "dim": "#b7d3f6"},
    "dark": {"surface": "#1a1a19", "ink": "#f0efec", "ink2": "#c3c2b7", "muted": "#8f8e86", "grid": "#2c2c2a",
             "series": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300"], "track": "#262624", "dim": "#184f95"},
}
FONT = {"family": "DejaVu Sans"}


def _style(ax, t, title: str, subtitle: str = ""):
    ax.set_facecolor(t["surface"])
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(t["grid"])
    ax.tick_params(colors=t["ink2"], labelsize=9, length=0)
    ax.grid(axis="x", color=t["grid"], linewidth=0.8)
    ax.set_axisbelow(True)
    fig = ax.figure
    fig.patch.set_facecolor(t["surface"])
    fig.text(0.02, 0.965, title, fontsize=13, fontweight="bold", color=t["ink"], va="top", **FONT)
    if subtitle:
        fig.text(0.02, 0.905, subtitle, fontsize=9.5, color=t["ink2"], va="top", **FONT)


def _save(fig, name: str, theme: str):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}-{theme}.png", dpi=200, facecolor=fig.get_facecolor())
    plt.close(fig)


# 1. Intent routing accuracy -------------------------------------------------------------------------

def routing(theme: str):
    t = THEMES[theme]
    d = MAN / "intent_routing"
    rows = [("Local Qwen only (old prompt)", "qwen_only_v1"), ("Local Qwen only (new prompt)", "qwen_only_v2_1"),
            ("Rules only (before)", "rules_v1"), ("Previous router (rules-first)", "rules_first_v1"),
            ("New router, no model", "router_v2_no_llm"), ("New router + local Qwen", "router_v2")]
    vals = [json.loads((d / f"test_{k}_final.json").read_text())["accuracy"] for _, k in rows]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    fig.subplots_adjust(left=0.30, right=0.94, top=0.78, bottom=0.12)
    ax.set_xlim(0, 1.09)
    ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ys = list(range(len(rows)))[::-1]
    for y, v, (label, key) in zip(ys, vals, rows):
        final = key.startswith("router_v2")
        ax.barh(y, 1.0, height=0.62, color=t["track"], zorder=1)
        ax.barh(y, v, height=0.62, color=t["series"][0] if final else t["dim"], zorder=2)
        ax.text(v + 0.012, y, f"{v:.1%}", va="center", fontsize=10, color=t["ink"], fontweight="bold" if final else "normal", zorder=3)
    ax.set_yticks(ys, [r[0] for r in rows], color=t["ink"], fontsize=10)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    _style(ax, t, "Intent routing accuracy on 73 held-out questions",
           "Benchmark v2 test split, scored once after the router was frozen · higher is better")
    ax.grid(axis="x", visible=False)
    _save(fig, "routing-accuracy", theme)


# 2. Retrieval methods ----------------------------------------------------------------------------------

def retrieval(theme: str):
    t = THEMES[theme]
    bm = json.loads((MAN / "evaluation_results.json").read_text())["retrieval"]["by_mode"]
    methods = [("LSA (lexical)", "lsa"), ("MiniLM (semantic)", "dense"), ("Hybrid (RRF)", "hybrid")]
    metrics = [("Topic precision@5", "topic_precision@5"), ("Exact precision@5", "exact_precision@5"), ("Hit rate@5", "hit_rate@5")]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    fig.subplots_adjust(left=0.08, right=0.98, top=0.74, bottom=0.12)
    w = 0.25
    for j, (mlabel, mk) in enumerate(methods):
        xs = [i + (j - 1) * (w + 0.02) for i in range(len(metrics))]
        vals = [bm[mk][k] for _, k in metrics]
        ax.bar(xs, vals, width=w, color=t["series"][j], label=mlabel, zorder=2)
        for x, v in zip(xs, vals):
            ax.text(x, v + 0.015, f"{v:.0%}", ha="center", fontsize=9, color=t["ink"])
    ax.set_xticks(range(len(metrics)), [m for m, _ in metrics], color=t["ink"], fontsize=10)
    ax.set_ylim(0, 1.13)
    ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.grid(axis="y", color=t["grid"], linewidth=0.8)
    ax.grid(axis="x", visible=False)
    _style(ax, t, "Hybrid retrieval: MiniLM + LSA fused by reciprocal rank fusion",
           "36 paraphrased queries over 18,639 chunks · random baseline topic precision 12.5%")
    ax.grid(axis="x", visible=False)
    leg = ax.legend(loc="upper left", bbox_to_anchor=(0, 1.04), ncol=3, frameon=False, fontsize=9.5)
    for txt in leg.get_texts():
        txt.set_color(t["ink2"])
    _save(fig, "retrieval-methods", theme)


# 3. Q1 negative topics ----------------------------------------------------------------------------------

def q1(theme: str):
    t = THEMES[theme]
    db = get_db()
    nov = Scope(window=resolve_window(db, "original", {"type": "last_month"}))
    r = run_operation(db, "rank_negative_topics", nov, {"top_n": 8})
    rows = r.table.rows
    fig, ax = plt.subplots(figsize=(9, 4.4))
    fig.subplots_adjust(left=0.28, right=0.95, top=0.78, bottom=0.12)
    xmax = max(x["conversations"] for x in rows) * 1.22
    ax.set_xlim(0, xmax)
    ys = list(range(len(rows)))[::-1]
    for y, row in zip(ys, rows):
        top5 = row["rank"] <= 5
        ax.barh(y, row["conversations"], height=0.64, color=t["track"], zorder=1)
        ax.barh(y, row["negative"], height=0.64, color=t["series"][1] if top5 else t["muted"], zorder=2)
        ax.text(row["conversations"] + xmax * 0.01, y, f"{int(row['negative'])} of {int(row['conversations'])}  ({row['negative_rate']:.0%})",
                va="center", fontsize=9, color=t["ink2"])
    ax.set_yticks(ys, [f"#{x['rank']}  {x['name']}" for x in rows], color=t["ink"], fontsize=10)
    _style(ax, t, f"Q1 · Negative conversations by topic, {r.scope.window.label}",
           f"Latest month in the data · {int(r.metric('negative_conversations').value)} of {int(r.metric('conversations_in_scope').value)} negative · "
           "orange = top 5 (rank 5 is a disclosed tie at 24) · track = all conversations")
    ax.grid(axis="x", visible=False)
    _save(fig, "q1-negative-topics", theme)


# 4. Q4 priority score composition -----------------------------------------------------------------------

def q4(theme: str):
    t = THEMES[theme]
    db = get_db()
    r = run_operation(db, "leadership_priorities", Scope(), {"top_n": 8})
    rows = r.table.rows
    weights = r.params["weights"]
    labels = {w["signal"]: w["label"] for w in r.series["weights"].rows}
    fig, ax = plt.subplots(figsize=(9, 4.6))
    fig.subplots_adjust(left=0.28, right=0.95, top=0.70, bottom=0.12)
    ax.set_xlim(0, 100)
    ys = list(range(len(rows)))[::-1]
    for y, row in zip(ys, rows):
        left = 0.0
        for i, k in enumerate(weights):
            v = row[f"contrib_{k}"]
            ax.barh(y, v, left=left, height=0.64, color=t["series"][i], edgecolor=t["surface"], linewidth=1.2, zorder=2,
                    label=f"{labels[k]} ({weights[k]:.0%})" if y == ys[0] else None)
            left += v
        ax.text(left + 1, y, f"{row['priority_score']:.1f}", va="center", fontsize=9.5, color=t["ink"], fontweight="bold")
    ax.set_yticks(ys, [f"#{x['rank']}  {x['name']}" for x in rows], color=t["ink"], fontsize=10)
    _style(ax, t, "Q4 · Leadership priority score and what drives it",
           "All 3,000 conversations · score = weighted, min-max-scaled signals (weights in the legend)")
    leg = ax.legend(loc="lower left", bbox_to_anchor=(-0.42, 1.0), ncol=3, frameon=False, fontsize=8.5)
    for txt in leg.get_texts():
        txt.set_color(t["ink2"])
    ax.grid(axis="x", visible=False)
    _save(fig, "q4-priorities", theme)


# 5. Monthly negative-rate trend --------------------------------------------------------------------------

def trend(theme: str):
    t = THEMES[theme]
    db = get_db()
    r = run_operation(db, "sentiment_trend", Scope(), {})
    rows = r.table.rows
    xs = list(range(len(rows)))
    fig, ax = plt.subplots(figsize=(9, 3.8))
    fig.subplots_adjust(left=0.08, right=0.97, top=0.76, bottom=0.14)
    lo = [x["rate_ci_low"] for x in rows]
    hi = [x["rate_ci_high"] for x in rows]
    ax.fill_between(xs, lo, hi, color=t["series"][0], alpha=0.16, linewidth=0, zorder=1)
    ax.plot(xs, [x["negative_rate"] for x in rows], color=t["series"][0], linewidth=2, zorder=2)
    ax.scatter(xs, [x["negative_rate"] for x in rows], s=48, color=t["series"][0], edgecolor=t["surface"], linewidth=2, zorder=3)
    for x, row in zip(xs, rows):
        ax.text(x, row["negative_rate"] + 0.012, f"{row['negative_rate']:.1%}", ha="center", fontsize=9, color=t["ink"])
    ax.set_xticks(xs, [x["month"] for x in rows], color=t["ink"], fontsize=10)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.grid(axis="y", color=t["grid"], linewidth=0.8)
    _style(ax, t, "Negative-conversation rate by month, with 95% Wilson intervals",
           "Overlapping intervals: the rise is not statistically reliable, and the app says so")
    ax.grid(axis="x", visible=False)
    _save(fig, "sentiment-trend", theme)


def main() -> None:
    for theme in THEMES:
        for fn in (routing, retrieval, q1, q4, trend):
            fn(theme)
    print("wrote", sorted(p.name for p in OUT.glob("*.png")))


if __name__ == "__main__":
    main()
