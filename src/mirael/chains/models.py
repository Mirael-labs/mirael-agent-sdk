"""
Typed Pydantic models for Hyperliquid on-chain data.

These models are used internally by ``HyperliquidReader`` to validate
and normalise raw API responses before returning serialised dicts to
callers (which expect the ``OnchainReader`` Protocol's ``dict[str, Any]``
return type).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PositionSummary(BaseModel):
    """A single open perpetual position."""

    asset: str
    size: float = Field(description="Positive = long, negative = short")
    entry_price: float
    mark_price: float
    unrealized_pnl: float
    liquidation_price: float | None = None
    margin_used: float
    leverage: float
    funding_since_open: float


class BalanceSummary(BaseModel):
    """Account-level margin summary."""

    account_value: float
    total_position_notional: float
    total_margin_used: float
    free_margin: float


class TradeRecord(BaseModel):
    """A single historical fill (executed trade)."""

    asset: str
    side: str = Field(description="'buy' or 'sell'")
    size: float
    price: float
    fee: float
    realized_pnl: float
    timestamp_ms: int = Field(description="Unix timestamp in milliseconds")


class FundingRateInfo(BaseModel):
    """Current funding rate snapshot for one perpetual asset."""

    asset: str
    rate: float = Field(description="Current 1h funding rate (decimal, e.g. 0.0001)")
    annualized: float = Field(description="rate x 24 x 365")
    open_interest: float
    mark_price: float
    oracle_price: float
    prev_day_price: float


class MarketInfo(BaseModel):
    """Market metadata for one perpetual asset."""

    asset: str
    mark_price: float
    oracle_price: float
    mid_price: float | None = None
    open_interest: float
    funding_rate: float
    max_leverage: int
    prev_day_price: float
    day_notional_volume: float
