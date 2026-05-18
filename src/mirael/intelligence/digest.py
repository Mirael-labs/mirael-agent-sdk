"""
Daily and weekly portfolio digest generator.

Generates AI-powered summaries of a user's DeFi portfolio status
and sends them to Discord/Telegram channels on a schedule.

Usage::

    digest = PortfolioDigest(
        chain_reader=HyperliquidReader(),
        llm=AnthropicLLM(api_key="..."),
    )
    report = await digest.generate(wallet="0x...")
    print(report.markdown)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from mirael.logging import get_logger

_log = get_logger(__name__)


@dataclass
class DigestReport:
    """A generated portfolio digest."""

    wallet: str
    generated_at: float
    period: str          # "daily" | "weekly"
    markdown: str        # formatted for Discord/Telegram
    positions_count: int
    total_pnl: float
    max_risk_asset: str
    min_health_factor: float
    total_funding_cost_24h: float
    ai_commentary: str


class PortfolioDigest:
    """
    Generates periodic portfolio reports with AI commentary.

    Args:
        chain_reader: OnchainReader for fetching positions.
        llm: AnthropicLLM for AI commentary.
        period: "daily" or "weekly".
    """

    def __init__(
        self,
        chain_reader: Any,  # noqa: ANN401
        llm: Any,  # noqa: ANN401
        *,
        period: str = "daily",
    ) -> None:
        self._chain = chain_reader
        self._llm = llm
        self._period = period

    async def generate(self, wallet: str) -> DigestReport:
        """Generate a full portfolio digest for a wallet."""
        try:
            balance = await self._chain.get_user_balance(wallet)
            positions = await self._chain.get_user_positions(wallet)
            await self._chain.get_funding_rate("BTC")  # sample — warms cache
        except Exception as exc:
            _log.warning("digest_fetch_error", wallet=wallet[:10], error=str(exc))
            balance = {}
            positions = []

        # Compute stats
        total_pnl = sum((float(p.get("unrealized_pnl", 0)) for p in positions), 0.0)
        health = float(balance.get("health_factor", 999))
        min_health = health

        # Find riskiest position
        max_risk = "none"
        if positions:
            riskiest = min(
                positions,
                key=lambda p: float(p.get("health_factor", 999))
                if "health_factor" in p
                else abs(float(p.get("liquidation_price") or 0) - float(p.get("mark_price") or 1)),
            )
            max_risk = str(riskiest.get("asset", riskiest.get("coin", "unknown")))

        # Estimate funding cost (simplified)
        funding_cost_24h = 0.0
        for p in positions:
            size = abs(float(p.get("size", 0))) * float(p.get("mark_price", 0))
            rate = abs(float(p.get("funding_since_open", 0))) * 0.01
            funding_cost_24h += size * rate

        # Build markdown report
        period_label = "Daily" if self._period == "daily" else "Weekly"
        wallet_short = f"{wallet[:8]}...{wallet[-4:]}"
        lines = [
            f"## {period_label} Portfolio Digest — {wallet_short}",
            f"*Generated: {time.strftime('%Y-%m-%d %H:%M UTC')}*",
            "",
            "### Summary",
            f"- Open positions: **{len(positions)}**",
            f"- Unrealized PnL: **${total_pnl:+,.2f}**",
            f"- Account value: **${float(balance.get('account_value', 0)):,.2f}**",
            f"- Health factor: **{min_health:.2f}**",
            f"- Est. funding cost (24h): **${funding_cost_24h:.2f}**",
        ]

        if positions:
            lines += ["", "### Positions"]
            for p in positions:
                asset = str(p.get("asset", p.get("coin", "?")))
                size = float(p.get("size", 0))
                pnl = float(p.get("unrealized_pnl", 0))
                side = "L" if size > 0 else "S"
                lines.append(f"- **{asset}** {side} | PnL: ${pnl:+,.2f}")

        if max_risk != "none":
            lines += ["", f"⚠️ **Highest risk:** {max_risk}"]

        # AI commentary
        ai_text = await self._generate_commentary(balance, positions, total_pnl)
        lines += ["", "### AI Commentary", ai_text]

        return DigestReport(
            wallet=wallet,
            generated_at=time.time(),
            period=self._period,
            markdown="\n".join(lines),
            positions_count=len(positions),
            total_pnl=total_pnl,
            max_risk_asset=max_risk,
            min_health_factor=min_health,
            total_funding_cost_24h=funding_cost_24h,
            ai_commentary=ai_text,
        )

    async def _generate_commentary(
        self,
        balance: dict[str, Any],
        positions: list[dict[str, Any]],
        total_pnl: float,
    ) -> str:
        from mirael.llm.models import ChatMessage

        if not positions:
            return "No open positions. Portfolio is in cash."

        summary = (
            f"Portfolio: {len(positions)} positions, "
            f"total PnL ${total_pnl:+,.2f}, "
            f"health factor {float(balance.get('health_factor', 999)):.2f}. "
            f"Assets: {', '.join(str(p.get('asset', p.get('coin', '?'))) for p in positions[:5])}."
        )
        prompt = (
            f"{summary}\n\n"
            "In 2-3 sentences, give a portfolio assessment: "
            "is the risk level appropriate? Any specific concerns? "
            "What should the trader watch today? Be direct and specific."
        )
        try:
            response = await self._llm.chat(
                [ChatMessage(role="user", content=prompt)],
                max_tokens=150,
            )
            return str(response.text)
        except Exception as exc:
            _log.warning("digest_commentary_failed", error=str(exc))
            return "Commentary unavailable."
