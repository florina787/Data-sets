import numpy as np
import pandas as pd

from flowwealth.features.build import FEATURES, build_features, feature_columns
from flowwealth.models.forecasters import LightGBMForecaster, MomentumBaseline
from flowwealth.research.backtest import run_backtest
from flowwealth.research.costs import CostModel
from flowwealth.research.metrics import calibration, information_coefficient, perf_stats
from flowwealth.validation.splits import chronological_split, walk_forward


def test_features_are_point_in_time(clean_small):
    """Features at t computed on history truncated at t equal features computed on full history."""
    bars, _, _ = clean_small
    full = build_features(bars, horizons=(5,), rank=False)
    cut = bars.ts.sort_values().iloc[len(bars) // 2]
    trunc = build_features(bars[bars.ts <= cut], horizons=(5,), rank=False)
    cols = list(FEATURES)
    a = full[full.ts <= cut].set_index(["ticker", "ts"])[cols].sort_index()
    b = trunc.set_index(["ticker", "ts"])[cols].sort_index()
    pd.testing.assert_frame_equal(a, b, check_exact=False, rtol=1e-9)


def test_ranked_features_point_in_time(clean_small):
    bars, _, _ = clean_small
    full = build_features(bars, horizons=(5,))
    cut = bars.ts.sort_values().iloc[len(bars) // 2]
    trunc = build_features(bars[bars.ts <= cut], horizons=(5,))
    a = full[full.ts <= cut].set_index(["ticker", "ts"])[feature_columns()].sort_index()
    b = trunc.set_index(["ticker", "ts"])[feature_columns()].sort_index()
    pd.testing.assert_frame_equal(a, b, check_exact=False, rtol=1e-9)


def test_labels_end_after_signal_and_delisting_return_kept(clean_small):
    bars, master, _ = clean_small
    f = build_features(bars, horizons=(5,))
    m = f.label_end_5.notna()
    assert (f.label_end_5[m] > f.ts[m]).all()
    tk = master.dropna(subset=["delisted"]).ticker.iloc[0]
    tail = f[f.ticker == tk].tail(3)
    assert tail.fwd_ret_5.iloc[:-1].notna().all()  # delisting loss is realised, not dropped
    assert pd.isna(tail.fwd_ret_5.iloc[-1])  # the delisting bar itself has no tradable future


def test_chronological_split_purges_and_embargoes(clean_small):
    bars, _, _ = clean_small
    f = build_features(bars, horizons=(5,)).dropna(subset=["ret_20_rk"]).reset_index(drop=True)
    s = chronological_split(f, "label_end_5", embargo_days=10)
    tr, va, ho = (f.iloc[s[k]] for k in ("train", "validation", "holdout"))
    assert tr.ts.max() < va.ts.min() < ho.ts.min()
    assert (pd.to_datetime(tr.label_end_5, utc=True) < va.ts.min()).all()
    assert (pd.to_datetime(va.label_end_5, utc=True) < ho.ts.min()).all()
    assert (va.ts.min() - tr.ts.max()).days >= 10
    assert set(s["train"]).isdisjoint(s["holdout"])


def test_walk_forward_never_trains_on_future(clean_small):
    bars, _, _ = clean_small
    f = build_features(bars, horizons=(5,)).dropna(subset=["ret_20_rk"]).reset_index(drop=True)
    folds = list(walk_forward(f, "label_end_5", n_folds=3, embargo_days=10))
    assert len(folds) == 3
    for fd in folds:
        tr, te = f.iloc[fd.train_idx], f.iloc[fd.test_idx]
        assert pd.to_datetime(tr.label_end_5, utc=True).max() < te.ts.min()


def test_costs_make_net_worse_than_gross(clean_small):
    bars, _, _ = clean_small
    f = build_features(bars, horizons=(5,))
    f["adv_usd"] = 5e7
    f["sig"] = MomentumBaseline().predict(f)
    bt = run_backtest(f, "sig", "fwd_ret_5", 5)
    assert bt.net.sum() < bt.gross.sum()
    free = run_backtest(f, "sig", "fwd_ret_5", 5, costs=CostModel(0, 0, 0, 0, 0))
    np.testing.assert_allclose(free.net.values, free.gross.values)


def test_backtest_perfect_foresight_is_positive_gross(clean_small):
    """Sanity: a signal equal to the realised return must make money gross."""
    bars, _, _ = clean_small
    f = build_features(bars, horizons=(5,))
    f["sig"] = f["fwd_ret_5"]
    assert run_backtest(f, "sig", "fwd_ret_5", 5).stats_gross["sharpe"] > 3


def test_metrics_basic():
    s = perf_stats(pd.Series([0.01, -0.005, 0.02, -0.01]), 252)
    assert s["max_drawdown"] < 0 and s["win_rate"] == 0.5
    c = calibration(np.array([0.9] * 100), np.array([1] * 90 + [0] * 10))
    assert c["ece"] < 1e-9
    d = pd.Series(np.repeat(pd.date_range("2024-01-01", periods=10), 20))
    x = pd.Series(np.random.default_rng(0).normal(size=200))
    assert information_coefficient(x, x, d)["ic_mean"] > 0.99


def test_lightgbm_trains_and_predicts(clean_small):
    bars, _, _ = clean_small
    f = build_features(bars, horizons=(5,)).dropna(subset=["fwd_xs_5", "ret_20_rk"])
    m = LightGBMForecaster(n_estimators=20, min_child_samples=200).fit(f[feature_columns()], f.fwd_xs_5)
    assert len(m.predict(f[feature_columns()].head(10))) == 10
