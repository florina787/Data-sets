"""Point-in-time data lake: partitioned Parquet + DuckDB.

Layout::

    lake/
      bars/version=<v>/year=<yyyy>/*.parquet
      securities/version=<v>/securities.parquet   # includes delisted names
      manifests/<v>.json                          # row counts, hashes, quality, lineage

Every bar has ``ts`` (session close, UTC) and ``available_at`` (first moment the
bar could have been known). ``as_of`` queries filter on ``available_at`` and on
the securities master's listing window, which is what prevents look-ahead and
survivorship bias at query time.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import warnings

import duckdb
import pandas as pd

from flowwealth.contracts import utcnow
from flowwealth.data.calendar import available_at_utc, close_timestamps_utc

# DuckDB's pandas bridge triggers a pandas-3 deprecation internally; harmless.
warnings.filterwarnings("ignore", message="The inplace keyword")


def attach_timestamps(bars: pd.DataFrame) -> pd.DataFrame:
    out = []
    for ex, g in bars.groupby("exchange", sort=False):
        g = g.copy()
        g["ts"] = close_timestamps_utc(g["date"], ex).to_numpy()
        g["available_at"] = available_at_utc(pd.Series(g["ts"].to_numpy()), ex).to_numpy()
        out.append(g)
    df = pd.concat(out)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df["available_at"] = pd.to_datetime(df["available_at"], utc=True)
    return df.sort_values(["ticker", "ts"]).reset_index(drop=True)


def _frame_hash(df: pd.DataFrame) -> str:
    return hashlib.sha256(pd.util.hash_pandas_object(df, index=False).values.tobytes()).hexdigest()


@dataclass
class DataLake:
    root: Path

    def __post_init__(self):
        self.root = Path(self.root)

    def write_version(self, version: str, bars: pd.DataFrame, securities: pd.DataFrame,
                      quality: dict, lineage: dict) -> dict:
        bdir = self.root / "bars" / f"version={version}"
        if bdir.exists():
            raise FileExistsError(f"dataset version {version} already exists; versions are immutable")
        bars = bars.assign(year=bars["ts"].dt.year, dataset_version=version, ingested_at=utcnow())
        bdir.parent.mkdir(parents=True, exist_ok=True)
        con = duckdb.connect()
        con.register("b", bars)
        con.execute(f"COPY b TO '{bdir}' (FORMAT PARQUET, PARTITION_BY (year), COMPRESSION ZSTD)")
        sdir = self.root / "securities" / f"version={version}"
        sdir.mkdir(parents=True)
        securities.to_parquet(sdir / "securities.parquet", index=False)
        manifest = {
            "version": version, "created_at": utcnow().isoformat(), "rows": int(len(bars)),
            "tickers": int(bars.ticker.nunique()), "start": str(bars.ts.min()), "end": str(bars.ts.max()),
            "status_counts": bars["status"].value_counts().to_dict(),
            "content_sha256": _frame_hash(bars.drop(columns=["ingested_at"])),
            "quality": quality, "lineage": lineage,
        }
        mdir = self.root / "manifests"
        mdir.mkdir(parents=True, exist_ok=True)
        (mdir / f"{version}.json").write_text(json.dumps(manifest, indent=2, default=str))
        return manifest

    def manifest(self, version: str) -> dict:
        return json.loads((self.root / "manifests" / f"{version}.json").read_text())

    def connect(self, version: str) -> duckdb.DuckDBPyConnection:
        con = duckdb.connect()
        con.execute(f"CREATE VIEW bars AS SELECT * FROM read_parquet('{self.root}/bars/version={version}/*/*.parquet', hive_partitioning=true)")
        con.execute(f"CREATE VIEW securities AS SELECT * FROM read_parquet('{self.root}/securities/version={version}/securities.parquet')")
        return con

    def universe_as_of(self, version: str, as_of: datetime) -> list[str]:
        """Tickers listed at ``as_of`` -- including ones that later delisted."""
        con = self.connect(version)
        q = """SELECT ticker FROM securities WHERE listed <= ?::TIMESTAMP
               AND (delisted IS NULL OR delisted >= ?::TIMESTAMP) ORDER BY ticker"""
        naive = pd.Timestamp(as_of).tz_convert("UTC").tz_localize(None) if pd.Timestamp(as_of).tzinfo else pd.Timestamp(as_of)
        return [r[0] for r in con.execute(q, [naive, naive]).fetchall()]

    def bars_as_of(self, version: str, as_of: datetime, tickers: list[str] | None = None,
                   lookback_days: int | None = None) -> pd.DataFrame:
        """Only bars whose ``available_at`` <= as_of. Never returns future data."""
        con = self.connect(version)
        where = ["available_at <= ?"]
        params: list = [pd.Timestamp(as_of)]
        if tickers:
            where.append("ticker IN (SELECT unnest(?))")
            params.append(tickers)
        if lookback_days:
            where.append("ts >= ?")
            params.append(pd.Timestamp(as_of) - pd.Timedelta(days=lookback_days))
        return con.execute(f"SELECT * FROM bars WHERE {' AND '.join(where)} ORDER BY ticker, ts", params).fetchdf()
