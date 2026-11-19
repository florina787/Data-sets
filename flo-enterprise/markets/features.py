"""Leakage-safe features and horizon labels, computed in DuckDB window functions.

Point-in-time rules (enforced by construction and tested in tests/unit/test_markets_pit.py):

* every feature window is ``ROWS BETWEEN n PRECEDING AND CURRENT ROW``; nothing looks forward;
* the research universe on date t uses only data up to t (top-N stocks by trailing 20-day median dollar volume,
  at least 252 prior bars), so names enter and leave the universe without hindsight;
* cross-sectional ranks are taken per availability cohort (``available_at``) and only among in-universe names;
* flagged bars (bad ticks, OHLC violations, unadjusted corporate actions) contribute no prices to features, and a label
  is NULL if any flagged bar or a missing session falls inside its horizon (no silent interpolation);
* labels use LEAD only and record ``label_end_h`` (availability of the outcome) for purging.

Targets for horizon h sessions:
  fwd_ret_h   log(adj_close[t+h] / adj_close[t])                       (adjusted: total return incl. dividends)
  fwd_bm_h    fwd_ret_h - SPY log return over the same sessions          (benchmark-relative)
  fwd_xs_h    fwd_ret_h - mean over in-universe names in the cohort      (cross-sectional, market-neutral)
"""
from __future__ import annotations

import time

from markets import config
from markets.lake import RESEARCH_START, connect

HORIZONS = (1, 5, 20)
UNIVERSE_SIZE = 1000
MIN_HISTORY = 252

FEATURES: dict[str, str] = {
    "ret_1": "1-session log return",
    "ret_5": "5-session log return (short-term reversal)",
    "ret_20": "20-session log return",
    "mom_12_1": "log return from t-252 to t-21 (12-1 momentum)",
    "vol_20": "20-session realised volatility of log returns",
    "vol_ratio": "vol_20 / vol_60 (volatility expansion)",
    "dist_ma50": "log distance from 50-session mean price",
    "dist_ma200": "log distance from 200-session mean price",
    "dd_252": "drawdown from the 252-session high",
    "volu_z20": "log-volume z-score vs the previous 20 sessions",
    "log_adv20": "log 20-session median dollar volume (liquidity)",
}


def _sql(where_extra: str = "") -> str:
    h_cols = []
    for h in HORIZONS:
        h_cols.append(f"""
          CASE WHEN lead(sidx, {h}) OVER w - sidx = {h} AND lead(nbad, {h}) OVER w = nbad
               THEN ln(lead(px, {h}) OVER w / px) END AS fwd_ret_{h},
          lead(available_at, {h}) OVER w AS label_end_{h},
          lead(spy_cum, {h}) OVER w - spy_cum AS spy_fwd_{h}""")
    fwd = ",".join(h_cols)
    rk = ",\n".join(f"CASE WHEN in_universe AND {f} IS NOT NULL THEN percent_rank() OVER (PARTITION BY available_at, in_universe, {f} IS NULL ORDER BY {f}) - 0.5 END AS {f}_rk"
                    for f in FEATURES)
    xs = ",\n".join(f"fwd_ret_{h} - spy_fwd_{h} AS fwd_bm_{h}, "
                    f"fwd_ret_{h} - avg(CASE WHEN in_universe THEN fwd_ret_{h} END) OVER (PARTITION BY available_at) AS fwd_xs_{h}"
                    for h in HORIZONS)
    return f"""
    WITH s AS (SELECT date, row_number() OVER (ORDER BY date) AS sidx FROM sessions),
    spy AS (SELECT date, sum(ln(adj_close / lag_c)) OVER (ORDER BY date) AS spy_cum FROM
              (SELECT date, adj_close, lag(adj_close) OVER (ORDER BY date) lag_c FROM bars WHERE ticker = 'SPY')),
    b AS (
      SELECT b.ticker, b.date, b.available_at, b.volume, s.sidx, coalesce(spy.spy_cum, 0) AS spy_cum,
             CASE WHEN b.quality_flag IN ('ok', 'zero_volume') THEN b.adj_close END AS px,
             CASE WHEN b.quality_flag IN ('ok', 'zero_volume') THEN b.adj_close * b.volume END AS dvol,
             sum(CASE WHEN b.quality_flag IN ('ok', 'zero_volume') THEN 0 ELSE 1 END) OVER (PARTITION BY b.ticker ORDER BY b.date) AS nbad,
             row_number() OVER (PARTITION BY b.ticker ORDER BY b.date) AS nhist
      FROM bars b JOIN s USING (date) LEFT JOIN spy USING (date)
      WHERE b.asset_type = 'stock' {where_extra}),
    r AS (SELECT *, ln(px / lag(px) OVER w) AS lr FROM b WINDOW w AS (PARTITION BY ticker ORDER BY date)),
    f AS (
      SELECT ticker, date, available_at, sidx, nhist, px, nbad, spy_cum,
        lr AS ret_1,
        ln(px / lag(px, 5) OVER w) AS ret_5,
        ln(px / lag(px, 20) OVER w) AS ret_20,
        ln(lag(px, 21) OVER w / lag(px, 252) OVER w) AS mom_12_1,
        stddev_samp(lr) OVER (w ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS vol_20,
        stddev_samp(lr) OVER (w ROWS BETWEEN 19 PRECEDING AND CURRENT ROW)
          / nullif(stddev_samp(lr) OVER (w ROWS BETWEEN 59 PRECEDING AND CURRENT ROW), 0) AS vol_ratio,
        ln(px / avg(px) OVER (w ROWS BETWEEN 49 PRECEDING AND CURRENT ROW)) AS dist_ma50,
        ln(px / avg(px) OVER (w ROWS BETWEEN 199 PRECEDING AND CURRENT ROW)) AS dist_ma200,
        px / max(px) OVER (w ROWS BETWEEN 251 PRECEDING AND CURRENT ROW) - 1 AS dd_252,
        (ln(1 + volume) - avg(ln(1 + volume)) OVER (w ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING))
          / nullif(stddev_samp(ln(1 + volume)) OVER (w ROWS BETWEEN 20 PRECEDING AND 1 PRECEDING), 0) AS volu_z20,
        median(dvol) OVER (w ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS adv20,
        {fwd}
      FROM r WINDOW w AS (PARTITION BY ticker ORDER BY date)),
    u AS (
      SELECT *, ln(1 + adv20) AS log_adv20,
        (nhist > {MIN_HISTORY} AND px IS NOT NULL AND adv20 > 0
         AND row_number() OVER (PARTITION BY available_at ORDER BY CASE WHEN nhist > {MIN_HISTORY} AND px IS NOT NULL THEN adv20 END DESC NULLS LAST)
             <= {UNIVERSE_SIZE}) AS in_universe
      FROM f)
    SELECT ticker, date, available_at, in_universe, adv20 AS adv_usd, px AS adj_close,
           {", ".join(FEATURES)},
           {rk},
           {", ".join(f"fwd_ret_{h}, label_end_{h}, spy_fwd_{h}" for h in HORIZONS)},
           {xs}
    FROM u WHERE date >= DATE '{RESEARCH_START}' + INTERVAL 365 DAY
    """


def build(out_name: str = "features.parquet") -> dict:
    t0 = time.perf_counter()
    con = connect()
    out = config.LAKE_DIR / "research" / out_name
    con.execute(f"COPY ({_sql()} ORDER BY date, ticker) TO '{out}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    s = con.execute(f"""SELECT count(*), count(*) FILTER (WHERE in_universe), count(DISTINCT ticker) FILTER (WHERE in_universe),
        CAST(min(date) AS VARCHAR), CAST(max(date) AS VARCHAR) FROM read_parquet('{out}')""").fetchone()
    return {"rows": s[0], "universe_rows": s[1], "universe_tickers_ever": s[2], "start": s[3], "end": s[4],
            "seconds": round(time.perf_counter() - t0, 1), "path": str(out)}


def compute(where_extra: str = ""):
    """Return the feature frame (used by tests to recompute on truncated history)."""
    return connect().execute(_sql(where_extra)).df()


if __name__ == "__main__":
    import json
    print(json.dumps(build(), indent=2))
