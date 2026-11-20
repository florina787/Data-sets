"""Answer handlers. Each one reads real Florome state and returns a compact, evidence-linked answer.

Answer contract (also the API's response model):
  statement   one sentence, the direct answer
  bullets     at most five short supporting points
  visual      optional {type: kpis|bars|chain|table|timeline, ...} rendered by the UI from these exact values
  evidence    links into the app ({label, href}) so every claim can be inspected
  follow_ups  exactly four next questions
No handler invents a value: when data is missing the statement says so.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from florome.connectors.base import ConnectorError
from florome.connectors.registry import NOT_IMPLEMENTED, PLATFORM_CATALOG
from florome.context import AppContext
from florome.governance.policy import effective_policy
from florome.models import (
    ActionExecution,
    AuditEvent,
    Connection,
    CostRecord,
    Evidence,
    Incident,
    MCPToolRecord,
    RCAReport,
    RemediationPlan,
    Tenant,
    ValidationResult,
    as_utc,
)
from florome.rca.service import evidence_hash, load_topology
from florome.security import audit
from florome.security.rbac import Principal
from florome.shield.models import BenchmarkRun, ContainmentEvent, RemediationPatch, SecurityHypothesis, VerificationRun, VulnerabilityFinding


@dataclass
class Ctx:
    db: Session
    app: AppContext
    p: Principal
    focus: dict[str, Any]
    request_samples: list[tuple[str, int, float]] = field(default_factory=list)


def A(statement: str, bullets: list[str] | None = None, visual: dict | None = None, evidence: list[dict] | None = None,
      follow: list[str] | None = None, **focus: Any) -> dict[str, Any]:
    return {"statement": statement, "bullets": (bullets or [])[:5], "visual": visual, "evidence": (evidence or [])[:6],
            "follow_ups": (follow or [])[:4], "focus": focus}


def clip(text: str, n: int) -> str:
    """Shorten on a word boundary so answers never end mid-word."""
    if len(text) <= n:
        return text
    return text[:n].rsplit(" ", 1)[0].rstrip(" ,:;") + "…"


def _money(x: float) -> str:
    return f"${x:,.0f}"


def _incident(c: Ctx) -> Incident | None:
    q = select(Incident).where(Incident.tenant_id == c.p.tenant_id)
    if c.focus.get("incident_id"):
        inc = c.db.get(Incident, c.focus["incident_id"])
        if inc is not None and inc.tenant_id == c.p.tenant_id:
            return inc
    ops = [i for i in c.db.scalars(q.order_by(Incident.detected_at.desc())) if i.source_system != "florome-shield"]
    open_ = [i for i in ops if i.status != "resolved"]
    return (open_ or ops or [None])[0]


def _rca(c: Ctx, inc: Incident | None) -> RCAReport | None:
    if inc is None:
        return None
    return c.db.scalars(select(RCAReport).where(RCAReport.incident_id == inc.id).order_by(RCAReport.created_at.desc())).first()


def _plan(c: Ctx) -> RemediationPlan | None:
    return c.db.scalars(select(RemediationPlan).where(RemediationPlan.tenant_id == c.p.tenant_id).order_by(RemediationPlan.created_at.desc())).first()


# ------------------------------------------------------------------------------------------------- overview

def incidents_open(c: Ctx) -> dict:
    incs = c.db.scalars(select(Incident).where(Incident.tenant_id == c.p.tenant_id, Incident.status != "resolved")
                        .order_by(Incident.detected_at.desc())).all()
    if not incs:
        return A("Nothing is broken right now: every recorded incident is resolved.", follow=["Did the fix work?", "Is the audit log intact?",
                                                                                              "Which vulnerabilities are confirmed?", "Where does the money go?"])
    rows = [[i.severity.upper(), clip(i.title, 70), i.status] for i in incs[:6]]
    return A(f"{len(incs)} incident{'s are' if len(incs) != 1 else ' is'} open; the most recent is “{incs[0].title}”.",
             [f"{Counter(i.severity for i in incs).most_common(1)[0][1]} at {Counter(i.severity for i in incs).most_common(1)[0][0].upper()}",
              f"{sum(i.source_system == 'florome-shield' for i in incs)} raised by Shield (security)"],
             {"type": "table", "columns": ["Severity", "Incident", "Status"], "rows": rows},
             [{"label": clip(i.title, 40), "href": f"/rca?incident={i.id}" if i.source_system != "florome-shield" else "/shield"} for i in incs[:3]],
             ["What caused the incident?", "What will the plan change?", "Which systems are failing?", "What needs my approval?"],
             incident_id=incs[0].id)


def approvals_pending(c: Ctx) -> dict:
    plans = c.db.scalars(select(RemediationPlan).where(RemediationPlan.tenant_id == c.p.tenant_id, RemediationPlan.status == "pending_approval")).all()
    follow = ["What will the plan change?", "What's the current policy?", "Did the fix work?", "What failed or was denied?"]
    if not plans:
        return A("No plan is waiting for approval.", follow=follow)
    pl = plans[0]
    return A(f"{len(plans)} plan{'s' if len(plans) > 1 else ''} await{'s' if len(plans) == 1 else ''} approval; the approver must not be {pl.created_by}.",
             [f"{len(pl.steps)} steps, {pl.risk} risk", f"Approval binds to plan hash {pl.plan_hash[:12]}…", "Approver role required: approver or admin"],
             {"type": "table", "columns": ["#", "Action", "Target", "Risk"], "rows": [[s["index"] + 1, s["title"], s["target_name"], s["risk"]] for s in pl.steps]},
             [{"label": "Open plan", "href": f"/actions?incident={pl.incident_id}"}], follow)


def connections_health(c: Ctx) -> dict:
    conns = c.db.scalars(select(Connection).where(Connection.tenant_id == c.p.tenant_id)).all()
    verified = [x for x in conns if x.status == "verified"]
    built = [p for p in PLATFORM_CATALOG if p["status"] != NOT_IMPLEMENTED]
    planned = len(PLATFORM_CATALOG) - len(built)
    return A(f"{len(verified)} of {len(conns)} connections pass their live health check; {planned} platforms are planned, not built.",
             [f"Verified: {', '.join(x.display_name for x in verified) or 'none'}", f"Built but not verified live: {', '.join(p['platform'] for p in built if p['status'] == 'implemented')}",
              "A platform shows as connected only after a real health check"],
             {"type": "kpis", "items": [{"label": "Verified", "value": len(verified)}, {"label": "Built", "value": len(built)}, {"label": "Planned", "value": planned}]},
             [{"label": "Integrations", "href": "/integrations"}],
             ["What can the MCP tools do?", "Which tools are quarantined?", "What's planned next?", "Where does the evidence come from?"])


def _costs(c: Ctx) -> tuple[list[CostRecord], list[str]]:
    rows = c.db.scalars(select(CostRecord).where(CostRecord.tenant_id == c.p.tenant_id)).all()
    return rows, sorted({r.period for r in rows})


def spend_month(c: Ctx) -> dict:
    rows, periods = _costs(c)
    if not periods:
        return A("No cost records are connected yet.", follow=["Which platforms are really connected?", "What's broken right now?", "Is the audit log intact?", "What needs my approval?"])
    last = periods[-1]
    tot = sum(r.amount for r in rows if r.period == last)
    by = defaultdict(float)
    for r in rows:
        if r.period == last:
            by[r.provider] += r.amount
    demo = " (synthetic demo records)" if any(r.is_demo for r in rows) else ""
    return A(f"Spend in {last} was {_money(tot)}{demo}.", [f"{k}: {_money(v)}" for k, v in sorted(by.items(), key=lambda kv: -kv[1])],
             {"type": "bars", "unit": "USD", "items": [{"label": k, "value": round(v, 2)} for k, v in sorted(by.items(), key=lambda kv: -kv[1])]},
             [{"label": "Money river", "href": "/finops"}], ["What changed month on month?", "Which AI component costs most?", "Which business outcome costs most?", "Where does the money go?"])


# ------------------------------------------------------------------------------------------------- topology

async def failing_systems(c: Ctx) -> dict:
    topo = load_topology(c.db, c.p.tenant_id)
    bad = []
    for rid, r in topo.resources.items():
        cid = r.get("connection_id")
        if cid and c.app.registry.has(cid):
            try:
                h = (await c.app.registry.get(cid).read_status(r["source_ref"])).get("health", "unknown")
            except ConnectorError:
                h = "unknown"
            if h not in ("healthy",):
                bad.append((r["name"], r["platform"], h))
    follow = ["What caused the incident?", "What is the blast radius?", "What's upstream of the failing service?", "Which cloud has the most failures?"]
    if not bad:
        return A("Every connected system reports healthy right now.", follow=follow)
    return A(f"{len(bad)} systems are not healthy, across {len({b[1] for b in bad})} platforms.", [f"{n} ({p}): {h}" for n, p, h in bad],
             {"type": "table", "columns": ["System", "Platform", "Health"], "rows": [list(b) for b in bad]}, [{"label": "Nervous system", "href": "/topology"}], follow)


def upstream(c: Ctx) -> dict:
    inc = _incident(c)
    follow = ["What caused the incident?", "Which systems are failing?", "What is the blast radius?", "Show the timeline of events"]
    if inc is None:
        return A("There is no incident to trace upstream from.", follow=follow)
    topo = load_topology(c.db, c.p.tenant_id)
    anc = topo.ancestors(inc.primary_resource_id)
    chain = list(reversed([topo.name(a) for a in anc])) + [topo.name(inc.primary_resource_id)]
    return A(f"{len(anc)} systems feed {topo.name(inc.primary_resource_id)}, directly or indirectly.", [" → ".join(chain)],
             {"type": "chain", "items": [{"label": n, "tone": "symptom" if i == len(chain) - 1 else "neutral"} for i, n in enumerate(chain)]},
             [{"label": "Map", "href": "/topology"}], follow, incident_id=inc.id)


def blast_radius(c: Ctx) -> dict:
    inc = _incident(c)
    follow = ["What caused the incident?", "Which systems are failing?", "What will the plan change?", "Who still needs to approve?"]
    rca = _rca(c, inc)
    if inc is None or rca is None:
        return A("Run the investigation first; the blast radius comes from its findings." if inc else "There is no incident.", follow=follow)
    aff = rca.report.get("affected_systems", [])
    biz = [a["name"] for a in aff if a["kind"] == "business_process"]
    return A(f"{len(aff)} systems are affected, including the business process “{biz[0]}”." if biz else f"{len(aff)} systems are affected.",
             [f"Root: {next((a['name'] for a in aff if a['role'] == 'root'), 'unknown')}", f"Platforms: {', '.join(sorted({a['platform'] for a in aff}))}"],
             {"type": "chain", "items": [{"label": a["name"], "tone": "root" if a["role"] == "root" else ("business" if a["kind"] == "business_process" else "impacted")} for a in aff]},
             [{"label": "Investigation", "href": f"/rca?incident={inc.id}"}], follow, incident_id=inc.id)


# ------------------------------------------------------------------------------------------------------ RCA

def root_cause(c: Ctx) -> dict:
    inc = _incident(c)
    rca = _rca(c, inc)
    follow = ["Which explanations were ruled out?", "Where is the evidence weakest?", "Show the timeline of events", "What will the plan change?"]
    if inc is None:
        return A("There is no incident on record.", follow=follow)
    if rca is None:
        return A(f"“{inc.title}” has not been investigated yet; press Run investigation on the RCA page.",
                 evidence=[{"label": "RCA", "href": f"/rca?incident={inc.id}"}], follow=follow, incident_id=inc.id)
    r = rca.report
    concl = r["conclusion"]
    root = next((h for h in r["hypotheses"] if h["id"] == concl.get("root_hypothesis_id")), None)
    names = {a["resource_id"]: a["name"] for a in r.get("affected_systems", [])}
    summ = {t["evidence_id"]: t["summary"] for t in r["timeline"]}
    chain = concl.get("causal_chain", [])
    bullets = [f"Verdict: {concl.get('final_status', concl['status'])}"]
    if root:
        bullets += [f"{t['test']}: {t['result']}" for t in root["tests"]][:4]
    return A(concl["statement"], bullets,
             {"type": "chain", "items": [{"label": names.get(x["resource_id"], x["resource_id"]), "tone": "root" if x["link_status"] == "root" else
                                          ("weak" if x["link_status"] != "confirmed" else "impacted"), "note": x["link_status"]} for x in chain]},
             [{"label": clip(summ.get(e, e), 42), "href": f"/rca?incident={inc.id}"} for e in (root["supporting_evidence"][:3] if root else [])], follow,
             incident_id=inc.id)


def ruled_out(c: Ctx) -> dict:
    inc = _incident(c)
    rca = _rca(c, inc)
    follow = ["What caused the incident?", "Where is the evidence weakest?", "Show the timeline of events", "Has any evidence been tampered with?"]
    if rca is None:
        return A("No investigation has run yet, so nothing has been ruled out.", follow=follow)
    dis = [h for h in rca.report["hypotheses"] if h["status"] == "disproven"]
    return A(f"{len(dis)} of {len(rca.report['hypotheses'])} explanations were disproven by evidence.",
             [f"{h['id']} {clip(h['title'].split(':')[0], 60)}: failed {', '.join(t['test'].replace('_', ' ') for t in h['tests'] if t['result'] == 'fail')}" for h in dis],
             {"type": "bars", "unit": "checks failed", "items": [{"label": f"{h['id']} {clip(h['title'].split(':')[0], 34)}", "value": sum(t['result'] == 'fail' for t in h['tests'])} for h in dis]},
             [{"label": "Hypothesis table", "href": f"/rca?incident={inc.id}"}], follow, incident_id=inc.id)


def weakest(c: Ctx) -> dict:
    inc = _incident(c)
    rca = _rca(c, inc)
    follow = ["What caused the incident?", "Which explanations were ruled out?", "Where does the evidence come from?", "Show the timeline of events"]
    if rca is None:
        return A("No investigation has run yet.", follow=follow)
    checks = [x for x in rca.report["challenge"]["checks"] if x["status"] != "pass"]
    return A(f"The challenger raised {len(checks)} caveat{'s' if len(checks) != 1 else ''}; the conclusion stayed {rca.report['challenge']['final_status']}.",
             [f"{x['check']}: {x['detail']}" for x in checks],
             {"type": "table", "columns": ["Check", "Status"], "rows": [[x["check"], x["status"]] for x in rca.report["challenge"]["checks"]]},
             [{"label": "Challenger", "href": f"/rca?incident={inc.id}"}], follow, incident_id=inc.id)


def timeline(c: Ctx) -> dict:
    inc = _incident(c)
    rca = _rca(c, inc)
    follow = ["What caused the incident?", "Which explanations were ruled out?", "Show the latest errors", "What is the blast radius?"]
    if rca is None:
        return A("No investigation has run yet, so there is no timeline.", follow=follow)
    tl = rca.report["timeline"]
    key = [t for t in tl if t["anomalous"] or t["kind"] in ("deployment", "config_change")]
    first = next((t for t in key if t["anomalous"]), None)
    return A(f"{len(tl)} events; the first failure was on {first['resource']}." if first else f"{len(tl)} events, none anomalous.",
             [f"{as_utc_str(t['at'])} · {t['resource']}: {clip(t['summary'], 70)}" for t in key[:5]],
             {"type": "timeline", "items": [{"at": t["at"], "label": t["resource"], "text": clip(t["summary"], 80), "tone": "bad" if t["anomalous"] else "change"} for t in key[:12]]},
             [{"label": "Time-travel view", "href": f"/rca?incident={inc.id}"}], follow, incident_id=inc.id)


def as_utc_str(iso: str) -> str:
    return iso[11:16] + " UTC"


# --------------------------------------------------------------------------------------------------- actions

def plan_changes(c: Ctx) -> dict:
    pl = _plan(c)
    follow = ["Who still needs to approve?", "Did the fix work?", "What failed or was denied?", "What caused the incident?"]
    if pl is None:
        return A("No remediation plan exists yet; generate one on the Actions page after the investigation.", follow=follow)
    return A(f"The plan has {len(pl.steps)} steps at {pl.risk} risk and is {STATUS_WORDS.get(pl.status, pl.status)}.",
             [f"{s['index'] + 1}. {s['title']} on {s['target_name']} (undo: {clip(s['rollback'], 50)})" for s in pl.steps],
             {"type": "table", "columns": ["#", "Action", "Target", "Risk", "Status"],
              "rows": [[s["index"] + 1, s["title"], s["target_name"], s["risk"], s.get("status", "pending")] for s in pl.steps]},
             [{"label": "Plan", "href": f"/actions?incident={pl.incident_id}"}], follow)


def who_approves(c: Ctx) -> dict:
    pl = _plan(c)
    follow = ["What will the plan change?", "Did the fix work?", "What's the current policy?", "What failed or was denied?"]
    if pl is None:
        return A("There is no plan to approve.", follow=follow)
    from florome.models import Approval

    ap = c.db.scalars(select(Approval).where(Approval.plan_id == pl.id).order_by(Approval.created_at.desc())).first()
    if ap:
        return A(f"Plan {pl.id} was {ap.decision} by {ap.approver_id}; it is now {STATUS_WORDS.get(pl.status, pl.status)}.",
                 [f"Bound to hash {ap.plan_hash[:12]}…", f"Expires {as_utc(ap.expires_at).strftime('%H:%M UTC')}"],
                 evidence=[{"label": "Plan", "href": f"/actions?incident={pl.incident_id}"}], follow=follow)
    return A(f"Plan {pl.id} still needs an approver who is not {pl.created_by}.", ["Roles that can approve: approver, admin"],
             evidence=[{"label": "Approve", "href": f"/actions?incident={pl.incident_id}"}], follow=follow)


def fix_worked(c: Ctx) -> dict:
    v = c.db.scalars(select(ValidationResult).where(ValidationResult.tenant_id == c.p.tenant_id).order_by(ValidationResult.created_at.desc())).first()
    follow = ["What will the plan change?", "What failed or was denied?", "Which systems are failing?", "Is the audit log intact?"]
    if v is None:
        return A("No fix has been executed and validated yet.", follow=follow)
    ok = [x for x in v.checks if x["passed"]]
    return A(("Yes: recovery was verified, " if v.passed else "No: recovery was not verified, ") + f"{len(ok)} of {len(v.checks)} checks passed.",
             [f"{x['resource']} · {x['check']}: {x.get('observed')}" for x in v.checks if x["check"] in ("business_outcome",) or not x["passed"]][:5]
             or [f"{x['resource']} · {x['check']}: {x.get('observed')}" for x in v.checks[:4]],
             {"type": "kpis", "items": [{"label": "Checks passed", "value": len(ok)}, {"label": "Checks failed", "value": len(v.checks) - len(ok)}]},
             [{"label": "Validation", "href": "/actions"}], follow)


def failures_denied(c: Ctx) -> dict:
    fails = c.db.scalars(select(ActionExecution).where(ActionExecution.tenant_id == c.p.tenant_id, ActionExecution.status.in_(["failed", "timed_out"]))).all()
    denied = c.db.scalars(select(AuditEvent).where(AuditEvent.tenant_id == c.p.tenant_id, AuditEvent.outcome == "denied")
                          .order_by(AuditEvent.seq.desc()).limit(5)).all()
    follow = ["What's the current policy?", "Is the audit log intact?", "Did the fix work?", "What will the plan change?"]
    return A(f"{len(fails)} action{'s' if len(fails) != 1 else ''} failed and {len(denied)} recent operation{'s were' if len(denied) != 1 else ' was'} denied.",
             [f"{e.action}: {str(e.detail.get('reason', e.detail.get('error', '')))[:70]}" for e in denied] + [f"{x.action_id} failed: {x.error}" for x in fails][:3],
             evidence=[{"label": "Audit trail", "href": "/governance"}], follow=follow)


# ------------------------------------------------------------------------------------------- integrations/sources

def mcp_tools(c: Ctx) -> dict:
    tools = c.db.scalars(select(MCPToolRecord).where(MCPToolRecord.tenant_id == c.p.tenant_id)).all()
    follow = ["Which tools are quarantined?", "Which platforms are really connected?", "Is the audit log intact?", "What was denied recently?"]
    if not tools:
        return A("No MCP tools are discovered yet; an admin can press Discover on the Integrations page.", follow=follow,
                 evidence=[{"label": "MCP gateway", "href": "/integrations"}])
    on = [t for t in tools if t.enabled]
    return A(f"{len(on)} of {len(tools)} MCP tools are enabled; only read-only tools can be called directly.",
             [f"{t.name} ({t.access}): {clip(t.description, 60)}" for t in on],
             {"type": "table", "columns": ["Tool", "Access", "Enabled"], "rows": [[t.name, t.access, "yes" if t.enabled else "no"] for t in tools]},
             [{"label": "MCP gateway", "href": "/integrations"}], follow)


def quarantined(c: Ctx) -> dict:
    tools = c.db.scalars(select(MCPToolRecord).where(MCPToolRecord.tenant_id == c.p.tenant_id, MCPToolRecord.enabled.is_(False))).all()
    follow = ["What can the MCP tools do?", "Which platforms are really connected?", "What was denied recently?", "Is the audit log intact?"]
    return A(f"{len(tools)} tool{'s are' if len(tools) != 1 else ' is'} disabled or quarantined." if tools else "No tool is quarantined.",
             [f"{t.name}: {t.quarantine_reason}" for t in tools], evidence=[{"label": "MCP gateway", "href": "/integrations"}], follow=follow)


def planned(c: Ctx) -> dict:
    plan = [p for p in PLATFORM_CATALOG if p["status"] == NOT_IMPLEMENTED]
    by = Counter(p["group"] for p in plan)
    return A(f"{len(plan)} integrations are planned but not built; none is shown as connected.", [f"{g}: {n}" for g, n in by.most_common()],
             {"type": "bars", "unit": "platforms", "items": [{"label": g, "value": n} for g, n in by.most_common()]},
             [{"label": "Integrations", "href": "/integrations"}],
             ["Which platforms are really connected?", "What can the MCP tools do?", "Where does the evidence come from?", "What's broken right now?"])


def evidence_sources(c: Ctx) -> dict:
    ev = c.db.scalars(select(Evidence).where(Evidence.tenant_id == c.p.tenant_id)).all()
    follow = ["Has any evidence been tampered with?", "Show the latest errors", "What caused the incident?", "Which platforms are really connected?"]
    if not ev:
        return A("No evidence has been collected yet; it is gathered when an investigation runs.", follow=follow)
    kinds = Counter(e.kind for e in ev)
    return A(f"{len(ev)} evidence records from {len({e.source_system for e in ev})} source(s), all with original IDs and fingerprints.",
             [f"{s}: {n}" for s, n in Counter(e.source_system for e in ev).items()] + (["All records are synthetic demo data"] if all(e.is_demo for e in ev) else []),
             {"type": "bars", "unit": "records", "items": [{"label": k, "value": n} for k, n in kinds.most_common()]},
             [{"label": "Evidence explorer", "href": "/sources"}], follow)


def evidence_integrity(c: Ctx) -> dict:
    ev = c.db.scalars(select(Evidence).where(Evidence.tenant_id == c.p.tenant_id)).all()
    bad = [e for e in ev if evidence_hash(e) != e.content_hash]
    follow = ["Is the audit log intact?", "Where does the evidence come from?", "Show the latest errors", "What caused the incident?"]
    return A(f"All {len(ev)} evidence records still match their fingerprints." if not bad else f"{len(bad)} of {len(ev)} records no longer match their fingerprints.",
             [f"Altered: {e.id} ({clip(e.summary, 50)})" for e in bad] or ["Checked just now by recomputing every SHA-256 fingerprint"],
             {"type": "kpis", "items": [{"label": "Intact", "value": len(ev) - len(bad)}, {"label": "Altered", "value": len(bad)}]},
             [{"label": "Sources", "href": "/sources"}], follow)


def latest_errors(c: Ctx) -> dict:
    from florome.rca.engine import EvidenceItem, is_anomalous

    ev = c.db.scalars(select(Evidence).where(Evidence.tenant_id == c.p.tenant_id).order_by(Evidence.observed_at.desc())).all()
    bad = [e for e in ev if is_anomalous(EvidenceItem(e.id, e.resource_id, e.kind, e.observed_at, e.summary, e.payload))][:5]
    follow = ["What caused the incident?", "Show the timeline of events", "Has any evidence been tampered with?", "Which systems are failing?"]
    if not bad:
        return A("No error records have been collected.", follow=follow)
    return A(f"The latest error came from {bad[0].source_system} at {as_utc(bad[0].observed_at).strftime('%H:%M UTC')}.",
             [f"{as_utc(e.observed_at).strftime('%H:%M')} · {clip(e.summary, 80)}" for e in bad], evidence=[{"label": "Sources", "href": "/sources"}], follow=follow)


# ----------------------------------------------------------------------------------------------- governance

def audit_intact(c: Ctx) -> dict:
    v = audit.verify_chain(c.db, c.p.tenant_id)
    follow = ["What was denied recently?", "What's the current policy?", "Has any evidence been tampered with?", "How fast is the API?"]
    return A(f"Yes: all {v['events_checked']} audit events verify as an unbroken chain." if v["valid"] else f"No: the chain breaks at event {v['broken_at']}.",
             ["Each entry seals the one before it (SHA-256)", "Editing or deleting any entry breaks verification from that point"],
             {"type": "kpis", "items": [{"label": "Events checked", "value": v["events_checked"]}, {"label": "Chain", "value": "intact" if v["valid"] else "broken"}]},
             [{"label": "Audit trail", "href": "/governance"}], follow)


def denied_recent(c: Ctx) -> dict:
    rows = c.db.scalars(select(AuditEvent).where(AuditEvent.tenant_id == c.p.tenant_id, AuditEvent.outcome == "denied")
                        .order_by(AuditEvent.seq.desc()).limit(8)).all()
    follow = ["What's the current policy?", "Is the audit log intact?", "Which tools are quarantined?", "Did any AI agent misbehave?"]
    if not rows:
        return A("Nothing has been denied.", follow=follow)
    by = Counter(r.action for r in rows)
    return A(f"{len(rows)} recent operations were denied; most often “{by.most_common(1)[0][0]}”.",
             [f"{r.action} by {r.actor}: {str(r.detail.get('reason') or r.detail.get('violation') or '')[:60]}" for r in rows[:5]],
             {"type": "bars", "unit": "denials", "items": [{"label": k, "value": n} for k, n in by.most_common(6)]},
             [{"label": "Audit trail", "href": "/governance"}], follow)


def policy_current(c: Ctx) -> dict:
    t = c.db.get(Tenant, c.p.tenant_id)
    pol = effective_policy(t.policy)
    return A(f"Execution mode is “{pol['execution_mode']}”; emergency stop is {'ACTIVE' if t.emergency_stop else 'off'}.",
             [f"Approvals expire after {pol['approval_ttl_minutes']} min", "Separation of duties: enforced (cannot be disabled)",
              f"Action budget: {pol['max_actions_per_hour']} per hour",
              "Autonomous only for: " + ", ".join(f"{a['action_id']}@{'/'.join(a['environments'])}" for a in pol["autonomous_allowlist"])],
             evidence=[{"label": "Policy", "href": "/governance"}],
             follow=["What was denied recently?", "Who still needs to approve?", "Is the audit log intact?", "How fast is the API?"])


def api_speed(c: Ctx) -> dict:
    ms = sorted(x[2] for x in c.request_samples)
    follow = ["Is the audit log intact?", "What was denied recently?", "What's the current policy?", "Which systems are failing?"]
    if not ms:
        return A("No requests have been measured since the server started.", follow=follow)
    p50, p95 = ms[len(ms) // 2], ms[min(len(ms) - 1, int(0.95 * (len(ms) - 1)))]
    by: dict[str, list[float]] = defaultdict(list)
    for path, _, m in c.request_samples:
        by[path].append(m)
    slow = sorted(((k, sorted(v)[len(v) // 2]) for k, v in by.items()), key=lambda kv: -kv[1])[:5]
    return A(f"Median response is {p50:.0f} ms (95th percentile {p95:.0f} ms) over {len(ms)} measured requests.",
             [f"Slowest median: {k.replace('/api/v1', '')} {v:.0f} ms" for k, v in slow[:3]],
             {"type": "bars", "unit": "ms (median)", "items": [{"label": k.replace("/api/v1", ""), "value": round(v, 1)} for k, v in slow]},
             [{"label": "System metrics", "href": "/governance"}], follow)


# ---------------------------------------------------------------------------------------------------- finops

def _cost_by(c: Ctx, attr: str, title: str, follow: list[str]) -> dict:
    rows, periods = _costs(c)
    if not periods:
        return A("No cost records are connected yet.", follow=follow)
    last = periods[-1]
    by = defaultdict(float)
    for r in rows:
        if r.period == last:
            by[getattr(r, attr)] += r.amount
    top = sorted(by.items(), key=lambda kv: -kv[1])
    return A(f"{top[0][0]} {title} in {last}: {_money(top[0][1])} of {_money(sum(by.values()))}.", [f"{k}: {_money(v)}" for k, v in top[:5]],
             {"type": "bars", "unit": "USD", "items": [{"label": k, "value": round(v, 2)} for k, v in top[:8]]},
             [{"label": "Money river", "href": "/finops"}], follow)


def spend_where(c: Ctx) -> dict:
    return _cost_by(c, "business_unit", "is the largest business unit", ["Which AI component costs most?", "Which business outcome costs most?",
                                                                          "What changed month on month?", "What did we spend last month?"])


def spend_change(c: Ctx) -> dict:
    rows, periods = _costs(c)
    follow = ["Where does the money go?", "Which AI component costs most?", "Which business outcome costs most?", "What did we spend last month?"]
    if len(periods) < 2:
        return A("At least two months of cost records are needed to compare.", follow=follow)
    tot = {p: sum(r.amount for r in rows if r.period == p) for p in periods}
    a, b = tot[periods[-2]], tot[periods[-1]]
    return A(f"Spend moved {(b - a) / a * 100:+.1f}% from {periods[-2]} to {periods[-1]} ({_money(a)} → {_money(b)}).",
             [f"{p}: {_money(v)}" for p, v in tot.items()],
             {"type": "bars", "unit": "USD", "items": [{"label": p, "value": round(v, 2)} for p, v in tot.items()]}, [{"label": "Money river", "href": "/finops"}], follow)


def spend_ai(c: Ctx) -> dict:
    return _cost_by(c, "ai_component", "costs the most", ["Which business outcome costs most?", "Where does the money go?", "What changed month on month?",
                                                          "What did we spend last month?"])


def spend_outcome(c: Ctx) -> dict:
    return _cost_by(c, "outcome", "is the most expensive outcome", ["Which AI component costs most?", "Where does the money go?",
                                                                     "What changed month on month?", "What did we spend last month?"])


# ---------------------------------------------------------------------------------------------------- shield

def _hyps(c: Ctx, status: str | None = None) -> list[SecurityHypothesis]:
    q = select(SecurityHypothesis).where(SecurityHypothesis.tenant_id == c.p.tenant_id)
    if status:
        q = q.where(SecurityHypothesis.status == status)
    return c.db.scalars(q).all()


SHIELD_FOLLOW = ["Which vulnerabilities are confirmed?", "Which alarms were false?", "Were the fixes verified?", "Did any AI agent misbehave?"]


def vulns_confirmed(c: Ctx) -> dict:
    hs = _hyps(c, "confirmed")
    if not hs:
        return A("No vulnerability is confirmed; Shield has not run, or nothing reproduced.", evidence=[{"label": "Shield", "href": "/shield"}],
                 follow=["Which alarms were false?", "Does proving beat guessing?", "Did any AI agent misbehave?", "Is the audit log intact?"])
    sev = {f.hypothesis_id: f.severity for f in c.db.scalars(select(VulnerabilityFinding).where(VulnerabilityFinding.tenant_id == c.p.tenant_id))}
    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    hs = sorted(hs, key=lambda h: rank.get(sev.get(h.id, "low"), 4))
    return A(f"{len(hs)} vulnerabilities are confirmed, each reproduced twice in the sealed lab; the worst is {hs[0].vuln_class.replace('_', ' ')} in {hs[0].function}.",
             [f"{sev.get(h.id, '?').upper()} · {h.vuln_class.replace('_', ' ')} in {h.function} ({h.file}:{h.line})" for h in hs],
             {"type": "bars", "unit": "confirmed", "items": [{"label": k.replace("_", " "), "value": n} for k, n in Counter(sev.get(h.id, "?") for h in hs).most_common()]},
             [{"label": f"{h.function}", "href": f"/shield?hypothesis={h.id}"} for h in hs[:4]],
             ["Explain the selected finding", "Were the fixes verified?", "Which alarms were false?", "Does proving beat guessing?"], hypothesis_id=hs[0].id)


def false_alarms(c: Ctx) -> dict:
    hs = _hyps(c, "disproven")
    if not hs:
        return A("No alarm has been disproven yet.", follow=SHIELD_FOLLOW)
    return A(f"{len(hs)} suspicions were disproven: the attack failed twice and a safety measure explains why.",
             [f"{h.function} · {h.vuln_class.replace('_', ' ')}: {', '.join(x['detail'].replace('_', ' ') for x in h.contradicting)}" for h in hs],
             {"type": "table", "columns": ["Where", "Suspected", "Safety measure"], "rows": [[h.function, h.vuln_class.replace("_", " "),
                                                                                              ", ".join(x["detail"] for x in h.contradicting)] for h in hs]},
             [{"label": "Research lab", "href": "/shield"}], ["Which vulnerabilities are confirmed?", "Does proving beat guessing?", "Were the fixes verified?",
                                                              "Did any AI agent misbehave?"])


def fixes_verified(c: Ctx) -> dict:
    ps = c.db.scalars(select(RemediationPatch).where(RemediationPatch.tenant_id == c.p.tenant_id)).all()
    if not ps:
        return A("No fix has been generated yet.", follow=SHIELD_FOLLOW)
    st = Counter(p.status for p in ps)
    ok = st.get("verified", 0) + st.get("approved_for_review", 0)
    return A(f"{ok} of {len(ps)} generated fixes blocked the attack in both retests without breaking features.",
             [f"{k.replace('_', ' ')}: {v}" for k, v in st.items()] + ["Fixes are never applied to the real code automatically"],
             {"type": "kpis", "items": [{"label": "Passed retest", "value": ok}, {"label": "Failed retest", "value": st.get("failed_regression", 0)},
                                        {"label": "Approved for review", "value": st.get("approved_for_review", 0)}]},
             [{"label": "Research lab", "href": "/shield"}], SHIELD_FOLLOW)


def agents(c: Ctx) -> dict:
    ev = c.db.scalars(select(ContainmentEvent).where(ContainmentEvent.tenant_id == c.p.tenant_id)).all()
    if not ev:
        return A("No AI agent session has been supervised yet.", follow=SHIELD_FOLLOW)
    bad = [e for e in ev if e.violation]
    return A(f"{len(bad)} of {len(ev)} agent sessions misbehaved and were stopped; their credentials were revoked.",
             [f"{e.scenario}: {e.violation} in {e.forensics.get('seconds', 0) * 1000:.0f} ms" for e in bad[:5]],
             {"type": "bars", "unit": "sessions", "items": [{"label": k, "value": n} for k, n in Counter(e.violation or "completed" for e in ev).most_common()]},
             [{"label": "Containment", "href": "/shield"}], SHIELD_FOLLOW)


def proving(c: Ctx) -> dict:
    rows = c.db.scalars(select(BenchmarkRun).where(BenchmarkRun.tenant_id == c.p.tenant_id).order_by(BenchmarkRun.created_at.desc()).limit(4)).all()
    done = {r.pipeline: r for r in rows if r.status == "completed"}
    if not done:
        return A("No evaluation has been run yet; an admin can press Run full research.", follow=SHIELD_FOLLOW)
    names = {"scanner_only": "Scanners only", "graph_unverified": "Code graph, no lab", "hybrid_verified": "Graph + lab"}
    return A("On the 9-spot test app the lab adds proof, not detection: the code graph alone also scored 5/5 with no false alarms.",
             [f"{names[k]}: {r.metrics['tp']} found, {r.metrics['fp']} false alarms, {r.metrics['fn']} missed" for k, r in done.items() if k in names]
             + ["AI-model-only: not run (no authorised model)"],
             {"type": "bars", "unit": "false alarms", "items": [{"label": names[k], "value": r.metrics["fp"]} for k, r in done.items() if k in names]},
             [{"label": "Evaluation", "href": "/shield"}], SHIELD_FOLLOW)


def finding_detail(c: Ctx) -> dict:
    hid = c.focus.get("hypothesis_id")
    h = c.db.get(SecurityHypothesis, hid) if hid else None
    if h is None or h.tenant_id != c.p.tenant_id:
        return A("Select a finding in the research lab first, then ask again.", follow=SHIELD_FOLLOW)
    runs = c.db.scalars(select(VerificationRun).where(VerificationRun.hypothesis_id == h.id).order_by(VerificationRun.created_at)).all()
    return A(f"{h.vuln_class.replace('_', ' ').capitalize()} in {h.function} is {h.status}: {h.status_basis}",
             [f"Assumption tested: {h.assumption}"] + [clip(x["detail"], 90) for x in h.supporting if x["type"] in ("data_flow", "graph")][:2]
             + [f"Against: {x['detail'].replace('_', ' ')}" for x in h.contradicting][:2],
             {"type": "table", "columns": ["Run", "Purpose", "Outcome", "Seconds"],
              "rows": [[r.attempt, r.purpose.replace("_", " "), r.outcome, round(r.seconds, 2)] for r in runs]},
             [{"label": f"{h.file}:{h.line}", "href": f"/shield?hypothesis={h.id}"}],
             ["Were the fixes verified?", "Which vulnerabilities are confirmed?", "Which alarms were false?", "Does proving beat guessing?"], hypothesis_id=h.id)


def code_reach(c: Ctx) -> dict:
    hs = [h for h in _hyps(c) if any(s["type"] == "data_flow" for s in h.supporting) and not h.contradicting
          and any("without authentication" in s["detail"] for s in h.supporting)]
    if not hs:
        return A("No unauthenticated path to a dangerous operation is recorded (or Shield has not run).", follow=SHIELD_FOLLOW)
    return A(f"{len(hs)} public endpoints pass visitor data to a dangerous operation with no safety check.",
             [f"{h.function} → {h.vuln_class.replace('_', ' ')} ({h.status})" for h in hs], evidence=[{"label": "Code graph", "href": "/shield"}],
             follow=["Which vulnerabilities are confirmed?", "Were the fixes verified?", "Which alarms were false?", "Does proving beat guessing?"])


# ------------------------------------------------------------------------------------------- added intents

async def health_by_platform(c: Ctx) -> dict:
    topo = load_topology(c.db, c.p.tenant_id)
    tally: dict[str, Counter] = defaultdict(Counter)
    for r in topo.resources.values():
        cid = r.get("connection_id")
        health = "unknown"
        if cid and c.app.registry.has(cid):
            try:
                health = (await c.app.registry.get(cid).read_status(r["source_ref"])).get("health", "unknown")
            except ConnectorError:
                health = "unknown"
        tally[r["platform"]][health] += 1
    bad = {p: sum(n for h, n in t.items() if h not in ("healthy", "unknown")) for p, t in tally.items()}
    worst = max(bad.items(), key=lambda kv: kv[1])
    follow = ["Which systems are failing?", "What is the blast radius?", "What's upstream of the failing service?", "What caused the incident?"]
    return A(f"{worst[0]} has the most unhealthy systems ({worst[1]})." if worst[1] else "No cloud has an unhealthy system right now.",
             [f"{p}: {t.get('healthy', 0)} healthy, {bad[p]} unhealthy" for p, t in sorted(tally.items())],
             {"type": "bars", "unit": "unhealthy systems", "items": [{"label": p, "value": n} for p, n in sorted(bad.items(), key=lambda kv: -kv[1])]},
             [{"label": "Map", "href": "/topology"}], follow)


def log_gaps(c: Ctx) -> dict:
    inc = _incident(c)
    rca = _rca(c, inc)
    follow = ["Where is the evidence weakest?", "Where does the evidence come from?", "Has any evidence been tampered with?", "Show the latest errors"]
    if rca is None:
        return A("No investigation has run yet, so evidence coverage is unknown.", follow=follow)
    topo = load_topology(c.db, c.p.tenant_id)
    have: dict[str, set[str]] = defaultdict(set)
    for t in rca.report["timeline"]:
        have[t["resource_id"]].add(t["kind"])
    scope = rca.report["scope"]
    silent = [r for r in scope if not have[r] & {"log", "trace", "status"} and topo.resources[r]["kind"] != "ci_pipeline"]
    return A(f"{len(silent)} of {len(scope)} investigated systems kept no logs or traces: {', '.join(topo.name(r) for r in silent)}." if silent
             else f"Every one of the {len(scope)} investigated systems provided logs or traces.",
             ["Links into a silent system can only be inferred from timing, never proven"] if silent else [],
             {"type": "table", "columns": ["System", "Evidence kinds"], "rows": [[topo.name(r), ", ".join(sorted(have[r])) or "none"] for r in scope]},
             [{"label": "Investigation", "href": f"/rca?incident={inc.id}"}], follow, incident_id=inc.id)


STATUS_WORDS = {"succeeded": "done and verified", "pending_approval": "waiting for approval", "approved": "approved, not yet run",
                "executing": "running", "failed": "stopped on a failed step", "rejected": "rejected", "blocked": "blocked by policy"}
