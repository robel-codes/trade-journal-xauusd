"""ORM models. All timestamps are timezone-aware UTC; rendering in the user's zone is a UI concern."""

import enum
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> uuid.UUID:
    return uuid.uuid4()


Money = Numeric(20, 8)
Price = Numeric(20, 8)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


def _enum(cls: type[enum.Enum], name: str) -> Enum:
    return Enum(cls, name=name, native_enum=False, length=32, values_callable=lambda e: [m.value for m in e])


# ---------------------------------------------------------------- identity & settings


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    settings: Mapped["ApplicationSettings"] = relationship(back_populates="user", uselist=False)


class ApplicationSettings(TimestampMixin, Base):
    __tablename__ = "application_settings"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    base_currency: Mapped[str] = mapped_column(String(3), default="USD")
    theme: Mapped[str] = mapped_column(String(8), default="dark")
    default_instrument_symbol: Mapped[str] = mapped_column(String(32), default="XAUUSD")
    # Configurable session windows, in their own reference timezones so DST is handled by tz rules.
    sessions: Mapped[list] = mapped_column(JSON, default=list)

    user: Mapped[User] = relationship(back_populates="settings")


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(64))
    target: Mapped[str] = mapped_column(String(255), default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    ip: Mapped[str] = mapped_column(String(64), default="")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


# ---------------------------------------------------------------- instruments & accounts


class Instrument(TimestampMixin, Base):
    __tablename__ = "instruments"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    symbol: Mapped[str] = mapped_column(String(32), unique=True)
    description: Mapped[str] = mapped_column(String(255), default="")
    base_currency: Mapped[str] = mapped_column(String(8))
    quote_currency: Mapped[str] = mapped_column(String(8))
    tick_size: Mapped[Decimal] = mapped_column(Price)
    price_precision: Mapped[int] = mapped_column(Integer)


class BrokerProfile(TimestampMixin, Base):
    """Broker-specific contract terms. XAUUSD specs differ between brokers, so nothing is global."""

    __tablename__ = "broker_profiles"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    instrument_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("instruments.id"))
    name: Mapped[str] = mapped_column(String(120))
    broker_symbol: Mapped[str] = mapped_column(String(32))
    contract_size: Mapped[Decimal] = mapped_column(Price)  # units (oz) per 1.0 lot
    min_lot: Mapped[Decimal] = mapped_column(Price)
    lot_step: Mapped[Decimal] = mapped_column(Price)
    typical_spread: Mapped[Decimal] = mapped_column(Price)  # in price units
    commission_per_lot_round_turn: Mapped[Decimal] = mapped_column(Money, default=Decimal(0))
    max_leverage: Mapped[Decimal | None] = mapped_column(Price, nullable=True)
    server_timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    notes: Mapped[str] = mapped_column(Text, default="")


class AccountKind(enum.StrEnum):
    demo = "demo"
    live = "live"
    simulation = "simulation"
    prop_eval = "prop_eval"


class TradingAccount(TimestampMixin, Base):
    __tablename__ = "trading_accounts"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[AccountKind] = mapped_column(_enum(AccountKind, "account_kind"))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    starting_balance: Mapped[Decimal] = mapped_column(Money)
    risk_per_trade_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("1.0"))
    daily_loss_limit_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    max_drawdown_limit_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    max_open_positions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    broker_profile_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("broker_profiles.id"), nullable=True)
    # Prop-style rules are data, never hardcoded firm rules: {"trailing_drawdown": true, "reset_tz": "..."}
    rules: Mapped[dict] = mapped_column(JSON, default=dict)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


# ---------------------------------------------------------------- strategies


class ScriptKind(enum.StrEnum):
    strategy = "strategy"
    indicator = "indicator"
    library = "library"
    unknown = "unknown"


class Compatibility(enum.StrEnum):
    validated = "validated"  # native adapter exists and parity tests pass
    partial = "partial"
    manual = "manual"  # requires manual conversion
    unsupported = "unsupported"  # cannot currently be executed reliably


class Strategy(TimestampMixin, Base):
    __tablename__ = "strategies"
    __table_args__ = (UniqueConstraint("user_id", "slug"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    slug: Mapped[str] = mapped_column(String(160))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    hypothesis: Mapped[str] = mapped_column(Text, default="")
    entry_conditions: Mapped[str] = mapped_column(Text, default="")
    exit_conditions: Mapped[str] = mapped_column(Text, default="")
    stop_methodology: Mapped[str] = mapped_column(Text, default="")
    target_methodology: Mapped[str] = mapped_column(Text, default="")
    supported_timeframes: Mapped[list] = mapped_column(JSON, default=list)
    session_restrictions: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    category: Mapped[str] = mapped_column(String(64), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    known_limitations: Mapped[str] = mapped_column(Text, default="")
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    cloned_from_strategy_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("strategies.id"), nullable=True)

    versions: Mapped[list["StrategyVersion"]] = relationship(
        back_populates="strategy", order_by="StrategyVersion.version_number", cascade="all, delete-orphan"
    )


class StrategyVersion(Base):
    """Immutable snapshot of a script. `source` is stored exactly as uploaded."""

    __tablename__ = "strategy_versions"
    __table_args__ = (UniqueConstraint("strategy_id", "version_number"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    strategy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("strategies.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(Text)
    source_sha256: Mapped[str] = mapped_column(String(64), index=True)
    normalized_sha256: Mapped[str] = mapped_column(String(64), index=True)
    source_filename: Mapped[str] = mapped_column(String(255), default="")
    source_bytes: Mapped[int] = mapped_column(Integer)
    pine_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    script_kind: Mapped[ScriptKind] = mapped_column(_enum(ScriptKind, "script_kind"))
    declared_title: Mapped[str] = mapped_column(String(255), default="")
    declaration: Mapped[dict] = mapped_column(JSON, default=dict)
    change_note: Mapped[str] = mapped_column(Text, default="")
    cloned_from_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("strategy_versions.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    strategy: Mapped[Strategy] = relationship(back_populates="versions")
    inputs: Mapped[list["StrategyInput"]] = relationship(
        back_populates="version", order_by="StrategyInput.position", cascade="all, delete-orphan"
    )
    report: Mapped["StrategyCompatibilityReport"] = relationship(
        back_populates="version", uselist=False, cascade="all, delete-orphan"
    )


class StrategyInput(Base):
    __tablename__ = "strategy_inputs"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("strategy_versions.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    variable: Mapped[str] = mapped_column(String(128), default="")
    input_type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(255), default="")
    default_raw: Mapped[str] = mapped_column(Text, default="")
    default_value: Mapped[dict] = mapped_column(JSON, default=dict)  # {"value": ...} when literal
    options: Mapped[dict] = mapped_column(JSON, default=dict)  # minval, maxval, step, options, group, tooltip
    line: Mapped[int] = mapped_column(Integer)

    version: Mapped[StrategyVersion] = relationship(back_populates="inputs")


class StrategyCompatibilityReport(Base):
    __tablename__ = "strategy_compatibility_reports"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("strategy_versions.id", ondelete="CASCADE"), unique=True
    )
    analyzer_version: Mapped[str] = mapped_column(String(32))
    classification: Mapped[Compatibility] = mapped_column(_enum(Compatibility, "compatibility"))
    summary: Mapped[str] = mapped_column(Text)
    findings: Mapped[list] = mapped_column(JSON, default=list)
    function_usage: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    version: Mapped[StrategyVersion] = relationship(back_populates="report")


# ---------------------------------------------------------------- journal


class Direction(enum.StrEnum):
    long = "long"
    short = "short"


class ExecutionKind(enum.StrEnum):
    entry = "entry"
    scale_in = "scale_in"
    scale_out = "scale_out"
    exit = "exit"


class JournalTrade(TimestampMixin, Base):
    """A position as the trader experienced it. Fills live in TradeExecution; P&L is derived from them."""

    __tablename__ = "journal_trades"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trading_accounts.id"), index=True)
    instrument_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("instruments.id"))
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("strategies.id"), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)  # broker ticket, for import dedupe
    direction: Mapped[Direction] = mapped_column(_enum(Direction, "direction"))
    timeframe: Mapped[str] = mapped_column(String(8), default="")
    session: Mapped[str] = mapped_column(String(32), default="")
    setup: Mapped[str] = mapped_column(String(120), default="")
    initial_stop: Mapped[Decimal | None] = mapped_column(Price, nullable=True)
    initial_target: Mapped[Decimal | None] = mapped_column(Price, nullable=True)
    planned_risk_amount: Mapped[Decimal | None] = mapped_column(Money, nullable=True)
    planned_risk_pct: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    stop_adjustments: Mapped[list] = mapped_column(JSON, default=list)  # [{at, price, reason}]
    pre_trade_reasoning: Mapped[str] = mapped_column(Text, default="")
    post_trade_review: Mapped[str] = mapped_column(Text, default="")
    emotional_state: Mapped[str] = mapped_column(String(64), default="")
    discipline_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5
    rule_following_score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-100
    mistakes: Mapped[list] = mapped_column(JSON, default=list)
    lessons: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")

    executions: Mapped[list["TradeExecution"]] = relationship(
        back_populates="trade", order_by="TradeExecution.executed_at", cascade="all, delete-orphan"
    )
    tags: Mapped[list["TradeTag"]] = relationship(secondary="journal_trade_tags")


class TradeExecution(Base):
    __tablename__ = "trade_executions"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    trade_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("journal_trades.id", ondelete="CASCADE"), index=True)
    kind: Mapped[ExecutionKind] = mapped_column(_enum(ExecutionKind, "execution_kind"))
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    price: Mapped[Decimal] = mapped_column(Price)
    quantity: Mapped[Decimal] = mapped_column(Price)  # instrument units (e.g. troy oz), always positive
    commission: Mapped[Decimal] = mapped_column(Money, default=Decimal(0))
    spread_cost: Mapped[Decimal] = mapped_column(Money, default=Decimal(0))
    slippage_cost: Mapped[Decimal] = mapped_column(Money, default=Decimal(0))
    other_fees: Mapped[Decimal] = mapped_column(Money, default=Decimal(0))

    trade: Mapped[JournalTrade] = relationship(back_populates="executions")


class TradeTag(Base):
    __tablename__ = "trade_tags"
    __table_args__ = (UniqueConstraint("user_id", "name"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(64))


class JournalTradeTag(Base):
    __tablename__ = "journal_trade_tags"
    trade_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("journal_trades.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trade_tags.id", ondelete="CASCADE"), primary_key=True)
