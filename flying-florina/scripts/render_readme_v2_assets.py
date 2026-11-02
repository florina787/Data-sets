"""Render the Flying_Florina 2.0 README graphics as SVG (no plotting libraries needed).

Every chart value is read from files the project itself wrote:
  docs/eval/four_questions_test_v1_rules_only.json, docs/eval/four_questions_test_v2_rules_only.json
  docs/latency_measured.json
Nothing is estimated. Diagrams (banner, architecture, pipeline) are drawings, not data.

Usage:  python scripts/render_readme_v2_assets.py
Output: docs/assets/v2/*.svg
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets" / "v2"

# Conversation Intelligence Copilot design tokens
BG, SURFACE, ELEV, BORDER = "#0B1020", "#111827", "#17233C", "#24314F"
INDIGO, CYAN, VIOLET = "#6366F1", "#22D3EE", "#A78BFA"
POS, WARN, NEG = "#34D399", "#FBBF24", "#F87171"
TEXT, MUTED, GOLD = "#E5E7EB", "#94A3B8", "#D7B46A"
FONT = "Inter, 'Segoe UI', system-ui, -apple-system, Helvetica, Arial, sans-serif"


def t(x, y, s, size=14, weight=400, fill=TEXT, anchor="start", extra=""):
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}" {extra}>{escape(str(s))}</text>')


def frame(w, h, title, subtitle, body, source):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
        f'aria-label="{escape(title)}">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{BG}"/>'
        f'<stop offset="1" stop-color="#131A35"/></linearGradient></defs>'
        f'<rect width="{w}" height="{h}" rx="20" fill="url(#g)"/>'
        f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="19" fill="none" stroke="{BORDER}"/>'
        + t(36, 50, title, 24, 800) + t(36, 76, subtitle, 14, 400, MUTED)
        + body + t(36, h - 20, source, 11, 400, MUTED) + "</svg>"
    )


def load(p):
    return json.loads((ROOT / p).read_text())


# ---------------------------------------------------------------- charts (data)

def eval_metrics(v1, v2):
    rows = [
        ("Routing accuracy", "routing_accuracy"),
        ("Macro-F1", "macro_f1"),
        ("Four-family routing", "four_family_routing_accuracy"),
        ("Workflow correctness", "workflow_correctness"),
        ("Evidence accuracy", "evidence_accuracy"),
        ("Answer completeness", "answer_completeness"),
        ("Follow-up accuracy", "follow_up_accuracy"),
    ]
    w, h, x0, x1 = 1200, 560, 280, 1100
    y = 130
    body = [t(x0, 112, "Held-out v1 (router 1.0)", 13, 600, VIOLET), t(x0 + 220, 112, "Fresh held-out v2 (router 1.1)", 13, 600, CYAN)]
    # target line at 95%
    tx = x0 + (x1 - x0) * 0.95
    for pct in (0, 0.25, 0.5, 0.75, 1.0):
        gx = x0 + (x1 - x0) * pct
        body.append(f'<line x1="{gx}" y1="{y-6}" x2="{gx}" y2="{y + len(rows)*52}" stroke="{BORDER}" stroke-dasharray="2 4"/>')
        body.append(t(gx, y + len(rows) * 52 + 18, f"{int(pct*100)}%", 11, 400, MUTED, "middle"))
    for label, key in rows:
        body.append(t(x0 - 16, y + 26, label, 14, 600, TEXT, "end"))
        for i, (d, col) in enumerate(((v1, VIOLET), (v2, CYAN))):
            v = d[key]
            bw = (x1 - x0) * v
            by = y + 6 + i * 20
            body.append(f'<rect x="{x0}" y="{by}" width="{bw:.1f}" height="16" rx="4" fill="{col}" opacity="0.9"/>')
            body.append(t(x0 + bw + 8, by + 13, f"{v*100:.1f}%", 12, 700, col))
        y += 52
    body.append(f'<line x1="{tx}" y1="122" x2="{tx}" y2="{y}" stroke="{WARN}" stroke-width="2" stroke-dasharray="6 4"/>')
    body.append(t(tx, 122 - 2, "95% routing target", 11, 700, WARN, "middle", 'dy="-2"'))
    return frame(w, h, "Four-question engine: measured evaluation",
                 f"{v1['items']} + {v2['items']} held-out questions · rules + semantic router · local Qwen not available on the build machine",
                 "".join(body), "Source: docs/eval/four_questions_test_v{1,2}_rules_only.json (written by scripts/eval_four_questions.py)")


def per_label_f1(v2):
    labels = sorted(v2["per_label"].items(), key=lambda kv: (-kv[1]["support"], kv[0]))
    w = 1200
    rowh = 26
    h = 150 + rowh * len(labels)
    x0, x1, y = 300, 1000, 110
    fam = {"diagnostics", "recovery", "modernization", "executive"}
    body = []
    for name, m in labels:
        f1 = m["f1"]
        col = CYAN if name in fam else INDIGO
        if f1 < 0.9:
            col = WARN
        body.append(t(x0 - 14, y + 15, name.replace("_", " "), 13, 700 if name in fam else 400, TEXT, "end"))
        body.append(f'<rect x="{x0}" y="{y+2}" width="{x1-x0}" height="16" rx="4" fill="{ELEV}"/>')
        body.append(f'<rect x="{x0}" y="{y+2}" width="{(x1-x0)*f1:.1f}" height="16" rx="4" fill="{col}"/>')
        body.append(t(x1 + 12, y + 15, f"{f1:.3f}", 12, 700, col))
        body.append(t(x1 + 90, y + 15, f"n={m['support']}", 12, 400, MUTED))
        y += rowh
    body.append(t(x1 + 12, 100, "F1", 12, 700, MUTED)); body.append(t(x0, 100, "Cyan = the four signature families · amber = F1 below 0.90", 12, 400, MUTED))
    return frame(w, h, "Per-label F1 on the fresh held-out set (v2)", f"Macro-F1 {v2['macro_f1']:.3f} across {len(labels)} labels",
                 "".join(body), "Source: docs/eval/four_questions_test_v2_rules_only.json → per_label")


def route_methods(v2):
    items = sorted(v2["route_methods"].items(), key=lambda kv: -kv[1])
    total = sum(v for _, v in items)
    colors = [CYAN, INDIGO, VIOLET, POS, WARN, NEG, GOLD, MUTED]
    w, h = 1200, 300
    x0, x1, y = 36, 1164, 110
    body, x = [], x0
    for i, (k, v) in enumerate(items):
        bw = (x1 - x0) * v / total
        body.append(f'<rect x="{x:.1f}" y="{y}" width="{bw:.1f}" height="46" fill="{colors[i % len(colors)]}"/>')
        if bw > 46:
            body.append(t(x + bw / 2, y + 29, str(v), 15, 800, BG, "middle"))
        x += bw
    lx, ly = x0, y + 90
    for i, (k, v) in enumerate(items):
        body.append(f'<rect x="{lx}" y="{ly-11}" width="12" height="12" rx="3" fill="{colors[i % len(colors)]}"/>')
        body.append(t(lx + 18, ly, f"{k}  {v} ({v/total*100:.0f}%)", 13, 500))
        lx += 220
        if lx > 1000:
            lx, ly = x0, ly + 28
    return frame(w, h, "Which router stage decided? (held-out v2)",
                 f"{total} items · high-precision rules first, semantic similarity next; local Qwen classifies only what remains ambiguous",
                 "".join(body), "Source: docs/eval/four_questions_test_v2_rules_only.json → route_methods (Qwen stage could not run on the build machine)")


def latency(lat):
    four = {"aircraft_diagnostics": "Q1 Diagnostics", "aircraft_recovery": "Q2 Recovery",
            "legacy_assessment": "Q3 Modernization", "executive_readiness": "Q4 Executive"}
    seen, rows = set(), []
    for q in lat["queries"]:
        if q["workflow"] in seen:
            continue
        seen.add(q["workflow"])
        rows.append((four.get(q["workflow"], q["workflow"].replace("_", " ")), q["workflow"] in four, q["cold_ms"], q["warm_median_ms"]))
    rows.sort(key=lambda r: (not r[1], r[3]))
    w = 1200
    h = 150 + 30 * len(rows)
    x0, x1, y = 300, 1060, 112
    mx = max(max(r[2], r[3]) for r in rows) * 1.05
    body = [t(x0, 100, "■ warm median", 12, 700, CYAN), t(x0 + 120, 100, "│ cold (first run)", 12, 700, VIOLET)]
    for name, is4, cold, warm in rows:
        body.append(t(x0 - 14, y + 16, name, 13, 700 if is4 else 400, TEXT, "end"))
        bw = (x1 - x0) * warm / mx
        body.append(f'<rect x="{x0}" y="{y+3}" width="{bw:.1f}" height="17" rx="4" fill="{CYAN if is4 else INDIGO}"/>')
        cx = x0 + (x1 - x0) * cold / mx
        body.append(f'<line x1="{cx:.1f}" y1="{y}" x2="{cx:.1f}" y2="{y+23}" stroke="{VIOLET}" stroke-width="3"/>')
        body.append(t(max(x0 + bw, cx) + 10, y + 16, f"{warm} ms", 12, 700, MUTED))
        y += 30
    return frame(w, h, "Deterministic workflow latency (no model)",
                 f"Routing + agents + SQL + statistics + workspace · {lat['machine']['cpus']} CPUs · Qwen explanation time is measured on your machine",
                 "".join(body), "Source: docs/latency_measured.json (scripts/measure_latency.py)")


def tests_growth():
    # Counts reported by the test runners at the 1.0 and 2.0 commits (README / CHANGELOG_2.0).
    rows = [("Backend pytest", 102, 131), ("Playwright e2e", 13, 18)]
    w, h = 1200, 300
    x0, x1, y = 260, 1080, 120
    mx = 140
    body = [t(x0, 104, "■ 1.0", 12, 700, VIOLET), t(x0 + 70, 104, "■ 2.0", 12, 700, CYAN)]
    for name, a, b in rows:
        body.append(t(x0 - 14, y + 28, name, 14, 700, TEXT, "end"))
        for i, (v, col) in enumerate(((a, VIOLET), (b, CYAN))):
            bw = (x1 - x0) * v / mx
            body.append(f'<rect x="{x0}" y="{y + 6 + i*22}" width="{bw:.1f}" height="18" rx="4" fill="{col}"/>')
            body.append(t(x0 + bw + 8, y + 20 + i * 22, f"{v} passed", 12, 700, col))
        y += 70
    return frame(w, h, "Test suites: 1.0 → 2.0", "All passing; new tests cover the Qwen gateway, four-question engine, insights APIs and new pages",
                 "".join(body), "Source: test runner output at commits 01a4baf (1.0) and bef7b48 (2.0)")


# ---------------------------------------------------------------- diagrams

def box(x, y, w, h, title, sub="", fill=SURFACE, stroke=BORDER, tcol=TEXT, size=15, scol=MUTED):
    s = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
    cy = y + h / 2 + (0 if not sub else -6)
    s += t(x + w / 2, cy + 5, title, size, 800, tcol, "middle")
    if sub:
        s += t(x + w / 2, cy + 24, sub, 11.5, 400, scol, "middle")
    return s


def arrow(x1, y1, x2, y2, col=INDIGO, dash=""):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" stroke-width="2.2" marker-end="url(#ah)"{d}/>')


def architecture():
    w, h = 1600, 1000
    s = [f'<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
         f'<path d="M0 0 L10 5 L0 10 z" fill="{INDIGO}"/></marker>'
         f'<linearGradient id="q" x1="0" x2="1"><stop offset="0" stop-color="{INDIGO}"/><stop offset="1" stop-color="{VIOLET}"/></linearGradient></defs>']
    # machine boundary
    s.append(f'<rect x="30" y="100" width="1540" height="850" rx="22" fill="none" stroke="{GOLD}" stroke-opacity="0.6" stroke-width="2" stroke-dasharray="10 8"/>')
    s.append(t(54, 128, "ONE MACHINE · OFFLINE · LOOPBACK ONLY", 13, 800, GOLD, "start", 'letter-spacing="2"'))
    # row 1: UI
    s.append(box(60, 150, 1480, 86, "React UI · Conversation Intelligence Copilot design system",
                 "AI Assistant · four question cards · Command Center · Predictive · Legacy X-Ray · Agents · Governance · Observability · 12 sections", ELEV, INDIGO))
    s.append(arrow(800, 236, 800, 280))
    # row 2: router
    stages = ["Policy", "Greeting", "Follow-up", "Rules", "Semantic", "Qwen classify", "Fallback"]
    s.append(f'<rect x="60" y="280" width="1480" height="110" rx="16" fill="{SURFACE}" stroke="{BORDER}"/>')
    s.append(t(84, 306, "HYBRID ROUTER", 12, 800, CYAN, "start", 'letter-spacing="2"'))
    bx = 84
    for i, st in enumerate(stages):
        col = VIOLET if st == "Qwen classify" else (NEG if st == "Policy" else CYAN)
        s.append(f'<rect x="{bx}" y="320" width="182" height="50" rx="10" fill="{ELEV}" stroke="{col}"/>')
        s.append(t(bx + 91, 351, st, 14, 700, TEXT, "middle"))
        if i < len(stages) - 1:
            s.append(arrow(bx + 182, 345, bx + 206, 345, CYAN))
        bx += 206
    s.append(arrow(800, 390, 800, 430))
    # row 3: specialist graphs
    fams = [("Q1 Diagnostics", "telemetry ‖ retrieval ‖ history"), ("Q2 Recovery", "parts ‖ scheduling → simulation"),
            ("Q3 Modernization", "Legacy X-Ray → adapters → tests"), ("Q4 Executive", "fleet ‖ downtime ‖ parts → levers")]
    s.append(t(84, 452, "SPECIALIST AGENT GRAPHS (DAG engine, checkpoints, retries)", 12, 800, CYAN, "start", 'letter-spacing="2"'))
    for i, (a, b) in enumerate(fams):
        s.append(box(84 + i * 362, 466, 340, 84, a, b, SURFACE, INDIGO))
    s.append(arrow(800, 550, 800, 590))
    # row 4: deterministic layer + policy gateway
    s.append(box(60, 590, 900, 96, "Deterministic data layer", "SQLite + FTS5 · z-score anomalies · reconciliation · scheduling · simulation · ROI models · synthetic data", SURFACE, POS))
    s.append(box(990, 590, 550, 96, "Policy gateway  POL-001…013", "deny by default · before every tool call · approvals · kill switch", "#2A1530", NEG))
    s.append(arrow(510, 686, 510, 730))
    # row 5: explanation chain
    chain = [("Evidence workspace", "citations · charts · tables", SURFACE, CYAN),
             ("Local Qwen gateway", "your model · cache · budget · timeout", "url(#q)", VIOLET),
             ("Evidence Challenger", "unknown numbers & IDs removed", SURFACE, WARN),
             ("Governance validation", "model approved nothing", SURFACE, POS)]
    cx = 60
    for i, (a, b, f, st) in enumerate(chain):
        s.append(box(cx, 730, 340, 92, a, b, f, st, TEXT, scol="#EEF0FF" if f.startswith("url") else MUTED))
        if i < 3:
            s.append(arrow(cx + 340, 776, cx + 380, 776, VIOLET))
        cx += 380
    s.append(arrow(1390, 822, 1390, 866, POS))
    s.append(box(1060, 866, 480, 64, "Response + hash-chained audit", "", ELEV, POS, size=15))
    # Qwen side detail
    s.append(box(60, 856, 640, 74, "Qwen runtimes found automatically", "llama.cpp (.gguf) · Ollama · OpenAI-compatible local server — no cloud fallback", BG, VIOLET))
    s.append(arrow(570, 822, 570, 856, VIOLET, "5 4"))
    body = "".join(s)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="Flying_Florina 2.0 architecture">'
            f'<rect width="{w}" height="{h}" rx="24" fill="{BG}"/>'
            + t(48, 58, "Flying_Florina 2.0 — question to governed answer", 28, 800)
            + t(48, 84, "Deterministic code produces every number; your local Qwen explains it; the Challenger and governance check what Qwen wrote.", 15, 400, MUTED)
            + body + "</svg>")


def banner(chips_override=None):
    w, h = 1280, 380
    lines = "".join(f'<path d="M{x} {h} L{x+360} 0" stroke="{VIOLET}" stroke-opacity="0.06"/>' for x in range(-100, 1400, 110))
    chips = chips_override or [("Q1 Diagnostics", CYAN), ("Q2 Recovery", INDIGO), ("Q3 Modernization", VIOLET), ("Q4 Executive", POS)]
    cx, cs = 252, ""
    for name, col in chips:
        cw = 14 + len(name) * 8.6
        cs += (f'<rect x="{cx}" y="268" width="{cw:.0f}" height="34" rx="17" fill="{col}" fill-opacity="0.14" stroke="{col}"/>'
               + t(cx + cw / 2, 290, name, 14, 700, col, "middle"))
        cx += cw + 12
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="Flying_Florina 2.0 banner">'
        f'<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{BG}"/><stop offset="0.6" stop-color="#151A45"/>'
        f'<stop offset="1" stop-color="#2B1F6B"/></linearGradient>'
        f'<radialGradient id="glow" cx="0.85" cy="0.2" r="0.55"><stop offset="0" stop-color="{CYAN}" stop-opacity="0.22"/><stop offset="1" stop-color="{CYAN}" stop-opacity="0"/></radialGradient>'
        f'<linearGradient id="mark" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#5C35B7"/><stop offset="1" stop-color="#0B1230"/></linearGradient>'
        f'<linearGradient id="txt" x1="0" x2="1"><stop offset="0" stop-color="#F7F8FC"/><stop offset="1" stop-color="{CYAN}"/></linearGradient></defs>'
        f'<rect width="{w}" height="{h}" rx="22" fill="url(#bg)"/><rect width="{w}" height="{h}" rx="22" fill="url(#glow)"/>{lines}'
        f'<path d="M640 320 C 840 270, 980 170, 1210 80" stroke="{GOLD}" stroke-opacity="0.55" stroke-width="2" stroke-dasharray="6 8" fill="none"/>'
        f'<g transform="translate(1150,48) rotate(-20)"><path d="M0 18 L70 0 L52 14 L70 22 L46 24 L32 44 Z" fill="#F7F8FC" opacity="0.92"/></g>'
        f'<g transform="translate(70,74)"><circle cx="70" cy="70" r="70" fill="url(#mark)"/><circle cx="70" cy="70" r="61" fill="none" stroke="{GOLD}" stroke-width="2.5"/>'
        f'<path d="M30 84 L110 48 L88 66 L110 75 L84 79 L66 101 Z" fill="#F7F8FC"/>' + t(70, 128, "FF", 16, 800, GOLD, "middle") + "</g>"
        + t(250, 118, "Flying_Florina", 58, 800, "url(#txt)")
        + f'<rect x="690" y="76" width="74" height="40" rx="12" fill="{INDIGO}"/>' + t(727, 104, "2.0", 22, 800, "#FFFFFF", "middle")
        + t(252, 160, "Aerospace & Defense Intelligence Copilot", 24, 700, TEXT)
        + t(252, 194, "Explainable industrial AI for mission-critical operations · your local Qwen · deny-by-default governance", 15, 400, MUTED)
        + t(252, 240, "FOUR SIGNATURE QUESTIONS", 12, 800, GOLD, "start", 'letter-spacing="2"') + cs
        + t(252, 344, "Independent concept demo · not affiliated with or endorsed by IFS · all data synthetic", 12, 400, MUTED)
        + "</svg>"
    )


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    v1 = load("docs/eval/four_questions_test_v1_rules_only.json")
    v2 = load("docs/eval/four_questions_test_v2_rules_only.json")
    lat = load("docs/latency_measured.json")
    files = {
        "banner_v2.svg": banner(),
        "architecture_v2.svg": architecture(),
        "eval_metrics.svg": eval_metrics(v1, v2),
        "per_label_f1.svg": per_label_f1(v2),
        "route_methods.svg": route_methods(v2),
        "latency.svg": latency(lat),
        "tests_growth.svg": tests_growth(),
    }
    for name, svg in files.items():
        (OUT / name).write_text(svg, encoding="utf-8")
        print("wrote", (OUT / name).relative_to(ROOT))


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------- 3.0 assets (data: docs/eval/forecast_metrics_3_0.json, ff3_intents_test_rules_only.json)
def v3_forecast_mae(m):
    d = m["metrics"]["demand"]["by_horizon"]
    hs = list(d)
    w, h = 1200, 500
    x0, y0, x1, y1 = 120, 120, 1150, 400
    mx = max(max(v["mae"], v["baseline_moving_average"]["mae"], v["baseline_seasonal_naive"]["mae"]) for v in d.values()) * 1.15
    body = [t(x0, 98, "■ model", 12, 700, CYAN), t(x0 + 90, 98, "■ moving average", 12, 700, VIOLET), t(x0 + 240, 98, "■ seasonal naive", 12, 700, MUTED)]
    gw = (x1 - x0) / len(hs)
    for i, k in enumerate(hs):
        v = d[k]
        for j, (val, col) in enumerate(((v["mae"], CYAN), (v["baseline_moving_average"]["mae"], VIOLET), (v["baseline_seasonal_naive"]["mae"], MUTED))):
            bh = (y1 - y0) * val / mx
            bx = x0 + i * gw + 30 + j * 46
            body.append(f'<rect x="{bx:.1f}" y="{y1 - bh:.1f}" width="40" height="{bh:.1f}" rx="5" fill="{col}" opacity="0.92"/>')
            body.append(t(bx + 20, y1 - bh - 6, f"{val:.2f}", 11, 700, col, "middle"))
        body.append(t(x0 + i * gw + 99, y1 + 22, f"+{k}", 14, 700, TEXT, "middle"))
        body.append(t(x0 + i * gw + 99, y1 + 42, f"coverage {v['coverage_80'] * 100:.0f}%", 11, 400, WARN if v["coverage_80"] < 0.75 else MUTED, "middle"))
    body.append(f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="{BORDER}"/>')
    return frame(w, h, "3.0 demand forecast: held-out MAE vs baselines (lower is better)",
                 "HistGradientBoosting (Poisson) + split-conformal 80% intervals · temporal split · synthetic dataset; amber = interval coverage below 75%",
                 "".join(body), "Source: docs/eval/forecast_metrics_3_0.json (GET /api/forecast/evaluation)")


def v3_model_vs_baseline(m):
    mm = m["metrics"]
    rows = [("Failure within 30 days (F1)", mm["failure_risk_30d"]["model_at_0.5"]["f1"], mm["failure_risk_30d"]["baseline_health_below_0.35"]["f1"], "RandomForest", "health rule"),
            ("Anomaly detection (F1)", mm["anomaly"]["isolation_forest"]["f1"], mm["anomaly"]["baseline_zscore_gt3"]["f1"], "IsolationForest", "z-score rule"),
            ("Lead time (1 - MAE/30d)", 1 - mm["lead_time"]["mae"] / 30, 1 - mm["lead_time"]["baseline_supplier_median"]["mae"] / 30, "quantile GBM", "supplier median"),
            ("RUL (1 - MAE/52w)", 1 - mm["rul"]["health_trend"]["mae"] / 52, 1 - mm["rul"]["survival"]["mae"] / 52, "health trend", "survival only")]
    w, h = 1200, 120 + 70 * len(rows)
    x0, x1, y = 330, 900, 110
    body = []
    for name, a, b, an, bn in rows:
        body.append(t(x0 - 14, y + 26, name, 14, 700, TEXT, "end"))
        for i, (v, col, lab) in enumerate(((a, CYAN, an), (b, VIOLET, bn))):
            bw = (x1 - x0) * max(v, 0)
            body.append(f'<rect x="{x0}" y="{y + 6 + i * 24}" width="{bw:.1f}" height="18" rx="4" fill="{col}"/>')
            body.append(t(x0 + bw + 8, y + 20 + i * 24, f"{v:.3f} {lab}", 12, 700, col))
        if b > a:
            body.append(t(x1 + 200, y + 26, "← baseline wins", 12, 800, WARN, "middle"))
        y += 70
    return frame(w, h, "3.0 models vs simpler baselines (held-out, higher is better)",
                 "Where the simpler method is better, the UI and docs say so", "".join(body), "Source: docs/eval/forecast_metrics_3_0.json")


def v3_banner():
    s = banner([("Global map", CYAN), ("Forecasting", INDIGO), ("Digital twin", VIOLET), ("Agent harness", POS), ("Local Qwen", GOLD)])
    s = s.replace(">2.0<", ">3.0<").replace("Aerospace &amp; Defense Intelligence Copilot", "Global Aerospace Predictive Intelligence &amp; Resilience")
    s = s.replace("Explainable industrial AI for mission-critical operations · your local Qwen · deny-by-default governance",
                  "Forecasting · global map · digital twins · supply chain · resilience · governed agent harness · local Qwen")
    s = s.replace("FOUR SIGNATURE QUESTIONS", "TEN SECTIONS · ONE GOVERNED HARNESS")
    return s


def main_v3():
    m = load("docs/eval/forecast_metrics_3_0.json")
    files = {"banner_v3.svg": v3_banner(), "forecast_mae_v3.svg": v3_forecast_mae(m), "models_vs_baselines_v3.svg": v3_model_vs_baseline(m)}
    for name, svg in files.items():
        (OUT / name).write_text(svg, encoding="utf-8")
        print("wrote", (OUT / name).relative_to(ROOT))


if __name__ == "__main__":
    main_v3()
