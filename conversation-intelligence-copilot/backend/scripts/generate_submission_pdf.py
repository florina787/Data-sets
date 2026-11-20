"""Generate the personalised submission report (PDF): docs/reports/Florina_Conversation_Intelligence_Copilot_Report.pdf.

Written in the author's voice: what was built, what was deliberately not built, and how.
Figures are reused from docs/readme (charts, screenshots) and docs/article/img (flowcharts).
Run: uv run python -m scripts.generate_submission_pdf
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Frame, Image, KeepTogether, NextPageTemplate, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

from app.config import PROJECT_ROOT

OUT = PROJECT_ROOT / "docs" / "reports" / "Florina_Conversation_Intelligence_Copilot_Report.pdf"
README = PROJECT_ROOT / "docs" / "readme"
FLOWS = PROJECT_ROOT / "docs" / "article" / "img"
REPO = "https://github.com/florina787/Data-sets/tree/claude/happy-edison-gef7ay/conversation-intelligence-copilot"
AUTHOR = "Florina"

FONT_DIRS = [Path("/usr/share/fonts/truetype/crosextra"), Path("/usr/share/fonts/truetype/jetbrains-mono"), Path("/usr/share/fonts/truetype")]


def _font(name: str) -> str:
    for d in FONT_DIRS:
        hit = next(d.rglob(name), None) if d.exists() else None
        if hit:
            return str(hit)
    raise FileNotFoundError(name)


pdfmetrics.registerFont(TTFont("Body", _font("Carlito-Regular.ttf")))
pdfmetrics.registerFont(TTFont("Body-Bold", _font("Carlito-Bold.ttf")))
pdfmetrics.registerFont(TTFont("Body-Italic", _font("Carlito-Italic.ttf")))
pdfmetrics.registerFont(TTFont("Body-BoldItalic", _font("Carlito-BoldItalic.ttf")))
pdfmetrics.registerFont(TTFont("Mono", _font("JetBrainsMono-Regular.ttf")))
pdfmetrics.registerFont(TTFont("Mono-Bold", _font("JetBrainsMono-Bold.ttf")))
pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body-Italic", boldItalic="Body-BoldItalic")

INK = colors.HexColor("#15212b")
INK2 = colors.HexColor("#44525e")
INK3 = colors.HexColor("#6b7781")
RULE = colors.HexColor("#d5dad3")
ACCENT = colors.HexColor("#0d6b74")
ACCENT_SOFT = colors.HexColor("#e6f2f3")
PAPER2 = colors.HexColor("#f3f5f1")
WARN_SOFT = colors.HexColor("#fbeee7")
WARN = colors.HexColor("#b4441c")
GOOD = colors.HexColor("#1a7a4c")

PAGE_W, PAGE_H = A4
MARGIN_X = 20 * mm
FRAME_W = PAGE_W - 2 * MARGIN_X

S = {
    "body": ParagraphStyle("body", fontName="Body", fontSize=10.5, leading=15, textColor=INK, spaceAfter=7, alignment=TA_LEFT),
    "lead": ParagraphStyle("lead", fontName="Body", fontSize=12.5, leading=18, textColor=INK2, spaceAfter=10),
    "h1": ParagraphStyle("h1", fontName="Body-Bold", fontSize=21, leading=25, textColor=INK, spaceBefore=4, spaceAfter=4),
    "kicker": ParagraphStyle("kicker", fontName="Mono-Bold", fontSize=7.5, leading=10, textColor=ACCENT, spaceAfter=2),
    "h2": ParagraphStyle("h2", fontName="Body-Bold", fontSize=13.5, leading=17, textColor=INK, spaceBefore=12, spaceAfter=5, keepWithNext=1),
    "h3": ParagraphStyle("h3", fontName="Body-Bold", fontSize=11, leading=14, textColor=ACCENT, spaceBefore=8, spaceAfter=3, keepWithNext=1),
    "bullet": ParagraphStyle("bullet", fontName="Body", fontSize=10.5, leading=14.5, textColor=INK, leftIndent=12, bulletIndent=2, spaceAfter=3),
    "small": ParagraphStyle("small", fontName="Body", fontSize=8.8, leading=12, textColor=INK3, spaceAfter=4),
    "cap": ParagraphStyle("cap", fontName="Body-Italic", fontSize=8.8, leading=12, textColor=INK3, spaceBefore=3, spaceAfter=10),
    "cell": ParagraphStyle("cell", fontName="Body", fontSize=9.3, leading=12.2, textColor=INK),
    "cellb": ParagraphStyle("cellb", fontName="Body-Bold", fontSize=9.3, leading=12.2, textColor=INK),
    "th": ParagraphStyle("th", fontName="Mono-Bold", fontSize=7.2, leading=9.5, textColor=INK3),
    "code": ParagraphStyle("code", fontName="Mono", fontSize=8.2, leading=11.5, textColor=INK, backColor=PAPER2, borderPadding=(6, 8, 6, 8),
                           spaceBefore=4, spaceAfter=10, leftIndent=8, rightIndent=8),
    "callt": ParagraphStyle("callt", fontName="Mono-Bold", fontSize=7.5, leading=10, textColor=ACCENT, spaceAfter=3),
    "callb": ParagraphStyle("callb", fontName="Body-Italic", fontSize=10.3, leading=14.5, textColor=INK),
    "toc1": ParagraphStyle("toc1", fontName="Body", fontSize=11, leading=19, textColor=INK, leftIndent=0),
    "statn": ParagraphStyle("statn", fontName="Body-Bold", fontSize=20, leading=23, textColor=INK),
    "statl": ParagraphStyle("statl", fontName="Body", fontSize=8.5, leading=11, textColor=INK3),
}


def P(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, S[style])


def bullets(items: list[str]) -> list[Paragraph]:
    return [Paragraph(t, S["bullet"], bulletText="•") for t in items]


def h1(kicker: str, title: str) -> list:
    p = Paragraph(title, S["h1"])
    p._toc = f"{kicker}  ·  {title}" if "·" not in kicker else f"{kicker.split('·', 1)[1].strip()}  ·  {title}"  # contents entry
    p._toc_num = kicker.split("·")[0].strip() if "·" in kicker else ""
    return [Spacer(1, 14), KeepTogether([P(kicker.upper(), "kicker"), p, Spacer(1, 2)])]


def thinking(text: str, label: str = "My thinking") -> Table:
    t = Table([[P(label.upper(), "callt")], [P(text, "callb")]], colWidths=[FRAME_W])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), ACCENT_SOFT), ("LINEBEFORE", (0, 0), (0, -1), 2.5, ACCENT),
                           ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                           ("TOPPADDING", (0, 0), (-1, 0), 8), ("BOTTOMPADDING", (0, -1), (-1, -1), 9), ("TOPPADDING", (0, 1), (-1, 1), 0)]))
    return KeepTogether([Spacer(1, 3), t, Spacer(1, 8)])


def table(rows: list[list], widths: list[float], header: bool = True, zebra: bool = True, bold_first: bool = False) -> Table:
    data = []
    for i, r in enumerate(rows):
        if header and i == 0:
            data.append([P(str(c).upper(), "th") for c in r])
        else:
            data.append([c if not isinstance(c, str) else P(c, "cellb" if (bold_first and j == 0) else "cell") for j, c in enumerate(r)])
    t = Table(data, colWidths=[w * FRAME_W for w in widths], repeatRows=1 if header else 0)
    st = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE), ("TOPPADDING", (0, 0), (-1, -1), 5),
          ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6)]
    if header:
        st += [("LINEBELOW", (0, 0), (-1, 0), 0.9, INK2)]
    if zebra:
        st += [("BACKGROUND", (0, i), (-1, i), PAPER2) for i in range(2 if header else 1, len(data), 2)]
    t.setStyle(TableStyle(st))
    return KeepTogether([t]) if len(data) <= 9 else t


def figure(path: Path, caption: str, width: float = 1.0, max_h: float = 120 * mm) -> KeepTogether:
    w, h = PILImage.open(path).size
    dw = FRAME_W * width
    dh = dw * h / w
    if dh > max_h:
        dh, dw = max_h, max_h * w / h
    img = Image(str(path), width=dw, height=dh)
    img.hAlign = "CENTER"
    return KeepTogether([Spacer(1, 4), img, P(caption, "cap")])


def two_figures(a: Path, b: Path, ca: str, cb: str) -> Table:
    cw = (FRAME_W - 8) / 2
    cells = []
    for p, c in ((a, ca), (b, cb)):
        w, h = PILImage.open(p).size
        cells.append([Image(str(p), width=cw, height=cw * h / w), P(c, "cap")])
    t = Table([[cells[0], cells[1]]], colWidths=[cw + 4, cw + 4])
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
    return t


def stats(items: list[tuple[str, str]]) -> Table:
    cells = [[P(n, "statn"), P(label, "statl")] for n, label in items]
    t = Table([cells], colWidths=[FRAME_W / len(items)] * len(items))
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, RULE), ("INNERGRID", (0, 0), (-1, -1), 0.6, RULE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9), ("LEFTPADDING", (0, 0), (-1, -1), 10)]))
    return t


class Doc(BaseDocTemplate):
    def __init__(self, path: str):
        super().__init__(path, pagesize=A4, leftMargin=MARGIN_X, rightMargin=MARGIN_X, topMargin=22 * mm, bottomMargin=20 * mm,
                         title="Conversation Intelligence Copilot: submission report", author=AUTHOR,
                         subject="Conversation Analysis Bot for Contact Centre Insights")
        cover = Frame(MARGIN_X, 20 * mm, FRAME_W, PAGE_H - 40 * mm, id="cover", showBoundary=0)
        body = Frame(MARGIN_X, 20 * mm, FRAME_W, PAGE_H - 42 * mm, id="body", showBoundary=0)
        self.addPageTemplates([PageTemplate("cover", [cover], onPage=self._cover), PageTemplate("body", [body], onPage=self._page)])

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and getattr(flowable, "_toc", None):
            num = flowable._toc_num
            self.notify("TOCEntry", (0, (f"{num}.  " if num else "") + flowable._toc, self.page))

    @staticmethod
    def _cover(c, doc):
        c.saveState()
        c.setFillColor(INK)
        c.rect(0, PAGE_H - 118 * mm, PAGE_W, 118 * mm, stroke=0, fill=1)
        c.setFillColor(ACCENT)
        c.rect(0, PAGE_H - 120 * mm, PAGE_W, 2 * mm, stroke=0, fill=1)
        # motif: the six-stage pipeline as quiet dots and connectors
        c.setStrokeColor(colors.HexColor("#3a4b58"))
        c.setLineWidth(1)
        xs = [MARGIN_X + 8 + i * 27 * mm for i in range(6)]
        y = PAGE_H - 30 * mm
        for i, x in enumerate(xs):
            c.setFillColor(colors.HexColor("#4fb8c2") if i in (0, 5) else colors.HexColor("#2b3a45"))
            c.circle(x, y, 3.2, stroke=0, fill=1)
            if i:
                c.line(xs[i - 1] + 5, y, x - 5, y)
        c.setFillColor(colors.HexColor("#9fc9cd"))
        c.setFont("Mono-Bold", 8)
        c.drawString(MARGIN_X, PAGE_H - 46 * mm, "TAKE-HOME SUBMISSION  ·  CONVERSATION ANALYSIS BOT FOR CONTACT CENTRE INSIGHTS")
        c.setFillColor(colors.white)
        c.setFont("Body-Bold", 34)
        c.drawString(MARGIN_X, PAGE_H - 64 * mm, "Conversation Intelligence")
        c.setFillColor(colors.HexColor("#4fb8c2"))
        c.drawString(MARGIN_X, PAGE_H - 78 * mm, "Copilot")
        c.setFillColor(colors.HexColor("#c9d3da"))
        c.setFont("Body", 13)
        c.drawString(MARGIN_X, PAGE_H - 92 * mm, "How I designed, built and evaluated an evidence-first analytics agent")
        c.drawString(MARGIN_X, PAGE_H - 99 * mm, "for 3,000 customer-support conversations, with the language model optional.")
        c.setFont("Body", 10)
        c.setFillColor(INK2)
        c.drawString(MARGIN_X, 30 * mm, f"Prepared by {AUTHOR}  ·  October 2026")
        c.setFont("Mono", 8)
        c.setFillColor(ACCENT)
        c.drawString(MARGIN_X, 24 * mm, REPO)
        c.linkURL(REPO, (MARGIN_X, 22 * mm, MARGIN_X + 150 * mm, 28 * mm))
        c.restoreState()

    @staticmethod
    def _page(c, doc):
        c.saveState()
        c.setStrokeColor(RULE)
        c.setLineWidth(0.5)
        c.line(MARGIN_X, PAGE_H - 14 * mm, PAGE_W - MARGIN_X, PAGE_H - 14 * mm)
        c.setFont("Mono", 7)
        c.setFillColor(INK3)
        c.drawString(MARGIN_X, PAGE_H - 12 * mm, "CONVERSATION INTELLIGENCE COPILOT")
        c.drawRightString(PAGE_W - MARGIN_X, PAGE_H - 12 * mm, f"{AUTHOR.upper()}  ·  SUBMISSION REPORT")
        c.line(MARGIN_X, 13 * mm, PAGE_W - MARGIN_X, 13 * mm)
        c.drawString(MARGIN_X, 9 * mm, "Numbers in this report are computed by registered DuckDB operations or measured by the evaluation scripts.")
        c.setFont("Mono-Bold", 8)
        c.setFillColor(INK)
        c.drawRightString(PAGE_W - MARGIN_X, 9 * mm, str(doc.page))
        c.restoreState()


def story() -> list:
    st: list = []

    # Cover: content sits below the dark band
    st += [Spacer(1, 108 * mm),
           stats([("4 / 4", "assignment questions answered and independently re-computed"),
                  ("95.9%", "intent routing on 73 held-out questions (from 61.6%)"),
                  ("125 ms", "median answer time on the deterministic path"),
                  ("$0", "to run: no API key; the optional model is local")]),
           Spacer(1, 10),
           P("This report covers the problem framing, dataset handling, system design, agent flow, model and tool choices, "
             "the three bonus extensions, evaluation, limitations and next improvements, as the brief requests. It is written "
             "in the first person because most of what matters here is judgement: what I chose to build, what I chose "
             "<i>not</i> to build, and why.", "lead"),
           P("Implementation repository: <font face='Mono'>github.com/florina787/Data-sets</font> (folder "
             "<font face='Mono'>conversation-intelligence-copilot</font>, branch <font face='Mono'>claude/happy-edison-gef7ay</font>). "
             "A ZIP can be built from it with <font face='Mono'>make package</font>. The next pages map every item in §6 of the brief "
             "to where it is answered.", "body"),
           NextPageTemplate("body"), PageBreak()]

    # Contents
    toc = TableOfContents()
    toc.levelStyles = [S["toc1"]]
    toc.dotsMinLevel = 0
    st += [P("CONTENTS", "kicker"), Paragraph("What is in this report", S["h1"]), Spacer(1, 6), toc, PageBreak()]

    # Submission checklist (brief §6)
    st += h1("Submission checklist", "How this submission meets §6 of the brief")
    st += [P("The brief asks for a short report and the implementation repository. This page maps each requirement to where it is "
             "answered, so nothing has to be searched for.", "body"),
           P("The report covers", "h3"),
           table([["Required topic", "Where in this report"],
                  ["Problem framing", "§1 Problem framing"],
                  ["Dataset handling", "§2 Dataset handling: preparation steps, assumptions, derived fields, labels, aggregations"],
                  ["System design", "§3 System design: components, contracts, schemas and data passed between agents"],
                  ["Agent flow", "§4 Agent flow: the four-stage graph, one request end to end, routing, failure handling"],
                  ["Model and tool choices", "§5 Model and tool choices: alternatives, dependencies, API keys, cost assumptions, and why a local model instead of a hosted API"],
                  ["Evaluation: representative successes and failures", "§9 Evaluation: Representative successes; Representative failures"],
                  ["Evaluation: task-specific metrics", "§9 Evaluation: Task-specific metrics"],
                  ["Evaluation: grounding quality", "§9 Evaluation: Grounding quality"],
                  ["Evaluation: latency or consistency", "§9 Evaluation: Latency and consistency"],
                  ["Limitations", "§11 Limitations"],
                  ["Next improvements", "§12 Next improvements"]],
                 [0.42, 0.58], bold_first=True),
           P("The repository includes", "h3"),
           table([["Required item", "Where in the repository"],
                  ["Source code and clear setup/run instructions", "<font face='Mono'>backend/</font>, <font face='Mono'>frontend/</font>; README · Quick start (<font face='Mono'>make install / prepare / index / dev</font>), IDE setup, Docker"],
                  ["Sample requests and outputs", "<font face='Mono'>examples/requests/</font> (6 requests) and <font face='Mono'>examples/outputs/</font> (JSON + readable Markdown), generated from real runs"],
                  ["Instructions for obtaining or preparing the dataset", "Supplied file committed at <font face='Mono'>data/raw/cs_conversations.csv.zip</font>; <font face='Mono'>make prepare</font>; <font face='Mono'>docs/dataset/DATASET.md</font>"],
                  ["Environment-variable requirements and external-service notes", "<font face='Mono'>.env.example</font>; README · Configuration and Models, dependencies and cost. No API key or external service is required."]],
                 [0.36, 0.64], bold_first=True),
           P("Details for each repository item are in §13.", "small")]

    # 0. Summary
    st += h1("Summary", "What I built, in one page")
    st += [P("Contact-centre leaders make decisions from conversation analytics. If a number in that analysis is wrong, people act on it "
             "anyway. So my first design decision came before any code: <b>numbers are computed, never generated.</b> Every count, rate "
             "and rank in an answer comes from a registered, parameterised DuckDB operation. A language model may help interpret a "
             "question or phrase an explanation, but it never produces a figure and never writes SQL.", "body"),
           P("On top of that rule I built an analyst-facing copilot: a React workspace and a FastAPI service around a LangGraph workflow "
             "of specialised agents. An analyst asks a question in plain language. The workflow then:", "body")]
    st += bullets(["decides whether a model is needed at all (a <b>Zero-LLM router</b>);",
                   "plans which registered operations answer the question;",
                   "computes the result and retrieves the source transcripts that illustrate it (hybrid FAISS search);",
                   "explains the result, choosing charts that fit its shape;",
                   "audits the answer with a QA agent and an <b>Evidence Challenger</b> before it is shown."])
    st += [P("The answer carries counts and rankings, charts, cited conversations with message IDs, uncertainty notes, and a replay of "
             "every step. All four example questions in the brief are answered with zero model calls.", "body"),
           Spacer(1, 4),
           table([["What I did", "What I deliberately did not do", "How"],
                  ["Answered all four questions end to end, each independently re-computed from the raw CSV",
                   "Rank individual agents for coaching: no agent has more than two conversations",
                   "A typed agent state, a registry of 15 DuckDB operations, one versioned result schema"],
                  ["Built all three bonus extensions: hybrid retrieval, a local LLM intent agent, session memory",
                   "Let a model write SQL, produce numbers, or claim causes",
                   "Numeric grounding check on every explanation; an adversarial Evidence Challenger"],
                  ["Measured everything: routing on a frozen held-out split, retrieval, QA, latency, 163 automated tests",
                   "Tune on the test split, or report the flattering retrieval number after the data changed",
                   "Benchmarks written before changes, frozen by SHA-256, scored once"],
                  ["Made it run with no API key and no cost", "Depend on a hosted model, or append new data",
                   "A local Qwen2.5-1.5B model on CPU, used only when the rules are unsure"]],
                 [0.36, 0.32, 0.32], bold_first=False),
           ]

    # 1. Problem framing
    st += h1("1 · Problem framing", "Reading the brief as an analyst would")
    st += [P("The brief asks for a prototype that helps analysts <i>make better decisions</i>, and for answers that are clear and "
             "evidence-based. I read that as three requirements, in this order of importance:", "body")]
    st += bullets(["<b>Correct.</b> A plausible wrong answer is the worst outcome for a decision-support tool, because it is trusted.",
                   "<b>Checkable.</b> An analyst must be able to see where a number came from and read the conversations behind it.",
                   "<b>Honest about uncertainty.</b> When the data cannot support a conclusion, the tool should say so rather than produce one anyway."])
    st += [thinking("The obvious build is one prompt: put the transcripts in front of a large model and ask the question. I rejected "
                    "it early. It cannot be tested properly, its counts drift between runs, and it hides which data it used. The brief "
                    "also asks explicitly for a deliberate workflow rather than a single prompt. I wanted the opposite extreme: "
                    "a system whose facts are deterministic and testable, with a model added only where interpretation genuinely helps."),
           P("<b>Who the user is.</b> A contact-centre analyst or team lead who knows the business but not the data model. They ask "
             "questions like the four in the brief, follow up (\"compare the top two\", \"what about the previous month?\"), and need "
             "something they can paste into a leadership update without re-checking every figure.", "body"),
           P("<b>What success meant.</b> Each of the four questions answered correctly and verifiably. Every number traceable to an "
             "operation. Every claim backed by retrievable evidence. Refusals for questions the data cannot answer. And a system that "
             "a reviewer could run in minutes, with no key.", "body")]

    # 2. Dataset handling
    st += h1("2 · Dataset handling", "Preparing 3,000 conversations, and what the data hid")
    st += [P("I used only the supplied sample of the Syncora.ai Customer Support Conversation dataset (Kaggle): 3,000 synthetic "
             "conversations, 41,965 messages, from 1 August to 2 December 2025. <b>No conversations were appended.</b> I generated "
             "120 tagged synthetic conversations for UI demos only; they are excluded from every default build and analysis.", "body"),
           P("Preparation steps", "h3")]
    st += bullets(["<b>Ingest and validate:</b> schema checks, duplicate and null checks, per-column profiles (data/manifests/).",
                   "<b>Clean:</b> every message ends in random filler tokens. I stripped them into <font face='Mono'>clean_text</font> and kept the raw text.",
                   "<b>Mask:</b> PII patterns are masked into <font face='Mono'>masked_text</font>, which is the only text sent to any model.",
                   "<b>Order:</b> timestamps are not in turn order in any of the 3,000 conversations, so the turn index is authoritative and each conversation is dated by its earliest message.",
                   "<b>Label:</b> after cleaning there are only 426 distinct message templates. I labelled the templates once with a documented rule set (act, sentiment score, empathy, courtesy, resolution fit, topic, product) instead of labelling 41,965 messages.",
                   "<b>Store:</b> DuckDB tables <font face='Mono'>conversations</font>, <font face='Mono'>messages</font>, <font face='Mono'>message_labels</font> and <font face='Mono'>topics</font>, with build metadata."])
    st += [P("Derived fields, labels and aggregations", "h3"),
           table([["Field", "Definition"],
                  ["Conversation sentiment", "Mean of customer-turn sentiment scores, rounded to 9 decimals; <b>negative</b> when ≤ −0.25"],
                  ["Primary topic", "Topic of the customer's opening message (each conversation is counted once)"],
                  ["Conversation month", "Month of the earliest message; \"last month\" = latest month in the data (November 2025)"],
                  ["Acknowledgement rate", "Share of negative customer turns whose next agent turn acknowledges or apologises"],
                  ["Closing-action fit", "Whether the agent's closing action matches the issue (documented mapping; general help excluded)"],
                  ["Escalation / urgency", "Customer turns explicitly asking to escalate, or pressing for urgency"],
                  ["Priority score (Q4)", "Weighted min-max signals: volume 0.30, negative rate 0.25, escalations 0.15, unresolved 0.15, misfit 0.10, month-on-month change 0.05"]],
                 [0.27, 0.73], bold_first=True),
           thinking("The 426 templates looked like a problem at first, because the data is obviously generated. I decided to treat them "
                    "as an opportunity instead. A documented template mapping is transparent and exactly reproducible, and every "
                    "reviewer can disagree with a specific label. The cost is that the labels are my judgement. I measured agreement "
                    "with an independent lexicon (78% accuracy, Cohen's κ 0.67), built an in-app panel to collect human labels, and I "
                    "say in the evaluation that human agreement has not been measured yet."),
           P("Every interpretation (windows, thresholds, mappings) is written down in ASSUMPTIONS.md, and the data dictionary is in "
             "docs/dataset/DATASET.md.", "small")]

    # 3. System design
    st += h1("3 · System design", "Components, contracts and the data passed between them")
    st += [figure(FLOWS / "flow-overview.png", "Figure 1. System overview. The model (dashed) is optional and local.", 0.95),
           table([["Component", "Responsibility", "Never does"],
                  ["Zero-LLM router (<font face='Mono'>agents/router.py</font>)", "Decides whether a model is needed; records why", "Call a model"],
                  ["Intent router (<font face='Mono'>agents/intent_router.py</font>)", "Turns a question into a typed intent", "Invent IDs, numbers or SQL"],
                  ["Supervisor (<font face='Mono'>agents/supervisor.py</font>)", "Resolves the window and references; picks operations", "Compute numbers"],
                  ["Specialists + query registry (<font face='Mono'>analytics/*</font>)", "Run 15 registered, parameterised DuckDB operations", "Accept free-form SQL"],
                  ["Retrieval (<font face='Mono'>retrieval/index.py</font>)", "Hybrid FAISS search for illustrative transcripts", "Produce numbers"],
                  ["QA + Evidence Challenger", "Verify quotes, samples, wording and grounding before display", "Change a number"],
                  ["Memory + telemetry (SQLite)", "Store references for follow-ups; record every step for replay", "Reuse model prose as fact"]],
                 [0.36, 0.40, 0.24]),
           P("Contracts", "h3"),
           P("Agents share one typed state (<font face='Mono'>agents/state.py</font>). Every analysis returns the same versioned "
             "<font face='Mono'>AnalysisResult</font>: parameters, scope, metrics, a table, chart series, evidence references, method "
             "notes, uncertainty notes and coverage. The API wraps results in a <font face='Mono'>ChatResponse</font>: headline, answer, "
             "KPIs, charts, evidence, recommendations, QA results, routing decision and a replay ID. Because every operation speaks "
             "the same schema, the QA checks, charts and memory work for any analysis without special cases.", "body"),
           thinking("I chose a registry of named operations over letting a model write SQL. It costs flexibility: a question with no "
                    "matching operation is answered with a clarification, not an improvised query. In exchange, every operation is "
                    "unit-tested against hand-counted fixtures, and the set of things the system can claim is finite and reviewable. "
                    "For a prototype that leaders might quote, that was the right trade.")]

    # 4. Agent flow
    st += h1("4 · Agent flow", "From question to checked answer")
    st += [figure(FLOWS / "flow-stages.png", "Figure 2. The LangGraph workflow in four stages. Every box is a real node with start and finish events.", 0.82, 105 * mm),
           P("A request, end to end", "h3")]
    st += bullets(["<b>Input validation</b> enforces length limits and scans for prompt injection. <b>Session memory</b> loads the previous turn's intent, window and ranked keys.",
                   "The <b>Zero-LLM router</b> and <b>intent</b> stages decide what is being asked (Figure 3). For \"Which recurring concerns should leadership review first?\" a high-precision rule matches, so the route is <i>analytics only</i>.",
                   "The <b>supervisor</b> plans <font face='Mono'>leadership_priorities</font>, <font face='Mono'>sentiment_trend</font> and <font face='Mono'>resolution_quality</font>. The <b>specialist</b> runs them; <b>retrieval</b> fetches three negative transcripts for the top concern.",
                   "<b>Explanation</b> writes the narrative (deterministic, or model-written and then checked for unverified numbers). <b>Visualisation</b> picks charts and says why.",
                   "<b>QA and the Evidence Challenger</b> re-read every quoted excerpt from the database (34 of 34 matched in this example), check denominators and sample sizes, and state counter-evidence. <b>Governance</b> adds review flags.",
                   "The <b>response</b> is returned with a replay; <b>memory</b> stores the ranked keys for follow-ups."])
    st += [figure(FLOWS / "flow-router.png", "Figure 3. The routing cascade. Policy refusals always win; the model is the last resort, not the first.", 0.7, 185 * mm),
           thinking("Failure handling follows the same principle. If the model is unavailable, slow or returns something invalid, the "
                    "request falls back to the deterministic path rather than failing; a circuit breaker stops repeated calls. If an "
                    "explanation names a number that is not in the verified result, it is discarded. The worst case is a plainer "
                    "answer, never a wrong one.")]

    # 5. Model and tool choices
    st += h1("5 · Model and tool choices", "What I chose, what I rejected, and what it costs")
    st += [table([["Choice", "Why", "Alternatives I considered"],
                  ["LangGraph", "Explicit graph with conditional and parallel edges, typed state, per-request checkpoints; easy to replay", "A single prompt chain (not inspectable); a custom loop (reinvents checkpoints)"],
                  ["DuckDB + pandas + SciPy", "Exact, in-process analytics; Wilson intervals, χ² and z-tests", "Model-computed statistics (not reproducible)"],
                  ["FAISS, MiniLM + LSA, fused by RRF", "Local and free; semantic and lexical signals complement each other", "A hosted vector store (unnecessary at this scale)"],
                  ["Qwen2.5-1.5B-Instruct, local (llama.cpp)", "No key, no cost, data stays on the machine; good enough for closed-list classification", "Hosted models (key blocked during development; see below)"],
                  ["FastAPI + React", "Streaming (SSE) for live agent progress; a real analyst workspace", "A CLI only (harder to show evidence and charts)"],
                  ["SQLite", "Sessions, checkpoints, telemetry, audit in one file", "A server database (no benefit for a single-node prototype)"]],
                 [0.24, 0.42, 0.34], bold_first=True),
           P("Dependencies, keys and cost", "h3")]
    st += bullets(["<b>API keys:</b> none required. Nothing secret is hardcoded; all settings are environment variables (<font face='Mono'>.env.example</font>).",
                   "<b>External services:</b> a one-time download from Hugging Face (MiniLM weights, and the local model if chosen). After that, no data leaves the machine.",
                   "<b>Cost:</b> $0. When the local model is used it makes at most two calls per question; intent classification measured about 660 prompt tokens.",
                   "<b>Latency:</b> deterministic answers p50 125 ms, p95 540 ms. With the local model, a warm routing call takes about a second; the first call after start-up took 8.7 s on an idle CPU."])
    st += [P("Why a local model instead of a hosted API", "h3"),
           P("The brief allows free, commercial or open-source hosted models. I deliberately chose a small open-source model that runs "
             "locally, for these reasons:", "body")]
    st += bullets(["<b>The hosted key I had did not work.</b> The API key available during development returned <font face='Mono'>401 API_KEY_SERVICE_BLOCKED</font>. "
                   "I did not want the prototype, or its evaluation, to depend on a credential I could not rely on.",
                   "<b>The model's job is narrow.</b> By design it never computes numbers or writes SQL. It only picks a question category from a closed "
                   "list when the rules are unsure (6.9% of test questions) and phrases explanations of verified results. A 1.5B model constrained "
                   "by a JSON grammar does this well: routing accuracy rises from 90.4% without it to 95.9% with it.",
                   "<b>Anyone can run it.</b> Reviewers need no account, no API key and no budget. The whole system, model included, costs $0 to run.",
                   "<b>The data stays on the machine.</b> Customer conversations are never sent to a third party, which matters for contact-centre data.",
                   "<b>Results are reproducible.</b> The model file is pinned, so the benchmarks score the same model every time. Hosted models can "
                   "change behind the same name, and rate limits or outages would have made the evaluation harder to repeat.",
                   "<b>Answers never wait on a network.</b> If the model is missing or slow, the request falls back to the deterministic answer."])
    st += [P("<b>The trade-off.</b> A local CPU model is slower and writes plainer explanations than a large hosted model: about 1 s per "
             "routing call, and tens of seconds for a model-written explanation. A hosted model can be added later behind the same router "
             "without redesigning anything (see §12).", "body"),
           thinking("When the key failed, instead of waiting I asked what the product actually needs a model for. The honest answer was: "
                    "routing the questions the rules cannot, and phrasing explanations. Once I saw how narrow that job was, a small local model "
                    "was not a compromise. It made the system cheaper, private by default, and easier to evaluate.")]

    # 6. The four questions
    st += h1("6 · Results", "The four questions, answered")
    st += [P("Q1 · Top 5 topics associated with negative sentiment in the last month", "h2"),
           figure(README / "q1-negative-topics-light.png", "Figure 4. November 2025: 240 of 682 conversations negative. Top 5 highlighted; rank 5 is a tie.", 0.9, 85 * mm),
           table([["Rank", "Topic", "Negative", "Of", "Rate"],
                  ["1", "General help request", "49", "156", "31.4%"], ["2", "Duplicate charge", "42", "87", "48.3%"],
                  ["3", "Paid but service not delivered", "30", "75", "40.0%"], ["4", "Feature not working", "28", "76", "36.8%"],
                  ["5", "Login / account locked (tied with Coupon not applying, 24 of 84)", "24", "58", "41.4%"]],
                 [0.08, 0.56, 0.12, 0.1, 0.14]),
           P("The answer also states that Duplicate charge leads by rate, and that differences between topics are not statistically "
             "significant (χ² p = 0.07). The result matches an independent oracle computed from the raw CSV exactly.", "body"),
           P("Q2 · Agents who may benefit from empathy or communication coaching", "h2"),
           P("The data has 2,987 agent IDs for 3,000 conversations, at most two conversations each. Any ranking of individuals would "
             "rest on one or two transcripts, so the answer says this plainly and gives what the data can support:", "body")]
    st += bullets(["<b>Workforce patterns:</b> only 3,215 of 10,966 negative customer turns (29.3%) received an acknowledgement or apology, and 1,340 of 2,338 assessable closing actions (57.3%) did not fit the issue.",
                   "<b>A review queue of conversations</b> for team leads, each with its evidence.",
                   "<b>Safeguards:</b> a minimum-sample gate (3 conversations) for any per-agent view, a human-review flag on every coaching answer, and refusals for personnel decisions."])
    st += [thinking("This was the answer I thought hardest about. The brief's question invites a league table of agents, and I could "
                    "have produced one. I would rather tell a team lead \"the data cannot support this\" than hand them a ranking that "
                    "could affect someone's job on the strength of two chats. Reframing to patterns and a review queue keeps the "
                    "question useful and the answer defensible."),
           P("Q3 · How customer sentiment changed over a selected conversation", "h2"),
           P("Turn-by-turn customer sentiment is shown in turn order, with turning points and the agent message just before each. For "
             "C0000479 (Coupon not applying · Voucher), sentiment worsened from +1.0 at the first follow-up to −1.0 at the end, across "
             "five turning points; the problem resurfaced after the customer said it was fixed. A Conversation X-Ray links each "
             "finding (escalation, urgency, repeated concern, unacknowledged frustration) to the exact messages.", "body"),
           figure(README / "shots" / "xray.png", "Figure 5. Conversation X-Ray: timeline, sentiment line, findings and transcript share one selection.", 0.95, 95 * mm),
           P("Q4 · Recurring concerns leadership should review first", "h2"),
           figure(README / "q4-priorities-light.png", "Figure 6. Leadership priority scores and what drives each one.", 0.9, 80 * mm),
           P("Item or service not received ranks first (67.1), then Coupon not applying (60.8) and Duplicate charge (59.8). The "
             "weights are shown with the chart, and a sensitivity analysis re-ranks under 13 weight scenarios: the top concern stays "
             "first in 92% of them. Each recommendation names the finding, its driver, an action, a decision owner, evidence and "
             "its uncertainty.", "body")]

    # 7. Bonus extensions
    st += h1("7 · Bonus extensions", "Retrieval, a specialised agent, and memory")
    st += [P("1 · Knowledge retrieval", "h2"),
           table([["Question from the brief", "My answer"],
                  ["How is it indexed?", "4-turn windows with an overlap of 2 (18,639 chunks), embedded twice (MiniLM and LSA) in exact-cosine FAISS indexes with metadata filters."],
                  ["When is it triggered?", "For similar-case questions; in parallel for coaching evidence; and after an analysis, to illustrate the top-ranked result with negative examples."],
                  ["What evidence is returned?", "One passage per conversation, with message IDs, CSV line references and each method's rank."],
                  ["How does it improve the answer?", "Analysts see real, on-topic transcripts beside every computed result, and can open the full conversation. Retrieval never produces a number."]],
                 [0.3, 0.7], bold_first=True),
           figure(README / "retrieval-methods-light.png", "Figure 7. 36 paraphrased queries: hybrid hit@5 86.1% and topic precision@5 62.8% (MiniLM alone 83.3% / 62.2%).", 0.85, 75 * mm),
           P("The hybrid's gain over MiniLM alone is small, and the fusion weight was tuned on the same queries. I report both facts.", "small"),
           P("2 · Specialised LLM agent: a constrained local intent classifier", "h2")]
    st += bullets(["<b>What:</b> Qwen2.5-1.5B-Instruct answers with exactly one category from a closed list, enforced by a JSON-schema grammar. Entities are validated before any query runs.",
                   "<b>Why this approach:</b> classifying a question is a safe job for a small model, because every entity and number still comes from deterministic code. Fine-tuning was not justified by 426 templates and a few hundred benchmark questions.",
                   "<b>How it fits:</b> it is the last automatic stage of the routing cascade, called for 6.9% of test questions.",
                   "<b>How usefulness is evaluated:</b> a 73-question test split written before the router changed, frozen by SHA-256 and scored once. The router scores 95.9% with the model and 90.4% without it."])
    st += [figure(README / "routing-accuracy-light.png", "Figure 8. Routing accuracy on the held-out split, from the first prompt (19.2%) to the final router (95.9%).", 0.85, 75 * mm),
           thinking("The model alone scored 19.2% with my first prompt and 58.9% after a careful rewrite. I could have kept tuning "
                    "prompts, but each tweak was a guess I could not verify without spending the test set. I stopped asking the model "
                    "to do the whole job and built the confidence cascade instead. I also built a semantic-similarity stage, "
                    "calibrated it, and left it switched off, because no threshold reached 95% precision on validation."),
           P("3 · Memory integration", "h2"),
           table([["Question from the brief", "My answer"],
                  ["What is stored?", "Per turn: question, intent, scope, plan, and deterministic references (ranked keys, conversation IDs). Never model prose."],
                  ["How is it retrieved?", "By session ID at the start of each request; references such as \"the top two\" or \"the previous month\" are resolved from it."],
                  ["How does it affect later answers?", "Follow-ups re-run the stored plan with the new scope, so \"compare the top two\" compares the real #1 and #2. 11 of 11 evaluation follow-ups routed correctly."],
                  ["Reliability and privacy", "References are re-validated against the database before reuse. Sessions are isolated, retained for 30 days (configurable) and deletable per session."]],
                 [0.3, 0.7], bold_first=True)]

    # 8. Six enhancements
    st += h1("8 · Beyond the brief", "Six enhancements")
    st += [P("After the four questions and the three extensions worked, I added six enhancements. Each one came from asking what an "
             "analyst would need in order to trust an answer, or to act on it. They follow the same rule as the rest of the system: "
             "they read verified results and never produce numbers of their own.", "body"),
           table([["Enhancement", "What it adds", "Why I built it"],
                  ["Zero-LLM Intelligence Router", "Decides before any model call whether a model is needed. Analysts can also choose Analytics only or Hybrid AI.", "Fact questions should cost nothing and never depend on a model. All four brief questions use zero model calls."],
                  ["Query-driven dashboards", "Turns each answer into a dashboard with a reason for each chart, filter chips and refinements that re-run the analysis.", "An answer is usually the start of an investigation, not the end of one."],
                  ["Conversation X-Ray", "Escalations, repeated concerns and communication gaps in one conversation, each linked to the exact messages.", "Q3 asks how sentiment changed; a team lead also needs to see where and why."],
                  ["Root Cause Investigator", "Tests factors associated with negative sentiment, with intervals, separating symptoms from candidate drivers.", "To answer why without claiming cause from observational data."],
                  ["AI Decision Replay", "Step-through playback of routing, every node, each DuckDB operation, retrieval and model call, with secrets redacted.", "Reviewers and analysts can check how an answer was produced."],
                  ["Evidence Challenger", "Re-reads every quote, discloses small samples, states counter-evidence and rewrites causal wording.", "A second, adversarial check before anything is shown."]],
                 [0.22, 0.42, 0.36], bold_first=True),
           two_figures(README / "shots" / "root-cause.png", README / "shots" / "evidence-review.png",
                       "Figure 9. Root Cause Investigator: drivers vs symptoms, with intervals.",
                       "Figure 10. Evidence Challenger: what was checked, and what does not fit the claim."),
           Spacer(1, 6),
           thinking("Building the Evidence Challenger exposed two real bugs: QA had been reporting zero resolved evidence items because "
                    "one node overwrote another's report, and a repeated-phrase detector always returned zero. It also caught one of my "
                    "own sentences: it rewrote \"because of\" into \"associated with\" in the tie disclosure for Q1. My wording was the problem.")]

    # 9. Evaluation
    st += h1("9 · Evaluation", "What I measured, what worked, and what failed")
    st += [P("I evaluated the system the way the brief suggests: task-specific metrics, representative successes and failures, "
             "grounding quality, and latency and consistency. Every benchmark was written before the change it measures.", "body"),
           P("Task-specific metrics", "h3"),
           table([["Measure", "Result", "How"],
                  ["Q1 vs independent oracle", "Exact match", "Separate code over the raw CSV, exact fractions"],
                  ["Intent routing (73 held-out)", "95.9% · macro F1 0.932", "Frozen split, scored once; 90.4% without a model"],
                  ["Refusals of unsupported questions", "6 / 6 end to end", "Revenue, CSAT, personnel decisions, off-topic"],
                  ["Follow-up routing", "11 / 11", "Multi-turn evaluation sessions"],
                  ["End-to-end QA pass rate", "88% of 51 requests", "All critical checks pass; the rest are Challenger warnings"],
                  ["Retrieval", "hit@5 86.1% · topic P@5 62.8%", "36 paraphrased queries; MiniLM alone 83.3% / 62.2%"],
                  ["Label agreement", "78% accuracy · Cohen's κ 0.67", "Template labels vs an independent lexicon"],
                  ["Automated tests", "138 backend · 8 Vitest · 17 Playwright", "All passing"]],
                 [0.3, 0.32, 0.38], bold_first=True),
           P("Representative successes", "h3")]
    st += bullets(["All four brief questions answered with zero model calls, correct counts, and evidence that opens the source transcript.",
                   "\"How much revenue did we lose to coupon issues?\" is refused with a reason: the dataset has no revenue.",
                   "\"Compare the top two\" after Q1 compares General help request and Duplicate charge, keeping November 2025."])
    st += [P("Representative failures (kept visible, not fixed on the test split)", "h3"),
           table([["Question", "Expected", "Got"],
                  ["Compare the sentiment mix across languages", "sentiment distribution", "topic comparison"],
                  ["Is delivery or payment worse for sentiment?", "topic comparison", "negative topics (model)"],
                  ["Why is the top negative topic so negative?", "root cause", "explain previous answer"]],
                 [0.5, 0.25, 0.25]),
           P("A failure that taught me the most", "h3"),
           P("While auditing my own submission, one Q4 score was off by 0.5. The cause was floating point: a conversation whose "
             "customer scores average exactly −0.25 on paper (for example −0.6, −0.6, −0.6, −0.6, +0.8, −0.6, +0.8, −0.6) sums to "
             "−0.24999999999999994 in floating point, so it was labelled not negative. Fixing it moved a priority score from 52.9 to "
             "53.4 and the November count from 239 to 240. My independent checker had made the same mistake, because it also "
             "averaged with floats. The oracle now uses exact fractions, and a regression test pins the case.", "body"),
           thinking("Two implementations that share an assumption are really one implementation. Since then I check the checker: the "
                    "oracle uses a different arithmetic from the system it verifies."),
           P("Grounding quality", "h3")]
    st += bullets(["<b>Excerpt fidelity 100%:</b> every quoted excerpt is re-read from DuckDB and must match word for word (34 of 34 in the Q4 example).",
                   "<b>Grounded explanations 100%:</b> an explanation containing any number not in the verified result is rejected and replaced by the deterministic narrative.",
                   "<b>Evidence coverage 92.3%:</b> the share of top-ranked claims with an attached example; missing examples are flagged as warnings.",
                   "<b>Evidence relevance:</b> examples must fit the claim (negative examples for a negative claim); counter-evidence is stated alongside."])
    st += [P("Latency and consistency", "h3")]
    st += bullets(["<b>Deterministic answers:</b> p50 125 ms, p95 540 ms end to end on a local CPU. Retrieval alone: p50 39 ms.",
                   "<b>With the local model:</b> about 1 s per warm routing call; the first call after start-up took 8.7 s on an idle CPU and 30–55 s under CPU contention. Model-written explanations take tens of seconds.",
                   "<b>Consistency:</b> the deterministic path returns identical answers for identical questions. The routing benchmark records the stage that decided each question, so any change in behaviour can be traced to a rule, a threshold or the model."])

    # 9. What I did / didn't
    st += h1("10 · Judgement", "What I did, what I chose not to do, and how I worked")
    st += [table([["I chose not to…", "Because…"],
                  ["Rank individual agents", "No agent has more than two conversations; a ranking would be noise with consequences."],
                  ["Let a model write SQL or produce numbers", "Numbers must be reproducible and testable; the registry keeps claims finite and reviewable."],
                  ["Claim causes", "Associations are tested with intervals and phrased as associations; customer reactions are treated as symptoms."],
                  ["Fine-tune a model", "426 templates and a small benchmark do not justify it; a constrained small model plus rules does the job."],
                  ["Enable the semantic routing stage", "It did not reach 95% precision on validation, so its own calibration keeps it off."],
                  ["Tune on the test split", "It would make the 95.9% meaningless; the three remaining errors stay listed."],
                  ["Append data or keep demo data in the default build", "Results must describe the supplied 3,000 conversations only."],
                  ["Build authentication or multi-tenancy", "Out of scope for a prototype; listed under next improvements."]],
                 [0.36, 0.64], bold_first=True),
           P("How I worked", "h3")]
    st += bullets(["<b>Data first.</b> Profiling, quality checks and the label mapping came before any agent, because every later answer depends on them.",
                   "<b>Analytics core and registry next</b>, each operation tested against hand-counted fixtures.",
                   "<b>Then the workflow:</b> LangGraph nodes, retrieval, memory and the API, followed by the analyst workspace.",
                   "<b>Evaluation alongside, not after:</b> an oracle for Q1, a routing benchmark, a retrieval benchmark, end-to-end QA.",
                   "<b>Routing optimisation as a controlled experiment:</b> baseline diagnosis, then rules, semantic stage, prompt and confidence router, then one score on the frozen test split.",
                   "<b>Finally, an audit of my own submission</b> against every sentence of the brief, which found the float bug, a stale report and missing documentation. I fixed them and recorded the fixes."])

    # 10. Limitations
    st += h1("11 · Limitations", "What a reviewer should know")
    st += bullets(["<b>Labels are a judgement</b> over templated synthetic text; agreement with human labellers is not yet measured.",
                   "<b>The routing benchmark is small and same-author:</b> 73 test questions written by the person who wrote the rules. The 95.9% is indicative, not precise.",
                   "<b>The hybrid retrieval gain is small</b>, and its weight was tuned on the evaluation queries.",
                   "<b>The local model is slow on CPU</b> for long explanations (tens of seconds), so interpretive answers in Hybrid mode are slower.",
                   "<b>Root-cause signals come from template labels</b>, so associations may reflect how the data was generated.",
                   "<b>Not production-hardened:</b> no authentication or role-based access, single-node storage, Docker images not verified end to end."])

    # 11. Next improvements
    st += h1("12 · Next improvements", "From prototype to production")
    st += [table([["Area", "Next step"],
                  ["Quality", "Collect human labels in the review panel; measure agreement; re-write a routing benchmark with other authors."],
                  ["Models", "Optionally add a hosted model behind the same router: function calling over the operation registry, streamed and schema-constrained explanations, context caching, token budgets with fallback to the local model, and the same frozen test split as a gate."],
                  ["Data platform", "Managed warehouse and vector store; a job queue for labelling and re-indexing."],
                  ["Security", "SSO and role-based access, tenant isolation, a secret manager, retention policies per tenant."],
                  ["Operations", "OpenTelemetry tracing, CI/CD with evaluation gates, A/B tests of prompts and models on human-labelled sets, horizontal API scaling."]],
                 [0.2, 0.8], bold_first=True)]

    # 12. Reproduce
    st += h1("13 · Repository", "What is in the repository, and how to run it")
    st += [P(f"<a href='{REPO}' color='#0d6b74'>{REPO}</a>", "small"),
           P("Source code and setup/run instructions", "h3"),
           P("<font face='Mono'>backend/</font> holds the FastAPI app, agents, analytics, retrieval, memory and tests. "
             "<font face='Mono'>frontend/</font> holds the React workspace and Playwright tests. Python 3.12+ with uv, Node 22+ and make; no API key.", "body"),
           Paragraph("git clone https://github.com/florina787/Data-sets.git<br/>"
                     "cd Data-sets/conversation-intelligence-copilot &amp;&amp; git checkout claude/happy-edison-gef7ay<br/>"
                     "cp .env.example .env<br/>make install &amp;&amp; make prepare &amp;&amp; make index<br/>"
                     "make dev            # UI http://localhost:5173 · API docs http://localhost:8000/docs<br/>"
                     "make test &amp;&amp; make e2e # 138 + 8 + 17 tests<br/>"
                     "make install-local-llm &amp;&amp; make llm-download   # optional local model", S["code"]),
           P("The README also covers Docker, VS Code launch configurations, PyCharm and a two-terminal setup.", "small"),
           P("Sample requests and outputs", "h3"),
           P("<font face='Mono'>examples/requests/</font> holds six requests and <font face='Mono'>examples/outputs/</font> the matching "
             "responses as JSON and readable Markdown, generated from real runs: the four brief questions (with follow-ups), a "
             "retrieval request and an unsupported question. For example:", "body"),
           Paragraph("curl -s localhost:8000/api/chat -H 'Content-Type: application/json' \\<br/>"
                     "&nbsp;&nbsp;-d '{\"question\":\"Which recurring customer concerns should contact-centre leadership review first?\"}'", S["code"]),
           P("Obtaining or preparing the dataset", "h3"),
           P("The supplied sample is committed at <font face='Mono'>data/raw/cs_conversations.csv.zip</font>, so nothing needs to be "
             "downloaded. <font face='Mono'>make prepare</font> validates, cleans, labels and loads it into DuckDB (about 30 seconds), and "
             "<font face='Mono'>make index</font> builds the retrieval index. The data dictionary is in "
             "<font face='Mono'>docs/dataset/DATASET.md</font> and every interpretation in <font face='Mono'>ASSUMPTIONS.md</font>.", "body"),
           P("Environment variables and external services", "h3"),
           table([["Variable", "Default", "Purpose"],
                  ["LLM_PROVIDER", "auto", "auto uses the local model if downloaded, otherwise none; none forces deterministic answers"],
                  ["LOCAL_MODEL_REPO / FILE / DIR", "Qwen2.5-1.5B GGUF, data/models", "Local model source and location"],
                  ["RETRIEVAL_MODE, RRF_K, HYBRID_LSA_WEIGHT", "hybrid, 60, 0.15", "Retrieval method and fusion settings"],
                  ["ENABLE_SYNTHETIC_DEMO", "false", "Demo conversations are loaded only when enabled"],
                  ["SESSION_RETENTION_DAYS", "30", "Memory retention"]],
                 [0.36, 0.26, 0.38]),
           P("All settings are environment variables listed in <font face='Mono'>.env.example</font>; nothing secret is hardcoded and "
             "no API key is required. The only external service is a one-time download from Hugging Face (MiniLM weights, and the "
             "local model if chosen). Cost: $0.", "body"),
           Spacer(1, 10),
           thinking("The brief says you are not looking for a polished enterprise product, but for practical engineering judgement. "
                    "I tried to spend my effort where judgement shows: deciding what the model should not do, refusing to overstate "
                    "thin data, and measuring the system honestly, including the parts that are not yet good enough.",
                    "A closing note")]
    return st


def _is_heading(f) -> bool:
    if isinstance(f, Paragraph):
        return f.style.name in ("h2", "h3")
    return isinstance(f, KeepTogether) and any(isinstance(x, Paragraph) and getattr(x, "_toc", None) for x in f._content)


def _is_block(f) -> bool:
    """Bounded in height: a figure, a small table, a callout, or a paragraph."""
    return isinstance(f, (KeepTogether, Paragraph)) and not _is_heading(f)


def bind_headings(items: list) -> list:
    """Keep a run of headings on the same page as the first bounded block after it (keepWithNext fails across tables)."""
    out: list = []
    i = 0
    while i < len(items):
        if not _is_heading(items[i]):
            out.append(items[i])
            i += 1
            continue
        group = []
        while i < len(items) and _is_heading(items[i]):
            group.append(items[i])
            i += 1
        if i < len(items) and _is_block(items[i]):
            group.append(items[i])
            i += 1
        elif i < len(items) and isinstance(items[i], Table):  # a long table: make room for its first rows instead
            out.append(CondPageBreak(70 * mm))
        flat = [x for f in group for x in (f._content if isinstance(f, KeepTogether) else [f])]  # nested KeepTogether mis-measures
        out.append(KeepTogether(flat))
    return out


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = Doc(str(OUT))
    doc.multiBuild(bind_headings(story()))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
