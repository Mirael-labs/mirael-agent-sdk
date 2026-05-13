"""
Channel adapter Protocol — interface for all output channels.

A channel adapter connects the Mirael Agent to a communication platform
(Discord, Telegram, etc.).  Concrete implementations satisfy this Protocol
via structural subtyping — no inheritance required.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ChannelAdapter(Protocol):
    """
    Interface every channel adapter must satisfy.

    Implementors must be async-safe: ``start()`` runs the bot event loop
    and blocks until ``stop()`` is called (or Ctrl-C).
    """

    async def start(self) -> None:
        """Connect to the platform and begin processing messages."""
        ...

    async def stop(self) -> None:
        """Gracefully disconnect and release resources."""
        ...

    async def send_message(self, channel_id: str, text: str) -> None:
        """
        Push a text message to a specific channel.

        Args:
            channel_id: Platform-specific channel identifier.
            text: Message content (may contain markdown).
        """
        ...
