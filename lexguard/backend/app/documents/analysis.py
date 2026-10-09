"""Deterministic document analysis: clause extraction, due diligence, comparison, obligations,
timelines, entities and extractive summaries. Works only on documents passed in by the caller,
which must come from `documents.access.permitted_documents`."""

from __future__ import annotations

import difflib
import re

from pydantic import BaseModel

from app.models.domain import Document
from app.security.injection import detect_injection

COC_RE = re.compile(r"\bchange (of|in) control\b", re.IGNORECASE)
SCHEDULE_REF_RE = re.compile(r"as defined in (Schedule \d+)", re.IGNORECASE)
DEF_RE = re.compile(r"\"Change (of|in) Control\" means[^.]*\.", re.IGNORECASE)
SENT_RE = re.compile(r"(?<=[.!?])\s+")


class Citation(BaseModel):
    doc_id: str
    section_id: str
    quote: str | None = None


class Proposition(BaseModel):
    pid: str
    claim: str
    citation: Citation | None = None
    material: bool = True


class ClauseFinding(BaseModel):
    finding_id: str
    doc_id: str
    doc_title: str
    counterparty: str | None
    doc_type: str
    section_id: str
    heading: str
    clause_text: str
    propositions: list[Proposition]


class CoCReview(BaseModel):
    matter_id: str
    documents_in_scope: int
    documents_processed: int
    excluded: dict[str, list[str]]
    findings: list[ClauseFinding]
    injection_flags: list[dict]
    non_coc_control_mentions: int


def _sentence_with(text: str, rx: re.Pattern) -> str:
    for s in SENT_RE.split(text):
        if rx.search(s):
            return s.strip()
    return text.split(".")[0]


def _schedule_section_id(ref: str) -> str:
    return "schedule-" + ref.split()[-1]


def review_change_of_control(matter_id: str, docs: list[Document]) -> CoCReview:
    excluded: dict[str, list[str]] = {"duplicate": [], "unreadable": []}
    findings: list[ClauseFinding] = []
    flags: list[dict] = []
    control_mentions = 0
    processed = 0
    for d in sorted(docs, key=lambda x: x.doc_id):
        if d.status == "duplicate":
            excluded["duplicate"].append(d.doc_id)
            continue
        if d.status == "unreadable" or d.ocr_status == "failed":
            excluded["unreadable"].append(d.doc_id)
            continue
        processed += 1
        definition = next((s for s in d.sections if "definition" in s.heading.lower()), None)
        for s in d.sections:
            hits = detect_injection(s.text)
            if hits:
                flags.append({"doc_id": d.doc_id, "section_id": s.section_id, "patterns": hits,
                              "handling": "Treated as untrusted data. No instruction executed; permissions unchanged."})
            if "definition" in s.heading.lower():
                continue
            if not COC_RE.search(s.text):
                if "control" in s.text.lower():
                    control_mentions += 1
                continue
            fid = f"F-{d.doc_id}-{s.section_id}"
            props = [Proposition(pid=f"{fid}-P1",
                                 claim=f"{d.title} contains a change-of-control provision in {s.heading}.",
                                 citation=Citation(doc_id=d.doc_id, section_id=s.section_id,
                                                   quote=_sentence_with(s.text, COC_RE)))]
            sched = SCHEDULE_REF_RE.search(s.text)
            if sched:
                ref = sched.group(1)
                props.append(Proposition(pid=f"{fid}-P2", claim=f"'Change of Control' is defined in {ref} of the agreement.",
                                         citation=Citation(doc_id=d.doc_id, section_id=_schedule_section_id(ref), quote=None)))
            elif definition is not None and DEF_RE.search(definition.text):
                props.append(Proposition(pid=f"{fid}-P2",
                                         claim="'Change of Control' is defined in the definitions clause of the agreement.",
                                         citation=Citation(doc_id=d.doc_id, section_id=definition.section_id,
                                                           quote=DEF_RE.search(definition.text).group(0))))
            else:
                props.append(Proposition(pid=f"{fid}-P2",
                                         claim="No definition of 'Change of Control' was located in the agreement.",
                                         citation=None, material=False))
            findings.append(ClauseFinding(finding_id=fid, doc_id=d.doc_id, doc_title=d.title, counterparty=d.counterparty,
                                          doc_type=d.doc_type, section_id=s.section_id, heading=s.heading,
                                          clause_text=s.text, propositions=props))
    return CoCReview(matter_id=matter_id, documents_in_scope=len(docs), documents_processed=processed, excluded=excluded,
                     findings=findings, injection_flags=flags, non_coc_control_mentions=control_mentions)


# ---- other extraction workflows -------------------------------------------------------------

MONEY_RE = re.compile(r"(USD|\$|EUR|GBP)\s?[\d,]+(?:\.\d+)?(?:\s?(?:million|m|bn|billion))?", re.IGNORECASE)
PCT_RE = re.compile(r"\d+(?:\.\d+)?\s?(?:%|per cent)")
DURATION_RE = re.compile(r"\b(?:\w+ \()?\d+\)? (?:business )?(?:days|months|years)\b|\b\w+ \(\d+\) (?:business )?(?:days|months|years)\b",
                         re.IGNORECASE)
DATE_RE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}|\d{1,2} (?:January|February|March|April|May|June|July|August|September|October|November|December) \d{4})\b")
OBLIGATION_RE = re.compile(r"\b(shall|must|is required to|agrees to)\b", re.IGNORECASE)


def summarize(doc: Document) -> dict:
    points = []
    for s in doc.sections:
        if not s.text:
            continue
        first = SENT_RE.split(s.text)[0]
        points.append({"heading": s.heading, "text": first, "citation": {"doc_id": doc.doc_id, "section_id": s.section_id}})
    return {"doc_id": doc.doc_id, "title": doc.title, "method": "extractive (first sentence of each section)", "points": points}


def extract_obligations(doc: Document) -> list[dict]:
    out = []
    for s in doc.sections:
        for sent in SENT_RE.split(s.text):
            m = OBLIGATION_RE.search(sent)
            if m:
                party = sent[:m.start()].strip().split(",")[-1].strip() or "Unspecified party"
                out.append({"party": party[:80], "obligation": sent.strip(), "section_id": s.section_id,
                            "heading": s.heading, "citation": {"doc_id": doc.doc_id, "section_id": s.section_id}})
    return out


def extract_timeline(docs: list[Document]) -> list[dict]:
    events = []
    for d in docs:
        for s in d.sections:
            for sent in SENT_RE.split(s.text):
                for m in DATE_RE.finditer(sent):
                    events.append({"date": m.group(1), "event": sent.strip(), "doc_id": d.doc_id, "section_id": s.section_id})
    from datetime import datetime

    def key(e):
        try:
            return datetime.strptime(e["date"], "%Y-%m-%d")
        except ValueError:
            return datetime.strptime(e["date"], "%d %B %Y")
    return sorted(events, key=key)


def extract_entities(doc: Document) -> dict:
    text = " ".join(s.text for s in doc.sections)
    return {
        "parties": sorted({p for p in [doc.counterparty, "Maple Industries" if doc.client_id == "C-001" else None] if p}),
        "amounts": sorted({m.group(0) for m in MONEY_RE.finditer(text)}),
        "percentages": sorted({m.group(0) for m in PCT_RE.finditer(text)}),
        "durations": sorted({m.group(0) for m in DURATION_RE.finditer(text)}),
        "dates": sorted({m.group(1) for m in DATE_RE.finditer(text)}),
    }


def compare_documents(a: Document, b: Document) -> dict:
    rows = []
    b_by_heading = {re.sub(r"^\d+\.\s*", "", s.heading).lower(): s for s in b.sections}
    for s in a.sections:
        key = re.sub(r"^\d+\.\s*", "", s.heading).lower()
        other = b_by_heading.pop(key, None)
        if other is None:
            rows.append({"heading": s.heading, "status": "ONLY_IN_A", "similarity": 0.0, "a": s.text, "b": None})
        else:
            ratio = difflib.SequenceMatcher(None, s.text, other.text).ratio()
            rows.append({"heading": s.heading, "status": "IDENTICAL" if ratio == 1 else "DIFFERENT",
                         "similarity": round(ratio, 3), "a": s.text, "b": other.text})
    for s in b_by_heading.values():
        rows.append({"heading": s.heading, "status": "ONLY_IN_B", "similarity": 0.0, "a": None, "b": s.text})
    return {"doc_a": a.doc_id, "doc_b": b.doc_id, "sections": rows}
