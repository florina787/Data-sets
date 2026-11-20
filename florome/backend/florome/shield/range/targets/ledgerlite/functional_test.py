"""Functional (non-security) checks a patch must not break. Run inside the range."""


def run(client) -> list[tuple[str, bool]]:
    a = {"Authorization": "Bearer token-alice"}
    checks = []
    r = client.get("/invoices/search", params={"customer": "Acme Synthetic"}, headers=a)
    checks.append(("search returns own invoice", r.status_code == 200 and len(r.json()) == 1))
    r = client.get("/invoices/1", headers=a)
    checks.append(("owner can read own invoice", r.status_code == 200 and r.json()["owner"] == "alice"))
    r = client.get("/files/download", params={"name": "report.txt"})
    checks.append(("report downloads", r.status_code == 200 and "Q3" in r.text))
    r = client.get("/diag/ping", params={"host": "localhost"})
    checks.append(("ping echoes host", r.status_code == 200 and "localhost" in r.text))
    import pickle

    r = client.post("/import", content=pickle.dumps({"rows": [1, 2]}), headers=a)
    checks.append(("import accepts a ledger document", r.status_code == 200))
    return checks
