"""
FEMORA Muse: menopause-timing models trained on real NHANES data (open-source stack).

Data:   CDC NHANES 2013-2014 (H), 2015-2016 (I), 2017-2018 (J): public-domain U.S. national survey.
        Files: RHQ (reproductive health), DEMO (demographics, survey weights), BMX (body measures), SMQ (smoking).
Models: 1. Kaplan-Meier curve of age at natural menopause (survey-weighted)          [lifelines]
        2. Weibull accelerated-failure-time model with covariates                    [lifelines]
        3. Classifier: P(reached natural menopause | age, profile) vs age-only base   [scikit-learn]
Output: femora/web/src/modules/forecast/model.json (small, aggregate; no individual records)
        femora/ml/reports/metrics.json and figures

Population-level estimates only. They do not predict an individual's final menstrual period.
Run:    python download_nhanes.py && python train_menopause.py
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from lifelines import KaplanMeierFitter, WeibullAFTFitter
from lifelines.utils import concordance_index
from sklearn.calibration import calibration_curve
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).parent
RAW = ROOT / "data" / "raw"
REPORTS = ROOT / "reports"
OUT = ROOT.parent / "web" / "src" / "modules" / "forecast" / "model.json"
CYCLES = {"H": "2013-2014", "I": "2015-2016", "J": "2017-2018"}
SEED = 7


def load_cycle(c: str) -> pd.DataFrame:
    read = lambda f: pd.read_sas(RAW / f"{f}_{c}.XPT", format="xport")
    rhq, demo = read("RHQ"), read("DEMO")
    bmx, smq = read("BMX")[["SEQN", "BMXBMI"]], read("SMQ")[["SEQN", "SMQ020", "SMQ040"]]
    keep = ["SEQN", "RHQ010", "RHQ031", "RHD043", "RHQ060", "RHD280", "RHQ305", "RHQ160", "RHQ540"]
    df = rhq[[k for k in keep if k in rhq]].merge(demo[["SEQN", "RIAGENDR", "RIDAGEYR", "RIDRETH3", "WTINT2YR"]], on="SEQN")
    df = df.merge(bmx, on="SEQN", how="left").merge(smq, on="SEQN", how="left")
    df["cycle"] = CYCLES[c]
    df["weight"] = df["WTINT2YR"] / len(CYCLES)  # combine 2-year weights across cycles (NCHS guidance)
    return df


def build() -> tuple[pd.DataFrame, dict]:
    raw = pd.concat([load_cycle(c) for c in CYCLES], ignore_index=True)
    flow = {"women_in_rhq_files": int(len(raw))}
    df = raw[(raw.RIAGENDR == 2) & raw.RIDAGEYR.between(20, 64)].copy()
    flow["women_aged_20_64"] = int(len(df))
    # Exclusions: surgical menopause, pregnancy/breastfeeding, unknown status
    surgical = (df.RHD280 == 1) | (df.RHQ305 == 1) | (df.RHD043 == 3)
    preg = df.RHD043.isin([1, 2])
    df = df[~surgical & ~preg]
    flow["after_excluding_surgical_pregnancy_breastfeeding"] = int(len(df))
    natural = (df.RHQ031 == 2) & (df.RHD043 == 7)
    premeno = df.RHQ031 == 1
    df = df[natural | premeno].copy()
    df["event"] = ((df.RHQ031 == 2) & (df.RHD043 == 7)).astype(int)
    # Time: age at last period for events (top/bottom-coded 19/60; 777/999 = missing), current age otherwise (censored)
    age_lmp = df.RHQ060.where(df.RHQ060.between(19, 60))
    df["time"] = np.where(df.event == 1, age_lmp, df.RIDAGEYR)
    df = df[df.time.notna() & (df.time <= df.RIDAGEYR + 0.5)]
    flow["analysis_cohort"] = int(len(df))
    flow["natural_menopause_events"] = int(df.event.sum())
    # Covariates (missing -> median + indicator handled by simple imputation below)
    df["smoker_ever"] = (df.SMQ020 == 1).astype(float)
    df["smoker_current"] = df.SMQ040.isin([1, 2]).astype(float)
    df["bmi"] = df.BMXBMI
    df["menarche_age"] = df.RHQ010.where(df.RHQ010.between(8, 20))
    df["pregnancies"] = df.RHQ160.where(df.RHQ160.between(0, 20)).fillna(0)
    for c in ["bmi", "menarche_age"]:
        df[c] = df[c].fillna(df[c].median())
    return df, flow


def km(df: pd.DataFrame, n_boot: int = 200) -> dict:
    """Survey-weighted Kaplan-Meier; 95% CI by bootstrap over women (weighted KM's analytic CI is invalid)."""
    ages = list(range(35, 61))
    fit = lambda d: 1 - KaplanMeierFitter().fit(d.time, d.event, weights=d.weight).survival_function_at_times(ages).values
    point = fit(df)
    rng = np.random.default_rng(SEED)
    boots = np.array([fit(df.iloc[rng.integers(0, len(df), len(df))]) for _ in range(n_boot)])
    lo, hi = np.percentile(boots, 2.5, axis=0), np.percentile(boots, 97.5, axis=0)
    k = KaplanMeierFitter().fit(df.time, df.event, weights=df.weight)
    return {"ages": ages, "reached": [round(float(v), 4) for v in point], "reached_lo": [round(float(v), 4) for v in lo],
            "reached_hi": [round(float(v), 4) for v in hi], "median_age": float(k.median_survival_time_), "ci_method": f"bootstrap, {n_boot} resamples"}


def weibull(df: pd.DataFrame) -> dict:
    cols = ["time", "event", "smoker_current", "bmi", "menarche_age", "pregnancies"]
    d = df[cols + ["weight"]].copy()
    train, test = train_test_split(d, test_size=0.2, random_state=SEED, stratify=d.event)
    w = WeibullAFTFitter(penalizer=0.01)
    w.fit(train, duration_col="time", event_col="event", weights_col="weight", robust=True)
    c_index = concordance_index(test.time, w.predict_median(test), test.event)
    params = w.params_
    lam = {k[1]: float(v) for k, v in params.items() if k[0] == "lambda_"}
    rho = float(np.exp(params[("rho_", "Intercept")]))
    summ = w.summary[["coef", "exp(coef)", "p"]]
    effects = {k[1]: {"time_ratio": round(float(r["exp(coef)"]), 4), "p": float(r["p"])} for k, r in summ.iterrows() if k[0] == "lambda_" and k[1] != "Intercept"}
    return {"lambda": lam, "rho": rho, "test_concordance": round(float(c_index), 3), "effects": effects,
            "note": "Weibull AFT: S(t)=exp(-(t/lambda)^rho), log(lambda)=Intercept+sum(beta*x). Time ratio >1 means later menopause."}


def classifier(df: pd.DataFrame) -> dict:
    feats = ["RIDAGEYR", "smoker_current", "bmi", "menarche_age", "pregnancies"]
    X, y = df[feats].values, df.event.values
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=SEED, stratify=y)
    cv = StratifiedKFold(5, shuffle=True, random_state=SEED)
    models = {
        "age_only_logistic": (make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)), [0]),
        "logistic_full": (make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)), list(range(len(feats)))),
        "gradient_boosting": (HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=300, random_state=SEED), list(range(len(feats)))),
    }
    results = {}
    for name, (m, cols) in models.items():
        cv_auc = cross_val_score(m, Xtr[:, cols], ytr, cv=cv, scoring="roc_auc")
        m.fit(Xtr[:, cols], ytr)
        p = m.predict_proba(Xte[:, cols])[:, 1]
        frac, mean_pred = calibration_curve(yte, p, n_bins=10, strategy="quantile")
        results[name] = {"cv_auc_mean": round(float(cv_auc.mean()), 4), "cv_auc_sd": round(float(cv_auc.std()), 4),
                         "test_auc": round(float(roc_auc_score(yte, p)), 4), "test_brier": round(float(brier_score_loss(yte, p)), 4),
                         "calibration": {"predicted": [round(float(v), 3) for v in mean_pred], "observed": [round(float(v), 3) for v in frac]}}
    # Export the transparent logistic model for the app (scaler + coefficients)
    lr = models["logistic_full"][0]
    sc, clf = lr.named_steps["standardscaler"], lr.named_steps["logisticregression"]
    export = {"features": feats, "mean": sc.mean_.round(6).tolist(), "scale": sc.scale_.round(6).tolist(),
              "coef": clf.coef_[0].round(6).tolist(), "intercept": round(float(clf.intercept_[0]), 6)}
    return {"n_train": int(len(ytr)), "n_test": int(len(yte)), "models": results, "export": export}


def generations(df: pd.DataFrame) -> dict:
    """Historical view: age at natural menopause across birth generations (Kaplan-Meier per decade + statsmodels logit)."""
    start_year = df.cycle.str[:4].astype(int) + 1
    df = df.assign(birth_year=start_year - df.RIDAGEYR)
    df["birth_decade"] = (df.birth_year // 10 * 10).astype(int)
    out = {}
    for dec in [1950, 1960, 1970]:
        g = df[df.birth_decade == dec]
        k = KaplanMeierFitter().fit(g.time, g.event, weights=g.weight)
        ages = list(range(40, 61))
        out[str(dec)] = {"n": int(len(g)), "events": int(g.event.sum()), "ages": ages,
                         "reached": [round(1 - float(v), 4) for v in k.survival_function_at_times(ages).values],
                         "median_age": None if np.isinf(k.median_survival_time_) else float(k.median_survival_time_)}
    # Among women aged 45-55 (the transition window), does birth year shift the odds of having reached menopause at a given age?
    w = df[df.RIDAGEYR.between(45, 55)]
    m = smf.logit("event ~ RIDAGEYR + birth_year", data=w).fit(disp=0)
    ci = m.conf_int().loc["birth_year"]
    out["test"] = {"framework": "statsmodels Logit", "window": "women aged 45-55", "n": int(len(w)),
                   "odds_ratio_per_birth_year": round(float(np.exp(m.params["birth_year"])), 4),
                   "ci95": [round(float(np.exp(ci[0])), 4), round(float(np.exp(ci[1])), 4)], "p": round(float(m.pvalues["birth_year"]), 4),
                   "note": "Within one survey period, age and birth year are almost collinear, so generational effects are weakly identifiable. Treat as descriptive."}
    return out


def main() -> None:
    REPORTS.mkdir(exist_ok=True)
    df, flow = build()
    print("Cohort flow:", json.dumps(flow, indent=2))
    curve, aft, clf, gen = km(df), weibull(df), classifier(df), generations(df)
    model = {
        "name": "FEMORA Muse menopause-timing model",
        "version": "1.0.0",
        "trained": date.today().isoformat(),
        "data": {"source": "CDC NHANES public-use files", "cycles": list(CYCLES.values()), "url": "https://wwwn.cdc.gov/nchs/nhanes/",
                 "licence": "Public domain (U.S. government work)", "cohort_flow": flow,
                 "definition": "Natural menopause = no period in past 12 months with reason 'menopause/change of life'. Surgical menopause, pregnancy and breastfeeding excluded."},
        "km": curve, "generations": gen, "weibull": aft, "classifier": clf["export"],
        "metrics": {k: {kk: vv for kk, vv in v.items() if kk != "calibration"} for k, v in clf["models"].items()} | {"weibull_test_concordance": aft["test_concordance"]},
        "limitations": [
            "Cross-sectional survey: age at last period is self-reported and subject to recall error.",
            "U.S. population (2013-2018); may not generalise to other countries.",
            "Population-level estimates. They cannot predict an individual's final menstrual period.",
            "Not clinically validated; for education only.",
        ],
        "frameworks": ["pandas", "numpy", "scikit-learn", "lifelines", "statsmodels"],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(model, indent=1))
    (REPORTS / "metrics.json").write_text(json.dumps({"cohort_flow": flow, "classifier": clf["models"], "weibull": {k: v for k, v in aft.items() if k != "lambda"}, "km_median_age": curve["median_age"], "generations_test": gen["test"]}, indent=2))
    print("KM median age at natural menopause:", curve["median_age"])
    print("Weibull test concordance:", aft["test_concordance"], "effects:", json.dumps(aft["effects"], indent=1))
    for k, v in clf["models"].items():
        print(f"{k:20s} CV AUC {v['cv_auc_mean']:.3f}±{v['cv_auc_sd']:.3f}  test AUC {v['test_auc']:.3f}  Brier {v['test_brier']:.3f}")
    print("Generations:", json.dumps({k: (v.get("n"), v.get("median_age")) if k != "test" else v for k, v in gen.items()}, indent=1))
    print("Wrote", OUT)


if __name__ == "__main__":
    main()
