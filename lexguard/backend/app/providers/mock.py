"""MockLegalAIProvider - a local, deterministic stand-in for an external legal-AI platform.

It makes NO network calls and NO paid model calls. It returns structured results with an
explicit `simulated: true` marker so they are never mistaken for a real vendor response.
"""

from __future__ import annotations

import re

from app.providers.base import BaseLegalAIProvider

_COC = re.compile(r"\bchange (of|in) control\b", re.IGNORECASE)


class MockLegalAIProvider(BaseLegalAIProvider):
    provider_id = "P-MOCK-LEGAL-AI"
    external = True

    def __init__(self) -> None:
        self.calls: list[str] = []

    def _meta(self, op: str, units: int) -> dict:
        self.calls.append(op)
        return {"provider_id": self.provider_id, "operation": op, "simulated": True,
                "est_cost_usd": round(0.02 * max(1, units), 2), "network_calls": 0}

    def analyze_documents(self, documents: list[dict], instructions: str) -> dict:
        """Simulated clause detection over the minimised payload LexGuard chose to send."""
        clauses = []
        for d in documents:
            for s in d.get("sections", []):
                if "definition" in s["heading"].lower() or not _COC.search(s["text"]):
                    continue
                quote = next((x for x in re.split(r"(?<=[.!?])\s+", s["text"]) if _COC.search(x)), s["text"])
                clauses.append({"doc_id": d["doc_id"], "section_id": s["section_id"], "heading": s["heading"],
                                "clause_text": s["text"], "quote": quote.strip()})
        return {"clauses": clauses, "documents_received": len(documents),
                "instructions_received": instructions[:200], **self._meta("analyze_documents", len(documents))}

    def research(self, question: str, context: list[dict]) -> dict:
        return {"answer_points": [{"text": c["text"][:240], "citation": {"doc_id": c["doc_id"], "section_id": c["section_id"]}}
                                  for c in context[:3]], **self._meta("research", len(context))}

    def draft(self, draft_type: str, context: list[dict]) -> dict:
        return {"draft_type": draft_type, "paragraphs": [c["text"][:240] for c in context[:5]], **self._meta("draft", len(context))}

    def compare(self, a: dict, b: dict) -> dict:
        return {"a": a.get("doc_id"), "b": b.get("doc_id"), **self._meta("compare", 2)}

    def summarize(self, document: dict) -> dict:
        return {"doc_id": document.get("doc_id"), "summary": [s["text"].split(".")[0] for s in document.get("sections", [])],
                **self._meta("summarize", 1)}
