"""Unit tests for GMXReader — mocked, no real API calls."""

from __future__ import annotations

import httpx
import pytest
import respx

from mirael.chains.gmx import GMXReader
from mirael.exceptions import ChainConnectionError, ChainDataError

_WALLET = "0xabcdef1234567890abcdef1234567890abcdef12"

_MOCK_POSITIONS = [
    {
        "market": "BTC/USD:BTC",
        "sizeInUsd": "50000000000000000000000000000000000",  # $50K in 1e30
        "collateralAmount": "5000000000",  # $5K in 1e6 (USDC)
        "entryPrice": "65000000000000000000000000000000000",  # $65K in 1e30
        "markPrice": "66000000000000000000000000000000000",  # $66K in 1e30
        "isLong": True,
    }
]

_MOCK_TICKERS = [
    {
        "tokenSymbol": "BTC",
        "markPrice": "65000000000000000000000000000000000",
        "indexPrice": "65100000000000000000000000000000000",
        "fundingRate": "0.0001",
        "openInterest": "500000000000000000000000000000000000",
    }
]

_MOCK_MARKETS = [
    {
        "indexToken": {"symbol": "BTC"},
        "markPrice": "65000000000000000000000000000000000",
        "indexPrice": "65100000000000000000000000000000000",
        "longInterestUsd": "250000000000000000000000000000000000",
        "shortInterestUsd": "200000000000000000000000000000000000",
        "fundingRate": "0.0001",
    }
]


@pytest.fixture()
def gmx_api() -> respx.MockRouter:  # type: ignore[type-arg]
    with respx.mock(base_url="https://arbitrum-api.gmxinfra.io", assert_all_called=False) as r:
        yield r


class TestGetUserPositions:
    async def test_returns_open_positions(self, gmx_api: respx.MockRouter) -> None:  # type: ignore[type-arg]
        gmx_api.get("/positions").mock(return_value=httpx.Response(200, json=_MOCK_POSITIONS))
        reader = GMXReader()
        positions = await reader.get_user_positions(_WALLET)
        assert len(positions) == 1
        assert positions[0]["asset"] == "BTC"
        assert positions[0]["is_long"] is True

    async def test_filters_zero_size(self, gmx_api: respx.MockRouter) -> None:  # type: ignore[type-arg]
        tiny = [{"market": "ETH/USD", "sizeInUsd": "0", "collateralAmount": "0",
                 "entryPrice": "0", "markPrice": "0", "isLong": True}]
        gmx_api.get("/positions").mock(return_value=httpx.Response(200, json=tiny))
        reader = GMXReader()
        positions = await reader.get_user_positions(_WALLET)
        assert positions == []

    async def test_http_error_raises(self, gmx_api: respx.MockRouter) -> None:  # type: ignore[type-arg]
        gmx_api.get("/positions").mock(return_value=httpx.Response(500))
        reader = GMXReader()
        with pytest.raises(ChainConnectionError):
            await reader.get_user_positions(_WALLET)


class TestGetFundingRate:
    async def test_returns_btc_funding(self, gmx_api: respx.MockRouter) -> None:  # type: ignore[type-arg]
        gmx_api.get("/prices/tickers").mock(return_value=httpx.Response(200, json=_MOCK_TICKERS))
        reader = GMXReader()
        result = await reader.get_funding_rate("BTC")
        assert result["asset"] == "BTC"
        assert isinstance(result["rate"], float)

    async def test_unknown_asset_raises(self, gmx_api: respx.MockRouter) -> None:  # type: ignore[type-arg]
        gmx_api.get("/prices/tickers").mock(return_value=httpx.Response(200, json=_MOCK_TICKERS))
        reader = GMXReader()
        with pytest.raises(ChainDataError):
            await reader.get_funding_rate("DOGE")


class TestGetMarketInfo:
    async def test_returns_btc_market(self, gmx_api: respx.MockRouter) -> None:  # type: ignore[type-arg]
        gmx_api.get("/markets").mock(return_value=httpx.Response(200, json=_MOCK_MARKETS))
        reader = GMXReader()
        info = await reader.get_market_info("BTC")
        assert info["asset"] == "BTC"
        assert info["protocol"] == "GMX V2"
        assert info["chain"] == "Arbitrum"
        assert info["max_leverage"] == 100


class TestGMXReaderProtocol:
    def test_implements_onchain_reader(self) -> None:
        from mirael.chains.base import OnchainReader
        reader = GMXReader()
        assert isinstance(reader, OnchainReader)
