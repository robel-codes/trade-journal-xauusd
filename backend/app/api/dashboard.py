"""Overview figures. Every number is computed from stored rows; nothing is a placeholder."""

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.analytics.metrics import TradeOutcome, breakdown, equity_curve, pnl_by_day, pnl_by_month, summarize
from app.analytics.positions import Fill, compute_position
from app.api.settings import get_or_create
from app.api.strategies import library_stats
from app.deps import DB, CurrentUser
from app.models import AccountKind, JournalTrade, Strategy, TradingAccount

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

ACTUAL_KINDS = {AccountKind.live, AccountKind.demo, AccountKind.prop_eval}


@router.get("/overview")
def overview(
    user: CurrentUser, db: DB,
    account_id: uuid.UUID | None = None,
    strategy_id: uuid.UUID | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    source: Literal["all", "actual", "simulated"] = "all",
):
    settings = get_or_create(db, user)
    accounts = db.scalars(select(TradingAccount).where(TradingAccount.user_id == user.id)).all()
    if account_id:
        accounts = [a for a in accounts if a.id == account_id]
    if source == "actual":
        accounts = [a for a in accounts if a.kind in ACTUAL_KINDS]
    elif source == "simulated":
        accounts = [a for a in accounts if a.kind == AccountKind.simulation]
    acc_ids = {a.id for a in accounts}
    starting = float(sum(a.starting_balance for a in accounts))

    stmt = (select(JournalTrade).where(JournalTrade.user_id == user.id)
            .options(selectinload(JournalTrade.executions)))
    if strategy_id:
        stmt = stmt.where(JournalTrade.strategy_id == strategy_id)
    trades = [t for t in db.scalars(stmt) if t.account_id in acc_ids]
    names = dict(db.execute(select(Strategy.id, Strategy.name).where(Strategy.user_id == user.id)).all())

    outcomes: list[TradeOutcome] = []
    meta: dict[int, JournalTrade] = {}
    open_count = 0
    data_warnings: list[dict] = []
    for t in trades:
        fills = [Fill(e.kind.value, e.executed_at, e.price, e.quantity,
                      e.commission + e.spread_cost + e.slippage_cost + e.other_fees) for e in t.executions]
        res = compute_position(t.direction.value, fills, t.initial_stop, t.planned_risk_amount)
        for err in res.errors:
            data_warnings.append({"level": "warning", "message": f"Trade {t.id}: {err}"})
        if res.status != "closed":
            open_count += 1
            continue
        closed = res.closed_at if res.closed_at.tzinfo else res.closed_at.replace(tzinfo=UTC)
        if (start and closed < start) or (end and closed > end):
            continue
        o = TradeOutcome(closed, float(res.net_pnl), float(res.r_multiple) if res.r_multiple is not None else None,
                         t.direction.value)
        meta[id(o)] = t
        outcomes.append(o)

    summary = summarize(outcomes, starting)
    lib = library_stats(user, db)
    warnings = list(data_warnings)
    if not accounts:
        warnings.append({"level": "info", "message": "No trading account yet. Add one in Settings to start the journal."})
    if summary.trades and summary.low_sample:
        warnings.append({"level": "warning", "message": f"Only {summary.trades} closed trades. Treat rates and ratios as unreliable below 30."})
    warnings.append({"level": "info", "message": "No market data imported. Candle import and backtests arrive in Phase 3, so no backtest results exist yet."})
    if lib["total"]:
        unsupported = lib["by_classification"].get("unsupported", 0)
        manual = lib["by_classification"].get("manual", 0)
        if unsupported or manual:
            warnings.append({"level": "info", "message": f"{manual} strategies need manual conversion and {unsupported} cannot currently be executed. See the Strategy Library."})

    def key(attr):
        return lambda o: getattr(meta[id(o)], attr)

    recent = sorted(outcomes, key=lambda o: o.closed_at, reverse=True)[:10]
    return {
        "as_of": datetime.now(UTC).isoformat(),
        "timezone": settings.timezone,
        "filters": {"account_id": account_id, "strategy_id": strategy_id, "start": start, "end": end, "source": source},
        "accounts": [{"id": a.id, "name": a.name, "kind": a.kind.value, "currency": a.currency,
                      "starting_balance": float(a.starting_balance)} for a in accounts],
        "summary": summary.to_dict(),
        "open_positions": open_count,
        "equity_curve": equity_curve(outcomes, starting),
        "daily": pnl_by_day(outcomes, settings.timezone),
        "monthly": pnl_by_month(outcomes, settings.timezone),
        "by_strategy": breakdown(outcomes, lambda o: names.get(meta[id(o)].strategy_id, "No strategy")),
        "by_timeframe": breakdown(outcomes, key("timeframe")),
        "by_session": breakdown(outcomes, key("session")),
        "by_direction": breakdown(outcomes, lambda o: o.direction),
        "recent_trades": [{"id": meta[id(o)].id, "closed_at": o.closed_at.isoformat(), "direction": o.direction,
                           "pnl": o.pnl, "r": o.r, "setup": meta[id(o)].setup,
                           "strategy": names.get(meta[id(o)].strategy_id)} for o in recent],
        "library": lib,
        "recent_backtests": [],
        "warnings": warnings,
    }
