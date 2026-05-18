"""
On-chain whale movement tracker with AI-powered context.

Detects large deposits, withdrawals, and position changes.
Uses Claude to generate market interpretation for each event.

Usage::

    tracker = WhaleTracker(
        chain_reader=HyperliquidReader(),
        llm=AnthropicLLM(api_key="..."),
        min_size_usd=500_000,
    )
    await tracker.start(on_alert=lambda alert: print(alert.summary))
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from mirael.logging import get_logger

_log = get_logger(__name__)


@dataclass
class WhaleAlert:
    """A detected large on-chain movement with AI context."""

    wallet: str
    asset: str
    action: str          # "opened_long", "opened_short", "closed", "deposited", "withdrew"
    size_usd: float
    protocol: str        # "Hyperliquid", "Aave", "GMX"
    timestamp: float = field(default_factory=time.time)
    raw_position: dict[str, Any] = field(default_factory=dict)
    ai_summary: str = ""  # populated by Claude if llm is provided
    historical_context: str = ""


class WhaleTracker:
    """
    Polls on-chain positions and detects large wallet movements.

    Optionally uses Claude to generate market context for each alert.

    Args:
        chain_reader: Any OnchainReader to poll positions from.
        llm: Optional AnthropicLLM for AI-powered summaries.
        min_size_usd: Minimum position size to consider a whale (default $500K).
        poll_interval: Seconds between position scans (default: 120).
        wallets_to_track: Specific wallets to monitor (empty = protocol-wide scan).
    """

    def __init__(
        self,
        chain_reader: Any,  # noqa: ANN401
        *,
        llm: Any | None = None,  # noqa: ANN401
        min_size_usd: float = 500_000,
        poll_interval: int = 120,
        wallets_to_track: list[str] | None = None,
    ) -> None:
        self._chain = chain_reader
        self._llm = llm
        self._min_size = min_size_usd
        self._interval = poll_interval
        self._wallets = wallets_to_track or []
        self._known_positions: dict[str, dict[str, Any]] = {}
        self._running = False

    async def start(
        self,
        on_alert: Callable[[WhaleAlert], Any] | None = None,
    ) -> None:
        """Poll indefinitely. Fires on_alert when whale movement detected."""
        self._running = True
        _log.info("whale_tracker_started", min_size=self._min_size)
        while self._running:
            try:
                alerts = await self._scan()
                for alert in alerts:
                    _log.info(
                        "whale_alert",
                        wallet=alert.wallet[:10],
                        asset=alert.asset,
                        action=alert.action,
                        size_usd=alert.size_usd,
                    )
                    if on_alert:
                        await on_alert(alert)
            except Exception as exc:
                _log.warning("whale_scan_error", error=str(exc))
            await asyncio.sleep(self._interval)

    def stop(self) -> None:
        self._running = False

    async def scan_wallet(self, wallet: str) -> list[WhaleAlert]:
        """Scan a single wallet for large positions. Returns any whale alerts."""
        return await self._scan_single(wallet)

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _scan(self) -> list[WhaleAlert]:
        alerts: list[WhaleAlert] = []
        for wallet in self._wallets:
            wallet_alerts = await self._scan_single(wallet)
            alerts.extend(wallet_alerts)
        return alerts

    async def _scan_single(self, wallet: str) -> list[WhaleAlert]:
        alerts: list[WhaleAlert] = []
        try:
            positions = await self._chain.get_user_positions(wallet)
        except Exception:
            return []

        prev = self._known_positions.get(wallet, {})
        current: dict[str, Any] = {}

        for pos in positions:
            asset = str(pos.get("asset", pos.get("coin", "?")))
            raw_size = abs(float(pos.get("size", 0))) * float(pos.get("mark_price", 0))
            size = float(pos.get("size_usd", raw_size))
            current[asset] = pos

            if size < self._min_size:
                continue

            prev_pos = prev.get(asset)
            if prev_pos is None:
                # New large position
                action = "opened_long" if float(pos.get("size", 1)) > 0 else "opened_short"
                alert = WhaleAlert(
                    wallet=wallet,
                    asset=asset,
                    action=action,
                    size_usd=size,
                    protocol=str(pos.get("protocol", "Hyperliquid")),
                    raw_position=pos,
                )
                if self._llm:
                    alert.ai_summary = await self._generate_summary(alert)
                alerts.append(alert)
            else:
                prev_size = float(prev_pos.get("size_usd", 0))
                delta = abs(size - prev_size)
                if delta > self._min_size * 0.2:  # >20% change
                    action = "increased" if size > prev_size else "reduced"
                    alert = WhaleAlert(
                        wallet=wallet,
                        asset=asset,
                        action=action,
                        size_usd=size,
                        protocol=str(pos.get("protocol", "Hyperliquid")),
                        raw_position=pos,
                    )
                    if self._llm:
                        alert.ai_summary = await self._generate_summary(alert)
                    alerts.append(alert)

        # Detect closed positions
        for asset, prev_pos in prev.items():
            if asset not in current:
                prev_size = float(prev_pos.get("size_usd", 0))
                if prev_size >= self._min_size:
                    alert = WhaleAlert(
                        wallet=wallet,
                        asset=asset,
                        action="closed",
                        size_usd=prev_size,
                        protocol=str(prev_pos.get("protocol", "Hyperliquid")),
                        raw_position=prev_pos,
                    )
                    if self._llm:
                        alert.ai_summary = await self._generate_summary(alert)
                    alerts.append(alert)

        self._known_positions[wallet] = current
        return alerts

    async def _generate_summary(self, alert: WhaleAlert) -> str:
        """Use Claude to generate a one-paragraph market context for this alert."""
        from mirael.llm.models import ChatMessage

        prompt = (
            f"A whale wallet {alert.wallet[:8]}... just {alert.action} a "
            f"${alert.size_usd:,.0f} {alert.asset} position on {alert.protocol}. "
            f"In 2-3 sentences, provide market context: what this movement might signal "
            f"about market sentiment, and what it means for smaller traders. "
            f"Be factual, not financial advice. Use specific numbers if available."
        )
        try:
            response = await self._llm.chat(
                [ChatMessage(role="user", content=prompt)],
                max_tokens=150,
            )
            return response.text
        except Exception as exc:
            _log.warning("whale_ai_summary_failed", error=str(exc))
            return ""
