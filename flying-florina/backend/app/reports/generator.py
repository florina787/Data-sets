"""Local report generation: PDF (ReportLab), HTML, Markdown, CSV and JSON.

No network access, no external fonts. Every report carries the synthetic-data
and independence disclaimers and a SHA-256 recorded in the reports table.
"""

from __future__ import annotations

import csv
import html
import io
import json
from typing import Any

from app.core import audit, db
from app.core.config import get_settings
from app.core.security import Actor
from app.core.util import DEMO_TODAY, new_id, now_iso

DISCLAIMER = ("SYNTHETIC DATA | DEMO MODE | NO LIVE IFS CONNECTION. Independent concept demo - not affiliated with or endorsed by IFS. "
              "Figures are computed from fictional data and editable assumptions; they are not customer actuals or promised savings. "
              "Compliance references are informational and require qualified compliance review.")

KINDS = {
    "executive_brief": ("Executive modernization brief", {"pdf", "md", "html"}),
    "one_page_brief": ("One-page pilot brief", {"pdf", "md"}),
    "architecture": ("Architecture overview", {"md"}),
    "evidence_manifest": ("Evidence manifest", {"json"}),
    "audit_packet": ("Audit packet", {"json"}),
    "work_orders": ("Open work orders", {"csv"}),
    "workspace": ("Workspace export", {"md", "html", "json", "pdf"}),
    "demo_script": ("Demo video script", {"md"}),
}

LABEL = {"audit_packet": "RESTRICTED", "work_orders": "INTERNAL"}


def _sections(kind: str, ctx: dict[str, Any]) -> list[tuple[str, list[str]]]:
    if kind in ("executive_brief", "one_page_brief"):
        e = ctx.get("exec") or {}
        f = e.get("fleet", {})
        r = ctx.get("roi") or {}
        last, prev = e.get("downtime_last", {}), e.get("downtime_prev", {})
        secs = [
            ("Problem", [
                f"Synthetic fleet of {f.get('total_aircraft', '?')} aircraft: {f.get('available_pct', '?')}% in service, {f.get('aog_count', '?')} AOG, {f.get('open_work_orders', '?')} open work orders.",
                f"Downtime per aircraft-day {last.get('hours_per_aircraft_day', 0):.3f} h in {last.get('month', '?')} vs {prev.get('hours_per_aircraft_day', 0):.3f} h in {prev.get('month', '?')}.",
                f"Legacy landscape: {e.get('legacy', {}).get('systems', '?')} systems, {e.get('legacy', {}).get('high', '?')} high-severity findings, {e.get('legacy', {}).get('unknowns', '?')} open unknowns.",
                "Evidence is spread across ERP, MRO, a legacy database, nightly CSV files and a document library that disagree."]),
            ("Proposed value", [
                "Read-only API and MCP bridges give agents verified data without rewriting the core.",
                "Agent workflows assemble evidence, options and drafts; humans approve every consequential action.",
                f"Governance is executable: {e.get('denied_actions', 0)} denied actions recorded with policy IDs and a hash-chained audit log."]),
        ]
        if r:
            lo, hi = r["annual_benefit"]["low"]["total"], r["annual_benefit"]["high"]["total"]
            secs.append(("Assumption-based value model", [
                f"Modeled annual benefit range ${lo:,} - ${hi:,}; first-year cost ${r['first_year_cost']:,}.",
                f"Payback (modeled): {r['payback_months']['high_case']} - {r['payback_months']['low_case']} months.",
                *r["formulas"], r["disclaimer"]]))
        secs.append(("90-day pilot roadmap", [f"{p['phase']} (owner: {p['owner']}): " + "; ".join(p["items"]) + f". Exit: {p['exit']}" for p in ctx.get("roadmap", [])]))
        secs.append(("Risks and open gaps", [
            "Unknowns U1-U5 (consumers of legacy tables, CDC permission, ERP/IFS access, inventory system of record, /admin/sql owner).",
            "This demo is not accredited for controlled or classified data; production needs enterprise IdP, hardened hosting and formal review.",
            "No live IFS connection was tested; any ERP integration must use documented, licensed APIs."]))
        secs.append(("Confidence", ["Medium for architecture direction (evidence-backed); low for financial figures until validated with customer data."]))
        if kind == "one_page_brief":
            return secs[:2] + secs[-3:-1]
        return secs
    if kind == "architecture":
        return [("Trust chain", ["User -> UI -> FastAPI (identity, envelope) -> intent router -> workflow engine -> tool gateway (policy deny-by-default) -> tools / MCP -> typed adapters -> synthetic systems",
                                 "Policy engine is deterministic Python; no model participates in decisions.",
                                 "Audit log is hash-chained (tamper-evident, not tamper-proof)."]),
                ("Components", ["React + Vite UI", "FastAPI backend", "SQLite + FTS5", "MCP server (official Python SDK)", "ReportLab PDF"])]
    if kind == "demo_script":
        return [("Act 1 - Legacy Transformation (2 min)", ["Open Legacy X-Ray, import bundled MRO schema and nightly CSV.", "Show dependencies, hotspots, unknowns.", "Generate safe read-only bridge; run contract tests; explain strangler + ACL."]),
                ("Act 2 - Operational AI (2 min)", ["Ask the AC-204 investigation question.", "Walk the agent timeline, citations, charts and the pending approval.", "Change the lead time and re-run the scenario comparison."]),
                ("Act 3 - Defense Trust (1 min)", ["Ask to export restricted records to personal e-mail.", "Show DENY, POL-004, tool invocation count 0, audit event.", "Approve the work order as a different persona; execute; replay is rejected."]),
                ("Act 4 - Executive Value (1 min)", ["Ask for the 90-day pitch.", "Show roadmap, ROI assumptions and download the brief."])]
    return [("Content", [json.dumps(ctx, default=str)[:4000]])]


def _md(title: str, secs: list[tuple[str, list[str]]]) -> str:
    out = [f"# {title}", "", f"_Flying_Florina | generated {now_iso()} | data as of {DEMO_TODAY}_", "", f"> {DISCLAIMER}", ""]
    for h, items in secs:
        out += [f"## {h}", ""] + [f"- {i}" for i in items] + [""]
    return "\n".join(out)


def _html(title: str, secs: list[tuple[str, list[str]]]) -> str:
    body = "".join(f"<h2>{html.escape(h)}</h2><ul>" + "".join(f"<li>{html.escape(i)}</li>" for i in items) + "</ul>" for h, items in secs)
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title>"
            "<style>body{font-family:system-ui,sans-serif;max-width:860px;margin:2rem auto;color:#0B1230;line-height:1.5}"
            "h1{color:#5C35B7}h2{color:#0B1230;border-bottom:2px solid #D7B46A;padding-bottom:.2rem}"
            ".d{background:#F7F8FC;border-left:4px solid #5C35B7;padding:.6rem;font-size:.85rem}"
            "@media print{body{margin:0}}</style></head><body>"
            f"<h1>{html.escape(title)}</h1><p class='d'>{html.escape(DISCLAIMER)}</p>{body}"
            f"<p style='font-size:.8rem;color:#555'>Generated {now_iso()} - Independent concept demo | Not affiliated with or endorsed by IFS</p></body></html>")


def _pdf(title: str, secs: list[tuple[str, list[str]]]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=title, author="Flying_Florina (synthetic demo)")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], textColor=colors.HexColor("#5C35B7"), fontSize=20, alignment=0)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=colors.HexColor("#0B1230"))
    small = ParagraphStyle("s", parent=ss["Normal"], fontSize=8, textColor=colors.HexColor("#444444"), backColor=colors.HexColor("#F7F8FC"), borderPadding=4)
    body = ParagraphStyle("b", parent=ss["Normal"], fontSize=9.5, leading=13)
    flow = [Paragraph(html.escape(title), h1), Paragraph(f"Flying_Florina | data as of {DEMO_TODAY}", ss["Normal"]), Spacer(1, 4),
            Paragraph(html.escape(DISCLAIMER), small), Spacer(1, 8)]
    for h, items in secs:
        flow.append(Paragraph(html.escape(h), h2))
        flow.append(ListFlowable([ListItem(Paragraph(html.escape(i), body), leftIndent=10) for i in items], bulletType="bullet", start="-"))
        flow.append(Spacer(1, 4))
    flow.append(Spacer(1, 10))
    flow.append(Paragraph("Independent concept demo | Not affiliated with or endorsed by IFS", small))
    doc.build(flow)
    return buf.getvalue()


def _workspace_sections(ctx: dict[str, Any]) -> list[tuple[str, list[str]]]:
    secs = [("Question", [ctx.get("query", "")]), ("Answer", [ctx.get("answer", "")])]
    if ctx.get("assumptions"):
        secs.append(("Assumptions", ctx["assumptions"]))
    cites = [f"{d['doc_id']} rev {d['revision']} ({d['effective_date']}, {d['status']}) - {d['title']}" for d in ctx.get("retrieved_docs", [])]
    if cites:
        secs.append(("Citations", cites))
    if ctx.get("warnings"):
        secs.append(("Warnings", ctx["warnings"]))
    pd = [f"{d['decision']} {d['action']} {d.get('tool') or d.get('resource')} ({d['policy_id']}): {d['reason']}" for d in ctx.get("policy_decisions", [])]
    if pd:
        secs.append(("Policy decisions", pd))
    return secs


def generate(actor: Actor, kind: str, fmt: str, context: dict[str, Any] | None = None, title: str | None = None) -> dict[str, Any]:
    if kind not in KINDS:
        raise ValueError(f"Unknown report kind '{kind}'")
    base_title, fmts = KINDS[kind]
    if fmt not in fmts:
        raise ValueError(f"Format '{fmt}' not available for {kind}; choose from {sorted(fmts)}")
    ctx = context or {}
    title = title or base_title
    if kind == "audit_packet":
        content: str | bytes = json.dumps({"generated": now_iso(), "disclaimer": DISCLAIMER, "verification": audit.verify(),
                                           "events": audit.export_chain()}, indent=1, default=str)
    elif kind == "evidence_manifest":
        content = json.dumps({"generated": now_iso(), "disclaimer": DISCLAIMER, "query": ctx.get("query"),
                              "evidence": ctx.get("evidence", []), "documents": [{k: d.get(k) for k in ("doc_id", "revision", "effective_date", "status", "provenance_sha256", "classification")} for d in ctx.get("retrieved_docs", [])],
                              "policy_decisions": ctx.get("policy_decisions", [])}, indent=1, default=str)
    elif kind == "work_orders":
        buf = io.StringIO()
        rows_ = db.query("SELECT id, aircraft_id, status, priority, opened, part_number, assigned_tech, source_system, classification FROM work_orders WHERE status != 'closed' AND classification != 'RESTRICTED' ORDER BY opened DESC")
        w = csv.DictWriter(buf, fieldnames=list(rows_[0].keys()) if rows_ else ["id"])
        w.writeheader()
        w.writerows(rows_)
        content = buf.getvalue()
    elif kind == "workspace":
        secs = _workspace_sections(ctx)
        content = json.dumps(ctx, indent=1, default=str) if fmt == "json" else _pdf(title, secs) if fmt == "pdf" else _html(title, secs) if fmt == "html" else _md(title, secs)
    else:
        secs = _sections(kind, ctx)
        content = _pdf(title, secs) if fmt == "pdf" else _html(title, secs) if fmt == "html" else _md(title, secs)

    rid = new_id("RPT")
    settings = get_settings()
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    path = settings.reports_dir / f"{rid}.{fmt}"
    raw = content if isinstance(content, bytes) else content.encode("utf-8")
    path.write_bytes(raw)
    import hashlib

    sha = hashlib.sha256(raw).hexdigest()
    label = LABEL.get(kind, "INTERNAL")
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO reports VALUES (?,?,?,?,?,?,?,?,?)", (rid, now_iso(), actor.id, kind, fmt, str(path), sha, label, title))
        audit.append(actor.id, "report.generated", f"{kind}.{fmt} {rid}", {"report_id": rid, "sha256": sha}, conn)
    return {"id": rid, "kind": kind, "fmt": fmt, "title": title, "sha256": sha, "bytes": len(raw), "classification": label,
            "download": f"/api/reports/{rid}/download"}


def get(report_id: str) -> dict[str, Any] | None:
    return db.query_one("SELECT * FROM reports WHERE id = ?", (report_id,))

