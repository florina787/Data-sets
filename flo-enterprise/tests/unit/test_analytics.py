"""Financial correctness tests. Expected values are computed by hand (shown inline). Release-blocking."""
from datetime import date
from decimal import Decimal

import pytest

from analytics import aum, profitability, returns, revenue, risk
from analytics.money import from_cents, money, to_cents

pytestmark = pytest.mark.critical
D = Decimal


def test_money_rounding_is_bankers():
    assert money("2.345") == D("2.34")
    assert money("2.355") == D("2.36")
    assert money("-1.005") == D("-1.00")
    assert from_cents(12345) == D("123.45")
    assert to_cents(D("10.005")) == 1000  # 1000.5 -> half-even -> 1000


def test_aum_reconciliation_balanced_and_break():
    rf = aum.RollForward(D(1000), D(200), D(50), D(30), D(1180))
    assert rf.net_flows == D(150)
    assert aum.reconcile("p", rf).balanced
    bad = aum.RollForward(D(1000), D(200), D(50), D(30), D("1180.02"))
    res = aum.reconcile("p", bad)
    assert not res.balanced and res.difference == D("0.02")
    assert aum.reconcile("p", bad, tolerance=D("0.05")).balanced


def test_roll_forward_and_waterfall_from_rows():
    rows = [
        dict(month=date(2025, 1, 31), aum_open_cents=100_00, subscriptions_cents=10_00, redemptions_cents=5_00, market_cents=2_00, aum_close_cents=107_00),
        dict(month=date(2025, 2, 28), aum_open_cents=107_00, subscriptions_cents=3_00, redemptions_cents=0, market_cents=-1_00, aum_close_cents=109_00),
    ]
    rf = aum.roll_forward_from_rows(rows, date(2025, 1, 31), date(2025, 2, 28))
    assert (rf.open, rf.subscriptions, rf.redemptions, rf.market, rf.close) == (D(100), D(13), D(5), D(1), D(109))
    assert rf.residual == 0
    wf = aum.waterfall(rf)
    assert [w["value"] for w in wf] == ["100.00", "13.00", "-5.00", "1.00", "109.00"]
    # organic growth: 8 / 100 * 12 / 2 = 0.48
    assert aum.organic_growth_rate(rf, 2) == D("0.48")


def test_twr_neutralizes_flows():
    # month1: 100 -> 110 (10%), contribution 50 at end -> 160 close; month2: 160 -> 152 (-5%)
    vals = [(100.0, 50.0, 160.0), (160.0, 0.0, 152.0)]
    assert returns.twr(vals) == pytest.approx(1.10 * 0.95 - 1)  # 0.045


def test_annualize():
    assert returns.annualize(0.21, 24) == pytest.approx(0.1)
    assert returns.annualize(0.05, 6) == 0.05  # not annualized below a year


def test_xirr_known_value():
    # invest 100, receive 110 exactly one year later -> 10%
    r = returns.xirr([(date(2025, 1, 1), -100.0), (date(2026, 1, 1), 110.0)])
    assert r == pytest.approx(0.10, abs=1e-8)


def test_mwr_vs_twr_flow_timing():
    # 100 grows 10% in year 1 -> 110; add 1000 at t=1y; then -10% -> 1089 at t=2y
    m = returns.mwr(date(2024, 1, 1), 100.0, [(date(2025, 1, 1), 1000.0)], date(2026, 1, 1), 1089.0)
    t = returns.twr([(100.0, 1000.0, 1110.0), (1110.0, 0.0, 999.0)])
    assert t == pytest.approx(1.1 * 0.9 - 1)
    assert m < 0  # large contribution before the loss: investor experience is negative
    with pytest.raises(ValueError):
        returns.xirr([(date(2025, 1, 1), 100.0)])


def test_relative_and_excess():
    p, b = [0.02, -0.01], [0.01, 0.0]
    assert returns.excess_returns(p, b) == pytest.approx([0.01, -0.01])
    rel = returns.relative_cumulative(p, b)
    assert rel[-1] == pytest.approx(1.02 * 0.99 / 1.01 - 1)


def test_volatility_and_sharpe():
    r = [0.01, 0.03, -0.02, 0.02]
    # mean 0.01, deviations 0, .02, -.03, .01 -> ss = 0.0014 -> var(n-1)=0.000466667 -> sd=0.0216025
    assert risk.stdev(r) == pytest.approx(0.0216024690)
    assert risk.volatility(r) == pytest.approx(0.0216024690 * 12 ** 0.5)
    rf = [0.0] * 4
    assert risk.sharpe(r, rf) == pytest.approx(0.01 * 12 / (0.0216024690 * 12 ** 0.5))
    assert risk.sharpe([0.01, 0.01, 0.01], [0, 0, 0]) is None


def test_max_drawdown():
    r = [0.10, -0.20, 0.05, 0.25]
    # wealth: 1.1, 0.88, 0.924, 1.155 ; peak 1.1 ; trough 0.88 -> -20% ; recovery at idx 3
    md = risk.max_drawdown(r)
    assert md["max_drawdown"] == pytest.approx(-0.2)
    assert (md["peak_index"], md["trough_index"], md["recovery_index"]) == (0, 1, 3)


def test_concentration_and_drift():
    w = [0.5, 0.3, 0.2]
    assert risk.hhi(w) == pytest.approx(0.38)
    assert risk.effective_n(w) == pytest.approx(1 / 0.38)
    assert risk.top_n_weight(w, 2) == pytest.approx(0.8)
    assert [b["id"] for b in risk.limit_breaches({"a": 0.5, "b": 0.3, "c": 0.2}, 0.25)] == ["a", "b"]
    d = risk.allocation_drift({"eq": 0.6, "fi": 0.4}, {"eq": 0.7, "fi": 0.3})
    assert d["total_drift"] == pytest.approx(0.1)
    assert d["per_asset"]["eq"] == pytest.approx(0.1)


def test_tracking_error_beta_correlation():
    p, b = [0.02, 0.04, 0.0, 0.02], [0.01, 0.02, 0.0, 0.01]
    assert risk.beta(p, b) == pytest.approx(2.0)
    assert risk.correlation(p, b) == pytest.approx(1.0)
    assert risk.tracking_error([0.01, 0.02], [0.01, 0.02]) == 0
    assert risk.information_ratio([0.01, 0.02], [0.01, 0.02]) is None


def test_monthly_fee_revenue():
    # avg AUM 1,000,000 ; 120 bps ; /12 -> 1,000.00
    assert revenue.monthly_fee_revenue(D(990_000), D(1_010_000), 120) == D("1000.00")


def test_revenue_yield():
    assert revenue.revenue_yield_bps(D(12_000), D(1_000_000), 12) == D(120)


def test_revenue_attribution_exact_decomposition():
    # period0: A 100 @1.0%, B 100 @0.2% ; period1: A 80 @0.85% (fee cut), B 220 @0.2%
    p0 = {"A": (D(100), D("1.0")), "B": (D(100), D("0.2"))}
    p1 = {"A": (D(80), D("0.68")), "B": (D(220), D("0.44"))}
    out = revenue.attribution(p0, p1, 12, 12)
    assert out["annualized_revenue_0"] == D("1.20") and out["annualized_revenue_1"] == D("1.12")
    assert out["change"] == D("-0.08")
    assert out["check_residual"] == 0
    assert out["volume_effect"] + out["rate_effect"] == out["change"]
    assert out["mix_effect"] + out["fee_change_effect"] == out["rate_effect"]
    # fee effect: s1_A * (0.0085-0.01) * 300 = (80/300)*(-0.0015)*300 = -0.12
    assert out["fee_change_effect"] == D("-0.12")


def test_fee_impact():
    out = revenue.fee_impact(D(100_000), D("0.06"), 200, 10)
    # 100000*1.06^10 = 179084.77 ; 100000*1.04^10 = 148024.43
    assert out["ending_no_fee"] == D("179084.77")
    assert out["ending_with_fee"] == D("148024.43")
    assert out["fee_drag"] == D("31060.34")


def test_operating_margin_and_product_contribution():
    assert profitability.operating_margin(D(100), D(70)) == D("0.3")
    prods = [dict(id="A", name="A", vehicle="Mutual Fund", asset_class="Equity", revenue=D(150), avg_aum=D(10000)),
             dict(id="B", name="B", vehicle="ETF", asset_class="Equity", revenue=D(50), avg_aum=D(20000))]
    out = profitability.product_contribution(prods, D(140), D(40), 12)
    # shared = 100, A gets 75, B 25 ; A direct = 10000*40bps = 40
    assert out[0]["contribution"] == D("35.00") and out[1]["contribution"] == D("25.00")
