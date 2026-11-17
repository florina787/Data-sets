"""Deterministic synthetic market generator for ENGINEERING TESTS ONLY.

Every row is labelled DataStatus.SYNTHETIC. Prices follow a regime-switching
factor model with fat tails, so pipelines, splits and evaluators can be
exercised at 1M+ rows. Nothing learned from this data says anything about real
markets. It deliberately injects defects (duplicates, gaps, bad ticks, a split,
delistings) so the quality and survivorship checks have something to catch.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from flowwealth.data.calendar import EXCHANGES

SECTORS = ["Technology", "Financials", "Energy", "Healthcare", "Industrials",
           "Consumer", "Materials", "Utilities", "Real Estate", "Communication"]


def generate_universe(n_tickers: int, start: str, end: str, seed: int = 7) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start, end)
    T = len(dates)
    exch_codes = list(EXCHANGES)

    # Market regime: 0 calm bull, 1 choppy, 2 stress. Sticky Markov chain.
    P = np.array([[0.985, 0.012, 0.003], [0.02, 0.97, 0.01], [0.03, 0.04, 0.93]])
    regime = np.zeros(T, dtype=int)
    for t in range(1, T):
        regime[t] = rng.choice(3, p=P[regime[t - 1]])
    mu = np.array([0.0006, 0.0, -0.0015])[regime]
    vol = np.array([0.008, 0.012, 0.028])[regime]
    market = mu + vol * rng.standard_t(4, T) / np.sqrt(2)
    sector_f = rng.normal(0, 0.006, (len(SECTORS), T)) * (vol / 0.01)
    # country factor: persistent (AR(1)) local drift + shocks, so country composites differ
    countries = sorted({EXCHANGES[e].country for e in exch_codes})
    c_idx = {c: k for k, c in enumerate(countries)}
    country_f = np.zeros((len(countries), T))
    for t in range(1, T):
        country_f[:, t] = 0.15 * country_f[:, t - 1] + rng.normal(0, 0.005, len(countries))

    master_rows, frames = [], []
    for i in range(n_tickers):
        tk = f"SYN{i:04d}"
        sector = int(rng.integers(len(SECTORS)))
        ex = exch_codes[i % len(exch_codes)]
        beta = rng.uniform(0.5, 1.6)
        idio = rng.uniform(0.008, 0.03)
        # staggered listings and ~8% delistings (survivorship bias test)
        list_idx = int(rng.integers(0, T // 4)) if rng.random() < 0.3 else 0
        delist_idx = int(rng.integers(T // 2, T - 5)) if rng.random() < 0.08 else T
        n = delist_idx - list_idx
        r = beta * market[list_idx:delist_idx] + sector_f[sector, list_idx:delist_idx] \
            + country_f[c_idx[EXCHANGES[exch_codes[i % len(exch_codes)]].country], list_idx:delist_idx] \
            + idio * rng.standard_t(5, n) / np.sqrt(5 / 3)
        # weak, noisy short-term momentum so models have *something* (small) to find
        r[1:] += 0.03 * r[:-1]
        if delist_idx < T:
            r[-20:] -= 0.02  # decline into delisting
        close = 20 * np.exp(rng.uniform(0, 3)) * np.exp(np.cumsum(r))
        spread = np.abs(rng.normal(0, idio / 2, n))
        open_ = close * np.exp(rng.normal(0, idio / 3, n))
        high = np.maximum(open_, close) * (1 + spread)
        low = np.minimum(open_, close) * (1 - spread)
        volume = np.round(rng.lognormal(13, 0.6, n) * (1 + 3 * np.abs(r) / idio))
        d = dates[list_idx:delist_idx]
        frames.append(pd.DataFrame({"ticker": tk, "exchange": ex, "date": d, "open": open_, "high": high,
                                    "low": low, "close": close, "adj_close": close, "volume": volume}))
        master_rows.append({"ticker": tk, "exchange": ex, "country": EXCHANGES[ex].country,
                            "sector": SECTORS[sector], "listed": d[0], "delisted": d[-1] if delist_idx < T else pd.NaT})
    bars = pd.concat(frames, ignore_index=True)

    # Inject a 2:1 split on one ticker: raw close halves, adj_close stays continuous.
    s = bars.ticker == "SYN0003"
    split_date = bars.loc[s, "date"].iloc[len(bars.loc[s]) // 2]
    m = s & (bars.date < split_date)
    bars.loc[m, ["open", "high", "low", "close"]] *= 2
    bars.loc[m, "volume"] = (bars.loc[m, "volume"] / 2).round()
    actions = pd.DataFrame([{"ticker": "SYN0003", "date": split_date, "action": "split", "ratio": 2.0}])

    # Defects for the quality checks.
    dup = bars.sample(50, random_state=seed)
    bad = bars.sample(20, random_state=seed + 1).index
    bars.loc[bad, ["open", "high", "low", "close", "adj_close"]] *= 25  # bad ticks (whole bar corrupted)
    gaps = bars.sample(200, random_state=seed + 2).index
    bars = pd.concat([bars.drop(gaps), dup], ignore_index=True)

    bars["source"] = "synthetic"
    bars["status"] = "SYNTHETIC"
    meta = {"regime": pd.Series(regime, index=dates), "injected": {
        "duplicates": 50, "bad_ticks": 20, "gaps": 200, "split": str(split_date.date())}}
    return bars, pd.DataFrame(master_rows), {**meta, "actions": actions}
