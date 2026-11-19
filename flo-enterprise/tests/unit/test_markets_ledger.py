"""Prediction Memory: record-before-outcome, single resolution, DB-level immutability and tamper detection."""
import importlib.util
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from backend.config import ROOT
from backend.db import models as m
from markets import ledger

T0 = datetime(2016, 3, 1, 21, 30, tzinfo=timezone.utc)


def _migration():
    spec = importlib.util.spec_from_file_location("m0005", ROOT / "backend/db/migrations/versions/0005_market_predictions.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def db(tmp_path):
    eng = sa.create_engine(f"sqlite:///{tmp_path / 'ledger.db'}")
    m.Base.metadata.create_all(eng, tables=[m.MarketPrediction.__table__, m.MarketPredictionOutcome.__table__])
    with eng.begin() as c:
        _migration().install_immutability(c)
    return eng


def _rec(s, now=T0, **kw):
    args = dict(now=now, mode="historical_replay", model_version="lightgbm@test", dataset_version="kaggle-us-stocks-etfs-v3",
                ticker="AAPL", horizon_sessions=5, feature_cutoff=now - timedelta(minutes=5), outcome_due=now + timedelta(days=7),
                predicted_excess_return=0.004, predicted_rank_pct=0.93, uncertainty=None, regime="bull_trend",
                evidence={"features": {"mom_12_1_rk": 0.4}, "source": "lake"})
    args.update(kw)
    return ledger.record(s, **args)


def test_record_then_resolve_once(db):
    with Session(db) as s, s.begin():
        pid = _rec(s)
        assert ledger.resolve_due(s, now=T0 + timedelta(days=1), lookup=lambda *a: {"return": 0.02, "benchmark_return": 0.01}, source="t") == 0
        assert ledger.resolve_due(s, now=T0 + timedelta(days=8), lookup=lambda *a: {"return": 0.02, "benchmark_return": 0.01}, source="t") == 1
        assert ledger.resolve_due(s, now=T0 + timedelta(days=9), lookup=lambda *a: {"return": -1.0, "benchmark_return": 0.0}, source="t") == 0
        r = ledger.rows(s)[0]
        assert r["id"] == pid and r["state"] == "resolved" and r["outcome"]["direction_correct"] is True
        assert abs(r["outcome"]["actual_excess_return"] - 0.01) < 1e-12
        summ = ledger.summary(s)
        assert summ["groups"]["mode:historical_replay"]["accuracy"] == 1.0 and summ["chain"]["valid"]


def test_cannot_record_after_outcome_or_with_future_inputs(db):
    with Session(db) as s:
        with pytest.raises(ledger.RecordingError, match="before its outcome"):
            _rec(s, outcome_due=T0 - timedelta(seconds=1))
        with pytest.raises(ledger.RecordingError, match="postdate"):
            _rec(s, feature_cutoff=T0 + timedelta(seconds=1))
        with pytest.raises(ledger.RecordingError, match="mode"):
            _rec(s, mode="live_trading")
        with pytest.raises(ledger.RecordingError, match="timezone"):
            _rec(s, now=T0.replace(tzinfo=None))


def test_database_rejects_update_and_delete(db):
    with Session(db) as s, s.begin():
        _rec(s)
        ledger.resolve_due(s, now=T0 + timedelta(days=8), lookup=lambda *a: {"return": 0.0, "benchmark_return": 0.0}, source="t")
    for stmt in ("UPDATE market_predictions SET predicted_excess_return = 0.5", "DELETE FROM market_predictions",
                 "UPDATE market_prediction_outcomes SET actual_return = 9", "DELETE FROM market_prediction_outcomes"):
        with pytest.raises(sa.exc.DatabaseError, match="append-only"):
            with db.begin() as c:
                c.exec_driver_sql(stmt)


def test_tampering_with_the_file_is_detected(db):
    with Session(db) as s, s.begin():
        for t in ("AAPL", "MSFT", "NVDA"):
            _rec(s, ticker=t)
    with db.begin() as c:   # an attacker with file access drops the trigger and edits a forecast
        c.exec_driver_sql("DROP TRIGGER market_predictions_no_update")
        n = c.exec_driver_sql("UPDATE market_predictions SET predicted_excess_return = 0.05 WHERE seq = 2").rowcount
        assert n == 1
    with Session(db) as s:
        v = ledger.verify_chain(s)
        assert v == {"valid": False, "checked": 2, "first_invalid_seq": 2, "prediction_id": v["prediction_id"]}


def test_migration_installs_triggers_on_the_application_database(st):
    """The seeded application DB (alembic upgrade head) has the ledger tables and rejects edits."""
    from backend.db.session import get_engine
    eng = get_engine()
    names = sa.inspect(eng).get_table_names()
    assert "market_predictions" in names and "market_prediction_outcomes" in names
    names_t = {r[0] for r in eng.connect().exec_driver_sql("SELECT name FROM sqlite_master WHERE type='trigger'")}
    assert {"market_predictions_no_update", "market_predictions_no_delete"} <= names_t
    # SQLite row triggers fire per row, so insert one inside a transaction that is rolled back afterwards
    conn = eng.connect()
    tx = conn.begin()
    try:
        s = Session(bind=conn)
        _rec(s)
        with pytest.raises(sa.exc.DatabaseError, match="append-only"):
            conn.exec_driver_sql("DELETE FROM market_predictions")
    finally:
        tx.rollback()
        conn.close()
