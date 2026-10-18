# Metric definitions

All metrics are computed from stored rows by `backend/app/analytics`. Each one is labelled with its
source in the UI: **actual** (live, demo, prop-evaluation accounts), **simulated** (simulation accounts),
or **backtest** (Phase 3+). They are never mixed silently.

## Position P&L (`analytics/positions.py`)

A journal trade is a list of fills. Cost basis is the volume-weighted average entry price.

| Quantity | Formula |
|---|---|
| Realized P&L per exit (long) | `(exit − avg_entry) × qty × multiplier` |
| Realized P&L per exit (short) | `(avg_entry − exit) × qty × multiplier` |
| Net P&L | `Σ realized − Σ fees` (commission + spread + slippage + other, on every fill) |
| Initial risk | planned risk amount if recorded, else `|first entry − initial stop| × first entry qty × multiplier` |
| R-multiple | `net P&L ÷ initial risk`; undefined when there is no stop or planned risk, or the trade is open |

Limitations: initial risk ignores fees and scale-ins (it is the risk *planned at entry*). Exits larger
than the open quantity are capped and reported as data errors, not silently absorbed.

## Summary metrics (`analytics/metrics.py`)

| Metric | Formula | Limitations |
|---|---|---|
| Win rate | `wins ÷ trades`, win = net P&L > 0 | Says nothing about payoff size. A 90% win rate can lose money (tested). |
| Profit factor | `gross profit ÷ |gross loss|` | Undefined (shown "—") with no losses, never "infinite". Sensitive to one large trade. |
| Expectancy | `net P&L ÷ trades` | Mean, so outliers dominate small samples. |
| Payoff ratio | `avg win ÷ |avg loss|` | Read together with win rate. |
| Avg / median R | over trades with a defined R | Median is more robust to a single outlier. |
| Equity | `starting balance + cumulative net P&L`, ordered by close time | Closed trades only; open P&L excluded. |
| Max drawdown | `max(peak − equity)`, peak includes the starting balance | Trade-close resolution, so intratrade drawdown is not seen. |
| Max drawdown % | `max((peak − equity) ÷ peak)` | Undefined with no starting balance. |
| Current drawdown | `final peak − final equity` | |
| Total return | `net P&L ÷ starting balance` | Simple, not compounded or annualized. |

**Sample size:** any group with fewer than 30 closed trades is flagged `low_sample` and shown with a
warning. 30 is a convention, not a guarantee; confidence intervals arrive with the robustness tools.

**Not computed yet (by design):** Sharpe, Sortino, Calmar and annualized return need a returns series
on a fixed calendar grid and enough history. They arrive with the backtest analytics in Phase 3 and
are withheld for short samples rather than annualized from a few weeks of data.

**Daily and monthly P&L** bucket each trade by its close time converted to the user's timezone, so a
trade closing at 23:30 UTC belongs to the next day for a Tokyo-based user (tested).
