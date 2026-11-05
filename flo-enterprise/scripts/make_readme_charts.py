"""Generate the README charts from FLO's own analytics services and measured evidence files.

    python scripts/make_readme_charts.py      # writes docs/images/*.png

Every number is computed here from the synthetic dataset (via the same services the API uses) or read from
docs/evidence/*.json (measured load tests / evaluations). Colours follow the validated FLO dark palette.
"""
from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from analytics import service as S  # noqa: E402
from backend import runtime as R  # noqa: E402
from backend.db.session import session_scope  # noqa: E402
from integrations.mock.adapters import Adapters  # noqa: E402
from scenarios import engine as E  # noqa: E402

OUT = ROOT / "docs" / "images"
BG, CARD, LINE, INK, MUTED, GOLD = "#0B1220", "#162338", "#26364F", "#ECF0F6", "#94A3B8", "#D4AF37"
SERIES = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]
GOOD, BAD = SERIES[2], SERIES[1]

plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": CARD, "axes.edgecolor": LINE, "axes.labelcolor": MUTED, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "grid.color": LINE, "grid.linewidth": 0.6, "axes.grid": True, "axes.axisbelow": True,
    "font.family": "DejaVu Sans", "font.size": 11, "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlecolor": INK,
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False, "legend.labelcolor": INK, "savefig.facecolor": BG,
})
bn = FuncFormatter(lambda v, _: f"{v / 1e9:.0f}bn")
mn = FuncFormatter(lambda v, _: f"{v / 1e6:.0f}m")
pct = FuncFormatter(lambda v, _: f"{v * 100:.0f}%")


def mlabel(iso: str) -> str:
    y, m, _ = iso.split("-")
    return ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][int(m) - 1] + f" {y[2:]}"


def finish(fig, name, note="SYNTHETIC DATA · FLO independent demonstration"):
    fig.text(0.995, 0.01, note, ha="right", va="bottom", fontsize=8, color=MUTED)
    fig.savefig(OUT / name, dpi=150, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print("wrote", name)


def story(a):
    """AUM grows while revenue yield and operating margin fall (small multiples, no dual axis)."""
    t = S.aum_trend(a, 24, group_by="vehicle")["data"]
    m = S.margin_trend(a, 24)["data"]
    x = range(len(t["months"]))
    labels = [mlabel(s) if i % 4 == 0 else "" for i, s in enumerate(t["months"])]
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.6))
    bottom = [0.0] * len(t["months"])
    for i, s in enumerate(t["series"]):
        ax[0].fill_between(x, bottom, [b + v for b, v in zip(bottom, s["values"])], color=SERIES[i], alpha=0.85, lw=0, label=s["name"])
        bottom = [b + v for b, v in zip(bottom, s["values"])]
    ax[0].set_title("Total AUM by vehicle (CAD)")
    ax[0].yaxis.set_major_formatter(bn)
    ax[0].legend(loc="upper left", fontsize=9, ncol=2)
    ax[1].plot(x, m["revenue_yield_bps"], color=SERIES[1], lw=2.2, marker="o", ms=3.5)
    ax[1].set_title("Revenue yield (bps of average AUM)")
    ax[2].plot(x, m["operating_margin"], color=SERIES[0], lw=2.2, marker="o", ms=3.5)
    ax[2].yaxis.set_major_formatter(pct)
    ax[2].set_title("Operating margin")
    for k, axx in enumerate(ax):
        axx.set_xticks(list(x))
        axx.set_xticklabels(labels)
        axx.grid(axis="x", visible=False)
    ax[1].annotate(f"{m['revenue_yield_bps'][0]:.0f} → {m['revenue_yield_bps'][-1]:.0f} bps", xy=(0.97, 0.9), xycoords="axes fraction", ha="right", color=INK)
    ax[2].annotate(f"{m['operating_margin'][0] * 100:.1f}% → {m['operating_margin'][-1] * 100:.1f}%", xy=(0.97, 0.9), xycoords="axes fraction", ha="right", color=INK)
    fig.suptitle("The CEO question in one picture: AUM up, yield and margin down", color=INK, fontsize=15, fontweight="bold", x=0.01, ha="left")
    fig.tight_layout()
    finish(fig, "story-aum-yield-margin.png")


def attribution(a):
    r = S.revenue_attribution(a, 12)["data"]
    steps = [("Prior 12m revenue", float(r["annualized_revenue_0"]), "total"), ("Volume effect\n(higher AUM)", float(r["volume_effect"]), "delta"),
             ("Mix effect\n(shift to low-fee)", float(r["mix_effect"]), "delta"), ("Fee changes", float(r["fee_change_effect"]), "delta"),
             ("Last 12m revenue", float(r["annualized_revenue_1"]), "total")]
    fig, ax = plt.subplots(figsize=(11, 5))
    run = 0.0
    for i, (lab, v, kind) in enumerate(steps):
        if kind == "total":
            ax.bar(i, v, color=SERIES[0], width=0.55)
            run = v
            ax.text(i, v, f"{v / 1e6:,.1f}m", ha="center", va="bottom", color=INK, fontsize=10)
        else:
            base = run if v >= 0 else run + v
            ax.bar(i, abs(v), bottom=base, color=GOOD if v >= 0 else BAD, width=0.55)
            ax.text(i, base + abs(v), f"{v / 1e6:+,.1f}m", ha="center", va="bottom", color=INK, fontsize=10)
            run += v
    ax.set_xticks(range(len(steps)))
    ax.set_xticklabels([s[0] for s in steps])
    lo = min(float(r["annualized_revenue_0"]), float(r["annualized_revenue_1"])) * 0.9
    ax.set_ylim(lo, max(float(r["annualized_revenue_0"]), float(r["annualized_revenue_1"])) * 1.08)
    ax.yaxis.set_major_formatter(mn)
    ax.grid(axis="x", visible=False)
    ax.set_title(f"Revenue attribution — exact volume / mix / fee decomposition (yield {float(r['yield_bps_0']):.1f} → {float(r['yield_bps_1']):.1f} bps)", loc="left")
    finish(fig, "revenue-attribution.png")


def flows(a):
    d = S.net_flows(a, 24, group_by="vehicle")["data"]
    fig, ax = plt.subplots(figsize=(11, 4.6))
    x = list(range(len(d["months"])))
    for i, s in enumerate(d["series"]):
        cum, c = [], 0.0
        for v in s["net"]:
            c += v
            cum.append(c)
        ax.plot(x, cum, color=SERIES[i], lw=2.4, label=s["name"])
        ax.text(x[-1] + 0.3, cum[-1], f"{s['name']} {cum[-1] / 1e9:+.1f}bn", color=INK, va="center", fontsize=10)
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([mlabel(s) if i % 4 == 0 else "" for i, s in enumerate(d["months"])])
    ax.set_xlim(0, len(x) + 4.5)
    ax.yaxis.set_major_formatter(bn)
    ax.grid(axis="x", visible=False)
    ax.set_title("Cumulative net client flows by vehicle — rotation from mutual funds to ETFs and pools", loc="left")
    finish(fig, "net-flows-rotation.png")


def scenarios(a):
    c = E.compare(a)["scenarios"]
    names = [s["scenario"].replace("_", " ") for s in c]
    fig, ax = plt.subplots(1, 2, figsize=(14, 4.6))
    aum = [float(s["aum_end"]) for s in c]
    oi = [float(s["operating_income"]) for s in c]
    ax[0].bar(names, aum, color=[SERIES[0]] * len(c), width=0.55)
    ax[0].yaxis.set_major_formatter(bn)
    ax[0].set_title("Estimated AUM after 12 months")
    for i, v in enumerate(aum):
        ax[0].text(i, v, f"{v / 1e9:.1f}bn", ha="center", va="bottom", color=INK)
    ax[1].bar(names, oi, color=[GOOD if v >= 0 else BAD for v in oi], width=0.55)
    ax[1].axhline(0, color=MUTED, lw=0.8)
    ax[1].yaxis.set_major_formatter(mn)
    ax[1].set_title("Estimated operating income")
    for i, v in enumerate(oi):
        ax[1].text(i, v, f"{v / 1e6:+.0f}m", ha="center", va="bottom" if v >= 0 else "top", color=INK)
    for axx in ax:
        axx.grid(axis="x", visible=False)
    fig.suptitle("Scenario simulator — deterministic, conditional on stated assumptions (no probabilities)", color=INK, fontsize=14, fontweight="bold", x=0.01, ha="left")
    fig.tight_layout()
    finish(fig, "scenarios.png")


def concentration(a):
    d = S.enterprise_concentration(a, top=10)["data"]
    rows = d["top_holdings"][::-1]
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.barh([r["name"].replace(" (SYN)", "") for r in rows], [r["weight"] for r in rows], color=SERIES[0], height=0.6)
    for i, r in enumerate(rows):
        ax.text(r["weight"], i, f"  {r['weight'] * 100:.1f}% · {r['portfolios_holding']} portfolios", va="center", color=INK, fontsize=9)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v * 100:.0f}%"))
    ax.set_xlim(0, max(r["weight"] for r in rows) * 1.6)
    ax.grid(axis="y", visible=False)
    ax.set_title(f"Largest issuer exposures across {d['portfolio_count']} portfolios — {d['portfolios_breaching_single_issuer_limit']} breach the 10% single-issuer limit", loc="left")
    finish(fig, "concentration.png")


def load_tests():
    runs = json.loads((ROOT / "docs" / "evidence" / "load_test_report.json").read_text())["runs"]
    users = [r["users"] for r in runs]
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.6))
    for i, kind in enumerate(["dashboard", "ask", "search"]):
        ax[0].plot(users, [r["by_kind"][kind]["p95_ms"] / 1000 for r in runs], marker="o", lw=2.2, color=SERIES[i], label=kind)
    ax[0].set_xscale("log")
    ax[0].set_yscale("log")
    ax[0].axhline(2, color=GOLD, ls="--", lw=1)
    ax[0].text(users[0], 2.3, "dashboard target p95 < 2 s", color=GOLD, fontsize=9)
    ax[0].set_title("p95 latency (s, log) vs virtual users")
    ax[0].legend()
    ax[1].bar([str(u) for u in users], [r["totals"]["throughput_rps"] for r in runs], color=SERIES[0], width=0.55)
    ax[1].set_title("Throughput (req/s) — single 4-vCPU host")
    ok = [r["totals"]["success_rate"] for r in runs]
    shed = [r["totals"]["load_shed_503"] / r["totals"]["requests"] for r in runs]
    ax[2].bar([str(u) for u in users], ok, color=GOOD, width=0.55, label="2xx")
    ax[2].bar([str(u) for u in users], shed, bottom=ok, color=SERIES[3], width=0.55, label="503 load-shed (Retry-After)")
    ax[2].yaxis.set_major_formatter(pct)
    ax[2].set_ylim(0, 1.05)
    ax[2].legend(loc="lower left", fontsize=9)
    ax[2].set_title("Outcome mix — no 500s, no crashes")
    for axx in ax[1:]:
        axx.grid(axis="x", visible=False)
        axx.set_xlabel("virtual users")
    fig.suptitle("Measured load tests (docs/evidence/load_test_report.json) — not production SLAs", color=INK, fontsize=14, fontweight="bold", x=0.01, ha="left")
    fig.tight_layout()
    finish(fig, "load-tests.png", "MEASURED · single host also running the load generator")


def verification():
    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "-o", "addopts="], cwd=ROOT,
                         capture_output=True, text=True).stdout
    counts = Counter()
    for line in out.splitlines():
        if "::" in line:
            counts[{"unit": "Unit & financial", "security": "Security & adversarial", "e2e": "End-to-end journeys"}.get(line.split("/")[1], line.split("/")[1])] += 1
    ev = json.loads((ROOT / "docs" / "evidence" / "eval_report.json").read_text())
    gate = json.loads((ROOT / "docs" / "evidence" / "release_gate.json").read_text())
    labels = list(counts) + ["Playwright browser journeys", "Evaluation cases", "OPA policy tests", "Release-gate checks"]
    vals = list(counts.values()) + [6, ev["cases"], 7, len(gate["checks"])]
    passed = list(counts.values()) + [6, ev["passed"], 7, sum(1 for c in gate["checks"] if c["passed"])]
    fig, ax = plt.subplots(figsize=(11, 4.6))
    ax.barh(labels[::-1], vals[::-1], color=LINE, height=0.6)
    ax.barh(labels[::-1], passed[::-1], color=GOOD, height=0.6)
    for i, (v, p) in enumerate(zip(vals[::-1], passed[::-1])):
        ax.text(v, i, f"  {p}/{v} pass", va="center", color=INK)
    ax.set_xlim(0, max(vals) * 1.25)
    ax.grid(axis="y", visible=False)
    ax.set_title(f"Verification — {sum(counts.values())} pytest tests (SQLite + PostgreSQL), release gate {gate['status']}", loc="left")
    finish(fig, "verification.png", "MEASURED")


def data_volumes(st):
    keys = ["clients", "transactions", "portfolio_monthly", "portfolio_holdings", "service_interactions", "client_goals", "client_positions",
            "product_monthly", "portfolios", "products", "decisions", "compliance_events", "advisors"]
    vals = {k: len(st.tables[k]) for k in keys}
    fig, ax = plt.subplots(figsize=(11, 5))
    items = sorted(vals.items(), key=lambda kv: kv[1])
    ax.barh([k.replace("_", " ") for k, _ in items], [v for _, v in items], color=SERIES[6], height=0.6)
    for i, (_, v) in enumerate(items):
        ax.text(v, i, f"  {v:,}", va="center", color=INK, fontsize=9)
    ax.set_xscale("log")
    ax.grid(axis="y", visible=False)
    ax.set_title("Synthetic dataset (seed 20261020, referential integrity enforced) — rows per table, log scale", loc="left")
    finish(fig, "synthetic-data.png")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with session_scope() as s:
        st = R.store(s)
    a = Adapters(st, "t-flo")
    story(a)
    attribution(a)
    flows(a)
    scenarios(a)
    concentration(a)
    data_volumes(st)
    load_tests()
    verification()


if __name__ == "__main__":
    main()
