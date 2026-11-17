"""Simulated-clock replay over the holdout period.

Purpose: exercise Prediction Memory end-to-end (record before outcome, resolve
after) and produce dashboard artefacts. The memory clock is the *simulated*
time, every record is strategy_id ``replay:*`` with the dataset's DataStatus, so
replay results can never be mistaken for live forward-tested predictions.

The model is fit once on data whose labels end before the first replay date
(purged), so no replayed forecast has seen its own outcome.
"""
from __future__ import annotations

import argparse
import json
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from flowwealth.contracts import DataStatus, Horizon, PredictionIn
from flowwealth.data.lake import DataLake
from flowwealth.evaluation.monitor import evaluate_records, psi
from flowwealth.features.build import FEATURES, build_features, feature_columns
from flowwealth.memory.store import PredictionMemory
from flowwealth.models.forecasters import LightGBMForecaster
from flowwealth.risk.regime import classify, evaluate_alarm, indicators, market_index
from flowwealth.validation.splits import chronological_split


class SimClock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


def run(lake_root: Path, version: str, out: Path, horizon: int = 5, n_steps: int = 40, per_step: int = 20) -> dict:
    lake = DataLake(lake_root)
    man = lake.manifest(version)
    status = DataStatus(next(iter(man["status_counts"])))
    bars = lake.connect(version).execute("SELECT * FROM bars ORDER BY ticker, ts").fetchdf()
    sec = lake.connect(version).execute("SELECT * FROM securities").fetchdf()
    f = build_features(bars, horizons=(horizon,))
    X = feature_columns()
    data = f.dropna(subset=X[:5]).reset_index(drop=True)
    sp = chronological_split(data, f"label_end_{horizon}", embargo_days=2 * horizon)
    dev = data.iloc[np.concatenate([sp["train"], sp["validation"]])].dropna(subset=[f"fwd_xs_{horizon}"])
    model = LightGBMForecaster().fit(dev[X], dev[f"fwd_xs_{horizon}"])
    model_version = f"{model.name}@{model.version}+{version}"

    hold = data.iloc[sp["holdout"]]
    dates = np.sort(hold.ts.dt.normalize().unique())
    step_dates = dates[::horizon][:n_steps]
    out.mkdir(parents=True, exist_ok=True)
    db = out / "prediction_memory.db"
    if db.exists():
        db.unlink()
    clock = SimClock(pd.Timestamp(step_dates[0]).to_pydatetime())
    mem = PredictionMemory(db, clock=clock)
    px = bars.set_index(["ticker", "ts"])["adj_close"].sort_index()
    idx_ret = market_index(bars)

    def lookup(ticker, start, end):
        s = px.loc[ticker]
        a, b = s[s.index <= pd.Timestamp(start)], s[s.index <= pd.Timestamp(end)]
        if a.empty or b.empty:
            return None
        bench = idx_ret[(idx_ret.index > pd.Timestamp(start).normalize()) & (idx_ret.index <= pd.Timestamp(end).normalize())].sum()
        return {"return": float(np.log(b.iloc[-1] / a.iloc[-1])), "benchmark_return": float(bench)}

    sec_map = sec.set_index("ticker")
    regimes = classify(indicators(idx_ret))["regime"]
    for d in step_dates:
        g = hold[hold.ts.dt.normalize() == d].copy()
        g["pred"] = model.predict(g[X])
        picks = pd.concat([g.nlargest(per_step // 2, "pred"), g.nsmallest(per_step // 2, "pred")])
        # simulated "now" = latest availability among inputs on that date
        clock.t = pd.Timestamp(g.available_at.max()).to_pydatetime()
        mem.resolve_due(lookup, f"lake:{version}")
        for _, r in picks.iterrows():
            tgt = pd.Timestamp(r.ts) + timedelta(days=int(horizon * 1.4) + 3)
            mem.record(PredictionIn(
                model_version=model_version, strategy_id=f"replay:xs_{horizon}d", ticker=r.ticker,
                horizon=Horizon.SWING, horizon_bars=horizon, input_cutoff=pd.Timestamp(r.available_at).to_pydatetime(),
                target_time=tgt.to_pydatetime(), regime=str(regimes.get(pd.Timestamp(d), "unknown")), forecast_return=float(r.pred),
                prob_up=None, calibrated=False, data_status=status,
                sources=[f"lake:{version}:{man['content_sha256'][:12]}"],
                bull_thesis="", bear_thesis="", risk_assessment="pre-trade risk engine not applied in replay"))
    clock.t = pd.Timestamp(dates[-1]).to_pydatetime() + timedelta(days=1)
    mem.resolve_due(lookup, f"lake:{version}")
    ok, _ = mem.verify_chain()
    records = mem.joined()
    evaluation = evaluate_records(records)

    # Rankings snapshot on the latest date (methodology spelled out)
    last = data[data.ts.dt.normalize() == data.ts.dt.normalize().max()].copy()
    last["pred"] = model.predict(last[X])
    last = last.join(sec_map[["exchange", "sector", "country"]], on="ticker")
    contrib = {c: float(last[c].corr(last["pred"])) for c in X}
    rank_cols = ["ticker", "exchange", "sector", "country", "adj_close", "ts", "pred", "vol_20", "ret_20", "dd_60"]
    top = last.nlargest(10, "pred")[rank_cols]
    rankings = {
        "horizon": f"{horizon} trading days (swing)", "as_of": str(last.ts.max()), "data_status": status.value,
        "model_version": model_version, "target": f"cross-sectional excess log return over {horizon} bars",
        "methodology": "LightGBM on 10 rank-normalised price/volume features; ranked by predicted excess return. "
                       "Not calibrated: no confidence is shown. Holdout evidence is in the experiment report.",
        "feature_correlation_with_score": contrib,
        "items": top.astype({"ts": str}).to_dict("records"),
    }

    # Crash-risk history + alarm evaluation
    ind = indicators(idx_ret, bars)  # breadth/dispersion included for the dashboard
    lv = classify(ind)
    crash = {"as_of": str(lv.index.max()), "data_status": status.value, "current": lv.iloc[-1].to_dict(),
             "inputs": ind.iloc[-1].round(4).to_dict(),
             "history": [{"date": str(i.date()), "level": r.level, "score": int(r.score)} for i, r in lv.iloc[-260:].iterrows()],
             "evaluation": [evaluate_alarm(lv["level"], idx_ret, alarm_from=a) for a in ("Elevated", "High")],
             "index": [{"date": str(i.date()), "value": float(v)} for i, v in np.exp(idx_ret.cumsum()).iloc[-520:].items()]}

    drift = {c: psi(dev[c].to_numpy(), hold[c].to_numpy()) for c in FEATURES}
    summary = {"model_version": model_version, "dataset_version": version, "data_status": status.value,
               "replay_steps": len(step_dates), "predictions": len(records), "chain_verified": ok,
               "evaluation": evaluation, "feature_drift_psi_dev_vs_holdout": drift}
    for name, obj in [("rankings.json", rankings), ("crash_risk.json", crash), ("memory_summary.json", summary)]:
        (out / name).write_text(json.dumps(obj, indent=2, default=str))
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lake", default="lake")
    ap.add_argument("--version", default="syn-v1")
    ap.add_argument("--out", default="artifacts")
    a = ap.parse_args()
    s = run(Path(a.lake), a.version, Path(a.out))
    print(json.dumps({k: v for k, v in s.items() if k != "feature_drift_psi_dev_vs_holdout"}, indent=2, default=str)[:3000])


if __name__ == "__main__":
    main()
