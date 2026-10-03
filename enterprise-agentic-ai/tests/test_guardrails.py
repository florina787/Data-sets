"""Guardrail: redaction, citation validation, grounding and confidence."""

from __future__ import annotations

from app.agents.evidence import EvidenceIndex
from app.agents.response_agent import INSUFFICIENT_EVIDENCE
from app.guardrails.sensitive_data import redact_sensitive
from app.guardrails.validator import GuardrailValidator
from app.models.domain import RetrievedChunk, ToolCallRecord

KEY_PREFIX = "sk-" + "ant-api03-"  # fake keys are assembled at runtime; none are real

CHUNK = RetrievedChunk(
    chunk_id="status#c001",
    document_id="status",
    filename="status.md",
    section="Executive Summary",
    text="Project Phoenix is 68 percent complete and remains AMBER for the October release.",
    score=0.6,
)
TOOL = ToolCallRecord(tool_name="get_project_status", result={"name": "Project Phoenix", "status": "AMBER", "percent_complete": 68})


def validator() -> GuardrailValidator:
    return GuardrailValidator(confidence_threshold=0.45, corporate_email_domain="novagrid.example")


def test_redacts_secrets_and_personal_data() -> None:
    text = (
        f"Key {KEY_PREFIX}abcdefghijklmnop, call +1 415 555 0134 or (212) 555-0199, "
        "SSN 123-45-6789, card 4111 1111 1111 1111, mail jane@gmail.com or maya.okafor@novagrid.example. "
        "Release 2026-10-28, PHX-214, budget 1.20 million."
    )
    result = redact_sensitive(text, "novagrid.example")
    assert "sk-ant" not in result.text
    assert "555" not in result.text
    assert "123-45-6789" not in result.text
    assert "4111" not in result.text
    assert "jane@gmail.com" not in result.text
    assert "maya.okafor@novagrid.example" in result.text  # work email allowed
    assert "2026-10-28" in result.text and "PHX-214" in result.text and "1.20" in result.text
    assert {r.split()[0] for r in result.redactions} >= {"api_key", "phone", "ssn", "payment_card", "personal_email"}


def test_grounded_answer_passes() -> None:
    draft = (
        "### Answer\nProject Phoenix remains AMBER and is 68 percent complete for the October release [S1].\n\n"
        "### Key Findings\n- Project Phoenix status is AMBER [T1]."
    )
    outcome = validator().validate(draft, EvidenceIndex([CHUNK], [TOOL]))
    assert outcome.report.passed
    assert outcome.report.grounding_score == 1.0
    assert outcome.report.citation_validity == 1.0
    assert outcome.confidence >= 0.8
    assert "Low confidence" not in outcome.final_answer


def test_invalid_citation_flagged_and_removed() -> None:
    draft = "### Answer\nProject Phoenix remains AMBER for the October release [S1][S9]."
    outcome = validator().validate(draft, EvidenceIndex([CHUNK], []))
    assert outcome.report.invalid_citations == ["S9"]
    assert not outcome.report.passed
    assert "[S9]" not in outcome.final_answer


def test_unsupported_claims_detected() -> None:
    draft = (
        "### Answer\nProject Phoenix remains AMBER for the October release [S1]. "
        "The vendor promised a refund of 250 thousand dollars next quarter [S1]."
    )
    outcome = validator().validate(draft, EvidenceIndex([CHUNK], []))
    assert any("refund" in c for c in outcome.report.unsupported_claims)
    assert "Guardrail note" in outcome.final_answer


def test_uncited_answer_gets_low_confidence() -> None:
    draft = "### Answer\nThe migration of the billing ledger finished early under budget with zero defects."
    outcome = validator().validate(draft, EvidenceIndex([CHUNK], []))
    assert outcome.report.needs_more_information
    assert "More information is required" in outcome.final_answer


def test_no_evidence_requires_more_information() -> None:
    outcome = validator().validate(INSUFFICIENT_EVIDENCE, EvidenceIndex([], []))
    assert outcome.confidence < 0.1
    assert outcome.report.needs_more_information
    assert "More information is required" in outcome.final_answer


def test_secret_in_draft_is_redacted() -> None:
    draft = f"### Answer\nProject Phoenix is AMBER [S1]. Use api_key={KEY_PREFIX}SECRETSECRETSECRET"
    outcome = validator().validate(draft, EvidenceIndex([CHUNK], []))
    assert "SECRETSECRET" not in outcome.final_answer
    assert outcome.report.redactions
