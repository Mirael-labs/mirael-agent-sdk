"""
E2E tests for the intelligence/ module against real services.

- AlertEngine: real Hyperliquid funding rates
- WhaleTracker: real wallet scan (no actual whales needed — just tests the pipeline)
- GovernanceDigest: real Snapshot GraphQL API
- PortfolioDigest: real Anthropic + Hyperliquid
"""

from __future__ import annotations

import time

import pytest

from mirael.chains.hyperliquid import HyperliquidReader
from mirael.intelligence.alerts import AlertCondition, AlertEngine
from mirael.intelligence.governance import GovernanceDigest
from mirael.intelligence.whale import WhaleTracker


@pytest.mark.e2e
class TestAlertEngineE2E:
    async def test_funding_rate_condition_evaluates(self) -> None:
        """AlertEngine fetches real BTC funding rate from Hyperliquid."""
        async with HyperliquidReader() as reader:
            engine = AlertEngine(chain_reader=reader, poll_interval=999)
            cond = AlertCondition(
                asset="BTC",
                metric="funding_rate",
                operator="above",
                threshold=-999.0,  # always true — any rate > -999
                user_id="e2e_test",
                message_template="BTC funding: {value:.6f}",
            )
            engine.add(cond)
            events = await engine.check_once()

        # Should have fired (rate > -999 is always true)
        assert len(events) == 1
        assert events[0].asset == "BTC"
        assert isinstance(events[0].value, float)

    async def test_price_condition_evaluates(self) -> None:
        """Price condition fetches real BTC mark price."""
        async with HyperliquidReader() as reader:
            engine = AlertEngine(chain_reader=reader, poll_interval=999)
            cond = AlertCondition(
                asset="ETH",
                metric="price",
                operator="above",
                threshold=0.0,  # always true
                user_id="e2e_test",
            )
            engine.add(cond)
            events = await engine.check_once()

        assert len(events) == 1
        assert events[0].value > 0

    async def test_multiple_conditions_concurrent(self) -> None:
        """Multiple conditions evaluated in one cycle."""
        async with HyperliquidReader() as reader:
            engine = AlertEngine(chain_reader=reader, poll_interval=999)
            for asset in ["BTC", "ETH", "SOL"]:
                engine.add(AlertCondition(
                    asset=asset,
                    metric="funding_rate",
                    operator="above",
                    threshold=-999.0,
                    user_id="e2e_test",
                ))

            t0 = time.monotonic()
            events = await engine.check_once()
            elapsed = time.monotonic() - t0

        assert len(events) == 3
        # 3 conditions should complete in under 10 seconds
        assert elapsed < 10.0, f"3 conditions took {elapsed:.2f}s"

    async def test_condition_latency(self) -> None:
        """Single condition check should complete in under 3 seconds."""
        async with HyperliquidReader() as reader:
            engine = AlertEngine(chain_reader=reader, poll_interval=999)
            engine.add(AlertCondition(
                asset="BTC",
                metric="price",
                operator="above",
                threshold=0.0,
                user_id="e2e_test",
            ))

            t0 = time.monotonic()
            await engine.check_once()
            elapsed = time.monotonic() - t0

        assert elapsed < 3.0, f"Alert check took {elapsed:.2f}s"


@pytest.mark.e2e
class TestWhaleTrackerE2E:
    async def test_scan_wallet_no_crash(self) -> None:
        """Whale tracker scans a wallet without crashing."""
        async with HyperliquidReader() as reader:
            tracker = WhaleTracker(
                chain_reader=reader,
                min_size_usd=1_000_000,  # high threshold — probably no alerts
            )
            # Use a known public address (zero address — likely has no positions)
            alerts = await tracker.scan_wallet(
                "0x0000000000000000000000000000000000000000"
            )
        # May or may not have alerts — just shouldn't crash
        assert isinstance(alerts, list)

    async def test_tracker_detects_large_position(self) -> None:
        """With low threshold, any position triggers alert (tests detection logic)."""
        from unittest.mock import AsyncMock

        chain = AsyncMock()
        chain.get_user_positions = AsyncMock(return_value=[{
            "asset": "BTC",
            "size": 10.0,
            "mark_price": 65000.0,
            "size_usd": 650_000.0,
            "unrealized_pnl": 5000.0,
        }])

        tracker = WhaleTracker(chain_reader=chain, min_size_usd=500_000)
        alerts = await tracker.scan_wallet("0xtest_wallet")

        assert len(alerts) == 1
        assert alerts[0].asset == "BTC"
        assert alerts[0].size_usd == pytest.approx(650_000.0)


@pytest.mark.e2e
class TestGovernanceDigestE2E:
    async def test_fetch_arbitrum_proposals(self, settings) -> None:
        """Fetch real Arbitrum DAO proposals from Snapshot."""
        from mirael.llm.anthropic import AnthropicLLM

        llm = AnthropicLLM(
            api_key=settings.anthropic_api_key.get_secret_value(),
            model=settings.llm_model,
            max_tokens=200,
        )
        digest = GovernanceDigest(llm=llm, snapshot_spaces=["arbitrumfoundation.eth"])
        proposals = await digest.fetch_active()

        # Arbitrum DAO usually has some active proposals
        # If none active, test that fetch doesn't crash
        assert isinstance(proposals, list)
        for p in proposals:
            assert p.title
            assert p.space == "arbitrumfoundation.eth"
            assert p.end > 0

    async def test_fetch_multiple_spaces(self, settings) -> None:
        """Fetch from multiple Snapshot spaces without errors."""
        from mirael.llm.anthropic import AnthropicLLM

        llm = AnthropicLLM(
            api_key=settings.anthropic_api_key.get_secret_value(),
            model=settings.llm_model,
        )
        digest = GovernanceDigest(
            llm=llm,
            snapshot_spaces=["aave.eth", "arbitrumfoundation.eth"],
        )
        proposals = await digest.fetch_active()
        assert isinstance(proposals, list)

    async def test_summarize_with_real_claude(self, settings) -> None:
        """Summarize a sample proposal with real Claude API."""
        from mirael.intelligence.governance import GovernanceProposal
        from mirael.llm.anthropic import AnthropicLLM

        llm = AnthropicLLM(
            api_key=settings.anthropic_api_key.get_secret_value(),
            model=settings.llm_model,
            max_tokens=300,
        )
        digest = GovernanceDigest(llm=llm)

        sample = GovernanceProposal(
            proposal_id="test-001",
            title="Increase ARB collateral factor from 56% to 62%",
            space="aave.eth",
            body=(
                "This proposal aims to increase the LTV of ARB token on Aave V3 Arbitrum "
                "from 56% to 62%. This allows ARB holders to borrow more USDC against their "
                "ARB collateral. Risk analysis shows ARB has maintained low correlation with "
                "liquidation cascades in the past 6 months."
            ),
            start=time.time() - 3600,
            end=time.time() + 86400 * 3,  # 3 days from now
            state="active",
        )

        result = await digest.summarize(sample)

        assert result.summary  # should have AI summary
        assert len(result.summary) > 20
        assert result.discord_message
        assert "ARB" in result.discord_message or "collateral" in result.summary.lower()


@pytest.mark.e2e
class TestPortfolioDigestE2E:
    async def test_generate_with_real_services(self, settings) -> None:
        """Generate a full digest with Hyperliquid + Claude."""
        from mirael.intelligence.digest import PortfolioDigest
        from mirael.llm.anthropic import AnthropicLLM

        llm = AnthropicLLM(
            api_key=settings.anthropic_api_key.get_secret_value(),
            model=settings.llm_model,
            max_tokens=200,
        )

        async with HyperliquidReader() as reader:
            digest = PortfolioDigest(chain_reader=reader, llm=llm)
            # Use test wallet (likely has no positions — graceful empty case)
            report = await digest.generate(
                wallet="0x65bf83b7B8B3370bf2Dc59cdF95BfE221d064Fc2"
            )

        assert report.wallet == "0x65bf83b7B8B3370bf2Dc59cdF95BfE221d064Fc2"
        assert "Portfolio Digest" in report.markdown
        assert isinstance(report.total_pnl, float)
        # Empty portfolio short-circuits to a static string — no LLM call needed
        assert report.ai_commentary

    async def test_digest_latency(self, settings) -> None:
        """Full digest generation should complete under 30 seconds."""
        from mirael.intelligence.digest import PortfolioDigest
        from mirael.llm.anthropic import AnthropicLLM

        llm = AnthropicLLM(
            api_key=settings.anthropic_api_key.get_secret_value(),
            model=settings.llm_model,
            max_tokens=100,
        )

        t0 = time.monotonic()
        async with HyperliquidReader() as reader:
            digest = PortfolioDigest(chain_reader=reader, llm=llm)
            await digest.generate(wallet="0x65bf83b7B8B3370bf2Dc59cdF95BfE221d064Fc2")
        elapsed = time.monotonic() - t0

        assert elapsed < 30.0, f"Digest took {elapsed:.2f}s"
