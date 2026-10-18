"""Hand-calculated metrics.

Sequence (start balance 1000): +100, -50, +200, -150, -50, 0
  equity: 1100, 1050, 1250, 1100, 1050, 1050   peak: 1100, 1100, 1250, 1250, 1250, 1250
  drawdown: 0, 50, 0, 150, 200, 200 -> max 200 (200/1250 = 16%)
  gross profit 300, gross loss 250 -> PF 1.2; net 50; expectancy 50/6
  wins 2, losses 3, breakeven 1 -> win rate 2/6
  avg win 150, avg loss -83.33 -> payoff 1.8
  consecutive losses: -150, -50 -> 2 (the 0 breaks the streak afterward)
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.analytics.metrics import TradeOutcome, breakdown, equity_curve, pnl_by_day, summarize

T0 = datetime(2026, 3, 9, 13, 0, tzinfo=UTC)
PNLS = [100, -50, 200, -150, -50, 0]
RS = [1.0, -0.5, 2.0, -1.5, -0.5, None]


def outcomes():
    return [TradeOutcome(T0 + timedelta(hours=6 * i), p, r, "long" if i % 2 == 0 else "short", f"S{i % 2}")
            for i, (p, r) in enumerate(zip(PNLS, RS, strict=False))]


def test_summary_hand_calculated():
    s = summarize(outcomes(), 1000)
    assert s.trades == 6 and s.wins == 2 and s.losses == 3 and s.breakeven == 1
    assert s.net_pnl == 50
    assert s.gross_profit == 300 and s.gross_loss == 250
    assert s.profit_factor == pytest.approx(1.2)
    assert s.win_rate == pytest.approx(2 / 6)
    assert s.expectancy == pytest.approx(50 / 6)
    assert s.avg_win == 150 and s.avg_loss == pytest.approx(-250 / 3)
    assert s.payoff_ratio == pytest.approx(1.8)
    assert s.largest_win == 200 and s.largest_loss == -150
    assert s.max_drawdown == 200
    assert s.max_drawdown_pct == pytest.approx(0.16)
    assert s.current_drawdown == 200
    assert s.ending_equity == 1050
    assert s.total_return_pct == pytest.approx(0.05)
    assert s.max_consecutive_losses == 2 and s.max_consecutive_wins == 1
    assert s.avg_r == pytest.approx(0.1) and s.r_trades == 5
    assert s.median_r == -0.5
    assert s.low_sample is True


def test_order_independent_of_input_order():
    a = summarize(outcomes(), 1000)
    b = summarize(list(reversed(outcomes())), 1000)
    assert a == b


def test_empty_is_all_undefined_not_zero():
    s = summarize([], 1000)
    assert s.trades == 0
    assert s.win_rate is None and s.profit_factor is None and s.expectancy is None and s.avg_r is None
    assert s.max_drawdown == 0 and s.ending_equity == 1000


def test_profit_factor_undefined_without_losses():
    s = summarize([TradeOutcome(T0, 10), TradeOutcome(T0 + timedelta(1), 5)], 100)
    assert s.profit_factor is None


def test_high_win_rate_can_hide_a_losing_system():
    # 9 winners of +10 and one -200 loser: 90% win rate, still net -110
    xs = [TradeOutcome(T0 + timedelta(minutes=i), 10) for i in range(9)] + [TradeOutcome(T0 + timedelta(hours=1), -200)]
    s = summarize(xs, 1000)
    assert s.win_rate == pytest.approx(0.9)
    assert s.net_pnl == -110 and s.profit_factor < 1


def test_equity_curve_points():
    pts = equity_curve(outcomes(), 1000)
    assert [p["equity"] for p in pts] == [1100, 1050, 1250, 1100, 1050, 1050]
    assert [p["drawdown"] for p in pts] == [0, -50, 0, -150, -200, -200]


def test_daily_pnl_uses_user_timezone_across_midnight():
    # 23:30 UTC on 9 March is 19:30 in New York (EDT since 8 March 2026) and 08:30 on 10 March in Tokyo
    o = [TradeOutcome(datetime(2026, 3, 9, 23, 30, tzinfo=UTC), 10)]
    assert list(pnl_by_day(o, "UTC")) == ["2026-03-09"]
    assert list(pnl_by_day(o, "America/New_York")) == ["2026-03-09"]
    assert list(pnl_by_day(o, "Asia/Tokyo")) == ["2026-03-10"]


def test_breakdown_groups():
    rows = {r["key"]: r for r in breakdown(outcomes(), lambda o: o.label)}
    assert rows["S0"]["net_pnl"] == 100 + 200 - 50
    assert rows["S1"]["net_pnl"] == -50 - 150 + 0
