"""Render the FLO 2.0 README graphs from the platform's deterministic analytics (synthetic data).

Style follows the app's chart language: near-black tiles, a glowing gold-to-lime hero line, fading area fills,
faint grids, rounded value pills. Every number comes from analytics/ functions, not from this script.
Run: .venv/bin/python scripts/make_flo2_charts.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("FLO_DATABASE_URL", f"sqlite:///{ROOT / 'var' / 'flo.db'}")

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

from analytics import performance  # noqa: E402
from backend import runtime as R  # noqa: E402
from backend.db.session import session_scope  # noqa: E402
from integrations.mock.adapters import Adapters  # noqa: E402

OUT = ROOT / "docs" / "images"
BG, TILE, INK, MUTED, GRID = "#0B0F17", "#121826", "#ECF0F6", "#94A3B8", "#1E2636"
GOLD, MID, LIME, INDIGO, RED = "#D4AF37", "#E2C766", "#C8E06B", "#5B67F1", "#EF6B6B"
HERO = LinearSegmentedColormap.from_list("hero", [GOLD, MID, LIME])
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.edgecolor": BG, "axes.labelcolor": MUTED, "xtick.color": MUTED,
                     "ytick.color": MUTED, "text.color": INK})


def tile(fig, ax):
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(TILE)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0, labelsize=10)


def glow_line(ax, x, y):
    pts = np.array([x, y]).T.reshape(-1, 1, 2)
    segs = np.concatenate([pts[:-1], pts[1:]], axis=1)
    for w, a in ((10, 0.06), (6, 0.12), (3.2, 1.0)):
        lc = LineCollection(segs, cmap=HERO, norm=plt.Normalize(x.min(), x.max()), linewidth=w, alpha=a, capstyle="round")
        lc.set_array(x[:-1])
        ax.add_collection(lc)
    ax.fill_between(x, y, y.min() - (y.max() - y.min()) * 0.15, color=MID, alpha=0.10, linewidth=0)


def pill(ax, x, y, text, fc, tc=BG, size=10, transform=None):
    ax.text(x, y, f" {text} ", fontsize=size, color=tc, ha="left", va="center", fontweight="bold", transform=transform or ax.transAxes,
            bbox=dict(boxstyle="round,pad=0.35,rounding_size=0.8", fc=fc, ec="none"))


def main() -> None:
    with session_scope() as s:
        st = R.store(s)
    a = Adapters(st, "t-flo")
    perf24 = performance.portfolio_performance(a, 12)["data"]
    perf3 = performance.portfolio_performance(a, 3)["data"]
    top = perf3["top_sector"]
    shock = performance.sector_shock(a, top, -0.15)["data"]

    # 1 portfolio performance: glowing cumulative line + faint monthly bars
    months = perf24["months"]
    cum = np.array(perf24["cumulative"]) * 100
    mon = np.array(perf24["monthly_returns"]) * 100
    x = np.arange(len(months))
    fig, ax = plt.subplots(figsize=(12, 5.2), dpi=160)
    tile(fig, ax)
    ax.bar(x, mon, width=0.55, color=[LIME if v >= 0 else RED for v in mon], alpha=0.28, zorder=1)
    glow_line(ax, x.astype(float), cum)
    ax.scatter([x[-1]], [cum[-1]], s=80, color=LIME, zorder=5, edgecolor=TILE, linewidth=2)
    ax.annotate(f"{cum[-1]:.2f}%", (x[-1], cum[-1]), xytext=(-60, 18), textcoords="offset points", fontsize=11, color=BG, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.35,rounding_size=0.8", fc=INK, ec="none"))
    ax.set_xlim(-0.5, len(x) - 0.5)
    ax.set_ylim(min(mon.min(), cum.min()) - 2, max(cum.max(), mon.max()) + 3)
    ax.set_xticks(x[::3], [m[:7] for m in months[::3]])
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    fig.text(0.06, 0.93, "Managed portfolios · cumulative return, 24 months", fontsize=13, color=MUTED)
    fig.text(0.06, 0.84, f"{perf3['period']['return'] * 100:.2f}%", fontsize=30, fontweight="bold", color=INK)
    fig.text(0.06, 0.80, "last quarter", fontsize=10, color=MUTED)
    pill(fig.axes[0], 0.2, 1.12, f"{(perf3['period']['return'] - perf3['prior_period']['return']) * 100:+.2f} pp vs prior quarter", LIME)
    fig.subplots_adjust(top=0.78, left=0.06, right=0.98, bottom=0.1)
    fig.savefig(OUT / "flo2-performance.png", facecolor=BG)
    plt.close(fig)

    # 2 sector contribution (last quarter)
    sc = perf3["sector_contribution"]
    fig, ax = plt.subplots(figsize=(12, 5.4), dpi=160)
    tile(fig, ax)
    ax.grid(axis="x", color=GRID)
    ax.grid(axis="y", visible=False)
    names = [r["sector"] for r in sc][::-1]
    vals = [r["contribution"] * 100 for r in sc][::-1]
    cols = [GOLD if n == top else (INDIGO if v >= 0 else RED) for n, v in zip(names, vals)]
    ax.barh(names, vals, color=cols, height=0.62)
    for i, v in enumerate(vals):
        ax.text(v + (0.01 if v >= 0 else -0.01), i, f"{v:+.2f} pp", va="center", ha="left" if v >= 0 else "right", fontsize=9, color=MUTED)
    ax.axvline(0, color=GRID, linewidth=1)
    fig.text(0.06, 0.93, "Return contribution by sector · last quarter (holdings-based approximation)", fontsize=13, color=MUTED)
    fig.text(0.06, 0.86, f"Top contributor: {top}", fontsize=18, fontweight="bold", color=GOLD)
    fig.subplots_adjust(top=0.82, left=0.22, right=0.97, bottom=0.08)
    fig.savefig(OUT / "flo2-sector-contribution.png", facecolor=BG)
    plt.close(fig)

    # 3 sector shock by mandate
    bm = shock["by_mandate"]
    fig, ax = plt.subplots(figsize=(12, 4.6), dpi=160)
    tile(fig, ax)
    ax.grid(axis="x", color=GRID)
    ax.grid(axis="y", visible=False)
    ks = sorted(bm, key=bm.get)
    ax.barh(ks, [bm[k] * 100 for k in ks], color=[RED if k == ks[0] else "#7C3A46" for k in ks], height=0.55)
    for i, k in enumerate(ks):
        ax.text(bm[k] * 100 + 0.03, i, f"{bm[k] * 100:.2f}%", va="center", ha="left", fontsize=11, color=INK, fontweight="bold")
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.1f}%")
    fig.text(0.06, 0.92, f"Simulated: {top} falls 15% (instantaneous, single-sector, not a forecast)", fontsize=13, color=MUTED)
    fig.text(0.06, 0.83, f"Portfolios −CAD {abs(shock['portfolio_impact']) / 1e6:.1f}m  ·  product AUM −CAD {abs(shock['product_aum_impact']) / 1e6:.0f}m  ·  "
                         f"fee revenue −CAD {abs(shock['annual_fee_revenue_impact']) / 1e6:.1f}m / yr", fontsize=15, fontweight="bold", color=INK)
    fig.subplots_adjust(top=0.76, left=0.2, right=0.97, bottom=0.1)
    fig.savefig(OUT / "flo2-sector-shock.png", facecolor=BG)
    plt.close(fig)

    # 4 verification tiles (counts from the FLO 2.0 verification run, see README)
    tiles = [("181", "backend tests passed", "1 skipped: OPA parity (no opa binary)"), ("20/20", "browser tests", "10 demos · memory · mobile · axe"),
             ("8/8", "frontend unit tests", "chart mapping · SSE · formatting"), ("10/10", "evaluation cases", "grounding · citations · injection"),
             ("0", "serious a11y violations", "axe-core on welcome + workspace"), ("PASS", "release gate", "ruff · bandit · pip-audit · secrets · tsc")]
    fig = plt.figure(figsize=(12, 4.2), dpi=160)
    fig.patch.set_facecolor(BG)
    for i, (big, label, sub) in enumerate(tiles):
        ax = fig.add_axes([0.02 + (i % 3) * 0.33, 0.52 - (i // 3) * 0.48, 0.31, 0.42])
        ax.axis("off")
        ax.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.08", fc=TILE, ec=GRID, transform=ax.transAxes))
        ax.text(0.07, 0.62, big, fontsize=30, fontweight="bold", color=LIME if big not in ("0",) else LIME, transform=ax.transAxes, va="center")
        ax.text(0.07, 0.32, label, fontsize=12, color=INK, transform=ax.transAxes)
        ax.text(0.07, 0.14, sub, fontsize=9, color=MUTED, transform=ax.transAxes)
    fig.savefig(OUT / "flo2-verification.png", facecolor=BG)
    plt.close(fig)
    print("wrote flo2-performance, flo2-sector-contribution, flo2-sector-shock, flo2-verification")


if __name__ == "__main__":
    main()
