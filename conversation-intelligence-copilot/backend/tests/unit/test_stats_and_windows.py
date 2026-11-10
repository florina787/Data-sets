import pytest

from app.analytics.stats import chi_square_independence, minmax, two_proportion_test, wilson_interval
from app.analytics.time_windows import resolve_window


def test_wilson_interval_known_values():
    lo, hi = wilson_interval(42, 87)
    assert lo == pytest.approx(0.3807, abs=1e-3) and hi == pytest.approx(0.5863, abs=1e-3)
    assert wilson_interval(0, 0) == (0.0, 0.0)
    lo, hi = wilson_interval(0, 10)
    assert lo == 0.0 and 0 < hi < 0.35


def test_chi_square_and_two_proportion():
    same = chi_square_independence([[50, 50], [50, 50]])
    assert same["p_value"] == pytest.approx(1.0)
    diff = chi_square_independence([[90, 10], [10, 90]])
    assert diff["p_value"] < 0.001
    assert chi_square_independence([[1, 1]])["valid"] is False
    assert two_proportion_test(42, 87, 49, 156)["p_value"] == pytest.approx(0.0092, abs=5e-4)


def test_minmax():
    assert minmax([1, 2, 3]) == [0, 0.5, 1]
    assert minmax([2, 2]) == [0.5, 0.5]


def test_last_month_is_latest_month_in_data_not_today(db):
    w = resolve_window(db, "original", {"type": "last_month"})
    assert (w.start, w.end, w.label) == ("2025-02-01", "2025-03-01", "February 2025")
    assert "conversations" in w.explanation


def test_previous_month_and_empty_month(db):
    w = resolve_window(db, "original", {"type": "previous_month", "month": "2025-02"})
    assert w.start == "2025-01-01" and w.label == "January 2025"
    w = resolve_window(db, "original", {"type": "month", "month": "2024-06"})
    assert "No conversations" in w.explanation


def test_unknown_window_type_rejected(db):
    with pytest.raises(ValueError):
        resolve_window(db, "original", {"type": "fortnight"})


def test_partial_low_volume_month_falls_back(tmp_path, monkeypatch):
    """A trailing month with few conversations and no data to month-end is skipped, with an explanation."""
    import duckdb
    import pandas as pd

    from app.analytics.db import AnalyticsDB

    path = tmp_path / "a.duckdb"
    con = duckdb.connect(str(path))
    rows = [("C%d" % i, "original", "2025-0%d" % m, pd.Timestamp(f"2025-0{m}-10")) for m, n in ((1, 40), (2, 40), (3, 3)) for i in range(n)]
    conv = pd.DataFrame(rows, columns=["conversation_id", "dataset_source", "month", "start_timestamp"])
    msgs = pd.DataFrame({"dataset_source": ["original"] * 2, "timestamp": [pd.Timestamp("2025-01-01"), pd.Timestamp("2025-03-11")]})
    con.register("c", conv)
    con.register("m", msgs)
    con.execute("CREATE TABLE conversations AS SELECT * FROM c")
    con.execute("CREATE TABLE messages AS SELECT * FROM m")
    con.close()
    w = resolve_window(AnalyticsDB(path), "original", {"type": "last_month"})
    assert w.label == "February 2025" and w.rule == "latest_complete_month" and "partly covered" in w.explanation
