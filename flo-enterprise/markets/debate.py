"""Bull, bear and skeptic reasoning over ONE point-in-time evidence pack, plus the evidence aggregator.

Every claim cites evidence ids (feature@date, headline id, report field), so the aggregator can keep source attribution.
Nothing is invented: a claim exists only if a measured value crosses a stated threshold. The skeptic always runs and
states what the evidence cannot support. Percentiles are cross-sectional within the point-in-time universe.
"""
from __future__ import annotations

from datetime import date


def _pct(rk: float | None) -> float | None:
    return None if rk is None else round((rk + 0.5) * 100, 1)


def _claim(text: str, refs: list[str], kind: str) -> dict:
    return {"claim": text, "evidence": refs, "kind": kind}


def bull_claims(ev: dict) -> list[dict]:
    f, d, out = ev["features"], ev["as_of"], []
    if (p := _pct(f.get("mom_12_1_rk"))) is not None and p >= 70:
        out.append(_claim(f"12-1 month momentum is in the {p:.1f}th percentile of the 1,000-stock universe.", [f"feature:mom_12_1@{d}"], "price"))
    if f.get("dist_ma200") is not None and f["dist_ma200"] > 0:
        out.append(_claim(f"Price is {f['dist_ma200'] * 100:.1f}% above its 200-session average.", [f"feature:dist_ma200@{d}"], "price"))
    if f.get("dd_252") is not None and f["dd_252"] > -0.05:
        out.append(_claim(f"Within {abs(f['dd_252']) * 100:.1f}% of its 252-session high.", [f"feature:dd_252@{d}"], "price"))
    n = ev.get("news") or {}
    c = n.get("event_counts", {})
    pos = c.get("upgrade", 0) + c.get("price_target_raise", 0)
    neg = c.get("downgrade", 0) + c.get("price_target_cut", 0)
    if pos > neg:
        ids = [i["id"] for i in n.get("items", []) if i["event_type"] in ("upgrade", "price_target_raise")][:3]
        out.append(_claim(f"{pos} analyst upgrades or target raises versus {neg} downgrades or cuts in the last {n.get('window_days')} days.",
                          ids or [f"news:{ev['ticker']}@{d}"], "news"))
    m = ev.get("model_score")
    if m and m.get("rank_pct") is not None and m["rank_pct"] >= 0.8:
        out.append(_claim(f"The research model ranked it in the top {100 - m['rank_pct'] * 100:.0f}% on {m['date'][:10]} (model not validated).",
                          [f"model:{m.get('model_version')}@{m['date'][:10]}"], "model"))
    return out


def bear_claims(ev: dict) -> list[dict]:
    f, d, out = ev["features"], ev["as_of"], []
    if (p := _pct(f.get("vol_20_rk"))) is not None and p >= 80:
        out.append(_claim(f"20-session volatility is in the {p:.1f}th percentile ({f['vol_20'] * 252 ** 0.5 * 100:.1f}% annualised).",
                          [f"feature:vol_20@{d}"], "risk"))
    if f.get("dd_252") is not None and f["dd_252"] < -0.2:
        out.append(_claim(f"Trading {abs(f['dd_252']) * 100:.1f}% below its 252-session high.", [f"feature:dd_252@{d}"], "price"))
    if f.get("dist_ma200") is not None and f["dist_ma200"] < 0:
        out.append(_claim(f"Price is {abs(f['dist_ma200']) * 100:.1f}% below its 200-session average.", [f"feature:dist_ma200@{d}"], "price"))
    if (p := _pct(f.get("mom_12_1_rk"))) is not None and p <= 30:
        out.append(_claim(f"12-1 month momentum is only in the {p:.1f}th percentile.", [f"feature:mom_12_1@{d}"], "price"))
    if (p := _pct(f.get("ret_5_rk"))) is not None and p >= 90:
        out.append(_claim(f"5-session return is in the {p:.1f}th percentile; short-term reversal has historically followed extreme moves.",
                          [f"feature:ret_5@{d}"], "price"))
    n = ev.get("news") or {}
    c = n.get("event_counts", {})
    pos = c.get("upgrade", 0) + c.get("price_target_raise", 0)
    neg = c.get("downgrade", 0) + c.get("price_target_cut", 0)
    if neg > pos:
        ids = [i["id"] for i in n.get("items", []) if i["event_type"] in ("downgrade", "price_target_cut")][:3]
        out.append(_claim(f"{neg} analyst downgrades or target cuts versus {pos} upgrades or raises in the last {n.get('window_days')} days.",
                          ids or [f"news:{ev['ticker']}@{d}"], "news"))
    m = ev.get("model_score")
    if m and m.get("rank_pct") is not None and m["rank_pct"] <= 0.2:
        out.append(_claim(f"The research model ranked it in the bottom {m['rank_pct'] * 100:.0f}% on {m['date'][:10]} (model not validated).",
                          [f"model:{m.get('model_version')}@{m['date'][:10]}"], "model"))
    return out


def skeptic_checks(ev: dict, report: dict | None, today: date) -> list[dict]:
    d = ev["as_of"]
    out = [_claim(f"The evidence is historical: the dataset ends on {d}, {(today - date.fromisoformat(d)).days} days ago. It says nothing about today.",
                  [f"dataset:{ev['dataset_id']}"], "staleness"),
           _claim("The universe only contains companies that survived to 2017; delisted names are missing, which flatters historical returns.",
                  [f"dataset:{ev['dataset_id']}#survivorship"], "bias"),
           _claim("Signals use price and volume only; fundamentals without filing dates are excluded to avoid look-ahead.",
                  ["dataset:kaggle-nyse-sp500-v3#fundamentals"], "coverage")]
    if report:
        h = report["horizons"].get("5") or next(iter(report["horizons"].values()))
        best = h["best_by_ic"]
        mm = h["models"][best]
        out.append(_claim(f"Model verdict: {report['verdict']}. The best 5-session model ({best}) had holdout rank IC {mm['ic_mean']:.4f} "
                          f"and long/short net Sharpe {mm['net_sharpe']:.2f} after costs.",
                          [f"report:horizons.5.models.{best}.ic_mean", f"report:horizons.5.models.{best}.net_sharpe"], "validation"))
    n = ev.get("news") or {}
    cov = n.get("coverage", {})
    if n.get("headlines_in_window", 0) == 0:
        out.append(_claim(f"No headlines for {ev['ticker']} in this window; coverage for this ticker runs {cov.get('first', '?')[:10]} to "
                          f"{cov.get('last', '?')[:10]}. Absence of headlines is not absence of news.", [f"news:{ev['ticker']}#coverage"], "coverage"))
    else:
        out.append(_claim("Headlines come from one publisher family and most carry dates without times; they are context, not proof of cause.",
                          [f"news:{ev['ticker']}#coverage"], "coverage"))
    missing = [k for k, v in ev["features"].items() if v is None]
    if missing:
        out.append(_claim(f"Missing inputs on this date: {', '.join(missing)}.", [f"feature:{k}@{d}" for k in missing], "missing_data"))
    if not ev.get("in_universe"):
        out.append(_claim("This name was outside the liquid research universe on this date, so model results do not apply to it.",
                          [f"universe@{d}"], "scope"))
    return out


def aggregate(ev: dict, report: dict | None, risk: dict, today: date) -> dict:
    bull, bear, skeptic = bull_claims(ev), bear_claims(ev), skeptic_checks(ev, report, today)
    validated = bool(report) and report["verdict"] != "NO VALIDATED TRADING EDGE"
    if not validated:
        conclusion = ("No validated trading edge: the evidence below describes the stock's history; it is not a forecast or a recommendation.")
    else:
        conclusion = "A model passed validation; its output still requires human approval and current data before use."
    refs = sorted({r for c in bull + bear + skeptic for r in c["evidence"]})
    return {"ticker": ev["ticker"], "as_of": ev["as_of"], "bull": bull, "bear": bear, "skeptic": skeptic, "risk": risk,
            "balance": {"bull_points": len(bull), "bear_points": len(bear), "skeptic_points": len(skeptic)},
            "conclusion": conclusion, "validated_edge": validated, "evidence_refs": refs}
