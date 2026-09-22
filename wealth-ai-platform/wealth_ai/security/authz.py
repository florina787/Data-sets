"""Authorization: decided *before* retrieval, by code, never by an LLM.

The key object is ``AccessScope``: the set of clients, document
classifications, groups and regions a principal may see *right now*. It is
computed once per request from the authoritative entitlement store and then
pushed down into every data access: the search index pre-filter, every tool
call, the LLM cache key. Data outside the scope is never fetched, so it can't
leak through a prompt, a cache hit, or a creative model answer.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from wealth_ai.data import seed
from wealth_ai.security.identity import Principal, Role


class AuthorizationError(Exception):
    pass


# Which document classifications each role may read.
_CLASSIFICATION_CLEARANCE: dict[Role, set[str]] = {
    Role.ADVISOR: {"public", "internal"},
    Role.RELATIONSHIP_MANAGER: {"public", "internal"},
    Role.PORTFOLIO_MANAGER: {"public", "internal"},
    Role.OPERATIONS: {"public", "internal"},
    Role.COMPLIANCE: {"public", "internal", "restricted"},
}

_GROUP_ACCESS: dict[Role, set[str]] = {
    Role.COMPLIANCE: {"wealth", "compliance"},
}


@dataclass(frozen=True)
class AccessScope:
    user_id: str
    client_ids: frozenset[str]
    classifications: frozenset[str]
    advisor_groups: frozenset[str]
    regions: frozenset[str]

    def can_access_client(self, client_id: str) -> bool:
        return client_id in self.client_ids

    def require_client(self, client_id: str) -> None:
        if not self.can_access_client(client_id):
            # Deliberately indistinguishable from "client does not exist".
            raise AuthorizationError(f"client {client_id} not found or not permitted")

    @property
    def fingerprint(self) -> str:
        """Stable hash of the scope; used to partition caches by entitlement."""
        raw = "|".join(
            [self.user_id, ",".join(sorted(self.client_ids)), ",".join(sorted(self.classifications)),
             ",".join(sorted(self.advisor_groups)), ",".join(sorted(self.regions))]
        )
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


class EntitlementService:
    """Adapter over the book-of-business / entitlement system of record."""

    def __init__(self, entitlements: dict[str, set[str]] | None = None) -> None:
        self._entitlements = entitlements if entitlements is not None else seed.CLIENT_ENTITLEMENTS

    def scope_for(self, principal: Principal) -> AccessScope:
        clients = frozenset(self._entitlements.get(principal.user_id, set()))
        classifications: set[str] = set()
        groups: set[str] = {principal.advisor_group}
        for role in principal.roles:
            classifications |= _CLASSIFICATION_CLEARANCE.get(role, {"public"})
            groups |= _GROUP_ACCESS.get(role, set())
        return AccessScope(
            user_id=principal.user_id,
            client_ids=clients,
            classifications=frozenset(classifications),
            advisor_groups=frozenset(groups),
            regions=frozenset({principal.region}),
        )


entitlements = EntitlementService()
