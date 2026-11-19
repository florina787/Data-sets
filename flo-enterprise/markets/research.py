"""Model training, chronological evaluation, cost-aware backtests and the promotion decision.

Protocol (per horizon h in 1, 5, 20 sessions; target = cross-sectional excess log return fwd_xs_h):

1. Chronological split of in-universe rows by date: 60% train / 20% validation / 20% holdout, with an embargo of
   2*h sessions between segments and purging of any training row whose label ends inside the next segment.
2. Hyperparameters are chosen on the validation segment only (small fixed grids); the chosen model is refit on
   train + validation and scored ONCE on the holdout.
3. Walk-forward (expanding, 4 folds) inside train + validation shows stability across time (h = 5).
4. Backtests rebalance every h sessions on non-overlapping windows: long/short deciles (market-neutral) and long-only top
   decile vs SPY, with commission, volatility-scaled spread, slippage, square-root impact, short borrow and a 5%-of-ADV
   liquidity cap. Gross and net are always reported together.
5. Significance uses non-overlapping dates (every h-th) so overlapping labels do not inflate t-statistics; net Sharpe gets a
   95% block-bootstrap interval.
6. Promotion requires every criterion in PromotionCriteria. If no model qualifies the verdict is
   "NO VALIDATED TRADING EDGE", which is a valid governance outcome.

Every report states that the universe is survivorship-biased (see the dataset catalog).
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from markets import catalog, config
from markets.features import FEATURES, HORIZONS

FEATURE_COLS = [f"{f}_rk" for f in FEATURES]
NO_EDGE = "NO VALIDATED TRADING EDGE"


# ------------------------------------------------------------------ data + splits
def load_universe(columns: list[str] | None = None) -> pd.DataFrame:
    import duckdb
    path = config.LAKE_DIR / "research" / "features.parquet"
    cols = "*" if columns is None else ", ".join(columns)
    return duckdb.connect().execute(f"SELECT {cols} FROM read_parquet('{path}') WHERE in_universe ORDER BY date, ticker").df()


def chronological_split(df: pd.DataFrame, h: int, fractions=(0.6, 0.2, 0.2)) -> dict[str, np.ndarray]:
    dates = np.sort(df["date"].unique())
    n = len(dates)
    c1, c2 = int(n * fractions[0]), int(n * (fractions[0] + fractions[1]))
    emb = 2 * h
    d = df["date"].to_numpy()
    end = pd.to_datetime(df[f"label_end_{h}"], utc=True)
    avail = pd.to_datetime(df["available_at"], utc=True)
    val_start_t = avail[df["date"] == dates[c1]].min()
    hold_start_t = avail[df["date"] == dates[c2]].min()
    train = (d < dates[c1]) & (end < val_start_t).to_numpy()
    val = (d >= dates[min(c1 + emb, n - 1)]) & (d < dates[c2]) & (end < hold_start_t).to_numpy()
    hold = d >= dates[min(c2 + emb, n - 1)]
    return {"train": np.flatnonzero(train), "validation": np.flatnonzero(val), "holdout": np.flatnonzero(hold)}


def walk_forward(df: pd.DataFrame, h: int, n_folds: int = 4, min_train_frac: float = 0.5):
    dates = np.sort(df["date"].unique())
    n = len(dates)
    first = int(n * min_train_frac)
    step = (n - first) // n_folds
    d = df["date"].to_numpy()
    end = pd.to_datetime(df[f"label_end_{h}"], utc=True)
    avail = pd.to_datetime(df["available_at"], utc=True)
    for k in range(n_folds):
        t0 = dates[first + k * step]
        t1 = dates[min(first + (k + 1) * step, n - 1)]
        t0_avail = avail[df["date"] == t0].min()
        train = (d < t0) & (end < t0_avail).to_numpy()
        test = (d >= dates[min(first + k * step + 2 * h, n - 1)]) & (d < t1)
        yield f"wf{k}", np.flatnonzero(train), np.flatnonzero(test), str(pd.Timestamp(t0).date()), str(pd.Timestamp(t1).date())


# ------------------------------------------------------------------ models
class Model:
    name = "base"
    family = "baseline"

    def fit(self, X, y, Xv=None, yv=None):
        return self

    def predict(self, X) -> np.ndarray:
        raise NotImplementedError

    def params(self) -> dict:
        return {}


class Naive(Model):
    """Predicts zero excess return for every name (no information)."""
    name = "naive_zero"

    def predict(self, X):
        return np.zeros(len(X))


class Momentum(Model):
    name = "momentum_12_1"

    def predict(self, X):
        return X["mom_12_1_rk"].fillna(0).to_numpy()


class Reversal(Model):
    name = "reversal_5d"

    def predict(self, X):
        return -X["ret_5_rk"].fillna(0).to_numpy()


class Ridge(Model):
    name, family = "ridge", "linear"

    def __init__(self, alpha: float = 10.0):
        self.alpha = alpha

    def fit(self, X, y, Xv=None, yv=None):
        from sklearn.linear_model import Ridge as R
        self.m = R(alpha=self.alpha).fit(X.fillna(0), y)
        return self

    def predict(self, X):
        return self.m.predict(X.fillna(0))

    def params(self):
        return {"alpha": self.alpha}


class LGBM(Model):
    name, family = "lightgbm", "gradient_boosting"

    def __init__(self, num_leaves=15, min_child_samples=5000, n_estimators=300, learning_rate=0.03, seed=0):
        self.p = dict(num_leaves=num_leaves, min_child_samples=min_child_samples, n_estimators=n_estimators, learning_rate=learning_rate,
                      subsample=0.5, subsample_freq=1, colsample_bytree=0.8, random_state=seed, n_jobs=4, verbose=-1)

    def fit(self, X, y, Xv=None, yv=None):
        import lightgbm as lgb
        self.m = lgb.LGBMRegressor(**self.p).fit(X, y)
        return self

    def predict(self, X):
        return self.m.predict(X)

    def params(self):
        return {k: v for k, v in self.p.items() if k not in ("n_jobs", "verbose")}

    def importance(self):
        return dict(zip(self.m.feature_name_, map(int, self.m.feature_importances_)))


class XGB(Model):
    name, family = "xgboost", "gradient_boosting"

    def __init__(self, max_depth=4, min_child_weight=5000, n_estimators=300, learning_rate=0.03, seed=0):
        self.p = dict(max_depth=max_depth, min_child_weight=min_child_weight, n_estimators=n_estimators, learning_rate=learning_rate,
                      subsample=0.5, colsample_bytree=0.8, tree_method="hist", random_state=seed, n_jobs=4)

    def fit(self, X, y, Xv=None, yv=None):
        import xgboost as xgb
        self.m = xgb.XGBRegressor(**self.p).fit(X, y)
        return self

    def predict(self, X):
        return self.m.predict(X)

    def params(self):
        return {k: v for k, v in self.p.items() if k != "n_jobs"}


BASELINES = [Naive, Momentum, Reversal]
GRIDS = {
    "ridge": [dict(alpha=1.0), dict(alpha=100.0)],
    "lightgbm": [dict(num_leaves=15, min_child_samples=5000), dict(num_leaves=31, min_child_samples=20000)],
    "xgboost": [dict(max_depth=3, min_child_weight=5000), dict(max_depth=5, min_child_weight=20000)],
}
LEARNERS = {"ridge": Ridge, "lightgbm": LGBM, "xgboost": XGB}


# ------------------------------------------------------------------ metrics
def ic_series(pred: np.ndarray, actual: pd.Series, dates: pd.Series) -> pd.Series:
    df = pd.DataFrame({"p": pred, "a": actual.to_numpy(), "d": dates.to_numpy()}).dropna()
    df["pr"] = df.groupby("d")["p"].rank()
    df["ar"] = df.groupby("d")["a"].rank()
    return df.groupby("d").apply(lambda g: g["pr"].corr(g["ar"]) if len(g) > 20 else np.nan, include_groups=False).dropna()


def ic_stats(ics: pd.Series, h: int) -> dict:
    if len(ics) < 4:
        return {"ic_mean": None, "ic_t": None, "n_dates": int(len(ics))}
    nov = ics.iloc[::h]  # non-overlapping dates for inference
    se = nov.std() / np.sqrt(len(nov)) if len(nov) > 1 else np.nan
    return {"ic_mean": float(ics.mean()), "ic_positive_share": float((ics > 0).mean()), "n_dates": int(len(ics)),
            "ic_t": float(nov.mean() / se) if se and se > 0 else None, "n_independent_dates": int(len(nov)),
            "ic_ci95": [float(nov.mean() - 1.96 * se), float(nov.mean() + 1.96 * se)] if se and se > 0 else None}


def perf(r: pd.Series, periods_per_year: float) -> dict:
    r = r.dropna()
    if len(r) < 3:
        return {"n_periods": int(len(r))}
    eq = (1 + r).cumprod()
    yrs = len(r) / periods_per_year
    sd = r.std()
    dn = r[r < 0]
    return {"n_periods": int(len(r)), "total_return": float(eq.iloc[-1] - 1),
            "cagr": float(eq.iloc[-1] ** (1 / yrs) - 1) if eq.iloc[-1] > 0 else -1.0,
            "volatility": float(sd * np.sqrt(periods_per_year)),
            "sharpe": float(r.mean() / sd * np.sqrt(periods_per_year)) if sd > 0 else 0.0,
            "sortino": float(r.mean() / dn.std() * np.sqrt(periods_per_year)) if len(dn) > 1 and dn.std() > 0 else None,
            "max_drawdown": float((eq / eq.cummax() - 1).min()), "hit_rate": float((r > 0).mean())}


def bootstrap_sharpe_ci(r: pd.Series, periods_per_year: float, block: int = 10, n: int = 1000, seed: int = 7) -> list[float] | None:
    x = r.dropna().to_numpy()
    if len(x) < 2 * block:
        return None
    rng = np.random.default_rng(seed)
    nb = int(np.ceil(len(x) / block))
    out = []
    for _ in range(n):
        starts = rng.integers(0, len(x) - block + 1, nb)
        s = np.concatenate([x[i:i + block] for i in starts])[: len(x)]
        out.append(s.mean() / s.std() * np.sqrt(periods_per_year) if s.std() > 0 else 0.0)
    return [float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))]


def decile_precision_recall(pred: np.ndarray, actual: pd.Series, dates: pd.Series) -> dict:
    df = pd.DataFrame({"p": pred, "a": actual.to_numpy(), "d": dates.to_numpy()}).dropna()
    df["pt"] = df.groupby("d")["p"].rank(pct=True) > 0.9
    df["at"] = df.groupby("d")["a"].rank(pct=True) > 0.9
    tp = (df.pt & df["at"]).sum()
    return {"top_decile_precision": float(tp / max(df.pt.sum(), 1)), "top_decile_recall": float(tp / max(df["at"].sum(), 1)),
            "directional_accuracy": float((np.sign(df.p) == np.sign(df.a)).mean()) if df.p.abs().sum() > 0 else None,
            "base_rate_top_decile": 0.1}


# ------------------------------------------------------------------ costs + backtest
@dataclass(frozen=True)
class CostModel:
    commission_bps: float = 0.5
    half_spread_bps: float = 3.0          # at median volatility; scaled by the name's volatility ratio (0.5x-4x)
    slippage_bps: float = 2.0
    impact_bps_at_1pct_adv: float = 10.0  # square-root impact
    borrow_bps_annual: float = 50.0
    max_adv_participation: float = 0.05
    capital_usd: float = 10_000_000

    def per_side_bps(self, participation, vol_mult):
        p = np.clip(np.asarray(participation, float), 0, None)
        return self.commission_bps + self.half_spread_bps * np.asarray(vol_mult) + self.slippage_bps \
            + self.impact_bps_at_1pct_adv * np.sqrt(p / 0.01)


def backtest(frame: pd.DataFrame, signal: np.ndarray, h: int, mode: str, costs: CostModel = CostModel()) -> dict:
    """mode 'long_short' (decile spread, market-neutral) or 'long_only' (top decile, reported vs SPY)."""
    df = frame.assign(sig=signal).dropna(subset=["sig", f"fwd_ret_{h}"])
    dates = np.sort(df["date"].unique())[::h]
    prev = pd.Series(dtype=float)
    rows = []
    for d in dates:
        g = df[df["date"] == d].set_index("ticker")
        if len(g) < 50:
            continue
        hi, lo = g["sig"].quantile(0.9), g["sig"].quantile(0.1)
        longs = g.index[g["sig"] >= hi]
        shorts = g.index[g["sig"] <= lo] if mode == "long_short" else []
        w = pd.Series(0.0, index=g.index)
        w[longs] = (0.5 if mode == "long_short" else 1.0) / max(len(longs), 1)
        if len(shorts):
            w[shorts] = -0.5 / len(shorts)
        cap = costs.max_adv_participation * g["adv_usd"] / costs.capital_usd
        w = np.sign(w) * np.minimum(w.abs(), cap.fillna(0))
        simple = np.expm1(g[f"fwd_ret_{h}"])
        gross = float((w * simple).sum())
        idx = w.index.union(prev.index)
        dw = w.reindex(idx, fill_value=0.0) - prev.reindex(idx, fill_value=0.0)
        adv = g["adv_usd"].reindex(idx)
        part = (dw.abs() * costs.capital_usd / adv).fillna(0.01)
        vm = (g["vol_20"].reindex(idx) / g["vol_20"].median()).clip(0.5, 4).fillna(1)
        cost = float((dw.abs() * costs.per_side_bps(part, vm)).sum()) / 1e4 + float(w[w < 0].abs().sum()) * costs.borrow_bps_annual * h / 252 / 1e4
        spy = float(np.expm1(g[f"spy_fwd_{h}"].iloc[0])) if g[f"spy_fwd_{h}"].notna().any() else np.nan
        rows.append({"date": d, "gross": gross, "net": gross - cost, "cost": cost, "turnover": float(dw.abs().sum()),
                     "spy": spy, "invested": float(w.abs().sum())})
        prev = w * (1 + simple) / (1 + gross)
    r = pd.DataFrame(rows).set_index("date")
    ppy = 252 / h
    out = {"mode": mode, "gross": perf(r["gross"], ppy), "net": perf(r["net"], ppy),
           "net_sharpe_ci95": bootstrap_sharpe_ci(r["net"], ppy), "avg_turnover": float(r["turnover"].mean()),
           "avg_cost_per_rebalance_bps": float(r["cost"].mean() * 1e4), "total_cost": float(r["cost"].sum()),
           "avg_gross_exposure": float(r["invested"].mean())}
    if mode == "long_only":
        out["benchmark_spy"] = perf(r["spy"], ppy)
        ex = r["net"] - r["spy"]
        out["net_excess_vs_spy"] = {"mean_per_period": float(ex.mean()), "annualised": float(ex.mean() * ppy),
                                    "information_ratio": float(ex.mean() / ex.std() * np.sqrt(ppy)) if ex.std() > 0 else None}
    out["equity_net"] = [[str(pd.Timestamp(i).date()), float(v)] for i, v in (1 + r["net"]).cumprod().items()]
    out["equity_gross"] = [[str(pd.Timestamp(i).date()), float(v)] for i, v in (1 + r["gross"]).cumprod().items()]
    if mode == "long_only":
        out["equity_spy"] = [[str(pd.Timestamp(i).date()), float(v)] for i, v in (1 + r["spy"].fillna(0)).cumprod().items()]
    return out


# ------------------------------------------------------------------ promotion
@dataclass(frozen=True)
class PromotionCriteria:
    min_holdout_ic_t: float = 2.0
    min_wf_positive_share: float = 0.75
    min_net_sharpe: float = 0.0
    require_net_sharpe_ci_above_zero: bool = True
    must_beat_baselines_net: bool = True
    long_only_must_beat_spy_net: bool = True
    max_drawdown_floor: float = -0.25
    human_approval_required: bool = True


def decide(model: str, h: int, res: dict, baselines: dict, wf_share: float | None, c: PromotionCriteria = PromotionCriteria()) -> dict:
    reasons = []
    ls, lo = res["backtest"]["long_short"], res["backtest"]["long_only"]
    ic_t = res["ic"].get("ic_t")
    if ic_t is None or ic_t < c.min_holdout_ic_t:
        reasons.append(f"holdout IC t-stat {ic_t if ic_t is None else round(ic_t, 2)} < {c.min_holdout_ic_t} (non-overlapping dates)")
    if wf_share is not None and wf_share < c.min_wf_positive_share:
        reasons.append(f"walk-forward IC positive in {wf_share:.0%} of folds (< {c.min_wf_positive_share:.0%})")
    ns = ls["net"].get("sharpe")
    if ns is None or ns <= c.min_net_sharpe:
        reasons.append(f"long/short net Sharpe {ns if ns is None else round(ns, 2)} is not positive after costs")
    ci = ls.get("net_sharpe_ci95")
    if c.require_net_sharpe_ci_above_zero and (ci is None or ci[0] <= 0):
        reasons.append(f"95% CI of net Sharpe {None if ci is None else [round(x, 2) for x in ci]} is not entirely above zero")
    if c.must_beat_baselines_net:
        worse = [b for b, s in baselines.items() if s is not None and (ns or -9) <= s]
        if worse:
            reasons.append(f"does not beat baseline(s) {worse} net of costs")
    if c.long_only_must_beat_spy_net and (lo.get("net_excess_vs_spy", {}).get("annualised") or -1) <= 0:
        reasons.append("long-only top decile does not beat SPY buy-and-hold after costs")
    if (ls["net"].get("max_drawdown") or -1) < c.max_drawdown_floor:
        reasons.append(f"net max drawdown {ls['net'].get('max_drawdown'):.1%} worse than {c.max_drawdown_floor:.0%}")
    return {"model": model, "horizon": h, "eligible": not reasons, "reasons": reasons,
            "status": "eligible_pending_human_approval" if not reasons else "rejected"}


def redecide(path=None) -> dict:
    """Re-apply the promotion rules to a saved report (no retraining); used when criteria wording or thresholds change."""
    path = path or config.REPORTS_DIR / "experiment.json"
    rep = json.loads(path.read_text())
    for h, hr in rep["horizons"].items():
        base = {n: m["backtest"]["long_short"]["net"].get("sharpe") for n, m in hr["models"].items()
                if m["family"] == "baseline" and m.get("backtest")}
        wf = pd.DataFrame(hr["walk_forward"]) if hr["walk_forward"] else None
        share = wf.groupby("model")["ic_mean"].apply(lambda s: float((s > 0).mean())).to_dict() if wf is not None else {}
        hr["decisions"] = [decide(n, int(h), m, base, share.get(n)) for n, m in hr["models"].items() if m["family"] != "baseline"]
    eligible = [d for hr in rep["horizons"].values() for d in hr["decisions"] if d["eligible"]]
    rep["verdict"] = "ELIGIBLE MODEL(S) AWAITING HUMAN APPROVAL" if eligible else NO_EDGE
    rep["eligible"] = eligible
    path.write_text(json.dumps(rep, indent=1, default=str))
    return rep


# ------------------------------------------------------------------ experiment
def _fit_predict(model: Model, tr: pd.DataFrame, te: pd.DataFrame, y: str) -> np.ndarray:
    t = tr.dropna(subset=[y])
    model.fit(t[FEATURE_COLS], t[y])
    return model.predict(te[FEATURE_COLS])


def run(horizons=HORIZONS, wf_horizon: int = 5, out_name: str = "experiment.json") -> dict:
    for d in (catalog.PRIMARY,):
        catalog.assert_real(catalog.CATALOG[d])
    t0 = time.perf_counter()
    cols = ["ticker", "date", "available_at", "adv_usd", "vol_20"] + FEATURE_COLS + \
        [c for h in HORIZONS for c in (f"fwd_ret_{h}", f"fwd_xs_{h}", f"spy_fwd_{h}", f"label_end_{h}")]
    df = load_universe(cols)
    lake = json.loads((config.MANIFEST_DIR / "research_lake.json").read_text())
    report = {"generated_at": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"), "dataset_id": catalog.PRIMARY,
              "dataset_content_sha256": json.loads((config.MANIFEST_DIR / f"{catalog.PRIMARY}.json").read_text())["files"]["content_sha256"],
              "universe": f"top {1000} US stocks by trailing 20-session median dollar volume, point-in-time",
              "rows_in_universe": int(len(df)), "features": FEATURE_COLS, "costs": asdict(CostModel()),
              "criteria": asdict(PromotionCriteria()), "data_quality_score": lake["quality"]["score"],
              "survivorship_biased": True,
              "survivorship_note": "Only stocks with history through 2017 exist in the source; "
                                   f"{lake['validation']['survivorship']['sp500_2016_members_absent_from_primary']} S&P 500 (2016) members "
                                   "acquired or delisted earlier are absent. Results are conditional on survival and likely overstate returns.",
              "horizons": {}}
    for h in horizons:
        y = f"fwd_xs_{h}"
        sp = chronological_split(df, h)
        tr, va, ho = (df.iloc[sp[k]] for k in ("train", "validation", "holdout"))
        dev = pd.concat([tr, va])
        hr = {"target": y, "split": {k: {"rows": int(len(v)), "start": str(df["date"].iloc[v].min().date()),
                                         "end": str(df["date"].iloc[v].max().date())} for k, v in sp.items()},
              "embargo_sessions": 2 * h, "models": {}, "tuning": {}, "walk_forward": []}
        # walk-forward stability (expanding), only for one horizon to bound runtime
        wf_share: dict[str, float] = {}
        if h == wf_horizon:
            for fold, a, b, s0, s1 in walk_forward(dev.reset_index(drop=True), h):
                d2 = dev.reset_index(drop=True)
                for name, cls in [("momentum_12_1", Momentum), ("reversal_5d", Reversal), ("ridge", Ridge), ("lightgbm", LGBM), ("xgboost", XGB)]:
                    p = _fit_predict(cls(), d2.iloc[a], d2.iloc[b], y)
                    st = ic_stats(ic_series(p, d2.iloc[b][y], d2.iloc[b]["date"]), h)
                    hr["walk_forward"].append({"fold": fold, "model": name, "test_start": s0, "test_end": s1, "ic_mean": st["ic_mean"]})
            wfd = pd.DataFrame(hr["walk_forward"])
            wf_share = wfd.groupby("model")["ic_mean"].apply(lambda s: float((s > 0).mean())).to_dict()
        # tune on validation only
        chosen: dict[str, Model] = {}
        for name, grid in GRIDS.items():
            scores = []
            for params in grid:
                p = _fit_predict(LEARNERS[name](**params), tr, va, y)
                scores.append(ic_stats(ic_series(p, va[y], va["date"]), h)["ic_mean"] or -1)
            best = int(np.argmax(scores))
            hr["tuning"][name] = {"grid": grid, "validation_ic": scores, "chosen": grid[best]}
            chosen[name] = LEARNERS[name](**grid[best])
        models: list[Model] = [cls() for cls in BASELINES] + list(chosen.values())
        base_net = {}
        for m in models:
            p = _fit_predict(m, dev, ho, y) if m.family != "baseline" else m.predict(ho[FEATURE_COLS])
            res = {"family": m.family, "params": m.params(), "ic": ic_stats(ic_series(p, ho[y], ho["date"]), h),
                   "classification": decile_precision_recall(p, ho[y], ho["date"])}
            if m.name != "naive_zero":
                res["backtest"] = {"long_short": backtest(ho, p, h, "long_short"), "long_only": backtest(ho, p, h, "long_only")}
            if isinstance(m, LGBM):
                res["feature_importance"] = m.importance()
            hr["models"][m.name] = res
            if m.family == "baseline" and "backtest" in res:
                base_net[m.name] = res["backtest"]["long_short"]["net"].get("sharpe")
        hr["benchmark_spy_buy_and_hold"] = hr["models"]["momentum_12_1"]["backtest"]["long_only"]["benchmark_spy"]
        hr["decisions"] = [decide(n, h, r, base_net, wf_share.get(n)) for n, r in hr["models"].items()
                           if r["family"] != "baseline"]
        report["horizons"][str(h)] = hr
        print(f"h={h} done {time.perf_counter() - t0:.0f}s", flush=True)
    eligible = [d for h in report["horizons"].values() for d in h["decisions"] if d["eligible"]]
    report["verdict"] = "ELIGIBLE MODEL(S) AWAITING HUMAN APPROVAL" if eligible else NO_EDGE
    report["eligible"] = eligible
    report["seconds"] = round(time.perf_counter() - t0, 1)
    out = config.REPORTS_DIR
    out.mkdir(parents=True, exist_ok=True)
    (out / out_name).write_text(json.dumps(report, indent=1, default=str))
    return report


if __name__ == "__main__":
    r = run()
    print(r["verdict"], r["seconds"], "s")
