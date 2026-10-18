"""Hand-calculated position P&L. Multiplier 1 = P&L per unit (troy oz)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

from app.analytics.positions import Fill, compute_position

T0 = datetime(2026, 3, 2, 8, 0, tzinfo=UTC)


def t(minutes):
    return T0 + timedelta(minutes=minutes)


def test_simple_long_winner_with_fees_and_r():
    # Buy 10 oz @ 2000.00, stop 1995.00 -> risk = 5.00 * 10 = 50.00
    # Sell 10 oz @ 2010.00 -> gross = 100.00; fees 0.70 + 0.70 -> net 98.60; R = 98.60 / 50 = 1.972
    r = compute_position("long", [Fill("entry", t(0), D("2000.00"), D(10), D("0.70")),
                                  Fill("exit", t(30), D("2010.00"), D(10), D("0.70"))], initial_stop=D("1995.00"))
    assert r.status == "closed"
    assert r.gross_pnl == D("100.00")
    assert r.net_pnl == D("98.60")
    assert r.initial_risk == D("50.00")
    assert r.r_multiple == D("1.972")


def test_short_with_partial_exits():
    # Sell 4 @ 2050, stop 2056 -> risk 24
    # Cover 2 @ 2044 -> +12 ; cover 2 @ 2052 -> -4 ; net +8 ; R = 8/24
    r = compute_position("short", [Fill("entry", t(0), D(2050), D(4)),
                                   Fill("scale_out", t(10), D(2044), D(2)),
                                   Fill("exit", t(20), D(2052), D(2))], initial_stop=D(2056))
    assert r.net_pnl == D(8)
    assert r.avg_exit_price == D(2048)
    assert r.r_multiple == D(8) / D(24)
    assert r.closed_at == t(20)


def test_scale_in_uses_average_cost_and_first_entry_risk():
    # Buy 1 @ 2000 (stop 1990 -> risk 10), add 1 @ 2010 -> avg 2005; exit 2 @ 2015 -> +20
    r = compute_position("long", [Fill("entry", t(0), D(2000), D(1)),
                                  Fill("scale_in", t(5), D(2010), D(1)),
                                  Fill("exit", t(9), D(2015), D(2))], initial_stop=D(1990))
    assert r.avg_entry_price == D(2005)
    assert r.net_pnl == D(20)
    assert r.initial_risk == D(10)
    assert r.r_multiple == D(2)


def test_planned_risk_amount_overrides_stop_distance():
    r = compute_position("long", [Fill("entry", t(0), D(2000), D(1)), Fill("exit", t(1), D(1990), D(1))],
                         initial_stop=D(1995), planned_risk_amount=D(20))
    assert r.r_multiple == D("-0.5")


def test_open_position_has_no_r_and_no_close_time():
    r = compute_position("long", [Fill("entry", t(0), D(2000), D(2)), Fill("scale_out", t(5), D(2004), D(1))],
                         initial_stop=D(1990))
    assert r.status == "open"
    assert r.open_quantity == D(1)
    assert r.gross_pnl == D(4)  # realized part only
    assert r.r_multiple is None and r.closed_at is None


def test_no_stop_means_r_is_undefined_not_zero():
    r = compute_position("long", [Fill("entry", t(0), D(2000), D(1)), Fill("exit", t(1), D(2001), D(1))])
    assert r.r_multiple is None


def test_over_exit_is_capped_and_reported():
    r = compute_position("long", [Fill("entry", t(0), D(2000), D(1)), Fill("exit", t(1), D(2001), D(3))])
    assert r.status == "closed" and r.net_pnl == D(1)
    assert r.errors and "capped" in r.errors[0]


def test_fills_are_ordered_by_time_not_input_order():
    r = compute_position("long", [Fill("exit", t(5), D(2003), D(1)), Fill("entry", t(0), D(2000), D(1))])
    assert r.net_pnl == D(3) and not r.errors


def test_contract_multiplier():
    # 0.10 lot at 100 oz/lot = 10 oz; modelled as quantity 0.10, multiplier 100
    r = compute_position("long", [Fill("entry", t(0), D(2000), D("0.10")), Fill("exit", t(1), D(2002.5), D("0.10"))],
                         multiplier=D(100))
    assert r.net_pnl == D("25.000")
