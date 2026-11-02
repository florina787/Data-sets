"""Component forecasting engine (Flying Florina 3.0).

Every number this module returns is computed by a model or by deterministic simulation from the SYNTHETIC global dataset. Qwen is
never asked for a number. All evaluation uses a temporal split: models are fit on earlier weeks and scored on later weeks only.

Tasks and methods
-----------------
1. Maintenance / replacement-part demand  : HistGradientBoosting quantile regression (P10/P50/P90), direct multi-horizon
                                            (7/14/30/60/90 days), vs moving-average and seasonal-naive baselines.
2. Remaining useful life                  : Weibull survival model (MLE with right-censoring) per category, conditional on age,
                                            plus a per-unit health-trend extrapolation; combined estimate. Scored on later failures.
3. Failure within 30 days (risk)          : RandomForest classifier, precision/recall/F1, Brier score, calibration (ECE, reliability bins).
4. Component anomaly detection            : IsolationForest vs a z-score rule, scored against labelled injected anomalies.
5. Supplier lead time                     : HistGradientBoosting quantile regression vs supplier-median baseline; late-delivery probability.
6. Repair turnaround                      : empirical quantiles per (center, category); interval coverage on later repairs.
7. Inventory depletion                    : seeded Monte Carlo from the demand quantiles + open orders with predicted lead times.
8. Maintenance workload & cost            : demand quantiles x labour hours / unit cost (stated assumptions).
9. Historical forecast accuracy           : rolling-origin weekly backtest of the 7-day model over the test window.
"""

from __future__ import annotations

import hashlib
import math
import pickle
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.core import db
from app.core.util import DEMO_TODAY, now_iso
from app.global_intel import dataset as ds

MODEL_VERSION = "ff3-forecast-1.0"
HORIZONS_DAYS = [7, 14, 30, 60, 90]
H_WEEKS = {7: 1, 14: 2, 30: 4, 60: 9, 90: 13}
QUANTILES = (0.1, 0.5, 0.9)
TEST_WEEKS = 26
LABOR_RATE = 95.0
CREW_HEADROOM = 1.25
MC_DRAWS = 400
RNG_SEED = 20261102


def _metrics_reg(y: np.ndarray, p50: np.ndarray, lo: np.ndarray | None = None, hi: np.ndarray | None = None) -> dict[str, float]:
    err = p50 - y
    out = {"mae": float(np.mean(np.abs(err))), "rmse": float(np.sqrt(np.mean(err ** 2))), "bias": float(np.mean(err)), "n": int(len(y))}
    if lo is not None and hi is not None:
        out["coverage_80"] = float(np.mean((y >= lo) & (y <= hi)))
        out["mean_interval_width"] = float(np.mean(hi - lo))
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in out.items()}


def _metrics_cls(y: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    tp = int(np.sum((pred == 1) & (y == 1)))
    fp = int(np.sum((pred == 1) & (y == 0)))
    fn = int(np.sum((pred == 0) & (y == 1)))
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4), "tp": tp, "fp": fp, "fn": fn,
            "positives": int(np.sum(y == 1)), "n": int(len(y))}


def _calibration(y: np.ndarray, prob: np.ndarray, bins: int = 10) -> dict[str, Any]:
    edges = np.linspace(0, 1, bins + 1)
    out, ece = [], 0.0
    for i in range(bins):
        m = (prob >= edges[i]) & (prob < edges[i + 1] if i < bins - 1 else prob <= 1)
        if m.sum() == 0:
            continue
        conf, acc = float(prob[m].mean()), float(y[m].mean())
        ece += m.sum() / len(y) * abs(conf - acc)
        out.append({"bin": f"{edges[i]:.1f}-{edges[i + 1]:.1f}", "predicted": round(conf, 4), "observed": round(acc, 4), "n": int(m.sum())})
    return {"ece": round(ece, 4), "brier": round(float(np.mean((prob - y) ** 2)), 4), "bins": out}


def _sort_q(q: np.ndarray) -> np.ndarray:
    return np.sort(np.maximum(q, 0), axis=1)


def _q_sample(q10: float, q50: float, q90: float, u: np.ndarray) -> np.ndarray:
    """Sample from a piecewise-linear quantile function through (0, q0), (.1, q10), (.5, q50), (.9, q90), (1, q100)."""
    q0 = max(0.0, q10 - (q50 - q10) * 0.25)
    q100 = q90 + max(q90 - q50, 0.5)
    return np.interp(u, [0, 0.1, 0.5, 0.9, 1.0], [q0, q10, q50, q90, q100])


@dataclass
class Engine:
    built_at: str = ""
    build_ms: float = 0.0
    data_hash: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)
    demand_fc: dict[tuple[str, str], dict[int, tuple[float, float, float]]] = field(default_factory=dict)
    demand_hist: dict[tuple[str, str], list[int]] = field(default_factory=dict)
    backtest: list[dict[str, Any]] = field(default_factory=list)
    weibull: dict[str, dict[str, float]] = field(default_factory=dict)
    units: dict[str, dict[str, Any]] = field(default_factory=dict)
    lead_q: dict[str, tuple[float, float, float]] = field(default_factory=dict)  # open order id -> lead-time quantiles
    repair_q: dict[tuple[str, str], tuple[float, float, float]] = field(default_factory=dict)
    inventory: dict[tuple[str, str], dict[int, dict[str, float]]] = field(default_factory=dict)
    cat: dict[str, dict[str, Any]] = field(default_factory=dict)
    fac: dict[str, dict[str, Any]] = field(default_factory=dict)
    sup: dict[str, dict[str, Any]] = field(default_factory=dict)
    links: list[dict[str, Any]] = field(default_factory=list)
    disruptions: list[dict[str, Any]] = field(default_factory=list)
    orders: list[dict[str, Any]] = field(default_factory=list)
    supplier_late: dict[str, float] = field(default_factory=dict)

    # ------------------------------------------------------------------ build
    def build(self) -> Engine:
        t0 = time.perf_counter()
        with db.session(write=True) as conn:
            ds.ensure(conn)
            self.cat = {r["id"]: r for r in db.rows(conn, "SELECT * FROM g_categories")}
            self.fac = {r["id"]: r for r in db.rows(conn, "SELECT * FROM g_facilities")}
            self.sup = {r["id"]: r for r in db.rows(conn, "SELECT * FROM g_suppliers")}
            self.links = db.rows(conn, "SELECT * FROM g_supply_links")
            self.disruptions = db.rows(conn, "SELECT * FROM g_disruptions ORDER BY start_day")
            demand = db.rows(conn, "SELECT facility_id, category_id, week, removals FROM g_demand ORDER BY facility_id, category_id, week")
            units = db.rows(conn, "SELECT * FROM g_units")
            uw = db.rows(conn, "SELECT * FROM g_unit_weeks ORDER BY unit_id, week")
            deliveries = db.rows(conn, "SELECT * FROM g_deliveries ORDER BY ordered_week")
            self.orders = db.rows(conn, "SELECT * FROM g_open_orders")
            repairs = db.rows(conn, "SELECT * FROM g_repairs")
            inv = db.rows(conn, "SELECT * FROM g_inventory")
        self.data_hash = hashlib.sha256(f"{len(demand)}:{len(uw)}:{len(deliveries)}:{ds.DATASET_VERSION}".encode()).hexdigest()[:16]
        for r in demand:
            self.demand_hist.setdefault((r["facility_id"], r["category_id"]), []).append(r["removals"])
        self._demand()
        self._survival(units, uw)
        self._risk_and_anomaly(units, uw)
        self._lead_time(deliveries)
        self._repairs(repairs)
        self._inventory(inv)
        self.build_ms = round((time.perf_counter() - t0) * 1000, 1)
        self.built_at = now_iso()
        self._persist()
        return self

    # ------------------------------------------------------------------ 1. demand
    def _features(self, series: np.ndarray, o: int, cat_i: int, fac_i: int) -> list[float]:
        h = series[:o]
        lag = [h[-i] if len(h) >= i else 0 for i in (1, 2, 3, 4)]
        m8, m26 = h[-8:].mean(), h[-26:].mean()
        last_year = h[-52:-39].mean() if len(h) >= 52 else m26
        return [*lag, m8, m26, h[-8:].std(), last_year, math.sin(2 * math.pi * o / 52), math.cos(2 * math.pi * o / 52), cat_i, fac_i]

    def _demand(self) -> None:
        """Poisson gradient boosting for the expected count + split-conformal prediction intervals.

        Origins are split in time: fit (target window ends before cutoff-13) -> calibrate (window ends in the 13 weeks before cutoff)
        -> test (origin >= cutoff). Interval = point +/- empirical quantiles of the scaled residual (y - p) / sqrt(p + 0.5) on the
        calibration slice, so the 80% interval is calibrated on data the model never trained on.
        """
        keys = sorted(self.demand_hist)
        cats, facs = sorted(self.cat), sorted({k[0] for k in keys})
        n = ds.N_WEEKS
        cutoff = n - TEST_WEEKS
        cal_start = cutoff - 13
        results: dict[str, Any] = {}
        self.conformal: dict[int, tuple[float, float]] = {}
        for days in HORIZONS_DAYS:
            H = H_WEEKS[days]
            parts: dict[str, list] = {k: [] for k in ("Xtr", "ytr", "Xca", "yca", "Xte", "yte", "ma", "sn", "Xall", "yall")}
            for k in keys:
                s = np.array(self.demand_hist[k], dtype=float)
                ci, fi = cats.index(k[1]), facs.index(k[0])
                for o in range(26, n - H + 1):
                    x, y = self._features(s, o, ci, fi), s[o:o + H].sum()
                    if o + H <= cal_start:
                        parts["Xtr"].append(x); parts["ytr"].append(y)  # noqa: E702
                    elif o + H <= cutoff and o >= cal_start - H:
                        parts["Xca"].append(x); parts["yca"].append(y)  # noqa: E702
                    elif o >= cutoff:
                        parts["Xte"].append(x); parts["yte"].append(y)  # noqa: E702
                        parts["ma"].append(s[o - 8:o].mean() * H)
                        parts["sn"].append(s[o - 52:o - 52 + H].sum() if o >= 52 else s[o - 8:o].mean() * H)
                    parts["Xall"].append(x); parts["yall"].append(y)  # noqa: E702
            P = {k: np.asarray(v, dtype=float) for k, v in parts.items()}
            model = self._hgb_poisson().fit(P["Xtr"], P["ytr"])
            pc = model.predict(P["Xca"])
            r = (P["yca"] - pc) / np.sqrt(pc + 0.5)
            lo_q, hi_q = float(np.quantile(r, 0.1)), float(np.quantile(r, 0.9))
            self.conformal[days] = (lo_q, hi_q)
            pt = model.predict(P["Xte"])
            lo, hi = np.maximum(pt + lo_q * np.sqrt(pt + 0.5), 0), pt + hi_q * np.sqrt(pt + 0.5)
            m = _metrics_reg(P["yte"], pt, lo, hi)
            m["baseline_moving_average"] = _metrics_reg(P["yte"], P["ma"])
            m["baseline_seasonal_naive"] = _metrics_reg(P["yte"], P["sn"])
            m["mae_improvement_vs_moving_average"] = round(1 - m["mae"] / max(m["baseline_moving_average"]["mae"], 1e-9), 4)
            m["train_rows"], m["calibration_rows"], m["test_rows"] = int(len(P["ytr"])), int(len(P["yca"])), int(len(P["yte"]))
            results[f"{days}d"] = m
            if days == 7:
                self._backtest(keys, np.column_stack([lo, pt, hi]), P["yte"])
            final = self._hgb_poisson().fit(P["Xall"], P["yall"])
            Xo = np.asarray([self._features(np.array(self.demand_hist[k], dtype=float), n, cats.index(k[1]), facs.index(k[0])) for k in keys])
            po = final.predict(Xo)
            for k, p in zip(keys, po, strict=True):
                q10, q90 = max(p + lo_q * math.sqrt(p + 0.5), 0.0), p + hi_q * math.sqrt(p + 0.5)
                self.demand_fc.setdefault(k, {})[days] = (round(float(q10), 3), round(float(p), 3), round(float(q90), 3))
        self.metrics["demand"] = {"method": "HistGradientBoostingRegressor (Poisson loss) point forecast + split-conformal 80% intervals, "
                                            "direct multi-horizon (7/14/30/60/90 days)",
                                  "split": f"fit: target windows ending before week {cal_start}; calibrate: windows ending weeks {cal_start}-{cutoff}; "
                                           f"test: origins from week {cutoff}",
                                  "series": len(keys), "by_horizon": results,
                                  "note": "Point forecast is the expected count (P50 column). Final models are refit on all history; the "
                                          "conformal offsets from the calibration slice are reused for the live forecast."}

    @staticmethod
    def _hgb_poisson():
        from sklearn.ensemble import HistGradientBoostingRegressor  # lazy: only needed while fitting

        return HistGradientBoostingRegressor(loss="poisson", max_iter=120, learning_rate=0.06, max_leaf_nodes=15, min_samples_leaf=40,
                                             random_state=RNG_SEED)

    @staticmethod
    def _hgb(q: float):
        from sklearn.ensemble import HistGradientBoostingRegressor  # lazy: only needed while fitting

        return HistGradientBoostingRegressor(loss="quantile", quantile=q, max_iter=150, learning_rate=0.06, max_leaf_nodes=15,
                                             min_samples_leaf=40, random_state=RNG_SEED)

    def _backtest(self, keys: list[tuple[str, str]], preds: np.ndarray, y: np.ndarray) -> None:
        # rows were appended series by series with origins cutoff..n-1 (H=1)
        per = ds.N_WEEKS - (ds.N_WEEKS - TEST_WEEKS)
        weeks = list(range(ds.N_WEEKS - TEST_WEEKS, ds.N_WEEKS))
        p = preds.reshape(len(keys), per, 3)
        a = y.reshape(len(keys), per)
        for i, w in enumerate(weeks):
            self.backtest.append({"week": w, "week_start": ds._week_start(w), "actual_total": int(a[:, i].sum()),
                                  "p50_total": round(float(p[:, i, 1].sum()), 2), "p10_total": round(float(p[:, i, 0].sum()), 2),
                                  "p90_total": round(float(p[:, i, 2].sum()), 2),
                                  "mae": round(float(np.mean(np.abs(p[:, i, 1] - a[:, i]))), 4),
                                  "coverage_80": round(float(np.mean((a[:, i] >= p[:, i, 0]) & (a[:, i] <= p[:, i, 2]))), 4)})

    # ------------------------------------------------------------------ 2. survival / RUL
    def _survival(self, units: list[dict[str, Any]], uw: list[dict[str, Any]]) -> None:
        from scipy.optimize import minimize  # lazy: only needed while fitting

        n = ds.N_WEEKS
        origin_eval = n - TEST_WEEKS
        health: dict[str, list[tuple[int, float]]] = {}
        for r in uw:
            if r["health"] is not None:
                health.setdefault(r["unit_id"], []).append((r["week"], r["health"]))

        def fit(rows: list[tuple[float, int]]) -> dict[str, float]:
            t = np.array([max(r[0], 0.5) for r in rows])
            e = np.array([r[1] for r in rows])

            def nll(p: np.ndarray) -> float:
                k, lam = math.exp(p[0]), math.exp(p[1])
                z = (t / lam) ** k
                return -float(np.sum(e * (np.log(k / lam) + (k - 1) * np.log(t / lam))) - np.sum(z))

            res = minimize(nll, x0=np.array([0.5, math.log(t.mean() * 1.5)]), method="Nelder-Mead", options={"maxiter": 600})
            return {"k": round(math.exp(res.x[0]), 4), "eta_weeks": round(math.exp(res.x[1]), 3), "n": int(len(t)), "failures": int(e.sum())}

        by_cat: dict[str, list[dict[str, Any]]] = {}
        for u in units:
            by_cat.setdefault(u["category_id"], []).append(u)
        eval_rows = []
        for cid, us in by_cat.items():
            # fit only on information available at the evaluation origin (no leakage): installs observed in-window, censored at origin
            train = []
            for u in us:
                if u["install_week"] < 0 or u["install_week"] >= origin_eval:
                    continue
                failed = u["removal_week"] is not None and u["removal_week"] < origin_eval
                end = u["removal_week"] if failed else origin_eval
                train.append((end - u["install_week"], 1 if failed else 0))
            w_eval = fit(train) if sum(r[1] for r in train) >= 3 else {"k": self.cat[cid]["weibull_k"], "eta_weeks": self.cat[cid]["weibull_eta_weeks"]}
            full = []
            for u in us:
                if u["install_week"] < 0:
                    continue
                failed = u["removal_week"] is not None
                full.append(((u["removal_week"] if failed else n) - u["install_week"], 1 if failed else 0))
            self.weibull[cid] = fit(full) if sum(r[1] for r in full) >= 3 else {**w_eval, "n": len(full), "failures": 0}
            for u in us:  # evaluation units: alive at origin and failed later inside the window
                if u["install_week"] < origin_eval and u["removal_week"] is not None and origin_eval <= u["removal_week"] < n:
                    age = origin_eval - u["install_week"]
                    surv = self._rul_survival(w_eval, age)
                    trend = self._rul_trend([h for h in health.get(u["id"], []) if h[0] < origin_eval])
                    eval_rows.append((u["removal_week"] - origin_eval, surv, trend))
        y = np.array([r[0] for r in eval_rows], dtype=float)
        s50 = np.array([r[1][1] for r in eval_rows])
        tr = np.array([r[2] if r[2] is not None else r[1][1] for r in eval_rows])
        comb = np.array([self._combine(r[1][1], r[2]) for r in eval_rows])
        self.metrics["rul"] = {
            "method": "Weibull survival (MLE, right-censored) conditional on age; health-trend extrapolation; combined = trend when >= 6 readings and degrading, else survival",
            "caveat": "Scored units are those that failed inside the test window, which favours early failures; survival estimates are biased high on this subset.",
            "split": f"fit on data before week {origin_eval}; scored on units alive then that failed later (censored units excluded)",
            "survival": _metrics_reg(y, s50, np.array([r[1][0] for r in eval_rows]), np.array([r[1][2] for r in eval_rows])),
            "health_trend": _metrics_reg(y, tr), "combined": _metrics_reg(y, comb), "units_scored": len(eval_rows), "unit": "weeks"}
        # current units
        for u in units:
            hs = health.get(u["id"], [])
            alive = u["removal_week"] is None
            age = n - u["install_week"] if alive else (u["removal_week"] - u["install_week"])
            rec = {"id": u["id"], "serial": u["serial"], "facility_id": u["facility_id"], "category_id": u["category_id"], "position": u["position"],
                   "install_week": u["install_week"], "removal_week": u["removal_week"], "status": u["status"], "age_weeks": age,
                   "engineering_revision": u["engineering_revision"], "last_health": hs[-1][1] if hs else None,
                   "health_slope_8w": self._slope(hs[-8:]) if len(hs) >= 4 else None}
            if alive:
                surv = self._rul_survival(self.weibull[u["category_id"]], age)
                trend = self._rul_trend(hs)
                rec.update(rul_p10=surv[0], rul_p50=surv[1], rul_p90=surv[2], rul_trend=trend, rul_combined=round(self._combine(surv[1], trend), 2))
            self.units[u["id"]] = rec

    @staticmethod
    def _rul_survival(w: dict[str, float], age: float) -> tuple[float, float, float]:
        k, eta = w["k"], w["eta_weeks"]
        base = (max(age, 0) / eta) ** k
        return tuple(round(eta * (base - math.log(1 - q)) ** (1 / k) - age, 2) for q in QUANTILES)  # type: ignore[return-value]

    @staticmethod
    def _slope(pts: list[tuple[int, float]]) -> float:
        x = np.array([p[0] for p in pts], dtype=float)
        y = np.array([p[1] for p in pts], dtype=float)
        return round(float(np.polyfit(x, y, 1)[0]), 5) if len(pts) >= 2 and x.std() > 0 else 0.0

    def _rul_trend(self, pts: list[tuple[int, float]]) -> float | None:
        pts = pts[-10:]
        if len(pts) < 6:
            return None
        slope = self._slope(pts)
        if slope >= -1e-4:
            return None
        return round(max(0.0, (0.2 - pts[-1][1]) / slope), 2)

    @staticmethod
    def _combine(surv50: float, trend: float | None) -> float:
        """Use the unit's own health trend when it has enough readings and is degrading; otherwise the category survival curve."""
        return surv50 if trend is None else trend

    # ------------------------------------------------------------------ 3/4. risk classifier and anomalies
    def _risk_and_anomaly(self, units: list[dict[str, Any]], uw: list[dict[str, Any]]) -> None:
        from sklearn.ensemble import IsolationForest, RandomForestClassifier  # lazy: only needed while fitting

        info = {u["id"]: u for u in units}
        n = ds.N_WEEKS
        cats = sorted(self.cat)
        rows, prev = [], {}
        for r in uw:
            u = info[r["unit_id"]]
            hp = prev.get(r["unit_id"])
            h = r["health"] if r["health"] is not None else (hp[0] if hp else 1.0)
            dh = h - hp[0] if hp else 0.0
            age = r["week"] - u["install_week"]
            w = self.cat[u["category_id"]]
            fail_in = (u["removal_week"] - r["week"]) if u["removal_week"] is not None else None
            label = 1 if fail_in is not None and 0 < fail_in <= 4 else 0
            rows.append((r["week"], [h, dh, r["vibration"], r["temperature"], r["pressure"], age / w["weibull_eta_weeks"], cats.index(u["category_id"]),
                                     1.0 if r["health"] is None else 0.0], label, r["anomaly"]))
            prev[r["unit_id"]] = (h,)
        cutoff = n - TEST_WEEKS
        tr = [r for r in rows if r[0] < cutoff - 4]
        te = [r for r in rows if cutoff <= r[0] < n - 4]
        Xtr, ytr = np.array([r[1] for r in tr]), np.array([r[2] for r in tr])
        Xte, yte = np.array([r[1] for r in te]), np.array([r[2] for r in te])
        clf = RandomForestClassifier(n_estimators=80, min_samples_leaf=8, random_state=RNG_SEED, n_jobs=2)
        clf.fit(Xtr, ytr)
        prob = clf.predict_proba(Xte)[:, 1]
        rule = (Xte[:, 0] < 0.35).astype(int)
        self.metrics["failure_risk_30d"] = {
            "method": "RandomForestClassifier on health, health change, vibration, temperature, pressure, normalised age",
            "label": "unit removed within the next 4 weeks", "split": f"train weeks < {cutoff - 4}; test weeks {cutoff}..{n - 5}",
            "model_at_0.5": _metrics_cls(yte, (prob >= 0.5).astype(int)), "baseline_health_below_0.35": _metrics_cls(yte, rule),
            "calibration": _calibration(yte.astype(float), prob)}
        # anomaly detection: sensor channels only, unsupervised fit on training weeks
        A_tr = np.array([[r[1][2], r[1][3], r[1][4], r[1][1]] for r in tr])
        A_te = np.array([[r[1][2], r[1][3], r[1][4], r[1][1]] for r in te])
        lab_tr = np.array([r[3] for r in tr])
        lab_te = np.array([r[3] for r in te])
        iso = IsolationForest(n_estimators=200, contamination=float(max(lab_tr.mean(), 0.005)), random_state=RNG_SEED).fit(A_tr)
        pred = (iso.predict(A_te) == -1).astype(int)
        mu, sd = A_tr.mean(axis=0), A_tr.std(axis=0) + 1e-9
        z = (np.abs((A_te - mu) / sd)[:, :3] > 3).any(axis=1).astype(int)
        self.metrics["anomaly"] = {"method": "IsolationForest on vibration, temperature, pressure, health change (unsupervised)",
                                   "ground_truth": "injected sensor anomalies + 3-week failure precursors (synthetic labels)",
                                   "split": f"fit on weeks < {cutoff - 4}; scored on weeks {cutoff}..{n - 5}",
                                   "isolation_forest": _metrics_cls(lab_te, pred), "baseline_zscore_gt3": _metrics_cls(lab_te, z)}
        # latest risk per alive unit
        latest: dict[str, list[float]] = {}
        for r, row in zip(uw, rows, strict=True):
            if r["week"] == n - 1:
                latest[r["unit_id"]] = row[1]
        if latest:
            ids = list(latest)
            pr = clf.predict_proba(np.array([latest[i] for i in ids]))[:, 1]
            an = iso.predict(np.array([[latest[i][2], latest[i][3], latest[i][4], latest[i][1]] for i in ids]))
            for i, p, a in zip(ids, pr, an, strict=True):
                if i in self.units:
                    self.units[i]["risk_30d"] = round(float(p), 4)
                    self.units[i]["anomaly_now"] = bool(a == -1)
        self.risk_importance = {name: round(float(v), 4) for name, v in zip(
            ["health", "health_change", "vibration", "temperature", "pressure", "age_vs_life", "category", "missing_reading"], clf.feature_importances_, strict=True)}

    # ------------------------------------------------------------------ 5/6. lead time and repair TAT
    def _lead_time(self, deliveries: list[dict[str, Any]]) -> None:
        sups, cats = sorted(self.sup), sorted(self.cat)
        hist: dict[str, list[float]] = {}
        X, y, w = [], [], []
        for d in deliveries:
            past = hist.get(d["supplier_id"], [])
            on_time = float(np.mean(past[-20:])) if past else 0.6
            X.append([sups.index(d["supplier_id"]), cats.index(d["category_id"]), d["promised_days"], d["qty"],
                      math.sin(2 * math.pi * d["ordered_week"] / 52), math.cos(2 * math.pi * d["ordered_week"] / 52), on_time])
            y.append(d["actual_days"])
            w.append(d["ordered_week"])
            if d["actual_days"] is not None:
                hist.setdefault(d["supplier_id"], []).append(1.0 if d["actual_days"] <= d["promised_days"] else 0.0)
        X, w = np.array(X), np.array(w)
        y = np.array([np.nan if v is None else v for v in y], dtype=float)
        self.lead_ratio = {}
        for d in deliveries:
            if d["actual_days"] is not None and d["ordered_week"] >= ds.N_WEEKS - 52:
                self.lead_ratio.setdefault(d["supplier_id"], []).append(d["actual_days"] / d["promised_days"])
        self.lead_ratio = {k: np.array(v) for k, v in self.lead_ratio.items()}
        ok = ~np.isnan(y)
        cutoff = ds.N_WEEKS - TEST_WEEKS
        tr, te = ok & (w < cutoff), ok & (w >= cutoff)
        models = [self._hgb(q).set_params(min_samples_leaf=15).fit(X[tr], y[tr]) for q in QUANTILES]
        p = _sort_q(np.column_stack([m.predict(X[te]) for m in models]))
        med = {s: float(np.median(y[tr][X[tr][:, 0] == i])) for i, s in enumerate(sups)}
        base = np.array([med[sups[int(i)]] for i in X[te][:, 0]])
        m = _metrics_reg(y[te], p[:, 1], p[:, 0], p[:, 2])
        m["baseline_supplier_median"] = _metrics_reg(y[te], base)
        late_true = (y[te] > X[te][:, 2]).astype(int)
        p_late = np.array([self._p_exceed(row, promised) for row, promised in zip(p, X[te][:, 2], strict=True)])
        m["late_delivery"] = {**_metrics_cls(late_true, (p_late >= 0.5).astype(int)), **_calibration(late_true.astype(float), p_late, 5)}
        m["missing_actuals_excluded"] = int((~ok).sum())
        self.metrics["lead_time"] = {"method": "HistGradientBoosting quantile regression; features: supplier, category, promised days, qty, season, "
                                               "supplier on-time rate from earlier deliveries only", "split": f"orders before week {cutoff} train", **m}
        final = [self._hgb(q).set_params(min_samples_leaf=15).fit(X[ok], y[ok]) for q in QUANTILES]
        late_by_sup: dict[str, list[float]] = {}
        for o in self.orders:
            past = hist.get(o["supplier_id"], [])
            x = [sups.index(o["supplier_id"]), cats.index(o["category_id"]), o["promised_days"], o["qty"],
                 math.sin(2 * math.pi * o["ordered_week"] / 52), math.cos(2 * math.pi * o["ordered_week"] / 52), float(np.mean(past[-20:])) if past else 0.6]
            q = np.sort(np.array([f.predict(np.array([x]))[0] for f in final]))
            self.lead_q[o["id"]] = tuple(round(float(v), 2) for v in q)
            late_by_sup.setdefault(o["supplier_id"], []).append(self._p_exceed(q, o["promised_days"]))
        for s in sups:
            if s in late_by_sup:
                self.supplier_late[s] = round(float(np.mean(late_by_sup[s])), 4)
            else:
                past = hist.get(s, [])
                self.supplier_late[s] = round(1 - float(np.mean(past[-20:])), 4) if past else 0.5

    @staticmethod
    def _p_exceed(q: np.ndarray, threshold: float) -> float:
        """P(lead time > threshold) from the piecewise-linear quantile function."""
        u = np.linspace(0, 1, 201)
        vals = _q_sample(float(q[0]), float(q[1]), float(q[2]), u)
        return round(float(np.mean(vals > threshold)), 4)

    def _repairs(self, repairs: list[dict[str, Any]]) -> None:
        cutoff = ds.N_WEEKS - TEST_WEEKS
        groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for r in repairs:
            groups.setdefault((r["center_id"], r["category_id"]), []).append(r)
        y, lo, mid, hi = [], [], [], []
        for k, rs in groups.items():
            tr = np.array([r["tat_days"] for r in rs if r["received_week"] < cutoff])
            if len(tr) < 4:
                continue
            q = np.quantile(tr, QUANTILES)
            self.repair_q[k] = tuple(round(float(v), 2) for v in q)
            for r in rs:
                if r["received_week"] >= cutoff:
                    y.append(r["tat_days"])
                    lo.append(q[0])
                    mid.append(q[1])
                    hi.append(q[2])
        self.metrics["repair_turnaround"] = {"method": "empirical quantiles per (repair center, category) from earlier repairs",
                                             "split": f"repairs received before week {cutoff} fit; later repairs scored",
                                             **_metrics_reg(np.array(y), np.array(mid), np.array(lo), np.array(hi)), "unit": "days"}

    # ------------------------------------------------------------------ 7/8. inventory Monte Carlo, workload, cost
    def _inventory(self, inv: list[dict[str, Any]]) -> None:
        self.inv_rows = {(r["facility_id"], r["category_id"]): r for r in inv}
        for k in self.inv_rows:
            if k in self.demand_fc:
                self.inventory[k] = self.inventory_sim(*k)
        # unscheduled-work crew per hub = 125% of its average historical weekly removal hours (stated assumption)
        self.crew_hours: dict[str, float] = {}
        for (f, c), hist in self.demand_hist.items():
            self.crew_hours[f] = self.crew_hours.get(f, 0.0) + float(np.mean(hist)) * self.cat[c]["labor_hours"] * CREW_HEADROOM

    def inventory_sim(self, fid: str, cid: str, supplier_delay: dict[str, float] | None = None, demand_mult: float = 1.0,
                      extra_stock: int = 0, reroute_to: str | None = None, seed_key: str = "") -> dict[int, dict[str, float]]:
        """Weekly (s, Q) inventory simulation, MC_DRAWS seeded paths.

        Demand: each path draws a 90-day demand percentile u from the forecast's quantile function and then Poisson weekly removals
        at that path's rate. Open purchase orders arrive at their model-predicted lead time; whenever stock position falls to the
        reorder point a new order of max(ROP, 4 weeks of demand) is placed with the primary supplier (or `reroute_to`), whose lead
        time is promised days x a ratio resampled from that supplier's recorded deliveries, plus any scenario delay.
        """
        inv = self.inv_rows[(fid, cid)]
        rng = np.random.default_rng(int(hashlib.sha256(f"{fid}|{cid}|{seed_key}".encode()).hexdigest()[:8], 16))
        D, T = MC_DRAWS, 13
        q90 = self.demand_fc[(fid, cid)][90]
        rate = np.maximum(_q_sample(*q90, rng.random(D)), 0) / T * demand_mult
        arrivals = np.zeros((D, T + 40))
        for o in self.orders:
            if o["facility_id"] != fid or o["category_id"] != cid:
                continue
            delay = (supplier_delay or {}).get(o["supplier_id"], 0.0)
            lead = _q_sample(*self.lead_q[o["id"]], rng.random(D)) + delay - (ds.N_WEEKS - o["ordered_week"]) * 7
            idx = np.clip(np.ceil(np.maximum(lead, 0) / 7).astype(int), 0, T + 39)
            np.add.at(arrivals, (np.arange(D), idx), o["qty"])
        links = [lk for lk in self.links if lk["category_id"] == cid]
        primary = max(links, key=lambda lk: lk["share"])
        if reroute_to:
            primary = next((lk for lk in links if lk["supplier_id"] == reroute_to), primary)
        ratios = self.lead_ratio.get(primary["supplier_id"], np.array([1.0]))
        rop = max(inv["reorder_point"], 1)
        mean_week = float(np.mean(self.demand_hist[(fid, cid)][-26:]))
        order_q = max(rop, int(math.ceil(mean_week * 4)), 1)
        on_hand = np.full(D, float(inv["on_hand"] + extra_stock))
        out = {0: {"p10": float(inv["on_hand"]), "p50": float(inv["on_hand"]), "p90": float(inv["on_hand"]),
                   "stockout_prob": 0.0 if inv["on_hand"] > 0 else 1.0, "expected_backorders": 0.0}}
        marks = {1: 7, 2: 14, 4: 30, 9: 60, 13: 90}
        delay_p = (supplier_delay or {}).get(primary["supplier_id"], 0.0)
        for t in range(T):
            on_hand += arrivals[:, t]
            on_hand -= rng.poisson(rate)
            position = on_hand + arrivals[:, t + 1:].sum(axis=1)
            need = position <= rop
            if need.any():
                lead = primary["promised_days"] * rng.choice(ratios, D) + delay_p
                idx = np.clip(t + 1 + np.ceil(lead / 7).astype(int), 0, T + 39)
                rows = np.nonzero(need)[0]
                np.add.at(arrivals, (rows, idx[rows]), order_q)
            if t + 1 in marks:
                lv = on_hand
                out[marks[t + 1]] = {"p10": round(float(np.quantile(lv, 0.1)), 2), "p50": round(float(np.quantile(lv, 0.5)), 2),
                                     "p90": round(float(np.quantile(lv, 0.9)), 2), "stockout_prob": round(float(np.mean(lv < 0)), 4),
                                     "expected_backorders": round(float(np.mean(np.maximum(-lv, 0))), 3)}
        return out

    def _persist(self) -> None:
        with db.session(write=True) as conn:
            conn.execute("INSERT INTO forecast_runs (id, ts, model_version, dataset, data_hash, build_ms, metrics_json) VALUES (?,?,?,?,?,?,?)",
                         (f"FC-{self.data_hash}-{int(time.time())}", self.built_at, MODEL_VERSION, f"{ds.DATASET_VERSION}:{ds.GLOBAL_SEED}",
                          self.data_hash, self.build_ms, db.jdump(self.metrics)))

    # ------------------------------------------------------------------ query helpers (all deterministic)
    def freshness(self) -> dict[str, Any]:
        return {"loaded_from_cache": getattr(self, "loaded_from_cache", False), "data_as_of": DEMO_TODAY, "forecast_origin": DEMO_TODAY, "models_built_at": self.built_at, "model_version": MODEL_VERSION,
                "dataset": f"{ds.DATASET_VERSION} (seed {ds.GLOBAL_SEED})", "synthetic": True, "build_ms": self.build_ms}

    def demand(self, days: int, facility: str | None = None, category: str | None = None, region: str | None = None) -> list[dict[str, Any]]:
        out = []
        for (f, c), fc in self.demand_fc.items():
            if (facility and f != facility) or (category and c != category) or (region and self.fac[f]["region"] != region):
                continue
            if days == 0:
                q = (0.0, 0.0, 0.0)
            else:
                q = fc[days]
            out.append({"facility_id": f, "category_id": c, "p10": q[0], "p50": q[1], "p90": q[2]})
        return out

    def _days(self, days: int) -> int:
        return min([0, *HORIZONS_DAYS], key=lambda d: abs(d - days))

    def active_disruptions(self, day: int) -> list[dict[str, Any]]:
        out = []
        for d in self.disruptions:
            end = d["start_day"] + d["duration_days"]
            if d["start_day"] <= day < end:
                prog = (day - d["start_day"]) / d["duration_days"]
                out.append({**d, "end_day": end, "recovery_progress": round(prog, 3), "days_to_restore": end - day, "phase": "active"})
            elif end <= day < end + 14:
                out.append({**d, "end_day": end, "recovery_progress": 1.0, "days_to_restore": 0, "phase": "recovered"})
        return out

    def facility_state(self, days: int) -> list[dict[str, Any]]:
        days = self._days(days)
        dis = self.active_disruptions(days)
        out = []
        for fid, f in self.fac.items():
            rec: dict[str, Any] = {k: f[k] for k in ("id", "name", "kind", "city", "country", "region", "lat", "lon")}
            us = [u for u in self.units.values() if u["facility_id"] == fid and u["status"] == "installed"]
            if us:
                proj = [max(0.0, min(1.0, (u["last_health"] or 0.5) + (u["health_slope_8w"] or 0) * days / 7)) for u in us]
                rec["health_mean"] = round(float(np.mean(proj)), 4)
                rec["units_tracked"] = len(us)
                rec["units_due"] = sum(1 for u in us if u.get("rul_combined") is not None and u["rul_combined"] * 7 <= max(days, 7))
                rec["high_risk_units"] = sum(1 for u in us if (u.get("risk_30d") or 0) >= 0.5)
            dem = self.demand(days, facility=fid) if days else []
            if dem:
                rec["demand_p50"] = round(sum(d["p50"] for d in dem), 2)
                rec["demand_p10"] = round(sum(d["p10"] for d in dem), 2)
                rec["demand_p90"] = round(sum(d["p90"] for d in dem), 2)
                hours = sum(d["p50"] * self.cat[d["category_id"]]["labor_hours"] for d in dem)
                weeks = days / 7
                cut = max([x["capacity_cut"] for x in dis if x["facility_id"] == fid and x["phase"] == "active"] or [0.0])
                cap = self.crew_hours.get(fid, 1.0) * (1 - cut)
                rec["workload_hours_p50"] = round(hours, 1)
                rec["workload_utilisation"] = round(hours / weeks / max(cap, 1), 4)
                rec["capacity_cut"] = cut
                rec["cost_p50_usd"] = round(sum(d["p50"] * (self.cat[d["category_id"]]["unit_cost_usd"] + LABOR_RATE * self.cat[d["category_id"]]["labor_hours"]) for d in dem), 0)
            inv = [(c, v[days]) for (fa, c), v in self.inventory.items() if fa == fid]
            if inv:
                short = [{"category_id": c, **x} for c, x in inv if x["stockout_prob"] >= 0.2]
                rec["shortages"] = sorted(short, key=lambda s: -s["stockout_prob"])
                rec["shortage_count"] = len(short)
                rec["max_stockout_prob"] = max(x["stockout_prob"] for _, x in inv)
            rec["disruptions"] = [x["id"] for x in dis if x["facility_id"] == fid]
            out.append(rec)
        return out

    def supplier_state(self, days: int) -> list[dict[str, Any]]:
        days = self._days(days)
        dis = self.active_disruptions(days)
        out = []
        for sid, s in self.sup.items():
            add = sum(x["lead_time_add_days"] for x in dis if (x["supplier_id"] == sid or (not x["supplier_id"] and not x["facility_id"]
                                                                                         and x["region"] == s["region"])) and x["phase"] == "active")
            base = self.supplier_late.get(sid, 0.5)
            # disruption adds days to every open order; recompute late probability with shifted lead-time quantiles
            ords = [o for o in self.orders if o["supplier_id"] == sid]
            if ords and add:
                p = float(np.mean([self._p_exceed(np.array(self.lead_q[o["id"]]) + add, o["promised_days"]) for o in ords]))
            else:
                p = base
            out.append({k: s[k] for k in ("id", "name", "city", "country", "region", "lat", "lon")} | {
                "late_probability": round(p, 4), "baseline_late_probability": base, "disruption_days_added": add, "open_orders": len(ords),
                "categories": [lk["category_id"] for lk in self.links if lk["supplier_id"] == sid]})
        return out


_engine: Engine | None = None
_lock = threading.Lock()


def _cache_path():
    from app.core.config import get_settings

    return get_settings().data_dir / f"forecast_cache_{MODEL_VERSION}_{ds.DATASET_VERSION}_{ds.GLOBAL_SEED}.pkl"


def engine() -> Engine:
    """Fitted engine. Results (not code) are cached in the local data folder, keyed by model version and dataset seed,
    so a restart does not refit; the cache file is written only by this process and lives next to the SQLite database."""
    global _engine
    if _engine is None:
        with _lock:
            if _engine is None:
                path = _cache_path()
                if path.exists():
                    try:
                        with open(path, "rb") as fh:
                            cached = pickle.load(fh)  # noqa: S301 - local file written by this application
                        with db.session(write=True) as conn:
                            ds.ensure(conn)
                        cached.loaded_from_cache = True
                        _engine = cached
                        return _engine
                    except Exception:  # noqa: BLE001 - stale or unreadable cache: refit
                        path.unlink(missing_ok=True)
                built = Engine().build()
                try:
                    with open(path, "wb") as fh:
                        pickle.dump(built, fh)
                except OSError:
                    pass
                _engine = built
    return _engine


def reset_engine() -> None:
    global _engine
    with _lock:
        _engine = None
        try:
            _cache_path().unlink(missing_ok=True)
        except OSError:
            pass
