import inspect
from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from flowwealth.contracts import DataStatus, Horizon, utcnow
from flowwealth.profiles.profile import HARD_LIMITS, Appetite, TraderProfile
from flowwealth.research.paper import PaperAccount
from flowwealth.risk.engine import OrderIntent, PortfolioState, Verdict, assess
from flowwealth.risk.regime import classify, evaluate_alarm, indicators


def _order(**kw):
    base = dict(ticker="AAA", side="buy", qty=100, price=100.0, stop_price=97.0, sector="Tech", adv_shares=1e6,
                daily_vol=0.02, data_status=DataStatus.DELAYED, data_timestamp=utcnow() - timedelta(minutes=1),
                horizon=Horizon.SWING)
    base.update(kw)
    return OrderIntent(**base)


def _pf(eq=100_000, peak=None, day=None):
    return PortfolioState(eq, peak or eq, day or eq, [])


def test_aggressive_cannot_exceed_hard_limits():
    p = TraderProfile(user_id="u", horizon=Horizon.INTRADAY, appetite=Appetite.AGGRESSIVE, capital=1e5,
                      leverage_permitted=True, overrides={"max_gross_leverage": 10, "max_loss_per_trade_pct": 50,
                                                          "max_drawdown_pct": 99, "daily_loss_limit_pct": 80})
    L = p.effective_limits()
    for k, v in HARD_LIMITS.model_dump().items():
        assert getattr(L, k) <= v


def test_fast_is_not_aggressive():
    p = TraderProfile(user_id="u", horizon=Horizon.SCALP, appetite=Appetite.CONSERVATIVE, capital=1e5)
    assert p.effective_limits().max_loss_per_trade_pct == 0.5 and p.effective_limits().max_gross_leverage == 1.0


def test_scalp_requires_live_fresh_data():
    p = TraderProfile(user_id="u", horizon=Horizon.SCALP, appetite=Appetite.AGGRESSIVE, capital=1e5)
    d = assess(_order(horizon=Horizon.SCALP), _pf(), p)
    assert d.verdict == Verdict.REJECT and "scalp requires" in d.reasons[0]
    d = assess(_order(horizon=Horizon.SCALP, data_status=DataStatus.LIVE, data_timestamp=utcnow()), _pf(), p)
    assert d.verdict != Verdict.REJECT


def test_synthetic_data_is_never_actionable():
    p = TraderProfile(user_id="u", horizon=Horizon.SWING, appetite=Appetite.MODERATE, capital=1e5)
    assert assess(_order(data_status=DataStatus.SYNTHETIC), _pf(), p).verdict == Verdict.REJECT


def test_loss_per_trade_reduces_size_using_gap_scenario():
    p = TraderProfile(user_id="u", horizon=Horizon.SWING, appetite=Appetite.MODERATE, capital=1e5)
    d = assess(_order(qty=1000, price=20.0, stop_price=19.4, daily_vol=0.05), _pf(), p)
    # 1% of 100k = 1000 at risk; gap = max(0.6, 20*0.05*3=3.0) -> 333 shares (position cap is 500)
    assert d.verdict == Verdict.REDUCE and d.approved_qty == 333 and "loss_per_trade" in d.reasons[-1]


def test_drawdown_and_daily_loss_halts():
    p = TraderProfile(user_id="u", horizon=Horizon.SWING, appetite=Appetite.AGGRESSIVE, capital=1e5)
    assert assess(_order(), _pf(eq=70_000, peak=100_000), p).verdict == Verdict.REJECT
    assert assess(_order(), _pf(eq=94_000, day=100_000), p).verdict == Verdict.REJECT


def test_stop_required_and_no_override_parameter():
    p = TraderProfile(user_id="u", horizon=Horizon.SWING, appetite=Appetite.AGGRESSIVE, capital=1e5)
    assert assess(_order(stop_price=101), _pf(), p).verdict == Verdict.REJECT
    params = set(inspect.signature(assess).parameters)
    assert params == {"order", "pf", "profile", "now"}  # no judge / agent override input exists


def test_paper_account_rejections_do_not_move_cash():
    p = TraderProfile(user_id="u", horizon=Horizon.SWING, appetite=Appetite.MODERATE, capital=1e5)
    acct = PaperAccount(p, cash=1e5)
    acct.submit(_order(stop_price=101))
    assert acct.cash == 1e5 and acct.blotter[-1]["verdict"] == "REJECT"
    d = acct.submit(_order(qty=50))
    assert d.verdict == Verdict.APPROVE and acct.positions["AAA"].qty == 50 and acct.cash < 1e5 - 5000
    assert acct.mode == "PAPER"


def test_crash_alarm_metrics_on_constructed_series():
    idx = pd.bdate_range("2020-01-01", periods=600)
    r = pd.Series(0.0005, index=idx)
    r.iloc[400:420] = -0.01  # ~18% drawdown
    r.iloc[380:420] += np.random.default_rng(0).normal(0, 0.03, 40)
    lv = classify(indicators(r))
    ev = evaluate_alarm(lv["level"], r, alarm_from="Elevated")
    assert ev["event_days"] > 0 and ev["precision"] is not None and set(ev) >= {"recall", "false_alarm_days"}
