"""Global supply-chain network for the maps: a configurable, clearly labelled SYNTHETIC scenario.

Nothing here is verified enterprise data. The scenario file (``fixtures/geo/scenario.json`` or
``FOODCARE_GEO_SCENARIO``) sets the country footprint, annual revenue, currency, seed and site
counts; everything else is generated deterministically from it:

* the footprint (the home country plus a seeded sample of Natural Earth countries),
* a per-country revenue split (seeded log-normal weights, summing exactly to the scenario total),
* farms -> suppliers -> factories -> distribution centres -> markets, placed near country
  centroids (so no real address is implied) and linked to their nearest downstream site,
* a year of historical quality incidents per site (Poisson), and
* 30/90/180-day risk simulations (Monte Carlo with Gamma-Poisson uncertainty).

Real records join the map in one place only: an inspection batch whose ``supplier`` field equals
a network supplier's name is placed at that supplier. Those incidents are ``operational_record``
and are visible only to the user who created the batch.

There are no shipment tracking events, so no movement is ever reported as real.
"""

from __future__ import annotations

import json
import math
import random
from collections import defaultdict
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from app.config import FIXTURES, get_settings
from app.memory.store import get_store

PROVENANCE = {
    "verified": "Verified enterprise data",
    "operational_record": "Historical operational record (created in this app)",
    "modeled": "Forecast / modelled scenario",
    "synthetic": "Synthetic demonstration data",
}
TIERS = ("farm", "supplier", "factory", "distribution_centre", "market")
TIER_LABEL = {"farm": "Farm", "supplier": "Supplier", "factory": "Factory",
              "distribution_centre": "Distribution centre", "market": "Market"}
HORIZONS = (30, 90, 180)
AS_OF = date(2026, 10, 31)  # the demo clock's date; history ends here
DRAWS = 400


def _countries() -> list[dict]:
    return json.loads((FIXTURES / "geo" / "countries.json").read_text())["countries"]


def scenario() -> dict:
    path = Path(get_settings().geo_scenario_path)
    data = json.loads(path.read_text())
    countries = _countries()
    n = int(data["countries"])
    available = len(countries) - len(set(data.get("exclude_territories", [])) & {c["name"] for c in countries})
    if not 1 <= n <= available:
        raise ValueError(f"scenario countries must be between 1 and {available} (Natural Earth 1:110m)")
    if float(data["annual_revenue"]) <= 0:
        raise ValueError("scenario annual_revenue must be positive")
    return {**data, "path": path.name}


def _haversine(a: dict, b: dict) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


@lru_cache(maxsize=8)
def _build(key: str) -> dict:
    sc = json.loads(key)
    rng = random.Random(sc["seed"])
    countries = {c["id"]: c for c in _countries()}
    home = sc.get("home_country") or next(iter(countries))
    excluded = set(sc.get("exclude_territories", []))
    others = sorted(i for i in countries if i != home and countries[i]["name"] not in excluded)
    rng.shuffle(others)
    footprint = [home] + others[: int(sc["countries"]) - 1]

    # Per-country revenue: seeded log-normal weights, rounded to whole currency units, exact total.
    total = int(round(float(sc["annual_revenue"])))
    home_share = float(sc.get("home_revenue_share", 0))
    weights = {c: rng.lognormvariate(0, 1.1) for c in footprint if c != home}
    wsum = sum(weights.values())
    rest = total - int(total * home_share)
    revenue = {home: int(total * home_share)} if home_share else {home: 0}
    if not home_share:
        weights[home] = rng.lognormvariate(0, 1.1)
        wsum += weights[home]
        rest = total
    revenue.update({c: int(rest * w / wsum) for c, w in weights.items()})
    revenue[max(revenue, key=revenue.get)] += total - sum(revenue.values())

    by_rev = sorted(footprint, key=lambda c: -revenue[c])
    nodes: list[dict] = []
    counters: dict[str, int] = defaultdict(int)

    def add(tier: str, cid: str) -> dict:
        counters[tier] += 1
        c = countries[cid]
        node = {
            "id": f"GEO-{tier[:3].upper()}-{counters[tier]:02d}", "tier": tier,
            "name": f"Synthetic {TIER_LABEL[tier].lower()} {c['name']} {counters[tier]:02d}",
            "country": cid, "country_name": c["name"],
            "lat": round(max(-60, min(75, c["lat"] + rng.uniform(-1.5, 1.5))), 3),
            "lon": round(((c["lon"] + rng.uniform(-1.5, 1.5) + 180) % 360) - 180, 3),
            "location_note": "Synthetic location near the country centroid, not a real address",
            "provenance": "synthetic",
        }
        nodes.append(node)
        return node

    net = sc["network"]
    # Markets sit in the biggest revenue countries; the rest of the chain is spread more widely.
    for cid in by_rev[: net["market"]]:
        add("market", cid)
    for tier in ("distribution_centre", "factory", "supplier", "farm"):
        pool = by_rev[: max(net[tier] * 3, 12)]
        for _ in range(net[tier]):
            add(tier, rng.choice(pool))

    tiers = {t: [n for n in nodes if n["tier"] == t] for t in TIERS}
    edges: list[dict] = []
    for up, down in zip(TIERS, TIERS[1:], strict=False):
        for a in tiers[up]:
            near = sorted(tiers[down], key=lambda b: _haversine(a, b))
            targets = near[: 1 if up in ("farm", "supplier") else 2]
            for b in targets:
                km = _haversine(a, b)
                edges.append({"id": f"{a['id']}>{b['id']}", "from": a["id"], "to": b["id"], "km": round(km),
                              "mode": "road" if km < 900 else "sea" if km > 3500 else "rail",
                              "lead_time_days": round(1 + km / 650, 1), "provenance": "synthetic"})
        # every downstream site gets at least one supplier of its own
        for b in tiers[down]:
            if not any(e["to"] == b["id"] for e in edges):
                a = min(tiers[up], key=lambda x: _haversine(x, b))
                km = _haversine(a, b)
                edges.append({"id": f"{a['id']}>{b['id']}", "from": a["id"], "to": b["id"], "km": round(km),
                              "mode": "road" if km < 900 else "sea" if km > 3500 else "rail",
                              "lead_time_days": round(1 + km / 650, 1), "provenance": "synthetic"})

    # Revenue dependent on each node: market = share of its country's revenue; upstream nodes
    # inherit the revenue of everything they feed, split evenly across a node's suppliers.
    ups = defaultdict(list)
    for e in edges:
        ups[e["to"]].append(e["from"])
    dependent: dict[str, float] = defaultdict(float)
    market_count = defaultdict(int)
    for m in tiers["market"]:
        market_count[m["country"]] += 1
    for m in tiers["market"]:
        dependent[m["id"]] = revenue[m["country"]] / market_count[m["country"]]
    for tier in reversed(TIERS[1:]):
        for n in tiers[tier]:
            for u in ups[n["id"]]:
                dependent[u] += dependent[n["id"]] / len(ups[n["id"]])
    for n in nodes:
        n["revenue_dependent"] = int(dependent[n["id"]])
        n["performance"] = {"on_time_pct": round(rng.uniform(86, 99.5), 1),
                            "quality_pass_pct": round(rng.uniform(90, 99.8), 1), "provenance": "synthetic"}

    # Historical incidents (synthetic): Poisson per site over the history window.
    incidents = []
    days = int(sc["history_days"])
    kinds = ("Bruising above spec", "Greening", "Soft rot", "Foreign material", "Temperature excursion",
             "Late delivery", "Undersize lot")
    for n in nodes:
        if n["tier"] == "market":
            continue
        lam = sc["incidents_per_site_year"] * days / 365 * rng.uniform(0.3, 2.2)
        k = _poisson(rng, lam)
        for _ in range(k):
            d = AS_OF - timedelta(days=rng.randint(0, days - 1))
            incidents.append({
                "id": f"GEO-INC-{len(incidents) + 1:04d}", "node_id": n["id"], "country": n["country"],
                "lat": n["lat"], "lon": n["lon"], "date": d.isoformat(), "kind": rng.choice(kinds),
                "severity": rng.choices(("low", "medium", "high"), (5, 3, 1))[0],
                "batch": f"SYN-LOT-{rng.randint(10000, 99999)}", "provenance": "synthetic"})
    incidents.sort(key=lambda i: i["date"], reverse=True)
    return {"footprint": footprint, "revenue": revenue, "nodes": nodes, "edges": edges, "incidents": incidents,
            "countries": countries}


def _poisson(rng: random.Random, lam: float) -> int:
    if lam <= 0:
        return 0
    if lam > 30:
        return max(0, round(rng.gauss(lam, math.sqrt(lam))))
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def _net() -> tuple[dict, dict]:
    sc = scenario()
    key = json.dumps({k: sc.get(k) for k in ("countries", "annual_revenue", "seed", "home_country", "network",
                                              "incidents_per_site_year", "history_days", "home_revenue_share",
                                              "exclude_territories")}, sort_keys=True)
    return sc, _build(key)


def _operational_incidents(username: str | None) -> list[dict]:
    """Inspection batches by this user whose supplier names a network supplier."""
    if not username:
        return []
    _, net = _net()
    suppliers = {n["name"]: n for n in net["nodes"] if n["tier"] == "supplier"}
    if not suppliers:
        return []
    marks = ",".join("?" * len(suppliers))
    rows = get_store().query(
        f"SELECT id, title, supplier, lot_code, created_at, summary_json FROM inspection_batches"
        f" WHERE username = ? AND supplier IN ({marks}) ORDER BY created_at DESC", (username, *suppliers))
    out = []
    for r in rows:
        s = json.loads(r["summary_json"] or "{}")
        graded = s.get("graded") or 0
        bad = (s.get("counts") or {}).get("Not Good", 0)
        n = suppliers[r["supplier"]]
        if graded and bad / graded >= 0.2:
            out.append({"id": r["id"], "node_id": n["id"], "country": n["country"], "lat": n["lat"],
                        "lon": n["lon"], "date": r["created_at"][:10],
                        "kind": f"Inspection: {bad} of {graded} potatoes Not Good", "severity": "high"
                        if bad / graded >= 0.4 else "medium", "batch": r["lot_code"] or r["id"],
                        "provenance": "operational_record", "title": r["title"]})
    return out


def _country_rows(sc: dict, net: dict, incidents: list[dict]) -> list[dict]:
    inc = defaultdict(int)
    for i in incidents:
        inc[i["country"]] += 1
    sites = defaultdict(int)
    for n in net["nodes"]:
        sites[n["country"]] += 1
    return sorted(({"id": c, "name": net["countries"][c]["name"], "lat": net["countries"][c]["lat"],
                    "lon": net["countries"][c]["lon"], "revenue": net["revenue"][c],
                    "revenue_share_pct": round(100 * net["revenue"][c] / int(sc["annual_revenue"]), 3),
                    "sites": sites[c], "incidents_365d": inc[c], "provenance": "synthetic"}
                   for c in net["footprint"]), key=lambda r: -r["revenue"])


def network(username: str | None = None, country: str | None = None, tier: str | None = None) -> dict:
    sc, net = _net()
    incidents = net["incidents"] + _operational_incidents(username)
    nodes, edges = net["nodes"], net["edges"]
    if country:
        keep = {n["id"] for n in nodes if n["country"] == country}
        edges = [e for e in edges if e["from"] in keep or e["to"] in keep]
        touched = keep | {e["from"] for e in edges} | {e["to"] for e in edges}
        nodes = [n for n in nodes if n["id"] in touched]
        incidents = [i for i in incidents if i["country"] == country]
    if tier:
        nodes = [n for n in nodes if n["tier"] == tier]
        ids = {n["id"] for n in nodes}
        edges = [e for e in edges if e["from"] in ids and e["to"] in ids]
    countries = _country_rows(sc, net, net["incidents"] + _operational_incidents(username))
    if country:
        countries = [c for c in countries if c["id"] == country]
    counts = defaultdict(int)
    for item in (*nodes, *edges, *incidents, *countries):
        counts[item["provenance"]] += 1
    return {
        "scenario": {k: sc[k] for k in ("name", "disclaimer", "countries", "annual_revenue", "currency", "seed",
                                        "path")},
        "filters": {"country": country, "tier": tier},
        "countries": countries, "nodes": nodes, "edges": edges, "incidents": incidents,
        "tracking": {"events": 0, "note": "No shipment tracking events exist. Any movement shown on the map is "
                                          "SIMULATED along the synthetic routes and is off by default."},
        "provenance": {k: {"label": v, "count": counts.get(k, 0)} for k, v in PROVENANCE.items()},
        "attribution": {"attributed_to_market_sites": sum(n["revenue_dependent"] for n in net["nodes"]
                                                          if n["tier"] == "market"),
                        "total": int(sc["annual_revenue"]),
                        "note": "Only countries with a market site attribute revenue to the site network; the rest "
                                "is shown on the country map but not traced to sites."},
        "as_of": AS_OF.isoformat(),
    }


def _upstream(net: dict, node_id: str) -> list[list[dict]]:
    """All upstream paths from a node back to farms (each path ordered node -> farm)."""
    by_id = {n["id"]: n for n in net["nodes"]}
    ups = defaultdict(list)
    for e in net["edges"]:
        ups[e["to"]].append(e["from"])
    paths: list[list[dict]] = []

    def walk(nid: str, acc: list[dict]) -> None:
        acc = acc + [by_id[nid]]
        if not ups[nid]:
            paths.append(acc)
            return
        for u in sorted(ups[nid]):
            walk(u, acc)
    walk(node_id, [])
    return paths


def trace(node_id: str) -> dict:
    _, net = _net()
    by_id = {n["id"]: n for n in net["nodes"]}
    if node_id not in by_id:
        raise KeyError(node_id)
    downs = defaultdict(list)
    for e in net["edges"]:
        downs[e["from"]].append(e["to"])
    seen, frontier = set(), [node_id]
    while frontier:
        nid = frontier.pop()
        for d in downs[nid]:
            if d not in seen:
                seen.add(d)
                frontier.append(d)
    return {"node": by_id[node_id], "upstream_paths": [[{k: n[k] for k in ("id", "tier", "name", "country_name")}
                                                        for n in p] for p in _upstream(net, node_id)],
            "downstream": [by_id[d] | {} for d in sorted(seen)], "provenance": "synthetic"}


def _incident_for(net: dict, incident_id: str, username: str | None) -> dict | None:
    for i in net["incidents"] + _operational_incidents(username):
        if i["id"] == incident_id:
            return i
    return None


def node_detail(node_id: str, username: str | None = None) -> dict:
    sc, net = _net()
    t = trace(node_id)
    incidents = [i for i in net["incidents"] + _operational_incidents(username) if i["node_id"] == node_id]
    by_month = defaultdict(int)
    for i in incidents:
        by_month[i["date"][:7]] += 1
    return {**t, "incidents": incidents,
            "recurrence": [{"month": m, "incidents": by_month[m]} for m in sorted(by_month)],
            "financial": {"revenue_dependent": t["node"]["revenue_dependent"], "currency": sc["currency"],
                          "formula": "Revenue of every market this site feeds, split evenly across each "
                                     "site's suppliers (synthetic scenario).", "provenance": "synthetic"},
            "risk": simulate(node=node_id)["horizons"]}


def simulate(country: str | None = None, node: str | None = None) -> dict:
    """30/90/180-day risk scenario: incident counts and revenue exposure with 10/50/90% bands.

    Model (stated, not fitted to real data): each site's incident rate has a Gamma posterior from
    its synthetic history (shape = incidents + 0.5, rate = history years + 0.5); each draw samples
    a rate, a Poisson count over the horizon and a log-normal disruption length per incident.
    Exposure = disrupted days x revenue dependent on the site / 365.
    """
    sc, net = _net()
    sites = [n for n in net["nodes"] if n["tier"] != "market"]
    if node:
        sites = [n for n in sites if n["id"] == node] or [n for n in net["nodes"] if n["id"] == node]
    elif country:
        sites = [n for n in sites if n["country"] == country]
    hist = defaultdict(int)
    for i in net["incidents"]:
        hist[i["node_id"]] += 1
    years = sc["history_days"] / 365
    seed = sc["seed"] * 31 + sum(ord(ch) for ch in (node or country or "all"))
    out = []
    for h in HORIZONS:
        rng = random.Random(seed + h)
        counts, losses = [], []
        for _ in range(DRAWS):
            c_total, loss = 0, 0.0
            for s in sites:
                lam = rng.gammavariate(hist[s["id"]] + 0.5, 1 / (years + 0.5)) * h / 365
                k = _poisson(rng, lam)
                c_total += k
                for _ in range(k):
                    days = rng.lognormvariate(math.log(sc["disruption_days_median"]), 0.6)
                    loss += min(days, h) * s["revenue_dependent"] / 365
            counts.append(c_total)
            losses.append(loss)
        counts.sort()
        losses.sort()

        def pct(xs: list[float], q: float) -> float:
            return xs[min(len(xs) - 1, int(q * len(xs)))]
        out.append({"days": h, "incidents": {"p10": pct(counts, 0.1), "p50": pct(counts, 0.5),
                                              "p90": pct(counts, 0.9)},
                    "exposure": {"p10": round(pct(losses, 0.1)), "p50": round(pct(losses, 0.5)),
                                 "p90": round(pct(losses, 0.9))}})
    return {"scope": {"country": country, "node": node, "sites": len(sites)}, "currency": sc["currency"],
            "horizons": out, "draws": DRAWS, "provenance": "modeled",
            "method": "Monte Carlo (Gamma-Poisson incident rates from the synthetic history, log-normal "
                      "disruption length). Bands are the 10th-90th percentile of simulated outcomes; they show "
                      "model uncertainty, not a guarantee. Inputs are synthetic."}


def summary_for_copilot(username: str | None, country: str | None = None, node: str | None = None) -> dict:
    sc, net = _net()
    if node:
        d = node_detail(node, username)
        return {"kind": "node", "detail": d, "scenario": sc}
    rows = _country_rows(sc, net, net["incidents"] + _operational_incidents(username))
    if country:
        rows = [r for r in rows if r["id"] == country]
    return {"kind": "country" if country else "network", "countries": rows, "scenario": sc,
            "risk": simulate(country=country), "operational": _operational_incidents(username)}


def find_country(text: str) -> str | None:
    t = text.lower()
    best = None
    for c in _countries():
        name = c["name"].lower()
        if len(name) > 3 and name in t and (best is None or len(name) > len(best[1])):
            best = (c["id"], name)
    return best[0] if best else None


def supplier_names() -> list[str]:
    _, net = _net()
    return sorted(n["name"] for n in net["nodes"] if n["tier"] == "supplier")


def incident(incident_id: str, username: str | None) -> dict | None:
    _, net = _net()
    return _incident_for(net, incident_id, username)
