"""Market data foundation: catalog/licensing, integrity, lake quality flags, point-in-time features (fixture data)."""
import json
from pathlib import Path

import pandas as pd
import pytest

from markets import catalog, config, ingest
from tests.fixtures.markets_fixture import build as build_fixture


@pytest.fixture
def fixture_lake(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LAKE_DIR", tmp_path / "lake")
    monkeypatch.setattr(config, "MANIFEST_DIR", tmp_path / "manifests")
    (tmp_path / "manifests").mkdir()
    info = build_fixture(tmp_path)
    from markets import lake
    res = lake.build()
    return info, res


def test_catalog_records_licence_and_provenance():
    for d in catalog.CATALOG.values():
        assert d.kaggle_license and d.url.startswith("https://www.kaggle.com/datasets/") and d.publisher and d.upstream_source
        assert d.known_limitations and d.classification == "public" and d.synthetic is False
    assert any("SURVIVORSHIP" in x for x in catalog.CATALOG[catalog.PRIMARY].known_limitations)


def test_synthetic_or_unapproved_data_cannot_enter_research():
    from dataclasses import replace
    with pytest.raises(ValueError, match="synthetic"):
        catalog.assert_real(replace(catalog.CATALOG[catalog.PRIMARY], synthetic=True))
    with pytest.raises(ValueError, match="not approved"):
        catalog.assert_real(catalog.CATALOG["kaggle-nasdaq-yfinance-v2"])


def test_inventory_dedupes_by_checksum_and_detects_changes(tmp_path):
    (tmp_path / "Stocks").mkdir()
    (tmp_path / "Data" / "Stocks").mkdir(parents=True)
    (tmp_path / "Stocks" / "aaa.us.txt").write_text("Date,Open\n2020-01-02,1\n")
    (tmp_path / "Data" / "Stocks" / "aaa.us.txt").write_text("Date,Open\n2020-01-02,1\n")  # byte-identical copy
    (tmp_path / "Stocks" / "empty.us.txt").write_text("")
    inv = ingest.inventory(tmp_path)
    assert list(inv.files) == ["Stocks/aaa.us.txt"]
    assert inv.duplicates == {"Data/Stocks/aaa.us.txt": "Stocks/aaa.us.txt"} and inv.empty == ["Stocks/empty.us.txt"]
    expected = dict(inv.files)
    d1 = inv.digest
    (tmp_path / "Stocks" / "aaa.us.txt").write_text("Date,Open\n2020-01-02,2\n")
    inv2 = ingest.inventory(tmp_path)
    assert inv2.digest != d1
    with pytest.raises(ingest.IntegrityError):
        ingest.verify(inv2, expected)


def test_share_classes_stay_distinct():
    assert ingest._ticker("brk-b.us") == "BRK-B" and ingest._ticker("abr_a.us") == "ABR_A" and ingest._ticker("aapl.us") == "AAPL"


def test_lake_flags_defects_instead_of_deleting_or_filling(fixture_lake):
    info, res = fixture_lake
    from markets.lake import connect
    con = connect()
    flags = dict(con.execute("SELECT quality_flag, count(*) FROM bars GROUP BY 1").fetchall())
    assert flags["spike_reversal"] == 1 and flags["ohlc_violation"] == 1 and flags["unadjusted_corporate_action"] == 1
    assert res.quality["missing_sessions"] == 1          # the gap is counted, not interpolated
    assert con.execute("SELECT count(*) FROM bars WHERE ticker='T05'").fetchone()[0] == 699
    assert res.validation["survivorship"]["sp500_2016_members_absent_from_primary"] == 1   # 'GONE'
    av = con.execute("SELECT CAST(available_at AS VARCHAR) FROM bars WHERE ticker='SPY' AND date = DATE '2005-07-01'").fetchone()[0]
    assert av.startswith("2005-07-01 20:30:00")   # 16:30 New York (EDT) as UTC


def test_features_are_point_in_time(fixture_lake):
    """Features and universe membership on truncated history equal those on full history; labels never cross the cut."""
    from markets import features
    monkey_universe = features.UNIVERSE_SIZE
    full = features.compute()
    cut = "2006-06-30"
    trunc = features.compute(f"AND b.date <= DATE '{cut}'")
    key = ["ticker", "date"]
    cols = list(features.FEATURES) + [f"{f}_rk" for f in features.FEATURES] + ["in_universe"]
    a = full[full.date <= pd.Timestamp(cut)].set_index(key)[cols].sort_index()
    b = trunc.set_index(key)[cols].sort_index()
    assert len(b) > 1000 and monkey_universe > 0
    pd.testing.assert_frame_equal(a, b, check_exact=False, rtol=1e-9)
    late = trunc[trunc.date > pd.Timestamp(cut) - pd.Timedelta(days=3)]
    assert late["fwd_ret_5"].isna().all()   # outcome not yet observable at the cut


def test_labels_never_span_flagged_bars_or_gaps(fixture_lake):
    from markets import features
    f = features.compute()
    days = pd.bdate_range("2005-02-25", periods=700)
    t01 = f[f.ticker == "T01"]
    before_bad = t01[(t01.date < days[300]) & (t01.date >= days[295])]   # 5-session labels would cross the bad tick
    assert len(before_bad) == 5 and before_bad["fwd_ret_5"].isna().all()
    t05 = f[f.ticker == "T05"]
    assert t05.loc[t05.date == days[399], "fwd_ret_1"].isna().all()     # next bar is two sessions later: no label
    assert t05.loc[t05.date == days[398], "fwd_ret_1"].notna().all()


def test_label_end_always_after_signal(fixture_lake):
    from markets import features
    f = features.compute()
    for h in features.HORIZONS:
        m = f[f"fwd_ret_{h}"].notna()
        assert (pd.to_datetime(f.loc[m, f"label_end_{h}"], utc=True) > pd.to_datetime(f.loc[m, "available_at"], utc=True)).all()


REAL = Path(config.LAKE_DIR / "research" / "features.parquet")


@pytest.mark.skipif(not REAL.exists(), reason="real Kaggle lake not built in this environment (run python -m markets.pipeline)")
def test_real_lake_meets_observation_and_provenance_targets():
    m = json.loads((config.MANIFEST_DIR / f"{catalog.PRIMARY}.json").read_text())
    assert m["normalised"]["rows"] >= 1_000_000 and m["files"]["duplicates_skipped"] > 0
    assert len((config.MANIFEST_DIR / f"{catalog.PRIMARY}.sha256").read_text().splitlines()) == m["files"]["canonical"]
    lake = json.loads((config.MANIFEST_DIR / "research_lake.json").read_text())
    assert lake["counts"]["research_window_clean_stock_bars"] >= 1_000_000
    assert lake["validation"]["cross_source_daily_returns"]["share_within_1pct"] > 0.99


@pytest.mark.skipif(not REAL.exists(), reason="real Kaggle lake not built in this environment")
def test_real_label_matches_hand_computation():
    import duckdb
    con = duckdb.connect()
    f = con.execute(f"SELECT fwd_ret_5 FROM read_parquet('{REAL}') WHERE ticker='AAPL' AND date = DATE '2015-06-01'").fetchone()[0]
    px = [r[0] for r in con.execute(f"SELECT adj_close FROM read_parquet('{config.LAKE_DIR / 'research' / 'bars.parquet'}') "
                                     "WHERE ticker='AAPL' AND date BETWEEN DATE '2015-06-01' AND DATE '2015-06-08' ORDER BY date").fetchall()]
    import math
    assert abs(f - math.log(px[5] / px[0])) < 1e-12
