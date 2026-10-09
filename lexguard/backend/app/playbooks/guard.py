"""PlaybookGuard - deterministic comparison of clauses and AI recommendations against practice playbooks."""

from __future__ import annotations

from pydantic import BaseModel

from app.models.domain import Playbook, PlaybookRule
from app.rag.index import tokenize

PRIORITY = {"ESCALATION_REQUIRED": 0, "DEVIATION": 1, "ALIGNED": 2}


class PlaybookResult(BaseModel):
    subject_id: str
    subject_text: str
    result: str  # ALIGNED | DEVIATION | ESCALATION_REQUIRED | NO_MATCHING_RULE
    rule_id: str | None
    topic: str | None
    standard_position: str | None
    playbook_id: str
    playbook_version: str
    source_doc_id: str
    source_section_id: str | None
    explanation: str


def _ordered(playbook: Playbook) -> list[PlaybookRule]:
    return sorted(playbook.rules, key=lambda r: PRIORITY[r.result])


def classify_clause(playbook: Playbook, subject_id: str, text: str) -> PlaybookResult:
    low = text.lower()
    for rule in _ordered(playbook):
        if not rule.clause_patterns:
            continue
        if any(p in low for p in rule.clause_patterns) and not any(x in low for x in rule.exclude_patterns):
            return PlaybookResult(subject_id=subject_id, subject_text=text, result=rule.result, rule_id=rule.rule_id,
                                  topic=rule.topic, standard_position=rule.standard_position,
                                  playbook_id=playbook.playbook_id, playbook_version=playbook.version,
                                  source_doc_id=playbook.source_doc_id, source_section_id=rule.section_id,
                                  explanation=f"Clause matches playbook rule {rule.rule_id} ({rule.topic}).")
    return PlaybookResult(subject_id=subject_id, subject_text=text, result="NO_MATCHING_RULE", rule_id=None, topic=None,
                          standard_position=None, playbook_id=playbook.playbook_id, playbook_version=playbook.version,
                          source_doc_id=playbook.source_doc_id, source_section_id=None,
                          explanation="No playbook rule matched; lawyer review required.")


def check_recommendation(playbook: Playbook, subject_id: str, text: str) -> PlaybookResult:
    """Compare an AI recommendation (not a clause) with the playbook position."""
    low = text.lower()
    for rule in _ordered(playbook):
        if any(p in low for p in rule.recommendation_patterns):
            res = rule.result if rule.result != "ALIGNED" else "ALIGNED"
            return PlaybookResult(subject_id=subject_id, subject_text=text, result=res, rule_id=rule.rule_id, topic=rule.topic,
                                  standard_position=rule.standard_position, playbook_id=playbook.playbook_id,
                                  playbook_version=playbook.version, source_doc_id=playbook.source_doc_id,
                                  source_section_id=rule.section_id,
                                  explanation=(f"Recommendation conflicts with playbook rule {rule.rule_id}: "
                                               f"{rule.standard_position}"))
    rec_tokens = set(tokenize(text))
    for rule in _ordered(playbook):
        if rule.result != "ALIGNED":
            continue
        for p in rule.clause_patterns:
            pt = set(tokenize(p))
            if pt and pt <= rec_tokens:
                return PlaybookResult(subject_id=subject_id, subject_text=text, result="ALIGNED", rule_id=rule.rule_id,
                                      topic=rule.topic, standard_position=rule.standard_position,
                                      playbook_id=playbook.playbook_id, playbook_version=playbook.version,
                                      source_doc_id=playbook.source_doc_id, source_section_id=rule.section_id,
                                      explanation=f"Recommendation is consistent with playbook rule {rule.rule_id}.")
    return PlaybookResult(subject_id=subject_id, subject_text=text, result="NO_MATCHING_RULE", rule_id=None, topic=None,
                          standard_position=None, playbook_id=playbook.playbook_id, playbook_version=playbook.version,
                          source_doc_id=playbook.source_doc_id, source_section_id=None,
                          explanation="No playbook rule addresses this recommendation; lawyer review required.")
