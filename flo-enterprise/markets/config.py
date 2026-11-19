"""Paths and settings for the market research lake (all local, gitignored under var/markets by default)."""
from __future__ import annotations

import os
from pathlib import Path

from backend.config import ROOT

MARKETS_DIR = Path(os.environ.get("FLO_MARKETS_DIR", ROOT / "var" / "markets"))
KAGGLE_CACHE = Path(os.environ.get("FLO_KAGGLE_CACHE", MARKETS_DIR / "kaggle-cache"))
LAKE_DIR = MARKETS_DIR / "lake"
REPORTS_DIR = MARKETS_DIR / "reports"
MANIFEST_DIR = ROOT / "markets" / "manifests"  # committed: provenance, licences, checksums, counts (no data)

# US equities: regular session closes 16:00 America/New_York; an EOD bar is treated as usable 30 minutes later.
EXCHANGE_TZ = "America/New_York"
CLOSE_HOUR = 16
EOD_PUBLICATION_LAG_MIN = 30

BENCHMARK = "SPY"
