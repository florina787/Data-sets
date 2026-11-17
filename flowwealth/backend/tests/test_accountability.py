import sqlite3
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from flowwealth.contracts import DataStatus, Horizon, PredictionIn
from flowwealth.evaluation.monitor import DegradationRule, check_degradation, evaluate_records, psi
from flowwealth.evaluation.registry import ModelCard, ModelRegistry
from flowwealth.memory.store import PredictionMemory, RecordingError

T0 = datetime(2025, 3, 3, 21, tzinfo=timezone.utc)


def _pred(**kw):
    base = dict(model_version="lgbm@1", strategy_id="xs5", ticker="SYN0001", horizon=Horizon.SWING, horizon_bars=5,
                input_cutoff=T0 - timedelta(minutes=30), target_time=T0 + timedelta(days=7), forecast_return=0.01,
                prob_up=0.6, data_status=DataStatus.SYNTHETIC, regime="bull_trend")
    base.update(kw)
    return PredictionIn(**base)


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


def test_record_and_resolve_lifecycle():
    clk = Clock(T0)
    mem = PredictionMemory(clock=clk)
    pid = mem.record(_pred())
    assert mem.resolve_due(lambda *a: {"return": 0.02}, "test") == 0  # not due yet
    clk.t = T0 + timedelta(days=8)
    assert mem.resolve_due(lambda *a: {"return": 0.02, "benchmark_return": 0.0}, "test") == 1
    rec = mem.joined()[0]
    assert rec["prediction_id"] == pid and rec["direction_correct"] == 1 and abs(rec["abs_error"] - 0.01) < 1e-12
    assert mem.resolve_due(lambda *a: {"return": -1}, "test") == 0  # outcome written once


def test_cannot_record_after_outcome_or_with_future_inputs():
    mem = PredictionMemory(clock=Clock(T0))
    with pytest.raises(RecordingError):
        mem.record(_pred(target_time=T0 - timedelta(seconds=1)))
    with pytest.raises(RecordingError):
        mem.record(_pred(input_cutoff=T0 + timedelta(seconds=1)))


def test_predictions_are_immutable_and_tamper_evident(tmp_path):
    path = tmp_path / "mem.db"
    mem = PredictionMemory(path, clock=Clock(T0))
    for i in range(3):
        mem.record(_pred(ticker=f"T{i}"))
    with pytest.raises(sqlite3.DatabaseError):
        mem.db.execute("UPDATE predictions SET payload='{}' WHERE seq=2")
    with pytest.raises(sqlite3.DatabaseError):
        mem.db.execute("DELETE FROM predictions")
    assert mem.verify_chain() == (True, None)
    # an attacker with file access drops the trigger and edits a forecast
    raw = sqlite3.connect(path)
    raw.execute("DROP TRIGGER predictions_no_update")
    cur = raw.execute("""UPDATE predictions SET payload=replace(payload, '"forecast_return": 0.01', '"forecast_return": 0.05') WHERE seq=2""")
    assert cur.rowcount == 1
    assert '0.05' in raw.execute("SELECT payload FROM predictions WHERE seq=2").fetchone()[0]
    raw.commit()
    assert PredictionMemory(path, clock=Clock(T0)).verify_chain() == (False, 2)


def test_evaluate_records_and_degradation():
    clk = Clock(T0)
    mem = PredictionMemory(clock=clk)
    rng = np.random.default_rng(0)
    for i in range(50):
        mem.record(_pred(ticker=f"T{i}", forecast_return=float(rng.normal()), prob_up=float(rng.uniform())))
    clk.t = T0 + timedelta(days=8)
    mem.resolve_due(lambda *a: {"return": float(rng.normal())}, "test")
    ev = evaluate_records(mem.joined())
    assert ev["n_resolved"] == 50 and "brier" in ev and "calibration" in ev
    d = check_degradation(0.05, -0.02, 50, DegradationRule())
    assert d["status"] == "degraded" and "no auto-retrain" in d["action"]
    assert check_degradation(0.05, 0.04, 10, DegradationRule())["status"] == "insufficient_data"


def test_psi_detects_shift():
    rng = np.random.default_rng(1)
    a = rng.normal(size=5000)
    assert psi(a, rng.normal(size=5000)) < 0.05
    assert psi(a, rng.normal(1.0, 1.5, size=5000)) > 0.25


def _card(mid, sharpe, ic_t=3.0, **kw):
    ev = dict(holdout_ic_t=ic_t, wf_folds_positive_frac=1.0, net_sharpe=sharpe, net_max_dd=-0.1, n_dates=200,
              baseline_net_sharpes={"momentum": 0.2})
    ev.update(kw)
    return ModelCard(mid, "swing", ev, "syn-v1")


def test_champion_challenger_promotion_approval_and_rollback(tmp_path):
    reg = ModelRegistry(tmp_path / "reg.json")
    reg.register(_card("weak@1", -0.5))
    with pytest.raises(PermissionError, match="after costs"):
        reg.promote("weak@1", approved_by="analyst")
    reg.register(_card("a@1", 0.8))
    with pytest.raises(PermissionError, match="human approval"):
        reg.promote("a@1", approved_by=None)
    reg.promote("a@1", approved_by="analyst")
    reg.register(_card("b@1", 0.85))
    assert not reg.evaluate("b@1")["eligible"]  # not better than champion by margin
    reg.register(_card("c@1", 1.2))
    reg.promote("c@1", approved_by="analyst")
    assert reg.champion("swing") == "c@1"
    assert reg.rollback("swing", approved_by="analyst") == "a@1"
    assert ModelRegistry(tmp_path / "reg.json").champion("swing") == "a@1"  # persisted
    with pytest.raises(ValueError):
        reg.register(_card("a@1", 2.0))
