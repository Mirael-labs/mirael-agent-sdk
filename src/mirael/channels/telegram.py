"""
Telegram bot channel adapter.

Connects the Mirael Agent to Telegram via the Bot API.
Uses ``python-telegram-bot`` (``pip install 'mirael-agent-sdk[telegram]'``).

Commands:
  /start              — welcome message
  /ask [question]     — ask the AI agent anything
  /positions [wallet] — show on-chain positions
  /health [wallet]    — show health factor summary
  /setwallet [addr]   — save your wallet for the session
  /help               — list commands

Setup:
  1. Message @BotFather on Telegram → /newbot → copy the token
  2. Set MIRAEL_TELEGRAM_BOT_TOKEN in .env
  3. Run: uv run python examples/telegram_demo/bot.py
"""

from __future__ import annotations

import asyncio
from typing import Any

from mirael.agent.base import Agent
from mirael.exceptions import MiraelError
from mirael.logging import get_logger

_log = get_logger(__name__)

_MAX_TG_LEN = 4000  # Telegram limit is 4096


def _split_message(text: str, max_len: int = _MAX_TG_LEN) -> list[str]:
    if len(text) <= max_len:
        return [text]
    chunks: list[str] = []
    while text:
        chunks.append(text[:max_len])
        text = text[max_len:]
    return chunks


class TelegramChannelAdapter:
    """
    Telegram bot adapter wrapping the Mirael Agent.

    Args:
        token: Telegram bot token (from @BotFather).
        agent: Configured ``Agent`` instance.
    """

    def __init__(self, token: str, agent: Agent) -> None:
        self._token = token
        self._agent = agent
        self._app: Any = None
        # Per-chat wallet registry (in-memory, resets on restart)
        self._wallets: dict[int, str] = {}

    async def start(self) -> None:
        """Start the Telegram bot (blocking until stopped)."""
        try:
            from telegram import Update
            from telegram.ext import (
                Application,
                CommandHandler,
                ContextTypes,
                MessageHandler,
                filters,
            )
        except ImportError as exc:
            raise ImportError(
                "python-telegram-bot not installed. Run: uv add 'python-telegram-bot>=20.7'"
            ) from exc

        app = Application.builder().token(self._token).build()
        self._app = app

        # ── Command handlers ─────────────────────────────────────────────────

        async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            text = (
                "👋 Mirael Agent — DeFi AI assistant\n\n"
                "Commands:\n"
                "  /ask [question] — ask about positions, protocol docs, risk\n"
                "  /positions [wallet] — show on-chain positions\n"
                "  /health [wallet] — health factor & liquidation risk\n"
                "  /setwallet 0xYOUR_WALLET — save wallet for this session\n"
                "  /help — this message\n\n"
                "Tip: use /setwallet first, then just type your questions directly."
            )
            if update.message:
                await update.message.reply_text(text)

        async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            await start_cmd(update, context)

        async def setwallet_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            if not update.message:
                return
            args = context.args or []
            if not args:
                await update.message.reply_text("Usage: /setwallet 0xYOUR_WALLET")
                return
            wallet = args[0].strip()
            if not (wallet.startswith("0x") and len(wallet) == 42):
                await update.message.reply_text(
                    "❌ Invalid wallet address. "
                    "Must be 42 characters starting with 0x.\n"
                    "Example: /setwallet 0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
                )
                return
            chat_id = update.message.chat_id
            self._wallets[chat_id] = wallet
            preview = f"{wallet[:8]}...{wallet[-4:]}"
            await update.message.reply_text(f"✅ Wallet saved: `{preview}`")

        async def ask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            if not update.message:
                return
            args = context.args or []
            if not args:
                await update.message.reply_text("Usage: /ask [your question]")
                return
            question = " ".join(args)
            wallet = self._wallets.get(update.message.chat_id)

            msg = await update.message.reply_text("⏳ Thinking...")
            try:
                response = await self._agent.chat(question, wallet=wallet)
                text = response.text
            except MiraelError as exc:
                text = f"⚠️ {exc}"
            except Exception as exc:
                _log.warning("telegram_ask_error", error=str(exc))
                text = "⚠️ An error occurred. Please try again."

            for chunk in _split_message(text):
                await msg.edit_text(chunk, parse_mode="Markdown")

        async def positions_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            if not update.message:
                return
            args = context.args or []
            wallet = args[0] if args else self._wallets.get(update.message.chat_id)
            if not wallet:
                await update.message.reply_text(
                    "Provide a wallet: /positions 0xYOUR_WALLET\n"
                    "Or save one first: /setwallet 0xYOUR_WALLET"
                )
                return
            msg = await update.message.reply_text("⏳ Fetching positions...")
            try:
                response = await self._agent.chat(
                    "Show my open positions with size, PnL, and liquidation price.",
                    wallet=wallet,
                )
                text = response.text
            except MiraelError as exc:
                text = f"⚠️ {exc}"
            await msg.edit_text(text[:_MAX_TG_LEN], parse_mode="Markdown")

        async def health_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            if not update.message:
                return
            args = context.args or []
            wallet = args[0] if args else self._wallets.get(update.message.chat_id)
            if not wallet:
                await update.message.reply_text("Provide a wallet: /health 0xYOUR_WALLET")
                return
            msg = await update.message.reply_text("⏳ Checking risk...")
            try:
                response = await self._agent.chat(
                    "What is my health factor and liquidation risk? Give a clear assessment.",
                    wallet=wallet,
                )
                text = response.text
            except MiraelError as exc:
                text = f"⚠️ {exc}"
            await msg.edit_text(text[:_MAX_TG_LEN], parse_mode="Markdown")

        async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            """Handle plain text messages as /ask."""
            if not update.message or not update.message.text:
                return
            question = update.message.text
            wallet = self._wallets.get(update.message.chat_id)
            msg = await update.message.reply_text("⏳ Thinking...")
            try:
                response = await self._agent.chat(question, wallet=wallet)
                text = response.text
            except MiraelError as exc:
                text = f"⚠️ {exc}"
            except Exception:
                text = "⚠️ An error occurred."
            await msg.edit_text(text[:_MAX_TG_LEN], parse_mode="Markdown")

        app.add_handler(CommandHandler("start", start_cmd))
        app.add_handler(CommandHandler("help", help_cmd))
        app.add_handler(CommandHandler("ask", ask_cmd))
        app.add_handler(CommandHandler("positions", positions_cmd))
        app.add_handler(CommandHandler("health", health_cmd))
        app.add_handler(CommandHandler("setwallet", setwallet_cmd))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

        _log.info("telegram_bot_starting")
        # run_polling is synchronous; run it in a thread to avoid blocking the event loop
        await asyncio.to_thread(app.run_polling, drop_pending_updates=True, close_loop=False)

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        if self._app is not None:
            await self._app.stop()
            _log.info("telegram_bot_stopped")

    async def send_message(self, channel_id: str, text: str) -> None:
        """Push a message to a Telegram chat by chat ID."""
        if self._app is None:
            raise RuntimeError("Bot not started — call start() first")
        try:
            for chunk in _split_message(text):
                await self._app.bot.send_message(chat_id=int(channel_id), text=chunk)
        except Exception as exc:
            _log.warning("telegram_send_failed", channel_id=channel_id, error=str(exc))


def create_adapter_from_settings(settings: Any, agent: Agent) -> TelegramChannelAdapter:  # noqa: ANN401
    """Factory: build a ``TelegramChannelAdapter`` from ``MiraelSettings``."""
    if not settings.telegram_bot_token:
        raise ValueError("MIRAEL_TELEGRAM_BOT_TOKEN is not set")
    return TelegramChannelAdapter(
        token=settings.telegram_bot_token.get_secret_value(),
        agent=agent,
    )
