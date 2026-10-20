"""Policy decision point (PDP): deny-by-default RBAC + ABAC evaluated from the versioned policy bundle in /policies.

The same bundle is evaluated by Open Policy Agent (policies/opa/flo_authz.rego) when FLO_OPA_URL is set; a parity
test (tests/security/test_opa_parity.py) proves both evaluators return identical decisions on a decision matrix.
Security decisions are made here, in trusted backend code; prompts never grant or remove access."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from backend.config import ROOT
from governance.identity import Principal

POLICY_DIR = ROOT / "policies"


@dataclass(frozen=True)
class Resource:
    type: str
    id: str
    tenant_id: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def as_policy_input(self) -> dict:
        return {"type": self.type, "id": self.id, "tenant_id": self.tenant_id, **self.attributes}


@dataclass
class Decision:
    allowed: bool
    action: str
    reasons: list[dict]
    policy_version: str
    obligations: list[str] = field(default_factory=list)
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    @property
    def denial_codes(self) -> list[str]:
        return [r["rule"] for r in self.reasons if r["effect"] == "deny"]

    def as_dict(self) -> dict:
        return {"allowed": self.allowed, "action": self.action, "reasons": self.reasons, "policy_version": self.policy_version,
                "obligations": self.obligations, "evaluated_at": self.evaluated_at}


class PolicyBundle:
    def __init__(self, directory: Path = POLICY_DIR):
        manifest = yaml.safe_load((directory / "bundle.yaml").read_text())
        self.docs = {f: yaml.safe_load((directory / f).read_text()) for f in manifest["files"]}
        digest = hashlib.sha256()
        for f in sorted(manifest["files"]):
            digest.update(f.encode() + (directory / f).read_bytes())
        self.hash = digest.hexdigest()
        self.version = f"{manifest['version']}+{self.hash[:10]}"
        self.rbac = self.docs["rbac.yaml"]
        self.abac = self.docs["abac.yaml"]
        self.approvals = self.docs["approvals.yaml"]
        self.providers = self.docs["providers.yaml"]
        self.suitability = self.docs["suitability.yaml"]
        self.retention = self.docs["retention.yaml"]

    def as_opa_data(self) -> dict:
        return {"flo": {"rbac": self.rbac, "abac": self.abac, "approvals": self.approvals, "version": self.version}}


def _get(path: str, inp: dict) -> Any:
    cur: Any = inp
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _action_matches(pattern: str, action: str) -> bool:
    if pattern == "*" or pattern == action:
        return True
    return pattern.endswith(":*") and action.split(":")[0] == pattern[:-2]


class PolicyEngine:
    def __init__(self, bundle: PolicyBundle | None = None):
        self.bundle = bundle or PolicyBundle()
        self.levels = self.bundle.abac["classification_levels"]

    @property
    def version(self) -> str:
        return self.bundle.version

    def permissions(self, principal: Principal) -> set[str]:
        perms: set[str] = set()
        for r in principal.roles:
            perms.update(self.bundle.rbac["roles"].get(r, []))
        return perms

    def _cond(self, c: dict, inp: dict) -> bool:
        if "any" in c:
            return any(self._cond(x, inp) for x in c["any"])
        if "all" in c:
            return all(self._cond(x, inp) for x in c["all"])
        left = _get(c["attr"], inp)
        right = _get(c["ref"], inp) if "ref" in c else c.get("value")
        op = c["op"]
        if op == "present":
            return left is not None
        if left is None or right is None:
            return False  # missing attributes fail closed
        if op == "eq":
            return left == right
        if op == "neq":
            return left != right
        if op == "in":
            return left in right
        if op == "contains_any":
            return bool(set(left) & set(right))
        if op == "lte_level":
            return left in self.levels and right in self.levels and self.levels[left] <= self.levels[right]
        raise ValueError(f"unknown operator {op}")

    def authorize(self, principal: Principal | None, action: str, resource: Resource | None = None,
                  context: dict | None = None) -> Decision:
        reasons: list[dict] = []
        ver = self.version
        if principal is None:
            return Decision(False, action, [{"rule": "AUTHN-REQUIRED", "effect": "deny", "message": "no authenticated principal"}], ver)
        if action in self.bundle.rbac.get("prohibited", []):
            return Decision(False, action, [{"rule": "PROHIBITED-ACTION", "effect": "deny",
                                             "message": f"{action} is prohibited in this deployment"}], ver)
        perms = self.permissions(principal)
        if not any(_action_matches(p, action) for p in perms):
            return Decision(False, action, [{"rule": "RBAC-DENY-DEFAULT", "effect": "deny",
                                             "message": f"no role of {list(principal.roles)} grants {action}"}], ver)
        reasons.append({"rule": "RBAC-GRANT", "effect": "allow", "message": f"granted by role(s) {list(principal.roles)}"})
        if resource is not None and resource.tenant_id is not None and resource.tenant_id != principal.tenant_id:
            return Decision(False, action, reasons + [{"rule": "TENANT-ISOLATION", "effect": "deny",
                                                       "message": "resource belongs to a different tenant"}], ver)
        inp = {"principal": principal.as_policy_input(), "resource": resource.as_policy_input() if resource else {},
               "context": context or {}, "action": action}
        allowed = True
        if resource is not None:
            for rule in self.bundle.abac["rules"]:
                if not any(_action_matches(a, action) for a in rule["actions"]):
                    continue
                if "resource_types" in rule and resource.type not in rule["resource_types"]:
                    continue
                ok = self._cond(rule["require"], inp)
                reasons.append({"rule": rule["id"], "effect": "allow" if ok else "deny",
                                "message": rule["description"] if not ok else "requirement satisfied"})
                allowed = allowed and ok
        obligations = []
        if allowed and action in self.bundle.approvals["actions"]:
            obligations.append("approval_required")
        return Decision(allowed, action, reasons, ver, obligations)

    def approval_spec(self, action: str) -> dict | None:
        return self.bundle.approvals["actions"].get(action)

    def provider(self, name: str) -> dict | None:
        return self.bundle.providers["providers"].get(name)

    def allowed_regions(self, residency: str) -> list[str]:
        return self.bundle.providers["tenant_residency"].get(residency, [])

    def decision_input(self, principal: Principal, action: str, resource: Resource | None, context: dict | None) -> dict:
        return {"principal": principal.as_policy_input(), "resource": resource.as_policy_input() if resource else None,
                "context": context or {}, "action": action}


@lru_cache
def get_policy_engine() -> PolicyEngine:
    return PolicyEngine()


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)
