"""Agent Containment Supervisor: synthetic escape scenarios, deterministic termination, credential revocation."""

from __future__ import annotations

import subprocess
import sys

from florome.shield.containment.scenarios import SCENARIOS
from florome.shield.models import TemporaryCredential
from tests.conftest import H


def test_every_scenario_is_handled_as_expected(client, db):
    c = client
    for name, sc in SCENARIOS.items():
        e = c.post("/api/v1/shield/containment/run", json={"scenario": name}, headers=H("admin")).json()
        assert e["forensics"]["matched_expectation"], (name, e["violation"], e["forensics"]["stderr_tail"])
        cred = db.query(TemporaryCredential).filter_by(session_id=e["session_id"]).one()
        if sc["expected"] == "completed":
            assert e["outcome"] == "completed" and not cred.revoked and e["actions_taken"] == []
        else:
            assert e["outcome"] == "contained" and cred.revoked and "credential_revoked" in e["actions_taken"]
            assert e["forensics"]["isolation"]["network_namespace"] is True


def test_credential_theft_never_returns_the_decoy_key(client):
    e = client.post("/api/v1/shield/containment/run", json={"scenario": "credential_theft"}, headers=H("admin")).json()
    assert "SYNTHETIC-DECOY" not in e["forensics"]["stdout_tail"] and e["forensics"]["guard_events"][0]["violation"] == "restricted_file_read"


def test_network_namespace_blocks_egress_even_without_the_audit_hook():
    """Defence in depth: the namespace alone stops the connection when the in-process guard is absent."""
    code = "import socket\ntry:\n    socket.create_connection(('198.51.100.7', 443), timeout=2)\n    print('CONNECTED')\nexcept OSError as e:\n    print('BLOCKED', e.errno)\n"
    out = subprocess.run(["unshare", "-n", sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=20).stdout
    assert out.startswith("BLOCKED")


def test_containment_events_are_audited(client):
    client.post("/api/v1/shield/containment/run", json={"scenario": "shell_escape"}, headers=H("admin"))
    items = client.get("/api/v1/governance/audit?action=shield.containment", headers=H("viewer")).json()["items"]
    assert items[0]["outcome"] == "denied" and items[0]["detail"]["violation"] == "subprocess_spawn"
