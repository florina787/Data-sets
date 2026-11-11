"""Role-based access control. Permissions are checked server-side on every endpoint."""

from __future__ import annotations

from dataclasses import dataclass

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "viewer": {"read"},
    "operator": {"read", "rca:run", "plan:create", "plan:execute", "mcp:invoke_read"},
    "approver": {"read", "plan:approve"},
    "admin": {"read", "rca:run", "plan:create", "plan:execute", "plan:approve", "mcp:invoke_read", "mcp:manage",
              "connections:manage", "governance:manage", "demo:reset"},
}


@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_id: str
    name: str
    roles: tuple[str, ...]

    @property
    def permissions(self) -> set[str]:
        out: set[str] = set()
        for r in self.roles:
            out |= ROLE_PERMISSIONS.get(r, set())
        return out

    def can(self, permission: str) -> bool:
        return permission in self.permissions
