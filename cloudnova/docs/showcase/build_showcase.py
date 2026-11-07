"""Builds docs/showcase/CloudNova_FDE_Engineering_Showcase.pptx from real screenshots and verified numbers.

Run from cloudnova/:  python docs/showcase/build_showcase.py
Every number on the slides is copied from a command output listed in docs/showcase/EVIDENCE.md.
"""
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[2]
MEDIA = ROOT / "docs" / "media"
OUT = ROOT / "docs" / "showcase" / "CloudNova_FDE_Engineering_Showcase.pptx"
NAVY, INK, GREY, GOLD, LINE, SOFT = (RGBColor(0x14, 0x1B, 0x3A), RGBColor(0x2A, 0x2F, 0x45), RGBColor(0x6B, 0x70, 0x8A),
                                      RGBColor(0xB8, 0x8A, 0x2E), RGBColor(0xD9, 0xDC, 0xE6), RGBColor(0xF6, 0xF7, 0xFA))
RED, GREEN = RGBColor(0xB4, 0x23, 0x2C), RGBColor(0x1F, 0x7A, 0x4D)
FONT, MONO = "Arial", "Courier New"

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]
W = 13.333


def _run(p, text, size=16, bold=False, color=INK, font=FONT, italic=False):
    r = p.add_run(); r.text = text; f = r.font
    f.size, f.bold, f.italic, f.name = Pt(size), bold, italic, font; f.color.rgb = color
    return r


def text(slide, x, y, w, h, lines, size=16, color=INK, font=FONT, bold=False, spacing=1.15, align=None):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)); tf = tb.text_frame; tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.02); tf.margin_top = tf.margin_bottom = Inches(0.02)
    for i, line in enumerate(lines if isinstance(lines, list) else [lines]):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph(); p.line_spacing = spacing
        if align: p.alignment = align
        if isinstance(line, tuple):  # (text, overrides)
            t, o = line; _run(p, t, o.get("size", size), o.get("bold", bold), o.get("color", color), o.get("font", font), o.get("italic", False))
        else:
            _run(p, line, size, bold, color, font)
        p.space_after = Pt(6)
    return tb


def bullets(slide, x, y, w, h, items, size=16):
    return text(slide, x, y, w, h, [f"•  {i}" if not isinstance(i, tuple) else (f"•  {i[0]}", i[1]) for i in items], size=size)


def header(slide, n, title, kicker=None):
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.6), Inches(0.55), Inches(0.08), Inches(0.62))
    bar.fill.solid(); bar.fill.fore_color.rgb = GOLD; bar.line.fill.background()
    if kicker:
        text(slide, 0.85, 0.42, 9, 0.3, kicker.upper(), size=11, color=GOLD, bold=True)
    text(slide, 0.85, 0.66 if kicker else 0.55, 11.6, 0.7, title, size=28, color=NAVY, bold=True)
    text(slide, W - 1.4, 7.0, 1, 0.3, f"{n} / 15", size=10, color=GREY, align=PP_ALIGN.RIGHT)
    text(slide, 0.6, 7.0, 8, 0.3, "CloudNova · FDE take-home · github.com/florina787/Data-sets (cloudnova/)", size=10, color=GREY)


def image(slide, name, x, y, w=None, h=None, border=True):
    p = MEDIA / name
    pic = slide.shapes.add_picture(str(p), Inches(x), Inches(y), Inches(w) if w else None, Inches(h) if h else None)
    if border:
        pic.line.color.rgb = LINE; pic.line.width = Pt(0.75)
    return pic


def box(slide, x, y, w, h, label, sub=None, fill=SOFT, stroke=LINE, size=13, color=NAVY):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    s.adjustments[0] = 0.12; s.fill.solid(); s.fill.fore_color.rgb = fill; s.line.color.rgb = stroke; s.line.width = Pt(1)
    tf = s.text_frame; tf.word_wrap = True; tf.margin_left = tf.margin_right = Inches(0.08)
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER; _run(p, label, size, True, color)
    if sub:
        q = tf.add_paragraph(); q.alignment = PP_ALIGN.CENTER; _run(q, sub, size - 3, False, GREY, MONO if "/" in sub or ".py" in sub else FONT)
    return s


def arrow(slide, x1, y1, x2, y2, color=GREY):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = color; c.line.width = Pt(1.5)
    c.line._get_or_add_ln().append(c.line._get_or_add_ln().makeelement("{http://schemas.openxmlformats.org/drawingml/2006/main}tailEnd", {"type": "triangle"}))
    return c


def table(slide, x, y, w, rows, col_w=None, size=12, header_fill=NAVY, row_h=0.36):
    t = slide.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w), Inches(row_h * len(rows))).table
    for j, cw in enumerate(col_w or []):
        t.columns[j].width = Inches(cw)
    for i, r in enumerate(rows):
        for j, v in enumerate(r):
            cell = t.cell(i, j); cell.text = ""; p = cell.text_frame.paragraphs[0]
            _run(p, str(v), size, i == 0, RGBColor(0xFF, 0xFF, 0xFF) if i == 0 else INK, MONO if (i > 0 and str(v).startswith(("$", "-$", "0 /", "1,421")) ) else FONT)
            cell.fill.solid(); cell.fill.fore_color.rgb = header_fill if i == 0 else (SOFT if i % 2 == 0 else RGBColor(0xFF, 0xFF, 0xFF))
            cell.margin_left = cell.margin_right = Inches(0.08); cell.margin_top = cell.margin_bottom = Inches(0.04)
    return t


def code(slide, x, y, w, h, lines, size=11):
    s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid(); s.fill.fore_color.rgb = RGBColor(0x14, 0x1B, 0x3A); s.line.fill.background()
    tf = s.text_frame; tf.word_wrap = True; tf.margin_left = tf.margin_right = Inches(0.15); tf.margin_top = Inches(0.1)
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph(); p.alignment = PP_ALIGN.LEFT
        _run(p, line, size, False, RGBColor(0xE6, 0xE9, 0xF5), MONO)
    return s


def note(slide, s):
    slide.notes_slide.notes_text_frame.text = s


# 1 ------------------------------------------------------------------ What I built
s = prs.slides.add_slide(BLANK)
text(s, 0.8, 0.9, 7.2, 0.4, "FORWARD DEPLOYED ENGINEERING · TAKE-HOME", size=12, color=GOLD, bold=True)
text(s, 0.8, 1.3, 6.3, 1.7, "CloudNova — My Forward Deployed Engineering Project", size=30, color=NAVY, bold=True, spacing=1.0)
text(s, 0.8, 3.15, 6.4, 2.6, [
    "CloudNova's finance lead handed me a messy invoice export and said: we want to ask questions about revenue in plain English and actually trust the answers.",
    "I wrote a spec, cleaned the data against it, loaded it into DuckDB, and built one query agent that shows the SQL behind every number. It runs locally with a small Qwen model, no API keys."], size=16)
text(s, 0.8, 6.2, 6.4, 0.4, "Florina · November 2026 · Track B (data pipeline + query agent)", size=12, color=GREY)
image(s, "command-center.png", 7.45, 1.0, w=5.3)
text(s, 7.45, 4.4, 5.3, 0.4, "The dashboard, running locally. Figures are from the provided synthetic dataset.", size=11, color=GREY)
note(s, "Keep it short. The point is: messy data in, answers you can audit out.")

# 2 ------------------------------------------------------------------ Customer problem
s = prs.slides.add_slide(BLANK); header(s, 2, "What the customer was struggling with", "the problem")
box(s, 0.8, 1.8, 2.6, 0.9, "Old billing tool"); box(s, 0.8, 2.95, 2.6, 0.9, "CRM"); box(s, 0.8, 4.1, 2.6, 0.9, "Hand-kept spreadsheet")
box(s, 4.3, 2.95, 2.8, 0.9, "One CSV export", "cloudnova_invoices.csv", fill=RGBColor(0xFF, 0xF7, 0xE6), stroke=GOLD)
for y in (2.25, 3.4, 4.55):
    arrow(s, 3.45, y, 4.25, 3.4)
bullets(s, 7.6, 1.7, 5.2, 3.4, ["5,125 rows that describe 5,000 invoices", "18 spellings of 3 plans, 25 of 5 statuses", "5 date formats, some ambiguous (05-01-2024)",
                                "Amounts like \"$4,900.00\" and \"1,200.00 EUR\"", "82 exact duplicate rows; 16 invoices where systems disagree on status"], size=15)
text(s, 0.8, 5.35, 11.8, 0.4, "The questions finance actually asked:", size=15, color=NAVY, bold=True)
text(s, 0.8, 5.75, 11.8, 1.1, ["Paid revenue in 2024? · Region with the highest average MRR? · How much did we refund? · Enterprise vs Starter churn? · Top 5 accounts, flag CSAT ≤ 2? · What's stuck in pending/failed?"], size=14, color=INK)

# 3 ------------------------------------------------------------------ Where I started
s = prs.slides.add_slide(BLANK); header(s, 3, "Where I started", "before any code")
text(s, 0.8, 1.6, 5.6, 0.4, "What the assignment asked for", size=16, color=NAVY, bold=True)
bullets(s, 0.8, 2.05, 5.6, 3.6, ["Write the spec first, then let AI build to it", "Show how I steered the AI (.claude/, CLAUDE.md)", "An eval harness — including a case I expect to fail",
                                 "Production instincts: errors, config, no secrets", "One command to run it", "A README a stakeholder can read in 3 minutes"], size=15)
text(s, 7.0, 1.6, 5.6, 0.4, "The first questions I asked the data", size=16, color=NAVY, bold=True)
bullets(s, 7.0, 2.05, 5.6, 3.8, ["Is 01/05/2024 January or May?", "When two systems disagree about an invoice, which one wins?", "Is account_id really \"the customer\"?",
                                 "Does \"revenue\" mean paid, or paid minus refunds?", "Do the amounts even match the price list?"], size=15)
text(s, 0.8, 5.95, 11.8, 0.8, "I answered these with small profiling scripts before writing a single rule. Most of the design came from these answers.", size=14, color=GREY)

# 4 ------------------------------------------------------------------ Why Track B
s = prs.slides.add_slide(BLANK); header(s, 4, "Why I chose Track B instead of RAG", "a scoping decision")
table(s, 0.8, 1.7, 11.7, [["", "RAG over the invoices", "Clean the data + governed SQL (Track B)"],
                          ["\"Paid revenue in 2024\"", "Retrieves some rows; the LLM adds numbers up", "One SUM over 1,000+ rows, exact to the cent"],
                          ["Duplicates & conflicts", "Retrieved twice, counted twice", "Removed once, by a written rule, with an audit trail"],
                          ["Business rules (paid only, refunds net)", "Hope the prompt is followed", "Encoded once in SQL metric definitions"],
                          ["Can finance check it?", "Hard — the answer is generated text", "Yes — every answer shows the SQL that ran"]],
      col_w=[3.0, 4.2, 4.5], size=13, row_h=0.55)
text(s, 0.8, 5.0, 11.7, 1.5, ["All six questions are aggregations: sums, averages, rankings. Retrieval returns rows, not totals.",
                              ("Trade-off: no free-text search. There is no free text in this dataset to search, so I accepted that.", {"color": GREY})], size=15)

# 5 ------------------------------------------------------------------ Understanding the data
s = prs.slides.add_slide(BLANK); header(s, 5, "Understanding the data", "evidence before rules")
image(s, "raw-vs-clean.png", 0.8, 1.55, w=6.6)
table(s, 7.7, 1.6, 5.0, [["Question", "What the data said"], ["NN/NN/YYYY order?", "1st part never > 12 in 1,320 rows → MM/DD"],
                         ["NN-NN-YYYY order?", "2nd part never > 12 → DD-MM"], ["43 duplicated invoice ids", "27 only differ by status spelling"],
                         ["Real conflicts", "16 (paid/pending 7, paid/void 5, paid/failed 2, paid/refunded 2)"]], col_w=[1.9, 3.1], size=11, row_h=0.6)
text(s, 7.7, 4.85, 5.0, 1.6, "Left: six real invoices, raw string → clean row. Rows where both date readings are valid (81 of them) are flagged, not guessed silently.", size=13, color=GREY)

# 6 ------------------------------------------------------------------ Pipeline
s = prs.slides.add_slide(BLANK); header(s, 6, "Building the data pipeline", "raw → cleaning → validation → DuckDB")
xs = [0.7, 3.25, 5.8, 8.35]
labels = [("Raw CSV", "5,125 rows, read as strings"), ("Source adapter", "app/sources/base.py"), ("Rules + cleaning", "app/pipeline/rules.py · clean.py"), ("Typed DuckDB", "app/pipeline/build.py")]
for x, (l, sub) in zip(xs, labels):
    box(s, x, 1.9, 2.25, 1.1, l, sub, size=14)
for x in xs[:-1]:
    arrow(s, x + 2.27, 2.45, x + 2.53, 2.45)
box(s, 10.9, 1.55, 1.9, 0.5, "invoices 5,000", size=11); box(s, 10.9, 2.15, 1.9, 0.5, "accounts 3,815", size=11)
box(s, 10.9, 2.75, 1.9, 0.5, "rejected_rows 125", size=11, fill=RGBColor(0xFF, 0xF7, 0xE6), stroke=GOLD); box(s, 10.9, 3.35, 1.9, 0.5, "dedup_conflicts 16", size=11, fill=RGBColor(0xFF, 0xF7, 0xE6), stroke=GOLD)
for y in (1.8, 2.4, 3.0, 3.6):
    arrow(s, 10.62, 2.45, 10.88, y)
text(s, 0.7, 3.5, 5.2, 0.4, "Cleaning order (data contract §3)", size=15, color=NAVY, bold=True)
bullets(s, 0.7, 3.9, 5.6, 2.6, ["Drop exact duplicates (82)", "Collapse synonym duplicates (27)", "Conflicts: refunded > paid > failed > void > pending (16)",
                                "Unknown plan/status → quarantined, never defaulted"], size=14)
text(s, 6.9, 4.35, 5.9, 0.4, "Validation", size=15, color=NAVY, bold=True)
bullets(s, 6.9, 4.75, 5.9, 2.0, ["Test: every raw row is in invoices OR rejected_rows", "Price-book check: 0 violations", "Build is skipped when the raw file's sha256 hasn't changed"], size=14)

# 7 ------------------------------------------------------------------ Local Qwen
s = prs.slides.add_slide(BLANK); header(s, 7, "Why I used a local Qwen model", "model choice")
bullets(s, 0.8, 1.7, 6.2, 4.2, ["No API keys, no per-query cost, invoice data never leaves the machine",
                                "Qwen2.5-Coder-3B (Q4 GGUF) — small enough for a 4-core CPU",
                                "Served through llama.cpp's OpenAI-compatible server. Ollama was my first choice, but its download was blocked in my container",
                                "One agent, deterministic routing first; the model is a fallback, not the source of numbers"], size=15)
table(s, 7.4, 1.8, 5.3, [["Measured on 4 CPU threads", ""], ["Short generation", "~0.5 s"], ["General chat answer", "4–16 s"], ["Text-to-SQL per question", "7–43 s"],
                         ["Approved-metric answer (no LLM)", "< 100 ms"]], col_w=[3.4, 1.9], size=13, row_h=0.5)
text(s, 7.4, 4.75, 5.3, 1.6, "If Qwen is down, the app still starts in \"deterministic mode\": all metric answers, data quality and evals work; chat returns a clear llm_unavailable error.", size=13, color=GREY)

# 8 ------------------------------------------------------------------ Where the model struggled
s = prs.slides.add_slide(BLANK); header(s, 8, "Where the model struggled", "Qwen writing all the SQL: 2 of 6 correct")
code(s, 0.8, 1.65, 6.0, 2.05, ["-- Q4 churn, Enterprise vs Starter (Qwen-only)", "SUM(CASE WHEN invoices.status = 'churned'", "    THEN 1 ELSE 0 END) AS churned_accounts", "...",
                               "-- 'churned' is not a status. Churn lives in", "-- accounts.churned. Also failed: ambiguous 'plan'."], size=11)
code(s, 0.8, 3.9, 6.0, 1.95, ["-- Q5 top 5 accounts (Qwen-only)", "SELECT account_id, SUM(amount_usd) ...", "FROM invoices WHERE status = 'paid'", "...",
                              "-- ignores refunds -> ACC-5211 and ACC-1196 swap"], size=11)
table(s, 7.2, 1.7, 5.5, [["Q", "Qwen-only result"], ["Q1 paid 2024", "correct"], ["Q2 avg MRR region", "SQL error: ambiguous \"region\""], ["Q3 refunds", "correct"],
                         ["Q4 churn", "invented status = 'churned'"], ["Q5 top 5", "wrong order, no error"], ["Q6 exposure", "unknown column — blocked by guard"]],
      col_w=[1.9, 3.6], size=12, row_h=0.47)
text(s, 7.2, 5.15, 5.5, 1.4, "The dangerous one is Q5: valid SQL, plausible answer, wrong. The SQL guard checks safety, not meaning.", size=14, color=RED)

# 9 ------------------------------------------------------------------ Hybrid
s = prs.slides.add_slide(BLANK); header(s, 9, "How I improved the design", "hybrid: approved metrics first, Qwen as fallback")
for i, (l, sub) in enumerate([("Question", ""), ("Semantic planner", "metric × dimension × filter"), ("SQL guard", "sqlglot allow-list"), ("DuckDB", "read-only"), ("Answer + SQL", "+ caveats")]):
    box(s, 0.7 + i * 2.5, 1.75, 2.1, 0.95, l, sub or None, size=13)
    if i:
        arrow(s, 0.7 + i * 2.5 - 0.38, 2.22, 0.7 + i * 2.5 - 0.02, 2.22)
box(s, 3.2, 3.05, 2.1, 0.8, "Qwen text-to-SQL", "only if no metric fits", fill=RGBColor(0xFF, 0xF7, 0xE6), stroke=GOLD, size=12)
arrow(s, 4.25, 2.72, 4.25, 3.03, GOLD); arrow(s, 5.32, 3.45, 5.75, 2.5, GOLD)
table(s, 0.8, 4.2, 6.2, [["Mode (same 6 questions)", "Correct", "Median", "Max"], ["Hybrid (default)", "6 / 6", "10 ms", "61 ms"], ["Qwen-only", "2 / 6", "20.6 s", "42.9 s"]],
      col_w=[2.9, 1.1, 1.1, 1.1], size=13, row_h=0.5)
text(s, 0.8, 5.85, 6.2, 0.9, "Measured 2026-11-07, temperature 0, correctness judged by an independent oracle. evals/results/mode_comparison.json", size=11, color=GREY)
image(s, "ai-evaluation.png", 7.35, 3.05, w=5.4)

# 10 ----------------------------------------------------------------- Financial problem
s = prs.slides.add_slide(BLANK); header(s, 10, "A financial problem I discovered", "the brief's own rule may be wrong")
text(s, 0.8, 1.6, 6.0, 0.4, "1. FX conversion", size=17, color=NAVY, bold=True)
text(s, 0.8, 2.0, 6.0, 1.2, "The brief says EUR→USD 1.08, GBP→USD 1.27. But every EUR/GBP amount already equals the USD price × the rate. Multiplying again counts FX twice.", size=14)
table(s, 0.8, 3.25, 6.0, [["Non-USD invoices (1,421)", "× rate (brief)", "÷ rate"], ["Match the USD price book", "0 / 1,421", "1,421 / 1,421"], ["Q1 paid revenue 2024", "$32,686,371.16", "$29,595,624.38"]],
      col_w=[2.4, 1.8, 1.8], size=12, row_h=0.5)
text(s, 7.2, 1.6, 5.6, 0.4, "2. Account identity", size=17, color=NAVY, bold=True)
text(s, 7.2, 2.0, 5.6, 1.2, "3,815 account ids but only 200 names. Every name spans several regions, plans and signup dates, so names are not a customer master.", size=14)
table(s, 7.2, 3.25, 5.5, [["Key", "Groups", "Inconsistent"], ["account_id", "3,815", "24.4%"], ["account_name", "200", "100%"]], col_w=[2.1, 1.6, 1.8], size=12, row_h=0.5)
text(s, 0.8, 5.2, 11.9, 1.4, ["Why I didn't let the AI decide: these are accounting policy, not data cleaning. The inverse FX rule moves 2024 revenue by $3.09M.",
                              ("That is the finance lead's decision. My job is to show the evidence and make the decision easy and auditable.", {"color": GREY})], size=15)

# 11 ----------------------------------------------------------------- Customer decisions
s = prs.slides.add_slide(BLANK); header(s, 11, "How I handled customer decisions", "versioned policy + approval")
image(s, "finance-decisions.png", 0.8, 1.55, w=6.2)
bullets(s, 7.3, 1.6, 5.5, 2.6, ["policies/financial_policy.yaml keeps the original rules (v1.0) and is never edited by the app",
                                "Decision records: docs/decisions/PDR-001 (FX), PDR-002 (identity)",
                                "Approval needs: name, finance_owner role, a rationale, the operator's PIN, and the hash of the impact report they saw",
                                "Approving only records. Applying is a separate rebuild."], size=13)
table(s, 7.3, 4.55, 5.5, [["Status", ""], ["Record / apply / revert / audit log", "implemented, 11 tests"], ["FX change", "recommended, NOT applied"],
                          ["Name-based identity", "blocked: needs CRM master data"], ["Real sign-in (SSO)", "not built — PIN is demo-grade"]], col_w=[3.0, 2.5], size=11, row_h=0.4)

# 12 ----------------------------------------------------------------- Enterprise systems
s = prs.slides.add_slide(BLANK); header(s, 12, "Thinking about existing enterprise systems", "adapters feed one contract")
for i, (l, st) in enumerate([("Finance CSV", "built"), ("Legacy billing", "simulated demo"), ("CRM (Salesforce)", "mapping only"), ("SaaS billing (Stripe)", "mapping only")]):
    box(s, 0.8, 1.6 + i * 0.85, 2.7, 0.7, l, st, fill=SOFT if st != "built" else RGBColor(0xEA, 0xF6, 0xEF), stroke=LINE if st != "built" else GREEN, size=12)
    arrow(s, 3.52, 1.95 + i * 0.85, 4.15, 2.9)
box(s, 4.2, 2.45, 2.2, 0.95, "Raw contract", "19 string columns + lineage", size=13)
arrow(s, 6.42, 2.92, 6.9, 2.92); box(s, 6.95, 2.45, 1.9, 0.95, "Same pipeline", "same rules", size=13)
image(s, "integrations.png", 9.1, 1.5, w=3.7)
text(s, 0.8, 5.1, 12.0, 0.4, "What the legacy-billing adapter actually did with its 12-row sample export:", size=15, color=NAVY, bold=True)
bullets(s, 0.8, 5.5, 12.0, 1.4, ["Trailer control total checked · 9 rows mapped · 3 rejected with reasons (unknown code ZZ, amount N/A, date 20241341)",
                                 "1 rejected by the ledger's own dedup rule · a planted 10× over-billing flagged · every row keeps source file, line and hash · read-only preview, ledger untouched"], size=13)

# 13 ----------------------------------------------------------------- UI
s = prs.slides.add_slide(BLANK); header(s, 13, "Building the user interface", "screens start from finance questions")
for (name, cap), (x, y) in zip([("reconciliation.png", "Where did 125 rows go? Dedup avoids a $2.12M overstatement of paid revenue."),
                                ("leakage.png", "What's at risk? Evidence and dollars at stake — never called 'lost'."),
                                ("simulator.png", "What if Pro costs $109? Clearly labelled hypothetical; ledger untouched."),
                                ("studio-replay.png", "How was this one invoice handled? Step-by-step replay with evidence.")],
                               [(0.8, 1.55), (6.95, 1.55), (0.8, 4.2), (6.95, 4.2)]):
    image(s, name, x, y, w=3.75)
    text(s, x + 3.9, y + 0.15, 1.95, 2.1, cap, size=12, color=INK)

# 14 ----------------------------------------------------------------- Testing & failures
s = prs.slides.add_slide(BLANK); header(s, 14, "Testing — and what went wrong along the way", "evidence")
table(s, 0.8, 1.6, 5.6, [["Check", "Result"], ["Unit tests (this branch)", "156 passed"], ["Unit tests (submission branch)", "114 passed"],
                         ["Evals, no LLM", "31 pass · 0 fail · 2 xfail · 3 skip"], ["Evals with local Qwen", "33 pass · 0 fail · 3 xfail"], ["Six stakeholder answers vs oracle", "6 / 6 to the cent"]],
      col_w=[3.0, 2.6], size=12, row_h=0.45)
text(s, 0.8, 4.5, 5.6, 2.2, ["The oracle (evals/oracle.py) re-implements the spec with the standard library and never imports the app, so it can disagree with it.",
                             ("Expected failures stay visible: FX inverse, name-based top 5, one Qwen SQL case.", {"color": GREY})], size=13)
text(s, 6.9, 1.6, 5.9, 0.4, "Mistakes I made and fixed", size=16, color=NAVY, bold=True)
bullets(s, 6.9, 2.0, 5.9, 4.7, ["\"accounts\" matched my count regex → Q5 answered with a count. Fixed with word boundaries.",
                                "\"support tickets\" silently answered as churn rate. Now unknown measures go to Qwen or 'clarify'.",
                                "A 24-question business battery found 8 phrasing gaps. Fixed with general rules, not per-question templates.",
                                "Journey approval buttons were wired after Nova finished talking — clicks were ignored. Found in a browser test.",
                                "My own README said ambiguous dates could change years. They can't; corrected after re-checking."], size=13)

# 15 ----------------------------------------------------------------- What I learned
s = prs.slides.add_slide(BLANK); header(s, 15, "What I learned", "reflection")
text(s, 0.8, 1.7, 11.8, 2.0, ("“I started by trying to understand the customer and their data. The model was only one part of the solution. The harder decisions involved financial definitions, system integration, validation, and making sure the customer could trust the results.”",
                              {"italic": True}), size=20, color=NAVY, spacing=1.2)
text(s, 0.8, 4.0, 5.6, 0.4, "What I'd do next", size=16, color=NAVY, bold=True)
bullets(s, 0.8, 4.4, 5.6, 2.4, ["Get the two policy decisions from CloudNova and update the expected answers in one reviewed commit",
                                "Let Qwen fill a structured query plan instead of free SQL", "Add support tickets, tenure and cohort metrics"], size=14)
text(s, 6.9, 4.0, 5.9, 0.4, "Still open / not built", size=16, color=NAVY, bold=True)
bullets(s, 6.9, 4.4, 5.9, 2.4, ["Real sign-in for approvals (PIN today)", "Live CRM / Stripe connectors (designed, not built)", "Churn prediction — the data has no churn dates"], size=14)

prs.save(OUT)
print("saved", OUT, len(prs.slides), "slides")
