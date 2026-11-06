"""Role-based permissions. Enforced in the backend for every route."""
from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    SPECIALIST = "specialist"
    NETWORK_ANALYST = "network_analyst"
    FIELD_COORDINATOR = "field_coordinator"
    SUPERVISOR = "supervisor"
    AUDITOR = "auditor"


class Perm(str, Enum):
    CASE_READ = "case:read"
    CASE_CREATE = "case:create"
    CASE_INVESTIGATE = "case:investigate"
    CASE_CLARIFY = "case:clarify"
    CASE_CANCEL = "case:cancel"
    EVIDENCE_READ = "evidence:read"
    CUSTOMER_CONTACT_READ = "customer_contact:read"
    RECOMMENDATION_READ = "recommendation:read"
    APPROVAL_DECIDE = "approval:decide"
    ACTION_EXECUTE = "action:execute"
    RECOVERY_VERIFY = "recovery:verify"
    AUDIT_READ = "audit:read"
    EVAL_READ = "evaluation:read"
    EVAL_RUN = "evaluation:run"
    DASHBOARD_READ = "dashboard:read"
    KNOWLEDGE_READ = "knowledge:read"


ROLE_PERMISSIONS: dict[Role, frozenset[Perm]] = {
    Role.SPECIALIST: frozenset(
        {
            Perm.CASE_READ, Perm.CASE_CREATE, Perm.CASE_INVESTIGATE, Perm.CASE_CLARIFY,
            Perm.CASE_CANCEL, Perm.EVIDENCE_READ, Perm.CUSTOMER_CONTACT_READ,
            Perm.RECOMMENDATION_READ, Perm.APPROVAL_DECIDE, Perm.ACTION_EXECUTE,
            Perm.RECOVERY_VERIFY, Perm.DASHBOARD_READ, Perm.KNOWLEDGE_READ,
        }
    ),
    Role.NETWORK_ANALYST: frozenset(
        {
            Perm.CASE_READ, Perm.CASE_INVESTIGATE, Perm.EVIDENCE_READ,
            Perm.RECOMMENDATION_READ, Perm.APPROVAL_DECIDE, Perm.ACTION_EXECUTE,
            Perm.RECOVERY_VERIFY, Perm.DASHBOARD_READ, Perm.KNOWLEDGE_READ,
        }
    ),
    Role.FIELD_COORDINATOR: frozenset(
        {
            Perm.CASE_READ, Perm.EVIDENCE_READ, Perm.RECOMMENDATION_READ,
            Perm.ACTION_EXECUTE, Perm.RECOVERY_VERIFY, Perm.KNOWLEDGE_READ,
        }
    ),
    Role.SUPERVISOR: frozenset(
        {
            Perm.CASE_READ, Perm.CASE_CREATE, Perm.CASE_INVESTIGATE, Perm.CASE_CLARIFY,
            Perm.CASE_CANCEL, Perm.EVIDENCE_READ, Perm.CUSTOMER_CONTACT_READ,
            Perm.RECOMMENDATION_READ, Perm.APPROVAL_DECIDE, Perm.ACTION_EXECUTE,
            Perm.RECOVERY_VERIFY, Perm.AUDIT_READ, Perm.EVAL_READ, Perm.EVAL_RUN,
            Perm.DASHBOARD_READ, Perm.KNOWLEDGE_READ,
        }
    ),
    # Auditors: read-only. No customer contact fields, no mutations.
    Role.AUDITOR: frozenset(
        {Perm.CASE_READ, Perm.EVIDENCE_READ, Perm.RECOMMENDATION_READ, Perm.AUDIT_READ,
         Perm.EVAL_READ, Perm.DASHBOARD_READ}
    ),
}


def has_perm(role: str, perm: Perm) -> bool:
    try:
        return perm in ROLE_PERMISSIONS[Role(role)]
    except ValueError:
        return False
