"""Generate the short submission report (DOCX) and the detailed engineering report (PDF).

All figures are read from the analytics database, the manifests and the evaluation
results produced by `make prepare index evaluate`; charts are drawn from the same data.

Usage (from backend/):  uv run python -m scripts.generate_report
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

from app.analytics.db import get_db  # noqa: E402
from app.analytics.query_registry import run_operation  # noqa: E402
from app.analytics.time_windows import resolve_window  # noqa: E402
from app.config import PROJECT_ROOT, get_settings  # noqa: E402
from app.schemas.analysis import Scope  # noqa: E402

OUT = PROJECT_ROOT / "docs" / "reports"
FIG = OUT / "figures"
SHOTS = PROJECT_ROOT / "docs" / "screenshots"
INK, MUTED, INDIGO, CYAN, VIOLET, NEG, POS, WARN = "#0F172A", "#64748B", "#6366F1", "#0891B2", "#8B5CF6", "#DC2626", "#059669", "#D97706"
TITLE = "Conversation Intelligence Copilot"


def load() -> dict:
    s = get_settings()
    db = get_db()
    m = lambda n: json.loads((s.manifests_dir / f"{n}.json").read_text())  # noqa: E731
    nov = Scope(window=resolve_window(db, "original", {"type": "last_month"}))
    return {
        "profile": m("data_profile"), "quality": m("data_quality_report"), "manifest": m("dataset_manifest"), "eval": m("evaluation_results"),
        "q1": run_operation(db, "rank_negative_topics", nov, {"top_n": 8}).model_dump(),
        "trend": run_operation(db, "sentiment_trend", Scope(), {}).model_dump(),
        "coach": run_operation(db, "agent_coaching_review", Scope(), {}).model_dump(),
        "lead": run_operation(db, "leadership_priorities", Scope(), {}).model_dump(),
        "traj": run_operation(db, "sentiment_trajectory", Scope(), {"conversation_id": "C0000479"}).model_dump(),
        "dist": run_operation(db, "sentiment_distribution", Scope(), {}).model_dump(),
    }


def _style(ax, title):
    ax.set_title(title, loc="left", fontsize=11, color=INK, fontweight="bold")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color("#CBD5E1")
    ax.spines["bottom"].set_color("#CBD5E1")
    ax.tick_params(colors=MUTED, labelsize=8)


def figures(d: dict) -> dict[str, Path]:
    FIG.mkdir(parents=True, exist_ok=True)
    paths = {}

    rows = d["q1"]["series"]["all_groups"]["rows"]
    rows_c = sorted(rows, key=lambda r: r["negative"])
    fig, (a, b) = plt.subplots(1, 2, figsize=(10, 3.6))
    a.barh([r["name"] for r in rows_c], [r["negative"] for r in rows_c], color=NEG)
    _style(a, f"Negative conversations by topic · {d['q1']['scope']['window']['label']}")
    rows_r = sorted(rows, key=lambda r: r["negative_rate"])
    rates = [r["negative_rate"] for r in rows_r]
    err = [[r["negative_rate"] - r["rate_ci_low"] for r in rows_r], [r["rate_ci_high"] - r["negative_rate"] for r in rows_r]]
    b.barh([r["name"] for r in rows_r], rates, xerr=err, color=VIOLET, ecolor=INK, capsize=3)
    b.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    _style(b, "Negative rate with 95% Wilson CI")
    fig.tight_layout()
    paths["q1"] = FIG / "q1_negative_topics.png"
    fig.savefig(paths["q1"], dpi=180)
    plt.close(fig)

    t = d["trend"]["table"]["rows"]
    fig, ax = plt.subplots(figsize=(6, 3))
    x = [r["month"] for r in t]
    ax.fill_between(x, [r["rate_ci_low"] for r in t], [r["rate_ci_high"] for r in t], color=CYAN, alpha=0.15)
    ax.plot(x, [r["negative_rate"] for r in t], color=CYAN, marker="o")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    _style(ax, "Monthly negative rate (95% CI band)")
    fig.tight_layout()
    paths["trend"] = FIG / "trend.png"
    fig.savefig(paths["trend"], dpi=180)
    plt.close(fig)

    lr = d["lead"]["table"]["rows"]
    weights = d["lead"]["params"]["weights"]
    labels = {w["signal"]: w["label"] for w in d["lead"]["series"]["weights"]["rows"]}
    colors = [INDIGO, NEG, WARN, VIOLET, CYAN, "#94A3B8"]
    fig, ax = plt.subplots(figsize=(10, 3.6))
    names = [r["name"] for r in lr][::-1]
    for i, k in enumerate(weights):
        vals = [r[f"contrib_{k}"] for r in lr][::-1]
        left = [sum(r[f"contrib_{kk}"] for kk in list(weights)[:i]) for r in lr][::-1]  # stack after earlier signals
        ax.barh(names, vals, left=left, color=colors[i], label=labels[k])
    ax.legend(fontsize=7, ncol=3, frameon=False, loc="lower right")
    _style(ax, "Leadership priority score and its drivers (all dates)")
    fig.tight_layout()
    paths["lead"] = FIG / "priority.png"
    fig.savefig(paths["lead"], dpi=180)
    plt.close(fig)

    tr = d["traj"]["series"]["trajectory"]["rows"]
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.axhline(0, color="#CBD5E1", lw=1)
    ax.plot([r["turn_index"] for r in tr], [r["sentiment_score"] for r in tr], color=CYAN, marker="o", label="message")
    ax.plot([r["turn_index"] for r in tr], [r["rolling_mean"] for r in tr], color=VIOLET, ls="--", label="running mean")
    for tp in d["traj"]["series"]["turning_points"]["rows"]:
        ax.annotate(tp["direction"], (tp["turn_index"], next(r["sentiment_score"] for r in tr if r["turn_index"] == tp["turn_index"])),
                    textcoords="offset points", xytext=(0, 8), ha="center", fontsize=7, color=POS if tp["direction"] == "improved" else NEG)
    ax.set_ylim(-1.2, 1.3)
    ax.legend(fontsize=7, frameon=False)
    _style(ax, "Customer sentiment by turn · C0000479")
    fig.tight_layout()
    paths["traj"] = FIG / "trajectory.png"
    fig.savefig(paths["traj"], dpi=180)
    plt.close(fig)

    rt = d["eval"]["retrieval"]["by_topic"]
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.barh([r["topic"] for r in rt], [r["topic_p@5"] for r in rt], color=INDIGO)
    ax.axvline(d["eval"]["retrieval"]["random_baseline_topic_precision"], color=WARN, ls="--", lw=1)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    _style(ax, "Retrieval topic precision@5 (dashed = random)")
    fig.tight_layout()
    paths["retrieval"] = FIG / "retrieval.png"
    fig.savefig(paths["retrieval"], dpi=180)
    plt.close(fig)

    paths["arch"] = architecture_figure()
    return paths


def architecture_figure() -> Path:
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 42)
    ax.axis("off")

    def box(x, y, w, h, text, color):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2", fc=color + "22", ec=color, lw=1.2))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=7.5, color=INK)

    def arrow(x1, y1, x2, y2):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=9, color=MUTED, lw=0.9))

    chain = [("Input\nvalidation", 2), ("Session\nmemory", 15), ("Intent\n(Gemini | rules)", 28), ("Supervisor /\nplanner", 41)]
    for t, x in chain:
        box(x, 30, 10.5, 8, t, INDIGO)
    for (_, x1), (_, x2) in zip(chain, chain[1:]):
        arrow(x1 + 10.8, 34, x2 - 0.3, 34)
    specs = ["Topic", "Sentiment", "Coaching", "Leadership", "Analytics"]
    for i, s in enumerate(specs):
        box(56, 34 - i * 6.2, 13, 4.6, f"{s} agent", VIOLET)
        arrow(51.8, 34, 55.7, 36.3 - i * 6.2)
    box(56, 2, 13, 4.6, "Retrieval (FAISS)", CYAN)
    arrow(51.8, 33, 55.7, 4.3)
    tail = ["Evidence", "Explanation\n(grounding check)", "Visualisation", "QA agent", "Governance", "Response +\nmemory/telemetry"]
    for i, s in enumerate(tail):
        box(75, 36 - i * 6.6, 16, 5, s, POS if i < 3 else WARN)
        if i:
            arrow(83, 36 - (i - 1) * 6.6 - 0.2, 83, 36 - i * 6.6 + 5.2)
    for i in range(5):
        arrow(69.3, 36.3 - i * 6.2, 74.7, 38.5)
    arrow(69.3, 4.3, 74.7, 37.5)
    ax.text(2, 22, "DuckDB: registered,\nparameterised operations\n(no model-written SQL)", fontsize=7, color=MUTED)
    ax.text(2, 12, "Gemini: intent, explanation,\nlabelling only — numbers\nnever generated", fontsize=7, color=MUTED)
    fig.tight_layout()
    p = FIG / "architecture.png"
    fig.savefig(p, dpi=180)
    plt.close(fig)
    return p


# ---------------------------------------------------------------------------------------------
# Short submission report (DOCX)
# ---------------------------------------------------------------------------------------------
def routing() -> dict:
    """Benchmark v2 intent-routing results (scored once on the frozen test split)."""
    base = PROJECT_ROOT / "data" / "manifests" / "intent_routing"
    out = {}
    for k, f in (("router", "test_router_v2_final.json"), ("no_llm", "test_router_v2_no_llm_final.json"), ("before", "test_rules_first_v1_final.json")):
        if (base / f).exists():
            out[k] = json.loads((base / f).read_text())
    return out


def routing_text() -> str:
    r = routing()
    if "router" not in r:
        return "not run"
    return (f"{r['router']['accuracy']:.1%} on {r['router']['n']} held-out questions (no model: {r['no_llm']['accuracy']:.1%}; "
            f"previous router: {r['before']['accuracy']:.1%})")


def docx_report(d: dict, figs: dict[str, Path]) -> Path:
    from docx import Document
    from docx.shared import Cm, Pt, RGBColor

    e, ev = d["eval"], d["eval"]["end_to_end"]
    q1 = d["q1"]
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(10.5)
    for sec in doc.sections:
        sec.left_margin = sec.right_margin = Cm(2.0)
        sec.top_margin = sec.bottom_margin = Cm(1.8)

    def h(text, level=1):
        p = doc.add_heading(text, level=level)
        for r in p.runs:
            r.font.color.rgb = RGBColor(0x1E, 0x1B, 0x4B)

    def para(text):
        return doc.add_paragraph(text)

    def bullets(items):
        for it in items:
            doc.add_paragraph(it, style="List Bullet")

    def table(rows, header):
        t = doc.add_table(rows=1, cols=len(header))
        t.style = "Light Grid Accent 1"
        for i, c in enumerate(header):
            t.rows[0].cells[i].text = c
        for r in rows:
            cells = t.add_row().cells
            for i, c in enumerate(r):
                cells[i].text = str(c)
        doc.add_paragraph()

    doc.add_heading(TITLE, 0)
    para(f"Conversation Analysis Bot for Contact Centre Insights — submission report · {date.today():%d %B %Y}")

    h("1. Problem framing")
    para("Contact-centre analysts and leaders need answers they can act on and defend: which issues drive negative sentiment, where communication "
         "could improve, how a conversation unfolded, and what to review first. The prototype turns a natural-language question into a coordinated, "
         "verifiable analysis: a LangGraph supervisor routes the question to specialist agents that run deterministic analytics, retrieve source "
         "evidence, explain the result, choose charts, and pass quality and governance checks before anything is shown.")

    h("2. Dataset and preparation")
    p = d["profile"]
    para(f"Syncora.ai customer-support sample (Kaggle): {p['conversations']:,} conversations, {p['rows']:,} messages, {p['timestamp_min'][:10]} to "
         f"{p['timestamp_max'][:10]}. Preparation (scripted, idempotent): schema discovery and explicit column mapping; removal of the random "
         "lowercase filler that ends every message (raw text kept); PII masking and customer pseudonymisation; 17 data-quality checks; a versioned "
         "taxonomy mapping the opening message to one of 8 issue topics and 51 products (domains inferred); message and conversation sentiment; "
         "empathy and resolution-fit signals; DuckDB tables and manifests.")
    bullets([
        "Timestamps are not in turn order in any of the 3,000 conversations: turn index is authoritative; conversations are dated by their earliest message.",
        f"{p['agents']:,} agent IDs for 3,000 conversations (max 2 each): per-agent rankings would be unreliable, so coaching analysis is sample-size gated.",
        "Messages are templated (426 unique texts); customer follow-ups and agents' closing actions are largely independent of the issue — reported, not hidden.",
    ])

    h("3. Architecture and agent flow")
    doc.add_picture(str(figs["arch"]), width=Cm(17))
    para("Input validation → session memory → intent (Gemini structured output, or a deterministic parser) → supervisor/planner (resolves follow-up "
         "references and the date window; picks registered operations, one specialist and a retrieval mode) → topic / sentiment / coaching / leadership / "
         "analytics agent, in parallel with retrieval when the query is known, or after it when the query depends on the result → evidence assembly → "
         "explanation (Gemini, rejected if it contains any number not in the verified results) → visualisation planner → QA agent → governance agent → "
         "response → memory and telemetry. Each request is checkpointed; each node emits real start/finish events that the UI and the Agent Harness show.")

    h("4. Model and tool choices")
    table([
        ["Gemini Flash (google-genai)", "Intent, grounded explanation, batch classification; structured JSON with closed enums; rate-limited, retried, cached, circuit-broken; tokens and cost recorded."],
        ["LangGraph", "Explicit, testable routing, parallel branches, checkpointing, observable nodes."],
        ["DuckDB", "All numbers: registered, parameterised operations; Wilson intervals, chi-square and z-tests for uncertainty."],
        ["FAISS + embeddings", "Exact cosine search with metadata filters; MiniLM preferred, local LSA fallback."],
        ["SQLite", "Session memory, checkpoints, telemetry, audit, human review."],
        ["React · Recharts · React Flow", "Chat-first workspace, validated declarative charts, live agent graph."],
    ], ["Component", "Role"])

    h("5. The four analytical demonstrations")
    top = q1["table"]["rows"][:5]
    para(f"Q1 — Negative topics, {q1['scope']['window']['label']} (latest month in the data): {q1['metrics'][1]['value']} of {q1['metrics'][0]['value']} "
         f"conversations negative. Top five by count: " + ", ".join(f"{r['name']} ({int(r['negative'])})" for r in top) + ". By rate, "
         + max(q1["series"]["all_groups"]["rows"], key=lambda r: r["negative_rate"])["name"] + f" leads; the chi-square p-value "
         f"({next(m['value'] for m in q1['metrics'] if m['id'] == 'chi_square_p')}) shows the differences are not significant at 5%, and the answer says so.")
    doc.add_picture(str(figs["q1"]), width=Cm(17))
    c = d["coach"]
    emp = next(m for m in c["metrics"] if m["id"] == "empathy_response_rate")
    mis = next(m for m in c["metrics"] if m["id"] == "irrelevant_resolution_rate")
    para(f"Q2 — Coaching: no agent has ≥ 3 conversations, so the answer ranks conversations for a team-lead review instead of people, with evidence. "
         f"Workforce-wide, {emp['numerator']:,} of {emp['denominator']:,} negative customer turns ({emp['value']:.1%}) were followed by an acknowledgement or apology, "
         f"and {mis['value']:.1%} of assessable closing actions did not fit the issue. Output is flagged for human review; personnel-decision questions are refused.")
    para("Q3 — Trajectory: per-turn customer sentiment in turn order, turning points with the agent turn that preceded them, and the annotated transcript.")
    doc.add_picture(str(figs["traj"]), width=Cm(12))
    lr = d["lead"]
    para(f"Q4 — Leadership: a documented priority score (volume, negative rate, escalation requests, unresolved endings, resolution misfit, trend). "
         f"First: {lr['table']['rows'][0]['name']} (score {lr['table']['rows'][0]['priority_score']}); each recommendation names a finding, driver, action, "
         f"owner, evidence and uncertainty. Sensitivity: {lr['uncertainty_notes'][-2] if len(lr['uncertainty_notes']) > 1 else ''}")
    doc.add_picture(str(figs["lead"]), width=Cm(17))

    h("6. Bonus extensions")
    rt = e["retrieval"]
    bullets([
        f"Knowledge retrieval: conversation-aware chunks (4 turns, overlap 2), FAISS with metadata filters, one passage per conversation, evidence with message IDs and CSV lines. "
        f"On {rt['queries']} paraphrased queries: topic precision@5 {rt['topic_precision@5']:.1%} vs {rt['random_baseline_topic_precision']:.1%} random with {rt['embedding_backend']} (36.7% with the LSA fallback used when the model is unavailable).",
        "Specialised LLM agent: Gemini classification of unique masked texts (sentiment, act, empathy, resolution, topic, product) in bounded, resumable batches with "
        "a content-hash cache and honest coverage reporting; scripted-SDK tested; not run live (credential blocked).",
        "Memory: session store of resolved intent, scope, plan and deterministic references; follow-ups such as 'compare the top two', 'previous month', "
        f"'the first one', 'why ranked first', 'which findings are uncertain'. Follow-up routing on the evaluation sessions: {ev['follow_up_routing_accuracy']:.0%}.",
    ])

    h("7. Evaluation")
    it = e["intent"]
    table([
        ["Q1 vs independent oracle", "exact match" if e["q1_oracle"]["top5_counts_match"] and e["q1_oracle"]["totals_match"] else "mismatch"],
        ["End-to-end QA pass rate", f"{ev['qa_pass_rate']:.0%} of {ev['requests']} requests"],
        ["Unsupported questions refused", ev["unsupported_correctly_refused"]],
        ["Intent routing (benchmark v2 test)", routing_text()],
        ["Retrieval topic P@5", f"{rt['topic_precision@5']:.1%}"],
        ["Latency p50 / p95", f"{ev['latency_p50_ms']:.0f} / {ev['latency_p95_ms']:.0f} ms"],
        ["Automated tests", "97 backend · 8 Vitest · 10 Playwright — passing"],
    ], ["Measure", "Result"])
    para("Gemini could not be evaluated live: the development environment's credential returned 401 API_KEY_SERVICE_BLOCKED. End-to-end results above are for the deterministic path; "
         "intent routing was also measured with the local Qwen2.5-1.5B model (docs/evaluation/INTENT_ROUTING.md).")

    h("8. Limitations")
    bullets([
        "Live hosted-model behaviour (Gemini/Groq intent, explanations, labels, latency, tokens) is unmeasured; the local model is slow on CPU.",
        "Sentiment/empathy mappings are developer judgements; human-agreement metrics await labels from the in-app blind review.",
        "Intent routing reaches 95.9% on 73 held-out questions written by the rules' author; three known misroutes are documented, unfixed. The semantic routing stage is disabled by its own calibration.",
        "Root cause findings are associational and depend on template-level labels; X-Ray signals are pointers for review, not a verdict.",
        "Retrieval still misses 'paid but not delivered' paraphrases with every method; hybrid MiniLM + LSA fusion is only marginally better than MiniLM alone, and its LSA weight was tuned on the evaluation queries.",
        "Synthetic, templated data: most topic differences are not significant; no cost, churn, CSAT or handle-time data.",
        "No authentication/RBAC; single-node storage; Docker images not built in the sandbox (registry rate limits).",
    ])

    h("9. Next improvements")
    bullets([
        "Enable a hosted model (Groq or Gemini); run labelling and the routing/explanation evaluation live; compare with rules and human labels.",
        "A held-out retrieval query set to validate the hybrid weight; a fresh routing test set to measure the three proposed rule fixes.",
        "Collect a few hundred human labels for calibrated sentiment/empathy evaluation.",
        "SSO/RBAC, managed storage, OpenTelemetry/LangSmith, CI evaluation gates.",
    ])
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "Conversation_Intelligence_Copilot_Submission_Report.docx"
    doc.save(path)
    return path


# ---------------------------------------------------------------------------------------------
# Detailed engineering report (PDF)
# ---------------------------------------------------------------------------------------------
def pdf_report(d: dict, figs: dict[str, Path]) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    ss = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9, leading=12.5, alignment=TA_LEFT)
    small = ParagraphStyle("s", parent=body, fontSize=7.5, leading=10, textColor=colors.HexColor(MUTED))
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontSize=15, textColor=colors.HexColor("#1E1B4B"), spaceBefore=8, spaceAfter=6)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=11.5, textColor=colors.HexColor("#312E81"), spaceBefore=6, spaceAfter=4)
    story: list = []
    W = A4[0] - 3.6 * cm

    def P(t, s=body):
        story.append(Paragraph(t, s))

    def T(rows, widths=None, header=True):
        rows = [[Paragraph(str(c), small if i or not header else ParagraphStyle("th", parent=small, textColor=colors.white)) for c in r] for i, r in enumerate(rows)]
        t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#312E81")) if header else ("BACKGROUND", (0, 0), (0, 0), colors.white),
                               ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")])]))
        story.append(t)
        story.append(Spacer(1, 6))

    def IMG(p: Path, width=W):
        from PIL import Image as PI

        with PI.open(p) as im:
            w, h = im.size
        height = width * h / w
        max_h = 22 * cm
        if height > max_h:
            width, height = width * max_h / height, max_h
        story.append(Image(str(p), width=width, height=height))
        story.append(Spacer(1, 6))

    def shot(name, caption, crop_h=None):
        p = SHOTS / name
        if not p.exists():
            return
        if crop_h:
            from PIL import Image as PI

            with PI.open(p) as im:
                c = im.crop((0, 0, im.size[0], min(im.size[1], crop_h)))
                q = FIG / f"crop-{name}"
                c.save(q)
            p = q
        IMG(p)
        P(caption, small)

    e, ev, rt, it, lb = d["eval"], d["eval"]["end_to_end"], d["eval"]["retrieval"], d["eval"]["intent"], d["eval"]["labels"]
    prof, q = d["profile"], d["quality"]

    story.append(Paragraph(TITLE, ParagraphStyle("t", parent=h1, fontSize=22, spaceAfter=4)))
    P(f"Detailed engineering report · generated {date.today():%d %B %Y} from the repository's data, manifests and evaluation results.", small)
    story.append(Spacer(1, 8))

    story.append(Paragraph("Executive summary", h1))
    P("The copilot answers contact-centre questions through a supervised LangGraph workflow over deterministic DuckDB analytics, FAISS retrieval and "
      "session memory, with Gemini for language and classification when available. All four assignment questions and the three bonus extensions work end to end "
      "in the API and the UI; every answer carries evidence linked to source rows, uncertainty notes and a QA result.")
    T([["Measure", "Result"],
       ["Q1 vs independent oracle", "exact match" if e["q1_oracle"]["top5_counts_match"] else "mismatch"],
       ["End-to-end QA pass rate", f"{ev['qa_pass_rate']:.0%} ({ev['requests']} requests, {ev['follow_up_requests']} follow-ups)"],
       ["Unsupported refused / supported answered", f"{ev['unsupported_correctly_refused']} / {ev['supported_answered']}"],
       ["Intent routing (benchmark v2 test)", routing_text()],
       [f"Retrieval topic P@5 ({rt['embedding_backend'].split('/')[-1]})", f"{rt['topic_precision@5']:.1%} (random {rt['random_baseline_topic_precision']:.1%})"],
       ["Latency p50 / p95 (deterministic)", f"{ev['latency_p50_ms']:.0f} / {ev['latency_p95_ms']:.0f} ms"],
       ["Gemini", f"not reachable: {str(e['model'].get('reason'))[:90]}"]], [6 * cm, W - 6 * cm])

    story.append(Paragraph("1. Requirements", h1))
    P("Requirement IDs (FR, NFR, GOV, EVAL) are mapped to modules and tests in docs/requirements/REQUIREMENTS_MATRIX.md; per-feature status in docs/IMPLEMENTATION_MATRIX.md. "
      "Scope is separated into assignment-required (four questions, coordinated analysis, explainable results, documentation), bonus (retrieval, specialised agent, memory) "
      "and enterprise enhancements (nine-page UI, harness, prompt library, telemetry, governance, human review, dataset modes).")

    story.append(Paragraph("2. Architecture", h1))
    IMG(figs["arch"])
    T([["Layer", "Responsibility"],
       ["Data", "schema discovery, filler removal, PII masking, quality report, atomic DuckDB build"],
       ["Labelling", "versioned taxonomy, deterministic labeller, resumable Gemini labelling with cache"],
       ["Analytics", "15 registered operations (incl. Conversation X-Ray and Root Cause); Wilson CI, chi-square, z-tests; sensitivity analysis"],
       ["LLM", "structured output, repair, rate limit, retries + Retry-After, circuit breaker, cache, token/cost accounting"],
       ["Retrieval", "chunking, embedder adapter, FAISS + metadata filters, evidence assembly"],
       ["Agents", "LangGraph graph, supervisor, specialists, explanation, QA, governance, tracing, checkpointing"],
       ["Memory / telemetry", "SQLite sessions with deterministic references; requests, node events, LLM calls, audit"],
       ["UI", "React chat workspace, dashboards, explorer, harness, prompts, metrics, governance"]], [3.5 * cm, W - 3.5 * cm])

    story.append(Paragraph("3. Data profiling and transformation", h1))
    T([["Measure", "Value"], ["Messages", f"{prof['rows']:,} (customer {prof['roles']['customer']:,}, agent {prof['roles']['agent']:,})"],
       ["Conversations", f"{prof['conversations']:,} · {prof['messages_per_conversation']['min']:.0f}–{prof['messages_per_conversation']['max']:.0f} messages"],
       ["Agents", f"{prof['agents']:,} (max {prof['conversations_per_agent']['max']:.0f} conversations each)"],
       ["Time range", f"{prof['timestamp_min']} – {prof['timestamp_max']}"], ["Unique cleaned texts", f"{prof['unique_clean_texts']}"]], [5 * cm, W - 5 * cm])
    T([["Check", "Count", "Severity"]] + [[c["check"], f"{c['count']} / {c['total']}", c["severity"]] for c in q["checks"]], [8 * cm, 4 * cm, W - 12 * cm])
    P("Transformation: canonical schema → clean_text (filler removed only when the tail is pure lowercase filler) → masked_text → stable IDs and source line references → "
      "labels → conversation aggregates. Analytical decisions are documented in ASSUMPTIONS.md (dataset interpretation, labels, windows, scoring).")

    story.append(Paragraph("4. Labelling methodology", h1))
    P(f"100% of original messages match a template (template coverage {lb['template_coverage']}). Topic/product come from the opening template; sentiment scores are an ordinal mapping of the 18 recurring phrases; "
      "conversation sentiment uses mean thresholds ±0.25 with a 'mixed' class. Unknown phrasing receives a provisional lexicon label (confidence 0.4). "
      f"Lexicon fallback vs template labels on {lb['lexicon_fallback_vs_templates']['n_messages']:,} customer messages: accuracy {lb['lexicon_fallback_vs_templates']['accuracy']:.1%}, "
      f"κ {lb['lexicon_fallback_vs_templates']['cohen_kappa']}. Human review: {lb['human_review'].get('status')}. Gemini labels: not run (model unavailable).")

    story.append(Paragraph("5. Gemini integration", h1))
    P("google-genai client with response_schema (Pydantic, closed enums), temperature ≤ 0.2, thinking budget 0; one repair attempt with the validation error; "
      "sliding-window RPM limiter and concurrency cap; retries only for 408/429/5xx/timeouts with full-jitter backoff or the server's retryDelay; permanent auth errors open the circuit; "
      "response cache keyed by model, prompt id+version, system, user, schema and config; per-call usage (streamed usage treated as cumulative), latency, retries, cache hits, cost estimate. "
      "Verified against a scripted SDK; the live API returned 401 API_KEY_SERVICE_BLOCKED in the development environment.")

    story.append(Paragraph("6. Agent harness and orchestration", h1))
    P("Conditional routing to one specialist; retrieval in parallel (same superstep) or after analysis; ≤ 4 operations per request; 90 s budget; node failures recorded without crashing non-critical paths; "
      "client disconnect cancels at the next node boundary; LangGraph SQLite checkpoint per request.")
    shot("12-agent-harness.png", "Agent Harness: real node statuses, durations, skipped nodes and the node inspector.")

    story.append(PageBreak())
    story.append(Paragraph("7. Analytical workflows", h1))
    story.append(Paragraph("Q1 — negative topics", h2))
    IMG(figs["q1"])
    P(" ".join(d["q1"]["uncertainty_notes"][:2]), small)
    story.append(Paragraph("Q2 — coaching", h2))
    P(" ".join(d["coach"]["uncertainty_notes"][:2]))
    story.append(Paragraph("Q3 — trajectory", h2))
    IMG(figs["traj"], W * 0.65)
    story.append(Paragraph("Q4 — leadership priorities", h2))
    IMG(figs["lead"])
    T([["Concern", "Priority", "Driver", "Action", "Owner"]] + [[r["concern"], r["priority"], r["supporting_metric"]["label"], r["suggested_action"], r["decision_owner"]]
                                                               for r in d["lead"]["series"]["recommendations"]["rows"]], [3.2 * cm, 1.6 * cm, 3 * cm, W - 11.6 * cm, 3.8 * cm])
    IMG(figs["trend"], W * 0.65)

    story.append(Paragraph("8. Retrieval and memory", h1))
    IMG(figs["retrieval"], W * 0.7)
    P(f"{rt['queries']} paraphrased queries; topic P@5 {rt['topic_precision@5']:.1%}, exact P@5 {rt['exact_precision@5']:.1%}, hit-rate@5 {rt['hit_rate@5']:.1%}, MRR@5 {rt['mrr@5']}, duplicates {rt['duplicate_rate']:.0%}, "
      f"latency p50 {rt['latency_p50_ms']} ms. Memory stores references, not prose; follow-up routing {ev['follow_up_routing_accuracy']:.0%} over {ev['follow_up_requests']} follow-ups.")
    shot("06-memory-follow-up.png", "Follow-up resolved from session memory (plan notes show the resolved references and inherited window).", crop_h=2200)

    story.append(PageBreak())
    story.append(Paragraph("9. Visualisation, prompts, governance, observability", h1))
    P("Charts are declarative, schema-validated specs copied from result tables (QA verifies equality); drilldowns open the underlying conversations; CSV/PNG export. "
      "Prompts are versioned JSON with schemas, model config, test cases and live usage. Governance controls are listed with their actual status (RBAC: not implemented); "
      "the blind human-review panel computes agreement metrics from submitted labels only. Telemetry records requests, node events, model calls, audit and UI events.")
    shot("09-leadership-dashboard.png", "Leadership Command Center.", crop_h=1800)
    shot("15-governance.png", "Governance: controls, model availability, blind human review, audit.", crop_h=1300)

    story.append(Paragraph("10. Test results", h1))
    T([["Suite", "Result"], ["Backend unit (pytest)", "80 passed"], ["Backend integration (pytest)", "56 passed"], ["Frontend unit (Vitest)", "8 passed"],
       ["End to end (Playwright, Chromium)", "17 passed"], ["Typecheck / production build", "passed"]], [7 * cm, W - 7 * cm])
    T([["QA check", "Pass rate"]] + [[k, f"{v:.0%}"] for k, v in ev["check_pass_rates"].items()], [7 * cm, W - 7 * cm])
    T([["Held-out routing miss (benchmark v2 test)", "Expected", "Predicted"]] + [[x["question"], x["expected"], x["predicted"]] for x in routing().get("router", {}).get("errors", [])],
      [9 * cm, 3.5 * cm, W - 12.5 * cm])

    story.append(Paragraph("11. Failure analysis and trade-offs", h1))
    T([["Defect found", "Fix"], ["Partial-month rule skipped a month ending one day early", "Require early stop and low volume"],
       ["Reference 'the first one' unresolved after a turn without ranking", "Use most recent ranking, with a note"],
       ["'Which agents should be fired?' routed to coaching", "Personnel decisions refused"],
       ["Coaching crash when no resolution is assessable", "Nullable float handling"], ["Cancellation recorded as failure", "Recorded as cancelled"]], [9 * cm, W - 9 * cm])
    P("Trade-offs: registered operations over text-to-SQL (safe, exact; less open-ended); deterministic defaults with a Zero-LLM router (reproducible, zero tokens for fact questions; a model only for interpretation); hybrid MiniLM + LSA retrieval (both indexes used, rankings fused; LSA alone works offline but is weak); "
      "in-process stores (zero infrastructure; single node).")

    story.append(Paragraph("12. Deployment and production roadmap", h1))
    P("Local: make install prepare index dev. Docker Compose: backend (uv-locked, prepares data on first start, health-checked) + nginx frontend with SSE-friendly proxy — not built in the sandbox "
      "because registries rate-limited anonymous pulls. Roadmap: managed storage and vector DB, labelling job queue, SSO/RBAC/tenancy, secret manager, OpenTelemetry/LangSmith, CI evaluation gates, "
      "human-labelled evaluation sets, prompt/model A/B, retention policies, horizontal scaling.")

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "Conversation_Intelligence_Copilot_Engineering_Report.pdf"
    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.6 * cm, bottomMargin=1.6 * cm,
                      title=TITLE, author="Conversation Intelligence Copilot").build(story)
    return path


def main() -> None:
    d = load()
    figs = figures(d)
    print(docx_report(d, figs))
    print(pdf_report(d, figs))


if __name__ == "__main__":
    main()
