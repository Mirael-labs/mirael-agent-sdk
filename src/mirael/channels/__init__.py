"""Output channel adapters."""

from mirael.channels.base import ChannelAdapter
from mirael.channels.discord import DiscordChannelAdapter
from mirael.channels.telegram import TelegramChannelAdapter

__all__ = [
    "ChannelAdapter",
    "DiscordChannelAdapter",
    "TelegramChannelAdapter",
]
