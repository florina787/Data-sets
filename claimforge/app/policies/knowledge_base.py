"""Local policy knowledge base: loads synthetic policy markdown and chunks by section.

Chunking strategy: one chunk per ``### <section-id> <title>`` subsection, carrying the
document id, section id, parent section and title so every retrieval result is citable.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.config.settings import SYNTHETIC_DATA_DIR
from app.models.domain import Policy, PolicySection
from app.security.sanitizer import screen_text

_SECTION_RE = re.compile(r"^###\s+([A-Z]-\d+(?:\.\d+)?)\s+(.+)$")
_PARENT_RE = re.compile(r"^##\s+([A-Z]-\d+)\s+(.+)$")
_DOC_ID_RE = re.compile(r"^Document-ID:\s*(\S+)", re.MULTILINE)
_VERSION_RE = re.compile(r"^Version:\s*(\S+)", re.MULTILINE)


def parse_policy_markdown(text: str, fallback_doc_id: str) -> Policy:
    title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    doc_id = (_DOC_ID_RE.search(text).group(1) if _DOC_ID_RE.search(text) else fallback_doc_id)
    version = _VERSION_RE.search(text).group(1) if _VERSION_RE.search(text) else "unversioned"
    sections: list[PolicySection] = []
    parent: str | None = None
    current: dict | None = None

    def flush() -> None:
        if current and current["lines"]:
            sections.append(PolicySection(doc_id=doc_id, section_id=current["id"], title=current["title"],
                                          text=" ".join(current["lines"]).strip(), parent_section=parent))

    for line in text.splitlines():
        if m := _PARENT_RE.match(line):
            flush()
            current = None
            parent = m.group(1)
            continue
        if m := _SECTION_RE.match(line):
            flush()
            current = {"id": m.group(1), "title": m.group(2).strip(), "lines": []}
            continue
        if current is not None and line.strip() and not line.startswith(">"):
            current["lines"].append(line.strip())
    flush()
    return Policy(doc_id=doc_id, title=title_match.group(1).strip() if title_match else doc_id,
                  version=version, sections=sections)


class PolicyKnowledgeBase:
    """In-memory store of policy documents and their section chunks."""

    def __init__(self) -> None:
        self.policies: dict[str, Policy] = {}
        self.quarantined: list[dict] = []

    @classmethod
    def from_directory(cls, directory: Path | None = None) -> "PolicyKnowledgeBase":
        kb = cls()
        directory = directory or (SYNTHETIC_DATA_DIR / "policies")
        for path in sorted(directory.glob("*.md")):
            kb.add_text(path.read_text(encoding="utf-8"), path.stem, trusted=True)
        return kb

    def add_text(self, text: str, fallback_doc_id: str, *, trusted: bool = False) -> dict:
        """Add a document. Untrusted documents are screened; instruction-like lines are quarantined."""
        report = {"doc_id": None, "sections": 0, "quarantined_lines": []}
        if not trusted:
            screened = screen_text(text)
            if screened.flagged:
                report["quarantined_lines"] = screened.matches
                self.quarantined.append({"doc": fallback_doc_id, "lines": screened.matches})
            text = screened.cleaned_text
        policy = parse_policy_markdown(text, fallback_doc_id)
        if not trusted and not policy.doc_id.startswith("UPLOAD-"):
            # Uploaded docs can never shadow the curated synthetic policy ids.
            policy = policy.model_copy(update={"doc_id": f"UPLOAD-{policy.doc_id}"[:60],
                                               "sections": [s.model_copy(update={"doc_id": f"UPLOAD-{s.doc_id}"[:60]})
                                                            for s in policy.sections]})
        self.policies[policy.doc_id] = policy
        report["doc_id"] = policy.doc_id
        report["sections"] = len(policy.sections)
        return report

    @property
    def sections(self) -> list[PolicySection]:
        return [s for p in self.policies.values() for s in p.sections]

    def get_section(self, section_id: str) -> PolicySection | None:
        for s in self.sections:
            if s.section_id == section_id:
                return s
        return None
