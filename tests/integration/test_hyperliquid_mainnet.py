"""
Integration tests against the Hyperliquid mainnet (read-only).

These tests make real network calls to ``api.hyperliquid.xyz``.
Run with: ``pytest tests/integration/ -m integration``

Public endpoints (no wallet needed):
  - get_funding_rate
  - get_market_info

Wallet-specific endpoints require the env var ``TEST_HL_WALLET``.
If not set, those tests are automatically skipped.
"""

from __future__ import annotations

import os

import pytest

from mirael.chains.hyperliquid import HyperliquidReader

_TEST_WALLET = os.getenv("TEST_HL_WALLET", "")


@pytest.mark.integration
class TestHyperliquidMainnetPublic:
    """Tests that require no wallet — safe to run against mainnet."""

    async def test_get_funding_rate_btc(self) -> None:
        async with HyperliquidReader() as reader:
            result = await reader.get_funding_rate("BTC")

        assert result["asset"] == "BTC"
        assert isinstance(result["rate"], float)
        assert isinstance(result["annualized"], float)
        assert result["mark_price"] > 0

    async def test_get_funding_rate_eth(self) -> None:
        async with HyperliquidReader() as reader:
            result = await reader.get_funding_rate("ETH")

        assert result["asset"] == "ETH"
        assert result["open_interest"] > 0

    async def test_get_market_info_btc(self) -> None:
        async with HyperliquidReader() as reader:
            info = await reader.get_market_info("BTC")

        assert info["asset"] == "BTC"
        assert info["mark_price"] > 0
        assert info["max_leverage"] >= 10
        assert info["oracle_price"] > 0

    async def test_get_market_info_sol(self) -> None:
        async with HyperliquidReader() as reader:
            info = await reader.get_market_info("SOL")

        assert info["asset"] == "SOL"
        assert isinstance(info["funding_rate"], float)

    async def test_unknown_asset_raises(self) -> None:
        from mirael.exceptions import ChainDataError

        async with HyperliquidReader() as reader:
            with pytest.raises(ChainDataError):
                await reader.get_funding_rate("NOTAREALASSET999")


@pytest.mark.integration
class TestHyperliquidMainnetWallet:
    """Tests that require TEST_HL_WALLET env var to be set."""

    @pytest.fixture(autouse=True)
    def require_wallet(self) -> None:
        if not _TEST_WALLET:
            pytest.skip("TEST_HL_WALLET env var not set — skipping wallet tests")

    async def test_get_user_balance(self) -> None:
        async with HyperliquidReader() as reader:
            balance = await reader.get_user_balance(_TEST_WALLET)

        assert "account_value" in balance
        assert "free_margin" in balance
        assert isinstance(balance["account_value"], float)

    async def test_get_user_positions(self) -> None:
        async with HyperliquidReader() as reader:
            positions = await reader.get_user_positions(_TEST_WALLET)

        # May be empty (no open positions) — just validate structure
        assert isinstance(positions, list)
        for p in positions:
            assert "asset" in p
            assert "size" in p
            assert "unrealized_pnl" in p

    async def test_get_recent_trades(self) -> None:
        async with HyperliquidReader() as reader:
            trades = await reader.get_recent_trades(_TEST_WALLET, limit=10)

        assert isinstance(trades, list)
        for t in trades:
            assert t["side"] in ("buy", "sell")
            assert isinstance(t["timestamp_ms"], int)
