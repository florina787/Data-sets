"""Matter access, ethical walls and the sealed retrieval scope.

Security property: an AccessScope can only be produced by `build_access_scope`, which runs the
deterministic checks. Retrieval refuses any scope that was not sealed by this module, so neither an
agent, an LLM nor document content can widen what is retrieved.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.access.rbac import LAWYER_ROLES, has_permission, max_sensitivity
from app.models.domain import Matter, Role, User
from app.services.data_store import DataStore

_SEAL = object()


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    code: str
    reason: str
    rule_id: str
    via: str | None = None  # named_team | practice_group


@dataclass(frozen=True)
class WallDecision:
    blocked: bool
    wall_id: str | None
    reason: str


@dataclass(frozen=True)
class AccessScope:
    user_id: str
    role: str
    matter_id: str | None
    client_id: str | None
    permitted_matter_ids: frozenset[str]
    permitted_labels: frozenset[str]
    max_sensitivity: str | None
    _seal: object = field(repr=False, compare=False, default=None)

    def is_sealed(self) -> bool:
        return self._seal is _SEAL


def check_matter_access(store: DataStore, user: User | None, matter: Matter | None) -> AccessDecision:
    if user is None:
        return AccessDecision(False, "UNKNOWN_USER", "User is not recognised.", "ACC-000")
    if matter is None:
        return AccessDecision(False, "UNKNOWN_MATTER", "Matter does not exist or is not visible.", "ACC-001")
    if not has_permission(user, "view_matter_content"):
        return AccessDecision(False, "ROLE_NOT_PERMITTED",
                              f"Role {user.role.value} does not grant access to matter content.", "ACC-002")
    if user.user_id in matter.authorized_users:
        return AccessDecision(True, "AUTHORIZED", "User is on the named matter team.", "ACC-003", via="named_team")
    if (matter.access_model == "practice_group" and user.practice_id == matter.practice_id
            and user.role in LAWYER_ROLES):
        return AccessDecision(True, "AUTHORIZED", "Matter access model grants practice-group lawyers access.", "ACC-004",
                              via="practice_group")
    return AccessDecision(False, "NOT_ON_MATTER_TEAM",
                          "User is not an authorised member of this matter.", "ACC-005")


def check_ethical_wall(store: DataStore, user: User | None, matter_id: str) -> WallDecision:
    if user is None:
        return WallDecision(True, None, "Unknown user.")
    for wall in store.walls_for(matter_id):
        if user.user_id in wall.screened_users:
            return WallDecision(True, wall.wall_id,
                                f"User is screened from this matter by ethical wall {wall.wall_id}.")
    return WallDecision(False, None, "No ethical wall applies to this user for this matter.")


def screened_matters(store: DataStore, user_id: str) -> set[str]:
    out: set[str] = set()
    for wall in store.ethical_walls:
        if user_id in wall.screened_users:
            out.update(wall.matter_ids)
    return out


def build_access_scope(store: DataStore, user: User, matter_id: str | None) -> AccessScope:
    """Compute the ONLY set of partitions retrieval may touch for this request.

    Retrieval is restricted to the active matter (never other matters, even ones the user can access)
    plus firm knowledge, practice knowledge and the active client's instructions.
    """
    labels: set[str] = {"firm"}
    permitted_matters: set[str] = set()
    client_id = None
    if user.practice_id and user.role not in (Role.ADMIN, Role.AI_GOVERNANCE):
        labels.add(f"practice:{user.practice_id}")
    if user.role == Role.KNOWLEDGE_LAWYER:
        labels.update(f"practice:{p}" for p in store.practices)
    if matter_id:
        matter = store.matters.get(matter_id)
        acc = check_matter_access(store, user, matter)
        wall = check_ethical_wall(store, user, matter_id)
        if acc.allowed and not wall.blocked and matter is not None:
            permitted_matters.add(matter.matter_id)
            labels.add(f"matter:{matter.matter_id}")
            labels.add(f"client:{matter.client_id}")
            labels.add(f"practice:{matter.practice_id}")
            client_id = matter.client_id
    return AccessScope(
        user_id=user.user_id, role=user.role.value, matter_id=matter_id if permitted_matters else None,
        client_id=client_id, permitted_matter_ids=frozenset(permitted_matters),
        permitted_labels=frozenset(labels), max_sensitivity=max_sensitivity(user), _seal=_SEAL,
    )


def matter_visibility(store: DataStore, user: User, matter: Matter) -> dict:
    """Matter list entry. Matters a user cannot access are redacted (no client name / description)."""
    acc = check_matter_access(store, user, matter)
    wall = check_ethical_wall(store, user, matter.matter_id)
    permitted = acc.allowed and not wall.blocked
    if permitted:
        return {"permitted": True, "reason": acc.reason}
    reason = wall.reason if wall.blocked else acc.reason
    return {"permitted": False, "reason": reason, "code": "ETHICAL_WALL" if wall.blocked else acc.code}
