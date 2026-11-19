"""Research lake: quality-flagged, point-in-time daily bars built from the normalised Kaggle Parquet files.

* Sessions = the dates on which the benchmark ETF (SPY) traded in the primary dataset. No holiday table is guessed.
* Every bar gets ``available_at`` = 16:30 America/New_York on its trade date (close + 30 min), as UTC.
* Bars are never interpolated or filled. Defects are *flagged*; flagged bars are excluded from features.
* Two independent checks use the secondary dataset: daily-return agreement on overlapping ticker-dates, and split
  detection (raw vs split-adjusted prices) to confirm the primary series has no unadjusted split jumps.

Quality score (documented calculation, research window only):

    defects = duplicate rows + OHLC violations + non-positive prices + spike-reversal outliers + missing sessions
              + 0.25 * zero-volume bars
    score   = 100 * (1 - defects / (bars + missing sessions))
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import duckdb

from markets import catalog, config

RESEARCH_START = "2005-02-25"   # first SPY bar in the primary dataset
SPIKE = 0.405                   # |log return| > ln(1.5): a >50% move that reverses the next day is a bad tick


def _p(dataset_id: str, name: str) -> str:
    return (config.LAKE_DIR / dataset_id / name).as_posix()


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    for name, path in [("raw_bars", _p(catalog.PRIMARY, "bars.parquet")),
                       ("nyse_raw", _p(catalog.SECONDARY, "prices_raw.parquet")),
                       ("nyse_adj", _p(catalog.SECONDARY, "prices_split_adjusted.parquet")),
                       ("nyse_sec", _p(catalog.SECONDARY, "securities.parquet")),
                       ("headlines", _p(catalog.NEWS, "headlines.parquet")),
                       ("bars", _p("research", "bars.parquet")),
                       ("securities", _p("research", "securities.parquet")),
                       ("sessions", _p("research", "sessions.parquet"))]:
        if Path(path).exists():
            con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{path}')")
    return con


@dataclass
class BuildResult:
    quality: dict
    validation: dict
    counts: dict


def build() -> BuildResult:
    for d in (catalog.PRIMARY, catalog.SECONDARY):
        catalog.assert_real(catalog.CATALOG[d])
    out = config.LAKE_DIR / "research"
    out.mkdir(parents=True, exist_ok=True)
    con = connect()
    lag = config.EOD_PUBLICATION_LAG_MIN
    con.execute(f"""COPY (SELECT DISTINCT date FROM raw_bars WHERE ticker = '{config.BENCHMARK}' AND date >= DATE '{RESEARCH_START}'
                 ORDER BY date) TO '{out / "sessions.parquet"}' (FORMAT PARQUET)""")
    con.execute(f"CREATE OR REPLACE VIEW sessions AS SELECT * FROM read_parquet('{out / 'sessions.parquet'}')")

    # Duplicate (ticker, date) rows: keep the first, count the rest.
    con.execute("""CREATE TEMP TABLE b AS
        SELECT *, row_number() OVER (PARTITION BY ticker, date ORDER BY open, high, low, adj_close, volume) AS dup_rank
        FROM raw_bars WHERE date >= DATE '2004-01-01'""")
    dup = con.execute("SELECT count(*) FROM b WHERE dup_rank > 1").fetchone()[0]
    con.execute(f"""CREATE TEMP TABLE c AS
        WITH x AS (
          SELECT * EXCLUDE (dup_rank), ln(adj_close / lag(adj_close) OVER w) AS lr
          FROM b WHERE dup_rank = 1 WINDOW w AS (PARTITION BY ticker ORDER BY date))
        SELECT *,
          CASE
            WHEN least(open, high, low, adj_close) <= 0 THEN 'non_positive'
            WHEN high < greatest(open, adj_close) * (1 - 1e-6) OR low > least(open, adj_close) * (1 + 1e-6) THEN 'ohlc_violation'
            WHEN abs(lr) > {SPIKE} AND abs(lead(lr) OVER w) > {SPIKE} AND sign(lr) <> sign(lead(lr) OVER w) THEN 'spike_reversal'
            WHEN volume = 0 THEN 'zero_volume'
            ELSE 'ok' END AS quality_flag
        FROM x WINDOW w AS (PARTITION BY ticker ORDER BY date)""")
    # Corporate actions the secondary dataset adjusts (splits, spin-offs) but the primary shows as a >=20% one-day move:
    # the bar is flagged so no feature or label is computed across it (e.g. spin-offs recorded as price "losses").
    con.execute("""CREATE TEMP TABLE ca_unadjusted AS
        WITH r AS (SELECT r.ticker, r.date, r.close / a.close AS k FROM nyse_raw r JOIN nyse_adj a USING (ticker, date) WHERE a.close > 0),
             s AS (SELECT ticker, date, k / lag(k) OVER (PARTITION BY ticker ORDER BY date) AS step FROM r),
             p AS (SELECT ticker, date, adj_close / lag(adj_close) OVER (PARTITION BY ticker ORDER BY date) - 1 AS r FROM c)
        SELECT s.ticker, s.date, s.step, p.r FROM s JOIN p USING (ticker, date) WHERE (s.step < 0.9 OR s.step > 1.1) AND abs(p.r) >= 0.2""")
    con.execute(f"""COPY (
        SELECT ticker, asset_type, date,
               timezone('UTC', (date + INTERVAL '{config.CLOSE_HOUR} hours' + INTERVAL '{lag} minutes')::TIMESTAMP AT TIME ZONE '{config.EXCHANGE_TZ}')
                 AS available_at,
               open, high, low, adj_close, volume,
               CASE WHEN (ticker, date) IN (SELECT (ticker, date) FROM ca_unadjusted) THEN 'unadjusted_corporate_action'
                    ELSE quality_flag END AS quality_flag, dataset_id
        FROM c ORDER BY ticker, date) TO '{out / "bars.parquet"}' (FORMAT PARQUET, COMPRESSION ZSTD)""")
    con.execute(f"CREATE OR REPLACE VIEW bars AS SELECT * FROM read_parquet('{out / 'bars.parquet'}')")

    # Securities master (survivorship facts recorded per ticker; sector/name from the S&P 500 file where available).
    con.execute(f"""COPY (
        SELECT b.ticker, any_value(b.asset_type) AS asset_type, min(b.date) AS first_date, max(b.date) AS last_date, count(*) AS bars,
               any_value(s.name) AS name, any_value(s.sector) AS sector, any_value(s.sub_industry) AS sub_industry,
               any_value(s.headquarters) AS headquarters
        FROM bars b LEFT JOIN nyse_sec s ON s.ticker = b.ticker GROUP BY b.ticker ORDER BY b.ticker
    ) TO '{out / "securities.parquet"}' (FORMAT PARQUET)""")
    con.execute(f"CREATE OR REPLACE VIEW securities AS SELECT * FROM read_parquet('{out / 'securities.parquet'}')")

    quality = _quality(con, dup)
    validation = _validate(con)
    counts = con.execute(f"""SELECT count(*) FILTER (WHERE date >= DATE '{RESEARCH_START}'),
        count(*) FILTER (WHERE date >= DATE '{RESEARCH_START}' AND asset_type = 'stock' AND quality_flag = 'ok'),
        count(DISTINCT ticker) FILTER (WHERE date >= DATE '{RESEARCH_START}'), (SELECT count(*) FROM sessions)
        FROM bars""").fetchone()
    res = BuildResult(quality, validation, {"research_window_bars": counts[0], "research_window_clean_stock_bars": counts[1],
                                            "research_window_tickers": counts[2], "sessions": counts[3],
                                            "research_window": [RESEARCH_START, "2017-11-10"]})
    (out / "lake_report.json").write_text(json.dumps(res.__dict__, indent=2, default=str))
    (config.MANIFEST_DIR / "research_lake.json").write_text(json.dumps(res.__dict__, indent=2, default=str))
    return res


def _quality(con, dup: int) -> dict:
    w = f"date >= DATE '{RESEARCH_START}'"
    flags = dict(con.execute(f"SELECT quality_flag, count(*) FROM bars WHERE {w} GROUP BY 1").fetchall())
    n = sum(flags.values())
    missing = con.execute(f"""WITH span AS (SELECT ticker, min(date) a, max(date) z, count(*) n FROM bars WHERE {w} GROUP BY ticker)
        SELECT sum((SELECT count(*) FROM sessions s WHERE s.date BETWEEN span.a AND span.z) - n) FROM span""").fetchone()[0] or 0
    defects = dup + flags.get("unadjusted_corporate_action", 0) + flags.get("ohlc_violation", 0) + flags.get("non_positive", 0) + flags.get("spike_reversal", 0) + missing \
        + 0.25 * flags.get("zero_volume", 0)
    return {"window_start": RESEARCH_START, "bars": n, "duplicate_rows_removed": dup, "flags": flags, "missing_sessions": int(missing),
            "score": round(100 * (1 - defects / (n + missing)), 3),
            "score_formula": "100*(1-(dup+unadjusted_ca+ohlc+non_positive+spike_reversal+missing+0.25*zero_volume)/(bars+missing))"}


def _validate(con) -> dict:
    # 1) Daily-return agreement with the independent NYSE dataset (split-adjusted only, so ex-dividend days differ slightly).
    agree = con.execute("""
        WITH a AS (SELECT ticker, date, adj_close / lag(adj_close) OVER (PARTITION BY ticker ORDER BY date) - 1 AS r FROM bars),
             n AS (SELECT ticker, date, close / lag(close) OVER (PARTITION BY ticker ORDER BY date) - 1 AS r FROM nyse_adj)
        SELECT count(*), avg(CASE WHEN abs(a.r - n.r) < 0.001 THEN 1 ELSE 0 END), avg(CASE WHEN abs(a.r - n.r) < 0.01 THEN 1 ELSE 0 END),
               quantile_cont(abs(a.r - n.r), 0.5), count(DISTINCT a.ticker)
        FROM a JOIN n USING (ticker, date) WHERE a.r IS NOT NULL AND n.r IS NOT NULL""").fetchone()
    # 2) Splits: the raw/adjusted ratio in the NYSE file steps on a split date. The primary (adjusted) series must not jump there.
    splits = con.execute("""
        WITH r AS (SELECT r.ticker, r.date, r.close / a.close AS k FROM nyse_raw r JOIN nyse_adj a USING (ticker, date) WHERE a.close > 0),
             s AS (SELECT ticker, date, k / lag(k) OVER (PARTITION BY ticker ORDER BY date) AS step FROM r),
             ev AS (SELECT ticker, date, step FROM s WHERE step < 0.9 OR step > 1.1),
             p AS (SELECT ticker, date, adj_close / lag(adj_close) OVER (PARTITION BY ticker ORDER BY date) - 1 AS r FROM bars),
             raw AS (SELECT ticker, date, close / lag(close) OVER (PARTITION BY ticker ORDER BY date) - 1 AS r FROM nyse_raw)
        SELECT count(*), count(p.r), count(*) FILTER (WHERE abs(p.r) < 0.2), count(*) FILTER (WHERE abs(raw.r) >= 0.2)
        FROM ev LEFT JOIN p USING (ticker, date) LEFT JOIN raw USING (ticker, date)""").fetchone()
    # 3) Survivorship evidence: S&P 500 (2016) members with no series at all in the primary dataset.
    missing = con.execute("""SELECT list(ticker ORDER BY ticker), count(*) FROM (SELECT DISTINCT ticker FROM nyse_raw)
        WHERE ticker NOT IN (SELECT DISTINCT ticker FROM bars)""").fetchone()
    ca = con.execute("SELECT list(ticker || ' ' || CAST(date AS VARCHAR) ORDER BY ticker) FROM ca_unadjusted").fetchone()[0]
    return {"survivorship": {"sp500_2016_members_absent_from_primary": missing[1], "examples": missing[0][:25],
                             "note": "members acquired or delisted before Nov 2017 (e.g. WFM, RAI) have no history at all"},
            "unadjusted_corporate_actions_flagged": ca,
            "cross_source_daily_returns": {"overlapping_ticker_days": agree[0], "tickers": agree[4],
                                           "share_within_0.1pct": round(agree[1], 4), "share_within_1pct": round(agree[2], 4),
                                           "median_abs_diff": agree[3],
                                           "note": "secondary is split-adjusted only; differences concentrate on ex-dividend dates"},
            "splits": {"detected_in_secondary": splits[0], "matched_in_primary": splits[1],
                       "primary_smooth_on_split_day": splits[2], "raw_jump_on_split_day": splits[3],
                       "note": "a smooth primary return on a day the raw price jumped confirms the primary series is split-adjusted"}}


if __name__ == "__main__":
    r = build()
    print(json.dumps(r.__dict__, indent=2, default=str))
