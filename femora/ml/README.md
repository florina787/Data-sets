# FEMORA Muse: forecasting & prediction models

Open-source, reproducible models trained on **real public data**. No synthetic or invented health records.

## Data
| | |
|---|---|
| Source | CDC **NHANES** public-use files, cycles 2013–14, 2015–16, 2017–18 (reproductive health, demographics, body measures, smoking) |
| Women in source files | **10,375** |
| Analysis cohort | **4,640** women aged 20–64 with known natural-menopause status (1,221 events). Surgical menopause, pregnancy and breastfeeding excluded. |
| Licence | Public domain (U.S. government work). Raw files are downloaded by script and not committed. |
| Historical view | Birth generations 1950s / 1960s / 1970s compared within the same data |

## Models (all open source)
| Model | Framework | Result (held-out 20%) |
|---|---|---|
| Survey-weighted Kaplan–Meier, age at natural menopause, bootstrap 95% CI | **lifelines** | Median **51.0 years**; at 48: 24% (22–27%); at 51: 52% (48–56%) |
| Weibull AFT with smoking, BMI, menarche age, pregnancies | **lifelines** | Concordance **0.535**: covariates add little. Current smoking: time ratio 0.958 (≈2 years earlier) |
| P(reached natural menopause) classifiers vs age-only baseline | **scikit-learn** | Age-only AUC **0.988**; full logistic 0.987; gradient boosting 0.986. **Covariates add no discrimination beyond age.** |
| Generational trend (women 45–55) | **statsmodels** Logit | OR per birth year 1.026 (95% CI 0.94–1.13), p = 0.58: **no detectable shift**; 1950s and 1960s medians both 51 |
| Personal next-period forecast | TypeScript (in app) | Exponentially weighted cycle mean, ~80% empirical interval, rolling-origin backtest on *her own* history; declines when cycles are too irregular |

## What these models are, and are not
- ✅ Population context: "Among U.S. women aged 48, about 24% had reached natural menopause."
- ❌ Not a prediction of any individual's final menstrual period, and not clinically validated.
- U.S. data, self-reported age at last period (recall error), cross-sectional design.
- The personal cycle forecaster hasn't been validated on an external longitudinal cycle dataset yet. Candidate open datasets require registration (e.g. via Kaggle/ICPSR).

## Reproduce
```bash
cd femora/ml
python -m venv .venv && .venv/bin/pip install pandas numpy scikit-learn lifelines statsmodels scipy
.venv/bin/python download_nhanes.py
.venv/bin/python train_menopause.py      # writes web/src/modules/forecast/model.json and reports/metrics.json
```
