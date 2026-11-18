"""Enterprise Pulse: what changed, why it matters, what to do next — from existing records only.

Everything here is *derived*: it reads the enterprise dataset (synthetic, labelled), this app's
operational records (inspections, incidents, deployments, agent runs, model calls), the modelled
supply-chain simulation and the user's own continuity records (visits, decisions, investigations).
Nothing is invented: when a source has no data, the item says so. Every item carries
``provenance`` (verified | operational_record | modeled | synthetic) and ``as_of``.

Continuity records (decision journal, investigations) are the user's own notes inside Flo & Jerry.
Recording a decision does not execute anything in an enterprise system, and the UI says so.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from app.db import new_id, now_iso, rows
from app.memory.store import get_store

LENSES = {
    "cto": "CTO", "executive": "CEO / executive", "factory": "Factory manager", "quality": "Quality inspector",
    "supply": "Supply-chain manager", "sales": "Sales manager", "admin": "Administrator",
}
# A lens only changes what is shown first. Permissions always come from the account's server-side role.
DEFAULT_LENS = {"engineer": "cto", "release_approver": "admin", "product_owner": "factory",
                "marketing": "sales", "viewer": "executive"}
PROVENANCE = {"verified": "Verified enterprise data", "operational_record": "Operational record (this app)",
              "modeled": "Modelled scenario", "synthetic": "Synthetic demonstration data"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="milliseconds")


def _money(cents: float) -> str:
    v = cents / 100
    return f"CAD {v / 1e6:,.2f}M" if v >= 1e6 else f"CAD {v:,.0f}"


# --- user state -------------------------------------------------------------------------

def state(username: str, role: str) -> dict:
    found = get_store().query("SELECT * FROM user_state WHERE username = ?", (username,))
    s = found[0] if found else {}
    lens = s.get("lens") or DEFAULT_LENS.get(role, "cto")
    return {"lens": lens, "lens_label": LENSES[lens], "lenses": LENSES, "last_seen_at": s.get("last_seen_at"),
            "prev_seen_at": s.get("prev_seen_at"), "role": role,
            "note": "Your workspace lens changes what is shown first. Permissions come from your account role."}


def set_lens(username: str, lens: str) -> None:
    if lens not in LENSES:
        raise ValueError(f"lens must be one of {', '.join(LENSES)}")
    get_store().write([("INSERT INTO user_state (username, lens, updated_at) VALUES (?, ?, ?) "
                        "ON CONFLICT(username) DO UPDATE SET lens = excluded.lens, updated_at = excluded.updated_at",
                        (username, lens, now_iso()))])


def mark_visit(username: str) -> None:
    """Record a visit: the previous 'last seen' becomes the baseline for 'Since your last visit'."""
    get_store().write([("INSERT INTO user_state (username, last_seen_at, updated_at) VALUES (?, ?, ?) "
                        "ON CONFLICT(username) DO UPDATE SET prev_seen_at = user_state.last_seen_at, "
                        "last_seen_at = excluded.last_seen_at, updated_at = excluded.updated_at",
                        (username, now_iso(), now_iso()))])


# --- measurements -----------------------------------------------------------------------

def _enterprise() -> dict:
    from app.enterprise import queries

    return queries.executive_overview()


def _quality(username: str) -> dict:
    from app import quality

    try:
        return quality.overview(username, days=30)
    except Exception:  # noqa: BLE001 - quality is optional context
        return {"totals": {"graded": 0, "Not Good": 0, "batches": 0}, "trend": []}


def _storefront() -> dict:
    from app.tools import deploy

    return {"health": deploy.health(timeout_s=1.0), "process": deploy.current_process()}


def _llm() -> dict:
    from app.llm import local

    return local.status() if not local._client else local._client.status(probe=False)


def _agent_runs_since(since: str) -> dict:
    r = get_store().query("SELECT COUNT(*) AS n, SUM(CASE WHEN status != 'ok' THEN 1 ELSE 0 END) AS failed "
                          "FROM agent_runs WHERE started_at >= ?", (since,))[0]
    return {"runs": r["n"] or 0, "failed": r["failed"] or 0}


def snapshot(username: str) -> dict:
    """Current values of the measures priorities and decisions are compared against."""
    e = _enterprise()
    q = _quality(username)
    t = q["totals"]
    return {
        "revenue_change_pct": e["sales"]["revenue_change_pct"],
        "critical_compliance": e["compliance"]["critical"],
        "critical_stock_alerts": sum(1 for a in e["inventory_alerts"] if a["status"] == "critical"),
        "high_campaign_risk": sum(1 for x in e["campaign_stock_risk"] if x["risk"] == "high"),
        "open_incidents": len(rows("SELECT id FROM incidents WHERE status != 'resolved'")),
        "not_good_pct_30d": round(100 * t["Not Good"] / t["graded"], 1) if t.get("graded") else None,
        "taken_at": now_iso(),
    }


# --- priorities -------------------------------------------------------------------------

def priorities(username: str) -> list[dict]:
    e = _enterprise()
    week = e["sales"]["current_weeks"][-1] if e["sales"].get("current_weeks") else None
    prods = {p["sku"]: p for p in rows("SELECT sku, price_cents FROM ent_products")}
    out: list[dict] = []

    for x in e["campaign_stock_risk"]:
        if x["risk"] != "high":
            continue
        at_risk = x["shortfall_units"] * prods.get(x["sku"], {}).get("price_cents", 0)
        out.append({
            "id": f"PRI-STOCK-{x['sku']}", "severity": "high", "score": 90,
            "title": f"{x['name']} may run out before the Ontario weekend campaign",
            "why": (f"Forecast weekend demand is {x['weekend_forecast_units']:,} units; projected stock at the "
                    f"start is "
                    f"{x['projected_at_start']:,}. Shortfall ≈ {x['shortfall_units']:,} units "
                    f"(≈ {_money(at_risk)} of campaign sales at list price)."),
            "areas": ["Supply chain", "Sales", "Marketing"],
            "evidence": [{"label": "Campaign stock-risk projection",
                          "ref": "ent_stock + ent_sales_weekly + ent_inbound",
                          "provenance": "synthetic", "as_of": week}],
            "owner": "Supply-chain manager (by responsibility; no named owner in the data)",
            "next_step": "Expedite the next inbound purchase order or transfer stock from another distribution centre.",
            "jerry_question": "Is there enough apple stock for the Ontario weekend campaign?",
            "link": "/inventory", "metric": "high_campaign_risk", "provenance": "synthetic", "as_of": week,
        })

    for i in e["compliance"]["issues"]:
        if i["severity"] != "critical":
            continue
        out.append({
            "id": f"PRI-COMP-{i['sku']}-{i['channel']}", "severity": "high", "score": 85,
            "title": f"{i['name']} listing on {i['channel']} has a critical compliance issue",
            "why": f"{i['detail'].rstrip('.')}. Selling with an incorrect allergen or label statement is a "
                   "food-safety risk.",
            "areas": ["Compliance & food safety", "Sales"],
            "evidence": [{"label": f"Rule {i['rule']}: record {i['record_version']} vs listing {i['listing_version']}",
                          "ref": "ent_product_records + ent_listings", "provenance": "synthetic", "as_of": week}],
            "owner": "Regulatory affairs (by responsibility)",
            "next_step": "Correct the channel listing to match the approved product record, then re-check.",
            "jerry_question": "Which listings have allergen issues?",
            "link": "/compliance", "metric": "critical_compliance", "provenance": "synthetic", "as_of": week,
        })

    for inc in rows("SELECT id, title, status, opened_at FROM incidents WHERE status != 'resolved' ORDER BY opened_at"):
        out.append({
            "id": f"PRI-INC-{inc['id']}", "severity": "high", "score": 88,
            "title": f"Open incident: {inc['title']}",
            "why": "The live demo storefront had a production incident that is not resolved yet.",
            "areas": ["Technology", "Online sales"],
            "evidence": [{"label": f"Incident {inc['id']} ({inc['status']})", "ref": f"incidents:{inc['id']}",
                          "provenance": "operational_record", "as_of": inc["opened_at"]}],
            "owner": "Engineering on-call (engineer role)",
            "next_step": "Review the incident evidence and approve the repair release.",
            "jerry_question": f"What happened in incident {inc['id']}?",
            "link": "/incidents", "metric": "open_incidents", "provenance": "operational_record",
            "as_of": inc["opened_at"],
        })

    critical_covered = {x["sku"] for x in e["campaign_stock_risk"] if x["risk"] == "high"}
    crit = [a for a in e["inventory_alerts"] if a["status"] == "critical" and a["sku"] not in critical_covered]
    if crit:
        a = min(crit, key=lambda a: a["days_of_cover"])
        out.append({
            "id": f"PRI-INV-{a['warehouse']}-{a['sku']}", "severity": "medium", "score": 60,
            "title": f"{a['name']} at {a['warehouse_name']}: {a['days_of_cover']} days of cover",
            "why": f"Below the reorder point; lead time is {a['lead_time_days']} days."
                   + (f" {len(crit) - 1} more critical stock line(s)." if len(crit) > 1 else ""),
            "areas": ["Supply chain"],
            "evidence": [{"label": "Inventory status", "ref": "ent_stock", "provenance": "synthetic", "as_of": week}],
            "owner": "Supply-chain manager (by responsibility)",
            "next_step": "Confirm the inbound purchase order and its arrival date.",
            "jerry_question": "Which products are running low?",
            "link": "/inventory", "metric": "critical_stock_alerts", "provenance": "synthetic", "as_of": week,
        })

    q = _quality(username)
    t = q["totals"]
    if t.get("graded") and t["Not Good"] / t["graded"] >= 0.2:
        pct = round(100 * t["Not Good"] / t["graded"], 1)
        out.append({
            "id": "PRI-QUAL-30D", "severity": "medium", "score": 65,
            "title": f"{pct}% of inspected potatoes graded Not Good in the last 30 days",
            "why": (f"{t['Not Good']} of {t['graded']} graded potatoes across {t['batches']} batch(es). "
                    "Grades come from "
                    "classical image rules (not a trained model) and need inspector review before rejecting lots."),
            "areas": ["Quality", "Supply chain"],
            "evidence": [{"label": "Your inspection batches", "ref": "inspection_batches", "provenance":
                          "operational_record", "as_of": q["trend"][-1]["created_at"] if q["trend"] else None}],
            "owner": "Quality inspector (approval required for rejections)",
            "next_step": "Review the reject candidates in Quality Intelligence and confirm or correct the grades.",
            "jerry_question": "Which potatoes were rejected and why?",
            "link": "/quality-intel", "metric": "not_good_pct_30d", "provenance": "operational_record",
            "as_of": q["trend"][-1]["created_at"] if q["trend"] else None,
        })

    rc = e["sales"]["revenue_change_pct"]
    if rc is not None and rc < -1:
        out.append({
            "id": "PRI-SALES-4W", "severity": "medium", "score": 50,
            "title": f"Revenue is down {abs(rc)}% over the last 4 weeks",
            "why": f"Last 4 weeks vs the 4 weeks before; units {e['sales']['units_change_pct']}%. "
                   "A before/after comparison, not a causal analysis.",
            "areas": ["Sales"],
            "evidence": [{"label": "Weekly sales history", "ref": "ent_sales_weekly", "provenance": "synthetic",
                          "as_of": week}],
            "owner": "Sales manager (by responsibility)",
            "next_step": "Ask Jerry which regions and products drove the decline.",
            "jerry_question": "How did our sales do in the last 4 weeks?",
            "link": "/sales", "metric": "revenue_change_pct", "provenance": "synthetic", "as_of": week,
        })

    try:
        from app import geo

        r = geo.simulate()["horizons"][0]
        cur = geo.scenario()["currency"]
        ex = r["exposure"]
        out.append({
            "id": "PRI-GEO-30D", "severity": "low", "score": 30,
            "title": f"Modelled supply-chain exposure, next 30 days: {cur} {ex['p50'] / 1e6:,.1f}M "
                     f"(range {ex['p10'] / 1e6:,.1f}–{ex['p90'] / 1e6:,.1f}M)",
            "why": "From the synthetic 161-country scenario: a modelled range, not a forecast of real events.",
            "areas": ["Global network", "Finance"],
            "evidence": [{"label": "Monte Carlo risk simulation (P10–P90)", "ref": "geo_risk_simulation",
                          "provenance": "modeled", "as_of": geo.AS_OF.isoformat()}],
            "owner": "Supply-chain manager (by responsibility)",
            "next_step": "Open the Global Network to see which countries and sites drive the exposure.",
            "jerry_question": "OriginTrace: summarise global supply chain risk and exposure",
            "link": "/network", "metric": None, "provenance": "modeled", "as_of": geo.AS_OF.isoformat(),
        })
    except Exception:  # noqa: BLE001 - the scenario is optional
        pass

    out.sort(key=lambda p: -p["score"])
    return out


# --- enterprise health ------------------------------------------------------------------

def health(username: str) -> list[dict]:
    e = _enterprise()
    week = e["sales"]["current_weeks"][-1] if e["sales"].get("current_weeks") else None
    rc = e["sales"]["revenue_change_pct"]
    q = _quality(username)["totals"]
    sf = _storefront()
    llm = _llm()
    seven = _iso(_now() - timedelta(days=7))
    runs = _agent_runs_since(seven)
    high_risk = sum(1 for x in e["campaign_stock_risk"] if x["risk"] == "high")
    crit_stock = sum(1 for a in e["inventory_alerts"] if a["status"] == "critical")
    open_inc = len(rows("SELECT id FROM incidents WHERE status != 'resolved'"))
    ng = round(100 * q["Not Good"] / q["graded"], 1) if q.get("graded") else None
    reach = sf["health"].get("reachable")
    return [
        {"key": "business", "label": "Business performance", "question": "Is revenue growing?",
         "value": f"{rc:+.1f}% revenue" if rc is not None else "No data",
         "status": "unknown" if rc is None else "good" if rc >= 0 else "watch",
         "explanation": f"Last 4 weeks vs the 4 weeks before "
                        f"({_money(e['sales']['revenue_cents'])} in the last 4 weeks).",
         "provenance": "synthetic", "as_of": week, "link": "/sales"},
        {"key": "supply", "label": "Supply-chain exposure", "question": "Can we meet demand?",
         "value": f"{high_risk} campaign risk · {crit_stock} critical stock",
         "status": "attention" if high_risk else "watch" if crit_stock else "good",
         "explanation": "Products that may run out before a campaign, and stock lines below their reorder point.",
         "provenance": "synthetic", "as_of": week, "link": "/inventory"},
        {"key": "quality", "label": "Quality & compliance", "question": "Is what we sell safe and to spec?",
         "value": f"{e['compliance']['critical']} critical listing issue(s)"
                  + (f" · {ng}% Not Good (30 d)" if ng is not None else ""),
         "status": "attention" if e["compliance"]["critical"] else "watch" if ng and ng >= 20 else "good",
         "explanation": "Listing checks against approved product records"
                        + ("; potato grades from your inspections (rules, not a trained model)." if ng is not None
                           else "; no inspections in the last 30 days."),
         "provenance": "synthetic" if ng is None else "operational_record", "as_of": week, "link": "/compliance"},
        {"key": "technology", "label": "Technology reliability", "question": "Are our systems running reliably?",
         "value": ("Storefront up" if reach else "Storefront down") + f" · {open_inc} open incident(s)",
         "status": "attention" if open_inc or not reach else "watch" if runs["failed"] else "good",
         "explanation": f"Health check of the live demo storefront; {runs['runs']} agent run(s) in 7 days, "
                        f"{runs['failed']} not ok.",
         "provenance": "operational_record", "as_of": now_iso(), "link": "/technology"},
        {"key": "ai", "label": "AI service health", "question": "Is Jerry available and trustworthy?",
         "value": ("Local model connected" if llm.get("configured") and llm.get("reachable", True)
                   else "Rules-based answers (local model not configured)" if not llm.get("configured")
                   else "Local model unreachable — rules-based answers"),
         "status": "good" if llm.get("configured") and llm.get("reachable", True) else "watch",
         "explanation": "Jerry always answers from cited, read-only queries; the local model only rewrites them "
                        "when configured. No cloud AI is used.",
         "provenance": "operational_record", "as_of": now_iso(), "link": "/technology"},
    ]


# --- since last visit -------------------------------------------------------------------

def since_last_visit(username: str) -> dict:
    s = get_store().query("SELECT last_seen_at, prev_seen_at FROM user_state WHERE username = ?", (username,))
    since = s[0]["last_seen_at"] if s and s[0]["last_seen_at"] else None
    if not since:
        return {"since": None, "first_visit": True, "changes": [],
                "message": "Welcome. This is your first visit, so everything below is new."}
    store = get_store()
    changes = []

    def add(kind: str, text: str, link: str, provenance: str, n: int) -> None:
        if n:
            changes.append({"kind": kind, "text": text, "link": link, "provenance": provenance, "count": n})

    opened = rows("SELECT id, title FROM incidents WHERE opened_at >= ?", (since,))
    add("incident", f"{len(opened)} incident(s) opened: " + ", ".join(i["title"] for i in opened[:2]), "/incidents",
        "operational_record", len(opened))
    resolved = rows("SELECT id FROM incidents WHERE resolved_at >= ?", (since,))
    add("incident", f"{len(resolved)} incident(s) resolved", "/incidents", "operational_record", len(resolved))
    deps = rows("SELECT status FROM deployments WHERE started_at >= ?", (since,))
    add("deployment", f"{len(deps)} deployment(s) to the demo storefront "
        f"({sum(1 for d in deps if d['status'] == 'healthy')} healthy)", "/releases", "operational_record", len(deps))
    insp = store.query("SELECT COUNT(*) AS n FROM inspection_batches WHERE username = ? AND created_at >= ?",
                       (username, since))[0]["n"]
    add("inspection", f"{insp} new inspection batch(es) of yours", "/quality-intel", "operational_record", insp)
    runs = _agent_runs_since(since)
    add("agents", f"{runs['runs']} agent run(s)" + (f", {runs['failed']} not ok" if runs["failed"] else ""),
        "/agents", "operational_record", runs["runs"])
    fails = store.query("SELECT COUNT(*) AS n FROM llm_usage WHERE ts >= ? AND status != 'ok'", (since,))[0]["n"]
    add("ai", f"{fails} local-model call(s) failed", "/observability", "operational_record", fails)
    due = store.query("SELECT id, title FROM decisions WHERE username = ? AND status = 'open' AND follow_up_on <= ?",
                      (username, date.today().isoformat()))
    add("decision", f"{len(due)} decision follow-up(s) due: " + ", ".join(d["title"] for d in due[:2]),
        "/priorities", "operational_record", len(due))
    return {"since": since, "first_visit": False, "changes": changes,
            "message": None if changes else "Nothing meaningful has changed since your last visit."}


# --- briefing ---------------------------------------------------------------------------

def briefing(username: str, prios: list[dict], hlth: list[dict], since: dict) -> list[dict]:
    lines = []
    if since["first_visit"]:
        lines.append({"text": "First visit: here is the current state of the enterprise.", "provenance": None})
    elif since["changes"]:
        lines.append({"text": "Since your last visit: " + "; ".join(c["text"] for c in since["changes"][:3]) + ".",
                      "provenance": "operational_record"})
    else:
        lines.append({"text": "Nothing meaningful has changed since your last visit.", "provenance": None})
    top = [p for p in prios if p["severity"] == "high"]
    if top:
        lines.append({"text": f"{len(top)} high-priority item(s). Most urgent: {top[0]['title']}.",
                      "provenance": top[0]["provenance"]})
    watch = [h for h in hlth if h["status"] in ("watch", "attention")]
    if watch:
        lines.append({"text": "Needs attention: " + ", ".join(f"{h['label'].lower()} ({h['value']})" for h in watch[:3])
                      + ".", "provenance": "mixed"})
    open_d = get_store().query("SELECT COUNT(*) AS n FROM decisions WHERE username = ? AND status = 'open'",
                               (username,))[0]["n"]
    done = get_store().query("SELECT title, outcome FROM decisions WHERE username = ? AND status = 'done' "
                             "ORDER BY outcome_recorded_at DESC LIMIT 1", (username,))
    if open_d:
        lines.append({"text": f"You have {open_d} open decision(s) in your journal.",
                      "provenance": "operational_record"})
    if done:
        lines.append({"text": f"Last recorded outcome: “{done[0]['title']}” — {done[0]['outcome']}.",
                      "provenance": "operational_record"})
    return lines


def pulse(username: str, role: str, mark: bool = True) -> dict:
    st = state(username, role)
    since = since_last_visit(username)
    prios = priorities(username)
    hlth = health(username)
    out = {"state": st, "generated_at": now_iso(), "since": since, "priorities": prios, "health": hlth,
           "briefing": briefing(username, prios, hlth, since), "provenance_labels": PROVENANCE,
           "data_status": "Synthetic enterprise dataset + this app's operational records. No verified enterprise "
                          "data source is connected."}
    if mark:
        mark_visit(username)
    return out


# --- decision journal & investigations ----------------------------------------------------

def _decision_row(d: dict, current: dict | None = None) -> dict:
    d = {**d, "evidence": json.loads(d.pop("evidence_json") or "[]"),
         "baseline": json.loads(d.pop("baseline_json") or "{}")}
    if current is not None and d["baseline"]:
        d["comparison"] = [{"metric": k, "then": v, "now": current.get(k)} for k, v in d["baseline"].items()
                           if k != "taken_at" and v != current.get(k)]
    d["note"] = "Recorded in Flo & Jerry only. No action was executed in any enterprise system."
    return d


def list_decisions(username: str) -> list[dict]:
    current = snapshot(username)
    return [_decision_row(d, current) for d in get_store().query(
        "SELECT * FROM decisions WHERE username = ? ORDER BY created_at DESC", (username,))]


def add_decision(username: str, body: dict) -> dict:
    did = new_id("DEC")
    prio = next((p for p in priorities(username) if p["id"] == body.get("priority_id")), None)
    evidence = body.get("evidence") or (prio["evidence"] if prio else [])
    get_store().write([(
        "INSERT INTO decisions (id, username, title, problem, evidence_json, recommendation, decision, owner, "
        "priority_id, created_at, follow_up_on, status, baseline_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
        "'open', ?)",
        (did, username, body["title"][:160], (body.get("problem") or (prio["why"] if prio else ""))[:1000],
         json.dumps(evidence), (body.get("recommendation") or (prio["next_step"] if prio else ""))[:1000],
         body["decision"][:1000], (body.get("owner") or (prio["owner"] if prio else ""))[:120],
         body.get("priority_id"), now_iso(), body.get("follow_up_on"), json.dumps(snapshot(username))))])
    return next(d for d in list_decisions(username) if d["id"] == did)


def update_decision(username: str, decision_id: str, body: dict) -> dict:
    found = get_store().query("SELECT id FROM decisions WHERE id = ? AND username = ?", (decision_id, username))
    if not found:
        raise KeyError(decision_id)
    sets, params = [], []
    if body.get("outcome") is not None:
        sets += ["outcome = ?", "outcome_recorded_at = ?"]
        params += [body["outcome"][:1000], now_iso()]
    if body.get("status") in ("open", "done", "dropped"):
        sets.append("status = ?")
        params.append(body["status"])
    if "follow_up_on" in body:
        sets.append("follow_up_on = ?")
        params.append(body["follow_up_on"])
    if sets:
        get_store().write([(f"UPDATE decisions SET {', '.join(sets)} WHERE id = ? AND username = ?",
                            (*params, decision_id, username))])
    return next(d for d in list_decisions(username) if d["id"] == decision_id)


def list_investigations(username: str) -> list[dict]:
    current = snapshot(username)
    prios = {p["id"]: p for p in priorities(username)}
    out = []
    for r in get_store().query("SELECT * FROM investigations WHERE username = ? ORDER BY updated_at DESC", (username,)):
        snap = json.loads(r.pop("snapshot_json") or "{}")
        r["geo"] = json.loads(r.pop("geo_json") or "null")
        p = prios.get(r["priority_id"])
        r["still_open"] = p is not None if r["priority_id"] else None
        r["changes"] = [{"metric": k, "then": v, "now": current.get(k)} for k, v in snap.items()
                        if k != "taken_at" and v != current.get(k)]
        r["snapshot_taken_at"] = snap.get("taken_at")
        out.append(r)
    return out


def add_investigation(username: str, body: dict) -> dict:
    iid = new_id("INV")
    ts = now_iso()
    get_store().write([(
        "INSERT INTO investigations (id, username, title, priority_id, geo_json, notes, status, created_at, "
        "updated_at, snapshot_json) VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?, ?)",
        (iid, username, body["title"][:160], body.get("priority_id"), json.dumps(body.get("geo")),
         (body.get("notes") or "")[:4000], ts, ts, json.dumps(snapshot(username))))])
    return next(i for i in list_investigations(username) if i["id"] == iid)


def update_investigation(username: str, inv_id: str, body: dict) -> dict:
    if not get_store().query("SELECT id FROM investigations WHERE id = ? AND username = ?", (inv_id, username)):
        raise KeyError(inv_id)
    sets, params = ["updated_at = ?"], [now_iso()]
    if body.get("notes") is not None:
        sets.append("notes = ?")
        params.append(body["notes"][:4000])
    if body.get("status") in ("open", "closed"):
        sets.append("status = ?")
        params.append(body["status"])
    get_store().write([(f"UPDATE investigations SET {', '.join(sets)} WHERE id = ? AND username = ?",
                        (*params, inv_id, username))])
    return next(i for i in list_investigations(username) if i["id"] == inv_id)


def add_feedback(username: str, body: dict) -> None:
    get_store().write([("INSERT INTO answer_feedback (username, conversation_id, agent_run_id, helpful, comment, "
                        "created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (username, body.get("conversation_id"), body.get("agent_run_id"), int(bool(body["helpful"])),
                         (body.get("comment") or "")[:1000] or None, now_iso()))])


# --- technology workspace ---------------------------------------------------------------

def technology(username: str) -> list[dict]:
    from app import observability, resources

    sf = _storefront()
    llm = _llm()
    seven = _iso(_now() - timedelta(days=7))
    runs = _agent_runs_since(seven)
    usage = observability.token_usage(days=7)
    fb = get_store().query("SELECT COUNT(*) AS n, SUM(helpful) AS up FROM answer_feedback WHERE created_at >= ?",
                           (seven,))[0]
    r = resources.snapshot()
    open_inc = len(rows("SELECT id FROM incidents WHERE status != 'resolved'"))
    t = usage["totals"]
    return [
        {"key": "reliable", "question": "Are our systems running reliably?",
         "answer": ("Yes — the demo storefront is up" if sf["health"].get("reachable") else "No — the demo storefront "
                    "is not answering")
                   + (f", with {open_inc} open incident(s)." if open_inc else ", no open incidents."),
         "status": "good" if sf["health"].get("reachable") and not open_inc else "attention",
         "diagnostics": {"storefront_health": sf["health"], "cpu_percent": r["cpu_percent"],
                         "ram_percent": r["ram_percent"], "backend_rss_mb": r["process"]["rss_mb"]},
         "link": "/observability", "provenance": "operational_record"},
        {"key": "jerry", "question": "Is Jerry available?",
         "answer": "Yes. Jerry answers from cited read-only queries" + (
             " and the local model is connected." if llm.get("configured") and llm.get("reachable", True)
             else "; the local model is not configured, so answers are rules-based (still cited)."),
         "status": "good" if llm.get("configured") else "watch",
         "diagnostics": {k: llm.get(k) for k in ("configured", "reachable", "model", "queue_depth", "in_flight")},
         "link": "/copilot", "provenance": "operational_record"},
        {"key": "integrations", "question": "Are our integrations healthy?",
         "answer": "Connected: inspection photos, inspector corrections, conversation memory, the demo storefront and "
                   "inventory simulator. Not connected yet: ERP, storage sensors, weather, weighing scales, conveyor "
                   "video, shipment tracking.",
         "status": "watch", "diagnostics": None, "link": "/", "provenance": "operational_record"},
        {"key": "trust", "question": "Are our AI outputs trustworthy?",
         "answer": (f"{runs['runs']} agent run(s) in 7 days, {runs['failed']} not ok. "
                    + (f"{fb['n']} answer rating(s), {fb['up'] or 0} helpful." if fb["n"] else
                       "No answer ratings yet — rate Jerry's answers to build this signal.")
                    + " Potato grading is rule-based; real-photo accuracy has not been measured."),
         "status": "good" if not runs["failed"] else "watch",
         "diagnostics": {"agent_runs_7d": runs, "feedback_7d": fb}, "link": "/agents",
         "provenance": "operational_record"},
        {"key": "cost", "question": "What is our AI operating cost?",
         "answer": (f"{t['calls']} local-model call(s) in 7 days, {t['prompt_tokens'] + t['completion_tokens']:,} "
                    "tokens reported by the server. A local model has no per-token charge; hardware and power costs "
                    "are not measured here."),
         "status": "good", "diagnostics": usage["totals"], "link": "/observability",
         "provenance": "operational_record"},
    ]


# --- reports: weekly review and time machine ---------------------------------------------

def _count(sql: str, params: tuple, store: bool = False) -> int:
    r = get_store().query(sql, params) if store else rows(sql, params)
    return int(r[0]["n"] or 0) if r else 0


def weekly_review(username: str) -> dict:
    now = _now()
    a, b, c = _iso(now - timedelta(days=7)), _iso(now - timedelta(days=14)), _iso(now)

    def window(lo: str, hi: str) -> dict:
        return {
            "incidents_opened": _count("SELECT COUNT(*) AS n FROM incidents WHERE opened_at >= ? AND opened_at < ?",
                                       (lo, hi)),
            "incidents_resolved": _count("SELECT COUNT(*) AS n FROM incidents WHERE resolved_at >= ? AND "
                                         "resolved_at < ?", (lo, hi)),
            "deployments": _count("SELECT COUNT(*) AS n FROM deployments WHERE started_at >= ? AND started_at < ?",
                                  (lo, hi)),
            "agent_runs": _count("SELECT COUNT(*) AS n FROM agent_runs WHERE started_at >= ? AND started_at < ?",
                                 (lo, hi), True),
            "inspections": _count("SELECT COUNT(*) AS n FROM inspection_batches WHERE username = ? AND created_at >= ? "
                                  "AND created_at < ?", (username, lo, hi), True),
            "decisions_made": _count("SELECT COUNT(*) AS n FROM decisions WHERE username = ? AND created_at >= ? AND "
                                     "created_at < ?", (username, lo, hi), True),
            "outcomes_recorded": _count("SELECT COUNT(*) AS n FROM decisions WHERE username = ? AND "
                                        "outcome_recorded_at >= ? AND outcome_recorded_at < ?",
                                        (username, lo, hi), True),
            "model_calls": _count("SELECT COUNT(*) AS n FROM llm_usage WHERE ts >= ? AND ts < ?", (lo, hi), True),
        }
    e = _enterprise()
    trend = e["sales"]["trend"]
    biz = None
    if len(trend) >= 2:
        last, prev = trend[-1], trend[-2]
        biz = {"week": last["week_start"], "revenue": last["revenue"], "previous_week": prev["week_start"],
               "previous_revenue": prev["revenue"],
               "change_pct": round(100 * (last["revenue"] - prev["revenue"]) / prev["revenue"], 1) if prev["revenue"]
               else None, "provenance": "synthetic"}
    unresolved = [p for p in priorities(username) if p["severity"] == "high"]
    return {"this_week": window(a, c), "last_week": window(b, a), "business": biz,
            "unresolved": [{"id": p["id"], "title": p["title"], "provenance": p["provenance"]} for p in unresolved],
            "decisions": [d for d in list_decisions(username) if d["created_at"] >= a or d.get("outcome_recorded_at")
                          and d["outcome_recorded_at"] >= a],
            "note": "Operational counts come from this app's records; business figures are synthetic. Changes are "
                    "shown side by side; no causal claims are made."}


def history(username: str) -> dict:
    """Weekly series for the Enterprise Time Machine (only what the data supports)."""
    e = _enterprise()
    weeks = [{"week": w["week_start"], "revenue": w["revenue"], "units": w["units"]} for w in e["sales"]["trend"]]
    store = get_store()
    insp = store.query("SELECT substr(created_at, 1, 10) AS day, summary_json FROM inspection_batches WHERE "
                       "username = ? ORDER BY created_at", (username,))
    by_week: dict[str, dict] = {}
    for r in insp:
        d = date.fromisoformat(r["day"])
        wk = (d - timedelta(days=d.weekday())).isoformat()
        s = json.loads(r["summary_json"] or "{}")
        w = by_week.setdefault(wk, {"week": wk, "batches": 0, "graded": 0, "not_good": 0})
        w["batches"] += 1
        w["graded"] += s.get("graded") or 0
        w["not_good"] += (s.get("counts") or {}).get("Not Good", 0)
    return {"sales": {"series": weeks, "provenance": "synthetic"},
            "quality": {"series": sorted(by_week.values(), key=lambda w: w["week"]),
                        "provenance": "operational_record"},
            "note": "Sales history is the synthetic 16-week dataset; quality history is your own inspections. "
                    "Other domains have no stored history yet (see FLO_JERRY_3_IMPLEMENTATION.md)."}
