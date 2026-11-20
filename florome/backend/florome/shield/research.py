"""Vulnerability research workflow, run by a deterministic supervisor.

Agents (stages) and what each may use
-------------------------------------
repository_intelligence   tree-sitter only; reads files inside the authorised root
static_analysis           Opengrep + Bandit (separate processes, timeouts)
dependency_security       Trivy (separate process)
security_hypothesis       stored graph + stored tool evidence; no execution
independent_verification  Cyber Range probes only; receives the route spec derived from code, never the
                          hypothesis' conclusion text, so it cannot "agree" with the research stage by construction
evidence_adjudicator      verification transcripts + static guards
patch_engineering         template patches + Cyber Range regression runs; never writes to the repository
incident_investigation    creates a Florome incident for confirmed high/critical findings

Agents cannot grant permissions: every entry point first passes ``control.authorize``. Each stage records an
``AgentExecution`` with its tools, duration and a summary; the tenant emergency stop cancels stages between steps.
No language model is used; ``model_provenance`` stays empty.
"""

from __future__ import annotations

import difflib
import hashlib
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from florome.config import Settings
from florome.models import Incident, Resource, Tenant, utcnow
from florome.security import audit
from florome.security.injection import scan as injection_scan
from florome.security.rbac import Principal
from florome.shield import code_intel as ci
from florome.shield.control import ShieldDenied, authorize, in_authorized_scope
from florome.shield.models import (
    AgentExecution,
    CodeRelationship,
    CodeSymbol,
    FindingEvidence,
    RemediationPatch,
    Repository,
    RepositorySnapshot,
    ScanRun,
    SecurityHypothesis,
    TrustBoundary,
    VerificationRun,
    VulnerabilityFinding,
)
from florome.shield.range.sandbox import run_probe
from florome.shield.scanners import run_bandit, run_opengrep, run_trivy

AGENTS: dict[str, dict[str, Any]] = {
    "repository_intelligence": {"tools": ["tree-sitter"], "budget_seconds": 120},
    "static_analysis": {"tools": ["opengrep", "bandit"], "budget_seconds": 400},
    "dependency_security": {"tools": ["trivy"], "budget_seconds": 300},
    "security_hypothesis": {"tools": ["graph", "evidence"], "budget_seconds": 30},
    "independent_verification": {"tools": ["cyber_range"], "budget_seconds": 120},
    "evidence_adjudicator": {"tools": ["transcripts"], "budget_seconds": 10},
    "patch_engineering": {"tools": ["patch_templates", "cyber_range"], "budget_seconds": 180},
    "incident_investigation": {"tools": ["florome_incidents"], "budget_seconds": 10},
}
SINK_CLASS = {"sql": "sql_injection", "command": "command_injection", "file": "path_traversal",
              "deserialization": "unsafe_deserialization", "code_exec": "code_injection"}
METHOD = {"sql_injection": "probe_sqli_tautology", "command_injection": "probe_cmd_canary", "path_traversal": "probe_traversal_canary",
          "unsafe_deserialization": "probe_pickle_callable", "broken_access_control": "probe_idor_cross_user"}
BASE_SEVERITY = {"command_injection": "critical", "unsafe_deserialization": "critical", "code_injection": "critical",
                 "sql_injection": "high", "path_traversal": "high", "broken_access_control": "high", "hardcoded_secret": "high",
                 "vulnerable_dependency": "medium"}
LOWER = {"critical": "high", "high": "medium", "medium": "low", "low": "low"}
ASSUMPTION = {
    "sql_injection": "Request values are passed to the database as data, never as SQL syntax.",
    "command_injection": "Request values cannot change which program the server runs or its arguments' structure.",
    "path_traversal": "Clients can only read files inside the intended base directory.",
    "unsafe_deserialization": "Client-supplied bytes cannot choose which Python callables run during decoding.",
    "broken_access_control": "An authenticated user can only read objects they own.",
    "code_injection": "Client input is never evaluated as code.",
}


class ResearchError(RuntimeError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _agent(db: Session, tenant_id: str, name: str, subject: str, fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    spec = AGENTS[name]
    if db.get(Tenant, tenant_id).emergency_stop:
        db.add(AgentExecution(tenant_id=tenant_id, agent=name, subject=subject, status="cancelled", tools_used=spec["tools"], seconds=0.0,
                              error="emergency stop"))
        db.flush()
        raise ShieldDenied("Emergency stop is active: agent cancelled", 423)
    t0 = time.perf_counter()
    try:
        out = fn()
    except ShieldDenied:
        raise
    except Exception as exc:
        db.add(AgentExecution(tenant_id=tenant_id, agent=name, subject=subject, status="failed", tools_used=spec["tools"],
                              seconds=time.perf_counter() - t0, error=f"{type(exc).__name__}: {exc}"[:500]))
        db.flush()
        raise
    secs = time.perf_counter() - t0
    status = "over_budget" if secs > spec["budget_seconds"] else "succeeded"
    db.add(AgentExecution(tenant_id=tenant_id, agent=name, subject=subject, status=status, tools_used=spec["tools"], seconds=secs,
                          output_summary={k: v for k, v in out.items() if isinstance(v, int | float | str | bool)}))
    db.flush()
    return out


# ------------------------------------------------------------------------------------------------ repositories

def register_repository(db: Session, settings: Settings, p: Principal, name: str, path: str, data_class: str = "benchmark") -> Repository:
    scoped = in_authorized_scope(settings, path)
    authorize(db, settings, p, "repository.register", {"id": name, "requires_scope": True, "in_authorized_scope": scoped})
    existing = db.scalars(select(Repository).where(Repository.tenant_id == p.tenant_id, Repository.name == name)).first()
    if existing:
        return existing
    repo = Repository(tenant_id=p.tenant_id, name=name, root=str(Path(path).resolve()), authorized_by=p.user_id, data_class=data_class)
    db.add(repo)
    db.flush()
    return repo


def _sym_id(snapshot_id: str, *parts: Any) -> str:
    return f"{snapshot_id}:{audit.sha256(':'.join(map(str, parts)))[:16]}"


def ingest(db: Session, settings: Settings, p: Principal, repo: Repository) -> RepositorySnapshot:
    authorize(db, settings, p, "repository.ingest", {"id": repo.id, "requires_scope": True, "in_authorized_scope": in_authorized_scope(settings, repo.root)})
    root = Path(repo.root)

    def work() -> dict[str, Any]:
        files = ci.repo_files(root)
        hashes = {str(f.relative_to(root)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
        commit, dirty = ci.git_commit(root)
        prev = db.scalars(select(RepositorySnapshot).where(RepositorySnapshot.repository_id == repo.id)
                          .order_by(RepositorySnapshot.created_at.desc())).first()
        snap = RepositorySnapshot(tenant_id=repo.tenant_id, repository_id=repo.id, commit=commit, dirty=dirty,
                                  tree_hash=audit.sha256(hashes), file_hashes=hashes, analyzer=ci.ANALYZER)
        db.add(snap)
        db.flush()
        reused = [f for f in hashes if prev and prev.file_hashes.get(f) == hashes[f]]
        changed = [f for f in hashes if f not in reused]
        parsed = []
        for rel in changed:
            src = (root / rel).read_bytes()
            parsed.append(ci.parse_python(rel, src) if rel.endswith(".py") else ci.parse_javascript(rel, src))
        reused_syms = 0
        if prev and reused:
            reused_syms = _copy_from_previous(db, prev, snap, set(reused))
        providers = ci.auth_providers(parsed) | {s.name for s in db.scalars(select(CodeSymbol).where(
            CodeSymbol.snapshot_id == snap.id, CodeSymbol.kind.in_(["function", "route"]))) if s.attrs.get("auth_provider")}
        _persist_files(db, snap, parsed, providers)
        snap.stats = {"files": len(hashes), "parsed": len(changed), "reused": len(reused), "reused_symbols": reused_syms,
                      "symbols": db.query(CodeSymbol).filter_by(snapshot_id=snap.id).count(),
                      "relationships": db.query(CodeRelationship).filter_by(snapshot_id=snap.id).count()}
        return {"snapshot_id": snap.id, **snap.stats}

    out = _agent(db, repo.tenant_id, "repository_intelligence", repo.id, work)
    audit.record(db, repo.tenant_id, p.user_id, "shield.ingest", repo.id, "success", out)
    return db.get(RepositorySnapshot, out["snapshot_id"])


def _copy_from_previous(db: Session, prev: RepositorySnapshot, snap: RepositorySnapshot, files: set[str]) -> int:
    n = 0
    for s in db.scalars(select(CodeSymbol).where(CodeSymbol.snapshot_id == prev.id)):
        if s.file in files or s.file == "":  # external nodes (modules, sinks) are shared by every file
            db.add(CodeSymbol(id=s.id.replace(prev.id, snap.id, 1), tenant_id=s.tenant_id, snapshot_id=snap.id, kind=s.kind, name=s.name,
                              qualname=s.qualname, file=s.file, start_line=s.start_line, end_line=s.end_line,
                              attrs={**s.attrs, "reused_from": prev.id}))
            n += 1
    for r in db.scalars(select(CodeRelationship).where(CodeRelationship.snapshot_id == prev.id)):
        if r.file in files:
            db.add(CodeRelationship(tenant_id=r.tenant_id, snapshot_id=snap.id, kind=r.kind, source_id=r.source_id.replace(prev.id, snap.id, 1),
                                    target_id=r.target_id.replace(prev.id, snap.id, 1), file=r.file, line=r.line, attrs=r.attrs,
                                    provenance={**r.provenance, "reused_from": prev.id}))
    db.flush()
    return n


def _persist_files(db: Session, snap: RepositorySnapshot, parsed: list[ci.FileResult], providers: set[str]) -> None:
    t, sid = snap.tenant_id, snap.id
    by_name: dict[str, str] = {}
    externals: dict[str, str] = {}

    def external(kind: str, name: str) -> str:
        key = f"{kind}:{name}"
        if key not in externals:
            externals[key] = _sym_id(sid, "external", key)
            if db.get(CodeSymbol, externals[key]) is None:  # may already exist when carried over from a previous snapshot
                db.add(CodeSymbol(id=externals[key], tenant_id=t, snapshot_id=sid, kind=kind, name=name, qualname=key, file="", start_line=0,
                                  end_line=0, attrs={}))
        return externals[key]

    prov = {"analyzer": "tree-sitter", "resolution": "syntactic"}
    for fr in parsed:
        for fn in fr.functions:
            by_name.setdefault(fn.name, _sym_id(sid, fr.path, fn.qualname, fn.start_line))
    for fr in parsed:
        mod = _sym_id(sid, fr.path, "<module>")
        db.add(CodeSymbol(id=mod, tenant_id=t, snapshot_id=sid, kind="module", name=fr.path, qualname=fr.path, file=fr.path, start_line=1,
                          end_line=0, attrs={"language": fr.language, "sha256": fr.sha256}))
        for imp in fr.imports:
            db.add(CodeRelationship(tenant_id=t, snapshot_id=sid, kind="imports", source_id=mod, target_id=external("module", imp["module"]),
                                    file=fr.path, line=imp["line"], provenance=prov))
        for c in fr.classes:
            cid = _sym_id(sid, fr.path, c["qualname"], c["start_line"])
            db.add(CodeSymbol(id=cid, tenant_id=t, snapshot_id=sid, kind="class", name=c["name"], qualname=c["qualname"], file=fr.path,
                              start_line=c["start_line"], end_line=c["end_line"], attrs={}))
            db.add(CodeRelationship(tenant_id=t, snapshot_id=sid, kind="contains", source_id=mod, target_id=cid, file=fr.path, line=c["start_line"], provenance=prov))
        for fn in fr.functions:
            fid = _sym_id(sid, fr.path, fn.qualname, fn.start_line)
            analysis = ci.analyse_function(fn, providers) if fr.language == "python" else {"auth": [], "params": [], "sinks": []}
            attrs = {"params": fn.params, "decorators": fn.decorators, "route": fn.route, "auth_provider": fn.name in providers,
                     "analysis": analysis, "injection_flags": injection_scan(" ".join(fn.decorators))}
            db.add(CodeSymbol(id=fid, tenant_id=t, snapshot_id=sid, kind="route" if fn.route else "function", name=fn.name,
                              qualname=fn.qualname, file=fr.path, start_line=fn.start_line, end_line=fn.end_line, attrs=attrs))
            db.add(CodeRelationship(tenant_id=t, snapshot_id=sid, kind="contains", source_id=mod, target_id=fid, file=fr.path, line=fn.start_line, provenance=prov))
            for c in fn.calls:
                short = c.callee.split(".")[-1].split("(")[0]
                target = by_name.get(short) if short in by_name and "." not in c.callee else None
                db.add(CodeRelationship(tenant_id=t, snapshot_id=sid, kind="calls", source_id=fid, target_id=target or external("external", c.callee),
                                        file=fr.path, line=c.line, attrs={"callee": c.callee},
                                        provenance={**prov, "resolution": "name_match" if target else "unresolved_external"}))
            for dep in analysis["auth"]:
                db.add(CodeRelationship(tenant_id=t, snapshot_id=sid, kind="authenticated_by", source_id=fid,
                                        target_id=by_name.get(dep.split(".")[-1]) or external("external", dep), file=fr.path, line=fn.start_line,
                                        provenance={**prov, "resolution": "Depends() on a function that raises 401/403"}))
            for s in analysis["sinks"]:
                sink = external("sink", f"{s['category']}:{s['callee']}")
                db.add(CodeRelationship(tenant_id=t, snapshot_id=sid, kind="sink", source_id=fid, target_id=sink, file=fr.path, line=s["line"],
                                        attrs={"category": s["category"], "guards": s["guards"]}, provenance=prov))
                if s["tainted_params"]:
                    db.add(CodeRelationship(tenant_id=t, snapshot_id=sid, kind="data_flow", source_id=fid, target_id=sink, file=fr.path, line=s["line"],
                                            attrs={"params": s["tainted_params"], "guards": s["guards"]},
                                            provenance={**prov, "resolution": "intraprocedural, name-based"}))
            if fn.route:
                db.add(TrustBoundary(tenant_id=t, snapshot_id=sid, route_symbol_id=fid,
                                     kind="authenticated_input" if analysis["auth"] else "unauthenticated_input",
                                     detail={"route": fn.route, "auth": analysis["auth"], "params": analysis["params"]}))
    db.flush()


# ------------------------------------------------------------------------------------------------ scanning

def scan(db: Session, settings: Settings, p: Principal, repo: Repository, snap: RepositorySnapshot) -> ScanRun:
    authorize(db, settings, p, "repository.scan", {"id": repo.id, "requires_scope": True, "in_authorized_scope": in_authorized_scope(settings, repo.root)})
    run = ScanRun(tenant_id=repo.tenant_id, snapshot_id=snap.id, started_by=p.user_id, status="running")
    db.add(run)
    db.flush()
    root = Path(repo.root)
    tool_runs = []

    def static() -> dict[str, Any]:
        rs = [run_opengrep(settings, root), run_bandit(settings, root)]
        tool_runs.extend(rs)
        return {"findings": sum(len(r.findings) for r in rs)}

    def deps() -> dict[str, Any]:
        r = run_trivy(settings, root)
        tool_runs.append(r)
        return {"findings": len(r.findings)}

    _agent(db, repo.tenant_id, "static_analysis", run.id, static)
    _agent(db, repo.tenant_id, "dependency_security", run.id, deps)
    for tr in tool_runs:
        for f in tr.findings:
            db.add(FindingEvidence(tenant_id=repo.tenant_id, scan_id=run.id, tool=f.tool, tool_version=f.tool_version, rule_id=f.rule_id,
                                   vuln_class=f.vuln_class, cwe=f.cwe, severity=f.severity, file=f.file, line=f.line, message=f.message,
                                   fingerprint=f.fingerprint(repo.id, snap.tree_hash), raw=f.raw))
    db.flush()
    run.tools = [t.summary() for t in tool_runs]
    run.status = "succeeded" if all(t.status == "succeeded" for t in tool_runs) else ("partial" if any(t.status == "succeeded" for t in tool_runs) else "failed")
    _agent(db, repo.tenant_id, "security_hypothesis", run.id, lambda: {"hypotheses": generate_hypotheses(db, repo, snap, run)})
    run.finished_at = utcnow()
    audit.record(db, repo.tenant_id, p.user_id, "shield.scan", repo.id, run.status, {"scan": run.id, "tools": run.tools})
    return run


def generate_hypotheses(db: Session, repo: Repository, snap: RepositorySnapshot, run: ScanRun) -> int:
    root = Path(repo.root)
    has_range = (root / "range.json").is_file()
    evidence = db.scalars(select(FindingEvidence).where(FindingEvidence.scan_id == run.id)).all()
    symbols = db.scalars(select(CodeSymbol).where(CodeSymbol.snapshot_id == snap.id, CodeSymbol.kind.in_(["function", "route"]))).all()
    created: dict[str, SecurityHypothesis] = {}
    attached: set[str] = set()

    def tool_support(sym: CodeSymbol, cls: str) -> list[dict[str, Any]]:
        out = []
        for e in evidence:
            if e.file == sym.file and sym.start_line <= e.line <= sym.end_line and e.vuln_class == cls:
                out.append({"type": "tool", "ref": e.id, "detail": f"{e.tool} {e.tool_version} {e.rule_id}: {e.message[:120]} (line {e.line})"})
                attached.add(e.id)
        return out

    def add(sym: CodeSymbol, cls: str, line: int, weakness: str, supporting: list, contradicting: list, spec: dict | None) -> None:
        fp = audit.sha256({"repo": repo.id, "tree": snap.tree_hash, "symbol": sym.qualname, "file": sym.file, "class": cls})
        if fp in created:
            return
        h = SecurityHypothesis(tenant_id=repo.tenant_id, snapshot_id=snap.id, scan_id=run.id, vuln_class=cls, symbol_id=sym.id, function=sym.qualname,
                               file=sym.file, line=line, assumption=ASSUMPTION.get(cls, "Input handling is safe."), weakness=weakness,
                               supporting=supporting, contradicting=contradicting,
                               verification_method=METHOD.get(cls) if (spec and has_range) else None, fingerprint=fp)
        h.status_basis = "Awaiting verification." if h.verification_method else "No safe verification method for this target."
        db.add(h)
        created[fp] = h
        if spec:
            h.supporting = supporting + [{"type": "route", "ref": sym.id, "detail": f"{spec['http_method']} {spec['path']}", "spec": spec}]

    for sym in symbols:
        a = sym.attrs.get("analysis", {})
        route = sym.attrs.get("route")
        auth = a.get("auth", [])
        exposure = {"type": "graph", "ref": sym.id, "detail": "reachable without authentication" if (route and not auth) else
                    (f"requires authentication via {', '.join(auth)}" if route else "no HTTP entry point found")}
        for s in a.get("sinks", []):
            if not s["tainted_params"]:
                continue
            cls = SINK_CLASS[s["category"]]
            flow = {"type": "data_flow", "ref": sym.id, "detail": f"parameter(s) {', '.join(s['tainted_params'])} reach {s['callee']} at line {s['line']} "
                                                                  f"(intraprocedural, name-based)"}
            supporting = [flow, exposure, *tool_support(sym, cls)]
            if s.get("dynamic_sql"):
                supporting.append({"type": "graph", "ref": sym.id, "detail": "SQL text is built dynamically"})
            if s["kwargs"].get("shell") == "True":
                supporting.append({"type": "graph", "ref": sym.id, "detail": "process started with shell=True"})
            contradicting = [{"type": "guard", "ref": sym.id, "detail": g} for g in s["guards"] if g != "owner_filter_in_query"]
            spec = ({"http_method": route["method"], "path": route["path"], "param": s["tainted_params"][0], "authenticated": bool(auth)}
                    if route else None)
            add(sym, cls, s["line"], f"{s['callee']} receives request data", supporting, contradicting, spec)
            # Broken access control: an authenticated route loads an object by a client-supplied id.
            id_params = [x for x in s["tainted_params"] if re.search(r"(^|_)id$", x)]
            if route and auth and s["category"] == "sql" and id_params and "{" + id_params[0] + "}" in route["path"]:
                owner = [{"type": "guard", "ref": sym.id, "detail": "owner_filter_in_query"}] if "owner_filter_in_query" in s["guards"] else []
                add(sym, "broken_access_control", s["line"], "object fetched by client-supplied id",
                    [{"type": "graph", "ref": sym.id, "detail": f"path parameter {id_params[0]} selects the object"}, exposure], owner,
                    {**spec, "param": id_params[0]})
    # Tool evidence that no graph hypothesis explains is kept, unverified, rather than dropped.
    for e in evidence:
        if e.id in attached or e.vuln_class in ("other",):
            continue
        sym = next((s for s in symbols if s.file == e.file and s.start_line <= e.line <= s.end_line), None)
        holder = sym or CodeSymbol(id=f"{snap.id}:module:{e.file}", qualname=f"<module {e.file}>", file=e.file, name="<module>", start_line=e.line, end_line=e.line)
        add(holder, e.vuln_class, e.line, e.message[:300], [{"type": "tool", "ref": e.id, "detail": f"{e.tool} {e.rule_id}: {e.message[:120]}"}], [], None)
    db.flush()
    return len(created)


# ------------------------------------------------------------------------------------------- verification

def _route_spec(h: SecurityHypothesis) -> dict[str, Any] | None:
    return next((s["spec"] for s in h.supporting if s.get("type") == "route"), None)


def verify(db: Session, settings: Settings, p: Principal, h: SecurityHypothesis) -> VulnerabilityFinding:
    repo = _repo_for(db, h)
    authorize(db, settings, p, "hypothesis.verify", {"id": h.id, "requires_scope": True, "in_authorized_scope": in_authorized_scope(settings, repo.root)})
    spec = _route_spec(h)
    if h.verification_method and spec:
        def work() -> dict[str, Any]:
            outcomes = []
            for attempt in (1, 2):  # two independent runs, fresh copy and canary each time
                res = run_probe(settings, Path(repo.root), {"method": h.verification_method, **spec})
                db.add(VerificationRun(tenant_id=h.tenant_id, hypothesis_id=h.id, method=h.verification_method, attempt=attempt,
                                       outcome=res["outcome"], isolation=res.get("isolation", {}),
                                       transcript={"probe": res.get("probe"), "error": res.get("error"), "stderr_tail": res.get("stderr_tail")},
                                       seconds=res.get("seconds", 0.0)))
                outcomes.append(res["outcome"])
            db.flush()
            return {"outcomes": ",".join(outcomes)}

        _agent(db, h.tenant_id, "independent_verification", h.id, work)
    finding = _agent(db, h.tenant_id, "evidence_adjudicator", h.id, lambda: {"finding": adjudicate(db, h).id})["finding"]
    f = db.get(VulnerabilityFinding, finding)
    if f.status == "confirmed" and f.severity in ("high", "critical") and f.incident_id is None:
        _agent(db, h.tenant_id, "incident_investigation", h.id, lambda: {"incident": open_incident(db, repo, h, f)})
    audit.record(db, h.tenant_id, p.user_id, "shield.verify", h.id, "success", {"status": f.status, "severity": f.severity})
    return f


def adjudicate(db: Session, h: SecurityHypothesis) -> VulnerabilityFinding:
    runs = db.scalars(select(VerificationRun).where(VerificationRun.hypothesis_id == h.id, VerificationRun.purpose == "verify")
                      .order_by(VerificationRun.created_at.desc())).all()[:2]
    guards = [c["detail"] for c in h.contradicting if c.get("type") == "guard"]
    has_flow = any(s.get("type") == "data_flow" for s in h.supporting)
    outcomes = [r.outcome for r in runs]
    if len(runs) == 2 and outcomes == ["reproduced", "reproduced"]:
        status, basis = "confirmed", "Reproduced in 2 of 2 isolated runs with independent canaries."
    elif len(runs) == 2 and outcomes == ["not_reproduced", "not_reproduced"]:
        if guards:
            status, basis = "disproven", f"Probe executed cleanly in 2 of 2 runs without reproducing; guard present: {', '.join(guards)}."
        else:
            status, basis = "inconclusive", "Probe did not reproduce, but no guard explains why; the probe may be inadequate."
    elif runs:
        status, basis = "inconclusive", f"Verification outcomes were inconsistent or failed: {', '.join(outcomes)}."
    elif has_flow and not guards:
        status, basis = "probable", "Static data flow to a sink with no guard; no safe verification method for this target."
    else:
        status, basis = "inconclusive", "Static evidence only (tool match without an established data flow or entry point)."
    h.status, h.status_basis = status, basis
    base = BASE_SEVERITY.get(h.vuln_class, "medium")
    exposure = next((s["detail"] for s in h.supporting if s.get("type") == "graph" and "authentication" in s["detail"]), "exposure unknown")
    if status == "disproven":
        sev, sev_basis = "none", "Disproven findings carry no severity."
    elif "without authentication" in exposure:
        sev, sev_basis = base, f"Class baseline {base}; {exposure}."
    else:
        sev, sev_basis = LOWER[base] if base == "critical" else base, f"Class baseline {base}; {exposure}."
    f = db.scalars(select(VulnerabilityFinding).where(VulnerabilityFinding.hypothesis_id == h.id)).first()
    if f is None:
        f = VulnerabilityFinding(tenant_id=h.tenant_id, hypothesis_id=h.id, status=status, severity=sev, severity_basis=sev_basis)
        db.add(f)
    else:
        f.status, f.severity, f.severity_basis = status, sev, sev_basis
    db.flush()
    return f


def open_incident(db: Session, repo: Repository, h: SecurityHypothesis, f: VulnerabilityFinding) -> str:
    ref = f"shield://{repo.name}"
    res = db.scalars(select(Resource).where(Resource.tenant_id == repo.tenant_id, Resource.source_ref == ref)).first()
    if res is None:
        res = Resource(id=f"res-shield-{repo.id[-8:]}", tenant_id=repo.tenant_id, connection_id=None, platform="shield", kind="repository",
                       name=repo.name, environment="dev", source_ref=ref, attributes={"root": repo.root}, is_demo=repo.data_class != "production")
        db.add(res)
        db.flush()
    inc = Incident(tenant_id=repo.tenant_id, title=f"Security: {h.vuln_class.replace('_', ' ')} in {h.function} ({repo.name})",
                   severity={"critical": "sev1", "high": "sev2"}.get(f.severity, "sev3"), primary_resource_id=res.id, detected_at=utcnow(),
                   symptoms=[h.weakness, h.status_basis], source_system="florome-shield", source_ref=h.id, is_demo=res.is_demo)
    db.add(inc)
    db.flush()
    f.incident_id = inc.id
    return inc.id


def _repo_for(db: Session, h: SecurityHypothesis) -> Repository:
    snap = db.get(RepositorySnapshot, h.snapshot_id)
    return db.get(Repository, snap.repository_id)


# ------------------------------------------------------------------------------------------------- patching

RESTRICTED_UNPICKLER = '''

class _RestrictedUnpickler(pickle.Unpickler):
    """Florome Shield patch: only plain data types may be decoded."""

    _ALLOWED = {("builtins", n) for n in ("dict", "list", "tuple", "set", "frozenset", "str", "int", "float", "bool", "bytes")}

    def find_class(self, module, name):
        if (module, name) in self._ALLOWED:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f"forbidden global {module}.{name}")


def _restricted_loads(data: bytes):
    import io

    return _RestrictedUnpickler(io.BytesIO(data)).load()
'''


def make_patch(source: str, h: SecurityHypothesis, auth_param: str | None) -> str | None:
    """Template patches for five classes. Returns patched source or None when no template applies."""
    lines = source.splitlines(keepends=True)
    i = h.line - 1
    line = lines[i]
    cls = h.vuln_class
    if cls == "sql_injection":
        m = re.search(r'execute\(f"([^"]*)"\)', line)
        if not m:
            return None
        params = re.findall(r"'\{([^}]+)\}'", m.group(1))
        sql = re.sub(r"'\{[^}]+\}'", "?", m.group(1))
        lines[i] = line.replace(m.group(0), f'execute("{sql}", ({", ".join(params)},))')
    elif cls == "command_injection":
        m = re.search(r'subprocess\.(\w+)\(f"([^"]*)", shell=True, ', line)
        if not m:
            return None
        argv = ", ".join(t[1:-1] if t.startswith("{") else f'"{t}"' for t in m.group(2).split())
        lines[i] = line.replace(m.group(0), f"subprocess.{m.group(1)}([{argv}], ")
    elif cls == "path_traversal":
        m = re.search(r"open\(os\.path\.join\((\w+), (\w+)\)\)", line)
        if not m:
            return None
        indent = line[: len(line) - len(line.lstrip())]
        base, name = m.group(1), m.group(2)
        guard = (f"{indent}_target = (Path({base}) / {name}).resolve()\n"
                 f"{indent}if not str(_target).startswith(str(Path({base}).resolve()) + os.sep):\n"
                 f"{indent}    raise HTTPException(400, \"invalid path\")\n")
        lines[i] = guard + line.replace(m.group(0), "open(_target)")
    elif cls == "unsafe_deserialization":
        if "pickle.loads(" not in line:
            return None
        lines[i] = line.replace("pickle.loads(", "_restricted_loads(")
        first_def = next(k for k, ln in enumerate(lines) if ln.startswith(("def ", "@", "class ", "async def ")))
        lines.insert(first_def, RESTRICTED_UNPICKLER.lstrip("\n") + "\n\n")
    elif cls == "broken_access_control":
        m = re.search(r'execute\("([^"]*)", \(([^)]*)\)\)', line)
        if not m or not auth_param:
            return None
        items = [x.strip() for x in m.group(2).split(",") if x.strip()]
        lines[i] = line.replace(m.group(0), f'execute("{m.group(1)} AND owner = ?", ({", ".join([*items, auth_param])},))')
    else:
        return None
    return "".join(lines)


def generate_patch(db: Session, settings: Settings, p: Principal, h: SecurityHypothesis) -> RemediationPatch:
    repo = _repo_for(db, h)
    authorize(db, settings, p, "patch.generate", {"id": h.id, "requires_scope": True, "in_authorized_scope": in_authorized_scope(settings, repo.root)})
    if h.status != "confirmed":
        raise ResearchError("Patches are generated only for confirmed findings", 409)
    spec = _route_spec(h)
    source = (Path(repo.root) / h.file).read_text()
    sym = db.get(CodeSymbol, h.symbol_id)
    auth_param = next((pr["name"] for pr in (sym.attrs.get("params", []) if sym else []) if pr["default"].startswith("Depends(")), None)

    def work() -> dict[str, Any]:
        patched = make_patch(source, h, auth_param)
        if patched is None:
            raise ResearchError(f"No patch template applies to this {h.vuln_class} site", 422)
        diff = "".join(difflib.unified_diff(source.splitlines(True), patched.splitlines(True), f"a/{h.file}", f"b/{h.file}"))
        results = []
        for attempt in (1, 2):
            res = run_probe(settings, Path(repo.root), {"method": h.verification_method, **spec, "functional_tests": True}, {h.file: patched})
            db.add(VerificationRun(tenant_id=h.tenant_id, hypothesis_id=h.id, method=h.verification_method, purpose="patch_regression",
                                   attempt=attempt, outcome=res["outcome"], isolation=res.get("isolation", {}),
                                   transcript={"probe": res.get("probe"), "error": res.get("error")}, seconds=res.get("seconds", 0.0)))
            results.append(res)
        exploit_blocked = all(r["outcome"] == "not_reproduced" for r in results)
        functional = (results[0].get("probe") or {}).get("functional", [])
        functional_ok = bool(functional) and all(c["passed"] for c in functional)
        patch = RemediationPatch(tenant_id=h.tenant_id, hypothesis_id=h.id, diff=diff, generator=f"template:{h.vuln_class}",
                                 regression={"exploit_blocked_runs": sum(r["outcome"] == "not_reproduced" for r in results), "runs": 2,
                                             "functional": functional, "functional_ok": functional_ok},
                                 status="verified" if exploit_blocked and functional_ok else "failed_regression",
                                 requested_by=p.user_id, patch_hash=audit.sha256(diff))
        db.add(patch)
        db.flush()
        return {"patch": patch.id, "status": patch.status}

    out = _agent(db, h.tenant_id, "patch_engineering", h.id, work)
    audit.record(db, h.tenant_id, p.user_id, "shield.patch.generate", h.id, "success", out)
    return db.get(RemediationPatch, out["patch"])


def review_patch(db: Session, settings: Settings, p: Principal, patch: RemediationPatch, approve: bool, presented_hash: str) -> RemediationPatch:
    authorize(db, settings, p, "patch.review", {"id": patch.id, "requested_by": patch.requested_by})
    if presented_hash != patch.patch_hash:
        raise ResearchError("Patch hash mismatch: the diff changed after it was presented", 409)
    if approve and patch.status != "verified":
        raise ResearchError("Only patches that passed regression can be approved for review", 409)
    patch.status = "approved_for_review" if approve else "rejected"
    patch.reviewed_by = p.user_id
    audit.record(db, patch.tenant_id, p.user_id, "shield.patch.review", patch.id, "success", {"status": patch.status, "patch_hash": patch.patch_hash})
    return patch
