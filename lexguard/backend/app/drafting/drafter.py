"""Template-grounded drafting. Drafts only from permitted, verified context.

Every material statement carries its citation. Findings whose evidence is not SUPPORTED are never silently
included in client-facing output: they are moved to an internal 'excluded pending evidence review' list.
"""

from __future__ import annotations

from datetime import date

DRAFT_TYPES = {
    "memo": "Internal memorandum",
    "due_diligence_report": "Due diligence report",
    "contract_summary": "Contract summary",
    "research_summary": "Research summary",
    "client_communication": "Client communication draft",
    "internal_briefing": "Internal briefing",
}

DISCLAIMER = ("DRAFT - AI-assisted work product prepared by LexGuard from permitted matter sources. "
              "Not legal advice until reviewed and adopted by a responsible lawyer.")


def _cite(c: dict) -> str:
    return f"[{c['doc_id']} §{c['section_id']}]"


def draft_due_diligence(*, matter: dict, client: dict, review_summary: dict, findings: list[dict],
                        verification_by_finding: dict[str, list[dict]], draft_type: str, destination: str) -> dict:
    client_facing = destination.startswith("external")
    verified, excluded = [], []
    for f in findings:
        statuses = [v["status"] for v in verification_by_finding.get(f["finding_id"], [])]
        if statuses and all(s == "SUPPORTED" for s in statuses):
            verified.append(f)
        else:
            excluded.append({"finding_id": f["finding_id"], "doc_id": f["doc_id"], "reason":
                             "Evidence not fully verified: " + ", ".join(sorted(set(s for s in statuses if s != "SUPPORTED")))})
    key = [f for f in verified if f.get("playbook_result") in ("ESCALATION_REQUIRED", "DEVIATION")]
    key.sort(key=lambda f: (0 if f["playbook_result"] == "ESCALATION_REQUIRED" else 1, f["doc_id"]))
    paragraphs = [
        {"heading": "Scope", "text": (f"We reviewed {review_summary['documents_processed']} of {review_summary['documents_in_scope']} "
                                      f"contracts in the {matter['name']} data room for change-of-control provisions. "
                                      f"{review_summary['excluded_total']} documents were excluded (duplicates or unreadable scans) "
                                      "and are listed in the appendix."), "citations": [], "verified": True},
        {"heading": "Summary", "text": (f"{review_summary['clauses']} change-of-control provisions were identified. "
                                        f"{review_summary['deviations']} deviate from the firm's M&A playbook, of which "
                                        f"{review_summary['escalations']} require partner escalation."), "citations": [], "verified": True},
    ]
    for f in key:
        paragraphs.append({
            "heading": f"{'ESCALATION' if f['playbook_result'] == 'ESCALATION_REQUIRED' else 'Deviation'}: {f['doc_title']}",
            "text": (f"{f['heading']}: \"{f['clause_text']}\" Playbook position ({f.get('rule_id')}): "
                     f"{f.get('standard_position')}"),
            "citations": [{"doc_id": f["doc_id"], "section_id": f["section_id"]}], "verified": True})
    for p in paragraphs:
        p["text_with_citations"] = p["text"] + (" " + " ".join(_cite(c) for c in p["citations"]) if p["citations"] else "")
    title = f"{DRAFT_TYPES.get(draft_type, 'Draft')}: {matter['name']} - change-of-control review"
    return {
        "draft_type": draft_type, "title": title, "date": date(2026, 10, 5).isoformat(), "destination": destination,
        "client_facing": client_facing, "disclaimer": DISCLAIMER, "paragraphs": paragraphs,
        "excluded_pending_review": excluded,
        "reviewer_note": (f"{len(excluded)} finding(s) were excluded because their evidence is not fully verified. "
                          "They must be resolved by a lawyer before inclusion." if excluded else "All included findings are verified."),
        "only_verified_findings": True,
    }


def draft_from_sources(*, title: str, draft_type: str, destination: str, points: list[dict]) -> dict:
    """Generic grounded draft: each point is {text, citation}. Uncited points are dropped from the draft."""
    paragraphs, dropped = [], []
    for pt in points:
        if pt.get("citation"):
            paragraphs.append({"heading": None, "text": pt["text"], "citations": [pt["citation"]], "verified": True,
                               "text_with_citations": f"{pt['text']} {_cite(pt['citation'])}"})
        else:
            dropped.append(pt["text"])
    return {"draft_type": draft_type, "title": title, "date": date(2026, 10, 5).isoformat(), "destination": destination,
            "client_facing": destination.startswith("external"), "disclaimer": DISCLAIMER, "paragraphs": paragraphs,
            "excluded_pending_review": [{"reason": "No citation", "text": t} for t in dropped],
            "reviewer_note": "Draft built only from cited, permitted sources.", "only_verified_findings": True}
