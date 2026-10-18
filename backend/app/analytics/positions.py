"""Realized P&L for a position built from individual fills.

A position is a sequence of fills: one entry, optional scale-ins, and any number of partial or full
exits. Cost basis is the volume-weighted average entry price (the convention MT4/MT5 and TradingView
use for a single net position). All money is in the instrument's quote currency.

    long  P&L per exit = (exit_price - avg_entry) * qty * contract_multiplier
    short P&L per exit = (avg_entry - exit_price) * qty * contract_multiplier
    net P&L            = gross P&L - all fees on all fills

R-multiple = net P&L / initial risk, where initial risk is the planned risk amount when recorded,
otherwise |first entry price - initial stop| * first entry quantity * multiplier. Fees are not added
to the risk denominator. If neither is available R is undefined (None), not zero.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

ZERO = Decimal(0)


@dataclass(frozen=True)
class Fill:
    kind: str  # entry | scale_in | scale_out | exit
    at: datetime
    price: Decimal
    quantity: Decimal
    fees: Decimal = ZERO


@dataclass
class PositionResult:
    status: str  # open | closed
    opened_at: datetime | None
    closed_at: datetime | None
    entry_quantity: Decimal  # total quantity bought (long) or sold (short) to open/add
    open_quantity: Decimal
    avg_entry_price: Decimal | None
    avg_exit_price: Decimal | None
    gross_pnl: Decimal
    fees: Decimal
    net_pnl: Decimal
    initial_risk: Decimal | None
    r_multiple: Decimal | None
    errors: list[str] = field(default_factory=list)


def compute_position(
    direction: str,
    fills: list[Fill],
    initial_stop: Decimal | None = None,
    planned_risk_amount: Decimal | None = None,
    multiplier: Decimal = Decimal(1),
) -> PositionResult:
    sign = Decimal(1) if direction == "long" else Decimal(-1)
    fills = sorted(fills, key=lambda f: f.at)
    errors: list[str] = []
    open_qty = ZERO
    cost = ZERO  # sum(price * qty) of the open quantity at avg cost
    entry_qty = ZERO
    exit_qty = ZERO
    exit_notional = ZERO
    gross = ZERO
    fees = ZERO
    opened_at = closed_at = None
    first_entry: Fill | None = None

    for f in fills:
        if f.quantity <= 0:
            errors.append(f"Fill at {f.at.isoformat()} has non-positive quantity.")
            continue
        fees += f.fees
        if f.kind in ("entry", "scale_in"):
            if first_entry is None:
                first_entry = f
                opened_at = f.at
            open_qty += f.quantity
            cost += f.price * f.quantity
            entry_qty += f.quantity
        else:
            if open_qty <= 0:
                errors.append(f"Exit at {f.at.isoformat()} has no open quantity to close.")
                continue
            qty = f.quantity
            if qty > open_qty:
                errors.append(f"Exit at {f.at.isoformat()} closes {qty} but only {open_qty} is open; capped.")
                qty = open_qty
            avg = cost / open_qty
            gross += (f.price - avg) * qty * sign * multiplier
            cost -= avg * qty
            open_qty -= qty
            exit_qty += qty
            exit_notional += f.price * qty
            if open_qty == 0:
                closed_at = f.at

    avg_entry = None
    if entry_qty > 0:
        total_entry_notional = sum((f.price * f.quantity for f in fills if f.kind in ("entry", "scale_in") and f.quantity > 0), ZERO)
        avg_entry = total_entry_notional / entry_qty
    risk = planned_risk_amount
    if risk is None and initial_stop is not None and first_entry is not None:
        risk = abs(first_entry.price - initial_stop) * first_entry.quantity * multiplier
    net = gross - fees
    status = "closed" if entry_qty > 0 and open_qty == 0 else "open"
    r = (net / risk) if (risk and risk > 0 and status == "closed") else None
    return PositionResult(
        status=status,
        opened_at=opened_at,
        closed_at=closed_at if status == "closed" else None,
        entry_quantity=entry_qty,
        open_quantity=open_qty,
        avg_entry_price=avg_entry,
        avg_exit_price=(exit_notional / exit_qty) if exit_qty > 0 else None,
        gross_pnl=gross,
        fees=fees,
        net_pnl=net,
        initial_risk=risk,
        r_multiple=r,
        errors=errors,
    )
