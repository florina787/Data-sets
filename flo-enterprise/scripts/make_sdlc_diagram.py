"""Render docs/images/sdlc/01-ai-sdlc.png — the ten-step AI-SDLC used to build FLO."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

BG, CARD, GOLD, TEXT, MUTED, RED = "#0B1220", "#162338", "#D4AF37", "#E6EDF7", "#9FB0C8", "#e66767"
LANES = [
    ("① DESIGN", "#3987e5", [("0  Discover", "personas · jobs-to-be-done\nharm & misuse cases"),
                             ("1  Frame & risk-tier", "decision rights · data class\nhuman-in-the-loop points"),
                             ("2  Data contract", "deterministic synthetic data\nschemas · lineage · ACLs")]),
    ("② BUILD", "#199e70", [("3  Policy-as-code", "RBAC + ABAC YAML · OPA\ndeny-by-default · fail-closed"),
                            ("4  Deterministic core", "Decimal finance engine\nsemantic layer · scenarios"),
                            ("5  Agents & HITL", "supervisors · tool gateway\nhash-bound approvals")]),
    ("③ PROVE", "#c98500", [("6  Evaluate", "unit · security · evals\nAPI journeys · browser · load"),
                            ("7  Release gate", "every check green\nor nothing ships")]),
    ("④ RUN", "#9085e9", [("8  Deploy", "Compose · k8s · Helm\nTerraform · migrations"),
                          ("9  Operate & observe", "audit chain · traces (masked)\nmetrics · drills")]),
]

fig = plt.figure(figsize=(16, 9.6), facecolor=BG)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 16); ax.set_ylim(-1.6, 8.6); ax.axis("off")
ax.text(8, 8.15, "Wealth Advisor — the AI-SDLC way", ha="center", color=TEXT, fontsize=22, weight="bold")
ax.text(8, 7.65, "Ten steps, four lanes. Security, privacy and evidence are designed in — not bolted on.",
        ha="center", color=MUTED, fontsize=12.5)

xs, W, H = [0.4, 4.4, 8.4, 12.4], 3.3, 1.45
centers = {}
for (lane, col, steps), x in zip(LANES, xs):
    ax.add_patch(FancyBboxPatch((x - 0.12, -0.15), W + 0.24, 7.25, boxstyle="round,pad=0.02,rounding_size=0.15",
                                fc="#101B2D", ec=col, lw=1.2, alpha=0.9))
    ax.text(x + W / 2, 6.72, lane, ha="center", color=col, fontsize=15, weight="bold")
    y = 5.0
    for title, sub in steps:
        gate = title.startswith("7")
        ax.add_patch(FancyBboxPatch((x, y), W, H, boxstyle="round,pad=0.02,rounding_size=0.12",
                                    fc=CARD, ec=GOLD if gate else col, lw=2.6 if gate else 1.4))
        ax.text(x + 0.18, y + H - 0.38, title, color=GOLD if gate else TEXT, fontsize=13.5, weight="bold", va="center")
        ax.text(x + 0.18, y + 0.45, sub, color=MUTED, fontsize=10.5, va="center", linespacing=1.35)
        centers[title[0]] = (x, y)
        y -= 2.05

def arrow(p, q, **kw):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=18, **kw))

# within-lane flow
for a, b in [("0", "1"), ("1", "2"), ("3", "4"), ("4", "5"), ("6", "7"), ("8", "9")]:
    (xa, ya), (_, yb) = centers[a], centers[b]
    arrow((xa + W / 2, ya), (xa + W / 2, yb + H), color=MUTED, lw=1.4)
# lane hand-offs, routed through the gutter between lanes
for a, b in [("2", "3"), ("5", "6"), ("7", "8")]:
    (xa, ya), (xb, yb) = centers[a], centers[b]
    gx = xa + W + 0.35
    ax.plot([xa + W, gx, gx], [ya + H / 2, ya + H / 2, yb + H / 2], color=TEXT, lw=1.6)
    arrow((gx, yb + H / 2), (xb, yb + H / 2), color=TEXT, lw=1.6)
# defects loop: evaluate -> build
(x6, y6), (x4, y4) = centers["6"], centers["4"]
arrow((x6, y6 + 0.35), (x4 + W, y4 + H - 0.35), color=RED, lw=1.6, linestyle="--", connectionstyle="arc3,rad=0.3")
ax.text(x6 + W / 2, 1.55, "↺ defects found in ③\nare fixed in the right layer of ②\n(policy, engine or agent — never the test)",
        ha="center", va="center", color=RED, fontsize=10.5, linespacing=1.4)
# measured feedback: operate -> discover, routed under the lanes
arrow((xs[3] + W / 2, -0.2), (xs[0] + W / 2, -0.2), color=GOLD, lw=2.2, connectionstyle="arc3,rad=-0.06")
ax.text(8, -1.4, "measured feedback — production evidence (not anecdotes) re-enters Discover",
        ha="center", color=GOLD, fontsize=12, style="italic")

out = Path(__file__).resolve().parents[1] / "docs/images/sdlc/01-ai-sdlc.png"
fig.savefig(out, dpi=150, facecolor=BG)
print(out)
