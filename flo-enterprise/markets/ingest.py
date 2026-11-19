"""Acquire Kaggle datasets, verify integrity, and normalise them into the research lake.

Steps per dataset: download with KaggleHub (public, anonymous; no credentials are stored or required) -> SHA-256 every
file -> drop byte-identical duplicates -> normalise with DuckDB's CSV reader (data is parsed, never executed) ->
Parquet under ``var/markets/lake/<dataset_id>/`` -> manifest with licence, coverage, counts and checksums.

Raw downloads are left untouched in the KaggleHub cache; a later run re-hashes them and refuses to proceed if any file
changed (``IntegrityError``).
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from markets import catalog, config


class IntegrityError(RuntimeError):
    pass


def download(record: catalog.DatasetRecord) -> Path:
    os.environ.setdefault("KAGGLEHUB_CACHE", str(config.KAGGLE_CACHE))
    import kagglehub  # imported late so the cache location above applies

    return Path(kagglehub.dataset_download(f"{record.kaggle_ref}/versions/{record.kaggle_version}"))


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


@dataclass
class Inventory:
    root: Path
    files: dict[str, str]          # canonical relative path -> sha256
    sizes: dict[str, int]
    duplicates: dict[str, str]     # duplicate relative path -> canonical relative path
    empty: list[str]

    @property
    def digest(self) -> str:
        """Content digest of the canonical file set: sha256 over sorted 'path sha256' lines."""
        lines = "\n".join(f"{p} {h}" for p, h in sorted(self.files.items()))
        return hashlib.sha256(lines.encode()).hexdigest()


def inventory(root: Path) -> Inventory:
    """Hash every file; byte-identical copies are recorded as duplicates of the shortest path."""
    by_hash: dict[str, list[str]] = {}
    sizes: dict[str, int] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            sizes[rel] = p.stat().st_size
            by_hash.setdefault(sha256_file(p), []).append(rel)
    files, dups, empty = {}, {}, []
    for h, paths in by_hash.items():
        paths.sort(key=lambda s: (s.count("/"), s))
        canon = paths[0]
        if sizes[canon] == 0:
            empty.extend(paths)
            continue
        files[canon] = h
        for d in paths[1:]:
            dups[d] = canon
    return Inventory(root, files, {k: v for k, v in sizes.items() if k in files}, dups, sorted(empty))


def verify(inv: Inventory, expected: dict[str, str]) -> None:
    changed = [p for p, h in expected.items() if inv.files.get(p) != h]
    if changed:
        raise IntegrityError(f"{len(changed)} files changed since the manifest was written, e.g. {changed[:3]}")


def _ticker(stem: str) -> str:
    # 'aapl.us' -> 'AAPL'; share classes 'brk-b.us' / 'abr_a.us' -> 'BRK-B' / 'ABR_A' (kept distinct, never merged)
    return stem.split(".")[0].upper()


def normalise_primary(inv: Inventory, out_dir: Path) -> dict:
    """borismarjanovic: one CSV per ticker under Stocks/ and ETFs/ -> bars.parquet (canonical files only)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    rows = []
    for rel in inv.files:
        top = rel.split("/")[0]
        if top in ("Stocks", "ETFs") and rel.endswith(".txt"):
            rows.append((str(inv.root / rel), _ticker(Path(rel).name.removesuffix(".txt")), "etf" if top == "ETFs" else "stock"))
    con.execute("CREATE TABLE files(path VARCHAR, ticker VARCHAR, asset_type VARCHAR)")
    con.executemany("INSERT INTO files VALUES (?, ?, ?)", rows)
    collisions = con.execute("SELECT ticker, count(*) FROM files GROUP BY ticker HAVING count(*) > 1").fetchall()
    if collisions:
        raise IntegrityError(f"ticker collisions after normalisation: {collisions[:5]}")
    paths = [r[0] for r in rows]
    con.execute("CREATE TEMP TABLE raw AS SELECT * FROM read_csv(?, filename=true, header=true, "
                "columns={'Date': 'DATE', 'Open': 'DOUBLE', 'High': 'DOUBLE', 'Low': 'DOUBLE', 'Close': 'DOUBLE', "
                "'Volume': 'BIGINT', 'OpenInt': 'BIGINT'})", [paths])
    con.execute(f"""COPY (
        SELECT f.ticker, f.asset_type, r.Date AS date, r.Open AS open, r.High AS high, r.Low AS low, r.Close AS adj_close,
               r.Volume AS volume, '{catalog.PRIMARY}' AS dataset_id
        FROM raw r JOIN files f ON r.filename = f.path ORDER BY ticker, date
    ) TO '{out_dir / "bars.parquet"}' (FORMAT PARQUET, COMPRESSION ZSTD)""")
    stats = con.execute(f"""SELECT count(*), count(DISTINCT ticker), min(date), max(date),
        count(*) FILTER (WHERE asset_type = 'stock'), count(*) FILTER (WHERE asset_type = 'etf')
        FROM read_parquet('{out_dir / "bars.parquet"}')""").fetchone()
    return {"rows": stats[0], "tickers": stats[1], "start": str(stats[2]), "end": str(stats[3]),
            "stock_rows": stats[4], "etf_rows": stats[5]}


def normalise_secondary(inv: Inventory, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    r = inv.root
    con.execute(f"""COPY (SELECT symbol AS ticker, CAST(date AS DATE) AS date, open, high, low, close, volume
                    FROM read_csv('{r / "prices.csv"}', header=true)) TO '{out_dir / "prices_raw.parquet"}' (FORMAT PARQUET)""")
    con.execute(f"""COPY (SELECT symbol AS ticker, CAST(date AS DATE) AS date, open, high, low, close, volume
                    FROM read_csv('{r / "prices-split-adjusted.csv"}', header=true)) TO '{out_dir / "prices_split_adjusted.parquet"}' (FORMAT PARQUET)""")
    con.execute(f"""COPY (SELECT "Ticker symbol" AS ticker, "Security" AS name, "GICS Sector" AS sector, "GICS Sub Industry" AS sub_industry,
                    "Address of Headquarters" AS headquarters, "Date first added" AS date_first_added, CAST("CIK" AS VARCHAR) AS cik
                    FROM read_csv('{r / "securities.csv"}', header=true, all_varchar=true)) TO '{out_dir / "securities.parquet"}' (FORMAT PARQUET)""")
    con.execute(f"""COPY (SELECT * FROM read_csv('{r / "fundamentals.csv"}', header=true)) TO '{out_dir / "fundamentals.parquet"}' (FORMAT PARQUET)""")
    s = con.execute(f"SELECT count(*), count(DISTINCT ticker), min(date), max(date) FROM read_parquet('{out_dir / 'prices_raw.parquet'}')").fetchone()
    n_sec = con.execute(f"SELECT count(*) FROM read_parquet('{out_dir / 'securities.parquet'}')").fetchone()[0]
    return {"rows": s[0], "tickers": s[1], "start": str(s[2]), "end": str(s[3]), "securities": n_sec}


def normalise_news(inv: Inventory, out_dir: Path) -> dict:
    """Analyst-ratings headlines with second-level publication times (UTC). Date-only partner headlines are counted, not used."""
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    r = inv.root
    # Point-in-time availability: a headline with a real time of day is usable from that instant; a date-only headline
    # (raw time 00:00:00) may have appeared after the close, so it becomes usable at 00:00 New York the next day.
    con.execute("SET TimeZone = 'UTC'")
    con.execute(f"""COPY (
        SELECT source_row, headline, url, publisher, published_at, ticker, time_precision,
               CASE WHEN time_precision = 'second' THEN published_at
                    ELSE timezone('UTC', (CAST(published_at AS DATE) + INTERVAL 1 DAY)::TIMESTAMP AT TIME ZONE 'America/New_York') END AS available_at
        FROM (SELECT CAST(column0 AS BIGINT) AS source_row, headline, url, publisher,
                     CAST(date AS TIMESTAMPTZ) AS published_at, upper(stock) AS ticker,
                     CASE WHEN substr(date, 12, 8) NOT IN ('', '00:00:00') THEN 'second' ELSE 'date_only' END AS time_precision
              FROM read_csv('{r / "raw_analyst_ratings.csv"}', header=true, all_varchar=true)
              WHERE date IS NOT NULL AND stock IS NOT NULL AND headline IS NOT NULL)
    ) TO '{out_dir / "headlines.parquet"}' (FORMAT PARQUET, COMPRESSION ZSTD)""")
    s = con.execute(f"""SELECT count(*), count(DISTINCT ticker), CAST(min(published_at) AS VARCHAR), CAST(max(published_at) AS VARCHAR),
        count(*) - count(DISTINCT (ticker, headline, published_at)), count(*) FILTER (WHERE time_precision = 'date_only')
        FROM read_parquet('{out_dir / "headlines.parquet"}')""").fetchone()
    partner = con.execute(f"SELECT count(*) FROM read_csv('{r / 'raw_partner_headlines.csv'}', header=true, all_varchar=true)").fetchone()[0]
    return {"rows": s[0], "tickers": s[1], "start": str(s[2]), "end": str(s[3]), "duplicate_rows": s[4], "date_only_rows": s[5],
            "excluded_partner_headlines_date_only": partner}


NORMALISERS = {catalog.PRIMARY: normalise_primary, catalog.SECONDARY: normalise_secondary, catalog.NEWS: normalise_news}


def ingest(dataset_id: str, root: Path | None = None) -> dict:
    rec = catalog.CATALOG[dataset_id]
    catalog.assert_real(rec)
    t0 = time.perf_counter()
    root = root or download(rec)
    inv = inventory(root)
    checksum_file = config.MANIFEST_DIR / f"{dataset_id}.sha256"
    if checksum_file.exists():  # re-run: raw files must be exactly what the committed manifest recorded
        expected = dict(line.split("  ", 1)[::-1] for line in checksum_file.read_text().splitlines() if line)
        verify(inv, expected)
    out = config.LAKE_DIR / dataset_id
    counts = NORMALISERS[dataset_id](inv, out)
    manifest = {
        "dataset": rec.as_dict(),
        "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": {"canonical": len(inv.files), "bytes": sum(inv.sizes.values()), "duplicates_skipped": len(inv.duplicates),
                  "empty_skipped": len(inv.empty), "content_sha256": inv.digest,
                  "duplicate_example": next(iter(inv.duplicates.items()), None)},
        "normalised": counts,
        "lake_path": str(out.relative_to(config.MARKETS_DIR)) if out.is_relative_to(config.MARKETS_DIR) else str(out),
        "seconds": round(time.perf_counter() - t0, 1),
    }
    config.MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    checksum_file.write_text("".join(f"{h}  {p}\n" for p, h in sorted(inv.files.items())))
    (config.MANIFEST_DIR / f"{dataset_id}.json").write_text(json.dumps(manifest, indent=2, default=str))
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    return manifest


if __name__ == "__main__":
    import sys
    for ds in sys.argv[1:] or [catalog.PRIMARY, catalog.SECONDARY, catalog.NEWS]:
        m = ingest(ds)
        print(ds, json.dumps(m["normalised"], default=str), m["files"]["duplicates_skipped"], "duplicates skipped", m["seconds"], "s")
