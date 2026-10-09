"""Role-based access control. Pure functions over static tables - no LLM involvement."""

from __future__ import annotations

from app.models.domain import Role, User

LAWYER_ROLES = {Role.PARTNER, Role.SENIOR_ASSOCIATE, Role.ASSOCIATE, Role.TRAINEE, Role.KNOWLEDGE_LAWYER}

PERMISSIONS: dict[str, set[Role]] = {
    "view_matter_content": {Role.PARTNER, Role.SENIOR_ASSOCIATE, Role.ASSOCIATE, Role.TRAINEE, Role.PARALEGAL, Role.KNOWLEDGE_LAWYER},
    "use_copilot": {Role.PARTNER, Role.SENIOR_ASSOCIATE, Role.ASSOCIATE, Role.TRAINEE, Role.PARALEGAL, Role.KNOWLEDGE_LAWYER},
    "request_external_provider": {Role.PARTNER, Role.SENIOR_ASSOCIATE, Role.ASSOCIATE},
    "approve_internal": {Role.PARTNER, Role.SENIOR_ASSOCIATE, Role.ASSOCIATE},
    "approve_external": {Role.PARTNER, Role.SENIOR_ASSOCIATE},
    "approve_escalation": {Role.PARTNER},
    "run_evaluation": {Role.AI_GOVERNANCE, Role.KNOWLEDGE_LAWYER, Role.ADMIN, Role.PARTNER},
    "analyze_policy_change": {Role.AI_GOVERNANCE, Role.KNOWLEDGE_LAWYER, Role.ADMIN, Role.PARTNER},
    "approve_policy_change": {Role.AI_GOVERNANCE},
    "promote_version": {Role.AI_GOVERNANCE},
    "view_all_audit": {Role.AI_GOVERNANCE, Role.ADMIN},
    "view_governance": {Role.AI_GOVERNANCE, Role.ADMIN, Role.PARTNER, Role.KNOWLEDGE_LAWYER, Role.SENIOR_ASSOCIATE, Role.ASSOCIATE},
}

# Highest document sensitivity a role may ever see (matter membership still required).
ROLE_MAX_SENSITIVITY: dict[Role, str | None] = {
    Role.PARTNER: "privileged", Role.SENIOR_ASSOCIATE: "privileged", Role.ASSOCIATE: "privileged",
    Role.KNOWLEDGE_LAWYER: "privileged", Role.PARALEGAL: "highly_confidential", Role.TRAINEE: "confidential",
    Role.AI_GOVERNANCE: "internal", Role.ADMIN: "internal",
}


def has_permission(user: User, permission: str) -> bool:
    return user.role in PERMISSIONS.get(permission, set())


def max_sensitivity(user: User) -> str | None:
    return ROLE_MAX_SENSITIVITY.get(user.role)
