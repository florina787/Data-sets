"""Jerry 3.0 commands and visuals: export, animate, architecture, X-Ray, scenarios, follow-ups.

Handlers append typed visuals (app/visuals.py) and safe UI actions to the context; nothing here
executes actions in enterprise systems. ``focus`` carries what the conversation is about (for
example the suppliers just ranked) so follow-ups like "show them on the globe", "only the
European ones", "compare the top two" or "what if the first one shuts down" resolve against it.
"""

from __future__ import annotations

import re

from app.copilot.router import Parsed

EUROPE = (35.0, 72.0, -25.0, 45.0)
REGIONS = {
    "europe": EUROPE,
    "european": EUROPE,
    "asia": (-10.0, 80.0, 45.0, 180.0),
    "asian": (-10.0, 80.0, 45.0, 180.0),
    "africa": (-35.0, 37.0, -20.0, 52.0),
    "african": (-35.0, 37.0, -20.0, 52.0),
    "americas": (-56.0, 72.0, -170.0, -30.0),
    "america": (-56.0, 72.0, -170.0, -30.0),
}


def _src(kind: str, label: str, ref: str, detail: str = "") -> dict:
    from app.enterprise import queries as q

    return q.src(kind, label, ref, detail)


def _principal(p: Parsed):
    from app import privacy

    return privacy.Principal(
        p.username or "anonymous", p.role or "viewer", privacy.USER_TENANT.get(p.username or "", privacy.DEFAULT_TENANT)
    )


def _sites(ids: list[str]) -> list[dict]:
    from app import geo

    by = {n["id"]: n for n in geo.network()["nodes"]}
    return [by[i] for i in ids if i in by]


# --- visuals for existing intents --------------------------------------------------------


def visualize(intents: list[str], p: Parsed, c) -> None:
    """Attach visuals that fit the question. Greetings and simple facts get none."""
    from app import privacy, pulse
    from app.enterprise import queries as q

    if "sales" in intents or "overview" in intents:
        s = q.sales_summary(window=p.weeks, province=(p.provinces or [None])[0])
        c.visuals.append(
            {
                "kind": "line",
                "title": "Weekly revenue",
                "unit": "CAD",
                "provenance": "synthetic",
                "points": [
                    {"label": w["week_start"][5:], "value": round(w["revenue"] / 100)}
                    for w in q.executive_overview()["sales"]["trend"]
                ],
            }
        )
        if s.get("by_province"):
            c.visuals.append(
                {
                    "kind": "bar",
                    "title": f"Revenue by region, last {p.weeks} weeks",
                    "unit": "CAD",
                    "provenance": "synthetic",
                    "items": [{"label": r["province"], "value": round(r["revenue"] / 100)} for r in s["by_province"]],
                }
            )
    if "overview" in intents or "pulse" in intents:
        c.visuals.append(
            {
                "kind": "kpis",
                "title": "Enterprise health",
                "provenance": "mixed",
                "items": [
                    {"label": h["label"], "value": h["value"][:60], "status": h["status"]}
                    for h in pulse.health(p.username)
                ],
            }
        )
    if "campaign" in intents and "inventory" in intents:
        r = q.campaign_stock_risk()
        c.visuals.append(
            {
                "kind": "bar",
                "title": "Weekend demand vs projected stock at campaign start",
                "unit": "units",
                "provenance": "synthetic",
                "highlight": [x["name"] for x in r["lines"] if x["risk"] == "high"],
                "items": [
                    {
                        "label": x["name"],
                        "value": x["projected_at_start"],
                        "note": f"forecast {x['weekend_forecast_units']:,}",
                    }
                    for x in r["lines"]
                ],
            }
        )
    elif "inventory" in intents:
        inv = q.inventory_status()
        c.visuals.append(
            {
                "kind": "bar",
                "title": "Lowest days of cover",
                "unit": "days",
                "provenance": "synthetic",
                "items": [
                    {"label": f"{a['name']} · {a['warehouse']}", "value": a["days_of_cover"]}
                    for a in sorted(inv["alerts"], key=lambda a: a["days_of_cover"])[:8]
                ],
            }
        )
    if "compliance" in intents:
        comp = q.compliance_check()
        c.visuals.append(
            {
                "kind": "table",
                "title": "Listing compliance issues",
                "provenance": "synthetic",
                "columns": ["Product", "Channel", "Severity", "Issue"],
                "rows": [[i["name"], i["channel"], i["severity"], i["detail"][:90]] for i in comp["issues"]],
            }
        )
    if "origin_trace" in intents:
        from app import geo

        sim = geo.simulate(country=p.country, node=p.geo_node)
        c.visuals.append(
            {
                "kind": "forecast_band",
                "title": "Modelled revenue exposure",
                "unit": geo.scenario()["currency"],
                "method": sim["method"][:400],
                "bands": [{"label": f"{h['days']} days", **h["exposure"]} for h in sim["horizons"]],
            }
        )
        c.ui_actions.append(
            {
                "type": "open_globe",
                "label": "Open on the globe",
                "geo": {k: v for k, v in {"country": p.country, "node": p.geo_node}.items() if v},
            }
        )
    if "suppliers" in intents:
        recs, _ = privacy.suppliers(_principal(p), "llm")
        top = sorted(recs, key=lambda r: (-(r["open_incidents"] or 0), r["quality_pass_pct"]))[:8]
        c.focus = {"kind": "suppliers", "sites": [r["id"] for r in top]}
        c.visuals.append(
            {
                "kind": "bar",
                "title": "Suppliers needing attention — incidents (365 days)",
                "unit": "incidents",
                "provenance": "synthetic",
                "items": [
                    {
                        "label": r["name"].replace("Synthetic supplier ", ""),
                        "value": r["open_incidents"] or 0,
                        "note": f"quality {r['quality_pass_pct']}% · spend {r['annual_spend_cents']}",
                    }
                    for r in top
                ],
            }
        )
        c.ui_actions.append(
            {"type": "open_globe", "label": "Show these suppliers on the globe", "sites": c.focus["sites"]}
        )
    if "tech_health" in intents:
        c.visuals.append(
            {
                "kind": "kpis",
                "title": "Technology health",
                "provenance": "operational_record",
                "items": [
                    {"label": t["question"], "value": t["answer"][:60], "status": t["status"]}
                    for t in pulse.technology(p.username)
                ],
            }
        )


# --- commands -----------------------------------------------------------------------------


def _export_kind(text: str) -> str:
    rules = (("security_savings", ("security and savings", "security and financial", "threats and savings")),
             ("incident_impact", ("incident impact",)), ("availability", ("downtime", "availability", "outage")),
             ("remediation", ("remediation",)), ("renewals", ("renewal",)),
             ("licenses", ("license", "licence", "software spend", "savings")),
             ("security_posture", ("security", "cyber", "threat")),
             ("delivery_board", ("enterprise delivery", "delivery briefing")),
             ("portfolio_weekly", ("delivery portfolio", "weekly delivery", "portfolio")),
             ("project_status", ("cross-functional", "project status")),
             ("tech_dependencies", ("technology dependency", "dependency report")),
             ("commercial_review", ("commercial initiative", "commercial review")),
             ("marketing_readiness", ("campaign technology", "marketing campaign", "readiness")),
             ("technology", ("technology", "tech ")), ("supplier_risk", ("supplier",)),
             ("architecture", ("architecture",)), ("decisions", ("decision", "action summary")),
             ("investigation", ("investigation",)), ("board", ("board",)),
             ("conversation", ("this conversation", "this into", "convert this", "this to pdf", "this to a pdf")))
    for kind, words in rules:
        if any(w in text for w in words):
            return kind
    return "executive"


def h_export(p: Parsed, c) -> list[str]:
    """Generate a real, policy-filtered PDF now (validated), and offer it for download."""
    from app import auth, exports, pulse

    text = p.question.lower()
    kind = _export_kind(text)
    if kind == "board" and "this" in text:
        kind = "conversation" if p.conversation_id else "board"
    ref = None
    if kind == "conversation":
        ref = p.conversation_id
        from app.memory.store import get_store

        if not ref or get_store().owner(ref) != p.username:
            kind = "board"  # nothing saved yet in this conversation: fall back to the board briefing
    if kind == "investigation":
        invs = pulse.list_investigations(p.username)
        if not invs:
            return ["You have no saved investigations to export yet. Save one from a priority, then ask again."]
        ref = invs[0]["id"]
    user = auth.User("", p.username or "", p.username or "", p.role or "viewer")
    try:
        pdf, name = c.call("export_pdf", lambda **_: exports.build(kind, user, ref), kind=kind)
    except Exception as exc:  # noqa: BLE001 - report the failure honestly, never a fake file
        return [f"I couldn't generate the {exports.KINDS.get(kind, kind)} PDF: {exc}. No file was created."]
    url = f"/api/exports/{kind}.pdf" + (f"?ref={ref}" if ref else "")
    c.ui_actions.append({"type": "download", "label": f"Download {exports.KINDS[kind]} (PDF)", "url": url})
    cite = c.cite(
        _src(
            "record",
            f"{exports.KINDS[kind]} (policy-filtered PDF)",
            f"export:{kind}",
            f"{len(pdf) // 1024} KB, classification INTERNAL",
        )
    )
    return [
        f"Your **{exports.KINDS[kind]}** is ready {cite}. It includes an executive summary, findings, charts where "
        "relevant, evidence with data provenance, the reporting period, assumptions and limitations, recommended "
        "next steps, a generation timestamp and its confidentiality classification.",
        "Privacy Shield applied: confidential commercial values appear only as bands, and personal, banking and "
        "credential data is excluded — the same rules as on screen. Nothing outside your permissions was used.",
    ]


def _architecture_graph() -> tuple[list[dict], list[dict]]:
    from app import connectors

    reg = {r["id"]: r for r in connectors.registry()}
    nodes = [
        {"id": "user", "label": "Your question", "group": "input"},
        {
            "id": "jerry",
            "label": "Jerry orchestrator",
            "group": "agent",
            "detail": "Routes the question to read-only tools",
        },
        {
            "id": "policy",
            "label": "Policy engine (Privacy Shield)",
            "group": "policy",
            "detail": "Tenant isolation, classification, minimisation",
        },
        {
            "id": "mcp",
            "label": "Approved tools / MCP",
            "group": "tools",
            "state": reg["mcp_server"]["state"],
            "detail": "Interface for approved AI tools — not a replacement for your systems",
        },
        {"id": "demo_data", "label": "Enterprise data (demo)", "group": "source", "state": reg["demo_data"]["state"]},
        {
            "id": "databricks",
            "label": "Databricks SQL",
            "group": "source",
            "state": reg["databricks"]["state"],
            "detail": "Governed analytics: allowlisted, parameterised, read-only",
        },
        {
            "id": "kubernetes",
            "label": "Kubernetes API",
            "group": "source",
            "state": reg["kubernetes"]["state"],
            "detail": "Infrastructure orchestration: read-only service health",
        },
        {"id": "legacy", "label": "Legacy ERP / SAP", "group": "source", "state": reg["sap_erp"]["state"]},
        {"id": "evidence", "label": "Evidence + citations", "group": "evidence"},
        {"id": "answer", "label": "Visual answer", "group": "output"},
    ]
    edges = [
        {"source": "user", "target": "jerry"},
        {"source": "jerry", "target": "policy"},
        {"source": "policy", "target": "mcp"},
        *({"source": "mcp", "target": s} for s in ("demo_data", "databricks", "kubernetes", "legacy")),
        *({"source": s, "target": "evidence"} for s in ("demo_data", "databricks", "kubernetes")),
        {"source": "evidence", "target": "policy", "label": "filtered again"},
        {"source": "policy", "target": "answer"},
    ]
    return nodes, edges


def h_architecture(p: Parsed, c) -> list[str]:
    from app import connectors

    nodes, edges = _architecture_graph()
    reg = connectors.registry()
    live = [r["name"] for r in reg if r["state"] in ("connected", "connection_tested", "read_only")]
    pending = [
        f"{r['name']} ({r['state'].replace('_', ' ')})"
        for r in reg
        if r["id"] in ("databricks", "kubernetes", "local_llm", "sap_erp")
    ]
    c.visuals.append(
        {
            "kind": "flow",
            "title": "How Jerry connects to your enterprise",
            "provenance": "operational_record",
            "nodes": nodes,
            "edges": edges,
            "caption": "States are verified, not assumed. Kubernetes orchestrates infrastructure; Databricks "
            "provides governed analytics; MCP is the interface for approved AI tools.",
        }
    )
    c.ui_actions += [
        {"type": "open_page", "label": "Open Connect Your Enterprise", "url": "/connect"},
        {
            "type": "open_motion",
            "label": "Animate how the systems work together",
            "url": "/api/motion/architecture.gif",
        },
    ]
    cite = c.cite(
        _src("record", "Connector registry (verified states)", "connectors:registry", f"{len(reg)} integration(s)")
    )
    text = p.question.lower()
    out = [
        f"**Your enterprise, as Jerry sees it** {cite}: working now — {', '.join(live)}. "
        f"Status of the key integrations: {'; '.join(pending)}."
    ]
    if "databricks" in text:
        out.append(
            "**Databricks:** Jerry would run only allowlisted, parameterised, read-only SQL through a "
            "least-privilege service principal, via the SQL Statement Execution API. It never writes SQL from your "
            "question. Results return through the Privacy Shield with their freshness and lineage. Until the "
            "credentials are configured, Databricks views are labelled simulated."
        )
    if "kubernetes" in text or "k8s" in text:
        out.append(
            "**Kubernetes:** Jerry reads deployment and pod health in allowlisted namespaces through a "
            "ServiceAccount with get/list permissions only — no exec, no logs, no secrets, no writes, and never "
            "kubectl from a conversation. Remediation stays a human decision in your existing tooling."
        )
    if "mcp" in text:
        out.append(
            "**MCP:** Flo & Jerry exposes approved, read-only, policy-filtered tools at /mcp (JSON-RPC 2.0). "
            "MCP is the interface for AI tools; it does not replace Databricks, Kubernetes or your ERP."
        )
    return out


def h_xray(p: Parsed, c) -> list[str]:
    if not p.last_agent_run_id:
        return [
            "Ask me a question first; then I can show exactly how I answered it — the tools, the policy checks "
            "and the sources, with timings."
        ]
    c.ui_actions.append({"type": "open_xray", "label": "Open Enterprise X-Ray", "agent_run_id": p.last_agent_run_id})
    return [
        "**Enterprise X-Ray** shows the recorded path of my previous answer: your question → orchestrator → policy "
        "engine → approved tools → sources → evidence → visual answer, with real timings. Arguments, prompts and "
        "payloads are withheld; only tool names, statuses and source states are shown."
    ]


def _story(kind: str, p: Parsed) -> dict:
    from app import geo

    if kind == "architecture":
        nodes, edges = _architecture_graph()
        steps = [
            {"title": "You ask", "text": "A question in plain language.", "nodes": ["user", "jerry"]},
            {
                "title": "Policy first",
                "text": "The policy engine decides what data you may see, before any tool runs.",
                "nodes": ["policy"],
            },
            {
                "title": "Approved tools",
                "text": "Only allowlisted, read-only tools are called (MCP is their interface).",
                "nodes": ["mcp"],
            },
            {
                "title": "Your systems",
                "text": "Demo data answers today; Databricks and Kubernetes adapters are ready but "
                "not configured here (shown with their real state).",
                "nodes": ["demo_data", "databricks", "kubernetes", "legacy"],
            },
            {
                "title": "Evidence, filtered again",
                "text": "Results return through the policy engine with citations.",
                "nodes": ["evidence", "policy"],
            },
            {
                "title": "A visual answer",
                "text": "Charts, maps and next steps — with provenance on every item.",
                "nodes": ["answer"],
            },
        ]
        return {
            "kind": "motion_story",
            "story": "architecture",
            "title": "How Jerry, MCP, Databricks and Kubernetes work together",
            "nodes": nodes,
            "edges": edges,
            "steps": steps,
            "provenance": "operational_record",
            "disclaimer": "An explanation of the request path with verified connector states — not live traffic.",
        }
    net = geo.network()
    by = {n["id"]: n for n in net["nodes"]}
    if kind == "supplier_disruption":
        sid = (p.focus or {}).get("sites", [None])[0] if (p.focus or {}).get("kind") == "suppliers" else None
        sid = sid or p.geo_node or next(n["id"] for n in net["nodes"] if n["tier"] == "supplier")
        t = geo.trace(sid)
        down = t["downstream"]
        tiers = {
            "factory": [d for d in down if d["tier"] == "factory"],
            "distribution_centre": [d for d in down if d["tier"] == "distribution_centre"],
            "market": [d for d in down if d["tier"] == "market"],
        }
        nodes = [
            {"id": sid, "label": by[sid]["name"].replace("Synthetic ", ""), "group": "supplier", "state": "disrupted"}
        ]
        nodes += [
            {"id": d["id"], "label": d["name"].replace("Synthetic ", ""), "group": d["tier"]}
            for d in (tiers["factory"] + tiers["distribution_centre"] + tiers["market"])[:24]
        ]
        ids = {n["id"] for n in nodes}
        edges = [{"source": e["from"], "target": e["to"]} for e in net["edges"] if e["from"] in ids and e["to"] in ids]
        rev = sum(m["revenue_dependent"] for m in tiers["market"])
        steps = [
            {
                "title": "Supplier stops",
                "text": f"{nodes[0]['label']} cannot ship (a modelled scenario).",
                "nodes": [sid],
            },
            {
                "title": "Factories",
                "text": f"{len(tiers['factory'])} factory(ies) lose this input.",
                "nodes": [d["id"] for d in tiers["factory"]],
            },
            {
                "title": "Distribution",
                "text": f"{len(tiers['distribution_centre'])} distribution centre(s) are affected downstream.",
                "nodes": [d["id"] for d in tiers["distribution_centre"]],
            },
            {
                "title": "Markets",
                "text": f"{len(tiers['market'])} market(s) carry USD {rev / 1e6:,.0f}M of annual "
                "scenario revenue that depends on this chain.",
                "nodes": [d["id"] for d in tiers["market"]],
            },
        ]
        return {
            "kind": "motion_story",
            "story": "supplier_disruption",
            "title": f"If {nodes[0]['label']} stops shipping",
            "nodes": nodes,
            "edges": edges,
            "steps": steps,
            "provenance": "synthetic",
            "disclaimer": "Simulation on the synthetic supply network — not a real event or live shipment data.",
        }
    market = next(n for n in net["nodes"] if n["tier"] == "market")
    path = geo.trace(market["id"])["upstream_paths"][0][::-1]
    nodes = [
        {"id": x["id"], "label": f"{x['tier'].replace('_', ' ').title()} · {x['country_name']}", "group": x["tier"]}
        for x in path
    ]
    edges = [{"source": a["id"], "target": b["id"]} for a, b in zip(path, path[1:], strict=False)]
    steps = [
        {"title": n["label"].split(" · ")[0], "text": f"Step {i + 1}: {n['label']}.", "nodes": [n["id"]]}
        for i, n in enumerate(nodes)
    ]
    return {
        "kind": "motion_story",
        "story": "farm_to_market",
        "title": "The product journey, farm to market",
        "nodes": nodes,
        "edges": edges,
        "steps": steps,
        "provenance": "synthetic",
        "disclaimer": "A path through the synthetic network — not tracking data.",
    }


def story_kind(text: str) -> str:
    if re.search(r"supplier|disruption|spread|shut|fail|outage", text):
        return "supplier_disruption"
    if re.search(r"journey|farm to|farm-to|product", text):
        return "farm_to_market"
    return "architecture"


def h_animate(p: Parsed, c) -> list[str]:
    kind = story_kind(p.question.lower())
    story = _story(kind, p)
    c.visuals.append(story)
    c.ui_actions.append({"type": "download", "label": "Download as GIF", "url": f"/api/motion/{kind}.gif"})
    cite = c.cite(
        _src("record" if kind == "architecture" else "data", story["title"], f"motion:{kind}", story["disclaimer"])
    )
    return [
        f"**{story['title']}** {cite} — press play to watch it step by step; a static version and a text "
        f"description are included. {story['disclaimer']}"
    ]


def h_scenario(p: Parsed, c) -> list[str]:
    from app import geo

    story = _story("supplier_disruption", p)
    sid = story["nodes"][0]["id"]
    sim = geo.simulate(node=sid)
    c.visuals.append(story)
    c.visuals.append(
        {
            "kind": "forecast_band",
            "title": "Modelled exposure for this supplier",
            "unit": "USD",
            "method": sim["method"][:400],
            "bands": [{"label": f"{h['days']} days", **h["exposure"]} for h in sim["horizons"]],
        }
    )
    c.focus = {"kind": "scenario", "sites": [sid]}
    cite = c.cite(
        _src(
            "data",
            "Supplier disruption scenario (synthetic network, modelled)",
            f"geo_scenario:{sid}",
            "Monte Carlo, P10–P90",
        )
    )
    factories = [n["label"] for n in story["nodes"] if n["group"] == "factory"]
    return [
        f"**Scenario: {story['nodes'][0]['label']} stops shipping** {cite}. Affected downstream: "
        f"{len(factories)} factory(ies) ({', '.join(factories[:4]) or 'none'}), then distribution centres and markets "
        "shown in the animation.",
        "This is a modelled scenario on synthetic data — not a prediction about a real "
        "supplier. A real assessment needs supplier contracts and inventory buffers from your systems.",
    ]


def h_globe(p: Parsed, c) -> list[str]:
    focus = p.focus or {}
    sites = focus.get("sites") or []
    text = p.question.lower()
    region = next((r for r in REGIONS if re.search(rf"\b{r}\b", text)), None)
    if region and sites:
        la0, la1, lo0, lo1 = REGIONS[region]
        sites = [s["id"] for s in _sites(sites) if la0 <= s["lat"] <= la1 and lo0 <= s["lon"] <= lo1]
        c.focus = {**focus, "sites": sites}
    if not sites:
        msg = "None of the sites in focus are in that region." if region else "Ask about suppliers or a site first."
        return [msg]
    rows = _sites(sites)
    c.ui_actions.append(
        {
            "type": "open_globe",
            "label": f"Open {len(rows)} site(s) on the globe",
            "sites": sites,
            "geo": {"country": rows[0]["country"], "node": rows[0]["id"]},
        }
    )
    c.visuals.append(
        {
            "kind": "table",
            "title": "Sites in focus",
            "provenance": "synthetic",
            "columns": ["Site", "Country", "Tier"],
            "rows": [[r["name"].replace("Synthetic ", ""), r["country_name"], r["tier"]] for r in rows],
        }
    )
    note = f" (filtered to {region.title()} by approximate latitude/longitude)" if region else ""
    return [f"Showing {len(rows)} site(s) on the globe{note}: " + ", ".join(r["country_name"] for r in rows) + "."]


def h_compare(p: Parsed, c) -> list[str]:
    from app import privacy

    sites = (p.focus or {}).get("sites") or []
    if len(sites) < 2:
        return ["Ask about suppliers first (for example “Which suppliers need attention?”), then I can compare them."]
    recs = {r["id"]: r for r in privacy.suppliers(_principal(p), "llm")[0]}
    pair = [recs[s] for s in sites[:2] if s in recs]
    if len(pair) < 2:
        return ["I can only compare suppliers you are allowed to see; fewer than two are available."]
    for metric, unit in (("quality_pass_pct", "%"), ("on_time_pct", "%"), ("open_incidents", "incidents")):
        c.visuals.append(
            {
                "kind": "bar",
                "title": metric.replace("_", " ").replace("pct", "(%)").capitalize(),
                "unit": unit,
                "provenance": "synthetic",
                "items": [
                    {"label": r["name"].replace("Synthetic supplier ", ""), "value": r[metric] or 0} for r in pair
                ],
            }
        )
    c.focus = {"kind": "suppliers", "sites": [r["id"] for r in pair]}
    a, b = pair
    cite = c.cite(_src("data", "Supplier scorecard (policy-filtered)", "ent_suppliers", "two suppliers compared"))
    return [
        f"**{a['name']} vs {b['name']}** {cite}: quality pass {a['quality_pass_pct']}% vs {b['quality_pass_pct']}%, "
        f"on time {a['on_time_pct']}% vs {b['on_time_pct']}%, incidents {a['open_incidents']} vs "
        f"{b['open_incidents']}; spend bands {a['annual_spend_cents']} vs {b['annual_spend_cents']}."
    ]


def h_impact(p: Parsed, c) -> list[str]:
    from app import geo

    sites = (p.focus or {}).get("sites") or []
    if not sites:
        return ["Tell me which supplier or site first (for example “What if the first supplier shuts down?”)."]
    t = geo.trace(sites[0])
    fac = [d for d in t["downstream"] if d["tier"] == "factory"]
    c.visuals.append(
        {
            "kind": "table",
            "title": "Factories downstream",
            "provenance": "synthetic",
            "columns": ["Factory", "Country", "Revenue dependent (USD M)"],
            "rows": [
                [f["name"].replace("Synthetic ", ""), f["country_name"], round(f["revenue_dependent"] / 1e6, 1)]
                for f in fac
            ],
        }
    )
    c.ui_actions.append(
        {
            "type": "open_globe",
            "label": "Highlight on the globe",
            "sites": [f["id"] for f in fac][:40],
            "geo": {"node": sites[0]},
        }
    )
    c.focus = {"kind": "factories", "sites": [f["id"] for f in fac]}
    return [
        f"{len(fac)} factory(ies) are downstream of {t['node']['name']} in the synthetic network: "
        + ", ".join(f["name"].replace("Synthetic ", "") for f in fac)
        + ". Supported relationships only — "
        "the network has no real bills of materials."
    ]


def h_plan(p: Parsed, c) -> list[str]:
    from app import pulse

    prios = pulse.priorities(p.username)[:4]
    steps = [
        {
            "step": x["next_step"],
            "owner": x["owner"][:120],
            "approval": "Approval by the accountable owner in the workflow screens",
            "evidence": f"{x['title'][:150]} ({x['provenance']})",
        }
        for x in prios
    ]
    if (p.focus or {}).get("kind") == "scenario":
        steps.insert(
            0,
            {
                "step": "Confirm alternative supply for the disrupted supplier and check safety stock",
                "owner": "Supply-chain manager",
                "approval": "Procurement approval required",
                "evidence": "Modelled disruption scenario (synthetic)",
            },
        )
    c.visuals.append(
        {
            "kind": "plan",
            "title": "Proposed action plan (for review)",
            "provenance": "mixed",
            "steps": steps,
            "assumptions": [
                "Owners are inferred from responsibilities, not named people.",
                "Nothing in this plan has been executed.",
            ],
        }
    )
    c.ui_actions.append({"type": "download", "label": "Export this as a PDF", "url": "/api/exports/decisions.pdf"})
    return [
        "Here is a reviewable action plan built from the current priorities. Each step names its evidence and the "
        "approval it needs; I have not executed anything. Record decisions on My Priorities to track outcomes."
    ]


def h_losses(p: Parsed, c) -> list[str]:
    from app.enterprise import queries as q

    risk = q.campaign_stock_risk()
    price = {r["sku"]: r["price_cents"] for r in q.products().values()}
    lost = sum(x["shortfall_units"] * price.get(x["sku"], 0) for x in risk["lines"])
    low = [a for a in q.inventory_status()["alerts"] if a["status"] == "critical"]
    c.visuals.append(
        {
            "kind": "waterfall",
            "title": "Where money is at risk (measurable parts only)",
            "unit": "CAD",
            "provenance": "synthetic",
            "steps": [{"label": "Campaign stockout (list price)", "value": round(lost / 100)}],
            "missing": ["Spoilage / expiry", "Shrink", "Overstock carrying cost", "Cold-chain losses"],
        }
    )
    cite = c.cite(_src("data", "Campaign stock-risk projection", "ent_stock + ent_sales_weekly", "synthetic"))
    return [
        f"**Measurable today** {cite}: the weekend campaign could lose about CAD {lost / 100:,.0f} of sales at list "
        f"price through stockouts, and {len(low)} stock line(s) are below their reorder point.",
        "**Not measurable yet:** spoilage, expiry, shrink, overstock and cold-chain losses — there is no batch-expiry, "
        "waste-weighing or temperature data connected. I show them as gaps rather than zero. Connecting the "
        "weighing scales and storage sensors (Connect Your Enterprise) would make them answerable.",
    ]


def h_facilities(p: Parsed, c) -> list[str]:
    from app import geo
    from app.enterprise import queries as q

    inv = q.inventory_status()
    dcs: dict[str, list[float]] = {}
    for a in inv["alerts"]:
        dcs.setdefault(a["warehouse_name"], []).append(a["days_of_cover"])
    inc: dict[str, int] = {}
    for i in geo.network()["incidents"]:
        inc[i["node_id"]] = inc.get(i["node_id"], 0) + 1
    fac = [n for n in geo.network()["nodes"] if n["tier"] == "factory"]
    worst = sorted(fac, key=lambda n: (-inc.get(n["id"], 0), n["performance"]["quality_pass_pct"]))[:6]
    c.visuals.append(
        {
            "kind": "bar",
            "title": "Factories by quality incidents (365 days)",
            "unit": "incidents",
            "provenance": "synthetic",
            "items": [
                {
                    "label": n["name"].replace("Synthetic factory ", ""),
                    "value": inc.get(n["id"], 0),
                    "note": f"quality pass {n['performance']['quality_pass_pct']}%",
                }
                for n in worst
            ],
        }
    )
    c.visuals.append(
        {
            "kind": "bar",
            "title": "Distribution centres — lowest days of cover",
            "unit": "days",
            "provenance": "synthetic",
            "items": [{"label": k, "value": min(v)} for k, v in dcs.items()],
        }
    )
    c.focus = {"kind": "factories", "sites": [n["id"] for n in worst]}
    cite = c.cite(_src("data", "Synthetic network factories + inventory", "geo + ent_stock", "synthetic"))
    return [
        f"**Underperforming sites** {cite}: factories ranked by quality incidents, and distribution centres by the "
        "lowest days of cover. Throughput, downtime and OEE are not available — they would come from Databricks "
        "(factory_performance query) once configured. I don't infer them."
    ]
