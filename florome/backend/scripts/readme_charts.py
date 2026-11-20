"""Draw README charts from a running Florome API (demo tenant). Every number is read from the API, not typed in.

Usage: python scripts/readme_charts.py http://localhost:8000 ../docs/readme
"""

import json
import sys
import urllib.request
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

API, OUT = sys.argv[1], Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
BG, FG, MUTED, GOLD, LIME, CORAL, TEAL, INDIGO = "#0b0d10", "#f2f2f2", "#8b8f9a", "#E8C26A", "#C6F36B", "#ff6b5b", "#7ad7c9", "#7C84F2"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.facecolor": BG, "figure.facecolor": BG, "axes.edgecolor": "#2a2e36",
                     "axes.labelcolor": FG, "xtick.color": MUTED, "ytick.color": MUTED, "text.color": FG, "axes.spines.top": False,
                     "axes.spines.right": False})


def get(path, role="admin"):
    req = urllib.request.Request(API + "/api/v1" + path, headers={"Authorization": f"Bearer demo-meridian-{role}"})
    return json.load(urllib.request.urlopen(req))


def save(fig, name):
    fig.savefig(OUT / name, dpi=180, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print("wrote", name)


# 1. Shield evaluation: three approaches on the same 9 labelled spots
rows = {r["pipeline"]: r for r in reversed(get("/shield/evaluation"))}
names = [("scanner_only", "Scanners only\n(Opengrep + Bandit)"), ("graph_unverified", "Code graph\n(no lab)"), ("hybrid_verified", "Florome Shield\n(graph + lab proof)")]
fig, ax = plt.subplots(figsize=(9, 4.4))
w = 0.26
for i, (key, label) in enumerate(names):
    m = rows[key]["metrics"]
    for j, (field, color, lab) in enumerate([("tp", LIME, "Real problems found"), ("fp", CORAL, "False alarms"), ("fn", "#555b66", "Real problems missed")]):
        ax.bar(i + (j - 1) * w, m[field], w * 0.92, color=color, label=lab if i == 0 else None, zorder=3)
        ax.text(i + (j - 1) * w, m[field] + 0.08, str(m[field]), ha="center", color=FG, fontsize=10)
ax.set_xticks(range(3), [n for _, n in names])
ax.set_ylim(0, 6)
ax.set_ylabel("sites (out of 5 real problems, 4 safe look-alikes)")
ax.grid(axis="y", color="#1d2026", zorder=0)
ax.legend(frameon=False, ncol=3, loc="upper left")
ax.set_title("Same test app, three approaches: who is right?", loc="left", fontsize=14, color=FG, pad=14)
save(fig, "chart-shield-evaluation.png")

# 2. RCA: what happened to each explanation the engine considered
inc = get("/incidents", "viewer")["items"]
inc = next(i for i in inc if i["title"].startswith("Revenue API"))
rep = get(f"/rca/{inc['id']}", "viewer")
colors = {"confirmed": LIME, "probable": INDIGO, "inconclusive": GOLD, "disproven": "#4a4f59"}
hyps = rep["hypotheses"]
fig, ax = plt.subplots(figsize=(9, 4.6))
for k, h in enumerate(reversed(hyps)):
    passed = sum(t["result"] == "pass" for t in h["tests"])
    failed = sum(t["result"] == "fail" for t in h["tests"])
    unknown = sum(t["result"] == "unknown" for t in h["tests"])
    ax.barh(k, passed, color=TEAL, zorder=3)
    ax.barh(k, failed, left=passed, color=CORAL, alpha=0.75, zorder=3)
    ax.barh(k, unknown, left=passed + failed, color="#3a3f48", zorder=3)
    title = h["title"].split(":")[0] if h["role"] == "root_cause" else h["title"].replace("Failure propagated from ", "").split(" (")[0]
    ax.text(-0.15, k, f"{h['id']}  {title[:46]}", ha="right", va="center", fontsize=9.5, color=FG)
    ax.text(passed + failed + unknown + 0.12, k, h["status"].upper(), va="center", fontsize=9, color=colors[h["status"]] if h["status"] != "disproven" else MUTED)
ax.set_yticks([])
ax.set_xlabel("checks: teal = passed, red = failed against the evidence, grey = could not be checked (missing evidence)")
ax.set_xlim(0, 7)
ax.grid(axis="x", color="#1d2026", zorder=0)
ax.set_title("Every explanation, and the checks that confirmed or killed it", loc="left", fontsize=14, pad=14)
save(fig, "chart-rca-hypotheses.png")

# 3. Containment: how fast each misbehaving agent was stopped
ev = {}
for e in get("/shield/containment/events"):
    ev.setdefault(e["scenario"], e)
order = sorted(ev.values(), key=lambda e: e["forensics"]["seconds"])
fig, ax = plt.subplots(figsize=(9, 3.8))
for k, e in enumerate(order):
    ms = e["forensics"]["seconds"] * 1000
    ax.barh(k, ms, color=LIME if e["outcome"] == "completed" else CORAL, zorder=3)
    ax.text(ms * 1.08, k, f"{ms:,.0f} ms  ·  {e['violation'] or 'finished normally'}", va="center", fontsize=9.5)
ax.set_yticks(range(len(order)), [e["scenario"].replace("_", " ") for e in order])
ax.set_xscale("log")
ax.set_xlim(10, 40000)
ax.set_xlabel("time from start until the session ended (log scale)")
ax.grid(axis="x", color="#1d2026", zorder=0)
ax.set_title("Misbehaving AI agents: stopped on their first bad move", loc="left", fontsize=14, pad=14)
save(fig, "chart-containment.png")

# 4. Lab verification: every isolated run, per suspected spot
runs = get("/shield/range/runs")
hyp = {h["id"]: h for h in get("/shield/hypotheses")}
per = Counter()
for r in runs:
    if r["purpose"] == "verify" and r["hypothesis_id"] in hyp:
        h = hyp[r["hypothesis_id"]]
        per[(h["function"], h["vuln_class"], r["outcome"])] += 1
sites = sorted({(f, c) for f, c, _ in per}, key=lambda x: (-per[(x[0], x[1], "reproduced")], x[0]))
fig, ax = plt.subplots(figsize=(9, 4.6))
for k, (f, c) in enumerate(reversed(sites)):
    rep_n, not_n = per[(f, c, "reproduced")], per[(f, c, "not_reproduced")]
    ax.barh(k, rep_n, color=CORAL, zorder=3)
    ax.barh(k, not_n, left=rep_n, color=TEAL, zorder=3)
    ax.text(-0.1, k, f"{f}  ·  {c.replace('_', ' ')}", ha="right", va="center", fontsize=9.5)
ax.set_yticks([])
ax.set_xlabel("isolated lab runs: red = attack worked (real problem), teal = attack failed (safe)")
ax.set_xticks([0, 1, 2])
ax.grid(axis="x", color="#1d2026", zorder=0)
ax.set_title("Proof, not opinion: every suspicion was attacked in a sealed copy", loc="left", fontsize=14, pad=14)
save(fig, "chart-lab-runs.png")
