"""OPA integration: export the YAML bundle as OPA data, and a remote PDP adapter that fails closed."""
from __future__ import annotations

import json
import sys

import httpx

from backend.config import ROOT
from governance.identity import Principal
from governance.policy import Decision, PolicyBundle, PolicyEngine, Resource

DATA_PATH = ROOT / "policies" / "opa" / "data.json"


def export(path=DATA_PATH) -> str:
    data = PolicyBundle().as_opa_data()
    text = json.dumps(data, indent=1, sort_keys=True) + "\n"
    path.write_text(text)
    return text


class OpaPolicyEngine(PolicyEngine):
    """Delegates the allow/deny decision to an OPA sidecar. Any OPA error results in DENY (fail closed)."""

    def __init__(self, url: str, timeout: float = 0.5):
        super().__init__()
        self.url = url.rstrip("/") + "/v1/data/flo/authz/decision"
        self.timeout = timeout

    def authorize(self, principal: Principal | None, action: str, resource: Resource | None = None,
                  context: dict | None = None) -> Decision:
        if principal is None:
            return super().authorize(principal, action, resource, context)
        inp = self.decision_input(principal, action, resource, context)
        try:
            res = httpx.post(self.url, json={"input": inp}, timeout=self.timeout).json()["result"]
        except Exception as e:  # noqa: BLE001 - any failure must deny
            return Decision(False, action, [{"rule": "PDP-UNAVAILABLE", "effect": "deny", "message": f"OPA error: {e.__class__.__name__}"}],
                            self.version)
        reasons = [{"rule": d, "effect": "deny", "message": "denied by OPA policy"} for d in sorted(res.get("denials", []))]
        if res.get("allow"):
            reasons = [{"rule": "OPA-ALLOW", "effect": "allow", "message": "allowed by OPA policy"}]
        return Decision(bool(res.get("allow")), action, reasons, res.get("policy_version", self.version), sorted(res.get("obligations", [])))


if __name__ == "__main__":
    if sys.argv[1:] == ["export"]:
        export()
        print(f"wrote {DATA_PATH}")
