"""
Stress tests for the intelligence/ module.

Tests concurrent alert evaluation, whale tracking, and digest generation.
All mocked — no real API calls.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from mirael.intelligence.alerts import AlertCondition, AlertEngine, AlertEvent
from mirael.intelligence.digest import PortfolioDigest
from mirael.intelligence.governance import GovernanceDigest, GovernanceProposal
from mirael.intelligence.whale import WhaleTracker


def _make_chain(funding_rate: float = 0.0001, price: float = 65000.0) -> AsyncMock:
    chain = AsyncMock()
    chain.get_market_info = AsyncMock(return_value={"mark_price": price, "open_interest": 1e9})
    chain.get_funding_rate = AsyncMock(return_value={"rate": funding_rate})
    chain.get_user_balance = AsyncMock(return_value={"health_factor": 2.0, "account_value": 10000.0})
    chain.get_user_positions = AsyncMock(return_value=[])
    return chain


@pytest.mark.volume
class TestAlertEngineStress:
    async def test_50_conditions_single_cycle(self) -> None:
        """50 conditions evaluated in one check_once() call."""
        chain = _make_chain()
        engine = AlertEngine(chain_reader=chain, poll_interval=999)

        for i in range(50):
            engine.add(AlertCondition(
                asset="BTC" if i % 2 == 0 else "ETH",
                metric="price",
                operator="above",
                threshold=0.0,  # always fires
                user_id=f"user_{i}",
            ))

        t0 = time.monotonic()
        events = await engine.check_once()
        elapsed = time.monotonic() - t0

        assert len(events) == 50
        # 50 mocked calls should complete well under 2 seconds
        assert elapsed < 2.0, f"50 conditions took {elapsed:.2f}s"
        print(f"\n  50 alert conditions: {elapsed*1000:.0f}ms")

    async def test_concurrent_engines(self) -> None:
        """10 independent AlertEngines running check_once() concurrently."""
        engines = []
        for i in range(10):
            chain = _make_chain(price=float(50000 + i * 1000))
            engine = AlertEngine(chain_reader=chain, poll_interval=999)
            engine.add(AlertCondition(
                asset="BTC", metric="price", operator="above",
                threshold=0.0, user_id=f"user_{i}",
            ))
            engines.append(engine)

        t0 = time.monotonic()
        results = await asyncio.gather(*[e.check_once() for e in engines])
        elapsed = time.monotonic() - t0

        assert len(results) == 10
        assert all(len(r) == 1 for r in results)
        assert elapsed < 2.0, f"10 concurrent engines took {elapsed:.2f}s"
        print(f"\n  10 concurrent alert engines: {elapsed*1000:.0f}ms")

    async def test_dedup_prevents_alert_flood(self) -> None:
        """above/below operators fire on every cycle where condition is true."""
        chain = _make_chain(price=55000.0)
        fired: list[AlertEvent] = []

        async def on_alert(e: AlertEvent) -> None:
            fired.append(e)

        engine = AlertEngine(chain_reader=chain, on_alert=on_alert, poll_interval=999)
        engine.add(AlertCondition(
            asset="BTC", metric="price", operator="below",
            threshold=60000.0,  # 55K < 60K → fires
            user_id="user1",
        ))

        # Run 5 cycles
        for _ in range(5):
            await engine.check_once()

        # "above/below" operators fire on every cycle where condition is true
        # For crosses_above/crosses_below it would only fire once
        assert len(fired) == 5  # fires every cycle (expected for "above/below")

    async def test_crosses_fires_only_once(self) -> None:
        """crosses_above should fire only when value crosses the threshold."""
        prices = [50000.0, 58000.0, 62000.0, 65000.0, 63000.0]
        call_idx = [0]

        chain = AsyncMock()

        def get_market_info(asset: str) -> dict:  # type: ignore[return]
            idx = min(call_idx[0], len(prices) - 1)
            call_idx[0] += 1
            return {"mark_price": prices[idx], "open_interest": 1e9}

        chain.get_market_info = AsyncMock(side_effect=get_market_info)

        fired: list[AlertEvent] = []

        async def on_alert(e: AlertEvent) -> None:
            fired.append(e)

        engine = AlertEngine(chain_reader=chain, on_alert=on_alert, poll_interval=999)
        engine.add(AlertCondition(
            asset="BTC", metric="price", operator="crosses_above",
            threshold=60000.0,  # only fires when crossing from below to above
            user_id="user1",
        ))

        for _ in range(5):
            await engine.check_once()

        # Should fire only once: when price crossed from 58K → 62K
        assert len(fired) == 1, f"Expected 1 crossing, got {len(fired)}"


@pytest.mark.volume
class TestWhaleTrackerStress:
    async def test_10_wallets_concurrent(self) -> None:
        """Scan 10 wallets concurrently for whale movements."""
        chain = AsyncMock()
        chain.get_user_positions = AsyncMock(return_value=[{
            "asset": "BTC", "size": 15.0, "mark_price": 65000.0,
            "size_usd": 975_000.0, "unrealized_pnl": 10000.0,
        }])

        tracker = WhaleTracker(chain_reader=chain, min_size_usd=500_000)
        wallets = [f"0x{i:040x}" for i in range(10)]

        t0 = time.monotonic()
        results = await asyncio.gather(*[tracker.scan_wallet(w) for w in wallets])
        elapsed = time.monotonic() - t0

        assert len(results) == 10
        assert all(len(r) == 1 for r in results)
        assert elapsed < 2.0, f"10 wallet scans took {elapsed:.2f}s"
        print(f"\n  10 concurrent whale scans: {elapsed*1000:.0f}ms")

    async def test_position_change_detection(self) -> None:
        """Tracker correctly detects position size changes across scans."""
        call_count = [0]

        chain = AsyncMock()

        def get_positions(wallet: str) -> list:  # type: ignore[return]
            call_count[0] += 1
            if call_count[0] == 1:
                return [{"asset": "ETH", "size": 500.0, "mark_price": 3000.0,
                         "size_usd": 1_500_000.0, "unrealized_pnl": 0.0}]
            return [{"asset": "ETH", "size": 700.0, "mark_price": 3000.0,
                     "size_usd": 2_100_000.0, "unrealized_pnl": 50000.0}]

        chain.get_user_positions = AsyncMock(side_effect=get_positions)

        tracker = WhaleTracker(chain_reader=chain, min_size_usd=500_000)

        # First scan: detects new position
        alerts1 = await tracker.scan_wallet("0xtest")
        assert len(alerts1) == 1
        assert alerts1[0].action == "opened_long"

        # Second scan: detects size increase (>20% change)
        alerts2 = await tracker.scan_wallet("0xtest")
        assert len(alerts2) == 1
        assert alerts2[0].action == "increased"


@pytest.mark.volume
class TestGovernanceDigestStress:
    async def test_summarize_10_proposals_concurrent(self) -> None:
        """Summarize 10 proposals concurrently with mocked LLM."""
        from mirael.llm.models import LLMResponse

        llm = AsyncMock()
        llm.chat = AsyncMock(return_value=LLMResponse(
            text="This proposal adjusts risk parameters. Impact: moderate. Vote: yes.",
            model="claude-sonnet-4-5", input_tokens=50, output_tokens=20,
        ))

        digest = GovernanceDigest(llm=llm, snapshot_spaces=[])
        proposals = [
            GovernanceProposal(
                proposal_id=f"prop-{i}",
                title=f"Proposal {i}: Adjust parameter X",
                space="aave.eth",
                body=f"This proposal changes parameter X to value {i}.",
                start=time.time() - 3600,
                end=time.time() + 86400,
                state="active",
            )
            for i in range(10)
        ]

        t0 = time.monotonic()
        results = await asyncio.gather(*[digest.summarize(p) for p in proposals])
        elapsed = time.monotonic() - t0

        assert len(results) == 10
        assert all(r.summary for r in results)
        assert all(r.discord_message for r in results)
        assert elapsed < 2.0, f"10 concurrent summaries took {elapsed:.2f}s"
        print(f"\n  10 concurrent governance summaries: {elapsed*1000:.0f}ms")


@pytest.mark.volume
class TestDigestStress:
    async def test_5_concurrent_digests(self) -> None:
        """Generate 5 digests concurrently with mocked services."""
        from mirael.llm.models import LLMResponse

        chain = _make_chain()
        llm = AsyncMock()
        llm.chat = AsyncMock(return_value=LLMResponse(
            text="Portfolio looks stable. No immediate risks.",
            model="claude-sonnet-4-5", input_tokens=30, output_tokens=10,
        ))

        wallets = [f"0x{i:040x}" for i in range(5)]

        async def gen(wallet: str) -> None:
            digest = PortfolioDigest(chain_reader=chain, llm=llm)
            await digest.generate(wallet)

        t0 = time.monotonic()
        await asyncio.gather(*[gen(w) for w in wallets])
        elapsed = time.monotonic() - t0

        assert elapsed < 3.0, f"5 concurrent digests took {elapsed:.2f}s"
        print(f"\n  5 concurrent portfolio digests: {elapsed*1000:.0f}ms")

    async def test_digest_markdown_structure(self) -> None:
        """Generated markdown has expected structure."""
        from mirael.llm.models import LLMResponse

        chain = _make_chain()
        chain.get_user_positions = AsyncMock(return_value=[
            {"asset": "BTC", "size": 0.5, "mark_price": 65000.0,
             "unrealized_pnl": 500.0, "funding_since_open": 5.0}
        ])
        chain.get_user_balance = AsyncMock(return_value={
            "account_value": 50000.0, "health_factor": 1.8,
        })

        llm = AsyncMock()
        llm.chat = AsyncMock(return_value=LLMResponse(
            text="BTC long looks healthy at current levels.",
            model="claude-sonnet-4-5", input_tokens=25, output_tokens=10,
        ))

        digest = PortfolioDigest(chain_reader=chain, llm=llm)
        report = await digest.generate("0xtest")

        assert "Daily Portfolio Digest" in report.markdown
        assert "BTC" in report.markdown
        assert "AI Commentary" in report.markdown
        assert report.positions_count == 1
        assert report.total_pnl == pytest.approx(500.0)
