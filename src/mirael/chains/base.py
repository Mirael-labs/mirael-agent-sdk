"""Protocol definition for on-chain readers."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class OnchainReader(Protocol):
    """
    Interface that all chain-specific readers must implement.

    Using Protocol (structural subtyping) rather than ABC keeps the
    module dependency graph clean — callers depend on the interface,
    not the implementation.
    """

    async def get_user_positions(self, wallet: str) -> list[dict[str, Any]]:
        """Return open positions for a wallet address."""
        ...

    async def get_user_balance(self, wallet: str) -> dict[str, Any]:
        """Return account balance summary for a wallet address."""
        ...

    async def get_recent_trades(self, wallet: str, limit: int = 50) -> list[dict[str, Any]]:
        """Return the most recent trades for a wallet address."""
        ...

    async def get_funding_rate(self, asset: str) -> dict[str, Any]:
        """Return current funding rate for a perpetual asset."""
        ...

    async def get_market_info(self, asset: str) -> dict[str, Any]:
        """Return market metadata for an asset (mark price, OI, etc.)."""
        ...
