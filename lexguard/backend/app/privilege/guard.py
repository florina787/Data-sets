"""PrivilegeGuard - flags POTENTIAL privilege / confidentiality risks for lawyer review.

It never makes a definitive privilege determination."""

from __future__ import annotations

import re

from pydantic import BaseModel

PRIVILEGE_PATTERNS = [
    (r"\bprivileged\b", "Marked privileged"),
    (r"attorney[- ]client", "Attorney-client communication indicator"),
    (r"(attorney )?work product", "Work-product indicator"),
    (r"in anticipation of litigation", "Prepared in anticipation of litigation"),
    (r"legal advice", "Legal advice indicator"),
    (r"without prejudice", "Settlement communication (without prejudice)"),
]
_PRIV = [(re.compile(p, re.IGNORECASE), label) for p, label in PRIVILEGE_PATTERNS]


class PrivilegeFlag(BaseModel):
    flag_type: str
    label: str = "POTENTIAL PRIVILEGE RISK"
    severity: str
    doc_id: str | None = None
    detail: str
    requires_lawyer_review: bool = True


def scan_text(text: str) -> list[str]:
    return [label for rx, label in _PRIV if rx.search(text or "")]


def evaluate(*, active_matter_id: str | None, active_client_id: str | None, destination: str,
             sources: list[dict]) -> list[PrivilegeFlag]:
    """sources: dicts with doc_id, matter_id, client_id, sensitivity, text, title."""
    flags: list[PrivilegeFlag] = []
    external = destination.startswith("external")
    for s in sources:
        indicators = scan_text(f"{s.get('title', '')} {s.get('text', '')}")
        if indicators or s.get("sensitivity") == "privileged":
            flags.append(PrivilegeFlag(
                flag_type="POTENTIAL_PRIVILEGE", severity="HIGH" if external else "MEDIUM", doc_id=s.get("doc_id"),
                label="POTENTIAL PRIVILEGE RISK",
                detail=("Indicators: " + ", ".join(indicators or ["sensitivity label 'privileged'"]) +
                        ". This is not a privilege determination; a lawyer must review.")))
        if s.get("matter_id") and active_matter_id and s["matter_id"] != active_matter_id:
            flags.append(PrivilegeFlag(flag_type="CROSS_MATTER_EXPOSURE", severity="CRITICAL", doc_id=s.get("doc_id"),
                                       label="CROSS-MATTER EXPOSURE", detail="Source belongs to a different matter."))
        if s.get("client_id") and active_client_id and s["client_id"] != active_client_id:
            flags.append(PrivilegeFlag(flag_type="CROSS_CLIENT_EXPOSURE", severity="CRITICAL", doc_id=s.get("doc_id"),
                                       label="CROSS-CLIENT EXPOSURE", detail="Source belongs to a different client."))
        if s.get("sensitivity") in ("highly_confidential",) and external:
            flags.append(PrivilegeFlag(flag_type="CONFIDENTIALITY", severity="HIGH", doc_id=s.get("doc_id"),
                                       label="CONFIDENTIALITY CONCERN",
                                       detail="Highly confidential source referenced in output intended for external delivery."))
    if external and flags:
        flags.append(PrivilegeFlag(flag_type="EXTERNAL_SHARING", severity="HIGH", label="EXTERNAL-SHARING CONCERN",
                                   detail="Output is intended for external delivery and contains flagged material."))
    return flags
