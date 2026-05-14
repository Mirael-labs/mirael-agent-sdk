"""
Proactive health factor monitor.

Polls on-chain positions on a configurable interval and sends
DM alerts via Discord or Telegram when health metrics cross thresholds.

Usage::

    monitor = HealthMonitor(
        chain_reader=HyperliquidReader(),
        discord_adapter=adapter,
        check_interval=60,
    )
    await monitor.start(wallet="0x...", discord_user_id="123456789")
"""

from __future__ import annotations

import asyncio
from typing import Any

from mirael.logging import get_logger

_log = get_logger(__name__)

# Alert thresholds
HEALTH_CRITICAL = 1.2   # liquidation imminent
HEALTH_WARNING = 1.5    # needs attention
HEALTH_WATCH = 2.0      # worth monitoring


class HealthAlert:
    """A triggered health alert."""

    def __init__(
        self,
        wallet: str,
        asset: str,
        health_factor: float,
        liq_distance_pct: float,
        message: str,
        severity: str,
    ) -> None:
        self.wallet = wallet
        self.asset = asset
        self.health_factor = health_factor
        self.liq_distance_pct = liq_distance_pct
        self.message = message
        self.severity = severity  # "watch" | "warning" | "critical"


class HealthMonitor:
    """
    Polls on-chain positions and fires alerts when health drops.

    Args:
        chain_reader: Any OnchainReader (HyperliquidReader or AaveV3Reader).
        check_interval: Seconds between health checks (default: 60).
        on_alert: Async callback receiving a HealthAlert. Used to send DMs.
    """

    def __init__(
        self,
        chain_reader: Any,  # noqa: ANN401
        *,
        check_interval: int = 60,
        on_alert: Any = None,  # noqa: ANN401
    ) -> None:
        self._chain = chain_reader
        self._interval = check_interval
        self._on_alert = on_alert
        self._running = False
        self._alerted: dict[str, str] = {}  # asset -> last severity (dedup)

    async def start(self, wallet: str) -> None:
        """Poll indefinitely until stop() is called."""
        self._running = True
        _log.info("health_monitor_started", wallet=wallet[:10], interval=self._interval)
        while self._running:
            try:
                await self._check(wallet)
            except Exception as exc:
                _log.warning("health_monitor_error", error=str(exc))
            await asyncio.sleep(self._interval)

    def stop(self) -> None:
        """Stop the polling loop."""
        self._running = False

    async def _check(self, wallet: str) -> None:
        balance = await self._chain.get_user_balance(wallet)
        positions = await self._chain.get_user_positions(wallet)

        # For Aave: health_factor is in balance dict
        global_health = float(balance.get("health_factor", 999))
        if global_health < HEALTH_CRITICAL:
            alert = HealthAlert(
                wallet=wallet,
                asset="ACCOUNT",
                health_factor=global_health,
                liq_distance_pct=0.0,
                message=(
                    f"CRITICAL: Health factor {global_health:.2f} — "
                    f"liquidation imminent! Reduce debt or add collateral NOW."
                ),
                severity="critical",
            )
            await self._fire(alert)
        elif global_health < HEALTH_WARNING:
            alert = HealthAlert(
                wallet=wallet,
                asset="ACCOUNT",
                health_factor=global_health,
                liq_distance_pct=0.0,
                message=(
                    f"WARNING: Health factor {global_health:.2f} — "
                    f"consider reducing exposure."
                ),
                severity="warning",
            )
            await self._fire(alert)

        # Per-position checks (Hyperliquid)
        for pos in positions:
            asset = str(pos.get("asset", pos.get("coin", "?")))
            liq_px = pos.get("liquidation_price") or pos.get("liquidationPx")
            mark_px = pos.get("mark_price") or pos.get("markPx")
            if liq_px and mark_px and float(mark_px) > 0:
                dist = abs(float(mark_px) - float(liq_px)) / float(mark_px) * 100
                if dist < 10:
                    await self._fire(HealthAlert(
                        wallet=wallet,
                        asset=asset,
                        health_factor=0.0,
                        liq_distance_pct=dist,
                        message=(
                            f"{asset}: {dist:.1f}% from liquidation! "
                            f"Mark ${float(mark_px):,.2f} -> Liq ${float(liq_px):,.2f}"
                        ),
                        severity="critical",
                    ))
                elif dist < 20:
                    await self._fire(HealthAlert(
                        wallet=wallet,
                        asset=asset,
                        health_factor=0.0,
                        liq_distance_pct=dist,
                        message=(
                            f"{asset}: {dist:.1f}% from liquidation. "
                            f"Mark ${float(mark_px):,.2f} -> Liq ${float(liq_px):,.2f}"
                        ),
                        severity="warning",
                    ))

    async def _fire(self, alert: HealthAlert) -> None:
        """Deduplicate and fire alert callback."""
        key = f"{alert.wallet}:{alert.asset}"
        last = self._alerted.get(key)
        # Only alert if severity increased or not alerted before
        severity_rank = {"watch": 1, "warning": 2, "critical": 3}
        if last and severity_rank.get(last, 0) >= severity_rank.get(alert.severity, 0):
            return
        self._alerted[key] = alert.severity
        _log.info(
            "health_alert_fired",
            asset=alert.asset,
            severity=alert.severity,
            hf=alert.health_factor,
        )
        if self._on_alert:
            try:
                await self._on_alert(alert)
            except Exception as exc:
                _log.warning("health_alert_callback_error", error=str(exc))
