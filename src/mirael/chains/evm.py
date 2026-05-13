"""EVM chain reader — placeholder, out of scope for current milestone."""

from __future__ import annotations

from typing import Any


class EVMReader:
    """
    Read-only reader for EVM-compatible chains.

    Placeholder — implementation is out of scope for this session.
    """

    async def get_user_positions(self, wallet: str) -> list[dict[str, Any]]:
        # TODO: implement EVM chain reader
        raise NotImplementedError

    async def get_user_balance(self, wallet: str) -> dict[str, Any]:
        raise NotImplementedError

    async def get_recent_trades(
        self, wallet: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    async def get_funding_rate(self, asset: str) -> dict[str, Any]:
        raise NotImplementedError

    async def get_market_info(self, asset: str) -> dict[str, Any]:
        raise NotImplementedError
