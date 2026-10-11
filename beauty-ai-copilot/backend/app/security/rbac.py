"""Server-side role permissions. The frontend persona selector only chooses *which seeded user*
the demo session acts as; every permission decision is made here."""
from __future__ import annotations

from app.errors import Forbidden

ROLES = {
    "product_owner": "Product owner",
    "domain_reviewer": "Beauty domain reviewer",
    "cv_engineer": "Computer-vision engineer",
    "ml_engineer": "ML engineer",
    "qa_engineer": "QA engineer",
    "privacy_reviewer": "Privacy reviewer",
    "release_manager": "Release manager",
    "ops_analyst": "Operations analyst",
}

PERMISSIONS: dict[str, set[str]] = {
    "change.create": {"product_owner"},
    "change.read": set(ROLES),
    "change.cancel": {"product_owner", "release_manager"},
    "clarification.answer": {"product_owner", "domain_reviewer", "ml_engineer", "qa_engineer", "privacy_reviewer", "release_manager"},
    "requirements.approve": {"product_owner"},
    "investigate.run": {"product_owner", "ml_engineer", "cv_engineer", "qa_engineer"},
    "impact.accept": {"product_owner", "ml_engineer"},
    "candidate.register": {"cv_engineer", "ml_engineer"},
    "evaluation.run": {"ml_engineer", "qa_engineer", "cv_engineer"},
    "evaluation.cancel": {"ml_engineer", "qa_engineer"},
    "review.code": {"ml_engineer", "qa_engineer", "cv_engineer"},
    "review.domain": {"domain_reviewer"},
    "review.privacy": {"privacy_reviewer"},
    "review.qa": {"qa_engineer"},
    "release.approve": {"release_manager"},
    "release.execute": {"release_manager"},
    "monitoring.read": set(ROLES),
    "monitoring.advance": {"ops_analyst", "release_manager"},
    "alert.investigate": {"ops_analyst", "ml_engineer"},
    "rollback.request": {"ops_analyst", "release_manager", "ml_engineer"},
    "rollback.approve": {"release_manager"},
    "audit.read": set(ROLES),
    "demo.reset": {"release_manager", "product_owner"},
    "image.upload": set(ROLES),
}


def has_permission(roles: list[str], permission: str) -> bool:
    return bool(set(roles) & PERMISSIONS.get(permission, set()))


def require(user, permission: str) -> None:
    if not has_permission(user.roles, permission):
        raise Forbidden("permission_denied", f"Role(s) {user.roles} lack permission '{permission}'.",
                        {"permission": permission, "allowed_roles": sorted(PERMISSIONS.get(permission, set()))})
