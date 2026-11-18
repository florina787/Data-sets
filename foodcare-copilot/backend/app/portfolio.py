"""Enterprise Delivery & Team Intelligence: what every department is building, and what needs attention.

No Jira, Azure DevOps, GitHub Projects, Confluence or SharePoint connection is configured, so the
portfolio is a labelled **synthetic** fixture for the fictional company. Calculations are
deterministic: schedule slip from milestone dates against the demo clock, budget variance from
budget and spend. Technology links are marked ``verified`` (recorded in the delivery system) or
``inferred`` (suggested by naming/ownership) and are never mixed up.

Privacy Shield: owners are shown as role titles with a synthetic display name (internal);
vendor contract values are confidential (banded), and personnel ratings are highly restricted
(never leave the server, even for the CTO).
"""

from __future__ import annotations

import re
from datetime import date

TODAY = date(2026, 10, 31)
SYN = "synthetic"
SOURCE = "Synthetic portfolio fixture (Jira / Azure DevOps / SharePoint not connected)"
DEPARTMENTS = [
    "Technology",
    "Marketing",
    "Commercial",
    "Sales",
    "Retail",
    "Operations",
    "Supply Chain",
    "Finance",
    "People",
]

INITIATIVES = [
    {
        "id": "INI-MKT-01",
        "dept": "Marketing",
        "name": "Loyalty programme relaunch",
        "objective": "Lift repeat purchases with personalised offers",
        "owner_title": "Head of Loyalty",
        "owner_name": "Avery (synthetic)",
        "team": "Loyalty squad",
        "milestones": [
            ("Offer design signed off", "2026-09-15", "2026-09-18"),
            ("Commercial pricing approval", "2026-10-15", None),
            ("Loyalty API live", "2026-11-15", None),
            ("Launch", "2026-12-01", None),
        ],
        "budget": 420_000_00,
        "spend": 265_000_00,
        "depends_on": ["INI-COM-02", "INI-TEC-03", "INI-TEC-04"],
        "risks": ["Pricing approval overdue", "API depends on cluster capacity"],
        "value": "Repeat purchase +3 pts (target)",
        "value_cents": 1_200_000_00,
        "measured": None,
        "vendor_contract_cents": 180_000_00,
        "ratings": "CANARY-RATING-MKT",
    },
    {
        "id": "INI-MKT-02",
        "dept": "Marketing",
        "name": "Weekend campaign automation",
        "objective": "Automate promotion set-up for regional campaigns",
        "owner_title": "Campaign Manager",
        "owner_name": "Jordan (synthetic)",
        "team": "Campaign ops",
        "milestones": [
            ("Templates", "2026-08-30", "2026-08-29"),
            ("Storefront integration", "2026-10-25", "2026-10-30"),
        ],
        "budget": 90_000_00,
        "spend": 88_000_00,
        "depends_on": ["INI-TEC-01"],
        "risks": [],
        "value": "Campaign set-up time −60%",
        "value_cents": 150_000_00,
        "measured": "Set-up time −45% (first 2 campaigns)",
        "vendor_contract_cents": None,
        "ratings": "CANARY-RATING-MKT2",
    },
    {
        "id": "INI-COM-02",
        "dept": "Commercial",
        "name": "Promotional pricing governance",
        "objective": "Approve promo mechanics and margins before launch",
        "owner_title": "Commercial Director",
        "owner_name": "Morgan (synthetic)",
        "team": "Pricing desk",
        "milestones": [("Margin model", "2026-09-30", "2026-10-06"), ("Loyalty pricing approval", "2026-10-15", None)],
        "budget": 60_000_00,
        "spend": 41_000_00,
        "depends_on": [],
        "risks": ["Approval board met once in October"],
        "value": "Promo margin leakage −1 pt",
        "value_cents": 300_000_00,
        "measured": None,
        "vendor_contract_cents": None,
        "ratings": "CANARY-RATING-COM",
    },
    {
        "id": "INI-COM-01",
        "dept": "Commercial",
        "name": "Key-account pricing refresh",
        "objective": "Re-price top 20 retail accounts",
        "owner_title": "Head of Key Accounts",
        "owner_name": "Riley (synthetic)",
        "team": "Key accounts",
        "milestones": [("Analysis", "2026-10-10", "2026-10-09"), ("Account negotiations", "2026-12-15", None)],
        "budget": 75_000_00,
        "spend": 30_000_00,
        "depends_on": ["INI-TEC-04"],
        "risks": [],
        "value": "Gross margin +0.4 pt",
        "value_cents": 500_000_00,
        "measured": None,
        "vendor_contract_cents": 40_000_00,
        "ratings": "CANARY-RATING-COM2",
    },
    {
        "id": "INI-TEC-01",
        "dept": "Technology",
        "name": "Storefront platform hardening",
        "objective": "Resilient checkout and safe releases",
        "owner_title": "Engineering Manager, E-commerce",
        "owner_name": "Sam (synthetic)",
        "team": "E-commerce platform",
        "milestones": [("Timeout repair", "2026-10-31", "2026-10-31"), ("Load test", "2026-11-20", None)],
        "budget": 150_000_00,
        "spend": 96_000_00,
        "depends_on": [],
        "risks": [],
        "value": "Checkout errors <0.5%",
        "value_cents": 250_000_00,
        "measured": "Repair release deployed (demo)",
        "vendor_contract_cents": None,
        "ratings": "CANARY-RATING-TEC",
    },
    {
        "id": "INI-TEC-03",
        "dept": "Technology",
        "name": "Loyalty API on Kubernetes",
        "objective": "Serve loyalty offers to web and stores",
        "owner_title": "Platform Lead",
        "owner_name": "Casey (synthetic)",
        "team": "Platform engineering",
        "milestones": [
            ("API design", "2026-10-01", "2026-10-03"),
            ("Staging on cluster", "2026-10-28", None),
            ("Production", "2026-11-15", None),
        ],
        "budget": 210_000_00,
        "spend": 190_000_00,
        "depends_on": ["INI-TEC-04"],
        "risks": ["Staging blocked on capacity"],
        "value": "Enables loyalty relaunch",
        "value_cents": 0,
        "measured": None,
        "vendor_contract_cents": 60_000_00,
        "ratings": "CANARY-RATING-TEC3",
    },
    {
        "id": "INI-TEC-04",
        "dept": "Technology",
        "name": "Customer segmentation pipeline (Databricks)",
        "objective": "Governed customer segments for offers and pricing",
        "owner_title": "Data Engineering Lead",
        "owner_name": "Drew (synthetic)",
        "team": "Data engineering",
        "milestones": [("Source mapping", "2026-09-20", "2026-09-25"), ("Pipeline in production", "2026-10-20", None)],
        "budget": 160_000_00,
        "spend": 171_000_00,
        "depends_on": [],
        "risks": ["Over budget", "Data quality checks failing"],
        "value": "Segments for 3 initiatives",
        "value_cents": 0,
        "measured": None,
        "vendor_contract_cents": 90_000_00,
        "ratings": "CANARY-RATING-TEC4",
    },
    {
        "id": "INI-TEC-05",
        "dept": "Technology",
        "name": "Jerry AI copilot rollout",
        "objective": "Evidence-backed answers for leaders",
        "owner_title": "CTO office",
        "owner_name": "CTO office",
        "team": "AI platform",
        "milestones": [("Pilot", "2026-10-15", "2026-10-14"), ("Rollout", "2026-12-10", None)],
        "budget": 120_000_00,
        "spend": 70_000_00,
        "depends_on": [],
        "risks": [],
        "value": "Analyst hours saved (to measure)",
        "value_cents": 200_000_00,
        "measured": None,
        "vendor_contract_cents": None,
        "ratings": "CANARY-RATING-TEC5",
    },
    {
        "id": "INI-SAL-01",
        "dept": "Sales",
        "name": "Retail order portal",
        "objective": "Self-service orders for stores",
        "owner_title": "Sales Operations Manager",
        "owner_name": "Quinn (synthetic)",
        "team": "Sales ops",
        "milestones": [("Pilot stores", "2026-10-10", "2026-10-24"), ("All stores", "2026-12-20", None)],
        "budget": 80_000_00,
        "spend": 52_000_00,
        "depends_on": ["INI-TEC-01"],
        "risks": ["Pilot late by two weeks"],
        "value": "Order errors −30%",
        "value_cents": 120_000_00,
        "measured": None,
        "vendor_contract_cents": None,
        "ratings": "CANARY-RATING-SAL",
    },
    {
        "id": "INI-RET-01",
        "dept": "Retail",
        "name": "Store availability dashboard",
        "objective": "Spot out-of-stocks per store",
        "owner_title": "Retail Insights Lead",
        "owner_name": "Parker (synthetic)",
        "team": "Retail insights",
        "milestones": [("Data feed", "2026-11-05", None)],
        "budget": 40_000_00,
        "spend": 12_000_00,
        "depends_on": ["INI-TEC-04"],
        "risks": [],
        "value": "Lost sales visibility",
        "value_cents": 90_000_00,
        "measured": None,
        "vendor_contract_cents": None,
        "ratings": "CANARY-RATING-RET",
    },
    {
        "id": "INI-OPS-01",
        "dept": "Operations",
        "name": "Potato inspection at intake",
        "objective": "Grade lots at the dock with camera + rules",
        "owner_title": "Plant Quality Manager",
        "owner_name": "Taylor (synthetic)",
        "team": "Plant quality",
        "milestones": [("Pilot dock", "2026-10-01", "2026-10-02"), ("All docks", "2026-11-30", None)],
        "budget": 70_000_00,
        "spend": 33_000_00,
        "depends_on": ["INI-TEC-05"],
        "risks": [],
        "value": "Rejected-lot disputes −20%",
        "value_cents": 110_000_00,
        "measured": None,
        "vendor_contract_cents": None,
        "ratings": "CANARY-RATING-OPS",
    },
    {
        "id": "INI-SCM-01",
        "dept": "Supply Chain",
        "name": "Supplier risk scoring",
        "objective": "Rank suppliers by incidents and exposure",
        "owner_title": "Supply Chain Risk Manager",
        "owner_name": "Robin (synthetic)",
        "team": "Supply chain analytics",
        "milestones": [("Scorecard", "2026-10-20", "2026-10-21"), ("Quarterly review", "2026-12-05", None)],
        "budget": 55_000_00,
        "spend": 29_000_00,
        "depends_on": ["INI-TEC-04"],
        "risks": [],
        "value": "Disruption exposure visibility",
        "value_cents": 0,
        "measured": None,
        "vendor_contract_cents": None,
        "ratings": "CANARY-RATING-SCM",
    },
    {
        "id": "INI-FIN-01",
        "dept": "Finance",
        "name": "Software spend optimisation",
        "objective": "Cut unused licences at renewal",
        "owner_title": "IT Finance Partner",
        "owner_name": "Alex (synthetic)",
        "team": "FP&A",
        "milestones": [("Licence inventory", "2026-10-25", "2026-10-28"), ("Renewal decisions", "2026-11-15", None)],
        "budget": 20_000_00,
        "spend": 9_000_00,
        "depends_on": [],
        "risks": ["Notice deadlines approaching"],
        "value": "Avoided expenditure (estimate in Defense Command)",
        "value_cents": 0,
        "measured": None,
        "vendor_contract_cents": None,
        "ratings": "CANARY-RATING-FIN",
    },
    {
        "id": "INI-PPL-01",
        "dept": "People",
        "name": "Shift scheduling app",
        "objective": "Self-service shift swaps",
        "owner_title": "HR Systems Lead",
        "owner_name": "Jamie (synthetic)",
        "team": "HR systems",
        "milestones": [("Vendor selection", "2026-09-30", "2026-10-12"), ("Pilot plant", "2026-11-25", None)],
        "budget": 65_000_00,
        "spend": 18_000_00,
        "depends_on": ["INI-TEC-01"],
        "risks": ["Vendor selection slipped"],
        "value": "Overtime −5%",
        "value_cents": 80_000_00,
        "measured": None,
        "vendor_contract_cents": 35_000_00,
        "ratings": "CANARY-RATING-PPL",
    },
]
TECH_MAP = {
    "INI-MKT-01": [
        ("Loyalty API", "api", "verified"),
        ("loyalty-api (Kubernetes)", "workload", "verified"),
        ("Customer segments (Databricks)", "pipeline", "verified"),
        ("Offer ranking model", "model", "inferred"),
    ],
    "INI-TEC-03": [("loyalty-api (Kubernetes)", "workload", "verified"), ("Loyalty DB", "storage", "verified")],
    "INI-TEC-04": [
        ("Customer segments (Databricks)", "pipeline", "verified"),
        ("Lakehouse storage", "storage", "inferred"),
    ],
    "INI-TEC-01": [("storefront (Kubernetes)", "workload", "verified"), ("Inventory API", "api", "verified")],
    "INI-SAL-01": [("Order portal", "app", "verified"), ("ERP ordering", "app", "inferred")],
    "INI-OPS-01": [("Potato inspection (vision)", "app", "verified"), ("Jerry copilot", "app", "verified")],
    "INI-COM-01": [("Customer segments (Databricks)", "pipeline", "inferred")],
    "INI-RET-01": [("Customer segments (Databricks)", "pipeline", "verified")],
}
APPROVALS = [
    {
        "initiative": "INI-COM-02",
        "decision": "Approve loyalty promo pricing (blocks Marketing launch)",
        "due": "2026-11-04",
        "needs": "Commercial Director, CTO informed",
    },
    {
        "initiative": "INI-TEC-03",
        "decision": "Approve extra cluster capacity for loyalty-api staging",
        "due": "2026-11-03",
        "needs": "CTO",
    },
    {
        "initiative": "INI-TEC-04",
        "decision": "Accept a 7% budget overrun or descope data-quality automation",
        "due": "2026-11-06",
        "needs": "CTO + IT Finance",
    },
]


def _band(cents: int | None) -> str | None:
    if cents is None:
        return None
    v = cents / 100
    return (
        "under CAD 50k"
        if v < 50_000
        else "CAD 50–150k"
        if v < 150_000
        else "CAD 150–500k"
        if v < 500_000
        else "over CAD 500k"
    )


def _calc(i: dict) -> dict:
    ms = []
    slip_days = 0
    next_ms = None
    for name, planned, actual in i["milestones"]:
        p = date.fromisoformat(planned)
        a = date.fromisoformat(actual) if actual else None
        late = (a - p).days if a else max(0, (TODAY - p).days)
        ms.append(
            {
                "name": name,
                "planned": planned,
                "actual": actual,
                "late_days": late,
                "state": "done" if a else ("overdue" if p < TODAY else "upcoming"),
            }
        )
        if not a and next_ms is None:
            next_ms = ms[-1]
        slip_days = max(slip_days, late if not a else 0)
    done = sum(1 for m in ms if m["state"] == "done")
    progress = round(100 * done / len(ms))
    variance = round(100 * (i["spend"] - i["budget"]) / i["budget"], 1)
    if done == len(ms):
        status = "done"
    elif (
        i["depends_on"]
        and any(m["state"] == "overdue" for m in ms)
        and "approval" in (next_ms or {}).get("name", "").lower()
    ):
        status = "blocked"
    elif slip_days > 14:
        status = "delayed"
    elif slip_days > 0 or variance > 0:
        status = "at_risk"
    else:
        status = "on_track"
    return {
        "milestones": ms,
        "progress_pct": progress,
        "schedule_slip_days": slip_days,
        "next_milestone": next_ms,
        "budget_variance_pct": variance,
        "status": status,
    }


def portfolio(principal=None, purpose: str = "llm") -> dict:
    """The portfolio, minimised: contract values banded, personnel ratings excluded, always."""
    granted = principal is not None and principal.role == "procurement" and purpose == "ui"
    out = []
    for i in INITIATIVES:
        c = _calc(i)
        out.append(
            {
                "id": i["id"],
                "dept": i["dept"],
                "name": i["name"],
                "objective": i["objective"],
                "owner": f"{i['owner_title']} — {i['owner_name']}",
                "team": i["team"],
                **c,
                "budget_cents": i["budget"],
                "spend_cents": i["spend"],
                "depends_on": i["depends_on"],
                "risks": i["risks"],
                "expected_value": i["value"],
                "expected_value_cents": i["value_cents"],
                "measured_outcome": i["measured"],
                "vendor_contract": i["vendor_contract_cents"] if granted else _band(i["vendor_contract_cents"]),
                "tech": [{"name": n, "kind": k, "relation": r} for n, k, r in TECH_MAP.get(i["id"], [])],
                "source": SOURCE,
                "provenance": SYN,
            }
        )
    by_dept = {}
    for d in DEPARTMENTS:
        items = [x for x in out if x["dept"] == d]
        if items:
            by_dept[d] = {
                "initiatives": len(items),
                "delayed_or_blocked": sum(x["status"] in ("delayed", "blocked") for x in items),
                "budget_cents": sum(x["budget_cents"] for x in items),
                "spend_cents": sum(x["spend_cents"] for x in items),
            }
    return {
        "initiatives": out,
        "departments": by_dept,
        "approvals": APPROVALS,
        "as_of": TODAY.isoformat(),
        "provenance": SYN,
        "note": SOURCE + ". Owners use synthetic display names. Vendor contract values are "
        "banded; personnel ratings are never shown.",
    }


def find_dept(text: str) -> str | None:
    t = text.lower()
    for d in DEPARTMENTS:
        if d.lower() in t or (d == "Technology" and re.search(r"\b(it|tech|technology team|engineering)\b", t)):
            return d
    return None


def dependents_of(dept_or_team: str) -> list[dict]:
    """Initiatives whose dependencies include work owned by a department/team (e.g. Technology, data engineering)."""
    p = portfolio()["initiatives"]
    key = dept_or_team.lower()
    owners = {x["id"] for x in p if x["dept"].lower() == key or key in x["team"].lower()}
    return [x for x in p if set(x["depends_on"]) & owners]
