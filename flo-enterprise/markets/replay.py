"""Historical replay into Prediction Memory, using the research candidate model (NOT a promoted model).

1. Fit the validation-chosen 5-session LightGBM on TRAIN only and predict VALIDATION: the realised dispersion of outcomes per
   predicted decile becomes each prediction's uncertainty (a measured band, not a confidence score).
2. Refit on TRAIN + VALIDATION and predict the untouched HOLDOUT; save holdout_predictions.parquet (used by evidence packs).
3. Walk a simulated clock over the last N rebalance dates of the holdout: at each date record every in-universe name's
   forecast (mode=historical_replay) BEFORE its outcome date, then resolve due forecasts from lake prices.

The replay demonstrates the ledger mechanics on real data. It is not a forward test and is labelled as such everywhere.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from backend.db.session import session_scope
from markets import catalog, config, ledger, research, service

H = 5


def _utc(x) -> datetime:
    """Lake timestamps are UTC; DuckDB may hand them back naive. Make that explicit before they reach the ledger."""
    t = pd.Timestamp(x)
    return (t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")).to_pydatetime()


def _version(params: dict) -> str:
    rep = json.loads((config.REPORTS_DIR / "experiment.json").read_text())
    tag = hashlib.sha256(json.dumps([params, rep["dataset_content_sha256"], rep["generated_at"]], sort_keys=True).encode()).hexdigest()[:8]
    return f"lightgbm-h{H}-candidate@{tag}"


def run(n_dates: int = 40) -> dict:
    t0 = time.perf_counter()
    rep = json.loads((config.REPORTS_DIR / "experiment.json").read_text())
    params = rep["horizons"][str(H)]["tuning"]["lightgbm"]["chosen"]
    version = _version(params)
    y = f"fwd_xs_{H}"
    cols = ["ticker", "date", "available_at", "adv_usd", "vol_20"] + research.FEATURE_COLS + \
        [c for h in research.HORIZONS for c in (f"fwd_ret_{h}", f"fwd_xs_{h}", f"spy_fwd_{h}", f"label_end_{h}")]
    df = research.load_universe(cols)
    sp = research.chronological_split(df, H)
    tr, va, ho = (df.iloc[sp[k]] for k in ("train", "validation", "holdout"))
    # uncertainty from validation residual dispersion per predicted decile
    m1 = research.LGBM(**params).fit(tr.dropna(subset=[y])[research.FEATURE_COLS], tr.dropna(subset=[y])[y])
    pv = m1.predict(va[research.FEATURE_COLS])
    vdf = pd.DataFrame({"p": pv, "a": va[y].to_numpy(), "d": va["date"].to_numpy()}).dropna()
    vdf["dec"] = vdf.groupby("d")["p"].rank(pct=True).mul(10).clip(upper=9.999).astype(int)
    band = vdf.groupby("dec")["a"].std().to_dict()
    dev = pd.concat([tr, va]).dropna(subset=[y])
    m2 = research.LGBM(**params).fit(dev[research.FEATURE_COLS], dev[y])
    ph = m2.predict(ho[research.FEATURE_COLS])
    out = ho[["ticker", "date", "available_at", f"label_end_{H}"]].copy()
    out["pred"] = ph
    out["rank_pct"] = out.groupby("date")["pred"].rank(pct=True)
    out["uncertainty"] = (out["rank_pct"].mul(10).clip(upper=9.999).astype(int)).map(band)
    out["model_version"] = version
    out[["ticker", "date", "model_version", "pred", "rank_pct", "uncertainty"]].to_parquet(config.REPORTS_DIR / "holdout_predictions.parquet", index=False)
    # simulated-clock replay into the ledger
    dates = np.sort(out["date"].unique())[::H][-n_dates:]
    px = service._q("SELECT ticker, date, adj_close FROM bars WHERE quality_flag IN ('ok','zero_volume') AND date >= ?", [str(pd.Timestamp(dates[0]).date())])
    px = px.set_index(["ticker", "date"])["adj_close"].sort_index()
    spy = px.loc[config.BENCHMARK]
    sessions = list(service._q("SELECT date FROM sessions WHERE date >= ? ORDER BY date", [str(pd.Timestamp(dates[0]).date())]).date)

    def lookup(ticker, cutoff, due, h):
        d0 = pd.Timestamp(cutoff.date())
        try:
            i = sessions.index(d0)
        except ValueError:
            return None
        if i + h >= len(sessions):
            return None
        d1 = sessions[i + h]
        try:
            a0, a1 = px.loc[(ticker, d0)], px.loc[(ticker, d1)]
        except KeyError:
            return {"return": None, "benchmark_return": None}
        return {"return": float(np.log(a1 / a0)), "benchmark_return": float(np.log(spy.loc[d1] / spy.loc[d0]))}

    recorded = resolved = 0
    for d in dates:
        g = out[out["date"] == d]
        clock = _utc(g["available_at"].max()) + pd.Timedelta(minutes=1)
        with session_scope() as s:
            resolved += ledger.resolve_due(s, now=clock, lookup=lookup, source=f"lake:{catalog.PRIMARY}")
            for r in g.itertuples():
                due = _utc(getattr(r, f"label_end_{H}")) if pd.notna(getattr(r, f"label_end_{H}")) else None
                if due is None:
                    continue
                ledger.record(s, now=clock, mode="historical_replay", model_version=version, dataset_version=catalog.PRIMARY, ticker=r.ticker,
                              horizon_sessions=H, feature_cutoff=_utc(r.available_at),
                              outcome_due=due, predicted_excess_return=float(r.pred), predicted_rank_pct=float(r.rank_pct),
                              uncertainty=None if pd.isna(r.uncertainty) else float(r.uncertainty), regime=service.regime_at(r.date),
                              evidence={"features": research.FEATURE_COLS, "target": y, "model_status": "research candidate, not promoted",
                                        "verdict": rep["verdict"]})
                recorded += 1
    final = datetime(2017, 11, 11, tzinfo=timezone.utc)
    with session_scope() as s:
        resolved += ledger.resolve_due(s, now=final, lookup=lookup, source=f"lake:{catalog.PRIMARY}")
        summ = ledger.summary(s)
    res = {"model_version": version, "params": params, "uncertainty_band_by_decile": band, "replay_dates": [str(pd.Timestamp(x).date()) for x in dates],
           "recorded": recorded, "resolved": resolved, "summary": {k: v for k, v in summ.items() if k != "groups"},
           "mode_group": summ["groups"].get("mode:historical_replay"), "seconds": round(time.perf_counter() - t0, 1)}
    (config.REPORTS_DIR / "replay.json").write_text(json.dumps(res, indent=1, default=str))
    return res


if __name__ == "__main__":
    print(json.dumps(run(), indent=1, default=str)[:2500])
