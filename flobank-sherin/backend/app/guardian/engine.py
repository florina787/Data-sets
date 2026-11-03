"""Sherin Guardian: deterministic pre-trade investment judgment.

Decision states:
  PASS              - every configured automated control passed. This is NOT authorization to trade.
  REVIEW            - a human must review (near-limit, materiality, weak evidence, advisory challenge).
  BLOCK             - a mandatory restriction is breached. No model and no approver can override it.
  INSUFFICIENT_DATA - inputs needed for a mandatory control are missing.

Advisory input (e.g. a language model's independent challenge) can only *escalate* PASS -> REVIEW. It is never
able to downgrade a BLOCK, REVIEW or INSUFFICIENT_DATA outcome; this is enforced in `decide()` and tested.
"""
from __future__ import annotations

import math
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models as M

RATING_ORDER = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "CC", "C", "D"]
SEVERITY = {"PASS": 0, "REVIEW": 1, "INSUFFICIENT_DATA": 2, "BLOCK": 3}
MEANING = {
    "PASS": "Configured automated controls passed. This is not authorization to trade; human approval is still required.",
    "REVIEW": "Human review required before any action.",
    "BLOCK": "A mandatory restriction is breached. The trade cannot proceed and cannot be approved by any role.",
    "INSUFFICIENT_DATA": "Required data is missing for a mandatory control. Provide the data and re-evaluate.",
}


def _f(x) -> float | None:
    return None if x is None else float(x)


def _check(cid: str, name: str, status: str, detail: str, mandatory: bool = True, value=None, limit=None) -> dict:
    return {"id": cid, "name": name, "status": status, "mandatory": mandatory, "detail": detail, "value": value, "limit": limit}


def decide(checks: list[dict], advisory: list[dict] | None = None) -> str:
    """Combine control outcomes. Advisory items may only escalate PASS to REVIEW."""
    worst = "PASS"
    for c in checks:
        st = c["status"]
        if st == "BLOCK" and not c["mandatory"]:
            st = "REVIEW"
        if SEVERITY[st] > SEVERITY[worst]:
            worst = st
    if worst == "PASS" and any(a.get("concern") for a in (advisory or [])):
        worst = "REVIEW"
    return worst


def evaluate(db: Session, proposal: M.TradeProposal, advisory: list[dict] | None = None) -> dict:
    pf = db.get(M.Portfolio, proposal.portfolio_id)
    if pf is None:
        raise KeyError(proposal.portfolio_id)
    mandate = pf.mandate
    positions = db.scalars(select(M.Position).where(M.Position.portfolio_id == pf.id)).all()
    nav = sum((Decimal(p.market_value_usd) for p in positions), Decimal(0))
    notional = Decimal(proposal.notional_usd)
    sign = Decimal(1) if proposal.side == "BUY" else Decimal(-1)
    checks: list[dict] = []

    # 1. Mandate: asset class
    allowed = mandate.get("allowed_asset_classes", [])
    checks.append(_check("mandate_asset_class", "Investment mandate - asset class",
                         "PASS" if proposal.asset_class in allowed else "BLOCK",
                         f"{proposal.asset_class} {'is' if proposal.asset_class in allowed else 'is not'} permitted ({', '.join(allowed)}).",
                         value=proposal.asset_class, limit=allowed))
    # 2. Restricted list
    restricted = mandate.get("restricted_issuers", [])
    hit = proposal.issuer in restricted
    checks.append(_check("restricted_list", "Restricted issuer list", "BLOCK" if hit and proposal.side == "BUY" else "PASS",
                         f"{proposal.issuer} is on the restricted list." if hit else "Issuer is not restricted.", value=proposal.issuer))
    # 3. Sector exclusions (ESG policy)
    excluded = mandate.get("excluded_sectors", [])
    ex = proposal.sector in excluded and proposal.side == "BUY"
    checks.append(_check("sector_exclusion", "ESG sector exclusion", "BLOCK" if ex else "PASS",
                         f"Sector {proposal.sector} is excluded by mandate." if ex else "Sector not excluded.", value=proposal.sector, limit=excluded))
    # 4/5. Concentration (post-trade)
    issuer_mv = sum((Decimal(p.market_value_usd) for p in positions if p.issuer == proposal.issuer), Decimal(0))
    sector_mv = sum((Decimal(p.market_value_usd) for p in positions if p.sector == proposal.sector), Decimal(0))
    if proposal.side == "SELL" and notional > issuer_mv:
        checks.append(_check("short_sale", "No short selling", "BLOCK",
                             f"Sell notional {float(notional):,.0f} exceeds holding {float(issuer_mv):,.0f}; short sales are not permitted.",
                             value=float(notional), limit=float(issuer_mv)))
    post_nav = nav  # cash-funded trade: NAV is unchanged, only the mix moves
    post_issuer = issuer_mv + sign * notional
    post_sector = sector_mv + sign * notional
    for cid, name, post, lim_key in [("concentration_issuer", "Single-issuer concentration", post_issuer, "max_issuer_pct"),
                                     ("concentration_sector", "Sector concentration", post_sector, "max_sector_pct")]:
        lim = float(mandate.get(lim_key, 100))
        pct = float(post / post_nav * 100) if post_nav else 0.0
        st = "BLOCK" if pct > lim else ("REVIEW" if pct > 0.8 * lim else "PASS")
        checks.append(_check(cid, name, st, f"Post-trade weight {pct:.2f}% vs limit {lim:.1f}%.", value=round(pct, 2), limit=lim))
    # 6. Liquidity
    max_liq = float(mandate.get("max_liquidity_days", 5))
    if proposal.liquidity_days is None:
        checks.append(_check("liquidity", "Liquidity (days to liquidate)", "INSUFFICIENT_DATA", "Liquidity days not provided.", limit=max_liq))
    else:
        ld = float(proposal.liquidity_days)
        st = "BLOCK" if ld > 2 * max_liq else ("REVIEW" if ld > max_liq else "PASS")
        checks.append(_check("liquidity", "Liquidity (days to liquidate)", st, f"{ld:.2f} days vs limit {max_liq:.1f}.", value=ld, limit=max_liq))
    # 7. Credit rating
    min_rating = mandate.get("min_rating", "BBB")
    if not proposal.rating:
        checks.append(_check("credit_rating", "Minimum credit rating", "INSUFFICIENT_DATA", "Rating not provided.", limit=min_rating))
    else:
        ok = RATING_ORDER.index(proposal.rating) <= RATING_ORDER.index(min_rating)
        checks.append(_check("credit_rating", "Minimum credit rating", "PASS" if ok else "BLOCK",
                             f"{proposal.rating} vs minimum {min_rating}.", value=proposal.rating, limit=min_rating))
    # 8. ESG
    min_esg = float(mandate.get("min_esg_score", 0))
    if proposal.esg_score is None:
        checks.append(_check("esg_score", "ESG minimum score", "INSUFFICIENT_DATA" if min_esg > 0 else "PASS",
                             "ESG score not provided." if min_esg > 0 else "No ESG minimum in mandate.", limit=min_esg))
    else:
        es = float(proposal.esg_score)
        checks.append(_check("esg_score", "ESG minimum score", "PASS" if es >= min_esg else "BLOCK", f"Score {es:.1f} vs minimum {min_esg:.1f}.",
                             value=es, limit=min_esg))
    # 9. Market risk (post-trade weighted volatility as a conservative, undiversified upper bound) and 1-day 99% VaR
    max_vol = float(mandate.get("max_portfolio_vol", 1))
    if proposal.volatility is None and proposal.side == "BUY":
        checks.append(_check("market_risk", "Portfolio volatility limit", "INSUFFICIENT_DATA", "Instrument volatility not provided.", limit=max_vol))
        post_vol = None
    else:
        w = {}
        for p in positions:
            w[p.issuer] = (Decimal(p.market_value_usd), float(p.volatility))
        mv0, v0 = w.get(proposal.issuer, (Decimal(0), float(proposal.volatility or 0)))
        w[proposal.issuer] = (mv0 + sign * notional, float(proposal.volatility) if proposal.volatility is not None else v0)
        tot = sum((m for m, _ in w.values()), Decimal(0))
        post_vol = sum(float(m) * v for m, v in w.values()) / float(tot) if tot else 0.0
        st = "BLOCK" if post_vol > 1.25 * max_vol else ("REVIEW" if post_vol > max_vol else "PASS")
        checks.append(_check("market_risk", "Portfolio volatility limit", st, f"Post-trade weighted volatility {post_vol:.2%} vs limit {max_vol:.2%}.",
                             value=round(post_vol, 4), limit=max_vol))
    var99 = float(nav) * (post_vol or 0) / math.sqrt(252) * 2.326 if post_vol is not None else None
    # 10. Evidence validation / independent challenge (deterministic)
    ev = proposal.evidence or []
    checks.append(_check("evidence", "Evidence validation", "PASS" if len(ev) >= 2 else "REVIEW",
                         f"{len(ev)} evidence item(s) supplied; at least 2 independent sources required." if len(ev) < 2 else f"{len(ev)} evidence items supplied.",
                         mandatory=False, value=len(ev), limit=2))
    # 11. Materiality -> human escalation
    material = float(notional) >= float(mandate.get("material_trade_usd", 1e12))
    checks.append(_check("materiality", "Material trade escalation", "REVIEW" if material else "PASS",
                         f"Notional {float(notional):,.0f} {'meets' if material else 'is below'} the materiality threshold {float(mandate.get('material_trade_usd', 0)):,.0f}.",
                         mandatory=False, value=float(notional), limit=mandate.get("material_trade_usd")))

    decision = decide(checks, advisory)
    exposures = _exposures(positions, proposal, sign * notional, nav)
    return {"proposal_id": proposal.id, "portfolio_id": pf.id, "portfolio": pf.name, "decision": decision, "meaning": MEANING[decision],
            "checks": checks, "advisory": advisory or [], "material": material,
            "risk": {"nav_usd": float(nav), "post_trade_volatility": post_vol, "var_99_1d_usd": round(var99, 2) if var99 is not None else None},
            "exposures": exposures, "data_class": proposal.data_class,
            "note": "Guardian does not estimate or claim losses prevented. Mandatory restrictions cannot be overridden by a model or by approval."}


def _exposures(positions, proposal, delta: Decimal, nav: Decimal) -> dict:
    by_issuer, by_sector = {}, {}
    for p in positions:
        by_issuer[p.issuer] = by_issuer.get(p.issuer, 0.0) + float(p.market_value_usd)
        by_sector[p.sector] = by_sector.get(p.sector, 0.0) + float(p.market_value_usd)
    post_i, post_s = dict(by_issuer), dict(by_sector)
    post_i[proposal.issuer] = post_i.get(proposal.issuer, 0.0) + float(delta)
    post_s[proposal.sector] = post_s.get(proposal.sector, 0.0) + float(delta)
    n = float(nav) or 1.0
    return {"by_sector": [{"sector": k, "pre_pct": round(by_sector.get(k, 0) / n * 100, 2), "post_pct": round(v / n * 100, 2)} for k, v in sorted(post_s.items(), key=lambda kv: -kv[1])],
            "by_issuer": [{"issuer": k, "pre_pct": round(by_issuer.get(k, 0) / n * 100, 2), "post_pct": round(v / n * 100, 2)} for k, v in sorted(post_i.items(), key=lambda kv: -kv[1])][:12]}
