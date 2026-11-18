"""Executive Export Studio: real, policy-filtered PDF reports built in memory.

Every report is assembled from the same server-side functions the app uses, with the Privacy
Shield purpose ``export`` (confidential values banded, restricted data excluded, other tenants
removed). Nothing is read from raw tables or from stored conversation payloads without filtering,
and no temporary files are written. Conversation and investigation exports are owner-only.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.errors import NotFound, PlatformError

KINDS = {
    "executive": "Executive summary",
    "board": "Board briefing",
    "technology": "Technology health report",
    "supplier_risk": "Supplier risk report",
    "architecture": "Architecture overview",
    "decisions": "Decision and action summary",
    "investigation": "Investigation report",
    "conversation": "Conversation briefing",
}
NAVY, GOLD, TEAL, INK, MUTED = (colors.HexColor(c) for c in ("#091321", "#B8955A", "#2C9C91", "#1B2430", "#5B6676"))
CLASSIFICATION = "INTERNAL — policy-filtered (confidential values banded, restricted data excluded)"


def _styles():
    ss = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "t",
            parent=ss["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=NAVY,
            alignment=TA_LEFT,
            spaceAfter=4,
        ),
        "sub": ParagraphStyle("s", parent=ss["Normal"], fontSize=11, leading=15, textColor=MUTED, spaceAfter=10),
        "h2": ParagraphStyle(
            "h2",
            parent=ss["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13.5,
            leading=17,
            textColor=NAVY,
            spaceBefore=12,
            spaceAfter=6,
        ),
        "body": ParagraphStyle("b", parent=ss["Normal"], fontSize=10.5, leading=15, textColor=INK),
        "small": ParagraphStyle("sm", parent=ss["Normal"], fontSize=8.5, leading=11.5, textColor=MUTED),
        "bullet": ParagraphStyle(
            "bl", parent=ss["Normal"], fontSize=10.5, leading=15, textColor=INK, leftIndent=12, bulletIndent=2
        ),
    }


def _esc(t) -> str:
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("**", "")


def _bar(title: str, labels: list[str], values: list[float], unit: str) -> Drawing:
    n = max(1, len(labels))
    d = Drawing(170 * mm, 14 * mm + n * 8 * mm)
    c = HorizontalBarChart()
    c.x, c.y, c.width, c.height = 62 * mm, 6 * mm, 95 * mm, n * 8 * mm
    c.data = [values or [0]]
    c.categoryAxis.categoryNames = [lb[:34] for lb in labels] or ["—"]
    c.categoryAxis.labels.fontSize, c.valueAxis.labels.fontSize = 8, 7
    c.categoryAxis.labels.fillColor = INK
    c.valueAxis.valueMin = 0
    c.bars[0].fillColor = TEAL
    c.barLabelFormat = "%.1f" if unit == "%" else "%.0f"
    c.barLabels.fontSize = 7
    c.barLabels.nudge = 8
    d.add(c)
    d.add(String(0, d.height - 9, f"{title} ({unit})", fontName="Helvetica-Bold", fontSize=9, fillColor=NAVY))
    return d


def _architecture() -> Drawing:
    """Static diagram of the orchestration path (the same graph Enterprise X-Ray animates)."""
    d = Drawing(170 * mm, 62 * mm)
    boxes = [("Your question", 0), ("Jerry orchestrator", 1), ("Policy engine", 2), ("Approved tools / MCP", 3)]
    w, h, y = 36 * mm, 11 * mm, 44 * mm
    for label, i in boxes:
        x = i * 44 * mm
        d.add(
            Rect(
                x,
                y,
                w,
                h,
                rx=6,
                ry=6,
                fillColor=colors.HexColor("#EAF6F4") if i != 2 else colors.HexColor("#F6EEDC"),
                strokeColor=TEAL if i != 2 else GOLD,
            )
        )
        d.add(String(x + w / 2, y + 4 * mm, label, textAnchor="middle", fontSize=8, fillColor=INK))
        if i < 3:
            d.add(Line(x + w, y + h / 2, x + 44 * mm, y + h / 2, strokeColor=MUTED))
            d.add(
                Polygon(
                    [x + 44 * mm, y + h / 2, x + 42 * mm, y + h / 2 + 1.2 * mm, x + 42 * mm, y + h / 2 - 1.2 * mm],
                    fillColor=MUTED,
                    strokeColor=MUTED,
                )
            )
    sources = [
        ("Demo data & app records", "connected"),
        ("Databricks SQL", "adapter, not configured"),
        ("Kubernetes API", "adapter, not configured"),
        ("Legacy ERP", "planned"),
    ]
    for i, (label, state) in enumerate(sources):
        x = i * 44 * mm
        d.add(Rect(x, 16 * mm, w, 14 * mm, rx=6, ry=6, fillColor=colors.white, strokeColor=MUTED))
        d.add(String(x + w / 2, 24 * mm, label, textAnchor="middle", fontSize=7.5, fillColor=INK))
        d.add(String(x + w / 2, 19.5 * mm, state, textAnchor="middle", fontSize=6.5, fillColor=MUTED))
        d.add(Line(3 * 44 * mm + w / 2, y, x + w / 2, 30 * mm, strokeColor=colors.HexColor("#C5CCD6")))
    d.add(
        String(
            0,
            4 * mm,
            "Evidence returns through the policy engine to a cited answer and visual response. Kubernetes = "
            "infrastructure orchestration; Databricks = governed analytics; MCP = interface for approved tools.",
            fontSize=6.8,
            fillColor=MUTED,
        )
    )
    return d


def _content(kind: str, user, ref: str | None) -> dict:
    from app import connectors, privacy, pulse
    from app.enterprise import queries

    principal = privacy.principal_for(user)
    prios = pulse.priorities(user.username)
    health = pulse.health(user.username)
    sales = queries.executive_overview()["sales"]
    period = f"Last 4 weeks to {sales['current_weeks'][-1]}" if sales.get("current_weeks") else "Last 4 weeks"
    base = {
        "period": period,
        "assumptions": [
            "Enterprise figures come from the fictional company's synthetic dataset; "
            "they are not real business results.",
            "Modelled ranges (P10–P90) come from a Monte Carlo scenario with stated assumptions, "
            "not forecasts of real events.",
        ],
        "limitations": [
            "No verified enterprise data source is connected. "
            "Databricks and Kubernetes adapters are not configured here.",
            "Potato grades come from classical image rules, not a trained model; real-photo accuracy is unmeasured.",
        ],
        "evidence": [e | {"for": p["title"]} for p in prios[:5] for e in p["evidence"]],
        "charts": [],
        "tables": [],
        "diagram": None,
    }

    if kind in ("executive", "board"):
        top = prios[:3]
        base |= {
            "summary": [
                f"{len([p for p in prios if p['severity'] == 'high'])} high-priority item(s) need a decision. "
                f"Most urgent: {top[0]['title']}."
                if top
                else "No open priorities in the current records.",
                "Enterprise health: " + "; ".join(f"{h['label']}: {h['value']}" for h in health) + ".",
            ],
            "findings": [f"{p['title']} — {p['why']}" for p in top],
            "next_steps": [f"{p['next_step']} (owner: {p['owner']})" for p in top],
            "charts": [
                (
                    "Weekly revenue, last 8 weeks",
                    [w["week_start"][5:] for w in sales["trend"][-8:]],
                    [round(w["revenue"] / 100_000, 1) for w in sales["trend"][-8:]],
                    "CAD 000s",
                )
            ],
        }
        if kind == "board":
            base["summary"].append(
                "Decisions requested from the board: none are executed by Flo & Jerry; each "
                "recommendation needs the accountable owner's approval."
            )
    elif kind == "technology":
        tech = pulse.technology(user.username)
        reg = connectors.registry()
        base |= {
            "summary": [f"{t['question']} {t['answer']}" for t in tech[:2]],
            "findings": [f"{t['question']} {t['answer']}" for t in tech],
            "next_steps": [
                "Configure the local model to enable LIVE answers (optional).",
                "Configure read-only Databricks and Kubernetes adapters to replace simulated views.",
            ],
            "tables": [
                (
                    "Integration status",
                    ["Integration", "State", "Access"],
                    [[r["name"], r["state"].replace("_", " "), r["access"]] for r in reg],
                )
            ],
        }
    elif kind == "supplier_risk":
        recs, rep = privacy.suppliers(principal, "export")
        top = sorted(recs, key=lambda r: (-(r["open_incidents"] or 0), r["quality_pass_pct"]))[:8]
        base |= {
            "summary": [
                f"{len(recs)} suppliers in scope. Confidential commercial terms are shown as bands; "
                f"personal and banking details are excluded by policy ({', '.join(rep.as_dict()['excluded'])})."
            ],
            "findings": [
                f"{r['name']}: {r['open_incidents']} incident(s), quality pass {r['quality_pass_pct']}%, "
                f"on time {r['on_time_pct']}%"
                for r in top[:3]
            ],
            "next_steps": [
                "Review the top suppliers with the supply-chain owner.",
                "Request exact commercial terms from the procurement system if a decision needs them.",
            ],
            "charts": [
                (
                    "Quality pass rate, suppliers needing attention",
                    [r["name"] for r in top],
                    [r["quality_pass_pct"] for r in top],
                    "%",
                )
            ],
            "tables": [
                (
                    "Supplier scorecard (policy-filtered)",
                    ["Supplier", "Country", "Incidents", "Spend band"],
                    [[r["name"], r["country"], r["open_incidents"], r["annual_spend_cents"]] for r in top],
                )
            ],
        }
    elif kind == "architecture":
        reg = connectors.registry()
        base |= {
            "summary": [
                "Flo & Jerry attaches to existing systems through governed, read-only adapters and an MCP "
                "interface; it does not replace them."
            ],
            "findings": [
                "Kubernetes provides infrastructure orchestration; Flo & Jerry reads service health only.",
                "Databricks provides governed analytics; only allowlisted, parameterised queries run.",
                "MCP is the interface for approved AI tools; every tool call is policy-filtered and audited.",
            ],
            "next_steps": ["Approve the data schemas and service accounts for the adapters you want enabled."],
            "diagram": "architecture",
            "tables": [
                (
                    "Connector states (verified, not assumed)",
                    ["Integration", "Category", "State"],
                    [[r["name"], r["category"], r["state"].replace("_", " ")] for r in reg],
                )
            ],
        }
    elif kind == "decisions":
        ds = pulse.list_decisions(user.username)
        base |= {
            "summary": [
                f"{len(ds)} decision(s) in your journal; {sum(d['status'] == 'done' for d in ds)} with a "
                "recorded outcome."
            ],
            "findings": [f"{d['title']}: {d['decision']} ({d['status']})" for d in ds[:10]],
            "next_steps": [f"Follow up “{d['title']}” on {d['follow_up_on']}" for d in ds if d["follow_up_on"]][:5],
            "tables": [
                (
                    "Decision journal",
                    ["Decision", "Owner", "Status", "Outcome"],
                    [[d["title"], d["owner"] or "—", d["status"], d["outcome"] or "—"] for d in ds],
                )
            ],
        }
    elif kind == "investigation":
        inv = next((i for i in pulse.list_investigations(user.username) if i["id"] == ref), None)
        if not inv:
            raise NotFound("Investigation not found")
        p = next((x for x in prios if x["id"] == inv["priority_id"]), None)
        base |= {
            "summary": [f"Investigation “{inv['title']}”, opened {inv['created_at'][:10]}, status {inv['status']}."],
            "findings": ([p["why"]] if p else ["The original priority is no longer open."])
            + [f"{c['metric'].replace('_', ' ')}: {c['then']} → {c['now']}" for c in inv["changes"]],
            "next_steps": [p["next_step"]] if p else ["Close the investigation if no action remains."],
            "evidence": [e | {"for": inv["title"]} for e in (p["evidence"] if p else [])],
        }
    elif kind == "conversation":
        from app.memory.store import get_store

        store = get_store()
        if not ref or store.owner(ref) != user.username:
            raise NotFound("Conversation not found")
        msgs = store.messages(ref, user.username)
        qa = [(m["content"], None) if m["role"] == "user" else (None, m["content"]) for m in msgs]
        questions = [privacy.scrub(q) for q, _ in qa if q]
        answers = [a for _, a in qa if a]
        base |= {
            "summary": [f"Briefing prepared from a conversation with Jerry ({len(questions)} question(s))."],
            "findings": [
                f"Q: {q}" + (f" — A: {a[:600]}" if a else "") for q, a in zip(questions, answers, strict=False)
            ],
            "next_steps": [p["next_step"] for p in prios[:2]],
        }
    else:
        raise PlatformError(f"Unknown report type. Choose one of: {', '.join(KINDS)}")
    return base


def build(kind: str, user, ref: str | None = None) -> tuple[bytes, str]:
    """Return (pdf bytes, file name). Raises NotFound/PlatformError for unauthorised or unknown requests."""
    from app import privacy
    from app.records import audit

    if kind not in KINDS:
        raise PlatformError(f"Unknown report type. Choose one of: {', '.join(KINDS)}")
    c = privacy.scrub_obj(_content(kind, user, ref))
    s = _styles()
    now = datetime.now(timezone.utc)
    buf = io.BytesIO()

    def frame(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, A4[1] - 12 * mm, A4[0], 12 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor("#D7B77A"))
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(15 * mm, A4[1] - 8 * mm, "FLO & JERRY 3.0  ·  " + KINDS[kind].upper())
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(15 * mm, 9 * mm, CLASSIFICATION)
        canvas.drawRightString(A4[0] - 15 * mm, 9 * mm, f"Generated {now:%Y-%m-%d %H:%M} UTC · page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=16 * mm,
        title=f"Flo & Jerry — {KINDS[kind]}",
        author="Flo & Jerry 3.0",
        subject=CLASSIFICATION,
        lang="en",
    )
    story = [
        Paragraph(KINDS[kind], s["title"]),
        Paragraph(
            f"Food Beverage Food Care (fictional) · {_esc(c['period'])} · prepared for {_esc(user.display_name)}"
            f" · {CLASSIFICATION}",
            s["sub"],
        ),
    ]

    def section(title: str, items: list[str]):
        if items:
            story.append(Paragraph(title, s["h2"]))
            story.extend(Paragraph(_esc(t), s["bullet"], bulletText="•") for t in items)

    section("Executive summary", c["summary"])
    section("Key findings", c["findings"])
    for title, labels, values, unit in c["charts"]:
        story.append(Paragraph("Chart", s["h2"]))
        story.append(_bar(title, labels, values, unit))
        story.append(
            Paragraph(
                "Text alternative: "
                + _esc(
                    "; ".join(f"{lb} {v}{unit if unit == '%' else ''}" for lb, v in zip(labels, values, strict=False))
                ),
                s["small"],
            )
        )
    if c["diagram"] == "architecture":
        story.append(Paragraph("Architecture", s["h2"]))
        story.append(_architecture())
    for title, cols, rws in c["tables"]:
        t = Table([cols] + [[Paragraph(_esc(x), s["small"]) for x in r] for r in rws], repeatRows=1, hAlign="LEFT")
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, 0), 8.5),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D5DAE1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
                ]
            )
        )
        story += [Paragraph(title, s["h2"]), t]
    section("Recommended next steps", c["next_steps"])
    if c["evidence"]:
        rows = [["Evidence", "Source", "Provenance", "As of"]] + [
            [
                Paragraph(_esc(e["label"]), s["small"]),
                Paragraph(_esc(e["ref"]), s["small"]),
                e["provenance"] or "—",
                str(e.get("as_of") or "—")[:16],
            ]
            for e in c["evidence"][:12]
        ]
        t = Table(rows, colWidths=[62 * mm, 52 * mm, 30 * mm, 26 * mm], hAlign="LEFT")
        t.setStyle(
            TableStyle(
                [
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF1F5")),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D5DAE1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story += [Paragraph("Supporting evidence and data provenance", s["h2"]), t]
    story.append(
        KeepTogether(
            [Paragraph("Assumptions and limitations", s["h2"])]
            + [Paragraph(_esc(x), s["bullet"], bulletText="•") for x in c["assumptions"] + c["limitations"]]
        )
    )
    story += [
        Spacer(1, 6),
        Paragraph(
            "Prepared by Flo &amp; Jerry from policy-filtered data. Recommendations are not "
            "actions: each needs approval by the accountable owner.",
            s["small"],
        ),
    ]
    doc.build(story, onFirstPage=frame, onLaterPages=frame)
    audit(user.username, f"export.{kind}", outcome="ok", entity_type="export", entity_id=kind, bytes=buf.tell())
    return buf.getvalue(), f"flo-jerry-{kind.replace('_', '-')}-{now:%Y%m%d-%H%M}.pdf"
