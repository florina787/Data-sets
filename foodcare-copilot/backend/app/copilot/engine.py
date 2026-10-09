"""Answer composition. Every number in an answer comes from a tool result and is cited.

DEMO mode composes the answer from templates over tool results (labelled
"Deterministic answer"). LIVE mode gives the same tool results to Claude, which
writes the prose; its citations are validated against the sources provided.
The copilot is read-only: it never performs workflow actions.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Callable

from pydantic import BaseModel, Field

from app.auth import User
from app.config import get_settings
from app.copilot.router import Parsed, parse
from app.db import kv_get, now_iso, row, rows, session
from app.enterprise import queries as q
from app.errors import PlatformError
from app.services import delivery, incidents
from app.tools.retrieval import get_index

ACTION_VERBS = ("approve", "deploy", "roll back", "rollback", "delete", "update", "change", "inject", "create",
                "cancel", "refund", "order", "set ", "clear the fault", "reset")
EXAMPLES = [
    "Give me a briefing",
    "How did our sales do in the last 4 weeks?",
    "Is there enough apple stock for the Ontario weekend campaign?",
    "Which products are running low in Vancouver?",
    "Which listings have allergen issues?",
    "How did past promotions perform?",
    "Why is the release blocked?",
    "What happened in the checkout incident?",
    "What does the returns policy say about partial returns?",
]


def money(cents: float | int | None) -> str:
    return "-" if cents is None else f"${cents / 100:,.0f}"


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:+.1f}%"


class Ctx:
    def __init__(self) -> None:
        self.sources: list[dict] = []
        self.tool_calls: list[dict] = []

    def call(self, tool: str, fn: Callable, **args):
        result = fn(**args)
        self.tool_calls.append({"tool": tool, "args": {k: v for k, v in args.items() if v not in (None, [], "")}})
        return result

    def cite(self, *sources: dict) -> str:
        marks = []
        for s in sources:
            key = (s["ref"], s.get("detail", ""))
            for existing in self.sources:
                if (existing["ref"], existing.get("detail", "")) == key:
                    marks.append(existing["id"])
                    break
            else:
                sid = f"S{len(self.sources) + 1}"
                self.sources.append({"id": sid, **s})
                marks.append(sid)
        return "".join(f"[{m}]" for m in marks)


# --- intent handlers -------------------------------------------------------------------

def h_sales(p: Parsed, c: Ctx) -> list[str]:
    s = c.call("sales_summary", q.sales_summary, window=p.weeks, province=p.provinces[0] if p.provinces else None,
               sku=p.skus[0] if p.skus else None, channel=p.channels[0] if p.channels else None)
    cite = c.cite(*s["sources"])
    out = [f"**Sales, {s['scope']}, last {s['window_weeks']} week(s)** ({s['current_weeks'][0]} to "
           f"{s['current_weeks'][1]}): revenue {money(s['revenue_cents'])} on {s['units']:,} units, "
           f"{pct(s['revenue_change_pct'])} revenue and {pct(s['units_change_pct'])} units against the previous "
           f"{s['window_weeks']} week(s) {cite}."]
    if not p.skus and s["by_sku"]:
        top = ", ".join(f"{x['name']} {money(x['revenue'])}" for x in s["by_sku"][:3])
        out.append(f"Top products by revenue: {top} {cite}.")
    if not p.provinces and s["by_province"]:
        top = ", ".join(f"{x['province']} {money(x['revenue'])}" for x in s["by_province"][:3])
        out.append(f"Top regions: {top} {cite}.")
    if s["by_channel"]:
        total = sum(x["revenue"] for x in s["by_channel"]) or 1
        mix = ", ".join(f"{x['channel']} {x['revenue'] / total * 100:.0f}%" for x in s["by_channel"])
        out.append(f"Channel mix (revenue): {mix} {cite}.")
    return out


def h_campaign(p: Parsed, c: Ctx) -> list[str]:
    out = []
    text = p.question.lower()
    current = any(w in text for w in ("ontario", "weekend", "buy 2", "buy two", "b2g1", "current", "live", "now"))
    if current:
        live = c.call("live_storefront_orders", q.live_storefront_orders)
        if live["available"] and live["orders"]:
            cite = c.cite(*live["sources"])
            out.append(f"**Ontario weekend campaign, live storefront so far:** {live['paid_orders']} paid order(s)"
                       f" from {live['customers']} customer(s), {live['units']} units including "
                       f"{live['free_units']} free unit(s), {live['redemptions']} committed redemption(s), "
                       f"{money(live['revenue_cents'])} "
                       f"order value, {money(live['refunded_cents'])} refunded {cite}. These are real orders on the "
                       "local demo storefront, mostly from demo traffic.")
        else:
            out.append("The Ontario weekend campaign has no orders on the live demo storefront yet. It starts "
                       "2026-10-31 (America/Toronto). Run the guided demo to deploy it and place orders.")
    perf = c.call("campaign_performance", q.campaign_performance)
    cite = c.cite(*perf["sources"])
    lines = [f"- {x['name']} ({x['region']}, {x['mechanic']}, {x['start']} to {x['end']}): units "
             f"{pct(x['unit_uplift_pct'])}, revenue {pct(x['revenue_change_pct'])} vs the 4 weeks before"
             for x in perf["campaigns"]]
    out.append(f"**Past promotions (measured uplift)** {cite}:\n" + "\n".join(lines))
    best = max(perf["campaigns"], key=lambda x: x["unit_uplift_pct"] or 0)
    weakest = min(perf["campaigns"], key=lambda x: x["revenue_change_pct"] or 0)
    out.append(f"{best['name']} had the strongest unit uplift. {weakest['name']} had the weakest revenue effect "
               f"({pct(weakest['revenue_change_pct'])}): its discount cost more than the extra volume earned. "
               "The uplift is a before/after comparison, not a controlled experiment.")
    return out


def h_campaign_risk(p: Parsed, c: Ctx) -> list[str]:
    r = c.call("campaign_stock_risk", q.campaign_stock_risk)
    cite = c.cite(*r["sources"])
    lines = []
    for x in r["lines"]:
        state = (f"stock runs out before the start, shortfall {x['shortfall_units']:,} units"
                 if x["stockout_before_start"] else f"{x['projected_at_start']:,} projected at start")
        nb = x["next_inbound"]
        nxt = f"; next inbound {nb['po']} ({nb['units']:,} units, ETA {nb['eta']})" if nb else ""
        lines.append(f"- {x['name']}: forecast {x['weekend_forecast_units']:,} units for the weekend, {state} "
                     f"→ **{x['risk']} risk**{nxt}")
    high = [x for x in r["lines"] if x["risk"] == "high"]
    out = [f"**Stock for the {r['campaign']['name']} at {r['warehouse']}** (starts in {r['days_to_start']} days) "
           f"{cite}:\n" + "\n".join(lines),
           "Assumptions: " + " ".join(r["assumptions"])]
    if high:
        out.append("Options to consider (decisions belong to supply planning and marketing): expedite "
                   f"{', '.join(x['next_inbound']['po'] for x in high if x['next_inbound']) or 'a purchase order'}, "
                   "transfer stock from another DC, or exclude the affected SKU from the free-unit choice. The "
                   "storefront already reserves stock at checkout, so orders cannot oversell.")
    return out


def h_inventory(p: Parsed, c: Ctx) -> list[str]:
    inv = c.call("inventory_status", q.inventory_status, warehouse=p.warehouses[0] if p.warehouses else None,
                 sku=p.skus[0] if p.skus else None)
    cite = c.cite(inv["sources"][0])
    items = inv["items"] if (p.skus or p.warehouses) else inv["alerts"]
    if not items:
        return [f"No stock alerts in the selected scope as of {inv['as_of']} {cite}."]
    def inbound(i: dict) -> str:
        return "; inbound " + ", ".join(f"{x['po']} {x['units']:,} ETA {x['eta']}" for x in i["inbound"]) \
            if i["inbound"] else ""

    lines = [f"- {i['name']} at {i['warehouse']}: {i['on_hand']:,} on hand, {i['days_of_cover']} days of cover "
             f"(lead time {i['lead_time_days']} d) → **{i['status']}**{inbound(i)}"
             for i in items[:8]]
    title = "Stock position" if (p.skus or p.warehouses) else "Stock alerts"
    out = [f"**{title}, as of {inv['as_of']}** {cite}:\n" + "\n".join(lines), f"Method: {inv['method']}."]
    if p.skus:
        alloc = {x["sku"]: x["stock"] for x in inv["ecommerce_allocation"]}
        if p.skus[0] in alloc:
            out.append(f"E-commerce allocation in the live inventory simulator: {alloc[p.skus[0]]} units "
                       f"{c.cite(inv['sources'][1])}.")
    return out


def h_compliance(p: Parsed, c: Ctx) -> list[str]:
    out = []
    sku = p.skus[0] if p.skus else None
    if sku and any(w in p.question.lower() for w in ("ingredient", "allergen", "contain")):
        rec = c.call("product_record", q.product_record, sku=sku)
        cite = c.cite(*rec["sources"])
        out.append(f"**{rec['name']}**, approved record v{rec['version']} ({rec['approved_by']},"
                   f" {rec['approved_at']}): "
                   f"ingredients {', '.join(rec['ingredients'])}; allergens "
                   f"{', '.join(rec['allergens']) or 'none declared'} {cite}.")
    comp = c.call("compliance_check", q.compliance_check, sku=sku, channel=p.channels[0] if p.channels else None)
    cite = c.cite(*comp["sources"])
    if not comp["issues"]:
        out.append(f"All {comp['listings_checked']} checked listing(s) match the approved records {cite}.")
        return out
    lines = [f"- **{i['severity']}**: {i['name']} on {i['channel']}: {i['detail']}" for i in comp["issues"]]
    out.append(f"**Listing compliance**: {comp['critical']} critical and {comp['warnings']} warning(s) across "
               f"{comp['listings_checked']} listing(s) {cite}:\n" + "\n".join(lines))
    if comp["critical"]:
        out.append("A missing allergen statement is a consumer-safety issue. The usual next step is to correct the "
                   "listing feed and notify Regulatory Affairs; the copilot cannot change listings itself.")
    return out


def h_delivery(p: Parsed, c: Ctx) -> list[str]:
    run = row("SELECT * FROM runs WHERE id = ?", (p.run_id,)) if p.run_id else \
        row("SELECT * FROM runs ORDER BY created_at DESC LIMIT 1")
    release = delivery.current_release()
    out = []
    if release:
        rel_cite = c.cite(q.src("record", "Release registry", "releases", release["id"]))
        out.append(f"Live storefront release: {release['id']} ({release['kind']}, revision "
                   f"{release['revision'][:10]}), last-known-good {kv_get(delivery.LKG_KEY)} {rel_cite}.")
    if not run:
        out.append("There are no delivery runs yet. Submit a brief or run the guided demo.")
        return out
    gates = c.call("evaluate_gates", delivery.evaluate_gates, run_id=run["id"],
                   revision=delivery.head_revision(run["id"]))
    cite = c.cite(q.src("record", f"Delivery run {run['id']}", f"runs:{run['id']}", "status, gates, tests"))
    failing = [g for g in gates["gates"] if not g["passed"]]
    out.append(f"**{run['title']}** ({run['id']}) is **{run['status']}** at stage {run['stage']}"
               + (f", waiting for {run['waiting_for'].replace('_', ' ')}" if run["waiting_for"] else "") + f" {cite}.")
    if gates["revision"]:
        if failing:
            out.append("Release gates failing on the candidate revision: "
                       + "; ".join(f"{g['id']} {g['name']} ({g['detail']})" for g in failing) + f" {cite}.")
        else:
            out.append(f"All 7 release gates pass on the candidate revision {gates['revision'][:10]} {cite}.")
    blocked = rows("SELECT id, status FROM releases WHERE status IN ('blocked', 'awaiting-approval', 'approved',"
                   " 'failed')")
    if "block" in p.question.lower() and run["status"] != "blocked" and not failing and not blocked:
        out.insert(0, "Nothing is blocked right now: no release is waiting, blocked or failed.")
    for b in blocked:
        out.append(f"Release {b['id']} is {b['status']}"
                   + (": it needs a release approver to approve and deploy it." if b["status"] in
                      ("awaiting-approval", "approved") else ".") + f" {cite}")
    tr = row("SELECT id, status, exit_code, revision FROM test_runs WHERE run_id = ? ORDER BY started_at DESC LIMIT 1",
             (run["id"],))
    if tr:
        tr_cite = c.cite(q.src("tool", "pytest test run", "test_runs:" + tr["id"]))
        out.append(f"Latest test run {tr['id']}: {tr['status']} (exit code {tr['exit_code']}) on "
                   f"{tr['revision'][:10]} {tr_cite}.")
    if run["error"]:
        out.append(f"Last step error: {run['error']}.")
    return out


def h_incident(p: Parsed, c: Ctx) -> list[str]:
    inc = row("SELECT id FROM incidents WHERE id = ?", (p.incident_id,)) if p.incident_id else \
        row("SELECT id FROM incidents ORDER BY opened_at DESC LIMIT 1")
    if not inc:
        return ["No incidents are recorded. In the guided demo, one is opened after the injected inventory timeout."]
    i = c.call("get_incident", incidents.get_incident, incident_id=inc["id"])
    cite = c.cite(q.src("record", f"Incident {i['id']}", f"incidents:{i['id']}", "evidence and hypotheses"))
    a = i["analysis"]
    out = [f"**{i['id']}: {i['title']}**, status **{i['status']}**, linked to release {i['release_id']} "
           f"(revision {i['revision'][:10]}) {cite}.",
           "Evidence (recorded facts):\n" + "\n".join(f"- {e['statement']}" for e in a["evidence"][:4]),
           "Hypotheses (not proven):\n" + "\n".join(f"- {h['id']} ({h['status']}): {h['statement']}"
                                                   for h in a["hypotheses"]),
           a["disclaimer"]]
    return out


def h_policy(p: Parsed, c: Ctx, min_score: float = 3.0) -> list[str]:
    hits = c.call("search_documents", lambda query: get_index().search(query, k=2, min_score=min_score),
                  query=p.question)
    if not hits:
        return []
    out = []
    for h in hits:
        cite = c.cite(q.src("document", f"{h['title']} v{h['version']}", h["ref"], h["heading"]))
        out.append(f"**{h['ref']} {h['heading']}**: {h['excerpt']} {cite}")
    return out


def h_overview(p: Parsed, c: Ctx) -> list[str]:
    o = c.call("executive_overview", q.executive_overview)
    data_cite = c.cite(q.src("data", q.SYNTHETIC, "enterprise overview", "sales, stock, listings"))
    s = o["sales"]
    out = [f"**Briefing (synthetic data)**: revenue {money(s['revenue_cents'])} over the last 4 weeks, "
           f"{pct(s['revenue_change_pct'])} vs the prior 4 weeks; top product "
           f"{o['top_product']['name']} {data_cite}."]
    crit = [a for a in o["inventory_alerts"] if a["status"] == "critical"]
    if crit:
        out.append("Stock: " + "; ".join(f"{a['name']} at {a['warehouse']} has {a['days_of_cover']} days of cover"
                                         for a in crit) + f" (critical) {data_cite}.")
    high = [x for x in o["campaign_stock_risk"] if x["risk"] == "high"]
    if high:
        out.append(f"Ontario weekend campaign: high stock risk for {', '.join(x['name'] for x in high)} "
                   f"{data_cite}.")
    if o["compliance"]["critical"]:
        first = next(i for i in o["compliance"]["issues"] if i["severity"] == "critical")
        out.append(f"Compliance: {o['compliance']['critical']} critical listing issue(s), e.g. {first['name']} on "
                   f"{first['channel']}: {first['detail']} {data_cite}.")
    open_inc = incidents.open_incidents()
    run = row("SELECT id, status, waiting_for FROM runs ORDER BY created_at DESC LIMIT 1")
    rec_cite = c.cite(q.src("record", "Delivery and incident records", "runs + incidents"))
    out.append(f"Digital delivery: latest run {run['id']} is {run['status']}"
               + (f" (waiting for {run['waiting_for'].replace('_', ' ')})" if run and run["waiting_for"] else "")
               + f"; {len(open_inc)} open incident(s) {rec_cite}." if run else
               f"Digital delivery: no runs yet; {len(open_inc)} open incident(s) {rec_cite}.")
    return out


def h_help(p: Parsed, c: Ctx) -> list[str]:
    return ["I answer read-only questions about FoodCare's **sales and promotions**, **inventory**, **product "
            "compliance**, **software delivery** (runs, tests, releases), **incidents** and **company policies**. I "
            "cite the data or document behind every figure. I can't take actions: approvals, deployments and fault "
            "controls stay in the workflow screens, under role permissions.",
            "Try: " + "; ".join(f"“{e}”" for e in EXAMPLES[:6])]


HANDLERS = {"sales": h_sales, "campaign": h_campaign, "inventory": h_inventory, "compliance": h_compliance,
            "delivery": h_delivery, "incident": h_incident, "policy": h_policy, "overview": h_overview,
            "help": h_help}


def compose(p: Parsed) -> tuple[list[str], Ctx, list[str]]:
    c = Ctx()
    paragraphs: list[str] = []
    intents = list(p.intents)
    if "campaign" in intents and "inventory" in intents:
        paragraphs += h_campaign_risk(p, c)
        intents = [i for i in intents if i not in ("campaign", "inventory")]
    for intent in intents:
        paragraphs += HANDLERS[intent](p, c)
    if not paragraphs:
        # Unclassified question: only answer from a document if it is a strong match.
        paragraphs = h_policy(p, c, min_score=8.0)
    if p.question.lower().lstrip().startswith(ACTION_VERBS):
        paragraphs.insert(0, "I'm read-only, so I can't do that. Approvals, deployments, rollbacks and fault "
                             "controls are actions in the workflow screens and need the right role. Here is the "
                             "relevant status:")
    return paragraphs, c, intents or p.intents


class LiveAnswer(BaseModel):
    answer: str = Field(max_length=4000)
    cited_source_ids: list[str] = Field(max_length=20)


def _live_answer(question: str, draft: list[str], c: Ctx) -> tuple[str, dict]:
    from app.agents import live

    sources = "\n".join(f"[{s['id']}] {s['label']} ({s['ref']}) {s.get('detail', '')}" for s in c.sources)
    prompt = (
        "Answer the user's question for FoodCare's leadership using ONLY the facts below. Cite sources inline as "
        "[S1], [S2] using only the listed IDs. Keep every number exactly as given. If the facts do not answer "
        "the question, say so. Keep it concise.\n"
        f"<untrusted_question>\n{question}\n</untrusted_question>\n"
        f"<facts>\n{chr(10).join(draft)}\n</facts>\n<sources>\n{sources}\n</sources>"
    )
    result, usage = live.LiveClient().structured(None, prompt, LiveAnswer)
    allowed = {s["id"] for s in c.sources}
    used = set(re.findall(r"\[(S\d+)\]", result.answer)) | set(result.cited_source_ids)
    if not used <= allowed:
        raise PlatformError("Live answer cited sources that were not provided", invalid=sorted(used - allowed))
    return result.answer, usage


def ask(question: str, user: User, conversation_id: str | None = None, mode: str = "demo") -> dict:
    question = question.strip()
    if not question or len(question) > 500:
        raise PlatformError("Questions must be 1-500 characters")
    conversation_id = conversation_id if conversation_id and re.fullmatch(r"CNV-[0-9A-F]{10}", conversation_id) \
        else f"CNV-{uuid.uuid4().hex[:10].upper()}"
    p = parse(question)
    paragraphs, c, intents = compose(p)
    answered = bool(paragraphs)
    if not answered:
        paragraphs = ["I can't answer that from FoodCare's data in this demo. I only answer questions about sales "
                      "and promotions, inventory, product compliance, software delivery, incidents and company "
                      "policies, and I won't guess.",
                      "Try: " + "; ".join(f"“{e}”" for e in EXAMPLES[:5])]
    answer_mode, provenance, notice, usage = "demo", "deterministic", None, None
    if mode == "live":
        settings = get_settings()
        live_count = row("SELECT COUNT(*) AS n FROM copilot_messages WHERE conversation_id = ? AND role = 'assistant'"
                         " AND answer_json LIKE '%\"mode\": \"live\"%'", (conversation_id,))["n"]
        if not settings.live_available:
            notice = ("LIVE mode is not configured (set ANTHROPIC_API_KEY and ANTHROPIC_MODEL). "
                      "This is the deterministic answer.")
        elif live_count >= settings.llm_max_calls_per_run * 3:
            notice = "LIVE answer budget for this conversation is used up. This is the deterministic answer."
        elif answered:
            try:
                text, usage = _live_answer(question, paragraphs, c)
                paragraphs, answer_mode, provenance = [text], "live", "live_ai"
            except PlatformError as exc:
                notice = f"LIVE answer unavailable ({exc.message}). This is the deterministic answer."
    result = {
        "conversation_id": conversation_id, "question": question, "answered": answered,
        "answer": "\n\n".join(paragraphs), "sources": c.sources, "tool_calls": c.tool_calls,
        "intents": intents, "entities": p.entities(), "mode": answer_mode, "provenance": provenance,
        "notice": notice, "usage": usage, "read_only": True,
        "follow_ups": [e for e in EXAMPLES if e.lower() != question.lower()][:3],
    }
    with session() as conn:
        conn.execute("INSERT INTO copilot_messages (conversation_id, ts, role, username, content) VALUES (?, ?, 'user',"
                     " ?, ?)", (conversation_id, now_iso(), user.username, question))
        conn.execute("INSERT INTO copilot_messages (conversation_id, ts, role, username, content, answer_json) VALUES"
                     " (?, ?, 'assistant', NULL, ?, ?)", (conversation_id, now_iso(), result["answer"],
                                                          json.dumps(result, default=str)))
    return result


def history(conversation_id: str) -> list[dict]:
    items = rows("SELECT * FROM copilot_messages WHERE conversation_id = ? ORDER BY seq", (conversation_id,))
    for item in items:
        item["answer"] = json.loads(item.pop("answer_json")) if item.get("answer_json") else None
    return items
