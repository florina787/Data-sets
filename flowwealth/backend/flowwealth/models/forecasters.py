"""Forecasters share one interface so baselines and ML models are compared like-for-like."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


class Forecaster:
    name: str = "base"
    version: str = "0"

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "Forecaster":
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        raise NotImplementedError

    def params(self) -> dict:
        return {}


@dataclass
class ZeroBaseline(Forecaster):
    """Predicts no excess return. Any model must beat this after costs."""
    name: str = "zero"
    version: str = "1"

    def predict(self, X):
        return np.zeros(len(X))


@dataclass
class MomentumBaseline(Forecaster):
    """Ranks by a single momentum feature -- the classic simple benchmark."""
    feature: str = "ret_60_skip5_rk"
    name: str = "momentum"
    version: str = "1"

    def predict(self, X):
        return X[self.feature].fillna(0).to_numpy()


@dataclass
class ShortReversalBaseline(Forecaster):
    feature: str = "ret_5_rk"
    name: str = "reversal_5d"
    version: str = "1"

    def predict(self, X):
        return -X[self.feature].fillna(0).to_numpy()


@dataclass
class RidgeForecaster(Forecaster):
    alpha: float = 10.0
    name: str = "ridge"
    version: str = "1"
    _m: object = field(default=None, repr=False)

    def fit(self, X, y):
        from sklearn.linear_model import Ridge
        self._m = Ridge(alpha=self.alpha).fit(X.fillna(0), y)
        return self

    def predict(self, X):
        return self._m.predict(X.fillna(0))

    def params(self):
        return {"alpha": self.alpha}


@dataclass
class LightGBMForecaster(Forecaster):
    n_estimators: int = 300
    learning_rate: float = 0.03
    num_leaves: int = 15
    min_child_samples: int = 2000  # heavy regularisation: financial targets are noisy
    subsample: float = 0.5
    seed: int = 0
    name: str = "lightgbm"
    version: str = "1"
    _m: object = field(default=None, repr=False)

    def fit(self, X, y):
        import lightgbm as lgb
        self._m = lgb.LGBMRegressor(n_estimators=self.n_estimators, learning_rate=self.learning_rate,
                                    num_leaves=self.num_leaves, min_child_samples=self.min_child_samples,
                                    subsample=self.subsample, subsample_freq=1, colsample_bytree=0.8,
                                    random_state=self.seed, n_jobs=4, verbose=-1).fit(X, y)
        return self

    def predict(self, X):
        return self._m.predict(X)

    def feature_importance(self) -> dict:
        return dict(zip(self._m.feature_name_, map(int, self._m.feature_importances_)))

    def params(self):
        return {k: getattr(self, k) for k in ("n_estimators", "learning_rate", "num_leaves", "min_child_samples", "subsample", "seed")}
