"""Guardrail: grounding, citation validation, sensitive-data redaction and confidence."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage

from app.agents.evidence import CITATION_RE, EvidenceIndex
from app.agents.response_agent import INSUFFICIENT_EVIDENCE
from app.graph.state import CopilotState
from app.guardrails.sensitive_data import redact_sensitive
from app.models.domain import GuardrailReport
from app.rag.text_utils import content_tokens, extract_numbers, split_sentences, stem

logger = logging.getLogger(__name__)

# Words that frame an answer rather than assert facts; they are not expected in evidence.
_FRAMING_WORDS = {
    stem(w)
    for w in """evidence highlights following priorities week drive resolution answer findings recommended
    actions based identified derived available specific additional best match directory employee
    retrieved sources source major key reported narrative point direction broadly consistent outside
    targets target there open issues release blockers story points peak latest from with against""".split()
}
_MIN_CLAIM_TOKENS = 4
_SUPPORT_THRESHOLD = 0.6


@dataclass(frozen=True)
class GuardrailOutcome:
    final_answer: str
    report: GuardrailReport
    confidence: float


def _strip_markup(text: str) -> str:
    text = CITATION_RE.sub("", text)
    text = re.sub(r"\(\d\)\s*", "", text)  # list ordinals such as "(1)"
    return re.sub(r"[*_`>#]", "", text).strip()


def _sections(body: str) -> dict[str, str]:
    """Split the markdown answer into its '### ' sections."""
    parts: dict[str, str] = {}
    current = "answer"
    buf: list[str] = []
    for line in body.splitlines():
        heading = re.match(r"^#{2,4}\s+(.+)$", line.strip())
        if heading:
            parts[current] = "\n".join(buf)
            current, buf = heading.group(1).strip().lower(), []
        else:
            buf.append(line)
    parts[current] = "\n".join(buf)
    return parts


class GuardrailValidator:
    """Validates a draft answer against the evidence it was built from."""

    def __init__(self, confidence_threshold: float, corporate_email_domain: str | None) -> None:
        self.confidence_threshold = confidence_threshold
        self.corporate_email_domain = corporate_email_domain

    def validate(self, draft: str, index: EvidenceIndex, errors: list[str] | None = None) -> GuardrailOutcome:
        errors = errors or []
        report = GuardrailReport()

        if not draft.strip() or draft.strip() == INSUFFICIENT_EVIDENCE or index.is_empty:
            report.passed = False
            report.needs_more_information = True
            report.issues.append("No supporting evidence was found for this question.")
            text = draft.strip() or INSUFFICIENT_EVIDENCE
            return GuardrailOutcome(redact_sensitive(text, self.corporate_email_domain).text, report, 0.05)

        # Redact first so nothing downstream (including quoted claims) can leak sensitive data.
        redaction = redact_sensitive(draft, self.corporate_email_domain)
        draft = redaction.text
        sections = _sections(draft)
        body_without_sources = "\n".join(v for k, v in sections.items() if k != "sources")

        # 1. Citations: every marker must refer to real evidence.
        markers = CITATION_RE.findall(body_without_sources)
        valid = [m for m in markers if m in index.labels]
        report.invalid_citations = sorted({m for m in markers if m not in index.labels})
        report.citation_validity = round(len(valid) / len(markers), 3) if markers else 0.0
        if not markers:
            report.issues.append("Answer makes factual statements without citing any source.")
        if report.invalid_citations:
            report.issues.append(f"Citations not backed by evidence: {', '.join(report.invalid_citations)}")

        # 2. Grounding: factual statements must be supported by evidence tokens and numbers.
        corpus = index.corpus()
        corpus_tokens = content_tokens(corpus)
        corpus_numbers = extract_numbers(corpus)
        claims_checked = 0
        supported = 0
        for name, text in sections.items():
            if name == "sources":
                continue
            factual = not name.startswith("recommended")
            for sentence in split_sentences(text):
                claim = _strip_markup(sentence)
                tokens = content_tokens(claim) - _FRAMING_WORDS
                numbers = extract_numbers(claim)
                missing_numbers = numbers - corpus_numbers
                if not factual:
                    if missing_numbers:
                        report.unsupported_claims.append(claim)
                    continue
                if len(tokens) < _MIN_CLAIM_TOKENS and not numbers:
                    continue
                claims_checked += 1
                ratio = len(tokens & corpus_tokens) / len(tokens) if tokens else 1.0
                if ratio >= _SUPPORT_THRESHOLD and not missing_numbers:
                    supported += 1
                else:
                    report.unsupported_claims.append(claim)
        report.grounding_score = round(supported / claims_checked, 3) if claims_checked else 0.0
        if report.unsupported_claims:
            report.issues.append(f"{len(report.unsupported_claims)} statement(s) could not be verified against the evidence.")

        # 3. Sensitive data (redacted above).
        report.redactions = redaction.redactions
        if redaction.redactions:
            report.issues.append(f"Sensitive data redacted: {', '.join(redaction.redactions)}")

        # 4. Confidence.
        confidence = self._confidence(index, report, errors)
        report.needs_more_information = confidence < self.confidence_threshold
        report.passed = not report.needs_more_information and not report.invalid_citations

        final = draft
        if report.invalid_citations:
            final = re.sub(
                r"\[(" + "|".join(map(re.escape, report.invalid_citations)) + r")\]", "", final
            )
        if report.needs_more_information:
            final = (
                f"> ⚠️ **Low confidence ({confidence:.0%}).** More information is required to answer this "
                "reliably; treat the points below as provisional.\n\n" + final
            )
        if report.unsupported_claims:
            listed = "\n".join(f">  - {c[:160]}" for c in report.unsupported_claims[:5])
            final += (
                f"\n\n> 🛡️ **Guardrail note:** {len(report.unsupported_claims)} statement(s) could not be fully "
                f"verified against the sources:\n{listed}"
            )
        return GuardrailOutcome(final, report, confidence)

    @staticmethod
    def _confidence(index: EvidenceIndex, report: GuardrailReport, errors: list[str]) -> float:
        doc_strength = 0.0
        if index.chunks:
            top = sorted((c.score for c in index.chunks), reverse=True)[:3]
            doc_strength = min(1.0, (sum(top) / len(top)) / 0.45)
        tool_strength = 1.0 if any(r.success for r in index.tool_results) else 0.0
        evidence_strength = max(doc_strength, tool_strength)
        penalty = min(0.3, 0.1 * len(errors))
        score = 0.45 * report.grounding_score + 0.30 * evidence_strength + 0.25 * report.citation_validity - penalty
        return round(max(0.0, min(1.0, score)), 3)


class GuardrailNode:
    """LangGraph node wrapping :class:`GuardrailValidator`."""

    def __init__(self, validator: GuardrailValidator) -> None:
        self._validator = validator

    def __call__(self, state: CopilotState) -> dict[str, Any]:
        index = EvidenceIndex(state.get("retrieved_documents", []), state.get("tool_results", []))
        outcome = self._validator.validate(state.get("draft_answer", ""), index, state.get("errors", []))
        r = outcome.report
        return {
            "final_answer": outcome.final_answer,
            "messages": [AIMessage(content=outcome.final_answer)],
            "guardrail": r,
            "confidence": outcome.confidence,
            "_detail": (
                f"{'passed' if r.passed else 'flagged'}; grounding={r.grounding_score:.2f}; "
                f"confidence={outcome.confidence:.2f}; unsupported={len(r.unsupported_claims)}; "
                f"redactions={len(r.redactions)}"
            ),
        }
