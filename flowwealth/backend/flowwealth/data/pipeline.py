"""Build a versioned dataset: fetch -> clean -> timestamp -> lake -> quality report."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from flowwealth.data.lake import DataLake, attach_timestamps
from flowwealth.data.providers.synthetic import generate_universe
from flowwealth.data.quality import clean_bars


def build_synthetic(lake_root: Path, version: str, n_tickers: int, start: str, end: str, seed: int = 7) -> dict:
    t0 = time.perf_counter()
    raw, master, meta = generate_universe(n_tickers, start, end, seed)
    t_gen = time.perf_counter() - t0
    clean, rep = clean_bars(raw)
    bars = attach_timestamps(clean)
    t_clean = time.perf_counter() - t0 - t_gen
    lineage = {"source": "synthetic.generate_universe", "seed": seed, "n_tickers": n_tickers,
               "start": start, "end": end, "injected_defects": meta["injected"],
               "corporate_actions": meta["actions"].astype(str).to_dict("records")}
    manifest = DataLake(lake_root).write_version(version, bars, master, rep.to_dict(), lineage)
    manifest["timings_s"] = {"generate": round(t_gen, 2), "clean_and_timestamp": round(t_clean, 2),
                             "total": round(time.perf_counter() - t0, 2)}
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lake", default="lake")
    ap.add_argument("--version", default="syn-v1")
    ap.add_argument("--tickers", type=int, default=650)
    ap.add_argument("--start", default="2019-01-01")
    ap.add_argument("--end", default="2025-12-31")
    a = ap.parse_args()
    print(json.dumps(build_synthetic(Path(a.lake), a.version, a.tickers, a.start, a.end), indent=2, default=str))


if __name__ == "__main__":
    main()
