"""
E2E tests: Hyperliquid mainnet (public endpoints, no wallet needed).

These tests call the real Hyperliquid REST API.
No authentication required for read-only market data.
"""

from __future__ import annotations

import time

import pytest

from mirael.chains.hyperliquid import HyperliquidReader


@pytest.mark.e2e
class TestHyperliquidE2E:
    async def test_get_funding_rate_btc(self):
        """Fetch live BTC funding rate from Hyperliquid mainnet."""
        async with HyperliquidReader() as reader:
            result = await reader.get_funding_rate("BTC")

        assert result["asset"] == "BTC"
        assert isinstance(result["rate"], float)
        assert isinstance(result["annualized"], float)
        assert result["mark_price"] > 0
        assert result["open_interest"] > 0

    async def test_get_funding_rate_eth(self):
        """Fetch live ETH funding rate."""
        async with HyperliquidReader() as reader:
            result = await reader.get_funding_rate("ETH")

        assert result["asset"] == "ETH"
        assert isinstance(result["rate"], float)

    async def test_get_market_info_btc(self):
        """Fetch full BTC market info including OI and oracle price."""
        async with HyperliquidReader() as reader:
            info = await reader.get_market_info("BTC")

        assert info["asset"] == "BTC"
        assert info["mark_price"] > 0
        assert info["oracle_price"] > 0
        assert info["max_leverage"] >= 10
        assert info["open_interest"] > 0

    async def test_get_market_info_sol(self):
        """SOL market info is available."""
        async with HyperliquidReader() as reader:
            info = await reader.get_market_info("SOL")

        assert info["asset"] == "SOL"
        assert isinstance(info["funding_rate"], float)

    async def test_get_all_mids_returns_dict(self):
        """metaAndAssetCtxs returns mark prices for BTC, ETH, and SOL."""
        async with HyperliquidReader() as reader:
            btc = await reader.get_market_info("BTC")
            eth = await reader.get_market_info("ETH")
            sol = await reader.get_market_info("SOL")

        assert btc["mark_price"] > 0
        assert eth["mark_price"] > 0
        assert sol["mark_price"] > 0

    async def test_api_latency(self):
        """Single API call to Hyperliquid should complete under 3 seconds."""
        t0 = time.monotonic()
        async with HyperliquidReader() as reader:
            await reader.get_funding_rate("BTC")
        elapsed = time.monotonic() - t0

        assert elapsed < 3.0, f"API call took {elapsed:.2f}s — too slow"

    async def test_unknown_asset_raises(self):
        """Querying a non-existent asset raises ChainDataError."""
        from mirael.exceptions import ChainDataError

        async with HyperliquidReader() as reader:
            with pytest.raises(ChainDataError):
                await reader.get_funding_rate("NOTAREALASSET999")
