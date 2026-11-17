"""Research experiment: walk-forward model selection, then one untouched holdout.

1. Build leakage-safe features/labels from a lake version (as of the lake's end).
2. Chronological 60/20/20 split with purge + embargo.
3. Walk-forward folds inside train+validation compare every forecaster.
4. Holdout is scored exactly once per model, gross and net of costs.
5. Results + config are written as JSON/Markdown; nothing is promoted automatically.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from flowwealth.data.lake import DataLake
from flowwealth.features.build import build_features, feature_columns
from flowwealth.models.forecasters import (LightGBMForecaster, MomentumBaseline, RidgeForecaster,
                                           ShortReversalBaseline, ZeroBaseline)
from flowwealth.research.backtest import run_backtest
from flowwealth.research.metrics import directional_accuracy, information_coefficient
from flowwealth.validation.splits import chronological_split, walk_forward


def default_models():
    return [ZeroBaseline(), MomentumBaseline(), ShortReversalBaseline(), RidgeForecaster(), LightGBMForecaster()]


def run(lake_root: Path, version: str, horizon: int = 5, out: Path | None = None, n_folds: int = 4) -> dict:
    t0 = time.perf_counter()
    lake = DataLake(lake_root)
    manifest = lake.manifest(version)
    con = lake.connect(version)
    bars = con.execute("SELECT * FROM bars ORDER BY ticker, ts").df()
    feats = build_features(bars, horizons=(horizon,))
    feats["adv_usd"] = (bars["close"] * bars["volume"]).groupby(bars["ticker"]).transform(
        lambda s: s.rolling(20, min_periods=10).mean()).to_numpy()
    X_cols = feature_columns()
    y_col, end_col = f"fwd_xs_{horizon}", f"label_end_{horizon}"
    data = feats.dropna(subset=X_cols[:5]).reset_index(drop=True)
    t_feat = time.perf_counter() - t0

    split = chronological_split(data, end_col, embargo_days=horizon * 2)
    dev = data.iloc[np.concatenate([split["train"], split["validation"]])].reset_index(drop=True)
    hold = data.iloc[split["holdout"]].reset_index(drop=True)

    def eval_on(model, train_df, test_df):
        tr = train_df.dropna(subset=[y_col])
        model.fit(tr[X_cols], tr[y_col])
        pred = pd.Series(model.predict(test_df[X_cols]), index=test_df.index)
        ic = information_coefficient(pred, test_df[y_col], test_df["available_at"])  # per availability cohort
        return pred, ic

    wf_rows = []
    for fold in walk_forward(dev, end_col, n_folds=n_folds, embargo_days=horizon * 2):
        tr, te = dev.iloc[fold.train_idx], dev.iloc[fold.test_idx]
        for m in default_models():
            _, ic = eval_on(m, tr, te)
            wf_rows.append({"fold": fold.name, "model": m.name, "train_end": str(fold.train_end.date()),
                            "test_start": str(fold.test_start.date()), "test_end": str(fold.test_end.date()),
                            "n_train": len(tr), "n_test": len(te), **ic})
    wf = pd.DataFrame(wf_rows)
    wf_summary = wf.groupby("model").agg(ic_mean=("ic_mean", "mean"), ic_min=("ic_mean", "min"),
                                         folds_positive=("ic_mean", lambda s: int((s > 0).sum()))).reset_index()

    holdout = {}
    for m in default_models():
        pred, ic = eval_on(m, dev, hold)
        h = hold.assign(signal=pred.to_numpy())
        bt = run_backtest(h, "signal", f"fwd_ret_{horizon}", horizon) if m.name != "zero" else None
        holdout[m.name] = {"ic": ic, "directional_accuracy_vs_xs": directional_accuracy(pred, hold[y_col]),
                           "backtest_long_short": bt.summary() if bt else None,
                           "params": m.params(), "version": m.version}
        if m.name == "lightgbm":
            holdout[m.name]["feature_importance"] = m.feature_importance()

    report = {
        "experiment": f"xs_{horizon}d_{version}", "dataset_version": version,
        "data_status": list(manifest["status_counts"]),
        "dataset_sha256": manifest["content_sha256"], "rows_bars": manifest["rows"], "rows_modelled": len(data),
        "horizon_bars": horizon, "target": y_col, "features": X_cols,
        "split": {k: {"rows": int(len(v)), "start": str(data.ts.iloc[v].min()), "end": str(data.ts.iloc[v].max())}
                  for k, v in split.items()},
        "walk_forward": wf.to_dict("records"), "walk_forward_summary": wf_summary.to_dict("records"),
        "holdout": holdout,
        "timings_s": {"features": round(t_feat, 1), "total": round(time.perf_counter() - t0, 1)},
        "caveat": ("SYNTHETIC data: results test the pipeline only and say nothing about real markets."
                   if "SYNTHETIC" in manifest["status_counts"] else ""),
    }
    if out:
        out.mkdir(parents=True, exist_ok=True)
        (out / f"{report['experiment']}.json").write_text(json.dumps(report, indent=2, default=str))
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lake", default="lake")
    ap.add_argument("--version", default="syn-v1")
    ap.add_argument("--horizon", type=int, default=5)
    ap.add_argument("--out", default="reports")
    a = ap.parse_args()
    r = run(Path(a.lake), a.version, a.horizon, Path(a.out))
    print(json.dumps({k: r[k] for k in ("experiment", "rows_modelled", "split", "walk_forward_summary", "timings_s")}, indent=2, default=str))
    for k, v in r["holdout"].items():
        bt = v["backtest_long_short"]
        print(k, "IC", v["ic"].get("ic_mean"), "t", v["ic"].get("ic_t"),
              "net sharpe", bt and bt["net"].get("sharpe"), "gross sharpe", bt and bt["gross"].get("sharpe"))


if __name__ == "__main__":
    main()
