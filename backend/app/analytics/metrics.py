"""Performance metrics over a sequence of closed trades.

Formulas (documented in docs/METRICS.md, which also lists their limitations):

* net = Σ pnl;  gross_profit = Σ pnl>0;  gross_loss = |Σ pnl<0|
* win_rate = wins / trades, where a win is pnl > 0 (breakeven trades count as non-wins)
* profit_factor = gross_profit / gross_loss  (None when there are no losses: undefined, not infinite)
* expectancy = net / trades
* payoff_ratio = avg_win / |avg_loss|
* avg_r, median_r over trades with a defined R only
* equity_t = starting_balance + cumulative pnl after trade t (trades ordered by close time)
* drawdown_t = peak_t - equity_t, peak including the starting balance
* max_drawdown_pct = max over t of drawdown_t / peak_t
* current_drawdown = peak - final equity
* total_return_pct = net / starting_balance

Sharpe, Sortino and annualized figures need a returns series on a fixed calendar grid and enough
history; they are computed in the backtest analytics (Phase 3) and deliberately not here.
"""

from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

MIN_TRADES_FOR_CONFIDENCE = 30


@dataclass(frozen=True)
class TradeOutcome:
    closed_at: datetime
    pnl: float
    r: float | None = None
    direction: str | None = None
    label: str | None = None  # strategy / timeframe / session key used for breakdowns


@dataclass
class Summary:
    trades: int
    wins: int
    losses: int
    breakeven: int
    net_pnl: float
    gross_profit: float
    gross_loss: float
    win_rate: float | None
    profit_factor: float | None
    expectancy: float | None
    avg_win: float | None
    avg_loss: float | None
    payoff_ratio: float | None
    largest_win: float | None
    largest_loss: float | None
    avg_r: float | None
    median_r: float | None
    r_trades: int
    max_consecutive_wins: int
    max_consecutive_losses: int
    starting_balance: float
    ending_equity: float
    total_return_pct: float | None
    max_drawdown: float
    max_drawdown_pct: float | None
    current_drawdown: float
    current_drawdown_pct: float | None
    low_sample: bool

    def to_dict(self) -> dict:
        return asdict(self)


def summarize(outcomes: list[TradeOutcome], starting_balance: float = 0.0) -> Summary:
    ordered = sorted(outcomes, key=lambda o: o.closed_at)
    pnls = [o.pnl for o in ordered]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gp, gl = sum(wins), -sum(losses)
    rs = [o.r for o in ordered if o.r is not None]
    n = len(pnls)

    max_w = max_l = cur_w = cur_l = 0
    for p in pnls:
        if p > 0:
            cur_w, cur_l = cur_w + 1, 0
        elif p < 0:
            cur_w, cur_l = 0, cur_l + 1
        else:
            cur_w = cur_l = 0
        max_w, max_l = max(max_w, cur_w), max(max_l, cur_l)

    equity = peak = starting_balance
    max_dd = 0.0
    max_dd_pct: float | None = 0.0 if starting_balance > 0 else None
    for p in pnls:
        equity += p
        peak = max(peak, equity)
        dd = peak - equity
        max_dd = max(max_dd, dd)
        if peak > 0 and max_dd_pct is not None:
            max_dd_pct = max(max_dd_pct, dd / peak)
    cur_dd = peak - equity
    avg_win = gp / len(wins) if wins else None
    avg_loss = -gl / len(losses) if losses else None
    return Summary(
        trades=n,
        wins=len(wins),
        losses=len(losses),
        breakeven=n - len(wins) - len(losses),
        net_pnl=sum(pnls),
        gross_profit=gp,
        gross_loss=gl,
        win_rate=len(wins) / n if n else None,
        profit_factor=gp / gl if gl > 0 else None,
        expectancy=sum(pnls) / n if n else None,
        avg_win=avg_win,
        avg_loss=avg_loss,
        payoff_ratio=(avg_win / -avg_loss) if avg_win is not None and avg_loss else None,
        largest_win=max(wins) if wins else None,
        largest_loss=min(losses) if losses else None,
        avg_r=sum(rs) / len(rs) if rs else None,
        median_r=statistics.median(rs) if rs else None,
        r_trades=len(rs),
        max_consecutive_wins=max_w,
        max_consecutive_losses=max_l,
        starting_balance=starting_balance,
        ending_equity=equity,
        total_return_pct=(sum(pnls) / starting_balance) if starting_balance > 0 else None,
        max_drawdown=max_dd,
        max_drawdown_pct=max_dd_pct,
        current_drawdown=cur_dd,
        current_drawdown_pct=(cur_dd / peak) if peak > 0 else None,
        low_sample=n < MIN_TRADES_FOR_CONFIDENCE,
    )


def equity_curve(outcomes: list[TradeOutcome], starting_balance: float = 0.0) -> list[dict]:
    """One point per closed trade: equity and drawdown after that trade."""
    equity = peak = starting_balance
    points = []
    for o in sorted(outcomes, key=lambda o: o.closed_at):
        equity += o.pnl
        peak = max(peak, equity)
        points.append({
            "at": o.closed_at.isoformat(),
            "equity": equity,
            "drawdown": equity - peak,  # ≤ 0
            "drawdown_pct": ((equity - peak) / peak) if peak > 0 else None,
        })
    return points


def pnl_by_day(outcomes: list[TradeOutcome], tz: str = "UTC") -> dict[str, dict]:
    """Daily P&L keyed by local calendar date in the user's timezone."""
    zone = ZoneInfo(tz)
    days: dict[date, dict] = {}
    for o in outcomes:
        d = o.closed_at.astimezone(zone).date()
        e = days.setdefault(d, {"pnl": 0.0, "trades": 0})
        e["pnl"] += o.pnl
        e["trades"] += 1
    return {d.isoformat(): v for d, v in sorted(days.items())}


def pnl_by_month(outcomes: list[TradeOutcome], tz: str = "UTC") -> dict[str, dict]:
    months: dict[str, dict] = {}
    for day, v in pnl_by_day(outcomes, tz).items():
        e = months.setdefault(day[:7], {"pnl": 0.0, "trades": 0})
        e["pnl"] += v["pnl"]
        e["trades"] += v["trades"]
    return months


def breakdown(outcomes: list[TradeOutcome], key) -> list[dict]:
    """Summaries grouped by key(outcome) -> str. Groups sorted by net P&L, descending."""
    groups: dict[str, list[TradeOutcome]] = {}
    for o in outcomes:
        groups.setdefault(key(o) or "Unassigned", []).append(o)
    rows = []
    for k, items in groups.items():
        s = summarize(items)
        rows.append({"key": k, "trades": s.trades, "net_pnl": s.net_pnl, "win_rate": s.win_rate,
                     "profit_factor": s.profit_factor, "expectancy": s.expectancy, "avg_r": s.avg_r,
                     "low_sample": s.low_sample})
    return sorted(rows, key=lambda r: r["net_pnl"], reverse=True)
