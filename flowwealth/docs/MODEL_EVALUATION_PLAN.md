# Model evaluation plan

## Principles

1. Time only moves forward: chronological splits, never shuffled; purge training rows whose label window reaches the test period; embargo gap.
2. Every candidate is compared with **simple baselines** (zero, 60-day momentum, 5-day reversal) under identical splits and costs.
3. Holdout is scored **once** per candidate after model selection on walk-forward folds inside train+validation.
4. Rank IC per *availability cohort* is the primary forecast metric; directional accuracy is reported but never alone.
5. Backtests report **gross and net** (commission, spread scaled by volatility, slippage, square-root impact, borrow, 5% ADV cap).
6. 1M rows ≠ 1M independent observations: significance uses per-cohort IC (≈2,000 cohorts on holdout), not row counts.
7. No confidence is displayed unless a model is calibrated (ECE ≤ 0.05 on holdout); current models emit uncalibrated scores.

## Splits (configurable)

`chronological_split(fractions=(0.6, 0.2, 0.2), embargo_days=2×horizon)` and `walk_forward(n_folds=4, expanding=True)`.
Leakage guarantees are tested: features on truncated history equal features on full history (including a mid-UTC-day cut that separates
Asian from New York closes), all training `label_end` < test start, embargo ≥ configured days.

## Labels

Per horizon h: `fwd_ret_h` (log return t→t+h), `fwd_xs_h` (excess over the cohort mean), `fwd_up_h`, `label_end_h`. A ticker that delists
inside the horizon receives its delisting return; the delisting bar itself has no label.
Planned additional targets: realised volatility, forward max drawdown, regime label.

## Promotion criteria (`evaluation/registry.py: PromotionCriteria`)

| Criterion | Default |
|---|---|
| Holdout IC t-stat | ≥ 2.0 |
| Walk-forward folds with positive IC | ≥ 75% |
| Net Sharpe | > 0 |
| Beats every baseline's net Sharpe | required |
| Margin over current champion's net Sharpe | ≥ 0.1 |
| Net max drawdown | better than −25% |
| Calibration (if probabilistic) | ECE ≤ 0.05 |
| Holdout length | ≥ 120 cohorts |
| Human approver | required (`approved_by`) |

Rollback restores the previous champion; every register/refusal/promotion/rollback is logged with time and approver.

## Monitoring after promotion

* Prediction Memory records every forecast before its target time; `resolve_due` scores it afterwards (raw, benchmark, excess).
* `check_degradation`: flags when recent rank IC < 0 or < 50% of reference, with ≥ 30 resolved forecasts. Action is **flag only**:
  retraining produces a challenger that must pass the same criteria; there is no automatic retrain loop.
* Feature drift: PSI per feature, reference = development window (> 0.25 significant).
* Self-generated labels are never used for training: outcomes come from the lake, not from model output.

## Planned evaluations not yet run

Purged k-fold CV (combinatorial), deflated Sharpe / multiple-testing adjustment across all tried configurations, parameter-stability sweeps,
Monte Carlo of trade order, regime-conditional promotion, calibration via isotonic regression on validation.
