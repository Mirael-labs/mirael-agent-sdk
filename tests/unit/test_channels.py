"""Unit tests for Discord and Telegram channel adapters."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mirael.channels.base import ChannelAdapter
from mirael.channels.discord import DiscordChannelAdapter, _chunk_text
from mirael.channels.telegram import TelegramChannelAdapter, _split_message


class TestChunkText:
    def test_short_text_not_split(self) -> None:
        assert _chunk_text("hello", max_len=100) == ["hello"]

    def test_long_text_split(self) -> None:
        text = "a" * 250
        chunks = _chunk_text(text, max_len=100)
        assert len(chunks) == 3
        assert all(len(c) <= 100 for c in chunks)

    def test_exact_length_not_split(self) -> None:
        text = "a" * 100
        assert _chunk_text(text, max_len=100) == [text]

    def test_reassembly_is_lossless(self) -> None:
        text = "x" * 500
        assert "".join(_chunk_text(text, max_len=100)) == text


class TestSplitMessage:
    def test_short_message_not_split(self) -> None:
        assert _split_message("hello", max_len=100) == ["hello"]

    def test_long_message_split(self) -> None:
        text = "b" * 300
        chunks = _split_message(text, max_len=100)
        assert len(chunks) == 3

    def test_reassembly(self) -> None:
        text = "y" * 450
        assert "".join(_split_message(text, max_len=100)) == text


class TestDiscordChannelAdapterProtocol:
    def test_satisfies_channel_adapter_protocol(self) -> None:
        mock_agent = MagicMock()
        adapter = DiscordChannelAdapter(token="test-token", agent=mock_agent)
        assert isinstance(adapter, ChannelAdapter)

    def test_start_raises_if_discord_not_installed(self) -> None:
        """When discord.py is not installed, start() raises ImportError."""
        import sys
        mock_agent = MagicMock()
        adapter = DiscordChannelAdapter(token="tok", agent=mock_agent)
        # Temporarily hide discord module
        original = sys.modules.get("discord")
        sys.modules["discord"] = None  # type: ignore[assignment]
        try:
            with pytest.raises((ImportError, TypeError)):
                import asyncio
                asyncio.get_event_loop().run_until_complete(adapter.start())
        finally:
            if original is None:
                sys.modules.pop("discord", None)
            else:
                sys.modules["discord"] = original

    async def test_stop_is_noop_when_not_started(self) -> None:
        mock_agent = MagicMock()
        adapter = DiscordChannelAdapter(token="tok", agent=mock_agent)
        # Should not raise
        await adapter.stop()


class TestTelegramChannelAdapterProtocol:
    def test_satisfies_channel_adapter_protocol(self) -> None:
        mock_agent = MagicMock()
        adapter = TelegramChannelAdapter(token="test-token", agent=mock_agent)
        assert isinstance(adapter, ChannelAdapter)

    async def test_stop_is_noop_when_not_started(self) -> None:
        mock_agent = MagicMock()
        adapter = TelegramChannelAdapter(token="tok", agent=mock_agent)
        await adapter.stop()

    def test_wallet_registry_starts_empty(self) -> None:
        mock_agent = MagicMock()
        adapter = TelegramChannelAdapter(token="tok", agent=mock_agent)
        assert adapter._wallets == {}


class TestCreateAdapterFromSettings:
    def test_discord_raises_without_token(self) -> None:
        from mirael.channels.discord import create_adapter_from_settings
        settings = MagicMock()
        settings.discord_bot_token = None
        mock_agent = MagicMock()
        with pytest.raises(ValueError, match="DISCORD_BOT_TOKEN"):
            create_adapter_from_settings(settings, mock_agent)

    def test_telegram_raises_without_token(self) -> None:
        from mirael.channels.telegram import create_adapter_from_settings
        settings = MagicMock()
        settings.telegram_bot_token = None
        mock_agent = MagicMock()
        with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
            create_adapter_from_settings(settings, mock_agent)

    def test_discord_created_with_token(self) -> None:
        from mirael.channels.discord import create_adapter_from_settings
        settings = MagicMock()
        token_mock = MagicMock()
        token_mock.get_secret_value.return_value = "real-token"
        settings.discord_bot_token = token_mock
        settings.discord_guild_id = None
        mock_agent = MagicMock()
        adapter = create_adapter_from_settings(settings, mock_agent)
        assert isinstance(adapter, DiscordChannelAdapter)
        assert adapter._token == "real-token"

    def test_telegram_created_with_token(self) -> None:
        from mirael.channels.telegram import create_adapter_from_settings
        settings = MagicMock()
        token_mock = MagicMock()
        token_mock.get_secret_value.return_value = "tg-token"
        settings.telegram_bot_token = token_mock
        mock_agent = MagicMock()
        adapter = create_adapter_from_settings(settings, mock_agent)
        assert isinstance(adapter, TelegramChannelAdapter)
        assert adapter._token == "tg-token"
