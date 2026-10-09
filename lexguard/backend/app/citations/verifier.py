"""Deterministic citation verification.

For every material proposition returns SUPPORTED | PARTIALLY_SUPPORTED | UNSUPPORTED | SOURCE_NOT_FOUND.
Sources are resolved ONLY within the request's permitted scope; a citation to a document the user may not
see is reported as SOURCE_NOT_FOUND (its existence is not disclosed). Missing citations are never invented.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from app.access.matter_access import AccessScope
from app.models.domain import sensitivity_rank
from app.rag.index import tokenize
from app.services.data_store import DataStore

NUMBER_WORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8",
                "nine": "9", "ten": "10", "eleven": "11", "twelve": "12", "fifteen": "15", "twenty": "20", "thirty": "30",
                "sixty": "60", "ninety": "90", "hundred": "100"}
NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")
PLACEHOLDER_RE = re.compile(r"\[●\]|\[NTD|\[TBC|\[\s*\]|\[insert", re.IGNORECASE)
ABSOLUTES = {"always", "never", "all", "guaranteed", "certainly", "must"}


class VerificationResult(BaseModel):
    pid: str
    claim: str
    doc_id: str | None
    section_id: str | None
    quote: str | None
    status: str
    evidence_text: str | None
    source_title: str | None
    reasons: list[str]
    checks: dict


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w%$● ]+", " ", s.lower())).strip()


def _numbers(text: str) -> set[str]:
    nums = {n.replace(",", "") for n in NUM_RE.findall(text)}
    for w in re.findall(r"[a-z]+", text.lower()):
        if w in NUMBER_WORDS:
            nums.add(NUMBER_WORDS[w])
    return nums


def resolve_source(store: DataStore, scope: AccessScope, doc_id: str):
    doc = store.documents.get(doc_id)
    if doc is not None:
        if doc.matter_id not in scope.permitted_matter_ids or doc.access_label not in scope.permitted_labels:
            return None
        if sensitivity_rank(doc.sensitivity) > sensitivity_rank(scope.max_sensitivity):
            return None
        return doc
    k = store.knowledge.get(doc_id)
    if k is None or k.access_label not in scope.permitted_labels:
        return None
    if k.matter_id is not None and k.matter_id not in scope.permitted_matter_ids:
        return None
    if sensitivity_rank(k.sensitivity) > sensitivity_rank(scope.max_sensitivity):
        return None
    return k


def verify(store: DataStore, scope: AccessScope, pid: str, claim: str, citation: dict | None,
           strict_numbers: bool = True) -> VerificationResult:
    if not citation or not citation.get("doc_id"):
        return VerificationResult(pid=pid, claim=claim, doc_id=None, section_id=None, quote=None, status="UNSUPPORTED",
                                  evidence_text=None, source_title=None,
                                  reasons=["No citation provided. LexGuard does not invent citations."],
                                  checks={"citation_present": False})
    doc_id, section_id, quote = citation.get("doc_id"), citation.get("section_id"), citation.get("quote")
    doc = resolve_source(store, scope, doc_id)
    if doc is None:
        return VerificationResult(pid=pid, claim=claim, doc_id=doc_id, section_id=section_id, quote=quote,
                                  status="SOURCE_NOT_FOUND", evidence_text=None, source_title=None,
                                  reasons=["Cited source does not exist in the permitted corpus for this matter."],
                                  checks={"citation_present": True, "source_found": False})
    section = doc.section(section_id) if section_id else None
    if section is None or not section.text.strip():
        return VerificationResult(pid=pid, claim=claim, doc_id=doc_id, section_id=section_id, quote=quote,
                                  status="SOURCE_NOT_FOUND", evidence_text=None, source_title=doc.title,
                                  reasons=[f"Cited section '{section_id}' was not found in {doc_id}."],
                                  checks={"citation_present": True, "source_found": True, "section_found": False})
    context = f"{doc.title} {section.heading} {section.text}"
    quote_found = bool(quote) and _norm(quote) in _norm(section.text)
    claim_tokens = set(tokenize(claim))
    overlap = len(claim_tokens & set(tokenize(context))) / max(1, len(claim_tokens))
    claim_nums = _numbers(claim)
    missing_nums = sorted(claim_nums - _numbers(context))
    numbers_ok = not missing_nums if strict_numbers else True
    unsupported_absolutes = sorted({w for w in re.findall(r"[a-z]+", claim.lower()) if w in ABSOLUTES}
                                   - set(re.findall(r"[a-z]+", context.lower())))
    placeholder = bool(PLACEHOLDER_RE.search(section.text))
    reasons: list[str] = []
    if placeholder:
        reasons.append("Cited source text contains a drafting placeholder; the source is incomplete.")
    if missing_nums:
        reasons.append(f"Figures in the claim not found in the source: {', '.join(missing_nums)}.")
    if unsupported_absolutes:
        reasons.append(f"Claim uses absolute language not present in the source: {', '.join(unsupported_absolutes)}.")
    if quote and not quote_found:
        reasons.append("Quoted text was not located in the cited section.")
    if overlap < 0.5:
        reasons.append(f"Low term overlap between claim and source ({overlap:.0%}).")

    if quote_found and numbers_ok and overlap >= 0.5 and not unsupported_absolutes and not placeholder:
        status = "SUPPORTED"
        reasons = ["Quote located in cited section; claim terms and figures match the source."]
    elif quote_found or (overlap >= 0.6 and numbers_ok):
        status = "PARTIALLY_SUPPORTED"
        if not reasons:
            reasons.append("Claim paraphrases the source but the exact quote was not provided.")
    else:
        status = "UNSUPPORTED"
    return VerificationResult(pid=pid, claim=claim, doc_id=doc_id, section_id=section_id, quote=quote, status=status,
                              evidence_text=section.text, source_title=doc.title, reasons=reasons,
                              checks={"citation_present": True, "source_found": True, "section_found": True,
                                      "quote_found": quote_found, "term_overlap": round(overlap, 3),
                                      "numbers_ok": numbers_ok, "placeholder": placeholder,
                                      "unsupported_absolutes": unsupported_absolutes})


def summarize_results(results: list[VerificationResult]) -> dict:
    counts = {k: 0 for k in ("SUPPORTED", "PARTIALLY_SUPPORTED", "UNSUPPORTED", "SOURCE_NOT_FOUND")}
    for r in results:
        counts[r.status] += 1
    return {"total": len(results), **counts,
            "issues": counts["PARTIALLY_SUPPORTED"] + counts["UNSUPPORTED"] + counts["SOURCE_NOT_FOUND"]}


def verify_batch(store: DataStore, scope: AccessScope, propositions: list[dict], strict_numbers: bool = True) -> list[dict]:
    """Verify a list of propositions in one governed tool call. Keeps `finding_id` when present."""
    out = []
    for p in propositions:
        if not p.get("material", True):
            continue
        d = verify(store, scope, p["pid"], p["claim"], p.get("citation"), strict_numbers=strict_numbers).model_dump()
        if p.get("finding_id"):
            d["finding_id"] = p["finding_id"]
        out.append(d)
    return out
