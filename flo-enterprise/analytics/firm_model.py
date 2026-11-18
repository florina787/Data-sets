"""Preliminary firm model for a prospective client who describes their own advisory business.

Every figure is either user-supplied, calculated from user-supplied inputs, or derived from an explicitly labelled
planning assumption. Nothing here is a benchmark, forecast or statement about any real firm, and no ROI or
probability is produced. Sensitivities are plain arithmetic (e.g. revenue per basis point of fee on the stated AUM).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal

# Illustrative planning range for an average management-fee rate when the user has not supplied one. Shown as a range
# with its midpoint labelled as an assumption; it is not a market benchmark.
FEE_RANGE_BPS = (50, 75, 100)
MARKET_MOVES = (-0.20, -0.10, 0.10)

FIELDS = {"aum": "Assets under management", "fee_bps": "Average fee rate", "revenue": "Annual revenue", "expenses": "Annual operating expenses",
          "advisors": "Number of advisors", "clients": "Number of client households", "net_flows": "Annual net client flows"}
DISCOVERY = {
    "fee_bps": "What is your average all-in fee rate (for example 0.85% or 85 bps), or your annual fee revenue?",
    "revenue": "What was your total revenue over the last 12 months?",
    "expenses": "What were your operating expenses over the last 12 months (compensation, technology, rent, compliance, other)?",
    "advisors": "How many advisors serve clients, and how are books assigned?",
    "clients": "How many client households do you serve, and how are they segmented by asset size?",
    "net_flows": "What were your net client flows (new money minus withdrawals) over the last 12 months?",
}
ALWAYS_ASK = [
    "What is your product and service mix (discretionary portfolios, mutual funds, ETFs, planning fees)?",
    "Which systems hold your data today (CRM, custodian or portfolio accounting, general ledger)?",
    "What are your top business priorities for the next 12 months: growth, margin, client experience or efficiency?",
]
INTEGRATIONS = [
    {"system": "CRM", "data": "households, segments, interactions, pipeline", "enables": "client segmentation, retention, advisor productivity"},
    {"system": "Custodian / portfolio accounting", "data": "positions, transactions, valuations", "enables": "AUM, flows, concentration, performance"},
    {"system": "General ledger / ERP", "data": "revenue and expense by line", "enables": "profitability, expense structure, margin"},
    {"system": "Fee billing", "data": "fee schedules and billed fees", "enables": "revenue yield and pricing analysis"},
]
MODULES = [("Total AUM", ("aum",)), ("Estimated fee revenue", ("aum", "fee_bps")), ("Net inflows", ("net_flows",)),
           ("Client segmentation", ("clients",)), ("Advisor productivity", ("advisors", "aum")), ("Revenue mix", ()),
           ("Operating expense structure", ("expenses",)), ("Profitability", ("revenue|fee_bps", "expenses")), ("Investment concentration", ()),
           ("Client retention", ()), ("Scenario analysis", ("aum",))]


@dataclass
class FirmProfile:
    aum: Decimal | None = None
    fee_bps: Decimal | None = None
    revenue: Decimal | None = None
    expenses: Decimal | None = None
    advisors: int | None = None
    clients: int | None = None
    net_flows: Decimal | None = None


def _r(x: Decimal | None, nd: int = 2) -> float | None:
    return None if x is None else round(float(x), nd)


def _has(p: FirmProfile, need: str) -> bool:
    return any(getattr(p, k) is not None for k in need.split("|"))


def assess(p: FirmProfile) -> dict:
    known = [k for k in FIELDS if getattr(p, k) is not None]
    missing = [k for k in FIELDS if getattr(p, k) is None]
    out: dict = {"profile": {k: (_r(v) if isinstance(v, Decimal) else v) for k, v in asdict(p).items()},
                 "known": known, "missing": missing, "metrics": [], "assumptions": [], "sensitivities": {}, "market_scenarios": []}
    m = out["metrics"]

    def metric(key, label, value, unit, provenance, basis):
        m.append({"key": key, "label": label, "value": _r(value, 4 if unit in ("ratio", "%") else 2), "unit": unit,
                  "provenance": provenance, "basis": basis})

    if p.aum is not None:
        metric("aum", "Assets under management", p.aum, "CAD", "user_supplied", "Stated by you")
    fee, fee_prov = None, None
    if p.revenue is not None:
        metric("revenue", "Annual revenue", p.revenue, "CAD", "user_supplied", "Stated by you")
        if p.aum:
            fee, fee_prov = p.revenue / p.aum * 10000, "calculated_from_user_inputs"
            metric("revenue_yield_bps", "Revenue yield", fee, "bps", fee_prov, "Annual revenue / AUM x 10,000")
    elif p.fee_bps is not None:
        fee, fee_prov = p.fee_bps, "user_supplied"
        if p.aum is not None:
            metric("revenue", "Estimated annual fee revenue", p.aum * p.fee_bps / 10000, "CAD", "calculated_from_user_inputs",
                   "AUM x stated average fee rate")
    elif p.aum is not None:
        lo, mid, hi = (p.aum * Decimal(b) / 10000 for b in FEE_RANGE_BPS)
        fee, fee_prov = Decimal(FEE_RANGE_BPS[1]), "illustrative_assumption"
        metric("revenue", "Illustrative annual fee revenue (midpoint)", mid, "CAD", "illustrative_assumption",
               f"AUM x {FEE_RANGE_BPS[1]} bps planning assumption; range CAD {_r(lo):,.0f} to CAD {_r(hi):,.0f} at {FEE_RANGE_BPS[0]}-{FEE_RANGE_BPS[2]} bps")
        out["assumptions"].append({"name": "average_fee_bps", "value": FEE_RANGE_BPS[1], "unit": "bps", "source": "illustrative planning assumption",
                                   "note": f"Replace with your actual fee rate; range shown {FEE_RANGE_BPS[0]}-{FEE_RANGE_BPS[2]} bps."})
        out["fee_range"] = [{"fee_bps": b, "revenue": _r(p.aum * Decimal(b) / 10000)} for b in FEE_RANGE_BPS]
    revenue = p.revenue if p.revenue is not None else (p.aum * p.fee_bps / 10000 if p.aum is not None and p.fee_bps is not None else None)
    if p.expenses is not None:
        metric("expenses", "Annual operating expenses", p.expenses, "CAD", "user_supplied", "Stated by you")
        if revenue:
            metric("operating_margin", "Operating margin", (revenue - p.expenses) / revenue, "ratio", "calculated_from_user_inputs",
                   "(revenue - operating expenses) / revenue")
            metric("operating_income", "Operating income", revenue - p.expenses, "CAD", "calculated_from_user_inputs", "revenue - operating expenses")
    if p.advisors:
        if p.aum is not None:
            metric("aum_per_advisor", "AUM per advisor", p.aum / p.advisors, "CAD", "calculated_from_user_inputs", "AUM / advisors")
        if revenue is not None:
            metric("revenue_per_advisor", "Revenue per advisor", revenue / p.advisors, "CAD", "calculated_from_user_inputs", "revenue / advisors")
        if p.clients:
            metric("clients_per_advisor", "Client households per advisor", Decimal(p.clients) / p.advisors, "count", "calculated_from_user_inputs",
                   "client households / advisors")
    if p.clients and p.aum is not None:
        metric("aum_per_client", "Average AUM per household", p.aum / p.clients, "CAD", "calculated_from_user_inputs", "AUM / client households")
    if p.net_flows is not None:
        metric("net_flows", "Annual net client flows", p.net_flows, "CAD", "user_supplied", "Stated by you")
        if p.aum:
            metric("organic_growth", "Organic growth rate", p.net_flows / p.aum, "ratio", "calculated_from_user_inputs", "net flows / AUM")
    if p.aum is not None and fee is not None:
        prov = "calculated_from_user_inputs" if fee_prov != "illustrative_assumption" else "illustrative_assumption"
        out["sensitivities"] = {
            "fee_bps_used": _r(fee), "fee_provenance": fee_prov,
            "revenue_per_1bp_fee": _r(p.aum / 10000), "revenue_per_1pct_net_new_assets": _r(p.aum * Decimal("0.01") * fee / 10000),
            "provenance": prov,
            "explanation": "Arithmetic on your stated AUM: each 1 bp of average fee changes annual revenue by AUM / 10,000; each 1% of AUM "
                           "added through net new assets adds that amount times the fee rate. These are not forecasts.",
        }
        for mv in MARKET_MOVES:
            aum1 = p.aum * Decimal(str(1 + mv))
            out["market_scenarios"].append({"market_move": mv, "aum": _r(aum1), "annual_fee_revenue": _r(aum1 * fee / 10000), "provenance": prov})
    out["data_readiness"] = [{"module": name, "status": "available" if need and all(_has(p, n) for n in need) else "needs_data",
                              "needs": [FIELDS.get(n.split("|")[0], n) for n in need if not _has(p, n)] if need else ["data integration"]}
                             for name, need in MODULES]
    out["discovery_questions"] = [DISCOVERY[k] for k in DISCOVERY if k in missing][:4] + ALWAYS_ASK
    out["integrations"] = INTEGRATIONS
    out["disclaimer"] = ("Preliminary assessment built from the figures you provided and clearly labelled planning assumptions. It is not an "
                         "audit, valuation, forecast or investment advice, and it does not use any other firm's data.")
    return out
