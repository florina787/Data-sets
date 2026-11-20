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

# 5. The outage as dominoes: when each system first went wrong, relative to the bad update
from datetime import datetime  # noqa: E402

onset = {k: datetime.fromisoformat(v) for k, v in rep["anomaly_onset"].items()}
names = {a["resource_id"]: a["name"] for a in rep["affected_systems"]}
root_h = next(h for h in rep["hypotheses"] if h["id"] == rep["conclusion"]["root_hypothesis_id"])
change = next(t for t in rep["timeline"] if t["evidence_id"] in root_h["supporting_evidence"] and t["kind"] == "deployment")
t0 = datetime.fromisoformat(change["at"])
chain = [c["resource_id"] for c in rep["conclusion"]["causal_chain"]]
detected = datetime.fromisoformat(rep["incident"]["detected_at"])
fig, ax = plt.subplots(figsize=(10, 4.2))
ys = list(range(len(chain)))[::-1]
for y, rid in zip(ys, chain):
    m = (onset[rid] - t0).total_seconds() / 60
    ax.plot([0, m], [y, y], color="#2a2e36", lw=1, zorder=1)
    ax.scatter([m], [y], s=180, color=CORAL, zorder=3, edgecolor=BG, linewidth=2)
    ax.text(m + 1.2, y, f"{names.get(rid, rid)}  ·  +{m:.0f} min", va="center", fontsize=10.5)
ax.axvline(0, color=GOLD, lw=2)
ax.text(0.6, ys[0] + 0.55, "the bad update (ingest-orders v2.14.0)", color=GOLD, fontsize=10)
dm = (detected - t0).total_seconds() / 60
ax.axvline(dm, color=INDIGO, lw=1.5, ls="--")
ax.text(dm - 0.6, ys[-1] - 0.6, "incident detected", color=INDIGO, fontsize=10, ha="right")
ax.set_yticks([])
ax.set_xlim(-3, dm + 14)
ax.set_ylim(-1, len(chain))
ax.set_xlabel("minutes after the update")
ax.grid(axis="x", color="#1d2026", zorder=0)
ax.set_title("One bad update, five systems falling like dominoes", loc="left", fontsize=14, pad=14)
save(fig, "chart-outage-dominoes.png")

# 6. Before and after the fix: each system's key measurement against its alarm line
plan = get("/remediations", "viewer")[0]
after = {(c["resource"], c["check"].removeprefix("metric:")): c for c in plan["validations"][-1]["checks"] if c["check"].startswith("metric:")}
ev_before = {}
for t in rep["timeline"]:
    if t["kind"] == "metric":
        e = get(f"/evidence/{t['evidence_id']}", "viewer")
        if not e["payload"].get("capacity"):
            ev_before[(names.get(e["resource_id"], t["resource"]), e["payload"]["name"])] = e["payload"]
order = [names.get(r, r) for r in chain]
pairs = sorted(((k, ev_before[k], after[k]) for k in ev_before if k in after), key=lambda x: order.index(x[0][0]) if x[0][0] in order else 99)
fig, axes = plt.subplots(1, len(pairs), figsize=(11, 3.6))
for ax, ((res, metric), b, a) in zip(axes, pairs):
    ax.bar([0, 1], [b["value"], a["observed"]], color=[CORAL, LIME], width=0.6, zorder=3)
    ax.axhline(b["threshold"], color=GOLD, ls="--", lw=1.4, zorder=4)
    ax.text(-0.55, b["threshold"], " alarm line", color=GOLD, fontsize=8.5, va="bottom", ha="left")
    for x, v in ((0, b["value"]), (1, a["observed"])):
        ax.text(x, v, f"{v:g}", ha="center", va="bottom", fontsize=10)
    ax.set_xticks([0, 1], ["during\noutage", "after\nfix"])
    ax.set_title(f"{res}\n{metric}", fontsize=10, color=FG)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_xlim(-0.6, 1.6)
fig.suptitle("Before and after the fix: each system's key reading versus its alarm line (each panel has its own scale)", x=0.01, ha="left", fontsize=14, y=1.06)
save(fig, "chart-before-after.png")

# 7. Speed, measured by scripts/benchmark.py (10 fresh end-to-end runs)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import io  # noqa: E402
import logging  # noqa: E402
from contextlib import redirect_stderr  # noqa: E402

logging.getLogger("florome").disabled = True
from scripts.benchmark import run as bench  # noqa: E402

with redirect_stderr(io.StringIO()):
    res = bench(10)
med = res["median_ms"]
labels = {"rca_collect_and_analyse": "Investigate\n(18 records, 9 explanations)", "plan": "Build the\nrepair plan",
          "execute_5_steps_and_validate": "Run 5 steps +\nprove recovery", "detect_to_validated_total": "Whole loop,\nend to end"}
fig, ax = plt.subplots(figsize=(9, 3.6))
keys = list(labels)
ax.barh(range(len(keys))[::-1], [med[k] for k in keys], color=[TEAL, TEAL, TEAL, LIME], zorder=3)
for y, k in zip(range(len(keys))[::-1], keys):
    ax.text(med[k] + 4, y, f"{med[k]:.0f} ms", va="center")
ax.set_yticks(range(len(keys))[::-1], [labels[k] for k in keys])
ax.set_xlabel(f"median of {res['runs']} runs, milliseconds (1,000 ms = 1 second)")
ax.grid(axis="x", color="#1d2026", zorder=0)
ax.set_title(f"The whole outage loop, detect to proven recovery: {med['detect_to_validated_total'] / 1000:.2f} s (median)", loc="left", fontsize=14, pad=14)
save(fig, "chart-speed.png")
print(json.dumps(med))
