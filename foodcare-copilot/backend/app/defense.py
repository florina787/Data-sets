"""Enterprise Defense Command: threats, downtime, guarded containment, alerts and license savings.

Evidence and honesty
* No SIEM, EDR, vulnerability scanner, identity, CSPM, network or billing system is connected.
  The security and licence records below are **simulated telemetry** for a fictional company and
  are labelled ``synthetic`` everywhere. The demo storefront's health check, its incidents and
  deployments are real **operational records** of this app and are labelled as such.
* Every security event is classified as ``alert`` (a detection), ``suspected_incident``
  (corroborated, under investigation) or ``confirmed_incident`` (analyst-confirmed). Nothing is
  called a compromise without a confirmed record.
* Downtime correlation reports *co-occurrence in time*, never causation.

Containment (the controlled kill switch)
* Read-only recommendations and dry-run previews by default. No universal kill switch.
* Explicit asset + action scope from an allowlist; protected environments (operational
  technology, refrigeration, production lines, life safety) can never be contained here — only
  escalated to the site's OT/safety team.
* Proposal → step-up authentication (password re-entry) → approval by others (two distinct
  approvers for high-impact actions, never the proposer) → time-limited (15 min) → execute with
  an idempotency key. In demo mode, and whenever no containment connector is configured,
  execution is **always a dry run**: nothing is changed anywhere.
* Every step is written to a hash-chained, tamper-evident log (:func:`verify_chain`).

Licence savings use deterministic arithmetic under contract constraints and are reported as
estimated avoided expenditure — never revenue, and never "realized" before it happens.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import date, datetime, timedelta, timezone

from app.db import new_id, now_iso, rows, session
from app.errors import Forbidden, NotFound, PlatformError

TODAY = date(2026, 10, 31)  # the demo clock's date
SIM = "synthetic"
SIM_NOTE = "Simulated security telemetry — no SIEM, EDR or scanner is connected."

ASSETS = [
    {
        "id": "WS-QA-014",
        "name": "QA laptop 14",
        "kind": "endpoint",
        "env": "corporate",
        "criticality": "medium",
        "protected": False,
        "services": ["quality_inspection"],
        "owner": "IT service desk",
    },
    {
        "id": "SRV-ERP-01",
        "name": "ERP application server",
        "kind": "server",
        "env": "datacentre",
        "criticality": "high",
        "protected": False,
        "services": ["erp_ordering", "reporting"],
        "owner": "ERP platform team",
    },
    {
        "id": "SRV-FILE-02",
        "name": "File server 02",
        "kind": "server",
        "env": "datacentre",
        "criticality": "medium",
        "protected": False,
        "services": ["reporting"],
        "owner": "Infrastructure team",
    },
    {
        "id": "svc-reporting",
        "name": "Reporting service account",
        "kind": "service_account",
        "env": "identity",
        "criticality": "medium",
        "protected": False,
        "services": ["reporting"],
        "owner": "Data platform team",
    },
    {
        "id": "k8s/foodcare/storefront",
        "name": "Storefront workload",
        "kind": "workload",
        "env": "kubernetes",
        "criticality": "high",
        "protected": False,
        "services": ["storefront_checkout"],
        "owner": "E-commerce team",
    },
    {
        "id": "k8s/analytics/batch-reports",
        "name": "Batch reports workload",
        "kind": "workload",
        "env": "kubernetes",
        "criticality": "low",
        "protected": False,
        "services": ["reporting"],
        "owner": "Data platform team",
    },
    {
        "id": "OT-REFRIG-03",
        "name": "Cold store 3 refrigeration controller",
        "kind": "ot_controller",
        "env": "plant OT",
        "criticality": "critical",
        "protected": True,
        "services": ["cold_chain"],
        "owner": "Plant OT & safety team",
    },
    {
        "id": "OT-LINE2-PLC",
        "name": "Fry line 2 PLC",
        "kind": "ot_controller",
        "env": "plant OT",
        "criticality": "critical",
        "protected": True,
        "services": ["production_line_2"],
        "owner": "Plant OT & safety team",
    },
]
SERVICES = {
    "storefront_checkout": {
        "name": "Online storefront checkout",
        "rto_min": 60,
        "revenue_per_hour_cents": 18_000_00,
        "depends": ["k8s/foodcare/storefront", "inventory_api"],
    },
    "erp_ordering": {"name": "ERP ordering", "rto_min": 240, "revenue_per_hour_cents": None, "depends": ["SRV-ERP-01"]},
    "reporting": {
        "name": "Management reporting",
        "rto_min": 1440,
        "revenue_per_hour_cents": None,
        "depends": ["SRV-FILE-02", "svc-reporting", "k8s/analytics/batch-reports"],
    },
    "quality_inspection": {
        "name": "Quality inspection app",
        "rto_min": 480,
        "revenue_per_hour_cents": None,
        "depends": ["WS-QA-014"],
    },
    "cold_chain": {
        "name": "Cold-chain monitoring",
        "rto_min": 15,
        "revenue_per_hour_cents": None,
        "depends": ["OT-REFRIG-03"],
    },
    "production_line_2": {
        "name": "Fry line 2",
        "rto_min": 30,
        "revenue_per_hour_cents": None,
        "depends": ["OT-LINE2-PLC"],
    },
}
# Detections (several share a dedup key so the alert engine can group them).
EVENTS = [
    {
        "id": "SEC-1001",
        "source": "EDR",
        "type": "malware",
        "severity": "high",
        "classification": "suspected_incident",
        "asset": "WS-QA-014",
        "dedup": "malware:WS-QA-014",
        "seen": "2026-10-31T08:12:00+00:00",
        "evidence": "EDR quarantined a trojan-like file; process tree shows an attempted connection to a "
        "known-bad domain.",
        "indicator": "bad-domain.example",
        "status": "investigating",
    },
    {
        "id": "SEC-1002",
        "source": "EDR",
        "type": "malware",
        "severity": "high",
        "classification": "suspected_incident",
        "asset": "WS-QA-014",
        "dedup": "malware:WS-QA-014",
        "seen": "2026-10-31T08:19:00+00:00",
        "evidence": "Second detection of the same file hash after reboot.",
        "indicator": "bad-domain.example",
        "status": "investigating",
    },
    {
        "id": "SEC-1003",
        "source": "Identity",
        "type": "suspicious_auth",
        "severity": "high",
        "classification": "alert",
        "asset": "svc-reporting",
        "dedup": "auth:svc-reporting",
        "seen": "2026-10-31T02:40:00+00:00",
        "evidence": "Service account signed in interactively from a new country; MFA not applicable to "
        "service accounts.",
        "indicator": None,
        "status": "new",
    },
    {
        "id": "SEC-1004",
        "source": "Vulnerability scanner",
        "type": "vulnerability",
        "severity": "critical",
        "classification": "alert",
        "asset": "SRV-ERP-01",
        "dedup": "vuln:SYN-VULN-001:SRV-ERP-01",
        "seen": "2026-10-30T22:00:00+00:00",
        "evidence": "Internet-reachable admin interface with a critical remote-code-"
        "execution weakness (SYN-VULN-001, CVSS 9.8, simulated identifier).",
        "indicator": None,
        "status": "new",
    },
    {
        "id": "SEC-1005",
        "source": "Cloud posture",
        "type": "misconfiguration",
        "severity": "medium",
        "classification": "alert",
        "asset": "SRV-FILE-02",
        "dedup": "cspm:public-share:SRV-FILE-02",
        "seen": "2026-10-29T15:00:00+00:00",
        "evidence": "File share readable by all authenticated users.",
        "indicator": None,
        "status": "new",
    },
    {
        "id": "SEC-1006",
        "source": "Network monitoring",
        "type": "network_anomaly",
        "severity": "low",
        "classification": "alert",
        "asset": "SRV-FILE-02",
        "dedup": "net:egress:SRV-FILE-02",
        "seen": "2026-10-31T03:05:00+00:00",
        "evidence": "Egress volume 3× the 30-day baseline for 40 minutes.",
        "indicator": None,
        "status": "new",
    },
    {
        "id": "SEC-0990",
        "source": "SIEM",
        "type": "malware",
        "severity": "medium",
        "classification": "confirmed_incident",
        "asset": "SRV-FILE-02",
        "dedup": "malware:SRV-FILE-02",
        "seen": "2026-10-20T11:00:00+00:00",
        "evidence": "Analyst-confirmed adware on a file server; removed and verified clean.",
        "indicator": None,
        "status": "resolved",
    },
]
VULNS = [
    {"id": "SYN-VULN-001", "asset": "SRV-ERP-01", "cvss": 9.8, "exploit_known": True, "internet_facing": True},
    {
        "id": "SYN-VULN-014",
        "asset": "k8s/foodcare/storefront",
        "cvss": 7.5,
        "exploit_known": False,
        "internet_facing": True,
    },
    {"id": "SYN-VULN-022", "asset": "WS-QA-014", "cvss": 6.1, "exploit_known": True, "internet_facing": False},
    {"id": "SYN-VULN-031", "asset": "SRV-FILE-02", "cvss": 5.3, "exploit_known": False, "internet_facing": False},
    {"id": "SYN-VULN-040", "asset": "OT-REFRIG-03", "cvss": 8.1, "exploit_known": False, "internet_facing": False},
]
DOWNTIME = [
    {
        "service": "reporting",
        "start": "2026-10-30T23:10:00+00:00",
        "end": "2026-10-31T01:25:00+00:00",
        "cause_recorded": None,
        "note": "Batch reports workload crash-looped (pod restarts).",
    },
    {
        "service": "erp_ordering",
        "start": "2026-10-31T06:00:00+00:00",
        "end": "2026-10-31T06:35:00+00:00",
        "cause_recorded": "Planned patching overran",
        "note": "Change ticket recorded the overrun.",
    },
]
CERTS = [
    {"name": "storefront TLS certificate", "expires": "2026-11-12", "critical": True},
    {"name": "ERP API client certificate", "expires": "2027-03-01", "critical": True},
]
BACKUPS = [
    {"name": "ERP nightly backup", "last_status": "failed", "last_run": "2026-10-31T01:00:00+00:00", "critical": True},
    {"name": "File server backup", "last_status": "ok", "last_run": "2026-10-31T02:00:00+00:00", "critical": False},
]
LICENSES = [
    {
        "id": "LIC-GHCP",
        "vendor": "GitHub",
        "product": "GitHub Copilot Business",
        "paid": 120,
        "assigned": 104,
        "active_30d": 71,
        "light_users": 0,
        "requested": 9,
        "unit_price_cents_month": 1900,
        "billing": "monthly",
        "min_seats": 0,
        "reassignable": True,
        "cancellation": "monthly, any time",
        "renewal": "2026-12-01",
        "notice_days": 0,
        "downgrade": None,
        "owner": "CTO office",
        "category": "AI developer tools",
    },
    {
        "id": "LIC-DBX",
        "vendor": "Databricks",
        "product": "Databricks (committed DBUs)",
        "paid": 1000,
        "assigned": 1000,
        "active_30d": 640,
        "light_users": 0,
        "requested": 0,
        "unit_price_cents_month": 5500,
        "billing": "annual commit",
        "min_seats": 800,
        "reassignable": False,
        "cancellation": "commitment reduces only at renewal",
        "renewal": "2027-03-31",
        "notice_days": 60,
        "downgrade": None,
        "owner": "Data platform team",
        "category": "Analytics platform",
        "unit": "DBU blocks",
    },
    {
        "id": "LIC-BI",
        "vendor": "BI vendor",
        "product": "BI Pro (dashboards)",
        "paid": 300,
        "assigned": 280,
        "active_30d": 150,
        "light_users": 90,
        "requested": 0,
        "unit_price_cents_month": 7000,
        "billing": "annual",
        "min_seats": 200,
        "reassignable": True,
        "cancellation": "at renewal only",
        "renewal": "2026-12-15",
        "notice_days": 30,
        "downgrade": {"tier": "BI Viewer", "unit_price_cents_month": 1000},
        "owner": "Finance",
        "category": "Analytics",
    },
    {
        "id": "LIC-COLLAB",
        "vendor": "Collaboration vendor",
        "product": "Video meetings Pro",
        "paid": 900,
        "assigned": 880,
        "active_30d": 610,
        "light_users": 0,
        "requested": 0,
        "unit_price_cents_month": 1500,
        "billing": "annual",
        "min_seats": 850,
        "reassignable": True,
        "cancellation": "at renewal only",
        "renewal": "2026-11-10",
        "notice_days": 30,
        "downgrade": None,
        "owner": "IT service desk",
        "category": "Collaboration",
    },
]
CONTAINMENT_ACTIONS = {
    "isolate_endpoint": {
        "label": "Isolate endpoint from the network",
        "kinds": {"endpoint"},
        "impact": "high",
        "rollback": "Release isolation in the EDR console; the device reconnects on next check-in.",
    },
    "revoke_credential": {
        "label": "Revoke credential sessions and tokens",
        "kinds": {"service_account"},
        "impact": "high",
        "rollback": "Issue a new credential through the identity team's process.",
    },
    "disable_service_account": {
        "label": "Disable service account",
        "kinds": {"service_account"},
        "impact": "high",
        "rollback": "Re-enable the account in the identity provider after review.",
    },
    "block_indicator": {
        "label": "Block network indicator at the egress proxy",
        "kinds": {"endpoint", "server"},
        "impact": "low",
        "rollback": "Remove the indicator from the block list.",
    },
    "pause_workload": {
        "label": "Scale a noncritical workload to zero",
        "kinds": {"workload"},
        "impact": "high",
        "rollback": "Scale the deployment back to its previous replica count.",
    },
    "trigger_ir_workflow": {
        "label": "Open the incident-response workflow",
        "kinds": None,
        "impact": "low",
        "rollback": "Close the workflow ticket.",
    },
}
APPROVAL_MINUTES = 15
CONTAINMENT_LIVE = False  # no containment connector exists in this app; execution is always a dry run

DDL = """
CREATE TABLE IF NOT EXISTS defense_proposals (
    id TEXT PRIMARY KEY, action TEXT NOT NULL, asset_id TEXT NOT NULL, indicator TEXT, proposed_by TEXT NOT NULL,
    created_at TEXT NOT NULL, status TEXT NOT NULL, impact TEXT NOT NULL, approvals_json TEXT NOT NULL DEFAULT '[]',
    required_approvals INTEGER NOT NULL, approved_until TEXT, result_json TEXT, idempotency_key TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS defense_chain (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, actor TEXT NOT NULL, event TEXT NOT NULL,
    detail_json TEXT NOT NULL, prev_hash TEXT NOT NULL, hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS defense_alert_state (
    alert_id TEXT PRIMARY KEY, state TEXT NOT NULL, by_user TEXT NOT NULL, at TEXT NOT NULL, note TEXT
);
"""


def ensure() -> None:
    with session() as conn:
        conn.executescript(DDL)


# --- tamper-evident log ---------------------------------------------------------------------


def _chain(actor: str, event: str, detail: dict) -> None:
    ensure()
    with session() as conn:
        last = conn.execute("SELECT hash FROM defense_chain ORDER BY seq DESC LIMIT 1").fetchone()
        prev = last[0] if last else "0" * 64
        ts = now_iso()
        body = json.dumps({"ts": ts, "actor": actor, "event": event, "detail": detail, "prev": prev}, sort_keys=True)
        h = hashlib.sha256(body.encode()).hexdigest()
        conn.execute(
            "INSERT INTO defense_chain (ts, actor, event, detail_json, prev_hash, hash) VALUES (?, ?, ?, ?, ?, ?)",
            (ts, actor, event, json.dumps(detail, sort_keys=True), prev, h),
        )


def verify_chain() -> dict:
    ensure()
    prev = "0" * 64
    for r in rows("SELECT * FROM defense_chain ORDER BY seq"):
        body = json.dumps(
            {
                "ts": r["ts"],
                "actor": r["actor"],
                "event": r["event"],
                "detail": json.loads(r["detail_json"]),
                "prev": prev,
            },
            sort_keys=True,
        )
        if r["prev_hash"] != prev or hashlib.sha256(body.encode()).hexdigest() != r["hash"]:
            return {"intact": False, "broken_at": r["seq"]}
        prev = r["hash"]
    return {"intact": True, "entries": len(rows("SELECT seq FROM defense_chain"))}


# --- threats ----------------------------------------------------------------------------------


def _asset(aid: str) -> dict:
    a = next((x for x in ASSETS if x["id"] == aid), None)
    if not a:
        raise NotFound("Unknown asset")
    return a


def threats() -> dict:
    groups: dict[str, dict] = {}
    for e in EVENTS:
        g = groups.setdefault(e["dedup"], {**e, "count": 0, "event_ids": [], "first_seen": e["seen"]})
        g["count"] += 1
        g["event_ids"].append(e["id"])
        g["first_seen"] = min(g["first_seen"], e["seen"])
        g["seen"] = max(g["seen"], e["seen"])
    out = []
    for g in groups.values():
        a = _asset(g["asset"])
        out.append(
            {
                k: g[k]
                for k in (
                    "dedup",
                    "source",
                    "type",
                    "severity",
                    "classification",
                    "asset",
                    "count",
                    "event_ids",
                    "first_seen",
                    "seen",
                    "evidence",
                    "status",
                    "indicator",
                )
            }
            | {
                "asset_name": a["name"],
                "asset_kind": a["kind"],
                "protected": a["protected"],
                "services": [SERVICES[s]["name"] for s in a["services"]],
                "owner": a["owner"],
                "provenance": SIM,
            }
        )
    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    cls_rank = {"confirmed_incident": 0, "suspected_incident": 1, "alert": 2}
    out.sort(key=lambda t: (t["status"] == "resolved", cls_rank[t["classification"]], rank[t["severity"]]))
    active = [t for t in out if t["status"] != "resolved"]
    return {
        "threats": out,
        "summary": {
            "active": len(active),
            "confirmed_active": sum(t["classification"] == "confirmed_incident" for t in active),
            "suspected": sum(t["classification"] == "suspected_incident" for t in active),
            "alerts": sum(t["classification"] == "alert" for t in active),
            "malware_active": sum(t["type"] == "malware" for t in active),
            "by_severity": {s: sum(t["severity"] == s for t in active) for s in rank},
        },
        "vulnerabilities": sorted(VULNS, key=lambda v: -v["cvss"]),
        "note": SIM_NOTE,
        "provenance": SIM,
        "under_attack": "No confirmed active compromise. One suspected malware incident is under investigation."
        if not any(t["classification"] == "confirmed_incident" for t in active)
        else "Confirmed active incident.",
    }


def attack_paths() -> dict:
    """Exposure graph from authorised evidence only: indicator → asset → service → business."""
    nodes, edges = [], []
    seen = set()

    def add(n):
        if n["id"] not in seen:
            seen.add(n["id"])
            nodes.append(n)

    for t in threats()["threats"]:
        if t["status"] == "resolved":
            continue
        tid = f"threat:{t['dedup']}"
        add(
            {
                "id": tid,
                "label": f"{t['type'].replace('_', ' ')} ({t['classification'].replace('_', ' ')})",
                "group": "threat",
                "state": t["severity"],
            }
        )
        a = _asset(t["asset"])
        add(
            {
                "id": a["id"],
                "label": a["name"],
                "group": "protected" if a["protected"] else a["kind"],
                "state": a["criticality"],
            }
        )
        edges.append({"source": tid, "target": a["id"], "label": t["source"]})
        for s in a["services"]:
            add({"id": f"svc:{s}", "label": SERVICES[s]["name"], "group": "service"})
            edges.append({"source": a["id"], "target": f"svc:{s}"})
    for v in VULNS:
        a = _asset(v["asset"])
        if v["cvss"] >= 7:
            add(
                {
                    "id": f"vuln:{v['id']}",
                    "label": f"{v['id']} (CVSS {v['cvss']})",
                    "group": "vulnerability",
                    "state": "exploit known" if v["exploit_known"] else None,
                }
            )
            add(
                {
                    "id": a["id"],
                    "label": a["name"],
                    "group": "protected" if a["protected"] else a["kind"],
                    "state": a["criticality"],
                }
            )
            edges.append({"source": f"vuln:{v['id']}", "target": a["id"], "label": "exposure"})
            for s in a["services"]:
                add({"id": f"svc:{s}", "label": SERVICES[s]["name"], "group": "service"})
                edges.append({"source": a["id"], "target": f"svc:{s}"})
    return {
        "nodes": nodes,
        "edges": edges,
        "provenance": SIM,
        "note": "Built only from recorded detections and "
        "scanner findings. It shows exposure, not a confirmed attack path.",
    }


# --- downtime -----------------------------------------------------------------------------------


def downtime() -> dict:
    from app.tools import deploy

    sf = deploy.health(timeout_s=1.0)
    real_inc = rows("SELECT id, title, status, opened_at, resolved_at FROM incidents ORDER BY opened_at")
    events = []
    for d in DOWNTIME:
        s, e = datetime.fromisoformat(d["start"]), datetime.fromisoformat(d["end"])
        mins = int((e - s).total_seconds() // 60)
        svc = SERVICES[d["service"]]
        rph = svc["revenue_per_hour_cents"]
        events.append(
            {
                "service": svc["name"],
                "start": d["start"],
                "end": d["end"],
                "minutes": mins,
                "rto_min": svc["rto_min"],
                "within_rto": mins <= svc["rto_min"],
                "cause_recorded": d["cause_recorded"],
                "note": d["note"],
                "provenance": SIM,
                "impact_estimate_cents": round(rph * mins / 60) if rph else None,
            }
        )
    corr = []
    for ev in events:
        s, e = datetime.fromisoformat(ev["start"]) - timedelta(hours=2), datetime.fromisoformat(ev["end"])
        near = [t["id"] for t in EVENTS if s <= datetime.fromisoformat(t["seen"]) <= e + timedelta(hours=2)]
        if near:
            corr.append(
                {
                    "service": ev["service"],
                    "co_occurring_events": near,
                    "statement": "These events happened within two hours of the outage. Timing alone does not "
                    "show that one caused the other.",
                }
            )
    deps = [
        {
            "service": v["name"],
            "depends_on": [(_asset(x)["name"] if any(a["id"] == x for a in ASSETS) else x) for x in v["depends"]],
            "rto_min": v["rto_min"],
        }
        for v in SERVICES.values()
    ]
    return {
        "live": {
            "storefront_reachable": sf.get("reachable"),
            "provenance": "operational_record",
            "incidents": [dict(r) for r in real_inc],
        },
        "outages": events,
        "correlations": corr,
        "dependencies": deps,
        "provenance": SIM,
        "note": "Outage history is simulated except the storefront health check and its incidents (real records).",
    }


# --- alerts -------------------------------------------------------------------------------------


def alerts(username: str | None = None) -> list[dict]:
    ensure()
    out = []

    def add(
        key: str,
        severity: str,
        title: str,
        category: str,
        owner: str,
        provenance: str,
        count: int = 1,
        evidence: str = "",
    ):
        aid = "ALR-" + hashlib.sha256(key.encode()).hexdigest()[:10].upper()
        out.append(
            {
                "id": aid,
                "key": key,
                "severity": severity,
                "title": title,
                "category": category,
                "owner": owner,
                "count": count,
                "evidence": evidence,
                "provenance": provenance,
            }
        )

    for t in threats()["threats"]:
        if t["status"] == "resolved":
            continue
        sev = "critical" if t["classification"] == "confirmed_incident" else t["severity"]
        add(
            t["dedup"],
            sev,
            f"{t['type'].replace('_', ' ').capitalize()} on {t['asset_name']} "
            f"({t['classification'].replace('_', ' ')})",
            "security",
            t["owner"],
            SIM,
            t["count"],
            t["evidence"],
        )
    dt = downtime()
    if dt["live"]["storefront_reachable"] is False:
        add(
            "outage:storefront",
            "critical",
            "Storefront is not answering its health check",
            "availability",
            "E-commerce team",
            "operational_record",
        )
    for i in dt["live"]["incidents"]:
        if i["status"] != "resolved":
            add(
                f"incident:{i['id']}",
                "high",
                f"Open incident: {i['title']}",
                "availability",
                "Engineering on-call",
                "operational_record",
            )
    for c in CERTS:
        days = (date.fromisoformat(c["expires"]) - TODAY).days
        if c["critical"] and days <= 30:
            add(
                f"cert:{c['name']}",
                "high" if days <= 14 else "medium",
                f"{c['name']} expires in {days} days",
                "certificates",
                "Infrastructure team",
                SIM,
            )
    for b in BACKUPS:
        if b["critical"] and b["last_status"] != "ok":
            add(
                f"backup:{b['name']}",
                "high",
                f"{b['name']} failed on its last run",
                "backups",
                "Infrastructure team",
                SIM,
            )
    for lic in LICENSES:
        deadline = date.fromisoformat(lic["renewal"]) - timedelta(days=lic["notice_days"])
        days = (deadline - TODAY).days
        if 0 <= days <= 45:
            add(
                f"renewal:{lic['id']}",
                "medium",
                f"{lic['product']}: renewal notice deadline in {days} days",
                "licenses",
                lic["owner"],
                SIM,
            )
    state = {r["alert_id"]: r for r in rows("SELECT * FROM defense_alert_state")}
    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    for a in out:
        s = state.get(a["id"])
        a["state"] = s["state"] if s else "open"
        a["state_by"] = s["by_user"] if s else None
        a["escalated"] = a["severity"] == "critical" and a["state"] == "open"
    out = [a for a in out if a["state"] not in ("suppressed", "resolved")] + [
        a for a in out if a["state"] in ("suppressed", "resolved")
    ]
    out.sort(key=lambda a: (a["state"] in ("suppressed", "resolved"), rank[a["severity"]]))
    return out


def set_alert_state(alert_id: str, state: str, user, note: str | None) -> dict:
    from app import auth

    auth.require(user, "alert.manage", "alert", alert_id)
    if state not in ("acknowledged", "suppressed", "resolved", "open"):
        raise PlatformError("state must be acknowledged, suppressed, resolved or open")
    if not any(a["id"] == alert_id for a in alerts()):
        raise NotFound("Unknown alert")
    with session() as conn:
        conn.execute(
            "INSERT INTO defense_alert_state (alert_id, state, by_user, at, note) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(alert_id) DO UPDATE SET state = excluded.state, by_user = excluded.by_user, "
            "at = excluded.at, note = excluded.note",
            (alert_id, state, user.username, now_iso(), note),
        )
    _chain(user.username, f"alert.{state}", {"alert": alert_id})
    return next(a for a in alerts() if a["id"] == alert_id)


# --- containment ------------------------------------------------------------------------------


def preview(action: str, asset_id: str, user, indicator: str | None = None) -> dict:
    """A dry-run plan: scope, impact, safety checks, approvals and rollback. Changes nothing."""
    a = _asset(asset_id)
    spec = CONTAINMENT_ACTIONS.get(action)
    if not spec:
        raise PlatformError("Unknown containment action")
    checks = []
    if a["protected"]:
        checks.append(
            {
                "check": "Protected environment",
                "ok": False,
                "detail": f"{a['name']} is {a['env']} (safety-critical). Flo & Jerry never contains protected "
                "systems; escalate to the site OT & safety team instead.",
            }
        )
    if spec["kinds"] is not None and a["kind"] not in spec["kinds"]:
        checks.append(
            {
                "check": "Action fits the asset",
                "ok": False,
                "detail": f"{spec['label']} does not apply to a {a['kind'].replace('_', ' ')}.",
            }
        )
    if action == "pause_workload" and a["criticality"] in ("high", "critical"):
        checks.append(
            {
                "check": "Noncritical workload only",
                "ok": False,
                "detail": "Only low-criticality workloads may be paused; this one serves customers.",
            }
        )
    if action == "block_indicator" and not indicator:
        checks.append({"check": "Indicator specified", "ok": False, "detail": "A specific indicator is required."})
    allowed = all(c["ok"] for c in checks)
    impacted = [SERVICES[s]["name"] for s in a["services"]]
    plan = {
        "action": action,
        "label": spec["label"],
        "asset": {k: a[k] for k in ("id", "name", "kind", "env", "criticality", "owner")},
        "indicator": indicator,
        "allowed": allowed,
        "checks": checks
        or [
            {
                "check": "Scope and safety",
                "ok": True,
                "detail": "Explicit asset, allowlisted action, not a protected environment.",
            }
        ],
        "impact": spec["impact"],
        "impacted_services": impacted,
        "required_approvals": 2 if spec["impact"] == "high" else 1,
        "approval_window_min": APPROVAL_MINUTES,
        "rollback": spec["rollback"],
        "dry_run": True,
        "live_execution_available": CONTAINMENT_LIVE,
        "escalation": "If containment is refused or not supported: page the security on-call, open the "
        "incident-response workflow, and for OT/safety systems call the site OT & safety lead.",
        "note": "Preview only — nothing has been changed.",
    }
    _chain(user.username, "containment.preview", {"action": action, "asset": asset_id, "allowed": allowed})
    return plan


def propose(action: str, asset_id: str, user, indicator: str | None = None) -> dict:
    from app import auth

    auth.require(user, "containment.propose", "asset", asset_id)
    plan = preview(action, asset_id, user, indicator)
    if not plan["allowed"]:
        raise Forbidden(
            "Containment refused by safety checks: " + "; ".join(c["detail"] for c in plan["checks"] if not c["ok"])
        )
    pid = new_id("CTN")
    ensure()
    with session() as conn:
        conn.execute(
            "INSERT INTO defense_proposals (id, action, asset_id, indicator, proposed_by, created_at, status, "
            "impact, required_approvals) VALUES (?, ?, ?, ?, ?, ?, 'awaiting_approval', ?, ?)",
            (pid, action, asset_id, indicator, user.username, now_iso(), plan["impact"], plan["required_approvals"]),
        )
    _chain(user.username, "containment.proposed", {"id": pid, "action": action, "asset": asset_id})
    return get_proposal(pid)


def get_proposal(pid: str) -> dict:
    ensure()
    r = rows("SELECT * FROM defense_proposals WHERE id = ?", (pid,))
    if not r:
        raise NotFound("Unknown proposal")
    p = dict(r[0])
    p["approvals"] = json.loads(p.pop("approvals_json"))
    raw = p.pop("result_json")
    p["result"] = json.loads(raw) if raw else None
    return p


def approve(pid: str, user, password: str) -> dict:
    from app import auth

    auth.require(user, "containment.approve", "containment", pid)
    found = rows("SELECT password_hash, salt FROM users WHERE username = ?", (user.username,))
    if not found or not hmac.compare_digest(found[0]["password_hash"], auth._hash(password, found[0]["salt"])):
        _chain(user.username, "containment.stepup_failed", {"id": pid})
        raise Forbidden("Step-up authentication failed")
    p = get_proposal(pid)
    if p["status"] not in ("awaiting_approval", "approved"):
        raise PlatformError(f"Proposal is {p['status']}")
    if user.username == p["proposed_by"]:
        raise Forbidden("The proposer cannot approve their own containment request")
    if user.username in {a["by"] for a in p["approvals"]}:
        raise Forbidden("Each approver can approve once; a second, different approver is required")
    approvals = p["approvals"] + [{"by": user.username, "role": user.role, "at": now_iso()}]
    status, until = p["status"], p["approved_until"]
    if len(approvals) >= p["required_approvals"]:
        status = "approved"
        until = (datetime.now(timezone.utc) + timedelta(minutes=APPROVAL_MINUTES)).isoformat(timespec="seconds")
    with session() as conn:
        conn.execute(
            "UPDATE defense_proposals SET approvals_json = ?, status = ?, approved_until = ? WHERE id = ?",
            (json.dumps(approvals), status, until, pid),
        )
    _chain(user.username, "containment.approved", {"id": pid, "approvals": len(approvals), "status": status})
    return get_proposal(pid)


def execute(pid: str, user, idempotency_key: str) -> dict:
    from app import auth

    auth.require(user, "containment.propose", "containment", pid)
    p = get_proposal(pid)
    if p["result"] is not None:
        return p  # idempotent: the same request returns the same recorded result
    if p["status"] != "approved":
        raise Forbidden("Containment needs its required approvals before execution")
    if datetime.fromisoformat(p["approved_until"]) < datetime.now(timezone.utc):
        with session() as conn:
            conn.execute("UPDATE defense_proposals SET status = 'expired' WHERE id = ?", (pid,))
        _chain(user.username, "containment.expired", {"id": pid})
        raise Forbidden("The approval window has expired; request approval again")
    result = {
        "executed": False,
        "dry_run": True,
        "at": now_iso(),
        "message": "Dry run only: no containment connector is configured and demo mode never executes actions. "
        "Nothing was changed. Use the rollback and escalation steps if you act in your security tools.",
        "would_do": CONTAINMENT_ACTIONS[p["action"]]["label"] + f" on {p['asset_id']}",
    }
    with session() as conn:
        conn.execute(
            "UPDATE defense_proposals SET status = 'dry_run_complete', result_json = ?, idempotency_key = ? "
            "WHERE id = ?",
            (json.dumps(result), idempotency_key, pid),
        )
    _chain(user.username, "containment.executed_dry_run", {"id": pid, "key": idempotency_key})
    return get_proposal(pid)


# --- licence savings ----------------------------------------------------------------------------


def _months_left_in_quarter(d: date) -> int:
    q_end_month = ((d.month - 1) // 3 + 1) * 3
    return q_end_month - d.month + 1


def license_savings(granted: bool = False) -> dict:
    """Deterministic savings maths. Unit prices are confidential: shown only to a procurement grant."""
    rows_out = []
    q_end = date(TODAY.year, ((TODAY.month - 1) // 3 + 1) * 3, 1) + timedelta(days=31)
    q_end = q_end.replace(day=1) - timedelta(days=1)
    for lic in LICENSES:
        price = lic["unit_price_cents_month"]
        unassigned = lic["paid"] - lic["assigned"]
        inactive = lic["assigned"] - lic["active_30d"]
        unused = unassigned + inactive
        reassign = min(unused, lic["requested"]) if lic["reassignable"] else 0
        after_reassign = unused - reassign
        downgrade_monthly = 0
        if lic["downgrade"]:
            downgrade_monthly = lic["light_users"] * (price - lic["downgrade"]["unit_price_cents_month"])
        floor = max(lic["min_seats"], lic["active_30d"] + lic["requested"])
        renewal_cut = max(0, lic["paid"] - floor)
        renewal_annual = renewal_cut * price * 12
        deadline = date.fromisoformat(lic["renewal"]) - timedelta(days=lic["notice_days"])
        notice_open = deadline >= TODAY
        if lic["billing"] == "monthly":
            realizable_q = after_reassign * price * _months_left_in_quarter(TODAY)
            realizable_note = "Monthly billing: unused seats can be removed now."
        elif notice_open and date.fromisoformat(lic["renewal"]) <= q_end:
            realizable_q = 0
            realizable_note = "Saving starts at renewal; this quarter avoids no spend."
        elif notice_open:
            realizable_q = 0
            realizable_note = f"Act before the notice deadline {deadline}; savings start at renewal {lic['renewal']}."
        else:
            realizable_q = 0
            renewal_annual = 0
            realizable_note = f"Notice deadline {deadline} has passed: no reduction possible this term."
        r = {
            "id": lic["id"],
            "vendor": lic["vendor"],
            "product": lic["product"],
            "category": lic["category"],
            "renewal": lic["renewal"],
            "notice_deadline": deadline.isoformat(),
            "notice_open": notice_open,
            "paid": lic["paid"],
            "assigned": lic["assigned"],
            "active_30d": lic["active_30d"],
            "unused": unused,
            "reassign": reassign,
            "billing": lic["billing"],
            "min_seats": lic["min_seats"],
            "cancellation": lic["cancellation"],
            "owner": lic["owner"],
            "unused_spend_annual_cents": unused * price * 12,
            "downgrade_annual_cents": downgrade_monthly * 12,
            "renewal_reduction_seats": renewal_cut,
            "renewal_reduction_annual_cents": renewal_annual,
            "realizable_this_quarter_cents": realizable_q,
            "realizable_note": realizable_note,
            "renegotiate": notice_open and (renewal_cut > 0 or downgrade_monthly > 0),
        }
        if granted:
            r["unit_price_cents_month"] = price
        else:  # money totals rounded to the nearest CAD 1,000 so unit prices cannot be back-calculated precisely
            for k in (
                "unused_spend_annual_cents",
                "downgrade_annual_cents",
                "renewal_reduction_annual_cents",
                "realizable_this_quarter_cents",
            ):
                r[k] = round(r[k] / 100_000) * 100_000
        rows_out.append(r)
    tot = {
        k: sum(r[k] for r in rows_out)
        for k in (
            "unused",
            "unused_spend_annual_cents",
            "downgrade_annual_cents",
            "renewal_reduction_annual_cents",
            "realizable_this_quarter_cents",
        )
    }
    return {
        "licenses": rows_out,
        "totals": tot,
        "provenance": SIM,
        "terms": "Estimated avoided expenditure (cost savings), not revenue. Nothing is realised until a contract "
        "change takes effect.",
        "note": "Simulated licence and usage data — no billing, procurement or SaaS-admin system is connected. "
        "Unit prices are confidential; totals are rounded to the nearest CAD 1,000 unless you hold a "
        "procurement grant.",
    }


def briefing() -> dict:
    t = threats()
    d = downtime()
    s = license_savings()
    al = alerts()
    return {
        "facts": [
            f"{t['summary']['active']} active security item(s): {t['summary']['confirmed_active']} confirmed, "
            f"{t['summary']['suspected']} suspected, {t['summary']['alerts']} alert(s) awaiting triage.",
            f"{len(d['outages'])} recorded outage(s) in the last 24 hours; "
            f"{sum(not o['within_rto'] for o in d['outages'])} exceeded the recovery objective.",
            f"{sum(a['severity'] == 'critical' for a in al)} critical and "
            f"{sum(a['severity'] == 'high' for a in al)} high "
            "alert(s) open after grouping.",
            f"{s['totals']['unused']:,} unused licence units; estimated unused spend CAD "
            f"{s['totals']['unused_spend_annual_cents'] / 100:,.0f} a year.",
        ],
        "hypotheses": [
            "The QA laptop malware detection may be one infection detected twice (same hash).",
            "The reporting outage overlaps the service-account sign-in alert in time; that is not evidence of cause.",
        ],
        "recommendations": [
            "Preview isolating QA laptop 14 (needs two approvals) and open the incident-response workflow.",
            "Patch or restrict the ERP admin interface (SYN-VULN-001) this week.",
            "Re-run the failed ERP backup today.",
            "Reduce BI Pro seats and move light users to the viewer tier before the notice deadline.",
        ],
        "provenance": SIM,
        "note": SIM_NOTE,
    }
