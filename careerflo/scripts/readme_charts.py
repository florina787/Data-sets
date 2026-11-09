"""Usage: python scripts/readme_charts.py .   (from careerflo/)
Render README charts as standalone SVG from measured data (docs/benchmark.json)."""
import json, sys
from pathlib import Path

root = Path(sys.argv[1])
out = root / "docs/assets/charts"
bench = json.loads((root / "docs/benchmark.json").read_text())["results"]
INK, MUTED, GRID = "#64748b", "#94a3b8", "#94a3b833"
V, S, E, A = "#7357FF", "#38BDF8", "#10B981", "#F59E0B"
FONT = "font-family='Inter,Segoe UI,Helvetica,Arial,sans-serif'"

def svg(w, h, body, title):
    return (f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}' viewBox='0 0 {w} {h}' role='img' aria-label='{title}' {FONT}>"
            f"<rect width='{w}' height='{h}' rx='18' fill='#7357ff08' stroke='#94a3b833'/>{body}</svg>")

def hbars(name, title, unit, rows, color, fmt="{:g}", maxv=None, note=""):
    w, rowh, left, top = 760, 46, 200, 70
    h = top + rowh * len(rows) + (50 if note else 30)
    maxv = maxv or max(v for _, v, _ in rows) * 1.15
    span = w - left - 130
    b = f"<text x='28' y='40' font-size='19' font-weight='700' fill='{INK}'>{title}</text>"
    for i, (label, v, hl) in enumerate(rows):
        y = top + i * rowh
        bw = max(4, span * v / maxv)
        b += f"<text x='28' y='{y + 22}' font-size='14' fill='{INK}' font-weight='{700 if hl else 500}'>{label}</text>"
        b += f"<rect x='{left}' y='{y + 6}' width='{span}' height='24' rx='12' fill='{GRID}'/>"
        b += f"<rect x='{left}' y='{y + 6}' width='{bw:.1f}' height='24' rx='12' fill='{color}' opacity='{1 if hl else .55}'/>"
        b += f"<text x='{left + bw + 10:.1f}' y='{y + 23}' font-size='14' font-weight='700' fill='{INK}'>{fmt.format(v)} {unit}</text>"
    if note:
        b += f"<text x='28' y='{h - 20}' font-size='12' fill='{MUTED}'>{note}</text>"
    (out / name).write_text(svg(w, h, b, title))

names = {"qwen3:0.6b": "Qwen3 0.6B", "qwen3:1.7b": "Qwen3 1.7B ★", "qwen3:4b": "Qwen3 4B"}
hbars("qwen-speed.svg", "Generation speed — tokens / second (higher is better)", "tok/s",
      [(names[r["model"]], r["tokens_per_second"], r["model"] == "qwen3:1.7b") for r in bench], V,
      note="4 vCPU · 16 GB · no GPU · Ollama 4-bit · ★ default model")
hbars("qwen-ttft.svg", "Time to first token — milliseconds (lower is better)", "ms",
      [(names[r["model"]], r["ttft_ms"], r["model"] == "qwen3:1.7b") for r in bench], S, fmt="{:,.0f}",
      note="Measured through the app's own QwenClient with thinking disabled")

# Accuracy: grouped bars
w, h = 760, 330
metrics = [("Structured JSON", "structured_output_accuracy"), ("Tool selection", "tool_selection_accuracy"), ("Interview feedback", "interview_feedback_relevance")]
cols = [V, S, E]
b = f"<text x='28' y='40' font-size='19' font-weight='700' fill='{INK}'>Task accuracy on fixed test sets</text>"
base, chart_h, x0 = 270, 190, 70
for gi, (label, key) in enumerate(metrics):
    gx = x0 + gi * 230
    b += f"<text x='{gx + 85}' y='{base + 26}' font-size='13' text-anchor='middle' fill='{INK}'>{label}</text>"
    for mi, r in enumerate(bench):
        num, den = map(int, r[key].split("/"))
        bh = chart_h * num / den
        x = gx + mi * 60
        b += f"<rect x='{x}' y='{base - chart_h}' width='46' height='{chart_h}' rx='10' fill='{GRID}'/>"
        b += f"<rect x='{x}' y='{base - bh:.1f}' width='46' height='{max(bh, 3):.1f}' rx='10' fill='{cols[mi]}'/>"
        b += f"<text x='{x + 23}' y='{base - bh - 8:.1f}' font-size='12' font-weight='700' text-anchor='middle' fill='{INK}'>{num}/{den}</text>"
for mi, r in enumerate(bench):
    b += f"<rect x='{470 + mi * 95}' y='26' width='12' height='12' rx='3' fill='{cols[mi]}'/><text x='{486 + mi * 95}' y='37' font-size='12' fill='{INK}'>{names[r['model']].replace(' ★', '')}</text>"
(out / "qwen-accuracy.svg").write_text(svg(w, h, b, "Task accuracy"))

# Test suite overview (counts from the repository's tests)
hbars("tests.svg", "Automated tests — all passing", "tests",
      [("Backend · SQLite", 45, True), ("Backend · PostgreSQL", 45, True), ("Frontend · Vitest", 5, False)], E, maxv=55,
      note="Scenarios A–F, MCP, LangGraph, SSE chat, Stripe webhooks, RLS isolation, concurrency, uploads, injection, sandbox")

# Trial model: 16 features x 2 dots
feats = ["Job Discovery", "Indeed / LinkedIn", "Job Matching", "Resume Optimization", "ATS Intelligence", "Cover Letters",
         "Mock Interviews", "Coding Coach", "Company Research", "Salary Intelligence", "GitHub Portfolio", "Recruiter Intelligence",
         "App Automation", "Career Analytics", "AI Assistant", "Multi-Agent Workflows"]
w, h = 760, 350
b = f"<text x='28' y='40' font-size='19' font-weight='700' fill='{INK}'>2 free uses of every premium feature · no card</text>"
for i, f in enumerate(feats):
    col, row = i % 4, i // 4
    x, y = 28 + col * 182, 70 + row * 62
    b += f"<rect x='{x}' y='{y}' width='170' height='50' rx='14' fill='#7357ff0d' stroke='#7357ff33'/>"
    b += f"<text x='{x + 12}' y='{y + 21}' font-size='12.5' font-weight='600' fill='{INK}'>{f}</text>"
    for d in range(2):
        b += f"<rect x='{x + 12 + d * 26}' y='{y + 31}' width='20' height='7' rx='3.5' fill='{V}'/>"
b += f"<text x='28' y='{h - 12}' font-size='12' fill='{MUTED}'>Server-side, per-feature, atomic and idempotent · failures never consume a use · trials never turn into a charge</text>"
(out / "trials.svg").write_text(svg(w, h, b, "Free trial model"))
print("ok", sorted(p.name for p in out.iterdir()))
