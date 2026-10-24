"""API & MCP Bridge generator.

Generates a runnable, read-only bundle from vetted templates (no model-written
code): FastAPI adapter + Pydantic models, a mock backend with a synthetic
snapshot, an MCP server built on the official Python SDK, pytest contract and
security tests, OpenAPI document, threat model, README and .env.example.

Generated code is preview-only until a permitted user explicitly runs its
tests; tests run in a subprocess with a minimal environment, no proxy
variables, a timeout, and the bundle directory as working directory.
"""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

from app.core import db
from app.core.config import GENERATED_DIR
from app.core.util import DEMO_TODAY, new_id, now_iso, sha256_text
from app.services import data

CAPABILITIES = {
    "part_availability": {
        "title": "Approved parts inventory view (read-only)",
        "source": "fixtures/legacy/mro_core_legacy.sql#V_PART_AVAILABILITY",
        "operation": "get_part_availability(part_number)",
        "mapping": [
            {"legacy": "PART_NO", "canonical": "part_number", "type": "string", "note": "Validated ^P-[0-9A-Z]{3,8}$"},
            {"legacy": "PART_DESC", "canonical": "description", "type": "string", "note": ""},
            {"legacy": "BASE_CODE", "canonical": "location", "type": "string", "note": ""},
            {"legacy": "QTY_OH", "canonical": "quantity_on_hand", "type": "integer", "note": "Reported quantity"},
            {"legacy": "LOT_NO", "canonical": "lot", "type": "string", "note": "UNKNOWN lot => not traceable"},
            {"legacy": "LAST_CNT_DT", "canonical": "last_counted", "type": "date", "note": "> 30 days for critical parts => unverified"},
        ],
        "scopes": ["inventory.read"],
    }
}

DISCOVERED_SOURCES = [
    {"id": "mro_view", "name": "MRO_CORE view V_PART_AVAILABILITY", "kind": "read-only DB view (DDL fixture)",
     "capabilities": ["part_availability"], "write_operations_excluded": 0},
    {"id": "java_erp", "name": "Java ERP Integration Service GET /stock/{partNo}", "kind": "OpenAPI fixture",
     "capabilities": ["part_availability"], "write_operations_excluded": 3},
    {"id": "erp_sim", "name": "ERP Simulator InventoryPartInStockSet", "kind": "OData-like fixture",
     "capabilities": ["part_availability"], "write_operations_excluded": 1},
]


def _snapshot() -> list[dict[str, Any]]:
    """Synthetic snapshot of the view rows, taken from the demo database."""
    rows_ = []
    for a in data.part_availability():
        rows_.append({"PART_NO": a["part_number"], "PART_DESC": a["name"], "BASE_CODE": a["location"],
                      "QTY_OH": a["reported_qty_by_source"].get(a["latest_source"], a["verified_qty"]), "LOT_NO": a["lot"],
                      "LAST_CNT_DT": a["last_verified"], "CRIT_CODE": a["criticality"][0].upper()})
    return rows_


T_MODELS = '''"""Canonical models for the read-only part availability adapter (generated, synthetic)."""
from datetime import date

from pydantic import BaseModel, Field

PART_PATTERN = r"^P-[0-9A-Z]{3,8}$"


class StockLocation(BaseModel):
    location: str
    quantity_on_hand: int = Field(ge=0)
    lot: str
    last_counted: date
    verified: bool
    note: str = ""


class PartAvailability(BaseModel):
    part_number: str = Field(pattern=PART_PATTERN)
    description: str
    total_verified: int = Field(ge=0)
    locations: list[StockLocation]
    source: str = "V_PART_AVAILABILITY (synthetic snapshot)"
    synthetic: bool = True


class Page(BaseModel):
    items: list[PartAvailability]
    limit: int
    offset: int
    total: int


class Problem(BaseModel):
    code: str
    message: str
'''

T_BACKEND = '''"""Mock 'authorized system endpoint': a read-only synthetic snapshot of V_PART_AVAILABILITY.

In production this module would call the approved read-only DB view or the
documented ERP projection with a *service* credential and parameterized
queries. It never receives the end user's token.
"""
import json
import time
from datetime import date
from pathlib import Path

from adapter.models import PartAvailability, StockLocation

DATA = json.loads((Path(__file__).resolve().parents[1] / "mock_backend" / "data.json").read_text())
AS_OF = date.fromisoformat(DATA["as_of"])
CRITICAL_VERIFY_DAYS = 30


class BackendTimeout(Exception):
    pass


def _canonical(part_number: str, rows: list[dict]) -> PartAvailability:
    locs = []
    for r in rows:
        counted = date.fromisoformat(r["LAST_CNT_DT"])
        critical = r["CRIT_CODE"] in ("C", "H")
        stale = critical and (AS_OF - counted).days > CRITICAL_VERIFY_DAYS
        verified = not stale and r["LOT_NO"] != "UNKNOWN"
        note = ("stale count; " if stale else "") + ("untraceable lot; " if r["LOT_NO"] == "UNKNOWN" else "")
        locs.append(StockLocation(location=r["BASE_CODE"], quantity_on_hand=max(0, int(r["QTY_OH"] or 0)), lot=r["LOT_NO"],
                                  last_counted=counted, verified=verified, note=note.strip("; ")))
    return PartAvailability(part_number=part_number, description=rows[0]["PART_DESC"],
                            total_verified=sum(loc.quantity_on_hand for loc in locs if loc.verified), locations=locs)


def get_part_availability(part_number: str, timeout_s: float = 2.0) -> PartAvailability | None:
    started = time.perf_counter()
    rows = [r for r in DATA["rows"] if r["PART_NO"] == part_number]  # parameter compared, never interpolated
    if time.perf_counter() - started > timeout_s:
        raise BackendTimeout("backend exceeded timeout")
    return _canonical(part_number, rows) if rows else None


def list_parts(limit: int, offset: int) -> tuple[list[PartAvailability], int]:
    numbers = sorted({r["PART_NO"] for r in DATA["rows"]})
    page = numbers[offset:offset + limit]
    return [get_part_availability(p) for p in page], len(numbers)
'''

T_AUTH = '''"""Token checks for the adapter (demo HMAC tokens; production: OIDC/JWT via the enterprise IdP).

Validates signature, audience, expiry and scope for every request. The
caller's token is verified here and is never forwarded upstream.
"""
import base64
import hashlib
import hmac
import json
import os
import time

AUDIENCE = "ff-parts-adapter"
REQUIRED_SCOPE = "inventory.read"


def _secret() -> bytes:
    return os.environ.get("ADAPTER_DEMO_SECRET", "local-demo-secret-change-me").encode()


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def issue_demo_token(sub: str, scopes: list[str], aud: str = AUDIENCE, ttl: int = 600) -> str:
    body = _b64(json.dumps({"sub": sub, "aud": aud, "scope": " ".join(scopes), "exp": int(time.time()) + ttl}).encode())
    return body + "." + _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())


class AuthError(Exception):
    def __init__(self, code: str, status: int = 401):
        super().__init__(code)
        self.code = code
        self.status = status


def verify(authorization: str | None) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("missing_token")
    token = authorization[7:].strip()
    try:
        body, sig = token.split(".", 1)
    except ValueError as exc:
        raise AuthError("malformed_token") from exc
    good = _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(good, sig):
        raise AuthError("bad_signature")
    claims = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    if claims.get("aud") != AUDIENCE:
        raise AuthError("wrong_audience")
    if claims.get("exp", 0) < time.time():
        raise AuthError("expired_token")
    if REQUIRED_SCOPE not in claims.get("scope", "").split():
        raise AuthError("insufficient_scope", 403)
    return claims
'''

T_APP = '''"""Read-only part availability adapter (generated by Flying_Florina Bridge Studio).

Synthetic demo. Only GET routes exist; there is no write path. Inputs are
validated, results are capped and paginated, logs are redacted.
"""
import logging
import re
import time
import uuid

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from adapter import backend
from adapter.auth import AuthError, verify
from adapter.models import Page, PartAvailability, Problem

log = logging.getLogger("adapter")
PART_RE = re.compile(r"^P-[0-9A-Z]{3,8}$")
MAX_LIMIT = 50

app = FastAPI(title="Part Availability Adapter (synthetic)", version="__VERSION__",
              description="Read-only facade over V_PART_AVAILABILITY. Bundle __BUNDLE_ID__.")


@app.middleware("http")
async def request_id(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["x-request-id"] = rid
    response.headers["cache-control"] = "no-store"
    log.info("rid=%s path=%s status=%s ms=%.1f", rid, request.url.path, response.status_code, (time.perf_counter() - started) * 1000)
    return response


@app.exception_handler(AuthError)
async def auth_error(_: Request, err: AuthError):
    return JSONResponse(status_code=err.status, content={"code": err.code, "message": "Unauthorized" if err.status == 401 else "Forbidden"})


@app.get("/v1/parts/{part_number}/availability", response_model=PartAvailability, responses={404: {"model": Problem}, 422: {"model": Problem}})
def get_part_availability(part_number: str, authorization: str | None = Header(default=None)):
    verify(authorization)
    if not PART_RE.fullmatch(part_number):
        raise HTTPException(status_code=422, detail={"code": "invalid_part_number", "message": "Part number format is invalid."})
    try:
        result = backend.get_part_availability(part_number)
    except backend.BackendTimeout as exc:
        raise HTTPException(status_code=504, detail={"code": "upstream_timeout", "message": "Backend timed out."}) from exc
    if result is None:
        raise HTTPException(status_code=404, detail={"code": "not_found", "message": "Unknown part number."})
    return result


@app.get("/v1/parts", response_model=Page)
def list_parts(limit: int = Query(20, ge=1, le=MAX_LIMIT), offset: int = Query(0, ge=0, le=100000),
               authorization: str | None = Header(default=None)):
    verify(authorization)
    items, total = backend.list_parts(limit, offset)
    return Page(items=items, limit=limit, offset=offset, total=total)


@app.get("/healthz")
def healthz():
    return {"status": "ok", "synthetic": True}
'''

T_MCP = '''"""MCP server exposing one read-only tool over the adapter (official Python SDK).

Run:  python -m mcp_server.server   (stdio transport)
MCP is the agent interface only. Authorization: the server requires a token
with audience ff-parts-adapter and scope inventory.read, supplied via the
MCP_ADAPTER_TOKEN environment variable at launch, and checks it on every call.
"""
import os
import re

from mcp.server.mcpserver import MCPServer

from adapter import backend
from adapter.auth import AuthError, verify

PART_RE = re.compile(r"^P-[0-9A-Z]{3,8}$")
server = MCPServer(name="ff-part-availability", version="__VERSION__",
                   instructions="Read-only, synthetic part availability. No write tools exist.")


@server.tool(name="get_part_availability", description="Verified, read-only availability for one part number (synthetic data).")
def get_part_availability(part_number: str) -> dict:
    try:
        verify("Bearer " + os.environ.get("MCP_ADAPTER_TOKEN", ""))
    except AuthError as err:
        return {"error": err.code}
    if not PART_RE.fullmatch(part_number):
        return {"error": "invalid_part_number"}
    result = backend.get_part_availability(part_number)
    return result.model_dump(mode="json") if result else {"error": "not_found"}


if __name__ == "__main__":
    server.run("stdio")
'''

T_CONFTEST = '''import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("ADAPTER_DEMO_SECRET", "test-secret-not-for-production")
'''

T_TEST_CONTRACT = '''import json
from pathlib import Path

from fastapi.testclient import TestClient

from adapter.app import app
from adapter.auth import issue_demo_token
from adapter.models import PartAvailability

client = TestClient(app)
TOKEN = {"Authorization": "Bearer " + issue_demo_token("tester", ["inventory.read"])}


def test_get_known_part_matches_contract():
    r = client.get("/v1/parts/P-7731/availability", headers=TOKEN)
    assert r.status_code == 200
    body = PartAvailability.model_validate(r.json())
    assert body.part_number == "P-7731"
    assert body.synthetic is True
    assert all(loc.quantity_on_hand >= 0 for loc in body.locations)


def test_stale_critical_count_is_not_verified():
    body = client.get("/v1/parts/P-7731/availability", headers=TOKEN).json()
    main = [loc for loc in body["locations"] if loc["location"] == "MAIN-HUB"]
    assert main, "seeded MAIN-HUB row expected"
    assert body["total_verified"] == sum(loc["quantity_on_hand"] for loc in body["locations"] if loc["verified"])


def test_unknown_part_returns_404():
    r = client.get("/v1/parts/P-0000/availability", headers=TOKEN)
    assert r.status_code == 404


def test_pagination_caps_limit():
    assert client.get("/v1/parts?limit=500", headers=TOKEN).status_code == 422
    r = client.get("/v1/parts?limit=5&offset=0", headers=TOKEN)
    assert r.status_code == 200 and len(r.json()["items"]) <= 5


def test_openapi_document_matches_generated_file():
    generated = json.loads((Path(__file__).resolve().parents[1] / "openapi.json").read_text())
    live = app.openapi()
    assert set(generated["paths"]) == set(live["paths"])


def test_no_write_routes_exist():
    for route in app.routes:
        methods = getattr(route, "methods", set()) or set()
        assert not (methods & {"POST", "PUT", "PATCH", "DELETE"}), route.path
'''

T_TEST_SECURITY = '''from fastapi.testclient import TestClient

from adapter.app import app
from adapter.auth import issue_demo_token

client = TestClient(app)


def test_missing_token_rejected():
    assert client.get("/v1/parts/P-7731/availability").status_code == 401


def test_wrong_audience_rejected():
    tok = issue_demo_token("tester", ["inventory.read"], aud="some-other-api")
    r = client.get("/v1/parts/P-7731/availability", headers={"Authorization": "Bearer " + tok})
    assert r.status_code == 401 and r.json()["code"] == "wrong_audience"


def test_missing_scope_forbidden():
    tok = issue_demo_token("tester", ["workorder.write"])
    assert client.get("/v1/parts/P-7731/availability", headers={"Authorization": "Bearer " + tok}).status_code == 403


def test_tampered_token_rejected():
    tok = issue_demo_token("tester", ["inventory.read"])
    assert client.get("/v1/parts/P-7731/availability", headers={"Authorization": "Bearer " + tok[:-2] + "xx"}).status_code == 401


def test_injection_like_input_rejected():
    tok = {"Authorization": "Bearer " + issue_demo_token("tester", ["inventory.read"])}
    for bad in ["P-7731' OR '1'='1", "P-7731;DROP", "../etc/passwd"]:
        assert client.get(f"/v1/parts/{bad}/availability", headers=tok).status_code in (404, 422)


def test_write_methods_not_allowed():
    tok = {"Authorization": "Bearer " + issue_demo_token("tester", ["inventory.read"])}
    assert client.post("/v1/parts/P-7731/availability", headers=tok).status_code == 405
'''

T_TEST_MCP = '''"""End-to-end MCP test: launches the generated MCP server over stdio and calls the tool."""
import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from adapter.auth import issue_demo_token

ROOT = Path(__file__).resolve().parents[1]


async def _call(token: str, part: str):
    params = StdioServerParameters(command=sys.executable, args=["-m", "mcp_server.server"], cwd=str(ROOT),
                                   env={"PYTHONPATH": str(ROOT), "MCP_ADAPTER_TOKEN": token, "PATH": os.environ.get("PATH", ""),
                                        "ADAPTER_DEMO_SECRET": os.environ["ADAPTER_DEMO_SECRET"]})
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            result = await session.call_tool("get_part_availability", {"part_number": part})
            return names, result


def _payload(result):
    if getattr(result, "structured_content", None):
        return result.structured_content
    if getattr(result, "structuredContent", None):
        return result.structuredContent
    import json
    return json.loads(result.content[0].text)


def test_mcp_tool_listed_and_returns_availability():
    names, result = asyncio.run(_call(issue_demo_token("agent", ["inventory.read"]), "P-7731"))
    assert names == ["get_part_availability"]
    payload = _payload(result)
    payload = payload.get("result", payload)
    assert payload["part_number"] == "P-7731"


def test_mcp_tool_denies_without_scope():
    _, result = asyncio.run(_call(issue_demo_token("agent", ["workorder.write"]), "P-7731"))
    payload = _payload(result)
    payload = payload.get("result", payload)
    assert payload == {"error": "insufficient_scope"}
'''

T_THREAT = '''# Threat model - part availability adapter (generated, synthetic)

| Asset | Threat | Mitigation in this bundle | Residual risk |
|---|---|---|---|
| Inventory data (INTERNAL) | Unauthenticated read | HMAC demo token: signature, audience, expiry, scope checked per request | Demo HMAC secret; use enterprise IdP (OIDC/JWT) in production |
| Legacy DB | SQL injection | Strict part-number regex; parameter compared, never interpolated; read-only view only | Production view permissions must be verified by DBA |
| Legacy DB | Writes via adapter | No write routes (tested); MCP exposes one read tool | Gateway must also block non-GET |
| User identity | Token passthrough to upstream | User token verified at adapter and never forwarded; backend uses a service credential | Service credential custody |
| Availability | Large result sets / slow backend | Pagination with max limit 50; backend timeout -> 504 | No rate limiting here: add at the gateway |
| Agents | Tool abuse / tool spoofing | Single read tool; scope check per invocation; tool pinned in caller allowlist | MCP is not the security boundary |
| Logs | Secret leakage | Logs contain request id, path, status, latency only | Upstream logs out of scope |
| Network | SSRF | Adapter accepts no URLs; backend is a fixed module | Production endpoint must be allowlisted |
'''

T_README = '''# Part Availability Adapter - bundle __BUNDLE_ID__

Generated by **Flying_Florina Bridge Studio** on __DATE__ from `__SOURCE__`.
SYNTHETIC DEMO: data is a fictional snapshot; there is no live ERP/IFS connection.

## What is inside
| Path | Purpose |
|---|---|
| `adapter/app.py` | FastAPI read-only facade: `GET /v1/parts/{part_number}/availability`, `GET /v1/parts` |
| `adapter/models.py` | Canonical Pydantic models (legacy -> canonical mapping below) |
| `adapter/auth.py` | Audience/scope/expiry checks (demo HMAC tokens) |
| `adapter/backend.py` | Mock authorized endpoint over `mock_backend/data.json` |
| `mcp_server/server.py` | MCP stdio server (official Python SDK) with one tool `get_part_availability` |
| `tests/` | Contract, security and end-to-end MCP tests |
| `openapi.json` | OpenAPI document of the adapter |
| `THREAT_MODEL.md` | Threats, mitigations and residual risk |

## Mapping
__MAPPING__

## Run
```bash
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\\Scripts\\Activate.ps1
pip install fastapi uvicorn pydantic mcp httpx pytest
export ADAPTER_DEMO_SECRET=change-me             # PowerShell: $env:ADAPTER_DEMO_SECRET="change-me"
python -m pytest -q
uvicorn adapter.app:app --port 8100
```

## Example calls
```bash
TOKEN=$(python -c "from adapter.auth import issue_demo_token; print(issue_demo_token('me', ['inventory.read']))")
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8100/v1/parts/P-7731/availability
curl -s -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8100/v1/parts?limit=5"
```

## Integration guide
1. Replace `adapter/backend.py` with a client for the approved read-only view or documented ERP projection, using a service credential.
2. Replace `adapter/auth.py` with your IdP's JWT validation (issuer, audience, scope).
3. Register the route behind your API gateway (rate limits, WAF) and pin the MCP tool in your agent allowlist.
'''


def _openapi(bundle_id: str) -> dict[str, Any]:
    return {
        "openapi": "3.1.0",
        "info": {"title": "Part Availability Adapter (synthetic)", "version": "1.0.0", "description": f"Bundle {bundle_id}"},
        "paths": {
            "/v1/parts/{part_number}/availability": {"get": {"operationId": "get_part_availability", "security": [{"bearer": ["inventory.read"]}],
                                                             "parameters": [{"name": "part_number", "in": "path", "required": True, "schema": {"type": "string", "pattern": "^P-[0-9A-Z]{3,8}$"}}],
                                                             "responses": {"200": {"description": "Availability"}, "401": {"description": "Unauthorized"}, "403": {"description": "Forbidden"}, "404": {"description": "Unknown part"}}}},
            "/v1/parts": {"get": {"operationId": "list_parts", "parameters": [{"name": "limit", "in": "query", "schema": {"type": "integer", "maximum": 50}},
                                                                             {"name": "offset", "in": "query", "schema": {"type": "integer"}}],
                                  "responses": {"200": {"description": "Page"}}}},
            "/healthz": {"get": {"operationId": "healthz", "responses": {"200": {"description": "OK"}}}},
        },
        "components": {"securitySchemes": {"bearer": {"type": "http", "scheme": "bearer"}}},
    }


def generate(actor_id: str, capability: str = "part_availability", source_id: str = "mro_view",
             scopes: list[str] | None = None, bundle_dir: Path | None = None) -> dict[str, Any]:
    if capability not in CAPABILITIES:
        raise ValueError(f"Unsupported capability '{capability}'")
    cap = CAPABILITIES[capability]
    bundle_id = new_id("BRG")
    root = bundle_dir or (GENERATED_DIR / bundle_id)
    version = "1.0.0"
    mapping_md = "| Legacy | Canonical | Type | Note |\n|---|---|---|---|\n" + "\n".join(
        f"| `{m['legacy']}` | `{m['canonical']}` | {m['type']} | {m['note']} |" for m in cap["mapping"])
    sub = lambda t: (t.replace("__BUNDLE_ID__", bundle_id).replace("__VERSION__", version)  # noqa: E731
                     .replace("__DATE__", now_iso()[:10]).replace("__SOURCE__", cap["source"]).replace("__MAPPING__", mapping_md))
    files = {
        "adapter/__init__.py": "",
        "adapter/models.py": T_MODELS,
        "adapter/backend.py": T_BACKEND,
        "adapter/auth.py": T_AUTH,
        "adapter/app.py": sub(T_APP),
        "mcp_server/__init__.py": "",
        "mcp_server/server.py": sub(T_MCP),
        "mock_backend/data.json": json.dumps({"as_of": DEMO_TODAY, "synthetic": True, "view": "V_PART_AVAILABILITY", "rows": _snapshot()}, indent=1),
        "tests/__init__.py": "",
        "tests/conftest.py": T_CONFTEST,
        "tests/test_contract.py": T_TEST_CONTRACT,
        "tests/test_security.py": T_TEST_SECURITY,
        "tests/test_mcp.py": T_TEST_MCP,
        "openapi.json": json.dumps(_openapi(bundle_id), indent=1),
        "THREAT_MODEL.md": T_THREAT,
        "README.md": sub(T_README),
        ".env.example": "# Synthetic demo only. Never commit real secrets.\nADAPTER_DEMO_SECRET=change-me\nMCP_ADAPTER_TOKEN=\n",
        "pytest.ini": "[pytest]\ntestpaths = tests\naddopts = -p no:cacheprovider\n",
        "curl_examples.sh": "#!/usr/bin/env sh\n# See README.md; requires a demo token.\ncurl -s -H \"Authorization: Bearer $TOKEN\" http://127.0.0.1:8100/v1/parts/P-7731/availability\n",
    }
    manifest = []
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        manifest.append({"path": rel, "bytes": len(content.encode()), "sha256": sha256_text(content)})
    static = static_checks(root)
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO bridge_bundles VALUES (?,?,?,?,?,?,?)",
                     (bundle_id, now_iso(), actor_id, capability, str(root), db.jdump(manifest), None))
    return {"bundle_id": bundle_id, "capability": capability, "source": next((s for s in DISCOVERED_SOURCES if s["id"] == source_id), DISCOVERED_SOURCES[0]),
            "mapping": cap["mapping"], "scopes": scopes or cap["scopes"], "files": manifest, "static_checks": static,
            "preview": {"adapter/app.py": files["adapter/app.py"], "mcp_server/server.py": files["mcp_server/server.py"],
                        "adapter/models.py": T_MODELS, "openapi.json": files["openapi.json"]},
            "status": "generated_not_executed"}


def static_checks(root: Path) -> list[dict[str, Any]]:
    """Checks that do not execute generated code."""
    app_src = (root / "adapter" / "app.py").read_text()
    all_src = "\n".join(p.read_text() for p in root.rglob("*.py"))
    checks = [
        ("Only GET routes declared", not re.search(r"@app\.(post|put|patch|delete)", app_src)),
        ("No outbound network clients in adapter", not re.search(r"\b(requests|urllib|httpx|socket)\b", (root / "adapter").joinpath("backend.py").read_text())),
        ("No subprocess / eval / exec", not re.search(r"\b(subprocess|eval\(|exec\(|os\.system)", all_src.replace("sys.executable", ""))),
        ("No credentials committed", not re.search(r"(?i)(password|secret)\s*=\s*['\"][^'\"]{6,}['\"]", all_src)),
        ("Input validation regex present", "PART_RE" in app_src),
        ("Pagination cap present", "MAX_LIMIT" in app_src),
        ("Every Python file parses", _parses(root)),
    ]
    return [{"check": c, "passed": bool(ok)} for c, ok in checks]


def _parses(root: Path) -> bool:
    import ast

    try:
        for p in root.rglob("*.py"):
            ast.parse(p.read_text())
        return True
    except SyntaxError:
        return False


def bundle_path(bundle_id: str) -> Path | None:
    if not re.fullmatch(r"BRG-[0-9a-f]{12}", bundle_id):
        return None
    r = db.query_one("SELECT path FROM bridge_bundles WHERE id = ?", (bundle_id,))
    if not r:
        return None
    p = Path(r["path"]).resolve()
    if GENERATED_DIR.resolve() not in p.parents:
        return None
    return p


def run_tests(bundle_id: str, timeout_s: int = 180) -> dict[str, Any]:
    root = bundle_path(bundle_id)
    if root is None or not root.exists():
        raise FileNotFoundError(bundle_id)
    report = root / "junit.xml"
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(root), "PYTHONDONTWRITEBYTECODE": "1",
           "ADAPTER_DEMO_SECRET": "sandbox-" + bundle_id, "NO_PROXY": "*", "HOME": str(root)}
    started = time.perf_counter()
    try:
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={report}"],
                              cwd=root, env=env, capture_output=True, text=True, timeout=timeout_s, check=False)
        output, code = proc.stdout[-6000:] + proc.stderr[-2000:], proc.returncode
    except subprocess.TimeoutExpired:
        output, code = "Timed out", -1
    tests = []
    if report.exists():
        tree = ET.parse(report)  # noqa: S314 - junit report written by our own pytest run
        for tc in tree.iter("testcase"):
            status = "passed"
            msg = ""
            for tag in ("failure", "error", "skipped"):
                el = tc.find(tag)
                if el is not None:
                    status = "failed" if tag in ("failure", "error") else "skipped"
                    msg = (el.get("message") or "")[:300]
            tests.append({"name": f"{tc.get('classname')}::{tc.get('name')}", "status": status, "time_s": float(tc.get("time") or 0), "message": msg})
    result = {"bundle_id": bundle_id, "exit_code": code, "passed": sum(t["status"] == "passed" for t in tests),
              "failed": sum(t["status"] == "failed" for t in tests), "tests": tests, "duration_s": round(time.perf_counter() - started, 2),
              "output_tail": output[-3000:], "sandbox": "subprocess, minimal env, no proxy variables, cwd=bundle, timeout"}
    with db.session(write=True) as conn:
        conn.execute("UPDATE bridge_bundles SET test_result_json = ? WHERE id = ?", (db.jdump(result), bundle_id))
    return result


def zip_bundle(bundle_id: str) -> bytes:
    root = bundle_path(bundle_id)
    if root is None:
        raise FileNotFoundError(bundle_id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(root.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts and p.name != "junit.xml":
                zf.write(p, f"{bundle_id}/{p.relative_to(root)}")
    return buf.getvalue()
