"""Offline metadata parsers for Legacy X-Ray.

Uploaded content is parsed as text only. Nothing is executed: SQL is matched
with regular expressions, YAML uses safe_load, XML rejects DTDs/entities, and
ZIP members are size-, count-, ratio- and path-checked before reading. Python
files are analysed with the `ast` module (parse only); Java with regexes.
"""

from __future__ import annotations

import ast
import csv
import io
import json
import re
import zipfile
from pathlib import PurePosixPath
from typing import Any

import yaml

ALLOWED_EXT = {".sql", ".json", ".yaml", ".yml", ".csv", ".zip", ".xml"}
MAX_ZIP_MEMBERS = 200
MAX_ZIP_TOTAL = 20 * 1024 * 1024
MAX_ZIP_RATIO = 50
MAX_MEMBER = 2 * 1024 * 1024


class ImportRejected(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def safe_filename(name: str) -> str:
    base = PurePosixPath(name.replace("\\", "/")).name
    base = re.sub(r"[^A-Za-z0-9._\-]", "_", base)[:120]
    if not base or base.startswith("."):
        raise ImportRejected("bad_filename", "Filename is empty or hidden after sanitization.")
    return base


def extension(name: str) -> str:
    return PurePosixPath(name.lower()).suffix


def detect_kind(name: str, text: str) -> str:
    ext = extension(name)
    if ext == ".sql":
        return "sql_ddl"
    if ext == ".csv":
        return "csv"
    if ext == ".xml":
        return "odata_metadata"
    if ext in {".json", ".yaml", ".yml"}:
        try:
            doc = json.loads(text) if ext == ".json" else yaml.safe_load(text)
        except Exception as err:  # noqa: BLE001
            raise ImportRejected("parse_error", f"Could not parse {ext} content: {err}") from err
        if isinstance(doc, dict) and ("openapi" in doc or "swagger" in doc):
            return "openapi"
        if isinstance(doc, dict) and "applications" in doc and "dependencies" in doc:
            return "dependency_graph"
        if isinstance(doc, dict) and ("$schema" in doc or "x-topic" in doc):
            return "event_schema"
        return "unknown_json"
    return "unsupported"


def _decode(raw: bytes) -> str:
    if b"\x00" in raw[:4096]:
        raise ImportRejected("binary_content", "File looks binary; only text metadata is accepted.")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


# ---------------------------------------------------------------- SQL DDL

_CREATE_TABLE = re.compile(r"CREATE\s+TABLE\s+([\w.\"]+)\s*\((.*?)\)\s*;", re.I | re.S)
_CREATE_VIEW = re.compile(r"CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+([\w.\"]+)\s+AS\s+(.*?);", re.I | re.S)
_FK_INLINE = re.compile(r"REFERENCES\s+([\w.\"]+)\s*\(\s*([\w\"]+)\s*\)", re.I)
_FK_CONSTRAINT = re.compile(r"FOREIGN\s+KEY\s*\(\s*([\w\"]+)\s*\)\s*REFERENCES\s+([\w.\"]+)\s*\(\s*([\w\"]+)\s*\)", re.I)
_META = re.compile(r"^--\s*([a-z_]+)\s*:\s*(.+)$", re.I | re.M)


def _split_columns(body: str) -> list[str]:
    parts, depth, cur = [], 0, []
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def parse_sql(text: str) -> dict[str, Any]:
    meta = {k.lower(): v.strip() for k, v in _META.findall(text)}
    clean = re.sub(r"--[^\n]*", "", text)
    tables, fks, views = [], [], []
    for name, body in _CREATE_TABLE.findall(clean):
        tname = name.strip('"').upper()
        cols, pk = [], []
        for item in _split_columns(body):
            up = item.upper()
            m = _FK_CONSTRAINT.search(item)
            if m:
                fks.append({"from_table": tname, "from_column": m.group(1).strip('"').upper(),
                            "to_table": m.group(2).strip('"').upper(), "to_column": m.group(3).strip('"').upper(), "kind": "constraint"})
                continue
            if up.startswith(("CONSTRAINT", "PRIMARY KEY", "UNIQUE", "CHECK", "INDEX", "KEY ")):
                pkm = re.search(r"PRIMARY\s+KEY\s*\(([^)]*)\)", item, re.I)
                if pkm:
                    pk += [c.strip().strip('"').upper() for c in pkm.group(1).split(",")]
                continue
            tokens = item.split()
            if len(tokens) < 2:
                continue
            col = {"name": tokens[0].strip('"').upper(), "type": tokens[1].upper(), "nullable": "NOT NULL" not in up,
                   "primary_key": "PRIMARY KEY" in up}
            if col["primary_key"]:
                pk.append(col["name"])
            fk = _FK_INLINE.search(item)
            if fk:
                fks.append({"from_table": tname, "from_column": col["name"], "to_table": fk.group(1).strip('"').upper(),
                            "to_column": fk.group(2).strip('"').upper(), "kind": "inline"})
            cols.append(col)
        tables.append({"name": tname, "columns": cols, "primary_key": pk})
    for name, body in _CREATE_VIEW.findall(clean):
        refs = sorted({t.upper() for t in re.findall(r"(?:FROM|JOIN)\s+([\w.]+)", body, re.I)})
        views.append({"name": name.strip('"').upper(), "references": refs, "read_only_candidate": True})
    findings = _sql_findings(tables, fks, meta)
    return {"kind": "sql_ddl", "metadata": meta, "tables": tables, "foreign_keys": fks, "views": views, "findings": findings,
            "summary": {"tables": len(tables), "columns": sum(len(t["columns"]) for t in tables), "foreign_keys": len(fks), "views": len(views)}}


def _sql_findings(tables: list[dict[str, Any]], fks: list[dict[str, Any]], meta: dict[str, str]) -> list[dict[str, Any]]:
    out = []
    names = {t["name"] for t in tables}
    for t in tables:
        if not t["primary_key"]:
            out.append({"severity": "medium", "kind": "no_primary_key", "object": t["name"],
                        "detail": "Table has no primary key; change data capture and idempotent sync are harder."})
        generic = [c["name"] for c in t["columns"] if re.fullmatch(r"CH_\d+|COL\d+|FIELD\d+", c["name"])]
        if generic:
            out.append({"severity": "medium", "kind": "opaque_columns", "object": t["name"],
                        "detail": f"Opaque column names {generic}; semantics unknown, needs SME confirmation."})
        if re.match(r"(TMP|TEMP|BAK|OLD)_", t["name"]):
            out.append({"severity": "low", "kind": "temporary_table", "object": t["name"],
                        "detail": "Looks like a leftover temporary/sync table; confirm ownership before migrating."})
        if any(c["type"].startswith(("CLOB", "BLOB", "LONG")) for c in t["columns"]):
            out.append({"severity": "low", "kind": "lob_payload", "object": t["name"],
                        "detail": "Large object payload column; opaque to analytics and APIs."})
        for c in t["columns"]:
            if c["name"].endswith(("_CODES", "_LIST")) and c["type"].startswith(("VARCHAR", "TEXT")):
                out.append({"severity": "medium", "kind": "multi_value_column", "object": f"{t['name']}.{c['name']}",
                            "detail": "Delimited multi-value column; no expiry or relational integrity (e.g. qualifications)."})
    for fk in fks:
        if fk["to_table"] not in names:
            out.append({"severity": "medium", "kind": "dangling_reference", "object": fk["from_table"],
                        "detail": f"References {fk['to_table']} which is not in this schema."})
    reviewed = meta.get("last_reviewed")
    if reviewed and reviewed < "2024-01-01":
        out.append({"severity": "medium", "kind": "stale_documentation", "object": meta.get("system", "schema"),
                    "detail": f"Schema documentation last reviewed {reviewed}."})
    return out


# ---------------------------------------------------------------- OpenAPI

WRITE_METHODS = {"post", "put", "patch", "delete"}


def parse_openapi(text: str, ext: str) -> dict[str, Any]:
    doc = json.loads(text) if ext == ".json" else yaml.safe_load(text)
    if not isinstance(doc, dict):
        raise ImportRejected("parse_error", "OpenAPI document is not an object.")
    ops, findings = [], []
    for path, item in (doc.get("paths") or {}).items():
        for method, op in (item or {}).items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            params = [p.get("name") for p in (op.get("parameters") or []) if isinstance(p, dict)]
            paginated = any(p in {"$top", "$skip", "cursor", "page", "limit", "offset"} for p in params)
            o = {"method": method.upper(), "path": path, "operation_id": op.get("operationId"), "summary": op.get("summary", ""),
                 "write": method.lower() in WRITE_METHODS, "paginated": paginated, "parameters": params}
            ops.append(o)
            if re.search(r"sql|exec|admin|debug", path, re.I):
                findings.append({"severity": "high", "kind": "dangerous_endpoint", "object": f"{method.upper()} {path}",
                                 "detail": "Administrative or arbitrary-execution endpoint; must never be exposed to agents."})
            if method.lower() == "get" and not paginated and re.search(r"s$|list", path + (op.get("operationId") or ""), re.I) and "{" not in path:
                findings.append({"severity": "medium", "kind": "no_pagination", "object": f"GET {path}",
                                 "detail": "Collection endpoint without pagination; adapters must cap result sizes."})
            if re.search(r"webhook|callback", path, re.I):
                findings.append({"severity": "high", "kind": "ssrf_surface", "object": f"{method.upper()} {path}",
                                 "detail": "Accepts callback URLs; requires allowlisting to prevent SSRF."})
    schemes = (doc.get("components") or {}).get("securitySchemes") or {}
    auth = [{"name": n, "type": s.get("type"), "in": s.get("in"), "flows": list((s.get("flows") or {}).keys())} for n, s in schemes.items()]
    if any(a["type"] == "apiKey" for a in auth):
        findings.append({"severity": "medium", "kind": "static_api_key", "object": "securitySchemes",
                         "detail": "Static API key authentication; no per-user identity or scope. Wrap behind a gateway with OAuth2 scopes."})
    if not auth:
        findings.append({"severity": "high", "kind": "no_auth_declared", "object": "securitySchemes", "detail": "No security scheme declared."})
    schemas = list(((doc.get("components") or {}).get("schemas") or {}).keys())
    info = doc.get("info") or {}
    servers = [s.get("url") for s in (doc.get("servers") or []) if isinstance(s, dict)]
    return {"kind": "openapi", "title": info.get("title"), "version": info.get("version"), "servers": servers,
            "operations": ops, "auth": auth, "schemas": schemas, "findings": findings,
            "summary": {"operations": len(ops), "read_operations": sum(not o["write"] for o in ops),
                        "write_operations": sum(o["write"] for o in ops), "schemas": len(schemas)}}


# ---------------------------------------------------------------- CSV batch feed

def parse_csv(text: str) -> dict[str, Any]:
    reader = csv.DictReader(io.StringIO(text))
    fields = reader.fieldnames or []
    rows_ = list(reader)[:50000]
    profile = {}
    for f in fields:
        vals = [r.get(f) for r in rows_]
        empties = sum(1 for v in vals if v in (None, ""))
        profile[f] = {"empty": empties, "distinct": len(set(vals)), "sample": [v for v in vals[:3]]}
    findings = []
    for f, p in profile.items():
        if p["empty"]:
            findings.append({"severity": "medium", "kind": "missing_values", "object": f, "detail": f"{p['empty']} empty value(s)."})
    if "rec_type" in fields:
        bad = [i + 2 for i, r in enumerate(rows_) if r.get("rec_type") not in {"IN", "OUT", "ADJ"}]
        if bad:
            findings.append({"severity": "medium", "kind": "invalid_record_type", "object": "rec_type",
                             "detail": f"Unknown record types on lines {bad}; these rows would be quarantined."})
    date_cols = [f for f in fields if "date" in f.lower()]
    stale = []
    for dc in date_cols:
        from app.core.util import DEMO_TODAY
        from datetime import date

        for i, r in enumerate(rows_):
            try:
                if (date.fromisoformat(DEMO_TODAY) - date.fromisoformat(r[dc])).days > 30:
                    stale.append(i + 2)
            except (ValueError, TypeError):
                continue
    if stale:
        findings.append({"severity": "medium", "kind": "stale_counts", "object": ",".join(date_cols),
                         "detail": f"Counts older than 30 days on lines {stale}."})
    return {"kind": "csv", "columns": fields, "row_count": len(rows_), "profile": profile, "findings": findings,
            "summary": {"rows": len(rows_), "columns": len(fields), "quarantine_candidates": sum(1 for f in findings if f["kind"] == "invalid_record_type")}}


# ---------------------------------------------------------------- OData metadata (XML, hardened)

def parse_odata(text: str) -> dict[str, Any]:
    if re.search(r"<!DOCTYPE|<!ENTITY", text, re.I):
        raise ImportRejected("xml_dtd", "XML with DTD or entity declarations is rejected (XXE / entity-expansion protection).")
    import xml.etree.ElementTree as ET

    root = ET.fromstring(text)  # noqa: S314 - DTD/ENTITY declarations rejected above
    ns = {"edm": "http://docs.oasis-open.org/odata/ns/edm"}
    entities = []
    for et in root.iter("{http://docs.oasis-open.org/odata/ns/edm}EntityType"):
        keys = [k.get("Name") for k in et.findall("edm:Key/edm:PropertyRef", ns)]
        props = [{"name": p.get("Name"), "type": p.get("Type"), "nullable": p.get("Nullable", "true") != "false"} for p in et.findall("edm:Property", ns)]
        navs = [{"name": n.get("Name"), "type": n.get("Type")} for n in et.findall("edm:NavigationProperty", ns)]
        entities.append({"name": et.get("Name"), "keys": keys, "properties": props, "navigation": navs})
    sets = [{"name": s.get("Name"), "entity_type": s.get("EntityType")} for s in root.iter("{http://docs.oasis-open.org/odata/ns/edm}EntitySet")]
    return {"kind": "odata_metadata", "entities": entities, "entity_sets": sets, "findings": [],
            "summary": {"entities": len(entities), "entity_sets": len(sets)}}


def parse_event_schema(text: str, ext: str) -> dict[str, Any]:
    doc = json.loads(text) if ext == ".json" else yaml.safe_load(text)
    props = list((doc.get("properties") or {}).keys())
    return {"kind": "event_schema", "title": doc.get("title"), "topic": doc.get("x-topic"), "producer": doc.get("x-producer"),
            "fields": props, "required": doc.get("required", []), "findings": [],
            "summary": {"fields": len(props)}}


# ---------------------------------------------------------------- ZIP bundles (metadata only)

def parse_zip(raw: bytes) -> dict[str, Any]:
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as err:
        raise ImportRejected("bad_zip", "Not a valid ZIP archive.") from err
    infos = zf.infolist()
    if len(infos) > MAX_ZIP_MEMBERS:
        raise ImportRejected("zip_too_many", f"ZIP has {len(infos)} members (limit {MAX_ZIP_MEMBERS}).")
    total = sum(i.file_size for i in infos)
    packed = sum(i.compress_size for i in infos) or 1
    if total > MAX_ZIP_TOTAL:
        raise ImportRejected("zip_too_large", f"Uncompressed size {total} exceeds {MAX_ZIP_TOTAL} bytes.")
    if total / packed > MAX_ZIP_RATIO:
        raise ImportRejected("zip_bomb", f"Compression ratio {total / packed:.0f}:1 exceeds {MAX_ZIP_RATIO}:1 (possible zip bomb).")
    files, unsupported, findings = [], [], []
    for info in infos:
        name = info.filename
        if name.endswith("/"):
            continue
        p = PurePosixPath(name)
        if p.is_absolute() or ".." in p.parts or name.startswith("\\") or re.match(r"^[A-Za-z]:", name):
            raise ImportRejected("zip_traversal", f"Unsafe path in archive: {name!r}")
        if info.external_attr >> 16 & 0o170000 == 0o120000:
            raise ImportRejected("zip_symlink", f"Symbolic link in archive: {name!r}")
        if info.file_size > MAX_MEMBER:
            unsupported.append({"path": name, "reason": "member too large"})
            continue
        ext = p.suffix.lower()
        text = _decode(zf.read(info))
        if ext == ".py":
            files.append(_analyze_python(name, text))
        elif ext == ".java":
            files.append(_analyze_java(name, text))
        elif ext == ".sql":
            r = parse_sql(text)
            files.append({"path": name, "language": "sql", "tables": [t["name"] for t in r["tables"]]})
            findings += r["findings"]
        elif ext in {".json", ".yaml", ".yml"}:
            files.append({"path": name, "language": ext.strip(".")})
        else:
            unsupported.append({"path": name, "reason": f"unsupported type '{ext or 'none'}' (not analysed)"})
    for f in files:
        for s in f.get("secrets_suspected", []):
            findings.append({"severity": "high", "kind": "hardcoded_secret", "object": f["path"], "detail": f"Possible credential literal: {s}"})
        for s in f.get("sql_strings", []):
            findings.append({"severity": "medium", "kind": "embedded_sql", "object": f["path"], "detail": f"Embedded SQL touches {s}"})
    return {"kind": "source_bundle", "files": files, "unsupported": unsupported, "findings": findings,
            "summary": {"analysed_files": len(files), "unsupported_files": len(unsupported), "uncompressed_bytes": total}}


_SECRET = re.compile(r"(?i)(password|passwd|secret|api_key|apikey|token)\s*[:=]\s*[\"'][^\"']{4,}[\"']")
_SQL_TABLE = re.compile(r"(?i)\b(?:from|join|into|update)\s+([A-Z_][A-Z0-9_]+)")


def _analyze_python(path: str, text: str) -> dict[str, Any]:
    out: dict[str, Any] = {"path": path, "language": "python"}
    try:
        tree = ast.parse(text)
    except SyntaxError as err:
        return {**out, "error": f"syntax error line {err.lineno}"}
    out["imports"] = sorted({a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
                            | {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)})
    out["functions"] = [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))][:50]
    out["classes"] = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)][:50]
    strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    out["sql_strings"] = sorted({t.upper() for s in strings if re.search(r"(?i)\bselect|insert|update\b", s) for t in _SQL_TABLE.findall(s)})
    out["secrets_suspected"] = [m.group(1) for m in _SECRET.finditer(text)][:5]
    return out


def _analyze_java(path: str, text: str) -> dict[str, Any]:
    return {"path": path, "language": "java",
            "package": (re.search(r"^\s*package\s+([\w.]+);", text, re.M) or [None, None])[1],
            "imports": re.findall(r"^\s*import\s+([\w.]+);", text, re.M)[:50],
            "classes": re.findall(r"\b(?:class|interface|enum)\s+(\w+)", text)[:50],
            "endpoints": re.findall(r"@(?:Get|Post|Put|Delete|Request)Mapping\(\s*\"?([^\")]+)", text)[:50],
            "sql_strings": sorted({t.upper() for t in _SQL_TABLE.findall(" ".join(re.findall(r"\"([^\"]*(?:SELECT|INSERT|UPDATE)[^\"]*)\"", text, re.I)))}),
            "secrets_suspected": [m.group(1) for m in _SECRET.finditer(text)][:5]}


def parse_upload(filename: str, raw: bytes, max_bytes: int) -> dict[str, Any]:
    name = safe_filename(filename)
    ext = extension(name)
    if ext not in ALLOWED_EXT:
        raise ImportRejected("bad_extension", f"Extension '{ext}' is not supported. Allowed: {sorted(ALLOWED_EXT)}")
    if len(raw) > max_bytes:
        raise ImportRejected("too_large", f"File is {len(raw)} bytes; limit is {max_bytes}.")
    if not raw:
        raise ImportRejected("empty", "File is empty.")
    if ext == ".zip":
        result = parse_zip(raw)
        return {"filename": name, **result}
    text = _decode(raw)
    kind = detect_kind(name, text)
    if kind == "sql_ddl":
        result = parse_sql(text)
    elif kind == "openapi":
        result = parse_openapi(text, ext)
    elif kind == "csv":
        result = parse_csv(text)
    elif kind == "odata_metadata":
        result = parse_odata(text)
    elif kind == "event_schema":
        result = parse_event_schema(text, ext)
    elif kind == "dependency_graph":
        doc = json.loads(text) if ext == ".json" else yaml.safe_load(text)
        result = {"kind": "dependency_graph", "applications": doc["applications"], "dependencies": doc["dependencies"], "findings": [],
                  "summary": {"applications": len(doc["applications"]), "dependencies": len(doc["dependencies"])}}
    else:
        raise ImportRejected("unsupported_content", f"Content kind '{kind}' is not supported.")
    return {"filename": name, **result}
