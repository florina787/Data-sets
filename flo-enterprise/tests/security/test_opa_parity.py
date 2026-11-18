"""The embedded Python PDP and the OPA/Rego policy must agree on every decision in the matrix."""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from governance import resources
from governance.opa import DATA_PATH
from governance.policy import PolicyBundle, Resource

pytestmark = [pytest.mark.critical, pytest.mark.opa]
OPA = shutil.which("opa")


def test_opa_data_in_sync_with_yaml():
    current = json.loads(DATA_PATH.read_text())
    assert current == json.loads(json.dumps(PolicyBundle().as_opa_data(), sort_keys=True)), "run: python -m governance.opa export"


@pytest.mark.skipif(OPA is None, reason="opa binary not on PATH")
def test_python_and_opa_decisions_match(engine, P, st, a001_client, other_client, nw_client):
    actions = ["client:read", "portfolio:read", "comms:send", "docs:read", "trade:execute", "exec:read", "privacy:rehydrate", "aiops:manage",
               "approvals:decide", "export:sensitive"]
    pid_a = next(p["id"] for p in st.tables["portfolios"] if p["client_id"] == a001_client)
    res = [None, resources.client(st, a001_client), resources.client(st, other_client), resources.client(st, nw_client),
           resources.client(st, "C-99999"), resources.portfolio(st, pid_a), Resource("document", "D1", "t-flo", {"classification": "restricted"}),
           Resource("document", "D2", "t-flo", {"classification": "public"}), Resource("document", "D3", "t-flo", {})]
    contexts = [{}, {"purpose": "compliance_review"}]
    cases = []
    for u in P.values():
        for a in actions:
            for r in res:
                for c in contexts:
                    cases.append(engine.decision_input(u, a, r, c))
    with tempfile.TemporaryDirectory() as td:
        inp = Path(td) / "cases.json"
        inp.write_text(json.dumps({"cases": cases}))
        query = "[d | some c in input.cases; d := data.flo.authz.decision with input as c]"
        out = subprocess.run([OPA, "eval", "-f", "json", "-d", str(DATA_PATH.parent), "-i", str(inp), query], capture_output=True, text=True, check=True)
    opa_dec = json.loads(out.stdout)["result"][0]["expressions"][0]["value"]
    mismatches = []
    for case, od in zip(cases, opa_dec):
        from governance.identity import Principal
        pr = case["principal"]
        principal = Principal(**{**pr, "roles": tuple(pr["roles"])})
        r = case["resource"]
        resource = Resource(r["type"], r["id"], r["tenant_id"], {k: v for k, v in r.items() if k not in ("type", "id", "tenant_id")}) if r else None
        pd = engine.authorize(principal, case["action"], resource, case["context"])
        if pd.allowed != od["allow"] or sorted(pd.denial_codes) != sorted(od["denials"]) or sorted(pd.obligations) != sorted(od["obligations"]):
            mismatches.append((case["principal"]["user_id"], case["action"], r and r["id"], case["context"], pd.denial_codes, od))
    assert not mismatches, mismatches[:5]
    assert len(cases) > 1500
