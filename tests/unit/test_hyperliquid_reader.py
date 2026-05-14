"""
Unit tests for HyperliquidReader.

Uses ``respx`` to mock httpx — no real network calls are made.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from mirael.chains.hyperliquid import HyperliquidReader
from mirael.exceptions import ChainConnectionError, ChainDataError

# ── Fixtures & helpers ─────────────────────────────────────────────────────────

_WALLET = "0xabcdef1234567890abcdef1234567890abcdef12"

_CLEARINGHOUSE_STATE: dict = {  # type: ignore[type-arg]
    "assetPositions": [
        {
            "position": {
                "coin": "BTC",
                "szi": "0.5",
                "entryPx": "64000.0",
                "positionValue": "32500.0",
                "unrealizedPnl": "500.0",
                "liquidationPx": "55000.0",
                "marginUsed": "3250.0",
                "leverage": {"type": "cross", "value": 10},
                "cumFunding": {"allTime": "25.5", "sinceOpen": "5.0", "sinceChange": "1.0"},
            },
            "type": "oneWay",
        },
        {
            "position": {
                "coin": "ETH",
                "szi": "0.0",  # zero size — should be filtered out
                "entryPx": "3000.0",
                "positionValue": "0.0",
                "unrealizedPnl": "0.0",
                "liquidationPx": None,
                "marginUsed": "0.0",
                "leverage": {"type": "cross", "value": 5},
                "cumFunding": {"allTime": "0.0", "sinceOpen": "0.0", "sinceChange": "0.0"},
            },
            "type": "oneWay",
        },
    ],
    "marginSummary": {
        "accountValue": "50000.0",
        "totalNtlPos": "32500.0",
        "totalRawUsd": "49500.0",
        "totalMarginUsed": "3250.0",
    },
}

_META_AND_ASSET_CTXS: list = [  # type: ignore[type-arg]
    {
        "universe": [
            {"name": "BTC", "szDecimals": 5, "maxLeverage": 50, "onlyIsolated": False},
            {"name": "ETH", "szDecimals": 4, "maxLeverage": 25, "onlyIsolated": False},
        ]
    },
    [
        {
            "funding": "0.0001234",
            "openInterest": "12345678.0",
            "oraclePx": "65000.0",
            "markPx": "65050.0",
            "midPx": "65048.0",
            "prevDayPx": "64000.0",
            "dayNtlVlm": "999999999.0",
        },
        {
            "funding": "-0.0000500",
            "openInterest": "9876543.0",
            "oraclePx": "3500.0",
            "markPx": "3502.0",
            "midPx": "3501.5",
            "prevDayPx": "3400.0",
            "dayNtlVlm": "123456789.0",
        },
    ],
]

_USER_FILLS: list = [  # type: ignore[type-arg]
    {
        "coin": "BTC",
        "px": "65000.0",
        "sz": "0.1",
        "side": "B",
        "time": 1700000000000,
        "closedPnl": "150.0",
        "fee": "6.5",
        "tid": 111,
    },
    {
        "coin": "ETH",
        "px": "3500.0",
        "sz": "2.0",
        "side": "A",
        "time": 1700001000000,
        "closedPnl": "-50.0",
        "fee": "7.0",
        "tid": 222,
    },
]


@pytest.fixture()
def hl_api() -> respx.MockRouter:  # type: ignore[type-arg]
    with respx.mock(base_url="https://api.hyperliquid.xyz", assert_all_called=False) as router:
        yield router


# ── Tests: get_user_positions ──────────────────────────────────────────────────


class TestGetUserPositions:
    async def test_returns_non_zero_positions(self, hl_api: respx.MockRouter) -> None:  # type: ignore[type-arg]
        hl_api.post("/info").mock(return_value=httpx.Response(200, json=_CLEARINGHOUSE_STATE))
        reader = HyperliquidReader()
        positions = await reader.get_user_positions(_WALLET)
        # Only BTC (size=0.5), ETH filtered (size=0.0)
        assert len(positions) == 1
        assert positions[0]["asset"] == "BTC"

    async def test_position_fields_correct(self, hl_api: respx.MockRouter) -> None:  # type: ignore[type-arg]
        hl_api.post("/info").mock(return_value=httpx.Response(200, json=_CLEARINGHOUSE_STATE))
        reader = HyperliquidReader()
        positions = await reader.get_user_positions(_WALLET)
        p = positions[0]
        assert p["size"] == pytest.approx(0.5)
        assert p["entry_price"] == pytest.approx(64000.0)
        assert p["unrealized_pnl"] == pytest.approx(500.0)
        assert p["liquidation_price"] == pytest.approx(55000.0)
        assert p["leverage"] == pytest.approx(10.0)
        assert p["funding_since_open"] == pytest.approx(25.5)

    async def test_mark_price_computed_from_notional(self, hl_api: respx.MockRouter) -> None:  # type: ignore[type-arg]
        hl_api.post("/info").mock(return_value=httpx.Response(200, json=_CLEARINGHOUSE_STATE))
        reader = HyperliquidReader()
        positions = await reader.get_user_positions(_WALLET)
        # mark_price = positionValue / abs(size) = 32500 / 0.5 = 65000
        assert positions[0]["mark_price"] == pytest.approx(65000.0)

    async def test_empty_positions_returns_empty_list(self, hl_api: respx.MockRouter) -> None:  # type: ignore[type-arg]
        empty: dict = {  # type: ignore[type-arg]
            "assetPositions": [],
            "marginSummary": {"accountValue": "10000", "totalNtlPos": "0", "totalMarginUsed": "0"},
        }
        hl_api.post("/info").mock(return_value=httpx.Response(200, json=empty))
        reader = HyperliquidReader()
        assert await reader.get_user_positions(_WALLET) == []

    async def test_null_liquidation_price_handled(self, hl_api: respx.MockRouter) -> None:  # type: ignore[type-arg]
        state = {
            "assetPositions": [
                {
                    "position": {
                        "coin": "SOL",
                        "szi": "10",
                        "entryPx": "150",
                        "positionValue": "1500",
                        "unrealizedPnl": "0",
                        "liquidationPx": None,
                        "marginUsed": "150",
                        "leverage": {"type": "cross", "value": 10},
                        "cumFunding": {},
                    },
                    "type": "oneWay",
                }
            ],
            "marginSummary": {
                "accountValue": "5000",
                "totalNtlPos": "1500",
                "totalMarginUsed": "150",
            },
        }
        hl_api.post("/info").mock(return_value=httpx.Response(200, json=state))
        reader = HyperliquidReader()
        positions = await reader.get_user_positions(_WALLET)
        assert positions[0]["liquidation_price"] is None


# ── Tests: get_user_balance ────────────────────────────────────────────────────


class TestGetUserBalance:
    async def test_returns_balance_fields(self, hl_api: respx.MockRouter) -> None:  # type: ignore[type-arg]
        hl_api.post("/info").mock(return_value=httpx.Response(200, json=_CLEARINGHOUSE_STATE))
        reader = HyperliquidReader()
        balance = await reader.get_user_balance(_WALLET)
        assert balance["account_value"] == pytest.approx(50000.0)
        assert balance["total_margin_used"] == pytest.approx(3250.0)
        assert balance["free_margin"] == pytest.approx(46750.0)

    async def test_free_margin_clamped_to_zero(self, hl_api: respx.MockRouter) -> None:  # type: ignore[type-arg]
        state = {
            "assetPositions": [],
            "marginSummary": {
                "accountValue": "1000",
                "totalNtlPos": "5000",
                "totalMarginUsed": "2000",  # more than accountValue
            },
        }
        hl_api.post("/info").mock(return_value=httpx.Response(200, json=state))
        reader = HyperliquidReader()
        balance = await reader.get_user_balance(_WALLET)
        assert balance["free_margin"] == pytest.approx(0.0)


# ── Tests: get_recent_trades ───────────────────────────────────────────────────


class TestGetRecentTrades:
    async def test_returns_trades(self, hl_api: respx.MockRouter) -> None:  # type: ignore[type-arg]
        hl_api.post("/info").mock(return_value=httpx.Response(200, json=_USER_FILLS))
        reader = HyperliquidReader()
        trades = await reader.get_recent_trades(_WALLET)
        assert len(trades) == 2

    async def test_side_mapping(self, hl_api: respx.MockRouter) -> None:  # type: ignore[type-arg]
        hl_api.post("/info").mock(return_value=httpx.Response(200, json=_USER_FILLS))
        reader = HyperliquidReader()
        trades = await reader.get_recent_trades(_WALLET)
        assert trades[0]["side"] == "buy"  # "B" → "buy"
        assert trades[1]["side"] == "sell"  # "A" → "sell"

    async def test_limit_applied(self, hl_api: respx.MockRouter) -> None:  # type: ignore[type-arg]
        hl_api.post("/info").mock(return_value=httpx.Response(200, json=_USER_FILLS))
        reader = HyperliquidReader()
        trades = await reader.get_recent_trades(_WALLET, limit=1)
        assert len(trades) == 1

    async def test_trade_fields(self, hl_api: respx.MockRouter) -> None:  # type: ignore[type-arg]
        hl_api.post("/info").mock(return_value=httpx.Response(200, json=_USER_FILLS))
        reader = HyperliquidReader()
        trades = await reader.get_recent_trades(_WALLET)
        t = trades[0]
        assert t["asset"] == "BTC"
        assert t["price"] == pytest.approx(65000.0)
        assert t["fee"] == pytest.approx(6.5)
        assert t["realized_pnl"] == pytest.approx(150.0)
        assert t["timestamp_ms"] == 1700000000000


# ── Tests: get_funding_rate ────────────────────────────────────────────────────


class TestGetFundingRate:
    async def test_returns_funding_fields(self, hl_api: respx.MockRouter) -> None:  # type: ignore[type-arg]
        hl_api.post("/info").mock(return_value=httpx.Response(200, json=_META_AND_ASSET_CTXS))
        reader = HyperliquidReader()
        result = await reader.get_funding_rate("BTC")
        assert result["asset"] == "BTC"
        assert result["rate"] == pytest.approx(0.0001234)
        assert result["annualized"] == pytest.approx(0.0001234 * 24 * 365)
        assert result["mark_price"] == pytest.approx(65050.0)

    async def test_unknown_asset_raises(self, hl_api: respx.MockRouter) -> None:  # type: ignore[type-arg]
        hl_api.post("/info").mock(return_value=httpx.Response(200, json=_META_AND_ASSET_CTXS))
        reader = HyperliquidReader()
        with pytest.raises(ChainDataError, match="DOGE"):
            await reader.get_funding_rate("DOGE")


# ── Tests: get_market_info ─────────────────────────────────────────────────────


class TestGetMarketInfo:
    async def test_returns_market_fields(self, hl_api: respx.MockRouter) -> None:  # type: ignore[type-arg]
        hl_api.post("/info").mock(return_value=httpx.Response(200, json=_META_AND_ASSET_CTXS))
        reader = HyperliquidReader()
        info = await reader.get_market_info("ETH")
        assert info["asset"] == "ETH"
        assert info["mark_price"] == pytest.approx(3502.0)
        assert info["max_leverage"] == 25
        assert info["funding_rate"] == pytest.approx(-0.00005)
        assert info["mid_price"] == pytest.approx(3501.5)

    async def test_none_mid_price_handled(self, hl_api: respx.MockRouter) -> None:  # type: ignore[type-arg]
        ctxs = [
            {"universe": [{"name": "BTC", "szDecimals": 5, "maxLeverage": 50}]},
            [
                {
                    "funding": "0.0001",
                    "openInterest": "1000",
                    "oraclePx": "65000",
                    "markPx": "65050",
                    "prevDayPx": "64000",
                    "dayNtlVlm": "999",
                }
            ],
        ]
        hl_api.post("/info").mock(return_value=httpx.Response(200, json=ctxs))
        reader = HyperliquidReader()
        info = await reader.get_market_info("BTC")
        assert info["mid_price"] is None


# ── Tests: error handling ──────────────────────────────────────────────────────


class TestErrorHandling:
    async def test_http_500_raises_chain_connection_error(
        self,
        hl_api: respx.MockRouter,  # type: ignore[type-arg]
    ) -> None:
        hl_api.post("/info").mock(return_value=httpx.Response(500, text="Internal Server Error"))
        reader = HyperliquidReader(max_retries=1)
        with pytest.raises(ChainConnectionError):
            await reader.get_user_balance(_WALLET)

    async def test_malformed_meta_response_raises_chain_data_error(
        self,
        hl_api: respx.MockRouter,  # type: ignore[type-arg]
    ) -> None:
        hl_api.post("/info").mock(return_value=httpx.Response(200, json={"bad": "data"}))
        reader = HyperliquidReader()
        with pytest.raises(ChainDataError):
            await reader.get_funding_rate("BTC")

    async def test_implements_onchain_reader_protocol(self) -> None:
        from mirael.chains.base import OnchainReader

        reader = HyperliquidReader()
        assert isinstance(reader, OnchainReader)
