"""
Condition-based alert engine for DeFi positions.

Monitors price, funding rates, liquidation distance, and health factor.
Fires callbacks when conditions are met.

Usage::

    engine = AlertEngine(chain_reader=HyperliquidReader())

    # Alert when BTC funding > 0.05%/hr
    engine.add(AlertCondition(
        asset="BTC",
        metric="funding_rate",
        operator="above",
        threshold=0.0005,
        user_id="discord_user_123",
        message_template="BTC funding is {value:.4%}/hr — your long is expensive",
    ))

    await engine.start(poll_interval=60)
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from mirael.logging import get_logger

_log = get_logger(__name__)

Operator = Literal["above", "below", "crosses_above", "crosses_below"]
Metric = Literal[
    "price",
    "funding_rate",
    "health_factor",
    "liquidation_distance_pct",
    "open_interest",
]


@dataclass
class AlertCondition:
    """A single monitoring condition."""

    asset: str
    metric: Metric
    operator: Operator
    threshold: float
    user_id: str
    message_template: str = "{asset} {metric} is {value:.4f} (threshold: {threshold:.4f})"
    wallet: str | None = None
    condition_id: str = field(default_factory=lambda: str(id(object())))
    active: bool = True


@dataclass
class AlertEvent:
    """A fired alert with context."""

    condition: AlertCondition
    asset: str
    metric: Metric
    value: float
    threshold: float
    message: str
    severity: Literal["info", "warning", "critical"]


class AlertEngine:
    """
    Polls on-chain data and fires alerts when conditions are met.

    Args:
        chain_reader: Any OnchainReader (HyperliquidReader, AaveV3Reader, etc.)
        on_alert: Async callback receiving AlertEvent when a condition fires.
        poll_interval: Seconds between checks (default: 60).
    """

    def __init__(
        self,
        chain_reader: Any,  # noqa: ANN401
        *,
        on_alert: Callable[[AlertEvent], Any] | None = None,
        poll_interval: int = 60,
    ) -> None:
        self._chain = chain_reader
        self._on_alert = on_alert
        self._interval = poll_interval
        self._conditions: list[AlertCondition] = []
        self._last_values: dict[str, float] = {}
        self._running = False

    def add(self, condition: AlertCondition) -> str:
        """Add a condition. Returns the condition_id."""
        self._conditions.append(condition)
        _log.info(
            "alert_condition_added",
            asset=condition.asset,
            metric=condition.metric,
            operator=condition.operator,
            threshold=condition.threshold,
        )
        return condition.condition_id

    def remove(self, condition_id: str) -> bool:
        """Remove a condition by ID. Returns True if found."""
        before = len(self._conditions)
        self._conditions = [c for c in self._conditions if c.condition_id != condition_id]
        return len(self._conditions) < before

    async def check_once(self) -> list[AlertEvent]:
        """Run one check cycle. Returns any fired alerts."""
        fired: list[AlertEvent] = []
        for condition in self._conditions:
            if not condition.active:
                continue
            try:
                value = await self._get_metric(condition)
                event = self._evaluate(condition, value)
                if event:
                    fired.append(event)
                    if self._on_alert:
                        await self._on_alert(event)
            except Exception as exc:
                _log.warning(
                    "alert_check_error",
                    condition_id=condition.condition_id,
                    error=str(exc),
                )
        return fired

    async def start(self, poll_interval: int | None = None) -> None:
        """Poll indefinitely. Call stop() to cancel."""
        interval = poll_interval or self._interval
        self._running = True
        _log.info("alert_engine_started", conditions=len(self._conditions), interval=interval)
        while self._running:
            await self.check_once()
            await asyncio.sleep(interval)

    def stop(self) -> None:
        self._running = False

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _get_metric(self, condition: AlertCondition) -> float:
        asset = condition.asset
        metric = condition.metric

        if metric == "price":
            info = await self._chain.get_market_info(asset)
            return float(info.get("mark_price", 0))

        if metric == "funding_rate":
            rate = await self._chain.get_funding_rate(asset)
            return float(rate.get("rate", 0))

        if metric in ("health_factor", "liquidation_distance_pct"):
            wallet = condition.wallet or ""
            if not wallet:
                return 999.0
            balance = await self._chain.get_user_balance(wallet)
            if metric == "health_factor":
                return float(balance.get("health_factor", 999))
            # liquidation_distance_pct: derived from positions
            positions = await self._chain.get_user_positions(wallet)
            for p in positions:
                if str(p.get("asset", p.get("coin", ""))).upper() == asset.upper():
                    mark = float(p.get("mark_price", 0))
                    liq = float(p.get("liquidation_price") or 0)
                    if mark > 0 and liq > 0:
                        return abs(mark - liq) / mark * 100
            return 100.0

        if metric == "open_interest":
            info = await self._chain.get_market_info(asset)
            return float(info.get("open_interest", 0))

        return 0.0

    def _evaluate(self, condition: AlertCondition, value: float) -> AlertEvent | None:
        key = f"{condition.condition_id}:{condition.asset}"
        prev = self._last_values.get(key)
        self._last_values[key] = value

        op = condition.operator
        thresh = condition.threshold
        triggered = False

        if op == "above":
            triggered = value > thresh
        elif op == "below":
            triggered = value < thresh
        elif op == "crosses_above":
            triggered = prev is not None and prev <= thresh < value
        elif op == "crosses_below":
            triggered = prev is not None and prev >= thresh > value

        if not triggered:
            return None

        severity: Literal["info", "warning", "critical"] = "info"
        if condition.metric == "health_factor" and value < 1.2:
            severity = "critical"
        elif condition.metric == "health_factor" and value < 1.5:
            severity = "warning"
        elif condition.metric == "liquidation_distance_pct" and value < 10:
            severity = "critical"
        elif condition.metric == "funding_rate" and abs(value) >= 0.001:
            severity = "warning"

        message = condition.message_template.format(
            asset=condition.asset,
            metric=condition.metric,
            value=value,
            threshold=thresh,
        )

        return AlertEvent(
            condition=condition,
            asset=condition.asset,
            metric=condition.metric,
            value=value,
            threshold=thresh,
            message=message,
            severity=severity,
        )
