import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal
from zoneinfo import available_timezones

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import AccountKind


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginIn(BaseModel):
    email: str = Field(max_length=320)
    password: str = Field(min_length=1, max_length=256)


class UserOut(ORM):
    id: uuid.UUID
    email: str
    display_name: str


class SessionWindow(BaseModel):
    """A named trading session, defined in its own reference timezone so DST follows tz rules."""

    key: str = Field(pattern=r"^[a-z0-9_]{1,32}$")
    label: str = Field(max_length=64)
    timezone: str
    start: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str) -> str:
        if v not in available_timezones():
            raise ValueError(f"Unknown timezone {v}")
        return v


class SettingsOut(ORM):
    timezone: str
    base_currency: str
    theme: Literal["dark", "light"]
    default_instrument_symbol: str
    sessions: list[SessionWindow]


class SettingsIn(BaseModel):
    timezone: str | None = None
    base_currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    theme: Literal["dark", "light"] | None = None
    sessions: list[SessionWindow] | None = None

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str | None) -> str | None:
        if v is not None and v not in available_timezones():
            raise ValueError(f"Unknown timezone {v}")
        return v


class AccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: AccountKind
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    starting_balance: Decimal = Field(gt=0, max_digits=20, decimal_places=2)
    risk_per_trade_pct: Decimal = Field(default=Decimal("1.0"), gt=0, le=100)
    daily_loss_limit_pct: Decimal | None = Field(default=None, gt=0, le=100)
    max_drawdown_limit_pct: Decimal | None = Field(default=None, gt=0, le=100)
    max_open_positions: int | None = Field(default=None, ge=1, le=1000)
    rules: dict = Field(default_factory=dict)


class AccountOut(ORM):
    id: uuid.UUID
    name: str
    kind: AccountKind
    currency: str
    starting_balance: Decimal
    risk_per_trade_pct: Decimal
    daily_loss_limit_pct: Decimal | None
    max_drawdown_limit_pct: Decimal | None
    max_open_positions: int | None
    rules: dict
    archived: bool
    created_at: datetime


class StrategyPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=20000)
    hypothesis: str | None = Field(default=None, max_length=20000)
    entry_conditions: str | None = Field(default=None, max_length=20000)
    exit_conditions: str | None = Field(default=None, max_length=20000)
    stop_methodology: str | None = Field(default=None, max_length=20000)
    target_methodology: str | None = Field(default=None, max_length=20000)
    supported_timeframes: list[Literal["1m", "5m", "15m", "30m", "1h", "4h", "1d"]] | None = None
    session_restrictions: str | None = Field(default=None, max_length=2000)
    tags: list[str] | None = Field(default=None, max_length=50)
    category: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=50000)
    known_limitations: str | None = Field(default=None, max_length=20000)
    archived: bool | None = None

    @field_validator("tags")
    @classmethod
    def _tags(cls, v):
        if v is None:
            return v
        out = []
        for t in v:
            t = t.strip()[:48]
            if t and t.lower() not in (x.lower() for x in out):
                out.append(t)
        return out


class NewVersionIn(BaseModel):
    source: str = Field(min_length=1, max_length=1_000_000)
    change_note: str = Field(default="", max_length=2000)


class CloneIn(BaseModel):
    name: str | None = Field(default=None, max_length=200)

