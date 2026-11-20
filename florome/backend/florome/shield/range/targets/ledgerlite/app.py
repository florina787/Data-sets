"""LedgerLite: a DELIBERATELY VULNERABLE training application for the Florome Shield Cyber Range.

Never deploy this. It exists so the research engine has real, reproducible weaknesses (and safe look-alikes) to
analyse inside the isolated range. All data is synthetic. Ground truth lives in ../ledgerlite_labels.json and is
read only by the evaluation harness, never by the research engine.
"""

import os
import pickle
import sqlite3
import subprocess
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse

BASE = Path(__file__).resolve().parent
FILES = BASE / "files"
DB = BASE / "ledger.db"
app = FastAPI(title="LedgerLite (training target)")
USERS = {"token-alice": "alice", "token-bob": "bob"}


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB)
    conn.execute("CREATE TABLE IF NOT EXISTS invoices (id INTEGER PRIMARY KEY, owner TEXT, customer TEXT, amount REAL)")
    if conn.execute("SELECT count(*) FROM invoices").fetchone()[0] == 0:
        conn.executemany("INSERT INTO invoices (owner, customer, amount) VALUES (?, ?, ?)",
                         [("alice", "Acme Synthetic", 120.0), ("alice", "Globex Synthetic", 80.5), ("bob", "Initech Synthetic", 999.0)])
        conn.commit()
    return conn


def current_user(authorization: str = Header(default="")) -> str:
    user = USERS.get(authorization.removeprefix("Bearer ").strip())
    if user is None:
        raise HTTPException(401, "unauthenticated")
    return user


@app.get("/invoices/search")
def search_invoices(customer: str, user: str = Depends(current_user)):
    # VULNERABLE: SQL built with string formatting.
    rows = db().execute(f"SELECT id, owner, customer, amount FROM invoices WHERE owner = '{user}' AND customer = '{customer}'").fetchall()
    return [dict(zip(("id", "owner", "customer", "amount"), r)) for r in rows]


@app.get("/invoices/by-customer")
def by_customer(customer: str, user: str = Depends(current_user)):
    # SAFE decoy: parameterised query.
    rows = db().execute("SELECT id, owner, customer, amount FROM invoices WHERE owner = ? AND customer = ?", (user, customer)).fetchall()
    return [dict(zip(("id", "owner", "customer", "amount"), r)) for r in rows]


@app.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: int, user: str = Depends(current_user)):
    # VULNERABLE: authenticated, but no ownership check (IDOR).
    row = db().execute("SELECT id, owner, customer, amount FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if row is None:
        raise HTTPException(404)
    return dict(zip(("id", "owner", "customer", "amount"), row))


@app.get("/mine/{invoice_id}")
def get_my_invoice(invoice_id: int, user: str = Depends(current_user)):
    # SAFE decoy: ownership enforced in the query.
    row = db().execute("SELECT id, owner, customer, amount FROM invoices WHERE id = ? AND owner = ?", (invoice_id, user)).fetchone()
    if row is None:
        raise HTTPException(404)
    return dict(zip(("id", "owner", "customer", "amount"), row))


@app.get("/files/download", response_class=PlainTextResponse)
def download(name: str):
    # VULNERABLE: unauthenticated path traversal.
    return open(os.path.join(FILES, name)).read()


@app.get("/files/read", response_class=PlainTextResponse)
def read_file(name: str):
    # SAFE decoy: resolved path must stay inside FILES.
    target = (FILES / name).resolve()
    if not str(target).startswith(str(FILES.resolve()) + os.sep):
        raise HTTPException(400, "invalid path")
    return target.read_text()


@app.get("/diag/ping", response_class=PlainTextResponse)
def ping(host: str):
    # VULNERABLE: unauthenticated command injection via shell=True.
    return subprocess.run(f"echo pinging {host}", shell=True, capture_output=True, text=True, timeout=5).stdout


@app.get("/diag/echo", response_class=PlainTextResponse)
def echo(message: str):
    # SAFE decoy: argument list, no shell.
    return subprocess.run(["echo", message], capture_output=True, text=True, timeout=5).stdout


@app.post("/import")
async def import_ledger(request: Request, user: str = Depends(current_user)):
    # VULNERABLE: unsafe deserialisation of client data.
    payload = await request.body()
    data = pickle.loads(payload)
    return {"imported": str(data)[:200]}
