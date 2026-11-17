# Evaluation report — dataset `syn-v1` (SYNTHETIC)

> **Read this first.** Every number below comes from generated data. It proves the pipeline runs, catches defects, avoids leakage and
> applies costs. It says **nothing** about whether any model works on real markets.

Reproduce (from `flowwealth/backend`):

```bash
uv run python -m flowwealth.data.pipeline --lake lake --version syn-v1
```
```bash
uv run python -m flowwealth.research.experiment --lake lake --version syn-v1 --out reports
```
```bash
uv run python -m flowwealth.research.replay --lake lake --version syn-v1 --out artifacts
```

## 1. Dataset quality

| Item | Value |
|---|---|
| Rows (after cleaning) | **1,119,431** daily bars |
| Instruments | 650 across 11 exchanges / 10 countries / 10 sectors, ~8% later delisted, staggered listings |
| Span | 2019-01-01 → 2025-12-31 |
| Build time | 6.4 s (generate 1.2 s, clean + timestamp 4.3 s) on 4 CPUs |
| Content hash | `4b3aa5e87c6e3fd8…` (in manifest) |
| Injected → detected | duplicates 50 → 50 · bad ticks 20 → 20 flagged outliers · gaps 200 → 200 · 2:1 split → adj_close continuous |
| OHLC violations / non-positive prices | 0 / 0 |
| Quality score | 99.969 overall, 99.573 worst ticker |

## 2. Cross-sectional 5-day forecasting experiment

Target: 5-bar excess log return vs availability cohort. 10 rank-normalised price/volume features. 1,080,335 modelled rows.

| Split | Rows | Window |
|---|---|---|
| train | 639,606 | 2019-03-26 → 2023-04-14 |
| validation | 213,431 | 2023-04-28 → 2024-08-15 |
| holdout | 212,174 | 2024-09-02 → 2025-12-31 |

Embargo 10 days between segments; training labels purged at each boundary.

**Walk-forward (4 expanding folds inside train+validation)**

| Model | Mean IC | Folds positive |
|---|---|---|
| ridge | 0.0156 | 4/4 |
| lightgbm | 0.0099 | 3/4 |
| momentum (baseline) | −0.0025 | 1/4 |
| reversal_5d (baseline) | −0.0128 | 0/4 |

**Holdout, scored once** (IC over 2,055 availability cohorts; long/short deciles rebalanced every 5 bars)

| Model | Rank IC | t | Sharpe gross | Sharpe **net** | Net total | Net max DD | Avg turnover |
|---|---|---|---|---|---|---|---|
| momentum (baseline) | 0.0066 | 2.31 | 0.15 | **−0.74** | −4.4% | −9.5% | 61% |
| reversal_5d (baseline) | −0.0044 | −1.47 | −1.00 | **−3.62** | −18.6% | −18.9% | 173% |
| ridge | 0.0073 | 2.56 | 2.30 | **−0.66** | −3.1% | −4.9% | 165% |
| lightgbm | 0.0115 | 4.08 | 2.21 | **−0.47** | −2.3% | −3.1% | 149% |

Reading: the ML models find a statistically detectable but tiny ranking signal (the generator plants a weak autocorrelation). Turnover of
~150% per rebalance turns a gross Sharpe above 2 into a net loss. **Under the promotion criteria no model is eligible.** This is the intended
behaviour of the gate.

## 3. Prediction Memory replay

40 rebalance dates × 20 forecasts (top-10 / bottom-10), recorded on a simulated clock before each outcome, resolved afterwards.

| Metric | Value |
|---|---|
| Forecasts recorded / resolved | 800 / 800 |
| Hash chain | verified |
| Directional accuracy vs excess | 50.0% |
| Rank IC vs excess | −0.015 |
| By regime (direction correct) | bear 51% (456) · bull 53% (120) · sideways 44% (179) · high-vol 35% (40) |
| Max feature drift PSI (dev → holdout) | 0.061 (`vol_ratio`), all features stable |

The model's small positive holdout IC across the full cross-section does **not** show up in its extreme picks over 40 dates — the kind of
gap Prediction Memory is designed to expose.

## 4. Crash-risk alarm

Event: equal-weight index falls ≥ 10% within the next 20 trading days (base rate 120 / 1,827 days = 6.6%).

| Alarm at | Alarm days | Precision | Recall | False-alarm days | Missed event days |
|---|---|---|---|---|---|
| Elevated+ | 1,005 | 9.3% | 77.5% | 912 | 27 |
| High+ | 418 | 10.3% | 35.8% | 375 | 77 |

Lift over base rate is ~1.5×; the alarm is weak and noisy. Thresholds were fixed in advance and deliberately not re-tuned on this history.

## 5. Bugs found by this evaluation

| Bug | Effect | Fix | Guard |
|---|---|---|---|
| Ranks and decile selection grouped by UTC date | Asian/Australian signals used New York data from ~15 h later (look-ahead) | group by `available_at` cohort | `test_ranks_do_not_use_later_closing_markets` (fails on old code) |
| Delisting bar got a zero label ending at its own timestamp | label_end == signal time | no label on the delisting bar | `test_labels_end_after_signal_and_delisting_return_kept` |
| Excess-return forecasts scored against raw returns | misleading IC | also score vs benchmark-excess | `evaluate_records` fields `*_vs_excess` |
| Drawdown measured from all-time peak | stress flag stuck on for years after one crash | 1-year rolling peak | — |
| NaN in API JSON | 500 errors | sanitiser on every response | `test_nan_is_serialised_as_null` |

## 6. Test results (this session)

| Suite | Result |
|---|---|
| Backend `uv run pytest` | **41 passed** (data foundation 11, leakage & research 10, accountability 6, risk 9, API 5) |
| Frontend `npm test` | **9 passed** |
| Frontend `npm run typecheck`, `npm run build` | pass (bundle 321 kB, 100 kB gzip) |
| CI smoke (80 tickers: lake → experiment → replay) | pass locally |
| Browser check of 12 views against live API | 0 console errors |
| GitHub Actions run | not yet executed (workflow added; runs on PR/push to master) |
