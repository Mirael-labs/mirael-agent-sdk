"""Unit tests for intelligence/ module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from mirael.intelligence.alerts import AlertCondition, AlertEngine
from mirael.intelligence.digest import DigestReport, PortfolioDigest
from mirael.intelligence.whale import WhaleTracker


class TestAlertEngine:
    def test_add_and_remove_condition(self) -> None:
        engine = AlertEngine(chain_reader=MagicMock())
        cond = AlertCondition(
            asset="BTC", metric="price", operator="below",
            threshold=60000, user_id="user1",
        )
        cid = engine.add(cond)
        assert len(engine._conditions) == 1
        assert engine.remove(cid) is True
        assert len(engine._conditions) == 0

    def test_remove_nonexistent_returns_false(self) -> None:
        engine = AlertEngine(chain_reader=MagicMock())
        assert engine.remove("nonexistent") is False

    async def test_check_once_fires_on_condition(self) -> None:
        chain = AsyncMock()
        chain.get_market_info = AsyncMock(return_value={"mark_price": 55000.0})
        engine = AlertEngine(chain_reader=chain)
        cond = AlertCondition(
            asset="BTC", metric="price", operator="below",
            threshold=60000, user_id="user1",
            message_template="{asset} price {value:.0f} < {threshold:.0f}",
        )
        engine.add(cond)
        events = await engine.check_once()
        assert len(events) == 1
        assert events[0].asset == "BTC"
        assert events[0].value == pytest.approx(55000.0)

    async def test_check_once_no_fire_when_ok(self) -> None:
        chain = AsyncMock()
        chain.get_market_info = AsyncMock(return_value={"mark_price": 70000.0})
        engine = AlertEngine(chain_reader=chain)
        cond = AlertCondition(
            asset="BTC", metric="price", operator="below",
            threshold=60000, user_id="user1",
        )
        engine.add(cond)
        events = await engine.check_once()
        assert events == []

    async def test_funding_rate_alert(self) -> None:
        chain = AsyncMock()
        chain.get_funding_rate = AsyncMock(return_value={"rate": 0.001})
        engine = AlertEngine(chain_reader=chain)
        cond = AlertCondition(
            asset="BTC", metric="funding_rate", operator="above",
            threshold=0.0005, user_id="user1",
        )
        engine.add(cond)
        events = await engine.check_once()
        assert len(events) == 1
        assert events[0].severity == "warning"

    def test_stop_sets_running_false(self) -> None:
        engine = AlertEngine(chain_reader=MagicMock())
        engine._running = True
        engine.stop()
        assert engine._running is False


class TestWhaleTracker:
    async def test_scan_wallet_detects_new_large_position(self) -> None:
        chain = AsyncMock()
        chain.get_user_positions = AsyncMock(return_value=[
            {"asset": "BTC", "size": 10.0, "mark_price": 65000.0,
             "size_usd": 650000.0, "unrealized_pnl": 5000.0}
        ])
        tracker = WhaleTracker(chain_reader=chain, min_size_usd=500_000)
        alerts = await tracker.scan_wallet("0xtest")
        assert len(alerts) == 1
        assert alerts[0].asset == "BTC"
        assert alerts[0].action == "opened_long"
        assert alerts[0].size_usd == pytest.approx(650_000.0)

    async def test_small_position_not_flagged(self) -> None:
        chain = AsyncMock()
        chain.get_user_positions = AsyncMock(return_value=[
            {"asset": "ETH", "size": 1.0, "mark_price": 3000.0,
             "size_usd": 3000.0, "unrealized_pnl": 0.0}
        ])
        tracker = WhaleTracker(chain_reader=chain, min_size_usd=500_000)
        alerts = await tracker.scan_wallet("0xtest")
        assert alerts == []

    async def test_stop_sets_running_false(self) -> None:
        tracker = WhaleTracker(chain_reader=MagicMock())
        tracker._running = True
        tracker.stop()
        assert tracker._running is False


class TestPortfolioDigest:
    async def test_generate_empty_portfolio(self) -> None:
        chain = AsyncMock()
        chain.get_user_balance = AsyncMock(return_value={"account_value": 10000.0, "health_factor": 999.0})
        chain.get_user_positions = AsyncMock(return_value=[])
        chain.get_funding_rate = AsyncMock(return_value={"rate": 0.0001})

        llm = AsyncMock()
        from mirael.llm.models import LLMResponse
        llm.chat = AsyncMock(return_value=LLMResponse(
            text="No positions. Portfolio is in cash.", model="claude-sonnet-4-5",
            input_tokens=10, output_tokens=5,
        ))

        digest = PortfolioDigest(chain_reader=chain, llm=llm)
        report = await digest.generate("0xtest")

        assert isinstance(report, DigestReport)
        assert report.positions_count == 0
        assert report.total_pnl == pytest.approx(0.0)
        assert "Portfolio Digest" in report.markdown

    async def test_generate_with_positions(self) -> None:
        chain = AsyncMock()
        chain.get_user_balance = AsyncMock(return_value={
            "account_value": 50000.0, "health_factor": 1.8
        })
        chain.get_user_positions = AsyncMock(return_value=[{
            "asset": "BTC", "size": 0.5, "mark_price": 65000.0,
            "unrealized_pnl": 500.0, "funding_since_open": 10.0,
        }])
        chain.get_funding_rate = AsyncMock(return_value={"rate": 0.0001})

        llm = AsyncMock()
        from mirael.llm.models import LLMResponse
        llm.chat = AsyncMock(return_value=LLMResponse(
            text="BTC long looks healthy.", model="claude-sonnet-4-5",
            input_tokens=20, output_tokens=10,
        ))

        digest = PortfolioDigest(chain_reader=chain, llm=llm)
        report = await digest.generate("0xtest")

        assert report.positions_count == 1
        assert report.total_pnl == pytest.approx(500.0)
        assert "BTC" in report.markdown
