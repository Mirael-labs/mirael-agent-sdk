"""
Discord bot channel adapter.

Connects the Mirael Agent to a Discord server via slash commands.
Uses ``discord.py`` (``pip install 'mirael-agent-sdk[discord]'``).

Commands:
  /ask [question]         — ask the AI agent anything
  /positions [wallet]     — show on-chain positions for a wallet
  /health [wallet]        — show risk / health factor summary
  /help                   — list available commands

Setup:
  1. Create a Discord Application at https://discord.com/developers/applications
  2. Add a Bot, copy the token → set MIRAEL_DISCORD_BOT_TOKEN in .env
  3. Invite the bot: OAuth2 → URL Generator → scopes: bot + applications.commands
  4. Run: uv run python examples/discord_demo/bot.py
"""

from __future__ import annotations

import asyncio
from typing import Any

from mirael.agent.base import Agent
from mirael.exceptions import MiraelError
from mirael.logging import get_logger

_log = get_logger(__name__)

_MAX_DISCORD_LEN = 1900  # Discord limit is 2000; leave buffer for formatting


def _chunk_text(text: str, max_len: int = _MAX_DISCORD_LEN) -> list[str]:
    """Split a long response into Discord-sized chunks."""
    if len(text) <= max_len:
        return [text]
    chunks: list[str] = []
    while text:
        chunks.append(text[:max_len])
        text = text[max_len:]
    return chunks


class DiscordChannelAdapter:
    """
    Discord bot adapter wrapping the Mirael Agent.

    Args:
        token: Discord bot token (from discord.com/developers).
        agent: Configured ``Agent`` instance.
        guild_id: Optional server ID to restrict slash command registration.
                  If None, commands are registered globally (up to 1h delay).
    """

    def __init__(
        self,
        token: str,
        agent: Agent,
        *,
        guild_id: int | None = None,
    ) -> None:
        self._token = token
        self._agent = agent
        self._guild_id = guild_id
        self._client: Any = None

    async def start(self) -> None:
        """Connect to Discord and run the bot (blocks until stopped)."""
        try:
            import discord
            from discord import app_commands
        except ImportError as exc:
            raise ImportError("discord.py not installed. Run: uv add 'discord.py>=2.3.2'") from exc

        intents = discord.Intents.default()
        intents.message_content = False  # not needed for slash commands
        client = discord.Client(intents=intents)
        tree = app_commands.CommandTree(client)
        self._client = client

        guild_obj = discord.Object(id=self._guild_id) if self._guild_id else None

        # ── Slash command definitions ────────────────────────────────────────

        @tree.command(
            name="ask",
            description="Ask the Mirael AI agent anything about DeFi, positions, or protocol docs.",
            guild=guild_obj,
        )
        @app_commands.describe(
            question="Your question",
            wallet="Your wallet address (optional, enables on-chain context)",
        )
        async def ask_cmd(
            interaction: Any,  # noqa: ANN401
            question: str,
            wallet: str | None = None,
        ) -> None:
            await interaction.response.defer(thinking=True)
            try:
                response = await self._agent.chat(question, wallet=wallet)
                text = response.text
                total_tok = response.input_tokens + response.output_tokens
                meta = f"\n\n*{response.rag_chunks_used} doc chunks · {total_tok} tokens*"
                full = text + meta
            except MiraelError as exc:
                full = f"⚠️ {exc}"
            except Exception as exc:
                _log.warning("discord_ask_error", error=str(exc))
                full = "⚠️ An unexpected error occurred. Please try again."

            chunks = _chunk_text(full)
            await interaction.followup.send(chunks[0])
            for chunk in chunks[1:]:
                await interaction.followup.send(chunk)

        @tree.command(
            name="positions",
            description="Show your on-chain positions (Hyperliquid or Aave on Arbitrum).",
            guild=guild_obj,
        )
        @app_commands.describe(wallet="Your wallet address (0x...)")
        async def positions_cmd(interaction: Any, wallet: str) -> None:  # noqa: ANN401
            await interaction.response.defer(thinking=True)
            try:
                response = await self._agent.chat(
                    "Show me my open positions with size, PnL, and liquidation price.",
                    wallet=wallet,
                )
                text = response.text
            except MiraelError as exc:
                text = f"⚠️ {exc}"
            await interaction.followup.send(text[:_MAX_DISCORD_LEN])

        @tree.command(
            name="health",
            description="Show risk assessment and health factor for your wallet.",
            guild=guild_obj,
        )
        @app_commands.describe(wallet="Your wallet address (0x...)")
        async def health_cmd(interaction: Any, wallet: str) -> None:  # noqa: ANN401
            await interaction.response.defer(thinking=True)
            try:
                response = await self._agent.chat(
                    "What is my current health factor and liquidation risk? "
                    "Give me a clear risk assessment.",
                    wallet=wallet,
                )
                text = response.text
            except MiraelError as exc:
                text = f"⚠️ {exc}"
            await interaction.followup.send(text[:_MAX_DISCORD_LEN])

        @tree.command(
            name="help",
            description="List Mirael Agent commands.",
            guild=guild_obj,
        )
        async def help_cmd(interaction: Any) -> None:  # noqa: ANN401
            text = (
                "**Mirael Agent** — DeFi AI assistant\n\n"
                "`/ask [question]` — ask anything about the protocol or your positions\n"
                "`/positions [wallet]` — show on-chain positions\n"
                "`/health [wallet]` — show health factor & risk assessment\n"
                "`/monitor [wallet]` — start proactive health monitoring with DM alerts\n"
                "`/help` — this message\n\n"
                "*Powered by Mirael Labs · [mirael-agent-sdk](https://github.com/Mirael-labs/mirael-agent-sdk)*"
            )
            await interaction.response.send_message(text, ephemeral=True)

        @tree.command(
            name="monitor",
            description="Start proactive health monitoring — DMs you if liquidation risk rises.",
            guild=guild_obj,
        )
        @app_commands.describe(
            wallet="Your wallet address (0x...)",
            interval="Check interval in seconds (default: 60)",
        )
        async def monitor_cmd(
            interaction: Any,  # noqa: ANN401
            wallet: str,
            interval: int = 60,
        ) -> None:
            await interaction.response.defer(ephemeral=True, thinking=True)
            user_id = str(interaction.user.id)

            async def send_dm(alert: Any) -> None:  # noqa: ANN401
                try:
                    user = await client.fetch_user(int(user_id))
                    await user.send(alert.message)
                except Exception as exc:
                    _log.warning("discord_dm_failed", error=str(exc))

            from mirael.monitoring.health_monitor import HealthMonitor

            monitor = HealthMonitor(
                chain_reader=self._agent._chain,
                check_interval=interval,
                on_alert=send_dm,
            )
            _monitor_task = asyncio.create_task(monitor.start(wallet))  # noqa: RUF006
            await interaction.followup.send(
                f"Health monitor started for `{wallet[:12]}...`\n"
                f"Checking every {interval}s. You'll receive DMs if liquidation risk rises.",
                ephemeral=True,
            )

        # ── Lifecycle ─────────────────────────────────────────────────────────

        @client.event
        async def on_ready() -> None:
            if guild_obj:
                tree.copy_global_to(guild=guild_obj)
                await tree.sync(guild=guild_obj)
                _log.info("discord_commands_synced_guild", guild_id=self._guild_id)
            else:
                await tree.sync()
                _log.info("discord_commands_synced_global")
            _log.info("discord_bot_ready", username=str(client.user))

        _log.info("discord_bot_starting")
        await client.start(self._token)

    async def stop(self) -> None:
        """Close the Discord connection."""
        if self._client is not None:
            await self._client.close()
            _log.info("discord_bot_stopped")

    async def send_message(self, channel_id: str, text: str) -> None:
        """Send a message to a Discord channel by ID."""
        if self._client is None:
            raise RuntimeError("Bot not started — call start() first")
        try:
            channel = self._client.get_channel(int(channel_id))
            if channel is None:
                channel = await self._client.fetch_channel(int(channel_id))
            for chunk in _chunk_text(text):
                await channel.send(chunk)
        except Exception as exc:
            _log.warning("discord_send_failed", channel_id=channel_id, error=str(exc))


def create_adapter_from_settings(settings: Any, agent: Agent) -> DiscordChannelAdapter:  # noqa: ANN401
    """Factory: build a ``DiscordChannelAdapter`` from ``MiraelSettings``."""
    if not settings.discord_bot_token:
        raise ValueError("MIRAEL_DISCORD_BOT_TOKEN is not set")
    return DiscordChannelAdapter(
        token=settings.discord_bot_token.get_secret_value(),
        agent=agent,
        guild_id=settings.discord_guild_id,
    )
