"""Software change-impact analysis over THIS repository (authorized: the user's own code) + a labelled synthetic requirement set.

Static analysis only: Python imports (ast), FastAPI route decorators, TypeScript imports and API path references, test imports.
It is import-based reachability, not line coverage and not a certification argument. Results are evidence for an engineer to review.
"""

from __future__ import annotations

import ast
import re
from collections import defaultdict, deque
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.core.config import BACKEND_DIR, FIXTURES_DIR, REPO_ROOT

APP_DIR = BACKEND_DIR / "app"
TEST_DIR = BACKEND_DIR / "tests"
FRONT_DIR = REPO_ROOT / "frontend" / "src"
ROUTE = re.compile(r"@router\.(get|post|put|delete|patch)\(\s*\"([^\"]+)\"")
TS_IMPORT = re.compile(r"""from\s+["'](@/[^"']+|\.{1,2}/[^"']+)["']""")
TS_API = re.compile(r"""["'`](/api/[a-zA-Z0-9_/\-{}$]+)""")


def _mod(path: Path) -> str:
    rel = path.relative_to(BACKEND_DIR).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


@lru_cache(maxsize=1)
def graph() -> dict[str, Any]:
    modules: dict[str, dict[str, Any]] = {}
    for p in sorted(APP_DIR.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        src = p.read_text(encoding="utf-8")
        tree = ast.parse(src)
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app"):
                subs = {f"{node.module}.{a.name}" for a in node.names}
                imports.update(subs)
                if not any((APP_DIR.parent / (x.replace(".", "/") + ".py")).exists() or (APP_DIR.parent / x.replace(".", "/")).is_dir() for x in subs):
                    imports.add(node.module)  # importing symbols from a module, not submodules from a package
            elif isinstance(node, ast.Import):
                imports.update(a.name for a in node.names if a.name.startswith("app"))
        symbols = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef))]
        modules[_mod(p)] = {"path": str(p.relative_to(REPO_ROOT)), "imports": imports, "symbols": symbols, "lines": src.count("\n") + 1,
                            "routes": [f"{m.upper()} {u}" for m, u in ROUTE.findall(src)]}
    names = set(modules)
    for m in modules.values():  # keep only edges to real modules (from x import y may name a symbol, not a module)
        m["deps"] = sorted({i for i in m["imports"] if i in names})
    rev: dict[str, set[str]] = defaultdict(set)
    for name, m in modules.items():
        for d in m["deps"]:
            if d != name:
                rev[d].add(name)
    tests: dict[str, set[str]] = {}
    for p in sorted(TEST_DIR.glob("test_*.py")):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        imp = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app"):
                subs = {f"{node.module}.{a.name}" for a in node.names} & names
                imp.update(subs or {node.module})
        if "client" in p.read_text(encoding="utf-8"):
            imp.add("app.main")  # API tests exercise the whole application through the TestClient
        tests[str(p.relative_to(BACKEND_DIR))] = {i for i in imp if i in names}
    front: dict[str, dict[str, Any]] = {}
    if FRONT_DIR.exists():
        for p in sorted(FRONT_DIR.rglob("*.ts*")):
            src = p.read_text(encoding="utf-8")
            front[str(p.relative_to(REPO_ROOT))] = {"imports": TS_IMPORT.findall(src), "api": sorted(set(TS_API.findall(src)))}
    return {"modules": modules, "reverse": {k: sorted(v) for k, v in rev.items()}, "tests": {k: sorted(v) for k, v in tests.items()}, "frontend": front}


def resolve(target: str) -> list[str]:
    g = graph()
    t = target.strip()
    mods = g["modules"]
    if t in mods:
        return [t]
    if t.startswith("/api/"):
        return [m for m, v in mods.items() if any(r.split(" ", 1)[1] == t or r.split(" ", 1)[1].startswith(t.rstrip("/") + "/") for r in v["routes"])]
    if t.endswith(".py"):
        return [m for m, v in mods.items() if v["path"].endswith(t)]
    hits = [m for m, v in mods.items() if t in v["symbols"]]
    return hits or [m for m in mods if m.endswith("." + t) or t.lower() in m.lower()][:5]


def analyze(target: str, max_depth: int = 6) -> dict[str, Any]:
    g = graph()
    roots = resolve(target)
    if not roots:
        return {"target": target, "resolved": [], "error": "No module, symbol, file or API route matches that target."}
    dist: dict[str, int] = {r: 0 for r in roots}
    dq = deque(roots)
    while dq:
        m = dq.popleft()
        if dist[m] >= max_depth:
            continue
        for user in g["reverse"].get(m, []):
            if user not in dist:
                dist[user] = dist[m] + 1
                dq.append(user)
    affected = sorted(dist.items(), key=lambda kv: (kv[1], kv[0]))
    routes = sorted({r for m in dist for r in g["modules"][m]["routes"]})
    tests = []
    for t, imps in g["tests"].items():
        hit = [m for m in imps if m in dist]
        if hit:
            tests.append({"test": t, "via": sorted(hit, key=lambda m: dist[m])[:4], "distance": min(dist[m] for m in hit)})
    tests.sort(key=lambda x: (x["distance"], x["test"]))
    paths = {r.split(" ", 1)[1] for r in routes}
    front = [{"file": f, "calls": [a for a in v["api"] if any(a.split("?")[0].split("$")[0].rstrip("/") == p.split("{")[0].rstrip("/")
                                                               or p.split("{")[0].rstrip("/").startswith(a.split("?")[0].split("$")[0].rstrip("/") + "/") for p in paths)]}
             for f, v in g["frontend"].items()]
    front = [f for f in front if f["calls"]]
    reqs = traceability()
    impacted_reqs = [r for r in reqs["requirements"] if set(r["modules"]) & set(dist)]
    risk = "high" if len(dist) > 15 or any(r.get("level", "").startswith("safety") for r in impacted_reqs) else "medium" if len(dist) > 5 else "low"
    return {
        "target": target, "resolved": roots, "risk": risk,
        "affected_modules": [{"module": m, "distance": d, "path": g["modules"][m]["path"], "lines": g["modules"][m]["lines"]} for m, d in affected],
        "affected_routes": routes, "affected_frontend": front[:25],
        "recommended_tests": tests, "untested_affected_modules": [m for m in dist if not any(m in v for v in g["tests"].values())][:20],
        "requirements": impacted_reqs,
        "graph": {"nodes": [{"id": m, "label": m.replace("app.", ""), "distance": d} for m, d in affected][:60],
                  "edges": [{"source": m, "target": u} for m in dist for u in g["reverse"].get(m, []) if u in dist][:150]},
        "method": "Static import graph (ast) + route decorators + test imports + TypeScript API references. Not line coverage.",
    }


def traceability() -> dict[str, Any]:
    data = yaml.safe_load((FIXTURES_DIR / "engineering" / "requirements.yaml").read_text())
    g = graph()
    out = []
    for r in data["requirements"]:
        missing_mod = [m for m in r["modules"] if m not in g["modules"]]
        ver = [{"file": v, "exists": (BACKEND_DIR / v).exists()} for v in r["verification"]]
        out.append({**r, "missing_modules": missing_mod, "verification": ver,
                    "status": "missing_verification" if any(not v["exists"] for v in ver) else "missing_module" if missing_mod else "traced"})
    return {"project": data["project"], "synthetic": True, "requirements": out,
            "summary": {"traced": sum(r["status"] == "traced" for r in out), "missing_verification": sum(r["status"] == "missing_verification" for r in out),
                        "missing_module": sum(r["status"] == "missing_module" for r in out)}}


def compare_config(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    sensitive = re.compile(r"(?i)offline|egress|llm_url|base_url|secret|token|cors|policy|kill|approval|model_path|enabled")
    keys = sorted(set(before) | set(after))
    changes = []
    for k in keys:
        if before.get(k) != after.get(k):
            kind = "added" if k not in before else "removed" if k not in after else "changed"
            changes.append({"key": k, "kind": kind, "before": before.get(k), "after": after.get(k),
                            "risk": "review" if sensitive.search(k) else "low"})
    return {"changes": changes, "review_required": [c["key"] for c in changes if c["risk"] == "review"]}


def overview() -> dict[str, Any]:
    g = graph()
    return {"modules": len(g["modules"]), "tests": len(g["tests"]), "frontend_files": len(g["frontend"]),
            "routes": sum(len(m["routes"]) for m in g["modules"].values()),
            "top_fan_in": sorted(((m, len(v)) for m, v in g["reverse"].items()), key=lambda kv: -kv[1])[:10],
            "traceability": traceability()["summary"]}
