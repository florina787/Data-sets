# Forecasting engine

Code: `backend/app/global_intel/forecast.py` (models, evaluation, inventory simulation), `dataset.py` (data), `simulate.py`
(supply-chain and resilience). Raw metrics: [`docs/eval/forecast_metrics_3_0.json`](eval/forecast_metrics_3_0.json).

> All data is SYNTHETIC (seed 20261102). NASA C-MAPSS was not used: the engine runs on a reproducible synthetic dataset with
> documented assumptions, and simulated degradation is never presented as real aircraft telemetry.

## Dataset (reproducible, referentially consistent)

12 fictional facilities (6 MRO hubs, 2 repair centers, 2 warehouses, 2 manufacturing sites) in real civilian cities, 8 fictional
suppliers, 20 component categories, 104 weekly periods ending 2026-10-23, 953 tracked units (49,442 unit-weeks), 12,480 demand
rows, 1,080 deliveries, 799 repairs, 8 synthetic disruption notices. Missing-data scenarios: 3% of health readings and 2% of
delivery actuals are missing. Assumptions are returned by every API response and listed in `dataset.assumptions()`.

## Models and evaluation design

Every task uses a **temporal split**: models are fit on earlier weeks and scored on the last 26 weeks, which they never saw.

| Task | Method | Baseline | Split |
|---|---|---|---|
| Removal / replacement-part demand (7-90 d) | HistGradientBoosting, Poisson loss, direct multi-horizon; split-conformal 80% intervals | moving average, seasonal naive | fit < week 65 · calibrate 65-78 · test ≥ 78 |
| Remaining useful life | Weibull survival (MLE, right-censored) conditional on age; per-unit health-trend extrapolation | survival-only | fit before week 78, score units failing after |
| Failure within 30 days | RandomForest classifier | health < 0.35 rule | train < 74, test 78-99 |
| Component anomalies | IsolationForest (unsupervised) | z-score > 3 rule | fit < 74, test 78-99 |
| Supplier lead time | HistGradientBoosting quantile regression (P10/P50/P90); on-time rate from earlier deliveries only | supplier median | orders before week 78 |
| Repair turnaround | empirical quantiles per (center, category) | — | repairs before week 78 |
| Inventory depletion | weekly (s, Q) reorder simulation, 400 seeded paths | — | — |
| Workload, cost | demand × labour hours / unit cost (USD 95/h assumption) | — | — |

Leakage controls: lag features use only weeks before the forecast origin; the supplier on-time feature is an expanding mean over
earlier deliveries; the Weibull fits used for scoring see only data before the scoring origin; conformal offsets come from a
calibration slice that is neither training nor test.

## Measured results (held-out, synthetic data)

| Demand horizon | Model MAE | Moving-average MAE | Seasonal-naive MAE | 80% interval coverage | Bias |
|---|---|---|---|---|---|
| 7 days | 0.641 | 0.648 | 0.738 | 78.0% | -0.01 |
| 14 days | 0.924 | 0.975 | 1.134 | 77.8% | -0.04 |
| 30 days | 1.391 | 1.506 | 1.662 | 75.2% | -0.04 |
| 60 days | 2.251 | 2.948 | 2.585 | 72.3% | -0.13 |
| 90 days | 2.861 | 4.029 | 3.145 | 66.7% | -0.10 |

* The model beats both baselines at every horizon; the gain grows with horizon (29% lower MAE than the moving average at 90 days).
* **Intervals under-cover at long horizons** (66.7% at 90 days vs the 80% target). Treat 60-90-day intervals as optimistic.

| Other task | Result | Baseline |
|---|---|---|
| Failure within 30 days (RandomForest, threshold 0.5) | precision 0.959, recall 0.771, F1 0.855; ECE 0.006, Brier 0.0065 | health rule F1 0.541 |
| Anomaly detection | IsolationForest F1 0.869 | **z-score rule F1 0.974 — the simpler rule wins on this data** |
| Remaining useful life (103 units) | health-trend MAE 9.5 weeks; survival-only MAE 36.7 weeks (80% interval coverage 57%) | — |
| Supplier lead time | MAE 6.1 days, 80% coverage 63.9%; late-delivery F1 0.826, Brier 0.195 | supplier median MAE 8.7 days |
| Repair turnaround | MAE 4.7 days, 80% coverage 68.9% | — |

Caveat on RUL: the scored units are those that failed inside the test window, which favours early failures; the survival model is
biased high on that subset. The production estimate therefore uses the unit's own health trend when it has at least six readings and
is degrading, and the survival curve otherwise.

## Inventory simulation

For each hub × category: each of 400 seeded paths draws a 90-day demand percentile from the forecast's quantile function, then
Poisson weekly removals at that rate. Open purchase orders arrive at their model-predicted lead time; when stock position reaches the
reorder point a new order of max(ROP, 4 weeks of demand) goes to the primary supplier, whose lead time is promised days × a ratio
resampled from its recorded deliveries (+ any scenario delay). Scenario variants reuse the same random stream, so differences come
from the scenario only. "Shortage" = stockout probability ≥ 20% at the horizon.

## Reproducibility and caching

Seeds: dataset 20261102, models/simulation 20261102. Fitting takes about 11 s on 4 CPUs (up to ~45 s when competing with first-run
seeding). Results are cached in the data folder (`forecast_cache_<model>_<dataset>_<seed>.pkl`, written only by this process) so a
restart does not refit; `POST /api/demo/reset` clears the cache. `scripts/setup.sh` pre-fits once (`python -m app.global_intel.prefit`) so the
first map request never waits. Fitting slows sharply when it competes for CPU (153 s instead of 12 s while headless Chromium was rendering
WebGL in software during e2e tests), which is why it is done up front. Each fit is recorded in `forecast_runs`. `test_models_are_reproducible`
refits from scratch and compares metrics and simulation output exactly.
