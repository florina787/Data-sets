"""Jerry commands for Defense Command (security, downtime, containment, alerts, licences) and
Enterprise Delivery & Team Intelligence (portfolio). Read-only: containment is only ever previewed here;
proposing, approving and executing happen in the containment console with step-up authentication.
"""

from __future__ import annotations

import re

from app.copilot.router import Parsed

SEV = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


def _src(kind: str, label: str, ref: str, detail: str = "") -> dict:
    from app.enterprise import queries as q

    return q.src(kind, label, ref, detail)


def _money(cents: int) -> str:
    v = cents / 100
    return f"CAD {v / 1e6:,.2f}M" if v >= 1e6 else f"CAD {v:,.0f}"


# --- Defense Command ------------------------------------------------------------------------


def h_threats(p: Parsed, c) -> list[str]:
    from app import defense

    t = c.call("security_threats", defense.threats)
    s = t["summary"]
    cite = c.cite(
        _src(
            "data",
            "Security detections (simulated SIEM/EDR/scanner/identity telemetry)",
            "defense:threats",
            "synthetic; no security tool connected",
        )
    )
    active = [x for x in t["threats"] if x["status"] != "resolved"]
    by_type: dict[str, int] = {}
    for x in active:
        by_type[x["type"]] = max(by_type.get(x["type"], 0), SEV[x["severity"]] * 25)
    axes = [
        {"label": lb, "value": float(by_type.get(k, 0)), "detail": f"{sum(a['type'] == k for a in active)} item(s)"}
        for k, lb in (
            ("malware", "Malware"),
            ("suspicious_auth", "Identity"),
            ("vulnerability", "Vulnerabilities"),
            ("misconfiguration", "Misconfiguration"),
            ("network_anomaly", "Network"),
        )
    ]
    c.visuals.append(
        {
            "kind": "radar",
            "title": "Enterprise threat radar",
            "axes": axes,
            "provenance": "synthetic",
            "caption": "Each axis shows the highest active severity (critical = 100).",
        }
    )
    graph = defense.attack_paths()
    c.visuals.append(
        {
            "kind": "flow",
            "title": "Exposure graph: detections → assets → business services",
            "nodes": graph["nodes"][:40],
            "edges": graph["edges"][:80],
            "provenance": "synthetic",
            "caption": graph["note"],
        }
    )
    assets = sorted({v["asset"] for v in t["vulnerabilities"]})
    vmap = {v["asset"]: v for v in t["vulnerabilities"]}
    c.visuals.append(
        {
            "kind": "heatmap",
            "title": "Vulnerability exposure matrix",
            "provenance": "synthetic",
            "rows": assets,
            "columns": ["CVSS", "Exploit known", "Internet-facing", "Active detection"],
            "values": [
                [
                    4 if vmap[a]["cvss"] >= 9 else 3 if vmap[a]["cvss"] >= 7 else 2 if vmap[a]["cvss"] >= 4 else 1,
                    3 if vmap[a]["exploit_known"] else 0,
                    3 if vmap[a]["internet_facing"] else 0,
                    3 if any(x["asset"] == a for x in active) else 0,
                ]
                for a in assets
            ],
        }
    )
    c.ui_actions.append({"type": "open_page", "label": "Open Defense Command", "url": "/defense"})
    c.focus = {"kind": "threats", "sites": []}
    lines = [
        f"- **{x['severity']}** · {x['type'].replace('_', ' ')} on {x['asset_name']} — "
        f"{x['classification'].replace('_', ' ')}, {x['count']} detection(s) grouped; owner {x['owner']}"
        for x in active[:5]
    ]
    return [
        f"**{t['under_attack']}** {cite}",
        f"Active items: {s['confirmed_active']} confirmed incident(s), "
        f"{s['suspected']} suspected, {s['alerts']} alert(s) awaiting triage; malware detections: "
        f"{s['malware_active']}.\n" + "\n".join(lines),
        "Alerts are detections, not proof of compromise. A confirmed incident needs an analyst's confirmation in "
        "the security tool. " + t["note"],
    ]


def h_downtime(p: Parsed, c) -> list[str]:
    from app import defense

    d = c.call("availability", defense.downtime)
    cite = c.cite(
        _src(
            "data",
            "Outage history (simulated) + storefront health check (live record)",
            "defense:downtime",
            "co-occurrence is not causation",
        )
    )
    events = [
        {
            "date": o["start"][:16].replace("T", " "),
            "label": f"{o['service']} down {o['minutes']} min"
            + (" (within RTO)" if o["within_rto"] else " (exceeded RTO)"),
            "provenance": "synthetic",
        }
        for o in d["outages"]
    ]
    events += [
        {
            "date": (i["opened_at"] or "")[:16].replace("T", " "),
            "label": f"Incident {i['id']}: {i['title']} ({i['status']})",
            "provenance": "operational_record",
        }
        for i in d["live"]["incidents"]
    ]
    c.visuals.append(
        {
            "kind": "timeline",
            "title": "Availability incident timeline",
            "events": sorted(events, key=lambda e: e["date"])[:30],
        }
    )
    c.visuals.append(
        {
            "kind": "bar",
            "title": "Outage minutes vs recovery objective (RTO)",
            "unit": "minutes",
            "provenance": "synthetic",
            "items": [
                {"label": o["service"], "value": o["minutes"], "note": f"RTO {o['rto_min']} min"} for o in d["outages"]
            ],
        }
    )
    nodes, edges = [], []
    for dep in d["dependencies"]:
        sid = "svc:" + dep["service"]
        nodes.append({"id": sid, "label": dep["service"], "group": "service", "state": f"RTO {dep['rto_min']} min"})
        for x in dep["depends_on"]:
            if not any(n["id"] == x for n in nodes):
                nodes.append({"id": x, "label": x, "group": "dependency"})
            edges.append({"source": x, "target": sid})
    c.visuals.append(
        {
            "kind": "flow",
            "title": "Business dependency graph",
            "nodes": nodes[:40],
            "edges": edges[:80],
            "provenance": "synthetic",
            "caption": "Which business services depend on which assets.",
        }
    )
    sf = "answering" if d["live"]["storefront_reachable"] else "NOT answering"
    out = [
        f"**Availability now** {cite}: the demo storefront is {sf} its health check (a live record). "
        + "; ".join(
            f"{o['service']} was down {o['minutes']} min"
            + (f" — recorded cause: {o['cause_recorded']}" if o["cause_recorded"] else " — no recorded cause")
            for o in d["outages"]
        )
        + "."
    ]
    for corr in d["correlations"]:
        out.append(f"{corr['service']}: {', '.join(corr['co_occurring_events'])} happened nearby. " + corr["statement"])
    impact = [o for o in d["outages"] if o["impact_estimate_cents"]]
    if impact:
        out.append(
            "Estimated revenue impact (where a revenue-per-hour figure exists): "
            + "; ".join(f"{o['service']} ≈ {_money(o['impact_estimate_cents'])}" for o in impact)
            + "."
        )
    else:
        out.append("No financial impact is estimated: none of these services has a defined revenue-per-hour figure.")
    return out


_ASSET_HINTS = [
    (r"laptop|endpoint|workstation|device", "WS-QA-014"),
    (r"service account|svc", "svc-reporting"),
    (r"refrigerat|cold store|ot\b|plc|production line|fry line|safety", "OT-REFRIG-03"),
    (r"erp", "SRV-ERP-01"),
    (r"batch|report workload|workload", "k8s/analytics/batch-reports"),
]


def h_containment(p: Parsed, c) -> list[str]:
    from app import defense
    from app.auth import User

    text = p.question.lower()
    if re.search(r"who (must|needs to|has to|should) approve|who approves|approval", text) and not re.search(
        r"isolate|disable|revoke|block|pause", text
    ):
        return [
            "**Who must approve containment:** an engineer proposes it; then one other person (low-impact) or two "
            "different people (high-impact: isolate, revoke, disable, pause) with the engineer or release-approver "
            "role must approve. Each approver re-enters their password (step-up authentication). Approvals expire "
            "after 15 minutes, every step is recorded in a tamper-evident log, and the proposer can never approve "
            "their own request.",
            "Protected systems — refrigeration, production lines, other OT and life-safety "
            "systems — cannot be contained from Flo & Jerry at all; they go to the site OT & safety team. In this "
            "demo, execution is always a dry run.",
        ]
    asset = next((a for rx, a in _ASSET_HINTS if re.search(rx, text)), "WS-QA-014")
    action = (
        ("disable_service_account" if "disable" in text else "revoke_credential")
        if asset == "svc-reporting"
        else "pause_workload"
        if asset.startswith("k8s/")
        else "block_indicator"
        if "block" in text
        else "isolate_endpoint"
    )
    user = User("", p.username or "", p.username or "", p.role or "viewer")
    plan = c.call(
        "containment_preview",
        defense.preview,
        action=action,
        asset_id=asset,
        user=user,
        indicator="bad-domain.example" if action == "block_indicator" else None,
    )
    cite = c.cite(_src("data", "Containment dry-run preview", f"containment:{asset}", "nothing executed"))
    c.ui_actions.append(
        {"type": "open_containment", "label": "Open the containment console", "url": "/defense?tab=containment"}
    )
    if not plan["allowed"]:
        return [
            f"**I can't contain {plan['asset']['name']}** {cite}. "
            + " ".join(ch["detail"] for ch in plan["checks"] if not ch["ok"]),
            f"**Escalation instead:** {plan['escalation']}",
        ]
    return [
        f"**Preview: {plan['label']} on {plan['asset']['name']}** {cite} — nothing has been changed. "
        f"Affected services: {', '.join(plan['impacted_services']) or 'none recorded'}. Impact: {plan['impact']}.",
        f"**To proceed:** propose it in the containment console; it then needs {plan['required_approvals']} "
        f"approval(s) from people other than you, each with step-up authentication, within "
        f"{plan['approval_window_min']} minutes. **Rollback:** {plan['rollback']}",
        "I won't execute containment from a conversation, and in demo mode even an approved request runs as a dry "
        "run only.",
    ]


def h_alerts(p: Parsed, c) -> list[str]:
    from app import defense

    al = c.call("alerts", defense.alerts)
    cite = c.cite(_src("data", "Alerting engine (grouped, deduplicated)", "defense:alerts", f"{len(al)} alert(s)"))
    open_ = [a for a in al if a["state"] not in ("suppressed", "resolved")]
    c.visuals.append(
        {
            "kind": "kpis",
            "title": "Open alerts by severity",
            "provenance": "mixed",
            "items": [
                {
                    "label": s.capitalize(),
                    "value": str(sum(a["severity"] == s for a in open_)),
                    "status": "attention"
                    if s in ("critical", "high") and any(a["severity"] == s for a in open_)
                    else "good",
                }
                for s in ("critical", "high", "medium", "low")
            ],
        }
    )
    c.visuals.append(
        {
            "kind": "table",
            "title": "Alerts needing attention",
            "provenance": "mixed",
            "columns": ["Severity", "Alert", "Category", "Owner", "Grouped", "State"],
            "rows": [
                [a["severity"], a["title"][:80], a["category"], a["owner"], a["count"], a["state"]] for a in open_[:12]
            ],
        }
    )
    c.ui_actions.append({"type": "open_page", "label": "Manage alerts", "url": "/defense?tab=alerts"})
    return [
        f"**{len(open_)} open alert(s) after grouping related events** {cite}. Most urgent: "
        + "; ".join(f"{a['title']} ({a['severity']})" for a in open_[:3])
        + ".",
        "Notifications: no external channel (email, chat, paging) is configured, so alerts appear here only.",
    ]


def h_licenses(p: Parsed, c) -> list[str]:
    from app import defense

    s = c.call("license_savings", defense.license_savings, granted=p.role == "procurement")
    t = s["totals"]
    cite = c.cite(
        _src(
            "data",
            "Licence utilisation (simulated billing/SaaS-admin data)",
            "defense:licenses",
            "deterministic; unit prices confidential",
        )
    )
    reassign = sum(x["reassign"] for x in s["licenses"])
    c.visuals.append(
        {
            "kind": "waterfall",
            "title": "From unused spend to realisable savings (annual, estimated)",
            "unit": "CAD",
            "provenance": "synthetic",
            "steps": [
                {"label": "Unused licence spend", "value": round(t["unused_spend_annual_cents"] / 100)},
                {"label": "Downgrade opportunity", "value": round(t["downgrade_annual_cents"] / 100)},
                {"label": "Renewal reduction", "value": round(t["renewal_reduction_annual_cents"] / 100)},
                {"label": "Realisable this quarter", "value": round(t["realizable_this_quarter_cents"] / 100)},
            ],
            "missing": [],
        }
    )
    c.visuals.append(
        {
            "kind": "table",
            "title": "Licences",
            "provenance": "synthetic",
            "columns": ["Product", "Paid", "Active (30 d)", "Unused", "Renewal", "Notice by", "Action"],
            "rows": [
                [
                    x["product"],
                    x["paid"],
                    x["active_30d"],
                    x["unused"],
                    x["renewal"],
                    x["notice_deadline"],
                    "Renegotiate" if x["renegotiate"] else x["realizable_note"][:60],
                ]
                for x in s["licenses"]
            ],
        }
    )
    c.ui_actions.append({"type": "open_page", "label": "Open licence savings", "url": "/defense?tab=licenses"})
    text = p.question.lower()
    out = [
        f"**{t['unused']:,} unused licence units** {cite}: estimated unused spend "
        f"{_money(t['unused_spend_annual_cents'])} "
        f"a year. {reassign} seat(s) can be reassigned to people waiting for access instead of buying more."
    ]
    if "quarter" in text:
        out.append(
            f"**This quarter** you can avoid about {_money(t['realizable_this_quarter_cents'])} — only where "
            "billing is monthly. Annual contracts save nothing until their renewal date."
        )
    reneg = [x for x in s["licenses"] if x["renegotiate"]]
    if reneg:
        out.append(
            "**Renegotiate before the notice deadline:** "
            + "; ".join(
                f"{x['product']} (notice by {x['notice_deadline']}, renewal {x['renewal']}, "
                f"−{x['renewal_reduction_seats']} "
                "seats possible)"
                for x in reneg
            )
            + "."
        )
    out.append(s["terms"] + " " + s["note"])
    return out


def h_defense_brief(p: Parsed, c) -> list[str]:
    from app import defense

    b = c.call("security_savings_briefing", defense.briefing)
    h_threats(p, c)
    cite = c.cite(_src("data", "Security & savings briefing (simulated telemetry)", "defense:briefing", "synthetic"))
    return [
        f"**Observed facts** {cite}:\n" + "\n".join(f"- {x}" for x in b["facts"]),
        "**Hypotheses (not established):**\n" + "\n".join(f"- {x}" for x in b["hypotheses"]),
        "**Recommendations (each needs an owner's approval):**\n" + "\n".join(f"- {x}" for x in b["recommendations"]),
        b["note"],
    ]


# --- Enterprise Delivery & Team Intelligence -------------------------------------------------


def _gantt(items: list[dict], title: str) -> dict:
    rows = []
    for x in items[:12]:
        ms = x["milestones"]
        rows.append(
            {
                "label": x["name"],
                "group": x["dept"],
                "start": min(m["planned"] for m in ms),
                "end": max(m["actual"] or m["planned"] for m in ms),
                "status": x["status"],
                "milestones": [
                    {"name": m["name"], "date": m["actual"] or m["planned"], "state": m["state"]} for m in ms
                ],
            }
        )
    from app import portfolio

    return {
        "kind": "gantt",
        "title": title,
        "today": portfolio.TODAY.isoformat(),
        "rows": rows,
        "provenance": "synthetic",
    }


def _deps_flow(items: list[dict], all_items: dict[str, dict]) -> dict:
    nodes, edges, seen = [], [], set()

    def add(x):
        if x["id"] not in seen:
            seen.add(x["id"])
            nodes.append({"id": x["id"], "label": x["name"], "group": x["dept"], "state": x["status"]})

    for x in items:
        add(x)
        for d in x["depends_on"]:
            add(all_items[d])
            edges.append({"source": d, "target": x["id"], "label": "verified dependency"})
        for t in x["tech"][:4]:
            tid = "tech:" + t["name"]
            if tid not in seen:
                seen.add(tid)
                nodes.append({"id": tid, "label": t["name"], "group": t["kind"]})
            edges.append({"source": tid, "target": x["id"], "label": t["relation"]})
    return {
        "kind": "flow",
        "title": "Initiatives, dependencies and supporting technology",
        "nodes": nodes[:40],
        "edges": edges[:80],
        "provenance": "synthetic",
        "caption": "Edge labels say whether a technology link is verified (recorded) or inferred (suggested).",
    }


def h_portfolio(p: Parsed, c) -> list[str]:
    from app import portfolio, privacy

    principal = privacy.Principal(p.username or "", p.role or "viewer")
    data = c.call("portfolio", portfolio.portfolio, principal=principal, purpose="llm")
    items = data["initiatives"]
    by_id = {x["id"]: x for x in items}
    cite = c.cite(_src("data", "Delivery portfolio (synthetic fixture)", "portfolio:initiatives", data["note"][:200]))
    text = p.question.lower()
    dept = portfolio.find_dept(p.question)
    focus = [x for x in items if not dept or x["dept"] == dept]
    out: list[str] = []
    if re.search(r"approv|decision", text):
        week = [a for a in data["approvals"]]
        c.visuals.append(
            {
                "kind": "table",
                "title": "Decisions awaiting executive approval",
                "provenance": "synthetic",
                "columns": ["Due", "Decision", "Initiative", "Needs"],
                "rows": [[a["due"], a["decision"], by_id[a["initiative"]]["name"], a["needs"]] for a in week],
            }
        )
        return [
            f"**{len(week)} decision(s) need executive approval this week** {cite}: "
            + "; ".join(f"{a['decision']} (due {a['due']})" for a in week)
            + ". Approvals happen in the owning "
            "system's workflow; I can't approve them from here."
        ]
    if re.search(r"behind|delay|late|slip", text):
        sel = [x for x in focus if x["status"] in ("delayed", "blocked", "at_risk") and x["schedule_slip_days"] > 0]
        c.visuals.append(_gantt(sel, "Initiatives behind schedule"))
        depts = sorted({x["dept"] for x in sel})
        out.append(
            f"**Behind schedule** {cite}: {', '.join(depts) or 'none'}. "
            + "; ".join(f"{x['name']} ({x['dept']}) {x['schedule_slip_days']} day(s) late — {x['status']}" for x in sel)
            + "."
        )
    elif re.search(r"budget|overspen|over spend|exceed|cost", text):
        sel = sorted([x for x in focus if x["budget_variance_pct"] > -10], key=lambda x: -x["budget_variance_pct"])
        c.visuals.append(
            {
                "kind": "bar",
                "title": "Spend vs budget (% of budget used)",
                "unit": "%",
                "provenance": "synthetic",
                "highlight": [x["name"] for x in sel if x["budget_variance_pct"] > 0],
                "items": [
                    {
                        "label": x["name"],
                        "value": round(100 * x["spend_cents"] / x["budget_cents"], 1),
                        "note": f"variance {x['budget_variance_pct']:+.1f}%",
                    }
                    for x in sel[:10]
                ],
            }
        )
        over = [x for x in sel if x["budget_variance_pct"] > 0]
        out.append(
            f"**Over budget** {cite}: "
            + (
                "; ".join(
                    f"{x['name']} {x['budget_variance_pct']:+.1f}% "
                    f"({_money(x['spend_cents'] - x['budget_cents'])} over)"
                    for x in over
                )
                or "none"
            )
            + "."
        )
    elif re.search(r"depend|blocked by|need[s]? (it|tech)", text):
        team = "data engineering" if "data engineering" in text else (dept or "Technology")
        sel = portfolio.dependents_of(team)
        c.visuals.append(_deps_flow(sel, by_id))
        out.append(
            f"**Initiatives depending on {team}** {cite}: "
            + "; ".join(f"{x['name']} ({x['dept']}, {x['status']})" for x in sel)
            + "."
        )
    elif re.search(r"\bwho owns|owner of|who is responsible", text):
        words = [w for w in re.findall(r"[a-z]{4,}", text) if w not in ("owns", "owner", "responsible")]
        hit = max(items, key=lambda x: sum(w in x["name"].lower() for w in words))
        out.append(
            f"**{hit['name']}** {cite} is owned by {hit['owner']} ({hit['team']}, {hit['dept']}). Owner names "
            "are synthetic display names; performance data is never shown."
        )
        focus = [hit]
    elif re.search(r"deliver(ed)?|shipped|this month", text):
        done = [(x, m) for x in focus for m in x["milestones"] if m["actual"] and m["actual"].startswith("2026-10")]
        c.visuals.append(
            {
                "kind": "timeline",
                "title": "Delivered this month",
                "events": [
                    {"date": m["actual"], "label": f"{x['name']}: {m['name']}", "provenance": "synthetic"}
                    for x, m in done
                ],
            }
        )
        out.append(
            f"**Delivered in October** {cite}: " + "; ".join(f"{m['name']} — {x['name']}" for x, m in done) + "."
        )
    elif re.search(r"\broi\b|return on|value of|ai invest", text):
        ai = [x for x in items if x["id"] in ("INI-TEC-05", "INI-OPS-01", "INI-TEC-04")]
        c.visuals.append(
            {
                "kind": "bar",
                "title": "AI initiatives: expected value vs budget (CAD)",
                "unit": "CAD",
                "provenance": "synthetic",
                "items": [{"label": f"{x['name']} — budget", "value": x["budget_cents"] / 100} for x in ai]
                + [{"label": f"{x['name']} — expected value", "value": x["expected_value_cents"] / 100} for x in ai],
            }
        )
        out.append(
            f"**Return on AI investments** {cite}: expected value is a target, not a measured return. "
            + "; ".join(
                f"{x['name']}: expected {x['expected_value']}; measured: {x['measured_outcome'] or 'not yet'}"
                for x in ai
            )
            + "."
        )
    else:
        c.visuals.append(_gantt(focus, f"{dept or 'All departments'}: delivery timeline"))
        c.visuals.append(
            {
                "kind": "table",
                "title": f"{dept or 'Portfolio'} initiatives",
                "provenance": "synthetic",
                "columns": ["Initiative", "Department", "Owner", "Status", "Progress", "Next milestone"],
                "rows": [
                    [
                        x["name"],
                        x["dept"],
                        x["owner"],
                        x["status"],
                        f"{x['progress_pct']}%",
                        (x["next_milestone"] or {}).get("name", "—"),
                    ]
                    for x in focus
                ],
            }
        )
        out.append(
            f"**{dept or 'Every department'} is building** {cite}: "
            + "; ".join(
                f"{x['name']} ({x['status'].replace('_', ' ')}, owner {x['owner'].split(' — ')[0]})" for x in focus
            )
            + "."
        )
    c.focus = {"kind": "initiatives", "sites": [], "ids": [x["id"] for x in focus][:20]}
    return out


def h_team_brief(p: Parsed, c) -> list[str]:
    from app import portfolio, privacy

    data = c.call(
        "portfolio",
        portfolio.portfolio,
        principal=privacy.Principal(p.username or "", p.role or "viewer"),
        purpose="llm",
    )
    items = data["initiatives"]
    by_id = {x["id"]: x for x in items}
    cite = c.cite(_src("data", "Delivery portfolio (synthetic fixture)", "portfolio:initiatives", "all departments"))
    delivered = [x for x in items if x["measured_outcome"] or x["status"] == "done"]
    late = [x for x in items if x["status"] in ("delayed", "blocked")]
    blockers = [x for x in items if x["status"] == "blocked"]
    over = [x for x in items if x["budget_variance_pct"] > 0]
    tech_deps = portfolio.dependents_of("Technology")
    upcoming = sorted(
        [(x, x["next_milestone"]) for x in items if x["next_milestone"] and x["next_milestone"]["state"] == "upcoming"],
        key=lambda t: t[1]["planned"],
    )[:5]
    c.visuals.append(
        {
            "kind": "kpis",
            "title": "Portfolio at a glance",
            "provenance": "synthetic",
            "items": [
                {"label": "Initiatives", "value": str(len(items)), "status": "unknown"},
                {"label": "Delayed or blocked", "value": str(len(late)), "status": "attention" if late else "good"},
                {"label": "Over budget", "value": str(len(over)), "status": "watch" if over else "good"},
                {"label": "Depend on Technology", "value": str(len(tech_deps)), "status": "unknown"},
                {"label": "Decisions this week", "value": str(len(data["approvals"])), "status": "watch"},
            ],
        }
    )
    c.visuals.append(_deps_flow([by_id["INI-MKT-01"]] + blockers, by_id))
    c.visuals.append(_gantt(late + [x for x, _ in upcoming], "Delayed initiatives and upcoming milestones"))
    c.focus = {"kind": "initiatives", "sites": [], "ids": [x["id"] for x in late]}
    return [
        f"**What every team is building — what needs you** {cite}",
        "1. **Important deliveries:** "
        + "; ".join(f"{x['name']} ({x['measured_outcome']})" for x in delivered if x["measured_outcome"])
        + ".",
        "2. **Delayed:** " + "; ".join(f"{x['name']} ({x['dept']}, {x['schedule_slip_days']} d)" for x in late) + ".",
        "3. **Cross-team blockers:** "
        + "; ".join(f"{x['name']} waits on {', '.join(by_id[d]['name'] for d in x['depends_on'])}" for x in blockers)
        + ".",
        "4. **Budget exposure:** " + "; ".join(f"{x['name']} {x['budget_variance_pct']:+.1f}%" for x in over) + ".",
        f"5. **Technology dependencies:** {len(tech_deps)} business initiative(s) depend on Technology delivery.",
        "6. **Upcoming milestones:** "
        + "; ".join(f"{m['name']} — {x['name']} ({m['planned']})" for x, m in upcoming)
        + ".",
        "7. **Decisions for you this week:** " + "; ".join(a["decision"] for a in data["approvals"]) + ".",
        data["note"],
    ]
